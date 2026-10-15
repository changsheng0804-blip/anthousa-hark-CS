# -*- coding: utf-8 -*-
"""surface_v23：用无头浏览器从页面现有代码里导出每栋房的推演人家（fams：入住年 B、散列行当 trade），供行当统一与冲突统计用。
页面行当是 household() 里按房屋 id 散列出来的，Python 复刻 rng 容易错，直接从页面取。输出 .path/fams.json（不入库）。——Hark（刘线）"""
import os, json, subprocess, time, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "-d", os.path.join(ROOT, "docs")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1200, "height": 800})
        pg.goto("http://localhost:8765/living/xerolophos/", wait_until="load")
        pg.wait_for_function("window.__anth && window.__anth.houses.length>0", timeout=60000)
        d = pg.evaluate("""()=>{const A=window.__anth,o={};for(const h of A.houses){const hh=A.household(h);o[h.id]=hh.fams.map(f=>[f.B,f.trade,f.out])}return o}""")
        json.dump(d, open(os.path.join(HERE, ".path", "fams.json"), "w"), ensure_ascii=False)
        print(len(d))
        b.close()
finally:
    srv.terminate()
