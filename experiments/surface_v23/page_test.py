# -*- coding: utf-8 -*-
"""surface_v23 页面无头测试：拖滑杆到 70、开表面、点房（老房 + 新建房）、切 65，收集 JS 报错，存截图。——Hark（刘线）"""
import os, sys, json, subprocess, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
SHOTS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".path")
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766", "-d", os.path.join(ROOT, "docs")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1); errs = []; log = {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
        pg.goto("http://localhost:8766/living/xerolophos/", wait_until="load")
        pg.wait_for_function("window.__anth && window.__anth.houses.length>0", timeout=60000)
        pg.wait_for_timeout(1500)
        def slide(y):
            pg.evaluate(f"()=>{{const e=document.getElementById('yr');e.value={y};e.dispatchEvent(new Event('input',{{bubbles:true}}))}}")
            pg.wait_for_timeout(900)
        for y in (55, 60, 61, 64, 66, 70):
            slide(y)
        log["ylab70"] = pg.inner_text("#ylab"); log["ystat70"] = pg.inner_text("#ystat")
        pg.click("#surfbtn"); pg.wait_for_timeout(2500)
        log["panel70"] = pg.inner_text("#surf")[:300]
        # 点一栋新建房
        nh = pg.evaluate("()=>{const A=window.__anth;const h=A.newHouses.find(h=>h.built<=70&&h.destroyed>70);return [h.id,h.cx,h.cy]}")
        def click_world(x, y, z=2.2):
            pg.evaluate(f"()=>{{const c=window.__anth.cam;c.x={x};c.y={y};c.z={z}}}"); pg.wait_for_timeout(500)
            pg.mouse.click(700, 450); pg.wait_for_timeout(1200)
        click_world(nh[1], nh[2])
        log["newhouse_card"] = pg.inner_text("#cardbody")[:400]
        pg.screenshot(path=os.path.join(SHOTS, "v23_af70_newhouse.png"))
        # 点一栋老房（埃及人巷 70 号那类：页面房，有邻居讲述的优先）
        hid = pg.evaluate("()=>{const A=window.__anth;const ids=Object.keys(A.VOICES).map(Number);for(const id of ids){const h=A.houseById(id);if(h&&h.built<=65&&h.destroyed>70)return [h.id,h.cx,h.cy]}}")
        click_world(hid[1], hid[2], 2.6)
        log["house70_card"] = pg.inner_text("#cardbody")[:600]
        slide(65); pg.wait_for_timeout(2500)
        log["ylab65"] = pg.inner_text("#ylab"); log["panel65"] = pg.inner_text("#surf")[:200]
        log["house65_card"] = pg.inner_text("#cardbody")[:700]
        pg.screenshot(path=os.path.join(SHOTS, "v23_af65_house_card.png"))
        # 故事房标签/卡片
        st = pg.evaluate("()=>{const A=window.__anth;const id=13821;const h=A.houseById(id);return [h.cx,h.cy]}")
        click_world(st[0], st[1], 2.6)
        log["story65_card"] = pg.inner_text("#cardbody")[:500]
        # 回到 30 年（表面层无经济账）、街坊在说什么
        slide(30); pg.wait_for_timeout(800); log["panel30"] = pg.inner_text("#surf")[:120]
        slide(57); pg.click("#gsp"); pg.wait_for_timeout(800); log["gossip57"] = pg.inner_text("#cardbody")[:300]
        b.close()
finally:
    srv.terminate()
print(json.dumps(log, ensure_ascii=False, indent=1))
print("ERRORS", len(errs)); print("\n".join(errs[:30]))
