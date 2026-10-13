"""CS 线 · /goal 2 项 5 检查：九块的活人层都在瓦片页里就地长出来。python3 tools/cs/check_hearts9.py [--only q1,q2] [--url URL]
  对九块每一块：把镜头放到该块中心（places.json）、街巷级 z=1.6、60 年，量：
  ① 进框放大到街巷级，心跳自己载入（__TILES.heart.ready(q)），载入没报错；
  ② 炊烟：这一年站着的房子每十栋一缕，数量 >0，清晨比白天浓，不冒在水里；
  ③ 家户推演：随手点（c.open）8 栋房子，卡上有名字、没有 undefined/NaN/null；
  ④ 真点：在屏幕上点一栋房子，卡片弹出，且归「先到的那块」（框重叠带归 tile_bake ORDER 里靠前的）；
  ⑤ 重叠带不重复：炊烟点按「先到先得」只画一次（同一世界点不在两块的炊烟里同时出现）；
  ⑥ 退出街巷级（z=0.5）：该块 drawn=0；
  ⑦ 页面无报错。人不出街/船不出水：有粮船日的块（南港）由 check_heart.py 管；没有粮船日的块 entities 恒空，由瓦片页自带的 LIFE 走网（check_tiles）。
  沙箱用 apt 的 chromium，本地起服务器。——Hark（CS线）"""
import json, os, sys, time, threading, http.server, socketserver, functools, argparse, re
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--only'); ap.add_argument('--url'); ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/hearts9'))
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
if not A.url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/tiles/'
else: url = A.url
TD = os.path.join(ROOT, 'docs/living/tiles'); M = json.load(open(os.path.join(TD, 'meta.json'))); TP = M['tile_px']; WC = M['water_cell']; N = M['water_cells_n']
PL = {t['q']: t for t in json.load(open(os.path.join(TD, 'places.json')))['quarters']}
QS_ALL = ['nangang','jinjiao','gucheng','siqiu','dongjia','xipo','qiangwai','jiaowan','nanan']
QS = [q for q in PL if not A.only or q in A.only.split(',')]
_vc = {}
def wcell(x, y, K):
    tx, ty = int(x // TP), int(y // TP)
    if (tx, ty) not in _vc:
        pp = os.path.join(TD, 'vec', f'{tx}_{ty}.json'); _vc[(tx, ty)] = json.load(open(pp)) if os.path.exists(pp) else {}
    wg = _vc[(tx, ty)].get('wg', {}).get(str(K))
    if not wg: return 0
    i, j = int((x - tx * TP) // WC), int((y - ty * TP) // WC)
    return 1 if 0 <= i < N and 0 <= j < N and wg[j * N + i] == '1' else 0
fails = []; rep = []
def ck(name, ok, info=''):
    rep.append((name, ok, info)); print(('  ok  ' if ok else ' FAIL ') + name + ('  ' + str(info) if info != '' else ''))
    if not ok: fails.append(name)
BAD = re.compile(r'undefined|NaN|null')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = b.new_page(viewport={'width': 1100, 'height': 700})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(url); pg.wait_for_function('window.__TILES&&window.__TILES.cam', timeout=30000)
    smk = {}
    for q in QS:
        print(f'— {q}')
        c = PL[q]
        pg.evaluate(f'(()=>{{const T=__TILES;T.cancelFly();T.setYear(60);T.cam.x={c["x"]};T.cam.y={c["y"]};T.cam.z=1.6}})()'); time.sleep(0.6)
        try: pg.wait_for_function(f'!!__TILES.heart.mod("{q}")', timeout=40000); ok = True
        except Exception as e: ok = False
        ck(f'{q} ① 心跳在街巷级里自己载好', ok)
        if not ok: continue
        pg.evaluate('__TILES.heart.setClock(6.0,0)'); time.sleep(0.5)
        es = pg.evaluate(f'__TILES.heart.smokes(6.5,"{q}")'); ed = pg.evaluate(f'__TILES.heart.smokes(12.0,"{q}")')
        ck(f'{q} ② 炊烟：有，清晨比白天浓', es['n'] > 0 and es['str'] > ed['str'], (es['n'], es['str'], ed['str']))
        bs = [s for s in es['pts'] if wcell(s[0], s[1], 60)]; ck(f'{q} ② 炊烟不冒在水里', not bs, bs[:3]); smk[q] = es['pts']
        hs = pg.evaluate(f'__TILES.heart.card.houses("{q}")'); hs.sort(key=lambda t: (t[1] - c['x']) ** 2 + (t[2] - c['y']) ** 2)
        bad = []
        for hid, x, y in hs[::max(1, len(hs) // 8)][:8]:
            pg.evaluate(f'__TILES.heart.card.open({hid},"{q}")'); h = pg.inner_html('#cardbody')
            if BAD.search(re.sub(r'data-[a-z]+="[^"]*"|csans', '', h)) or not pg.query_selector('#cardbody h2'): bad.append(hid)
        ck(f'{q} ③ 家户推演：8 张卡有名字、无 undefined/NaN/null', not bad and len(hs) >= 8, (len(hs), bad[:3]))
        pg.evaluate('__TILES.heart.card.close()')
        got = None
        for hid, x, y in hs[:25]:
            sx, sy = pg.evaluate(f'__TILES.heart.card.screen({x},{y})')
            if not (60 < sx < 1040 and 40 < sy < 660): continue
            pg.mouse.click(sx, sy); time.sleep(0.2)
            if pg.evaluate('__TILES.heart.card.shown'): got = (hid, pg.evaluate('__TILES.heart.card.q')); break
        own = None
        if got:
            hx, hy = [(x, y) for hid, x, y in hs if hid == got[0]][0]
            own = next(e for e in QS_ALL if M['quarters'][e][0] < hx < M['quarters'][e][0] + M['quarters'][e][2] and M['quarters'][e][1] < hy < M['quarters'][e][1] + M['quarters'][e][3])
        ck(f'{q} ④ 真点房子：卡片弹出、归先到那块（框重叠带归先到的）', bool(got) and got[1] == own, (got, own))
        if got: pg.screenshot(path=os.path.join(A.out, f'{q}.jpg'), type='jpeg', quality=78)
        pg.evaluate('__TILES.heart.card.close()')
        pg.evaluate(f'(()=>{{const T=__TILES;T.cam.z=0.5}})()'); time.sleep(0.7)
        ck(f'{q} ⑥ 退出街巷级：心跳不画', pg.evaluate('__TILES.heart.drawn') == 0)
    # ⑤ 重叠带炊烟不重复：同一世界点（精确到 0.1 px，邻栋不算）只在一块里出现
    seen = {}; dup = []
    for q in QS:
        for x, y in smk.get(q, []):
            k = (round(x, 1), round(y, 1))
            if k in seen and seen[k] != q: dup.append((seen[k], q, k))
            seen.setdefault(k, q)
    ck('⑤ 重叠带炊烟只画一次', not dup, dup[:3])
    errs = [e for e in errs if '404' not in e]; ck('⑦ 页面无报错（404 的 favicon 等不计）', not errs, errs[:2])
    b.close()
json.dump({'results': rep, 'fails': fails}, open(os.path.join(A.out, 'hearts9.json'), 'w'), ensure_ascii=False, indent=1)
print('不过：', fails if fails else '无'); sys.exit(1 if fails else 0)
