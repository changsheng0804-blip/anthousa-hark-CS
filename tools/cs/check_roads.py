#!/usr/bin/env python3
"""/goal 4 G5 检查：道路规则（谭线 HANDOFF 第 4 节，搬到 CS 派生表上）。九块街区，各自 houses_street.json + streets.json（街区本地像素）。
 ① 房不压路：任一房在 [开工,拆毁) 内，与同期在世的街（[开,关)）——街面（中线 ± 半宽×0.5）与房脚印相交面积 = 0（压路 0，strict）；
 ② 无孤岛：在 30..155 年每 5 年各查一次，在世的小巷/院巷（l、c）若与街网（含出框边——出框的街在邻块接上）断开，算孤岛，必须 0；
 ③ 水渠桥下只有大街：渠桥（aqb_*）存续期内穿过它脚印的街，只许 m/s 两类，小巷（l、c）不行（蓄水池/广场/宁芙泉由 check_epic_clear 管）。
 年份、脚印读派生表 + world.json；不自编。——Hark（CS线）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, 'factory'))
import landmarks_city as L
from shapely.geometry import Polygon, LineString
from shapely.strtree import STRtree
YEARS = list(range(30, 156, 5)); HALF = float(os.environ.get("CHK_HALF", "0.5"))   # 街面取半宽的一半：贴边的墙角不算压路，压到路中心带才算
bad = []; stats = {}
AQB = [(s['id'], Polygon(s['geom']['coords']).buffer(0), s['built'], s['destroyed'] if s['destroyed'] is not None else 9999)
       for s in L.W['structures'] if s['geom']['type'] == 'polygon' and str(s['id']).startswith('aqb')]
def alive(s, Y): return s[6] <= Y and not (s[7] and s[7] <= Y)
for q in L.QS:
    HS = json.load(open(os.path.join(L.LIV, q, 'houses_street.json')))['houses']; ST = json.load(open(os.path.join(L.LIV, q, 'streets.json')))
    fr = json.load(open(os.path.join(L.LIV, q, 'frame.json'))); FW, FH = fr['frame'][2] * fr['scale'], fr['frame'][3] * fr['scale']
    # ① 房不压路
    bands = [LineString([(s[0], s[1]), (s[2], s[3])]).buffer(max(s[4] * HALF / 2, 0.3), cap_style=2) for s in ST]
    T = STRtree(bands); n1 = 0
    for h in HS:
        if h[3] <= h[2]: continue
        P = Polygon([(h[4][i], h[4][i + 1]) for i in range(0, 8, 2)]).buffer(0)
        for j in T.query(P):
            s = ST[j]; sb, se = s[6], (s[7] or 9999)
            if se <= sb or not (h[2] < se and h[3] > sb): continue
            a = P.intersection(bands[j]).area
            if a > 1e-3 * max(P.area, 1e-9):
                n1 += 1; bad.append(f"{q} 房 h{h[0]}（{h[2]}–{h[3]}）压在街 ({s[0]:.0f},{s[1]:.0f})-({s[2]:.0f},{s[3]:.0f}) {s[5]}（{sb}–{se if se < 9999 else '今'}）上 {a / P.area:.0%}")
                break
    # ② 无孤岛
    n2 = 0
    for Y in YEARS:
        V = [s for s in ST if alive(s, Y)]
        par = list(range(len(V)))
        def f(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        grid = {}
        for i, s in enumerate(V):
            for (x, y) in ((s[0], s[1]), (s[2], s[3])):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        pass
                grid.setdefault((round(x / 3), round(y / 3)), []).append(i)
        for k, ids in grid.items():
            for dx in (0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((k[0] + dx, k[1] + dy), []):
                        for i in ids:
                            if i != j: par[f(i)] = f(j)
        # 街的中线上相交也算连通（T 字路口：小巷端点落在大街中段）
        lines = [LineString([(s[0], s[1]), (s[2], s[3])]).buffer(2.0) for s in V]
        T2 = STRtree(lines)
        for i, ln in enumerate(lines):
            for j in T2.query(ln):
                if j != i and ln.intersects(lines[j]): par[f(i)] = f(j)
        comp = {}
        for i, s in enumerate(V): comp.setdefault(f(i), []).append(i)
        for r, ids in comp.items():
            edge = any(min(V[i][0], V[i][2]) < 14 or max(V[i][0], V[i][2]) > FW - 14 or min(V[i][1], V[i][3]) < 14 or max(V[i][1], V[i][3]) > FH - 14 for i in ids)
            mainy = any(V[i][5] in ('m', 's') for i in ids)
            if not edge and not mainy and all(V[i][5] in ('l', 'c') for i in ids):
                n2 += 1; s = V[ids[0]]; bad.append(f"{q} {Y} 年孤岛：{len(ids)} 段小巷/院巷（如 ({s[0]:.0f},{s[1]:.0f})）与街网断开")
    # ③ 渠桥下小巷
    n3 = 0
    for s in ST:
        if s[5] not in ('l', 'c'): continue
        ln = LineString([L.to_world(q, s[0], s[1]), L.to_world(q, s[2], s[3])]); sb, se = s[6], (s[7] or 9999)
        for i, P, eb, ee in AQB:
            if sb < ee and se > eb and ln.intersects(P) and ln.intersection(P).length > 0.05:
                n3 += 1; bad.append(f"{q} 小巷 ({s[0]:.0f},{s[1]:.0f})（{sb}–{se}）穿过渠桥 {i} 脚印"); break
    stats[q] = (n1, n2, n3)
print('各块 [压路, 孤岛, 渠桥下小巷]：' + ' '.join(f'{k}={v}' for k, v in stats.items()))
uniq = sorted(set(bad))
print('\n'.join('❌ ' + b for b in uniq[:30]) + (f'\n… 共 {len(uniq)} 条' if len(uniq) > 30 else '') or '✅ 全过'); sys.exit(1 if uniq else 0)
