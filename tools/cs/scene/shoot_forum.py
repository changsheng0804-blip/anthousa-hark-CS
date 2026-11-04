"""狄奥多西广场一景的无头验收（2026-11-05，CS 线）：起本地服务 → chromium（SwiftShader）开 forum.html →
宽景 / 近景点一个人的签 / 进一间铺子 / 手机 390×844 点一个人，各拍一张；记三角形、人数、指得到的东西。
  python3 tools/cs/scene/shoot_forum.py [输出目录]      （默认 /tmp/forum_shots）
——Hark（CS线）"""
import json, os, subprocess, sys, time, socket
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/forum_shots'; os.makedirs(OUT, exist_ok=True)
ONLY = os.environ.get('ONLY', '')
s = socket.socket(); s.bind(('', 0)); PORT = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=os.path.join(ROOT, 'docs'), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f'http://127.0.0.1:{PORT}/living/nodes/nangang/forum.html?still=1'   # still：不跑动画循环，每次 __forum.render() 才画一帧（SwiftShader 一帧好几秒）
ARGS = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
R = {}
def wait(pg):
    pg.wait_for_function('window.__forumReady === 1', timeout=240000)
    pg.evaluate('__forum.render(), 1')
def frames(pg, n=1):
    for _ in range(n): pg.evaluate('__forum.render(), 1')
def shot(pg, path, quality=88):
    pg.screenshot(path=path, quality=quality, timeout=180000)
def pick_person(pg, kinds, touch=False):
    """在当前画面里找一个 kinds 里、没被挡住（__forum.pick 指得到他本人）的人，返回 (id, x, y)：离画面中心最近的那个"""
    return pg.evaluate("""([kinds, touch]) => { const F = window.__forum, W = innerWidth, H = innerHeight, L = [];
      for (const c of F.CAST.cast) { if (!kinds.includes(c.kind)) continue; const p = F.screenOf(c.id); if (!p) continue;
        if (p[0] < 40 || p[0] > W - 40 || p[1] < 80 || p[1] > H * .55) continue; L.push([c.id, p[0], p[1], Math.hypot(p[0] - W / 2, p[1] - H * .4)]) }
      L.sort((a, b) => a[3] - b[3]);
      for (const q of L) if (F.pick(q[1], q[2], touch) === 'person:' + q[0]) return q;
      return null }""", [kinds, touch])
try:
    with sync_playwright() as P:
        b = P.chromium.launch(executable_path='/usr/bin/chromium', args=ARGS)
        # ---- 桌面 ----
        if ONLY in ('', 'desk'):
            pg = b.new_page(viewport={'width': 1400, 'height': 860}); logs = []
            pg.on('console', lambda m: logs.append(m.type + ' ' + m.text)); pg.on('pageerror', lambda e: logs.append('ERR ' + str(e)))
            t0 = time.time(); pg.goto(URL); wait(pg); R['load_s'] = round(time.time() - t0, 1)
            R['tris_home'] = pg.evaluate('__forum.tris()'); R['crowd_home'] = pg.evaluate('__forum.last()')
            shot(pg, f'{OUT}/wide.jpg', quality=88)
            # 指几样东西（屏幕坐标 → 名字）
            pts = {}
            for k in ['column', 'arch', 'wingN', 'wingE', 'court']:
                pts[k] = pg.evaluate("""(k) => { const p = __forum.PLACES.find(q => q.key === k), m = p.meshes[0], v = m.position.clone().project(__ctx.camera); return [(v.x + 1) / 2 * innerWidth, (1 - v.y) / 2 * innerHeight] }""", k)
                pts[k] = [pts[k], pg.evaluate('([x, y]) => __forum.pick(x, y, false)', pts[k])]
            R['picks_home'] = pts
            # 近景：凑近纪功柱和北柱廊，点一个摆摊的
            pg.evaluate('__forum.view([1455, __ctx.groundMesh(1436,313) + 14, 300], [1446, __ctx.groundMesh(1436,313) + 3, 268], 50)'); frames(pg, 3); pg.wait_for_timeout(800)
            who = pick_person(pg, ['stall', 'shopper', 'idler', 'kid'])
            R['close_person'] = who
            pg.evaluate('__forum.pick(-999, -999, false)')   # 放开 pick_person 试指时钉住的人
            if who:
                pg.mouse.move(who[1], who[2]); pg.wait_for_timeout(300); pg.mouse.click(who[1], who[2]); frames(pg, 2); pg.wait_for_timeout(400)
                R['close_info'] = pg.inner_text('#info')
            shot(pg, f'{OUT}/close.jpg', quality=88)
            # 进门：北柱廊的铺面
            pg.evaluate('__forum.home()'); frames(pg, 2)
            pg.evaluate("__forum.enter('shopN')"); pg.wait_for_timeout(200); pg.evaluate('__forum.finishFly()'); frames(pg, 3); pg.wait_for_timeout(800)
            R['card'] = pg.inner_text('#card'); shot(pg, f'{OUT}/interior.jpg', quality=88)
            nx = pg.query_selector('#nx')
            if nx: nx.click(); pg.wait_for_timeout(200); R['card_next'] = pg.inner_text('#card .who')
            R['tris_interior'] = pg.evaluate('__forum.tris()')
            pg.evaluate('__forum.leave()'); pg.evaluate("__forum.enter('column')"); R['card_column'] = pg.inner_text('#card'); pg.evaluate('__forum.leave()')
            R['desk_logs'] = [l for l in logs if 'ERR' in l or l.startswith('error')][:10]
            pg.close()
        # ---- 手机 390×844（iOS 那样：触屏、DPR 3） ----
        if ONLY in ('', 'mob'):
            ctxm = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            pg = ctxm.new_page(); logs = []
            pg.on('pageerror', lambda e: logs.append('ERR ' + str(e)))
            t0 = time.time(); pg.goto(URL); wait(pg); R['mob_load_s'] = round(time.time() - t0, 1); R['mob_url'] = pg.url
            R['mob_tris'] = pg.evaluate('__forum.tris()')
            pg.evaluate('__forum.view([1418, __ctx.groundMesh(1436,313) + 16, 352], [1436, __ctx.groundMesh(1436,313) + 3, 316], 55)'); frames(pg, 3); pg.wait_for_timeout(800)
            who = pick_person(pg, ['idler', 'stall', 'kid', 'shopper', 'petition'], True)
            R['mob_person'] = who
            pg.evaluate('__forum.pick(-999, -999, true)')   # pick_person 试指时把他钉住了，先放开，不然这一点会把签收起来
            if who: pg.touchscreen.tap(who[1], who[2]); frames(pg, 2); pg.wait_for_timeout(500); R['mob_info'] = pg.inner_text('#info')
            shot(pg, f'{OUT}/mobile.jpg', quality=88)
            R['mob_logs'] = logs[:10]
            pg.close()
        b.close()
finally:
    srv.terminate()
json.dump(R, open(f'{OUT}/result.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1))
