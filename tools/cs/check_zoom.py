"""CS 线 · /goal 2 G1 检查：从全城一路推到一户人家门口，200 步、每步截帧。
python3 tools/cs/check_zoom.py [--steps 200] [--out tools/cs/factory/out/zoom]
  空白：测试时把页面的清屏底色 #cdb68c 换成探针色品红 #ff00ff（只在测试里换，线上不动），
        数屏幕上落在「有瓦片的世界格」里、整块是品红的 8×8 像素块（世界外、本来就没瓦片的格不算；瓦片里烤进去的底色不算空白）。
  跳变：把上一帧按这一步的缩放倍数绕屏幕中心放大，和这一帧比中间 60% 的灰度平均差（MAD，0–255）；
        正常连续缩放只有画面细节和行人带来的小差，分级切换、换底图、闪白会冲高。
  达标线（GOAL.md G1）：空白块 0；跳变不许冒尖——每一步的 MAD 不超过 max(1.0, 1.5 × 前后各 5 步的中位数)，且绝对值 ≤ JUMP（默认 8）。
        冒尖就是分级切换被眼睛看见的那一下（cs36 现状：级 3→2、2→1、1→0、换街巷级四处都冒尖）。
每步只等两帧 rAF 就截图——就是用户滚轮时眼睛看到的样子，不给页面额外的加载时间。
沙箱 arm64 无 GPU，用 apt 的 chromium；浏览器访问不到 github.io，所以本地起服务器。——Hark（CS线）"""
import json, os, sys, threading, http.server, socketserver, functools, argparse
import numpy as np, cv2
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--steps', type=int, default=200); ap.add_argument('--jump', type=float, default=8.0)
ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/zoom')); ap.add_argument('--url'); ap.add_argument('--target', default='nangang')
ap.add_argument('--year', type=int, default=60); ap.add_argument('--zmax', type=float, default=6.0)
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
url = A.url
if not url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
TD = os.path.join(ROOT, 'docs/living/tiles'); M = json.load(open(os.path.join(TD, 'meta.json'))); TP = M['tile_px']
have = {tuple(map(int, f[:-5].split('_'))) for f in os.listdir(os.path.join(TD, str(A.year), '0'))}
# 门口：目标街区里房子最多的那块矢量瓦片里，离瓦片中心最近的一栋房子
qx, qy, qw, qh = M['quarters'][A.target]; best = None
for f in os.listdir(os.path.join(TD, 'vec')):
    tx, ty = map(int, f[:-5].split('_')); cx, cy = (tx + .5) * TP, (ty + .5) * TP
    if not (qx <= cx <= qx + qw and qy <= cy <= qy + qh): continue
    d = json.load(open(os.path.join(TD, 'vec', f))); hs = [h for h in d['h'] if h[0] <= A.year < h[1]]
    if not best or len(hs) > best[0]: best = (len(hs), tx, ty, hs)
_, tx, ty, hs = best
def cen(h): s = h[3]; return sum(s[0::2]) / (len(s) // 2), sum(s[1::2]) / (len(s) // 2)
door = min((cen(h) for h in hs), key=lambda c: (c[0] - (tx + .5) * TP) ** 2 + (c[1] - (ty + .5) * TP) ** 2)
FILL = np.array([255, 0, 255], np.int16)  # 探针色 #ff00ff（BGR 同）
VW, VH = 960, 600
def blanks(img, cam, dbg=None):
    """整块品红、且四个角都落在有瓦片的世界格里的 8×8 块数（瓦片边上被半块切到的不算）"""
    z = cam['z']; nY, nX = VH // 8, VW // 8; inw = np.ones((nY, nX), bool)
    for ox in (0, 7):
        for oy in (0, 7):
            ys, xs = np.mgrid[0:nY, 0:nX]; wx = cam['x'] + (xs * 8 + ox + .5 - VW / 2) / z; wy = cam['y'] + (ys * 8 + oy + .5 - VH / 2) / z
            txs = np.floor(wx / TP).astype(int); tys = np.floor(wy / TP).astype(int)
            inw &= np.vectorize(lambda a, b: (a, b) in have)(txs, tys)
    eq = (np.abs(img.astype(np.int16) - FILL).max(axis=2) <= 8)
    blk = eq[:nY * 8, :nX * 8].reshape(nY, 8, nX, 8).all(axis=(1, 3)) & inw
    if dbg is not None:
        for (y, x) in zip(*np.nonzero(blk)): cv2.rectangle(dbg, (x * 8, y * 8), (x * 8 + 7, y * 8 + 7), (0, 255, 0), 1)
    return int(blk.sum())
def jump(prev, cur, k):
    g0 = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY).astype(np.float32); g1 = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY).astype(np.float32)
    Mx = np.float32([[k, 0, VW / 2 * (1 - k)], [0, k, VH / 2 * (1 - k)]]); w = cv2.warpAffine(g0, Mx, (VW, VH), flags=cv2.INTER_LINEAR)
    x0, x1, y0, y1 = int(VW * .2), int(VW * .8), int(VH * .2), int(VH * .8)
    a = cv2.GaussianBlur(w[y0:y1, x0:x1], (5, 5), 0); b = cv2.GaussianBlur(g1[y0:y1, x0:x1], (5, 5), 0)
    return float(np.abs(a - b).mean())
rows = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=1)
    def probe(route):
        r = route.fetch(); body = r.text().replace("fillStyle='#cdb68c'", "fillStyle='#ff00ff'")
        route.fulfill(response=r, body=body, headers={**r.headers, 'content-type': 'text/html; charset=utf-8'})
    pg.route('**/tiles/', probe); pg.route('**/tiles/index.html', probe)
    pg.goto(url, wait_until='networkidle'); pg.wait_for_function('()=>window.__TILES')
    pg.evaluate("Y=>__TILES.setYear(Y)", A.year); pg.wait_for_timeout(1500)
    z0 = pg.evaluate("()=>__TILES.cam.z")
    pg.evaluate("([x,y])=>{const T=__TILES;T.cam.x=x;T.cam.y=y;T.zoomAt(innerWidth/2,innerHeight/2,1)}", list(door)); pg.wait_for_timeout(1500)
    K = (A.zmax / z0) ** (1 / A.steps); prev = None
    RAF2 = "k=>new Promise(r=>{__TILES.zoomAt(innerWidth/2,innerHeight/2,k);requestAnimationFrame(()=>requestAnimationFrame(()=>r({x:__TILES.cam.x,y:__TILES.cam.y,z:__TILES.cam.z,l:__TILES.level()})))})"
    for i in range(A.steps + 1):
        cam = pg.evaluate(RAF2, 1 if i == 0 else K)
        img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        bl = blanks(img, cam); j = jump(prev, img, K) if prev is not None else 0.0
        rows.append(dict(i=i, z=round(cam['z'], 4), level=cam['l'], blank=bl, jump=round(j, 2)))
        if bl: blanks(img, cam, img2 := img.copy()); cv2.imwrite(os.path.join(A.out, f'z{i:03d}_blank.jpg'), img2, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if bl or j > 1.5 or i % 25 == 0: cv2.imwrite(os.path.join(A.out, f'z{i:03d}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        prev = img
    b.close()
for k, r in enumerate(rows):
    if k == 0: r['spike'] = False; continue
    nbh = [x['jump'] for x in rows[max(1, k - 5):k + 6] if x is not r]; med = float(np.median(nbh))
    r['spike'] = bool(r['jump'] > A.jump or r['jump'] > max(1.0, 1.5 * med))
nb = sum(r['blank'] > 0 for r in rows); nj = sum(r['spike'] for r in rows); mj = max(rows, key=lambda r: r['jump'])
res = dict(target=A.target, door=[round(door[0]), round(door[1])], year=A.year, steps=A.steps, jump_limit=A.jump,
           frames_blank=nb, blank_blocks=sum(r['blank'] for r in rows), frames_jump=nj, max_jump=mj['jump'], max_jump_at=mj, rows=rows)
json.dump(res, open(os.path.join(A.out, 'zoom.json'), 'w'), ensure_ascii=False, indent=0)
for r in rows:
    if r['blank'] or r['spike']: print(f"  ❌ 步 {r['i']} z={r['z']} 级 {r['level']}：空白 {r['blank']} 块，跳变 {r['jump']}")
ok = nb == 0 and nj == 0
print(f"{'✅' if ok else '❌'} 连续缩放 {A.steps} 步（{A.target} 门口 {res['door']}，{A.year} 年）：有空白的帧 {nb}，跳变冒尖的帧 {nj}，最大跳变 {mj['jump']}（步 {mj['i']}，z={mj['z']}）")
sys.exit(0 if ok else 1)
