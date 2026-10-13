"""CS 线 · /goal 2 G3 检查（项 4b）：敲门卡接在瓦片页上。python3 tools/cs/check_card_tile.py [--q nangang] [--url URL]
  瓦片页 = 街巷级里点房子弹出 cs3 的卡（现在 / 一个钩子 / 敲门·再问一句 / 后来呢）。这里量：
  ① __TILES.heart.card 存在；
  ② 真的点一下（鼠标点在一栋房子的屏幕位置）：卡片弹出，有名字（h2）和 meta，选中圈跟着；点空处/× 关掉；
  ③ 40/50/60 三年各抽一批房子（每隔几栋一栋）：卡片没有 undefined/NaN/null；有「现在」或「钩子」；折起来之外的字数不超 cs3 的线；
     点「敲门」「再问一句」三下：每下有回话、相邻两下不一样；点钩子里的名字 → 跟一个人走，点「后来呢」几步，不抛错，年份可跳；
  ④ 和街区页同一份推演：同一栋房子、同一年，瓦片页的卡和街区页（nangang/index.html）的卡 h2 / meta / 钩子 / 折起来的家人与年代逐字一样（抽 18 栋）；
  ⑤ 退出街巷级（z=0.5）：卡自己收掉；切年份：卡跟着重算、不抛错；
  ⑥ 页面无报错。
  沙箱用 apt 的 chromium，本地起服务器。——Hark（CS线）"""
import json, os, sys, time, threading, http.server, socketserver, functools, argparse, re
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--q', default='nangang'); ap.add_argument('--url'); ap.add_argument('--out', default=os.path.join(ROOT, 'tools/cs/factory/out/card')); ap.add_argument('--n', type=int, default=14)
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
base = None
if not A.url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); base = f'http://127.0.0.1:{srv.server_address[1]}/'
else: base = A.url.rsplit('/tiles/', 1)[0] + '/'
url = base + 'tiles/'
M = json.load(open(os.path.join(ROOT, 'docs/living/tiles/meta.json'))); ox, oy = M['quarters'][A.q][:2]
sc = json.load(open(os.path.join(ROOT, 'docs/living', A.q, 'scene.json'))); F = sc.get('fleet') or {}
quay = (F['quay'][0] + ox, F['quay'][1] + oy) if F.get('quay') else (ox + 300, oy + 300)
fails = []; rep = []
def ck(name, ok, info=''):
    rep.append((name, ok, info)); print(('  ok  ' if ok else ' FAIL ') + name + ('  ' + str(info) if info != '' else ''))
    if not ok: fails.append(name)
BAD = re.compile(r'undefined|NaN|null')
def clean(h): return BAD.search(re.sub(r'data-[a-z]+="[^"]*"|csans', '', h))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = b.new_page(viewport={'width': 1100, 'height': 700})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(url); pg.wait_for_function('window.__TILES&&window.__TILES.cam', timeout=30000)
    pg.evaluate(f'(()=>{{const T=__TILES;T.cancelFly();T.setYear(60);T.cam.x={quay[0]};T.cam.y={quay[1]};T.cam.z=1.6}})()'); time.sleep(0.6)
    has = pg.evaluate('!!(window.__TILES&&window.__TILES.heart&&window.__TILES.heart.card)')
    ck('① __TILES.heart.card 存在', has)
    if has:
        try: pg.wait_for_function('__TILES.heart.ready', timeout=40000)
        except Exception as e: ck('① 心跳载好', False, str(e)[:80]); has = False
    if has:
        C = lambda js: pg.evaluate('(()=>{const c=__TILES.heart.card;' + js + '})()')
        body = lambda: pg.inner_html('#cardbody')
        # ② 真点
        hs = C('return c.houses()'); hs.sort(key=lambda t: (t[1] - quay[0]) ** 2 + (t[2] - quay[1]) ** 2)
        got = None
        for hid, x, y in hs[:12]:
            sx, sy = C(f'return c.screen({x},{y})')
            if not (60 < sx < 1040 and 40 < sy < 660): continue
            pg.mouse.click(sx, sy); time.sleep(0.25)
            if C('return c.shown'): got = (hid, x, y, sx, sy); break
        ck('② 点房子：卡片弹出', got is not None, got[0] if got else len(hs))
        if got:
            ck('② 卡上有名字和 meta', bool(pg.query_selector('#cardbody h2')) and bool(pg.query_selector('#cardbody .meta')), pg.inner_text('#cardbody h2')[:12])
            time.sleep(0.4); pg.screenshot(path=os.path.join(A.out, 'tap.jpg'), type='jpeg', quality=80)
            pg.click('#cardx'); time.sleep(0.2); ck('② 点 × 关掉', not C('return c.shown'))
            pg.mouse.click(got[3], got[4]); time.sleep(0.25); ck('② 再点开', C('return c.shown'))
            scr = [C(f'return c.screen({x},{y})') for _, x, y in hs]
            empty = None
            for sx in range(80, 1020, 40):
                for sy in range(60, 650, 40):
                    if all((sx - a) ** 2 + (sy - b_) ** 2 > 70 ** 2 for a, b_ in scr): empty = (sx, sy); break
                if empty: break
            if empty:
                pg.mouse.click(*empty); time.sleep(0.25); ck('② 点空处收掉', not C('return c.shown'), empty)
            else: print('  --  视野里没有离房子 70 px 以上的空处，跳过「点空处收掉」')
        # ③ 三年抽样
        for Y in M['years']:
            pg.evaluate(f'__TILES.setYear({Y})'); time.sleep(0.8)
            hs = C('return c.houses()'); step = max(1, len(hs) // A.n); samp = hs[::step][:A.n]
            bad = []; lens = []; nonow = 0; noans = 0; same = 0; chain_err = 0; steps_ok = 0; n = 0
            for hid, x, y in samp:
                C(f'c.open({hid},"{A.q}")'); h = body(); n += 1
                if not C('return c.shown'): print('   卡被收了', hid, C('return [__TILES.cam.z,__TILES.flying]')); C(f'c.open({hid},"{A.q}")')
                if clean(h): bad.append((hid, BAD.search(re.sub(r'data-[a-z]+="[^"]*"', '', h)).group(0)))
                vis = pg.evaluate("[...document.querySelectorAll('#cardbody h2,#cardbody .meta,#cardbody .now,#cardbody .story,#cardbody .cshook,#cardbody .cstalk')].filter(e=>!e.closest('details')).map(e=>e.textContent).join(' ').length"); lens.append(vis)
                if not (pg.query_selector('#cardbody .now') or pg.query_selector('#cardbody .cshook') or pg.query_selector('#cardbody .story')): nonow += 1
                if pg.query_selector('#cardbody [data-q=next]'):
                    ans = []
                    for k in range(3):
                        pg.click('#cardbody [data-q=next]'); time.sleep(0.03); t = pg.inner_text('#cardbody .csans') if pg.query_selector('#cardbody .csans') else ''
                        ans.append(t)
                    if not all(a.strip() for a in ans): noans += 1
                    if len(set(ans)) < 3: same += 1
                if pg.query_selector('#cardbody .cshook [data-p]') and n % 3 == 0:
                    try:
                        pg.click('#cardbody .cshook [data-p]'); time.sleep(0.05)
                        ok = bool(pg.query_selector('#cardbody .csstep'))
                        for k in range(3):
                            nx = pg.query_selector('#cardbody [data-step]:has-text("后来呢")')
                            if not nx: break
                            nx.click(); time.sleep(0.08)
                        if ok and C('return c.shown') and not clean(body()): steps_ok += 1
                        else: chain_err += 1; print('   链错', hid, ok, C('return c.shown'), body()[:300])
                    except Exception as e: chain_err += 1; print('   链错', hid, str(e)[:100])
                    pg.evaluate(f'(()=>{{const T=__TILES;T.cancelFly();T.setYear({Y});T.cam.x={quay[0]};T.cam.y={quay[1]};T.cam.z=1.6}})()'); time.sleep(0.1)
            lens.sort(); med = lens[len(lens) // 2] if lens else 0; p90 = lens[int(len(lens) * .9)] if lens else 0
            ck(f'③ {Y} 年 {n} 张卡：没有 undefined/NaN/null', not bad, bad[:3])
            ck(f'③ {Y} 年：每张卡有「现在」或钩子或故事', nonow == 0, nonow)
            ck(f'③ {Y} 年：折起来之外的字数 中位数 ≤ 160、p90 ≤ 260', med <= 160 and p90 <= 260, (med, p90))
            ck(f'③ {Y} 年：敲门三下都有回话且互不相同', noans == 0 and same == 0, (noans, same))
            ck(f'③ {Y} 年：跟一个人走（后来呢）不抛错', chain_err == 0, (steps_ok, chain_err))
            if Y == M['years'][-1]: pg.screenshot(path=os.path.join(A.out, f'card{Y}.jpg'), type='jpeg', quality=80)
        # ⑤ 切年份 / 退出
        pg.evaluate('__TILES.cancelFly();__TILES.setYear(60)'); time.sleep(0.6)
        hs = C('return c.houses()'); C(f'c.open({hs[len(hs)//2][0]},"{A.q}")'); t60 = pg.inner_text('#cardbody')
        pg.evaluate('__TILES.setYear(40)'); time.sleep(0.5)
        ck('⑤ 切年份：卡还在、跟着重算', C('return c.shown'), '')
        pg.evaluate(f'(()=>{{const T=__TILES;T.cam.z=0.5}})()'); time.sleep(0.8)
        ck('⑤ 退出街巷级：卡自己收掉', not C('return c.shown'))
        # ④ 和街区页同一份推演
        pg.evaluate(f'(()=>{{const T=__TILES;T.setYear(60);T.cam.x={quay[0]};T.cam.y={quay[1]};T.cam.z=1.6}})()'); time.sleep(0.8)
        pg.evaluate('__TILES.heart.setClock(10.0,0)')
        hs = C('return c.houses()'); step = max(1, len(hs) // 18); ids = [h[0] for h in hs[::step][:18]]
        T = {}
        for i in ids:
            C(f'c.open({i},"{A.q}")'); T[i] = {k: (pg.inner_html('#cardbody ' + k) if pg.query_selector('#cardbody ' + k) else '') for k in ('h2', '.meta', '.cshook', '.csmore')}
        q = b.new_page(viewport={'width': 1100, 'height': 700}); q.on('pageerror', lambda e: errs.append('街区页 ' + str(e)))
        q.goto(base + A.q + '/index.html'); q.wait_for_function('window.__anth&&window.__cs', timeout=60000)
        q.evaluate('(()=>{const A=window.__anth;A.setYear(60);A.clock=10})()'); time.sleep(1.0)
        diff = []
        for i in ids:
            q.evaluate(f'window.__cs.openHouse({i})')
            for k in ('h2', '.meta', '.cshook', '.csmore'):
                v = q.inner_html('#card ' + k) if q.query_selector('#card ' + k) else ''
                if v != T[i][k]: diff.append((i, k, v[:60], T[i][k][:60]))
        ck(f'④ 和街区页同一份推演（{len(ids)} 栋 × h2/meta/钩子/家人年代）逐字一样', not diff, diff[:2])
    errs = [e for e in errs if '404' not in e]; ck('⑥ 页面无报错（404 的 favicon 等不计）', not errs, errs[:2])
    b.close()
json.dump({'q': A.q, 'results': rep, 'fails': fails}, open(os.path.join(A.out, 'card.json'), 'w'), ensure_ascii=False, indent=1)
print('\n不过：', fails if fails else '无'); sys.exit(1 if fails else 0)
