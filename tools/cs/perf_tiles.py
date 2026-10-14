"""CS 线 · cs36 真浏览器压力测（Chromium + Playwright）：全城瓦片页的首屏下载、帧率、内存。
python3 tools/cs/perf_tiles.py [url]   默认起本地服务器读 docs/living/tiles/
场景：全城一屏 → 推到街巷级最密的地方 → 街巷级横穿全城 10 秒 → 换年份 → 拉回全城；
/goal 2 项 7 加三个：从全城飞到门口（南港门口，z=4.5 倾斜带）、门口飞到另一块街区（第四丘门口，z=4.5）、倾斜带里平移 6 秒。
飞行场景的 FPS = 飞行期间（flyTo 起到落地）rAF 实测的平均，worst_ms = 其间最长一帧；G5 线：平均 ≥50 FPS、最差一帧 ≤50 ms。每段记 FPS（rAF 实测）、JS 堆、累计请求数和字节。
注意：沙箱是 arm64、无 GPU（SwiftShader 软件渲染），帧率是悲观值，看相对变化和有没有掉坑。"""
import json, os, sys, time, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
url = sys.argv[1] if len(sys.argv) > 1 else None
if not url:
    H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, 'docs', 'living'))
    import gzip, io
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        # /goal 4 项 1b：GitHub Pages 对 json/js/html 发 gzip（实测 vec/1_9.json 794501→154591 字节），本地服务器也照样压，
        # 才量得出用户真实下载；未压的原始体积另记 mb_raw（解析/堆的压力看原始体积）
        def send_head(self):
            path = self.translate_path(self.path)
            if os.path.isfile(path) and path.endswith(('.json', '.js', '.html')) and 'gzip' in self.headers.get('Accept-Encoding', ''):
                data = gzip.compress(open(path, 'rb').read(), 6)
                self.send_response(200); self.send_header('Content-Type', self.guess_type(path)); self.send_header('Content-Encoding', 'gzip')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); return io.BytesIO(data)
            return super().send_head()
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
FPS_JS = """ms=>new Promise(r=>{let n=0,t0=performance.now(),worst=0,last=t0;function f(t){n++;worst=Math.max(worst,t-last);last=t;if(t-t0<ms)requestAnimationFrame(f);else r({fps:+(n*1000/(t-t0)).toFixed(1),worst_ms:+worst.toFixed(0)})}requestAnimationFrame(f)})"""
out = {'url': url, 'steps': []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-precise-memory-info', '--no-sandbox'])
    pg = b.new_page(viewport={'width': 1440, 'height': 900})
    net = {'n': 0, 'bytes': 0, 'raw': 0}
    def onresp(r):
        try:
            l = int(r.headers.get('content-length') or 0) or len(r.body())
            raw = len(r.body()) if r.headers.get('content-encoding') == 'gzip' else l
        except Exception: l = raw = 0
        net['n'] += 1; net['bytes'] += l; net['raw'] += raw
    pg.on('response', onresp)
    t0 = time.time(); pg.goto(url, wait_until='networkidle'); first = time.time() - t0
    def step(name, ms=3000):
        pg.wait_for_timeout(800)
        f = pg.evaluate(FPS_JS, ms)
        m = pg.evaluate("()=>({heap_mb:+(performance.memory.usedJSHeapSize/1048576).toFixed(1),drawn:__TILES.drawn,houses:__TILES.hdrawn,walkers:__TILES.LIFE.walkers,ships:__TILES.LIFE.ships,cache:__TILES.cache.size,vtiles:__TILES.vtiles.size})")
        r = dict(step=name, **f, **m, requests=net['n'], mb=round(net['bytes'] / 1048576, 2), mb_raw=round(net['raw'] / 1048576, 2)); out['steps'].append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
    step('全城一屏（首屏 %.1fs）' % first)
    # 推到街巷级：选房子最多的矢量块
    M = pg.evaluate("()=>__TILES.M")
    tp = M['tile_px']; VD = os.path.join(ROOT, 'docs', 'living', 'tiles', 'vec')
    fn = max(os.listdir(VD), key=lambda f: len(json.load(open(os.path.join(VD, f)))['h'])); tx, ty = map(int, fn[:-5].split('_'))
    best = [(tx + 0.5) * tp, (ty + 0.5) * tp]
    pg.evaluate("([x,y])=>{const T=__TILES;T.cam.x=x;T.cam.y=y;T.cam.z=T.STREET_Z*1.3;T.zoomAt(innerWidth/2,innerHeight/2,1)}", [best[0] if best else M['grid'][0] * tp / 2, best[1] if best else M['grid'][1] * tp / 2])
    step('街巷级最密处')
    # 横穿：10 秒从西到东
    W0 = M['grid'][0] * tp
    pg.evaluate("""([W0])=>{const T=__TILES;window.__pan=true;const t0=performance.now(),x0=W0*0.1,x1=W0*0.9;(function f(){if(!window.__pan)return;const k=Math.min(1,(performance.now()-t0)/10000);T.cam.x=x0+(x1-x0)*k;T.zoomAt(innerWidth/2,innerHeight/2,1);if(k<1)requestAnimationFrame(f)})()}""", [W0])
    pg.wait_for_timeout(200); f = pg.evaluate(FPS_JS, 9500)
    m = pg.evaluate("()=>({heap_mb:+(performance.memory.usedJSHeapSize/1048576).toFixed(1),cache:__TILES.cache.size,vtiles:__TILES.vtiles.size,walkers:__TILES.LIFE.walkers})")
    r = dict(step='街巷级横穿全城 10 秒', **f, **m, requests=net['n'], mb=round(net['bytes'] / 1048576, 2), mb_raw=round(net['raw'] / 1048576, 2)); out['steps'].append(r); print(json.dumps(r, ensure_ascii=False))
    pg.evaluate("()=>{window.__pan=false;__TILES.setYear(40)}"); step('换到 40 年')
    pg.evaluate("()=>{const T=__TILES;T.cam.z=0.08;T.zoomAt(innerWidth/2,innerHeight/2,1)}"); step('拉回全城')
    # ── /goal 2 项 7：飞行场景。FPS 只量飞行期间；落地后的等待（hold）另记
    FLY_JS = """async([x,y,z,yr])=>{const T=__TILES;let n=0,worst=0,last=performance.now(),run=true,gaps=[],big=[];const t0=last;
      const f=t=>{if(!run)return;n++;const g=t-last;worst=Math.max(worst,g);gaps.push(g);if(g>40)big.push([Math.round(t-t0),Math.round(g),+T.cam.z.toFixed(2)]);last=t;requestAnimationFrame(f)};requestAnimationFrame(f);
      const r=await T.flyTo(x,y,z,{year:yr});run=false;const el=performance.now()-t0;gaps.sort((a,b)=>a-b);
      return {fps:+(n*1000/el).toFixed(1),worst_ms:+worst.toFixed(0),p99_ms:+gaps[Math.floor(gaps.length*.99)].toFixed(0),dur:r.dur,hold:r.hold,frames:n,big,tilt_deg:+(T.tilt*57.2958).toFixed(1)}}"""
    P = json.load(open(os.path.join(ROOT, 'docs', 'living', 'tiles', 'places.json'))); QC = {c['q']: c for c in P['quarters']}
    def fly(name, q, z=4.5):
        c = QC[q]; pg.wait_for_timeout(800)
        f = pg.evaluate(FLY_JS, [c['x'], c['y'], z, 60])
        m = pg.evaluate("()=>({heap_mb:+(performance.memory.usedJSHeapSize/1048576).toFixed(1),houses:__TILES.hdrawn,walkers:__TILES.LIFE.walkers,cache:__TILES.cache.size,vtiles:__TILES.vtiles.size})")
        r = dict(step=name, **f, **m, requests=net['n'], mb=round(net['bytes'] / 1048576, 2), mb_raw=round(net['raw'] / 1048576, 2)); out['steps'].append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
    pg.evaluate("()=>{const T=__TILES;T.cam.z=0.08;T.zoomAt(innerWidth/2,innerHeight/2,1);T.setYear(60)}"); pg.wait_for_timeout(1500)
    fly('飞行：全城→南港门口（z=4.5 倾斜）', 'nangang')
    fly('飞行：南港门口→第四丘门口（z=4.5）', 'siqiu')
    pg.wait_for_timeout(800)
    pg.evaluate("""()=>{const T=__TILES;window.__pan=true;const t0=performance.now(),x0=T.cam.x,y0=T.cam.y;(function f(){if(!window.__pan)return;const k=Math.min(1,(performance.now()-t0)/6000);T.cam.x=x0+450*k;T.cam.y=y0-120*k;T.zoomAt(innerWidth/2,innerHeight/2,1);if(k<1)requestAnimationFrame(f)})()}""")
    pg.wait_for_timeout(200); f = pg.evaluate(FPS_JS, 5600); pg.evaluate("()=>{window.__pan=false}")
    r = dict(step='倾斜带平移 6 秒（z=4.5）', **f, tilt_deg=pg.evaluate("()=>+(__TILES.tilt*57.2958).toFixed(1)"), houses=pg.evaluate("()=>__TILES.hdrawn"), requests=net['n'], mb=round(net['bytes'] / 1048576, 2), mb_raw=round(net['raw'] / 1048576, 2)); out['steps'].append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
    b.close()
json.dump(out, open(os.path.join(ROOT, 'docs', 'living', 'tiles', 'perf.json'), 'w'), ensure_ascii=False, indent=1)
