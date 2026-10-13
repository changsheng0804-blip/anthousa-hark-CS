"""CS 线 · /goal 2 G4 检查（项 6）：最后一段镜头微倾，房子立起来，倾角随缩放连续变。
python3 tools/cs/check_tilt.py [--url URL] [--index 某个 index.html（拿旧版本来证明“修前不过”）]
  ① 页面有 __TILES.tilt / tiltOf / UPR：倾角是缩放的函数；
  ② 倾角曲线：z·dpr ≤ 2.3 时为 0；单调不减；z 每乘 1.01 倾角最多变 0.7°（连续，不跳）；z=6 时 ≥ 30°；
  ③ 画布几何：未倾时 H=Hv 且 CSS 无压扁；倾时 H·cos(a)=Hv，CSS 的 scaleY 就是 Hv/H（画布按最大倾角分配，不重配）；
  ④ 指针：倾斜里滚轮缩放时光标下的那个世界点不漂（≤2 px）；拖一下地面，抓住的那点跟着光标（≤2 px）；
  ⑤ 点房子：倾斜里真点屏幕上的房子，卡片弹出；
  ⑥ 房子立起来：倾斜里每栋站着的房子都有立起来的贴图（miss=0），没有品红探针色漏出，退出倾斜（z=1）后贴图不再画、画布不压扁。
沙箱用 apt 的 chromium，本地起服务器。——Hark（CS线）"""
import json, os, sys, time, math, threading, http.server, socketserver, functools, argparse
import numpy as np, cv2
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--url'); ap.add_argument('--index'); ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/tilt'))
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
if not A.url:
    idx = open(A.index, 'rb').read() if A.index else None
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if idx is not None and self.path.split('?')[0] in ('/tiles/', '/tiles/index.html'):
                self.send_response(200); self.send_header('content-type', 'text/html; charset=utf-8'); self.send_header('content-length', str(len(idx))); self.end_headers(); self.wfile.write(idx); return
            super().do_GET()
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
else: url = A.url
M = json.load(open(os.path.join(ROOT, 'docs/living/tiles/meta.json')))
sc = json.load(open(os.path.join(ROOT, 'docs/living/nangang/scene.json'))); ox, oy = M['quarters']['nangang'][:2]; F = sc.get('fleet') or {}
door = (1589, 4328)
fails = []
def ck(name, ok, info=''):
    print(('  ok  ' if ok else ' FAIL ') + name + ('  ' + str(info) if info != '' else ''))
    if not ok: fails.append(name)
VW, VH = 1000, 640
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox']); pg = b.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=1)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    def probe(route):
        r = route.fetch(); body = r.text() if not A.index else open(A.index, encoding='utf-8').read()
        body = body.replace("fillStyle='#cdb68c'", "fillStyle='#ff00ff'")
        route.fulfill(response=r, body=body, headers={**r.headers, 'content-type': 'text/html; charset=utf-8'})
    pg.route('**/tiles/', probe); pg.route('**/tiles/index.html', probe)
    pg.goto(url, wait_until='networkidle'); pg.wait_for_function('()=>window.__TILES')
    has = pg.evaluate("()=>typeof __TILES.tiltOf==='function'&&typeof __TILES.tilt==='number'&&!!__TILES.UPR")
    ck('① __TILES.tilt / tiltOf / UPR 存在', has)
    if not has:
        print('❌ 倾斜未实现'); sys.exit(1)
    pg.evaluate("Y=>__TILES.setYear(Y)", 60); time.sleep(1.0)
    # ② 曲线
    zs = [0.05 * 1.01 ** i for i in range(int(math.log(6 / 0.05) / math.log(1.01)) + 1)]
    ts = pg.evaluate("zs=>zs.map(z=>__TILES.tiltOf(z)*180/Math.PI)", zs); dpr = pg.evaluate("devicePixelRatio")
    ck('② z·dpr ≤ 2.3 时倾角为 0', all(t == 0 for z, t in zip(zs, ts) if z * dpr <= 2.3), max(t for z, t in zip(zs, ts) if z * dpr <= 2.3))
    ck('② 倾角单调不减', all(b2 >= a - 1e-9 for a, b2 in zip(ts, ts[1:])))
    ck('② z 每乘 1.01 倾角最多变 0.7°', max(b2 - a for a, b2 in zip(ts, ts[1:])) <= 0.7, round(max(b2 - a for a, b2 in zip(ts, ts[1:])), 3))
    ck('② z=6 时倾角 ≥ 30°', ts[-1] >= 30, round(ts[-1], 1))
    # ③ 几何
    G = "()=>{const c=document.getElementById('c');return {H:__TILES.H,Hv:__TILES.Hv,t:__TILES.tilt,tr:c.style.transform,ch:c.height,dpr:devicePixelRatio}}"
    def settle(x, y, z):
        pg.evaluate("([x,y,z])=>{const T=__TILES;T.cancelFly();T.cam.x=x;T.cam.y=y;T.cam.z=z;T.zoomAt(innerWidth/2,innerHeight/2,1)}", [x, y, z]); time.sleep(2.2)
    settle(*door, 1.0); g = pg.evaluate(G)
    ck('③ z=1：H=Hv，CSS 不压扁', abs(g['H'] - g['Hv']) < 1e-6 and g['tr'] in ('scaleY(1)', ''), g['tr'])
    settle(*door, 5.0); g = pg.evaluate(G)
    ck('③ z=5：H·cos(a)=Hv', abs(g['H'] * math.cos(g['t']) - g['Hv']) < 1e-3, f"H={g['H']:.1f} a={math.degrees(g['t']):.1f}°")
    ck('③ z=5：CSS scaleY = Hv/H', abs(float(g['tr'][7:-1]) - g['Hv'] / g['H']) < 1e-6, g['tr'])
    ck('③ 画布够大（按最大倾角分配）', g['ch'] >= g['Hv'] / math.cos(math.radians(36)) * g['dpr'] - 2, g['ch'])
    # ④ 指针
    settle(*door, 3.4)
    W_ = "(sx,sy)=>{const T=__TILES;const f=sy*T.H/T.Hv;return [T.cam.x+(sx-innerWidth/2)/T.cam.z,T.cam.y+(f-T.H/2)/T.cam.z]}"
    sx, sy = 760, 470; w0 = pg.evaluate(f"([a,b])=>({W_})(a,b)", [sx, sy])
    for _ in range(12): pg.evaluate("([a,b])=>__TILES.zoomAt(a,b,1.03)", [sx, sy]); time.sleep(0.05)
    time.sleep(0.4); sp = pg.evaluate("([x,y])=>__TILES.heart.card.screen(x,y)", w0)
    ck('④ 倾斜里缩放：光标下的点不漂', abs(sp[0] - sx) <= 2 and abs(sp[1] - sy) <= 2, f"漂 {sp[0] - sx:.1f},{sp[1] - sy:.1f} px")
    w1 = pg.evaluate(f"([a,b])=>({W_})(a,b)", [600, 300]); pg.mouse.move(600, 300); pg.mouse.down(); pg.mouse.move(640, 380, steps=6); pg.mouse.up(); time.sleep(0.3)
    sp = pg.evaluate("([x,y])=>__TILES.heart.card.screen(x,y)", w1)
    ck('④ 拖地面：抓住的点跟着光标', abs(sp[0] - 640) <= 2 and abs(sp[1] - 380) <= 2, f"差 {sp[0] - 640:.1f},{sp[1] - 380:.1f} px")
    # ⑤ 点房子
    settle(*door, 4.2); hs = pg.evaluate("()=>__TILES.heart.card.houses('nangang')") if pg.evaluate("()=>!!__TILES.heart") else []
    t0 = time.time()
    while not hs and time.time() - t0 < 30: time.sleep(0.5); hs = pg.evaluate("()=>__TILES.heart.card.houses('nangang')")
    got = False; info = len(hs)
    hs.sort(key=lambda t: (t[1] - door[0]) ** 2 + (t[2] - door[1]) ** 2)
    for hid, x, y in hs[:14]:
        s2 = pg.evaluate("([x,y])=>__TILES.heart.card.screen(x,y)", [x, y])
        if not (60 < s2[0] < VW - 60 and 60 < s2[1] < VH - 60): continue
        pg.mouse.click(*s2); time.sleep(0.3)
        if pg.evaluate("()=>__TILES.heart.card.shown"): got = True; info = hid; break
    ck('⑤ 倾斜里点房子：卡片弹出', got, info)
    if got: pg.click('#cardx'); time.sleep(0.2)
    rp = pg.evaluate("()=>__TILES.roofPts(10)"); got2 = 0
    for wx_, wy_, sx_, sy_ in rp:
        if not (60 < sx_ < VW - 60 and 60 < sy_ < VH - 60): continue
        pg.mouse.click(sx_, sy_); time.sleep(0.3)
        if pg.evaluate("()=>__TILES.heart.card.shown"): got2 += 1; pg.click('#cardx'); time.sleep(0.2)
    nin = sum(1 for r_ in rp if 60 < r_[2] < VW - 60 and 60 < r_[3] < VH - 60)
    ck('⑤ 点立起来的屋顶：卡片弹出（屋顶点离脚印很远，也要中）', nin >= 3 and got2 >= nin - 1, f'{got2}/{nin}')
    # ⑥ 立起来
    settle(*door, 5.0); time.sleep(1.5); u = pg.evaluate("()=>({n:__TILES.UPR.n,of:__TILES.UPR.of,miss:__TILES.UPR.miss,built:__TILES.sprBuilt})")
    ck('⑥ 倾斜里房子都有立起来的贴图', u['of'] > 20 and u['miss'] == 0 and u['n'] == u['of'], u)
    img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_COLOR); cv2.imwrite(os.path.join(A.out, 'tilt5.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    mag = (np.abs(img.astype(np.int16) - np.array([255, 0, 255], np.int16)).max(axis=2) <= 8).sum()
    ck('⑥ 画面里没有品红探针色漏出', mag == 0, int(mag))
    settle(*door, 1.0); u = pg.evaluate("()=>({n:__TILES.UPR.n,tilt:__TILES.tilt})"); g = pg.evaluate(G)
    ck('⑥ 退出倾斜：贴图不画、画布不压扁', u['n'] == 0 and u['tilt'] == 0 and abs(g['H'] - g['Hv']) < 1e-6, u)
    ck('页面无报错', not errs, errs[:2])
    b.close()
print(('✅ 微倾检查全过' if not fails else f'❌ {len(fails)} 项不过：' + '；'.join(fails)))
sys.exit(0 if not fails else 1)
