"""liu2 无头自查：页面无报错、voices.json 后台加载完成、不同年份 × 不同时辰点房子，「此刻」随时辰变化；截图。
Headless check for liu2: no console errors; voices.json loads in the background (page usable before it arrives);
taps voiced houses (old and newly-arrived families) at several years and four times of day, checks the 'now' line
follows the hour; saves screenshots.
usage: python3 tools/smoke_liu2.py URL OUTDIR
"""
import sys, os, json, urllib.parse
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
errs = []
CLOCKS = {'morning': 6.5, 'day': 12, 'evening': 19.2, 'night': 23}
with sync_playwright() as p:
    px = os.environ.get('HTTPS_PROXY') if url.startswith('https') else None
    kw = {}
    if px:
        u = urllib.parse.urlparse(px); kw['proxy'] = {'server': f'{u.scheme}://{u.hostname}:{u.port}', 'username': urllib.parse.unquote(u.username or ''), 'password': urllib.parse.unquote(u.password or '')}
    b = p.chromium.launch(**kw)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('response', lambda r: errs.append(f'{r.status} {r.url}') if r.status >= 400 else None)
    pg.goto(url, wait_until='commit', timeout=60000)
    pg.wait_for_function('window.__anth', timeout=100000)
    early = pg.evaluate('Object.keys(window.__anth.VOICES).length')
    pg.wait_for_function('Object.keys(window.__anth.VOICES).length>300', timeout=100000); pg.wait_for_timeout(1200)
    if pg.locator('#skip').is_visible(): pg.click('#skip'); pg.wait_for_timeout(800)
    V = pg.evaluate('window.__anth.VOICES')
    old = [k for k, v in V.items() if v['fam'] <= 50][:4]
    new = [k for k, v in V.items() if v['fam'] > 50 and v['nowY'] and v['nowY'][0] <= 60][:6]
    rows = []; changed = 0; shown = 0; tot = 0
    def tap(hid, Y, per, shot=None):
        pg.evaluate(f'window.__anth.setYear({Y})')
        pg.evaluate(f'window.__anth.clock={CLOCKS[per]}')
        pg.evaluate(f'(()=>{{const A=window.__anth,h=A.houseById({hid});A.cam.x=h.cx;A.cam.y=h.cy;A.cam.z=3}})()')
        pg.wait_for_timeout(250); pg.mouse.click(640, 400); pg.wait_for_timeout(350)
        txt = pg.inner_text('#cardbody') if pg.locator('#card').is_visible() else ''
        if shot: pg.screenshot(path=os.path.join(out, shot))
        now = next((l for l in txt.split('\n') if l.startswith('此刻')), '')
        return txt, now
    for hid in old + new:
        Y = V[hid]['nowY'][1]
        seen = {}
        for per in CLOCKS:
            txt, now = tap(hid, Y, per)
            tot += 1
            if now: shown += 1
            seen[per] = now
            rows.append({'id': hid, 'year': Y, 'per': per, 'now': now, 'story': ('——' in txt)})
        if len(set(seen.values())) == 4: changed += 1
    # screenshots: a newcomer family at dawn and at night, an old family at dusk, another year
    tap(new[0], V[new[0]]['nowY'][1], 'morning', 'new_morning.png')
    tap(new[1], V[new[1]]['nowY'][1], 'night', 'new_night.png')
    tap(old[0], V[old[0]]['nowY'][1], 'evening', 'old_evening.png')
    tap(old[1], 52, 'day', 'old_y52_day.png')
    # a non-voiced house: the generic hill line must not send a hill family to the quay
    gen = pg.evaluate('''(()=>{const A=window.__anth,out=[];for(const h of A.houses){if(A.VOICES[h.id]||A.STORIES[h.id])continue;if(!(h.built<=55&&h.destroyed>55))continue;out.push(h.id);if(out.length>=40)break}return out})()''')
    quay = 0
    for hid in gen[:25]:
        txt, now = tap(hid, 55, 'morning')
        if '码头' in now:
            fam = pg.evaluate(f'(()=>{{const A=window.__anth;const hh=A.household(A.houseById({hid}));let f=hh.fams[0];for(const x of hh.fams)if(x.B<=55)f=x;return f.trade}})()')
            if fam != '运水人': quay += 1
    b.close()
json.dump(rows, open(os.path.join(out, 'taps.json'), 'w'), ensure_ascii=False, indent=1)
print('voices at first paint:', early, '(0 = loaded in background, page did not wait)')
print('voices loaded:', len(V))
print(f'taps with a 此刻 line: {shown}/{tot}; households whose 此刻 differs in all four periods: {changed}/{len(old + new)}')
print('generic lines putting a non-water-carrier at the quay:', quay)
print('errors:', errs or 'none')
sys.exit(1 if errs or len(V) < 300 or quay else 0)
