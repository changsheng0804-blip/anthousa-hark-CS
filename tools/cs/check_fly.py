"""CS 线 · /goal 2 G2 检查：弧线飞行。python3 tools/cs/check_fly.py [--set quick|all]
  从全城视野起，连着飞：每块街区的门口（南港门口先）、地标、48 年大火；每一程都量——
  ① 有 __TILES.flyTo(x,y,z[,{year}])；
  ② 飞行时长 1.5–4 秒（页面自己报的动画时长，落地等瓦片的 hold 另报，≤1 秒）；
  ③ 路上每隔 ~150 ms 截一帧：空白块（品红探针，同 check_zoom）逐帧数，飞行中也不许有空洞；
  ④ 路线是「先拉高再俯冲」：两点相隔 >1 屏时，中途最低缩放 ≤ 两端较小者的 0.8；
  ⑤ 落地那一帧：镜头离目标 <1 px、z 误差 <0.5%、视口里本级瓦片全到（pending=0）、空白块 0。
  --set all 飞 11 座以上地标 + 九块中心 + 大火（耗时几分钟）；quick 取代表。
  沙箱 arm64 无 GPU，用 apt 的 chromium，本地起服务器。——Hark（CS线）"""
import json, os, sys, time, threading, http.server, socketserver, functools, argparse
import numpy as np, cv2
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--set', default='quick'); ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/fly')); ap.add_argument('--url')
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
url = A.url
if not url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
TD = os.path.join(ROOT, 'docs/living/tiles'); M = json.load(open(os.path.join(TD, 'meta.json'))); TP = M['tile_px']
P = json.load(open(os.path.join(TD, 'places.json'))) if os.path.exists(os.path.join(TD, 'places.json')) else None
have = {tuple(map(int, f[:-5].split('_'))) for f in os.listdir(os.path.join(TD, '60', '0'))}
VW, VH = 960, 600; FILL = np.array([255, 0, 255], np.int16)
def blanks(img, *cams):
    """cams：截图前后各读一次镜头，两个镜头下都在有瓦片的世界格里的块才算（飞行中镜头在动，只读一次会错位）"""
    nY, nX = VH // 8, VW // 8; inw = np.ones((nY, nX), bool)
    for cam in cams:
      z = cam['z']
      for ox in (0, 7):
        for oy in (0, 7):
            ys, xs = np.mgrid[0:nY, 0:nX]; wx = cam['x'] + (xs * 8 + ox + .5 - VW / 2) / z; wy = cam['y'] + (ys * 8 + oy + .5 - VH / 2) / z
            inw &= np.vectorize(lambda a, b: (a, b) in have)(np.floor(wx / TP).astype(int), np.floor(wy / TP).astype(int))
    eq = (np.abs(img.astype(np.int16) - FILL).max(axis=2) <= 8)
    return int((eq[:nY * 8, :nX * 8].reshape(nY, 8, nX, 8).all(axis=(1, 3)) & inw).sum())
# 目标：(名字, x, y, z, year)
T = []
if P:
    L = {l['id']: l for l in P['landmarks']}; QC = {c['q']: c for c in P['quarters']}
    door = lambda q: (QC[q]['name'] + '门口', QC[q]['x'], QC[q]['y'], 1.6, 60)
    quick = ['nangang', 'gucheng', 'dongjia', 'nanan']
    if A.set == 'all':
        for q in M['owner_order']: T.append(door(q))
        for l in P['landmarks']: T.append((l['name'], l['x'], l['y'], 1.6, 60))
        for e in P['events']: T.append((e['name'], e['x'], e['y'], e['z'], e['show_year']))
    elif A.set == 'edge':
        for i in ['barracks_gate', 'cistern_carriers', 'xenon_xerolophos']: T.append((L[i]['name'], L[i]['x'], L[i]['y'], 1.6, 60))
    else:
        for q in quick: T.append(door(q))
        for i in ['palace_great', 'hippodrome', 'fort_acropolis', 'tower_horn', 'horrea_theodosius']: T.append((L[i]['name'], L[i]['x'], L[i]['y'], 1.6, 60))
        for e in P['events']: T.append((e['name'], e['x'], e['y'], e['z'], e['show_year']))
res = []; fails = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=1)
    def probe(route):
        r = route.fetch(); body = r.text().replace("fillStyle='#cdb68c'", "fillStyle='#ff00ff'")
        route.fulfill(response=r, body=body, headers={**r.headers, 'content-type': 'text/html; charset=utf-8'})
    pg.route('**/tiles/', probe); pg.route('**/tiles/index.html', probe)
    pg.goto(url, wait_until='networkidle'); pg.wait_for_function('()=>window.__TILES')
    pg.evaluate("Y=>__TILES.setYear(Y)", 60); pg.wait_for_timeout(1500)
    has = pg.evaluate("()=>typeof __TILES.flyTo")
    if has != 'function' or not T:
        print('❌ 页面还没有 flyTo（__TILES.flyTo）' if has != 'function' else '❌ 没有 places.json'); b.close(); sys.exit(1)
    for n, (name, x, y, z, yr) in enumerate(T):
        c0 = pg.evaluate("()=>({x:__TILES.cam.x,y:__TILES.cam.y,z:__TILES.cam.z})")
        pg.evaluate("([x,y,z,yr])=>{window.__done=null;__TILES.flyTo(x,y,z,{year:yr}).then(r=>window.__done=r)}", [x, y, z, yr])
        fr = []; t0 = time.time()
        while time.time() - t0 < 12:
            if pg.evaluate("()=>window.__done"): break
            # 飞行中读画布本身（toDataURL）：画布和镜头在同一个 rAF 里一起更新，两者必然对得上；page.screenshot 会截到合成器没刷完的半帧，是测量假象
            d = pg.evaluate("()=>({x:__TILES.cam.x,y:__TILES.cam.y,z:__TILES.cam.z,u:document.getElementById('c').toDataURL('image/png')})")
            cam = cam2 = dict(x=d['x'], y=d['y'], z=d['z']); import base64
            img = cv2.imdecode(np.frombuffer(base64.b64decode(d['u'].split(',')[1]), np.uint8), cv2.IMREAD_COLOR)
            bl = blanks(img, cam); fr.append(dict(z=round(cam['z'], 4), blank=bl))
            if bl: print('    空白帧诊断', name, cam2, pg.evaluate("""()=>{const T=__TILES,c=T.cam,[l,fr]=T.levelF(),W=innerWidth,H=innerHeight,o=[];for(let L=l;L<Math.min(l+3,4);L++){const ts=455*2**L;for(let ty=Math.floor((c.y-H/2/c.z)/ts);ty<=Math.floor((c.y+H/2/c.z)/ts);ty++)for(let tx=Math.floor((c.x-W/2/c.z)/ts);tx<=Math.floor((c.x+W/2/c.z)/ts);tx++){const v=T.cache.get(T.curYear+'/'+L+'/'+tx+'_'+ty);o.push(L+'/'+tx+'_'+ty+':'+(v===undefined?'none':v===null?'null':v.ok?'ok':v.miss?'miss':'pend'))}}return {l,fr,o}}"""))
            if bl: cv2.imwrite(os.path.join(A.out, f'f{n:02d}_mid_blank.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if len(fr) in (2, 5, 8) and n < 3: cv2.imwrite(os.path.join(A.out, f'f{n:02d}_{len(fr)}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            pg.wait_for_timeout(100)
        r = pg.evaluate("()=>window.__done"); pg.wait_for_timeout(120)
        cam = pg.evaluate("()=>({x:__TILES.cam.x,y:__TILES.cam.y,z:__TILES.cam.z,pend:__TILES.pending()})")
        img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_COLOR); lb = blanks(img, cam)
        cv2.imwrite(os.path.join(A.out, f'f{n:02d}_land.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not r: row = dict(name=name, err='没落地', frames=len(fr)); res.append(row); fails += 1; print('  ❌', name, '12 秒没落地'); continue
        d = np.hypot(x - c0['x'], y - c0['y']); far = d * min(c0['z'], z) > VW
        zmin = min([f['z'] for f in fr] + [c0['z'], z]); fit = min(VW / (M['grid'][0] * TP), VH / (M['grid'][1] * TP)) * .95; lift = (not far) or zmin <= 0.8 * min(c0['z'], z) or zmin <= fit * .8
        errs = []
        if not (1.5 <= r['dur'] <= 4.0): errs.append(f"时长 {r['dur']:.2f}s")
        if r['hold'] > 1.0: errs.append(f"落地等瓦片 {r['hold']:.2f}s")
        if not lift: errs.append(f"没先拉高（最低 z {zmin:.3f}，端点 {min(c0['z'], z):.3f}）")
        if sum(f['blank'] for f in fr): errs.append(f"飞行中空白 {sum(f['blank'] for f in fr)} 块（{sum(1 for f in fr if f['blank'])} 帧）")
        if np.hypot(cam['x'] - x, cam['y'] - y) > 1 or abs(cam['z'] / z - 1) > .005: errs.append(f"没对准（差 {np.hypot(cam['x'] - x, cam['y'] - y):.1f}px，z {cam['z']:.3f}/{z}）")
        if cam['pend']: errs.append(f"落地时还有 {cam['pend']} 块没到")
        if lb: errs.append(f"落地帧空白 {lb} 块")
        row = dict(name=name, dur=round(r['dur'], 2), hold=round(r['hold'], 2), frames=len(fr), zmin=round(zmin, 3), land_blank=lb, errs=errs); res.append(row)
        fails += bool(errs); print(('  ❌ ' if errs else '  ✅ ') + f"{name}：{r['dur']:.2f}s 取样 {len(fr)} 帧 最低 z {zmin:.3f}" + ('  ← ' + '；'.join(errs) if errs else ''))
    b.close()
json.dump(res, open(os.path.join(A.out, 'fly.json'), 'w'), ensure_ascii=False, indent=0)
print(f"{'✅' if not fails else '❌'} 弧线飞行 {len(T)} 程：{fails} 程不过")
sys.exit(1 if fails else 0)
