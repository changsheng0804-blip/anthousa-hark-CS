"""CS 线 · cs26 分区（埋在底下的规则，从底账推）
判法照上游 tanxinhao 线 tools/district_rules.py classify() 的优先顺序（v23），前面加上南港自己的两档：
  1 码头货栈 dock   ：贴着建成的港岸 / 栈桥（≤ 70px）。港挖成后两年起；栈桥建成后，旁边的住家由近到远、每 20px 晚一年改成货栈
  2 仓场 horrea     ：粮仓建成后，粮仓周围 ≤ 110px
  3 汲水坊 water    ：蓄水池 / 水神殿建成后周围 ≤ 130px                           （上游第 1 档）
  4 新街坊 planned  ：火烧地上（48 年烧掉的房子 ≤ 14px 以内）重建的房子，49 年起    （上游第 2 档）
  5 市集 market / 铺面 shops：临主街（≤ 12px）；离主街交叉口 ≤ 170px 是市集        （上游第 3 档，按单户离街代替街区临街比）
  6 民居 homes
上游的兵营坊 / 作坊 / 体面人家 / 菜园在南港这块地里没有对应的东西（没有兵营、城门、浴场），不判。
输出 scene.json zones：{房子 id: [[起年, 代号], ...]}（只记变化）、zone_labels：{年: [[x, y, 代号], ...]}（远看时像旧地图那样写街区名，民居不写）。"""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'; Q = os.path.join(ROOT, 'docs', 'living', q)
sc = json.load(open(os.path.join(Q, 'scene.json'))); city = json.load(open(os.path.join(Q, 'city.json'))); HD = json.load(open(os.path.join(Q, 'houses.json')))
F = sc.get('fleet', {}); LM = {l['id']: l for l in city['landmarks']}; LATE = HD.get('late', {})
hs = []
for id_, d_, b, e, p in HD['houses']:
    if e <= 1 or e <= b + 1: continue
    xs, ys = p[0::2], p[1::2]; hs.append((id_, b, e, sum(xs) / len(xs), sum(ys) / len(ys)))
ids = np.array([h[0] for h in hs]); B = np.array([h[1] for h in hs]); E = np.array([h[2] for h in hs]); X = np.array([h[3] for h in hs]); Yc = np.array([h[4] for h in hs])
def segd(px, py, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay; t = np.clip(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
    return np.hypot(px - ax - t * dx, py - ay - t * dy)
def near_pts(P, r):
    if not P: return np.full(len(X), 1e9)
    P = np.asarray(P, float); return np.min(np.hypot(X[:, None] - P[None, :, 0], Yc[:, None] - P[None, :, 1]), 1)
# 1 码头：港岸 = 泊位、码头站位（不在栈桥上的）、港墙；栈桥 = 每座的格子
hb = F.get('harbor_from', 33)
quay_pts = [F['quay']] + [s for s in F.get('spots', []) if s not in F.get('pier_spots', [])] + F.get('wall', [])
d_quay = near_pts(quay_pts, 70)
# 港岸线：步行网里的水格（底账和画都算水）离房子多近；只算港里（离港的地标 ≤ 420px），开阔海滩不算
from scipy import ndimage as ndi
WK = F['walk']; wat = np.array([c == 'w' for c in WK['quay']]).reshape(WK['H'], WK['W'])
wat = ndi.binary_opening(wat, iterations=2)   # 画上的小船不算岸
dist_w = ndi.distance_transform_edt(~wat) * WK['R']
d_water = dist_w[np.clip((Yc // WK['R']).astype(int), 0, WK['H'] - 1), np.clip((X // WK['R']).astype(int), 0, WK['W'] - 1)]
HARB = []
for k, l in LM.items():
    if k.startswith('harbor'):
        st = next((s_ for s_ in json.load(open(os.path.join(ROOT, 'world.json')))['structures'] if s_['id'] == k), None)
        HARB.append((l['xy'], st['built'] if st else hb))
d_pier = [near_pts([[r[0] + r[2] / 2, r[1] + r[3] / 2] for r in d['rects']], 70) for d in F.get('docks', [])]
# 2 仓场
GR = [(k, LATE[k]['built'], LM[k]['xy']) for k in LATE if k.startswith('horrea') and k in LM]
# 3 汲水坊
WA = [(k, LATE[k]['built'], LM[k]['xy'] if k in LM else np.mean(LATE[k]['p'], 0)) for k in LATE if k.startswith(('cistern', 'nymph'))]
# 4 火烧地：48 年被烧掉的房子
burnt = (E == 48); bx, by = X[burnt], Yc[burnt]
d_burn = np.min(np.hypot(X[:, None] - bx[None], Yc[:, None] - by[None]), 1) if burnt.any() else np.full(len(X), 1e9)
# 5 主街
R = [r['pts'] for r in city['roads']]
d_road = np.full(len(X), 1e9)
for P in R:
    for a, b in zip(P[:-1], P[1:]): d_road = np.minimum(d_road, segd(X, Yc, a, b))
def _inter(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9: return None
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d; u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    if 0 <= t <= 1 and 0 <= u <= 1: return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
MJ = [q_ for i in range(len(R)) for j in range(i + 1, len(R)) for a, b in zip(R[i][:-1], R[i][1:]) for c, d in zip(R[j][:-1], R[j][1:]) for q_ in [_inter(a, b, c, d)] if q_]
d_mj = near_pts(MJ, 170)

# 南港的主街画得宽、房子退在街后：临街那一排离街中线 20–40px。取全区离街最近 10% 的距离当临街线（上游按街区临街比，这里按单户）
ROAD_R = float(np.percentile(d_road, 10)); QUAY_R = float(np.percentile(d_quay, 1)) + 40
def classify(Y):
    z = np.array(['homes'] * len(X), dtype=object)
    road = d_road <= ROAD_R
    z[road] = 'shops'; z[road & (d_mj <= 170)] = 'market'
    z[(B >= 49) & (d_burn <= 14) & (Y >= 49)] = 'planned'
    for k, y0, xy in WA:
        if Y >= y0: z[np.hypot(X - xy[0], Yc - xy[1]) <= 130] = 'water'
    for k, y0, xy in GR:
        if Y >= y0: z[np.hypot(X - xy[0], Yc - xy[1]) <= 110] = 'horrea'
    for xy, y0 in HARB:
        if Y >= y0 + 2: z[(d_water <= 72) & (np.hypot(X - xy[0], Yc - xy[1]) <= 420)] = 'dock'
    if Y >= hb + 2: z[d_quay <= QUAY_R] = 'dock'
    for d, dp in zip(F.get('docks', []), d_pier):
        z[(dp <= QUAY_R) & (Y >= d['from'] + 1 + dp // 20)] = 'dock'
    return z
zones = {}; prev = None; labels = {}
for Y in range(0, 61):
    z = classify(Y)
    for i in range(len(X)):
        if prev is None or z[i] != prev[i]: zones.setdefault(str(int(ids[i])), []).append([Y, z[i]])
    prev = z
    alive = (B <= Y) & (E > Y); L = []
    for code in ('dock', 'horrea', 'water', 'planned', 'market', 'shops'):
        m = alive & (z == code)
        if m.sum() < 8: continue
        # 80px 格子里够 6 户的格子聚成团，每团写一处，同名 360px 内只写一次
        gx, gy = (X[m] // 80).astype(int), (Yc[m] // 80).astype(int); cells = {}
        for a, b_, x, y in zip(gx, gy, X[m], Yc[m]): cells.setdefault((a, b_), []).append((x, y))
        big = sorted(((len(v), np.mean(v, 0)) for v in cells.values() if len(v) >= 6), key=lambda t: -t[0])
        for n, c in big:
            if all(not (l[2] == code and math.hypot(l[0] - c[0], l[1] - c[1]) < 360) for l in L): L.append([int(c[0]), int(c[1]), code])
    labels[str(Y)] = L
sc['zones'] = zones; sc['zone_labels'] = labels
json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
from collections import Counter
for Y in (30, 40, 50, 60):
    z = classify(Y); al = (B <= Y) & (E > Y); print(Y, dict(Counter(z[al])), len(labels[str(Y)]))
if '--dbg' in sys.argv:
    print('road', np.percentile(d_road, [1, 5, 10, 25, 50]).round(1), 'quay', np.percentile(d_quay, [1, 5]).round(1), 'mj', len(MJ), [len(r) for r in R])
