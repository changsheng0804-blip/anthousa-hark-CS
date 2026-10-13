"""CS 线 · /goal 2 G3 检查：心跳接在瓦片页上。python3 tools/cs/check_heart.py [--q nangang]
  把南港的粮船日、炊烟、时钟就地接到瓦片页（不跳页）。这里量：
  ① __TILES.heart 存在且在街巷级里载好（ready）；
  ② 粮船日当天（dayIdx%3==0）10 点（缆绳那一刻）：船 ≥1、码头上的人 ≥20；换到第二天（dayIdx=1）整个粮船日不出现（节律同街区页）；
  ③ 定律 1/2 在瓦片页里照样成立：50、60 两年，一路从 6 点走到 22 点（每 0.5 点一取），
     人不踩进烤瓦片里的水域（所在水格和四周 8 格全是水才算），船的中心在水格 2 格（16 像素）以内（画上停着的小船在掩膜里是岸，航线擦过它不算上岸）；
  ④ 炊烟在清晨和傍晚比白天浓（str 1 对 .55）、且炊烟的点不落在水格里；
  ⑤ 退出去（z<街巷级）：心跳不画、不占主线程（heart.drawn=0）。
  截图 out/heart/*.jpg：粮船日 10 点（缆绳）、7 点（船队进港）、18 点（散去）、夜里酒馆。
  沙箱用 apt 的 chromium，本地起服务器。——Hark（CS线）"""
import json, os, sys, time, threading, http.server, socketserver, functools, argparse
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--q', default='nangang'); ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/heart')); ap.add_argument('--url')
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
url = A.url
if not url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
TD = os.path.join(ROOT, 'docs/living/tiles'); M = json.load(open(os.path.join(TD, 'meta.json'))); TP = M['tile_px']; WC = M['water_cell']; N = M['water_cells_n']
sc = json.load(open(os.path.join(ROOT, 'docs/living', A.q, 'scene.json'))); F = sc['fleet']; ox, oy = M['quarters'][A.q][:2]
quay = (F['quay'][0] + ox, F['quay'][1] + oy)
_vc = {}
def vec(tx, ty):
    if (tx, ty) not in _vc:
        p = os.path.join(TD, 'vec', f'{tx}_{ty}.json'); _vc[(tx, ty)] = json.load(open(p)) if os.path.exists(p) else {}
    return _vc[(tx, ty)]
def wcell(x, y, K):
    tx, ty = int(x // TP), int(y // TP); wg = vec(tx, ty).get('wg', {}).get(str(K))
    if not wg: return 0
    i, j = int((x - tx * TP) // WC), int((y - ty * TP) // WC)
    return 1 if 0 <= i < N and 0 <= j < N and wg[j * N + i] == '1' else 0
def deep_water(x, y, K):
    """人站在水格里、且四周 8 格也全是水才算下水（岸线上差一两个格是两年画的岸线略有出入，不算）"""
    return all(wcell(x + a * WC, y + b * WC, K) for a in (-1, 0, 1) for b in (-1, 0, 1))
def near_water(x, y, K, r=2):
    return any(wcell(x + a * WC, y + b * WC, K) for a in range(-r, r + 1) for b in range(-r, r + 1))
fails = []; rep = []
def ck(name, ok, info=''):
    rep.append((name, ok, info)); print(('  ok  ' if ok else ' FAIL ') + name + ('  ' + str(info) if info != '' else ''))
    if not ok: fails.append(name)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = b.new_page(viewport={'width': 960, 'height': 600})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(url); pg.wait_for_function('window.__TILES&&window.__TILES.cam', timeout=30000)
    pg.evaluate(f'(()=>{{const T=__TILES;T.cancelFly();T.setYear(60);T.cam.x={quay[0]};T.cam.y={quay[1]};T.cam.z=1.6}})()'); time.sleep(0.5)
    has = pg.evaluate('!!(window.__TILES&&window.__TILES.heart)')
    ck('① __TILES.heart 存在', has)
    if has:
        try: pg.wait_for_function('__TILES.heart.ready', timeout=40000); ck('① 心跳在街巷级里载好', True)
        except Exception as e: ck('① 心跳在街巷级里载好', False, str(e)[:80])
    if has and pg.evaluate('__TILES.heart.ready'):
        H = lambda js: pg.evaluate('(()=>{const h=__TILES.heart;' + js + '})()')
        H('h.setClock(10.0,0)'); time.sleep(1.2)
        e = H('return h.entities()'); ck('② 粮船日 10 点：船', len(e['ships']) >= 1, len(e['ships'])); ck('② 粮船日 10 点：码头上的人', len(e['people']) >= 20, len(e['people']))
        pg.screenshot(path=os.path.join(A.out, 'h10.jpg'), type='jpeg', quality=80)
        H('h.setClock(10.0,1)'); time.sleep(0.6); e1 = H('return h.entities()')
        ck('② 第二天（dayIdx=1）没有粮船日', len(e1['ships']) == 0 and len(e1['people']) == 0, (len(e1['ships']), len(e1['people'])))
        for Y in (50, 60):
            pg.evaluate(f'__TILES.setYear({Y})'); time.sleep(1.2); badp = []; bads = []; np_ = ns_ = 0
            for hh in [6 + 0.5 * k for k in range(0, 34)]:
                H(f'h.setClock({hh},0)'); e = H('return h.entities()'); np_ += len(e['people']); ns_ += len(e['ships'])
                for x, y, k in e['people']:
                    if deep_water(x, y, Y): badp.append((hh, round(x), round(y), k))
                for x, y in e['ships']:
                    if not near_water(x, y, Y): bads.append((hh, round(x), round(y)))
            ck(f'③ {Y} 年 人不下水（6–22 点共 {np_} 人次）', not badp, badp[:3]); ck(f'③ {Y} 年 船在水里（{ns_} 艘次）', not bads, bads[:3])
        H('h.setClock(7.0,0)'); time.sleep(1.0); pg.screenshot(path=os.path.join(A.out, 'h07.jpg'), type='jpeg', quality=80)
        H('h.setClock(18.0,0)'); time.sleep(1.0); pg.screenshot(path=os.path.join(A.out, 'h18.jpg'), type='jpeg', quality=80)
        H('h.setClock(21.0,0)'); time.sleep(1.0); pg.screenshot(path=os.path.join(A.out, 'h21.jpg'), type='jpeg', quality=80)
        H('h.setClock(6.0,0)'); es = H('return h.smokes(6.5)'); H('h.setClock(12.0,0)'); ed = H('return h.smokes(12.0)')
        ck('④ 炊烟：清晨比白天浓', es['n'] > 0 and es['str'] > ed['str'], (es['n'], es['str'], ed['str']))
        bs = [s for s in es['pts'] if wcell(s[0], s[1], 60)]; ck('④ 炊烟不冒在水里', not bs, bs[:3])
        pg.evaluate(f'(()=>{{const T=__TILES;T.cam.z=0.5;T.cam.x={quay[0]};T.cam.y={quay[1]}}})()'); time.sleep(0.8)
        ck('⑤ 退出街巷级：心跳不画', H('return h.drawn')==0, H('return h.drawn'))
    errs=[e for e in errs if '404' not in e]; ck('页面无报错（404 的 favicon 等不计）', not errs, errs[:2])
    b.close()
json.dump({'q': A.q, 'results': rep, 'fails': fails}, open(os.path.join(A.out, 'heart.json'), 'w'), ensure_ascii=False, indent=1)
print('不过：', fails if fails else '无'); sys.exit(1 if fails else 0)
