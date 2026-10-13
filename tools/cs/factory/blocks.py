"""CS 线 · cs28 按街道、街区分区（取上游 tanxinhao 线 v23 的做法：先有街，街围出街区，一个街区整块是一种；所有者点名取用）
南港底账里的房子是满地撒的，只有主街没有巷子，所以这里先补巷子：
  1 主街（画上和底账都空着的宽街）把地切成大格；
  2 每个大格里顺着最近的主街方向开巷子：沿街每 84px 一条横巷，进深每 64px 一条顺巷，巷宽 6px —— 切出的小块就是街区；
  3 街区整块定性：街区里活着的房子按 districts.py 的判法投票，非民居的一种占到 40% 就整块算它，否则民居；
  4 码头货栈、仓场街区整块翻建：用空地底图抹平，顺着街区方向排长屋（进深 18px，长 ≤ 56px，屋间留巷）。
输出 scene.json：blocks（街区多边形）、zones（每户跟着街区）、zone_labels（同种相连的街区一处一个名）、halls、hall_blocks（翻建的街区）。"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely import affinity
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'; Q = os.path.join(ROOT, 'docs', 'living', q)
sc = json.load(open(os.path.join(Q, 'scene.json'))); city = json.load(open(os.path.join(Q, 'city.json'))); HD = json.load(open(os.path.join(Q, 'houses.json')))
W, H, S = 1820, 2048, 2; w, h = W // S, H // S
HS = [hh for hh in HD['houses'] if hh[3] > 1 and hh[3] > hh[2] + 1]
LATE = HD.get('late', {})
# ---- 1 主街大格 ----
m = Image.new('L', (w, h), 0); d = ImageDraw.Draw(m)
for i, dd, b, e, p in HS:
    if b <= 60 < e: d.polygon([(x / S, y / S) for x, y in zip(p[0::2], p[1::2])], fill=255)
lm = Image.new('L', (w, h), 0); dl = ImageDraw.Draw(lm)
for k, l in LATE.items():
    if k.startswith(('fire', 'arian')): continue
    dl.polygon([(x / S, y / S) for x, y in l['p']], fill=255)
WK = sc['fleet']['walk']; wat = np.array([c_ == 'w' for c_ in WK['quay']]).reshape(WK['H'], WK['W'])
wat = np.array(Image.fromarray(wat.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 0
house = (np.array(m) > 0) | (np.array(lm) > 0); land_lm = np.array(lm) > 0
free = ~house & ~wat; st = ndi.distance_transform_edt(free) >= 3; st = ndi.binary_dilation(st, iterations=3) & free
sl, sn = ndi.label(st); ss = ndi.sum(np.ones_like(sl), sl, range(1, sn + 1))
st = np.isin(sl, 1 + np.flatnonzero(ss >= 1500))   # 只留连成长街的空地；房子之间的小空当不算街
st = ndi.binary_opening(st, iterations=2)
cell, nc = ndi.label(ndi.binary_opening(~st & ~wat & ~land_lm, iterations=2))
R = [r['pts'] for r in city['roads']]
def road_dir(cx, cy):
    best = (1e9, (1., 0.))
    for P in R:
        for a, b in zip(P[:-1], P[1:]):
            ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
            t = max(0, min(1, ((cx - ax) * dx + (cy - ay) * dy) / L / L)); dd_ = math.hypot(cx - ax - t * dx, cy - ay - t * dy)
            if dd_ < best[0]: best = (dd_, (dx / L, dy / L))
    u = best[1]; return u if u[0] >= 0 else (-u[0], -u[1])
def runs_poly(mask):
    mask = ndi.binary_fill_holes(mask); rects = []
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any(): continue
        xs = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
        for a, b in zip(xs[0::2], xs[1::2]): rects.append(box(a * S, y * S, b * S, (y + 1) * S))
    return unary_union(rects).buffer(4).buffer(-8).buffer(4).simplify(3)
# 临港的大格顺着港岸开巷（货栈一排排对着码头），其余顺着最近的主街
DW = ndi.distance_transform_edt(~wat); GY, GX = np.gradient(DW)
def shore_dir(msk):
    sel = msk & (DW * S <= 80) & (DW > 0)
    if sel.sum() < 150: return None
    a2 = np.arctan2(GY[sel], GX[sel]) * 2; c2, s2 = np.cos(a2).mean(), np.sin(a2).mean()
    if math.hypot(c2, s2) < .45: return None
    n = math.atan2(s2, c2) / 2; u = (-math.sin(n), math.cos(n)); return u if u[0] >= 0 else (-u[0], -u[1])
# ---- 2 巷子切街区 ----
PU, PV, LANE = 84, 64, 6
blocks = []   # [poly, (ux,uy), centroid, area]
sizes = ndi.sum(np.ones_like(cell), cell, range(1, nc + 1))
for ci in range(1, nc + 1):
    if sizes[ci - 1] * S * S < 1500: continue
    cp = runs_poly(cell == ci)
    if cp.is_empty: continue
    cx, cy = cp.centroid.x, cp.centroid.y; u = shore_dir(cell == ci) or road_dir(cx, cy); ang = math.degrees(math.atan2(u[1], u[0]))
    # 在街区自己的坐标系里（u 沿街，v 进深）切格子
    rp = affinity.rotate(cp, -ang, origin=(cx, cy)); x0, y0, x1, y1 = rp.bounds
    for a in np.arange(x0 - PU / 2, x1 + PU, PU):
        for b in np.arange(y0, y1 + PV, PV):
            g = box(a + LANE / 2, b + LANE / 2, a + PU - LANE / 2, b + PV - LANE / 2).intersection(rp)
            for gg in (getattr(g, 'geoms', None) or [g]):
                if gg.geom_type != 'Polygon' or gg.area < 500: continue
                bp = affinity.rotate(gg, ang, origin=(cx, cy)).simplify(1.0)
                blocks.append([bp, u, (bp.centroid.x, bp.centroid.y), bp.area])
print('cells', nc, 'blocks', len(blocks))
# 每户落在哪个街区（不在任何街区里的落最近的）
from shapely.strtree import STRtree
from shapely.geometry import Point
polys = [b[0] for b in blocks]; tree = STRtree(polys)
hb = {}
for i, dd, b, e, p in HS:
    pt = Point(sum(p[0::2]) / 4, sum(p[1::2]) / 4); k = tree.nearest(pt); hb[i] = int(k)
# ---- 3 街区整块定性 ----
Zh = sc.get('zones') or {}
def zat(z, Y):
    c_ = 'homes'
    for y, k in z:
        if y <= Y: c_ = k
    return c_
from collections import Counter
members = {}
for i, k in hb.items(): members.setdefault(k, []).append(i)
LIFE = {hh[0]: (hh[2], hh[3]) for hh in HS}
bz = {}   # 年 -> 每块代号
for Y in range(0, 61):
    z = []
    for k in range(len(blocks)):
        al = [i for i in members.get(k, []) if LIFE[i][0] <= Y < LIFE[i][1]]
        if not al: z.append('homes'); continue
        c_ = Counter(zat(Zh.get(str(i), []), Y) for i in al); c_.pop('homes', None)
        top = c_.most_common(1); z.append(top[0][0] if top and top[0][1] >= 0.4 * len(al) else 'homes')
    bz[Y] = z
zones = {}
for i, k in hb.items():
    prev = None
    for Y in range(0, 61):
        if bz[Y][k] != prev: zones.setdefault(str(i), []).append([Y, bz[Y][k]]); prev = bz[Y][k]
# 同种相连的街区一处一个名
adj = {k: set() for k in range(len(blocks))}
for k, pk in enumerate(polys):
    for j in tree.query(pk.buffer(LANE + 2)):
        if j != k: adj[k].add(int(j))
labels = {}
for Y in range(0, 61):
    seen = set(); L = []
    RK = {'horrea': 0, 'water': 1, 'dock': 2, 'planned': 3, 'market': 4, 'shops': 5, 'homes': 9}
    for k in sorted(range(len(blocks)), key=lambda k: (RK[bz[Y][k]], -blocks[k][3])):   # 小而要紧的先写
        c_ = bz[Y][k]
        if c_ == 'homes' or k in seen or not members.get(k): continue
        grp = [k]; seen.add(k); st_ = [k]
        while st_:
            x = st_.pop()
            for j in adj[x]:
                if j not in seen and bz[Y][j] == c_: seen.add(j); grp.append(j); st_.append(j)
        A = sum(blocks[j][3] for j in grp)
        if A < (1800 if c_ in ('horrea', 'water') else 4500): continue   # 仓场、汲水坊本来就小，也要写名
        cx = sum(blocks[j][2][0] * blocks[j][3] for j in grp) / A; cy = sum(blocks[j][2][1] * blocks[j][3] for j in grp) / A
        if all(math.hypot(l[0] - cx, l[1] - cy) > (150 if l[2] == c_ else 100) for l in L): L.append([int(cx), int(cy), c_])
    labels[str(Y)] = L
# ---- 4 货栈街区翻建成长屋 ----
KA = {}
def key_img(Y):
    K = min([k for k in sc['keys'] if Y <= k[0]] or [sc['keys'][-1]], key=lambda k: k[0])
    if K[0] not in KA: KA[K[0]] = np.asarray(Image.open(os.path.join(Q, K[1])).convert('RGB').resize((W, H))).astype(float)
    return KA[K[0]]
def roof_col(A, x, y):
    x0, y0 = int(np.clip(x, 26, W - 27)), int(np.clip(y, 26, H - 27)); ring = A[y0 - 26:y0 + 26, x0 - 26:x0 + 26].reshape(-1, 3)
    r_ = ring[(ring[:, 0] > ring[:, 2] + 70) & (ring[:, 0] > ring[:, 1] + 40)]
    col = np.median(r_, 0) if len(r_) > 4 else np.array([178, 98, 62.]); return (col * .82 + col.mean() * .18) * .93
DEP, GAPV, LEN, GAPU = 18, 6, 56, 5
layout = {}
def lay(k):
    if k in layout: return layout[k]
    bp, u, (cx, cy), A = blocks[k]; ang = math.degrees(math.atan2(u[1], u[0])); rp = affinity.rotate(bp, -ang, origin=(cx, cy))
    out = []
    # 街区边上跟着房子走、不齐；长屋只要七成落在街区里、又不碰水和地标就排
    x0, y0, x1, y1 = rp.buffer(-1).bounds; nv = max(1, int((y1 - y0 + GAPV) // (DEP + GAPV))); oy = y0 + ((y1 - y0) - (nv * DEP + (nv - 1) * GAPV)) / 2
    ca_, sa_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    def ok(bx):
        if bx.intersection(rp).area < .7 * bx.area: return False
        for fx in (.1, .5, .9):
            for fy in (.15, .85):
                sx = bx.bounds[0] + (bx.bounds[2] - bx.bounds[0]) * fx; sy = bx.bounds[1] + (bx.bounds[3] - bx.bounds[1]) * fy
                wx = cx + (sx - cx) * ca_ - (sy - cy) * sa_; wy = cy + (sx - cx) * sa_ + (sy - cy) * ca_
                gx, gy = int(np.clip(wx / S, 0, w - 1)), int(np.clip(wy / S, 0, h - 1))
                if wat[gy, gx] or land_lm[gy, gx]: return False
        return True
    for r in range(nv):
        ya = oy + r * (DEP + GAPV); x = x0 + 1
        while x < x1 - 12:
            L = min(LEN, x1 - 1 - x)
            while L >= 14 and not ok(box(x, ya, x + L, ya + DEP)): L -= 4
            if L >= 14: out.append((x + L / 2, ya + DEP / 2, L / 2, DEP / 2)); x += L + GAPU
            else: x += 4
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    layout[k] = [(cx + (sx - cx) * ca - (sy - cy) * sa, cy + (sx - cx) * sa + (sy - cy) * ca, u[0], u[1], hl, hw) for sx, sy, hl, hw in out]
    return layout[k]
halls = {}; hblk = {}
for Y in range(0, 61):
    ks = [k for k in range(len(blocks)) if bz[Y][k] in ('dock', 'horrea') and any(LIFE[i][0] <= Y < LIFE[i][1] for i in members.get(k, []))]
    if not ks: continue
    A = key_img(Y); HL = []
    for k in ks:
        for x, y, ux, uy, hl, hw in lay(k): HL.append([round(x, 1), round(y, 1), round(ux, 4), round(uy, 4), round(hl, 1), round(hw, 1)] + [int(v) for v in roof_col(A, x, y)])
    halls[str(Y)] = HL; hblk[str(Y)] = ks
sc['blocks'] = [[round(v, 1) for xy in list(b[0].exterior.coords)[:-1] for v in xy] for b in blocks]
sc['zones'] = zones; sc['zone_labels'] = labels; sc['halls'] = halls; sc['hall_blocks'] = hblk
json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
for Y in (30, 40, 50, 60):
    print(Y, dict(Counter(z for z, k in zip(bz[Y], range(len(blocks))) if members.get(k))), 'labels', len(labels[str(Y)]), 'halls', len(halls.get(str(Y), [])))
if '--png' in sys.argv:
    im = Image.open(os.path.join(Q, 'ng_af60.jpg')).convert('RGB').resize((W, H)); ov = Image.new('RGBA', (W, H)); dv = ImageDraw.Draw(ov)
    CO = {'dock': (60, 90, 200), 'horrea': (40, 160, 200), 'water': (70, 140, 200), 'planned': (90, 150, 110), 'market': (214, 120, 40), 'shops': (226, 170, 60), 'homes': (200, 180, 140)}
    for k, b in enumerate(blocks): dv.polygon(list(b[0].exterior.coords), fill=CO[bz[60][k]] + (110,), outline=(60, 30, 10, 255))
    im.paste(ov, (0, 0), ov); im.resize((910, 1024)).save('/workspace/work/blocks60.jpg', quality=85)
if '--dbg' in sys.argv:
    ks = hblk['60'][:5]
    for k in ks:
        bp = blocks[k][0]; print(k, round(bp.area), [round(v) for v in bp.bounds], blocks[k][1], len(lay(k)))
