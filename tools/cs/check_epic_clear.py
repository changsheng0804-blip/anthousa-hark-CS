#!/usr/bin/env python3
"""/goal 4 G3 检查：史诗地块先占地——world.json 里的史诗建筑（广场、宁芙泉、大粮仓、浴场、教堂、宫、竞技场、水渠桥、粮仓、蓄水池、市场、营房、堡垒、修道院……
多边形结构；港口是水域盒子、片区/农田/城墙/城门不算）存续期内，脚印下 0 栋房、0 段街。
 ① 派生表 houses_street.json（全城 9 块、含重叠区的副本）：每栋房（含 lm: 地标）在 [开工, 拆毁) 内，与史诗存续期 [建成, 拆毁) 有交集时，
    房与脚印的相交面积 ≤ 房面积的 1e-3（世界单位²）；
 ② 街 streets.json：每段街在 [开),[关) 内与史诗存续期有交集时，穿过脚印的长度 ≤ 0.05 世界单位；
 ③ 瓦片 vec 里没有压在史诗脚印里的房（读 h[5] 底账 id → 派生表里的年份）。
 年份、脚印全读 world.json，不自编；叠层「旧街坊」的拆房记在 tiles/epic_cleared.json（epic_clear.py 写）。——Hark（CS线）"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, 'factory'))
import landmarks_city as L
from shapely.geometry import Polygon, LineString
SKIP = {'district', 'farmland', 'wall', 'gate', 'harbor'}
EP = [s for s in L.W['structures'] if s['geom']['type'] == 'polygon' and s['type'] not in SKIP]
bad = []; nh = ns = 0
PE = [(e, Polygon(e['geom']['coords']).buffer(0), e['built'], e['destroyed'] if e['destroyed'] is not None else 9999) for e in EP]
for q in L.QS:
    HS = json.load(open(os.path.join(L.LIV, q, 'houses_street.json')))['houses']; ST = json.load(open(os.path.join(L.LIV, q, 'streets.json')))
    for h in HS:
        if h[3] <= h[2]: continue
        Q = L.wpoly(q, h[4]).buffer(0); nh += 1
        for e, P, eb, ee in PE:
            if h[2] < ee and h[3] > eb and Q.intersects(P) and Q.intersection(P).area > 1e-3 * max(Q.area, 1e-9):
                bad.append(f"{q} 房 h{h[0]}（{h[2]}–{h[3]}）压在 {e['id']}（{eb}–{ee if ee < 9999 else '今'}）脚印里 {Q.intersection(P).area / Q.area:.0%}")
    for s in ST:
        sb = s[6]; se = s[7] or 9999
        if se <= sb: continue
        ln = LineString([L.to_world(q, s[0], s[1]), L.to_world(q, s[2], s[3])]); ns += 1
        for e, P, eb, ee in PE:
            if sb < ee and se > eb and ln.intersects(P) and ln.intersection(P).length > 0.05:
                bad.append(f"{q} 街 ({s[0]:.0f},{s[1]:.0f})（{sb}–{se if se < 9999 else '今'}）穿过 {e['id']}（{eb}）脚印 {ln.intersection(P).length:.2f}")
# ③ vec（页面真正画的）：脚印取 vec 里那栋房的底面四边形，年份用 vec 自己的 [开工, 拆毁)
nv = 0
for f in glob.glob(os.path.join(L.OUT, 'vec', '*.json')):
    for r in json.load(open(f))['h']:
        if r[1] <= r[0] or str(r[5]).startswith('epic:'): continue   # 'epic:' 行是史诗自己的分期部件（check_epic_stage.py ⑥ 按部件年份查）
        nv += 1; i = r[5]
        Q = Polygon([(L.X0 + r[3][k] / L.S, L.Y0 + r[3][k + 1] / L.S) for k in range(0, len(r[3]) - 1, 2)][:4]).buffer(0)   # vec 里的底面四边形（全城瓦片像素）→ 世界坐标
        for e, P, eb, ee in PE:
            if r[0] < ee and r[1] > eb and Q.intersects(P) and Q.intersection(P).area > 1e-3 * max(Q.area, 1e-9):
                bad.append(f"vec {os.path.basename(f)} {i}（{r[0]}–{r[1]}）压在 {e['id']}（{eb}）脚印里")
bad = sorted(set(bad))
print(f'{len(EP)} 座史诗多边形；查 {nh} 栋房（含副本）、{ns} 段街、vec {nv} 栋')
print('\n'.join('❌ ' + b for b in bad[:40]) + (f'\n… 共 {len(bad)} 条' if len(bad) > 40 else '') or '✅ 全过'); sys.exit(1 if bad else 0)
