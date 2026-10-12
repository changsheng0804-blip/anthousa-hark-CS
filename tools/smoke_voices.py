"""Headless smoke test for the Liu-line voices: page loads without console errors, voices.json loads,
clicking voiced houses (by real mouse taps) shows the neighbour's story; saves a screenshot.
usage: python3 tools/smoke_voices.py URL [shot.png]"""
import sys, random
from playwright.sync_api import sync_playwright
url = sys.argv[1]; shot = sys.argv[2] if len(sys.argv) > 2 else None
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('response', lambda r: errs.append(f'{r.status} {r.url}') if r.status >= 400 else None)
    pg.goto(url, wait_until='networkidle'); pg.wait_for_timeout(2500)
    if pg.locator('#skip').is_visible(): pg.click('#skip'); pg.wait_for_timeout(800)
    n = pg.evaluate('Object.keys(window.__anth.VOICES).length')
    ids = pg.evaluate('Object.keys(window.__anth.VOICES)')
    random.seed(1); sample = random.sample(ids, 12)
    ok = tot = 0; first = None
    for Y in (50, 55, 60):
        pg.evaluate(f'window.__anth.setYear({Y})')
        for hid in sample:
            pg.evaluate(f'(()=>{{const A=window.__anth,h=A.houseById({hid});A.cam.x=h.cx;A.cam.y=h.cy;A.cam.z=3}})()')
            pg.wait_for_timeout(120); pg.mouse.click(640, 400); pg.wait_for_timeout(200)
            txt = pg.inner_text('#cardbody') if pg.locator('#card').is_visible() else ''
            tot += 1
            if '说' in txt and '——' in txt: ok += 1
            elif first is None: first = (Y, hid, txt[:120])
    # final screenshot: a voiced house at year 58 with its threads
    pg.evaluate('window.__anth.setYear(58)')
    pg.evaluate(f'(()=>{{const A=window.__anth,h=A.houseById({ids[0]});A.cam.x=h.cx-60;A.cam.y=h.cy;A.cam.z=2.2}})()')
    pg.wait_for_timeout(300); pg.mouse.click(640 + 60 * 2.2, 400); pg.wait_for_timeout(1500)
    card = pg.inner_text('#cardbody')
    if shot: pg.screenshot(path=shot)
    b.close()
print('voices loaded:', n)
print(f'taps showing a neighbour story: {ok}/{tot}', '(first miss:', first, ')')
print('card at 58:', card[:400].replace('\n', ' / '))
print('errors:', errs or 'none')
sys.exit(1 if errs or n < 200 else 0)
