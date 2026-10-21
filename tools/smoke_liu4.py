"""liu4 无头自查：门牌（街名·门牌·街区功能，来自上游事实 facts_upstream/）——
人家卡片有门牌、改写过的闲话提到自己的街、「街坊在说什么」每户标街名、相遇（scenes）标街名；桌面 + 手机，控制台无报错；截图。
usage: python3 tools/smoke_liu4.py URL OUTDIR"""
import sys, os, json, urllib.parse
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
errs, rows, fails = [], [], []
CASES = [(12992, 60, '运水人池街'), (12575, 47, '运水人巷'), (12575, 56, '运水人池街'), (16571, 60, '兵营街'), (6847, 59, '牧羊人巷'), (16668, 60, '新四街')]
with sync_playwright() as p:
    px = os.environ.get('HTTPS_PROXY') if url.startswith('https') else None
    kw = {}
    if px:
        u = urllib.parse.urlparse(px); kw['proxy'] = {'server': f'{u.scheme}://{u.hostname}:{u.port}', 'username': urllib.parse.unquote(u.username or ''), 'password': urllib.parse.unquote(u.password or '')}
    b = p.chromium.launch(**kw)
    for vw in ({'width': 1280, 'height': 800}, {'width': 390, 'height': 844}):
        pg = b.new_page(viewport=vw)
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('response', lambda r: errs.append(f'{r.status} {r.url}') if r.status >= 400 else None)
        pg.goto(url, wait_until='commit', timeout=60000)
        pg.wait_for_function('window.__anth', timeout=100000)
        pg.wait_for_function('Object.keys(window.__anth.ADDR.h).length>4000 && Object.keys(window.__anth.VOICES).length>300', timeout=60000)
        pg.wait_for_timeout(1500)
        if pg.locator('#skip').is_visible(): pg.click('#skip'); pg.wait_for_timeout(800)
        pg.wait_for_timeout(4000)  # let the opening greeting (Daphne's card) settle before opening houses
        for hid, Y, st in (CASES if vw['width'] > 500 else CASES[:2]):
            pg.evaluate(f'window.__anth.setYear({Y})'); pg.wait_for_timeout(250)
            # open the card through the gossip-jump path the page already exposes
            pg.evaluate(f"document.getElementById('cardbody').innerHTML='<button data-go=\"{hid}\" id=\"_go\">x</button>';document.getElementById('card').style.display='block'")
            pg.click('#_go'); pg.wait_for_timeout(1900)
            door = pg.inner_text('#card .door') if pg.locator('#card .door').count() else ''
            body = pg.inner_text('#cardbody')
            ok = st in door
            rows.append((vw['width'], hid, Y, door))
            if not ok: fails.append(f'{hid}@{Y}: 门牌里没有 {st}（{door!r}）')
            pg.screenshot(path=os.path.join(out, f'door_{vw["width"]}_{hid}_{Y}.png'))
        for Y in ((50, 60) if vw['width'] > 500 else (60,)):
            pg.evaluate(f'window.__anth.setYear({Y})'); pg.wait_for_timeout(300)
            pg.click('#gsp'); pg.wait_for_timeout(500)
            tags = pg.locator('#card .gh button i').count(); btns = pg.locator('#card .gh button').count()
            sts = pg.locator('#card .gq .st').count()
            rows.append((vw['width'], 'gossip', Y, f'{tags}/{btns} 户标了街名，{sts} 句标了街名'))
            if btns and not tags: fails.append(f'gossip@{Y}: 没有街名')
            pg.screenshot(path=os.path.join(out, f'gossip_{vw["width"]}_{Y}.png'))
        if vw['width'] > 500:
            sc = pg.evaluate("""(()=>{const A=window.__anth,o=[];for(const S of A.SCENES){A.setYear(S.y[0]);o.push([S.y[0],A.sceneWhere(S)])}return o})()""")
            for y, w in sc: rows.append((vw['width'], 'scene', y, w))
            if not any('（' in w for _, w in sc): fails.append('相遇没有一处标上街名')
        pg.close()
    b.close()
for r in rows: print(r)
for f in fails: print('✗', f)
print('errors:', errs or 'none')
sys.exit(1 if errs or fails else 0)
