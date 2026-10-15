#!/usr/bin/env python3
"""无头浏览器打开 CS 干山页（docs/living/xerolophos/），真的点几栋房子，看敲门卡里的「生计/房况」段；收集 JS 报错，截图。
python3 liu/tools/shot_econ_card.py [输出目录]   ——Hark（刘线）"""
import os, sys, json, time, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work_shots'); os.makedirs(OUT, exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'docs', 'living')))
threading.Thread(target=srv.serve_forever, daemon=True).start(); url = f'http://127.0.0.1:{srv.server_address[1]}/xerolophos/'
exe = os.environ.get('CHROMIUM')
res = {'url': url, 'clicks': [], 'errors': [], 'requests_econ_before_click': 0}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe, args=['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader']) if exe else p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    reqs = []; pg.on('request', lambda r: reqs.append(r.url))
    pg.on('pageerror', lambda e: res['errors'].append('pageerror: ' + str(e)))
    pg.on('console', lambda m: res['errors'].append('console.error: ' + m.text) if m.type == 'error' else None)
    pg.goto(url); pg.wait_for_function('window.__anth&&window.__anth.houses&&window.__anth.houses.length>0&&window.__econ', timeout=60000); time.sleep(2.5)
    res['requests_econ_before_click'] = sum('/econ/' in u for u in reqs)
    box = pg.evaluate("(()=>{const c=document.querySelector('canvas');const r=c.getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    for Y, hid in ((50, 2604), (60, 2617), (40, 2611)):
        pg.evaluate(f"window.__anth.setYear({Y});document.getElementById('yr').value={Y}"); time.sleep(0.8)
        pg.evaluate(f"(()=>{{const A=window.__anth,h=A.houseById({hid});A.cam.x=h.cx;A.cam.y=h.cy;A.cam.z=3}})()"); time.sleep(0.8)
        pg.mouse.click(box[0] + box[2] / 2, box[1] + box[3] / 2); 
        try: pg.wait_for_selector('#card .obj.econ', timeout=8000); ok = True
        except Exception: ok = False
        time.sleep(0.4)
        txt = pg.evaluate("(()=>{const e=document.querySelector('#card .obj.econ');return e?e.innerText:''})()")
        h2 = pg.evaluate("(()=>{const e=document.querySelector('#card h2');return e?e.innerText:''})()")
        f = os.path.join(OUT, f'card_AF{Y}_h{hid}.png'); pg.screenshot(path=f)
        res['clicks'].append({'year': Y, 'aim': hid, 'h2': h2, 'econ_shown': ok, 'econ_text': txt, 'shot': f})
    res['requests_econ_total'] = sum('/econ/' in u for u in reqs)
    b.close()
json.dump(res, open(os.path.join(OUT, 'result.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(0 if not res['errors'] and all(c['econ_shown'] for c in res['clicks']) else 1)
