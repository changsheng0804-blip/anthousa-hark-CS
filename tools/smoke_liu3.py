"""liu3 无头自查：「街坊在说什么」入口——几个年份打开、每年三件事、点一户人家跳过去，控制台无报错；截图。
usage: python3 tools/smoke_liu3.py URL OUTDIR   (URL = .../docs/living/xerolophos/ locally, or the live Pages URL)"""
import sys, os, urllib.parse
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
errs, rows = [], []
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
        pg.wait_for_function('window.__anth', timeout=100000); pg.wait_for_timeout(9000)
        if pg.locator('#skip').is_visible(): pg.click('#skip'); pg.wait_for_timeout(800)
        for Y in ((35, 48, 55, 60) if vw['width'] > 500 else (60,)):
            pg.evaluate(f'window.__anth.setYear({Y})'); pg.wait_for_timeout(300)
            pg.click('#gsp'); pg.wait_for_timeout(400)
            txt = pg.inner_text('#cardbody')
            n = pg.locator('#card .gt').count()
            pg.screenshot(path=os.path.join(out, f'gossip_{vw["width"]}_{Y}.png'))
            jumped = ''
            if n:
                pg.locator('#card .gh button').first.click(); pg.wait_for_timeout(1900)
                jumped = pg.inner_text('#cardbody').split('\n')[0]
                pg.screenshot(path=os.path.join(out, f'gossip_{vw["width"]}_{Y}_jump.png'))
            rows.append((vw['width'], Y, n, txt.split('\n')[2:3], jumped))
        pg.close()
    b.close()
for r in rows: print(r)
print('errors:', errs or 'none')
sys.exit(1 if errs else 0)
