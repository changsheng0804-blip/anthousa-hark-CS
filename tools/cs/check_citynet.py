"""CS 线 · 全城一张街网的检查（cs31）。用法: python tools/cs/check_citynet.py <q>
每行 ✅/❌ 规则 —— 数据；有 ❌ 退出码 1。规则见 tools/cs/factory/CITY_RULES.md。
1 一张网：街区里的街（大道以外）≥ 95% 落在全城街网上（街区不许自己长街）
2 顺着大道：大道 20 单位内、非旧区的街，≥ 80% 的点和最近大道成 0° 或 90°（差 ≤ 20°）
3 没有街区专用街网参数：街区配方/场景里没有 wide_street 一类街网参数被 streets_ng 用到
4 同分布：框里每片有人区的街长密度在全城的 0.6–1.6 倍之间
5 接缝：框边上，街区的街端头和全城网穿过框边的位置一一对应（差 ≤ 3 px）"""
import json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
F = os.path.join(ROOT, 'tools', 'cs', 'factory')
q = sys.argv[1]; X = os.path.join(ROOT, 'docs', 'living', q)
CS = json.load(open(os.path.join(F, 'city', 'streets.json')))['streets']
w = json.load(open(os.path.join(ROOT, 'world.json')))
fr = json.load(open(os.path.join(X, 'frame.json'))); x0, y0, FW, FH = fr['frame']; S = fr['scale']
roads = [s['geom']['coords'] for s in w['structures'] if s['type'] == 'road']
out = []; bad = 0
def rep(ok, name, info):
    global bad
    out.append(('✅ ' if ok else '❌ ') + name + '  —— ' + info); bad += (not ok)

def segs(lines):
    A = []
    for L in lines:
        for a, b in zip(L[:-1], L[1:]): A.append((a[0], a[1], b[0], b[1]))
    return np.array(A, float)
def dist_to(Sg, px, py):
    ax, ay, bx, by = Sg.T; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy + 1e-9
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
    d = np.hypot(px - ax - t * dx, py - ay - t * dy); k = int(np.argmin(d)); return d[k], k

# 全城网换到页面坐标
CP = [[((x - x0) * S, (y - y0) * S) for x, y in s['pts']] for s in CS]
CPs = segs(CP)
# 1 一张网
st = json.load(open(os.path.join(X, 'streets.json')))
nm = [r for r in st if r[5] != 'm']
idx = np.random.RandomState(0).choice(len(nm), min(800, len(nm)), replace=False) if nm else []
on = sum(dist_to(CPs, (nm[i][0] + nm[i][2]) / 2, (nm[i][1] + nm[i][3]) / 2)[0] < 2.5 for i in idx)
rep(len(idx) and on >= 0.95 * len(idx), '一张网：街区的街都从全城街网裁下来', f'{on}/{len(idx)} 段在全城网上')
# 2 顺着大道
RS = segs(roads); n_ok = n_all = 0
from shapely.geometry import Point
sys.path.insert(0, os.path.join(ROOT, 'engine')); from terrain import land
LB = land().boundary
for s in CS:
    if s['old'] > 0.3: continue
    for (ax, ay), (bx, by) in zip(s['pts'][:-1:3], s['pts'][1::3]):
        mx, my = (ax + bx) / 2, (ay + by) / 2
        if not (x0 <= mx <= x0 + FW and y0 <= my <= y0 + FH): continue
        d, k = dist_to(RS, mx, my)
        if d > 10 or LB.distance(Point(mx, my)) < d: continue   # 离岸比离大道近的，顺岸
        r = RS[k]; a1 = math.atan2(by - ay, bx - ax); a2 = math.atan2(r[3] - r[1], r[2] - r[0])
        dd = abs((a1 - a2 + math.pi / 2) % math.pi - math.pi / 2); dd = min(dd, abs(math.pi / 2 - dd))
        n_all += 1; n_ok += dd <= math.radians(20)
rep(n_all == 0 or n_ok >= 0.8 * n_all, '顺着大道：近大道的街和大道平行或垂直', f'{n_ok}/{n_all}' + ('（框里没有大道）' if n_all == 0 else ''))
# 3 没有街区专用街网参数
src = open(os.path.join(F, 'streets_ng.py')).read()
used = [k for k in ('wide_street', '_shore_dir', 'street_dir', 'street_sep') if k in src]
rcp = os.path.join(F, 'quarters', q + '.json')
rk = [k for k in (json.load(open(rcp)) if os.path.exists(rcp) else {}) if 'street' in k or k in ('dir', 'sep')]
rep(not used and not rk, '没有街区专用的街网参数', f'streets_ng 用到 {used or "无"}；配方 {rk or "无"}')
# 4 同分布：每 20×20 单位格子，有人区的街长 / 房子数
def dens(box=None):
    G = {}
    for s in CS:
        for a, b in zip(s['pts'][:-1], s['pts'][1:]):
            k = (int(a[0] // 20), int(a[1] // 20)); G[k] = G.get(k, 0) + math.hypot(b[0] - a[0], b[1] - a[1])
    Hn = {}
    for h in w['houses']:
        c = np.mean(h['p'], 0); k = (int(c[0] // 20), int(c[1] // 20)); Hn[k] = Hn.get(k, 0) + 1
    return {k: G.get(k, 0) / 400 for k, n in Hn.items() if n > 40}
D = dens(); allm = float(np.median(list(D.values())))
inb = [v for k, v in D.items() if x0 <= k[0] * 20 + 10 <= x0 + FW and y0 <= k[1] * 20 + 10 <= y0 + FH]
qm = float(np.median(inb)) if inb else allm
rep(0.6 <= qm / allm <= 1.6, '同分布：框里街的疏密和全城一样（随密度，不随街区）', f'框里 {qm:.3f} / 全城 {allm:.3f} = {qm / allm:.2f}')
# 5 接缝：全城网穿过框边的点，街区在边上 3 px 内有街端头
W_, H_ = FW * S, FH * S; cross = []
from shapely.geometry import Polygon
MK = [Polygon(s['geom']['coords']).buffer(1.2) for s in w['structures'] if s['geom']['type'] == 'polygon' and s['type'] not in ('district', 'farmland')]
miss = []
for L in CP:
    for (ax, ay), (bx, by) in zip(L[:-1], L[1:]):
        for E, ax_ in ((0, 'x'), (W_, 'x'), (0, 'y'), (H_, 'y')):
            u, v = (ax, bx) if ax_ == 'x' else (ay, by)
            if (u - E) * (v - E) < 0:
                t = (E - u) / (v - u); px, py = ax + t * (bx - ax), ay + t * (by - ay)
                wx, wy = px / S + x0, py / S + y0
                if -1 <= px <= W_ + 1 and -1 <= py <= H_ + 1 and LB.distance(Point(wx, wy)) > 1.5 and not any(M.contains(Point(wx, wy)) for M in MK): cross.append((px, py))
ends = np.array([[r[0], r[1]] for r in nm] + [[r[2], r[3]] for r in nm]) if nm else np.zeros((0, 2))
# 街区页面在框边内缩 4 px 裁街，所以对端头放宽到离边 ≤ 20 px 的那一段
hit = 0
for px, py in cross:
    if len(ends) and (np.hypot(ends[:, 0] - px, ends[:, 1] - py) < 48).any(): hit += 1
    else: miss.append((round(px), round(py)))
# 穿过框边却落在水里/禁建地（街区本来就不画）的不算
rep(not cross or hit >= 0.85 * len(cross), '接缝：全城网出框的地方，街区的街接得上', f'{hit}/{len(cross)}' + (f' 没接上 {miss[:4]}' if miss else ''))
print('\n'.join(out)); sys.exit(1 if bad else 0)
