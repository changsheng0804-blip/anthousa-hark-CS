"""CS 线 · 性能余量：在街巷级最密处做 A/B（有/无史诗叠层），并用 CDP Profiler 拆每帧时间花在哪个函数上。
python3 tools/cs/prof_tiles.py → tiles/prof.json。沙箱 arm64 无 GPU（SwiftShader），绝对值悲观，看占比。"""
import json, os, sys, threading, http.server, socketserver, functools, collections
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
FPS = "ms=>new Promise(r=>{let n=0,t0=performance.now(),w=0,l=t0,g=[];function f(t){n++;g.push(t-l);w=Math.max(w,t-l);l=t;if(t-t0<ms)requestAnimationFrame(f);else{g.sort((a,b)=>a-b);r({fps:+(n*1000/(t-t0)).toFixed(1),worst_ms:+w.toFixed(0),p50_ms:+g[g.length>>1].toFixed(1)})}}requestAnimationFrame(f)})"
VD = os.path.join(ROOT, 'docs', 'living', 'tiles', 'vec')
fn = max(os.listdir(VD), key=lambda f: len(json.load(open(os.path.join(VD, f)))['h'])); tx, ty = map(int, fn[:-5].split('_'))
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-precise-memory-info', '--no-sandbox'])
    for tag in ('有史诗', '无史诗', '有史诗#2', '无史诗#2'):
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        if tag.startswith('无'): pg.route('**/ep.json', lambda r: r.fulfill(status=404, body=''))
        pg.goto(url, wait_until='networkidle'); M = pg.evaluate("()=>__TILES.M"); tp = M['tile_px']
        pg.evaluate("([x,y])=>{const T=__TILES;T.setYear(60);T.cam.x=x;T.cam.y=y;T.cam.z=T.STREET_Z*1.3;T.zoomAt(innerWidth/2,innerHeight/2,1)}", [(tx + .5) * tp, (ty + .5) * tp])
        pg.wait_for_timeout(4000)
        r = pg.evaluate(FPS, 4000); r['ep'] = pg.evaluate("()=>window.__EP?__EP.drawn:0")
        r['walkers'] = pg.evaluate("()=>__TILES.LIFE.walkers"); r['houses'] = pg.evaluate("()=>__TILES.hdrawn")
        if tag == '有史诗':
            cdp = pg.context.new_cdp_session(pg); cdp.send('Profiler.enable'); cdp.send('Profiler.setSamplingInterval', {'interval': 200}); cdp.send('Profiler.start')
            pg.wait_for_timeout(4000); prof = cdp.send('Profiler.stop')['profile']
            dt = prof['timeDeltas']; cnt = collections.Counter(prof['samples']); tot = sum(cnt.values())
            byid = {n['id']: n for n in prof['nodes']}; self_ = collections.Counter()
            for i, c in cnt.items(): fr = byid[i]['callFrame']; self_[fr['functionName'] or '(' + fr['url'][-20:] + ')'] += c
            # 归到每帧的顶层子函数：累计（含子调用）时间
            parent = {}
            for n in prof['nodes']:
                for ch in n.get('children', []): parent[ch] = n['id']
            incl = collections.Counter()
            for i, c in cnt.items():
                seen = set(); j = i
                while j is not None:
                    nm = byid[j]['callFrame']['functionName']
                    if nm and nm not in seen: incl[nm] += c; seen.add(nm)
                    j = parent.get(j)
            r['self_top'] = [(k, round(100 * v / tot, 1)) for k, v in self_.most_common(14)]
            r['incl_top'] = [(k, round(100 * v / tot, 1)) for k, v in incl.most_common(22)]
        out[tag] = r; print(tag, json.dumps(r, ensure_ascii=False)[:1500], flush=True); pg.close()
    b.close()
json.dump(out, open(os.path.join(ROOT, 'docs', 'living', 'tiles', 'prof.json'), 'w'), ensure_ascii=False, indent=1)
