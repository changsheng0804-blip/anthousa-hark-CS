"""CS 线 · cs27 货栈长屋：分区里的码头货栈、仓场不再是一个个小民房，而是并成一排排长屋（照画上粮仓的样子：长条瓦顶、一道屋脊、浅色墙边）。
做法：每年把货栈/仓场房子按 ≤26px 连成团；每团按主方向（PCA）切成长 ≤ 60px、宽 ≤ 24px 的长屋，盖住团里所有小房子。
瓦色取那一年用的关键年画上、长屋中心一圈的瓦色，旧一点灰一点。
输出 scene.json halls：{年: [[cx, cy, ux, uy, 半长, 半宽, r, g, b], ...]}（33–60 年，只有分区里有货栈的年份）。"""
import json, math, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'; Q = os.path.join(ROOT, 'docs', 'living', q)
sc = json.load(open(os.path.join(Q, 'scene.json'))); HD = json.load(open(os.path.join(Q, 'houses.json')))
Z = sc.get('zones') or {}; W, H = 1820, 2048
def at(z, Y):
    c = 'homes'
    for y, k in z:
        if y <= Y: c = k
    return c
KA = {}
def key_img(Y):
    K = min([k for k in sc['keys'] if Y <= k[0]] or [sc['keys'][-1]], key=lambda k: k[0])
    if K[0] not in KA: KA[K[0]] = np.asarray(Image.open(os.path.join(Q, K[1])).convert('RGB').resize((W, H))).astype(float)
    return KA[K[0]]
HS = [(h[0], h[2], h[3], np.array(h[4], float).reshape(-1, 2)) for h in HD['houses'] if h[3] > h[2] + 1 and h[3] > 1]
LATE = HD.get('late', {}); LP = []
for k_, l_ in LATE.items():
    p_ = np.array(l_['p'], float); c_ = p_.mean(0); LP.append(c_ + (p_ - c_) * 1.25)
def _inpoly(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
out = {}
for Y in range(0, 61):
    P = [(i, p) for i, b, e, p in HS if b <= Y < e and at(Z.get(str(i), []), Y) in ('dock', 'horrea')]
    if not P: continue
    A = key_img(Y); C = np.array([p.mean(0) for _, p in P])
    # 连成团：中心距离 ≤ 18px
    n = len(C); par = list(range(n))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    D = np.hypot(C[:, None, 0] - C[None, :, 0], C[:, None, 1] - C[None, :, 1])
    for i, j in zip(*np.nonzero(np.triu(D <= 26, 1))): par[f(i)] = f(j)
    groups = {}
    for i in range(n): groups.setdefault(f(i), []).append(i)
    halls = []
    for g in groups.values():
        pts = np.vstack([P[i][1] for i in g]); m = pts.mean(0)
        if len(g) == 1:
            e = pts[1] - pts[0] if np.hypot(*(pts[1] - pts[0])) >= np.hypot(*(pts[2] - pts[1])) else pts[2] - pts[1]; u = e / (np.hypot(*e) or 1)
        else:
            w_, v_ = np.linalg.eigh(np.cov((pts - m).T)); u = v_[:, -1]
            if w_[-1] < 2.2 * w_[0]: u = np.array([1., 0.])   # 团不够长：照港岸横平竖直
            else:
                a_ = math.atan2(u[1], u[0]); a_ = round(a_ / (math.pi / 12)) * (math.pi / 12); u = np.array([math.cos(a_), math.sin(a_)])   # 15° 一档，免得一排排长屋歪得各不相同
        if u[0] < 0: u = -u
        v = np.array([-u[1], u[0]]); s = (pts - m) @ u; t = (pts - m) @ v
        s0, s1, t0, t1 = s.min() - 1, s.max() + 1, t.min() - 1, t.max() + 1
        ns = max(1, round((s1 - s0) / 58)); nt = max(1, round((t1 - t0) / 25)); cs_ = C[g]; cs_s = (cs_ - m) @ u; cs_t = (cs_ - m) @ v   # 长屋之间留 6–7px 的巷子
        for a in range(ns):
            for b in range(nt):
                sa, sb = s0 + (s1 - s0) * a / ns, s0 + (s1 - s0) * (a + 1) / ns; ta, tb = t0 + (t1 - t0) * b / nt, t0 + (t1 - t0) * (b + 1) / nt
                if any(_inpoly(c_, cc_) for cc_ in LP for c_ in [m + u * (sa + sb) / 2 + v * (ta + tb) / 2]): continue   # 不压在粮仓等地标上
                inside = (cs_s >= sa) & (cs_s <= sb) & (cs_t >= ta) & (cs_t <= tb)
                if inside.sum() < (1 if len(g) <= 2 else 2): continue
                c = m + u * (sa + sb) / 2 + v * (ta + tb) / 2; hl, hw = max((sb - sa) / 2 - 3, 7), min(max((tb - ta) / 2 - 3.5, 5), 10)
                x0, y0 = int(np.clip(c[0], 4, W - 5)), int(np.clip(c[1], 4, H - 5)); ring = A[y0 - 26:y0 + 26, x0 - 26:x0 + 26].reshape(-1, 3)
                roofish = ring[(ring[:, 0] > ring[:, 2] + 70) & (ring[:, 0] > ring[:, 1] + 40)]   # 只取瓦（红），不取沙地
                col = np.median(roofish, 0) if len(roofish) > 4 else np.array([178, 98, 62.])
                col = (col * .82 + col.mean() * .18) * .93
                halls.append([round(float(c[0]), 1), round(float(c[1]), 1), round(float(u[0]), 4), round(float(u[1]), 4), round(float(hl), 1), round(float(hw), 1)] + [int(x) for x in col])
    out[str(Y)] = halls
sc['halls'] = out; json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
print('halls', {y: len(v) for y, v in out.items() if int(y) % 5 == 0 or int(y) in (35, 39, 44, 47)})
