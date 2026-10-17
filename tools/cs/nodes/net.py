"""CS 线 · 路网节点（2026-10-17，主人：房子跟着路重排，更看重方法）
学 WorldGacha 的町节点（只学方法，不抄代码）：地形 → 可达代价 → 干道（最省力路径）→ 小街（张量场流线）→ 地块 → 入户。
底账不动：海岸、港池、地标、梅塞大道（canon）、每户的年份/用途都照底账；只有「路怎么走、户落在哪块地」是这里长出来的。
每一步有自己的种子（recipe.json seeds.net_*），改一个只重算它和下游；随机数按位置哈希。
输入 docs/living/nodes/<q>/nodes.json（build.py 的产物），输出同目录 nodes_net.json + net_report.json。
用法: python3 tools/cs/nodes/net.py nangang      页面: scroll.html?n=net
——Hark（CS线）"""
import json, math, os, sys, hashlib, heapq, collections, time
import numpy as np, cv2
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union, linemerge
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt, label
from skimage.graph import MCP_Geometric
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'cs', 'factory'))
import house_types as HT

def h32(*a): return int(hashlib.blake2b(repr(a).encode(), digest_size=4).hexdigest(), 16)
def hf(*a): return h32(*a) / 4294967296
G = 2   # 栅格：2 像素一格
T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, file=sys.stderr)

q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
O = os.path.join(ROOT, 'docs', 'living', 'nodes', q)
D = json.load(open(os.path.join(O, 'nodes.json'))); R = json.load(open(os.path.join(O, 'recipe.json')))
NUM = dict(dsep=56, dtest=22, step=2.0, max_slope=0.16, lot_f=(6.5, 10.5), lot_d=(10, 15), erosion_drops=30000)
NUM.update(R.get('net', {}))
seed = lambda name: R['seeds'].get('net_' + name, h32(R['seed'], 'net_' + name))
W, H = D['W'], D['H']; gw, gh = W // G + 1, H // G + 1
F = D['features']
def mp(g): return MultiPolygon([Polygon(P[0], P[1:]) for P in g]).buffer(0)
def raster(geom, val=1, thick=None):
    m = np.zeros((gh, gw), np.uint8)
    for p in (geom.geoms if hasattr(geom, 'geoms') else [geom]):
        if p.is_empty: continue
        if p.geom_type == 'Polygon':
            cv2.fillPoly(m, [np.int32(np.array(p.exterior.coords) / G)], val)
            for r in p.interiors: cv2.fillPoly(m, [np.int32(np.array(r.coords) / G)], 0)
        elif p.geom_type == 'LineString':
            cv2.polylines(m, [np.int32(np.array(p.coords) / G)], False, val, max(1, int(round((thick or 2) / G))))
    return m

# ① 地形：底账高程（SRTM）是设计图；在上面跑水滴侵蚀补出冲沟细节（WorldGacha 的侵蚀节点）；地标底下削平台
E = D['elev']; ez = np.array(E['dm'], float).reshape(E['h'], E['w']) / 10.0   # 米
yy, xx = np.mgrid[0:gh, 0:gw]
hgt = map_coordinates(ez, [yy * G / E['st'], xx * G / E['st']], order=3, mode='nearest')
land = mp([f['g'] for f in F if f['t'] == 'land'][0]) if False else unary_union([mp(f['g']) for f in F if f['t'] == 'land'])
basins = [(mp(f['g']), f['y0']) for f in F if f['t'] == 'water' and f.get('k') == 'harbor']
moles = unary_union([mp(f['g']) for f in F if f['t'] == 'mole'])
dry = land.difference(unary_union([b for b, _ in basins])).intersection(box(0, 0, W, H))
landM = raster(dry) > 0
def erode(h, n, sd):
    rng = np.random.default_rng(sd); h = h.copy(); mpp = D['elev']['mpp'] * G
    for _ in range(n):
        x, y = rng.uniform(1, gw - 2), rng.uniform(1, gh - 2); sed = 0.0; vel = 1.0; wat = 1.0; dx = dy = 0.0
        for _s in range(40):
            ix, iy = int(x), int(y)
            if not (1 <= ix < gw - 2 and 1 <= iy < gh - 2) or not landM[iy, ix]: break
            gx = (h[iy, ix + 1] - h[iy, ix - 1]) / 2; gy = (h[iy + 1, ix] - h[iy - 1, ix]) / 2
            dx = dx * 0.3 - gx * 0.7; dy = dy * 0.3 - gy * 0.7; L = math.hypot(dx, dy)
            if L < 1e-6: break
            dx /= L; dy /= L; nx, ny = x + dx, y + dy
            h0 = h[iy, ix]; h1 = h[int(ny), int(nx)]; dh = h1 - h0
            cap = max(-dh, 0.01) * vel * wat * 0.6
            if sed > cap or dh > 0:
                dep = min(sed, dh) if dh > 0 else (sed - cap) * 0.3
                h[iy, ix] += dep; sed -= dep
            else:
                er = min((cap - sed) * 0.3, -dh, 0.05); h[iy, ix] -= er; sed += er
            vel = math.sqrt(max(0.01, vel * vel + dh * -1.0)); wat *= 0.98; x, y = nx, ny
    return h
log('terrain')
hgt = erode(hgt, NUM['erosion_drops'], seed('terrain'))
hgt = gaussian_filter(hgt, 0.6)
LM = [f for f in F if f['t'] == 'landmark']
lmPoly = {f['id']: Polygon(f['g']).buffer(0) for f in LM}
for f in LM:   # 平台：地标底下取中位高程压平，边上 6 像素缓坡
    m = raster(lmPoly[f['id']].buffer(3)) > 0; lvl = np.median(hgt[m]) if m.any() else 0
    d = distance_transform_edt(~m) * G; wgt = np.clip(1 - d / 10, 0, 1)
    hgt = hgt * (1 - wgt) + lvl * wgt
mpp = D['elev']['mpp']
gyh, gxh = np.gradient(hgt, G * mpp)
slope = np.hypot(gxh, gyh)   # 米/米

# ② 可达代价：坡越陡越贵，水和地标不能走
lmAll = unary_union(list(lmPoly.values()))
block = (~landM) | (raster(lmAll.buffer(1)) > 0)
cost = 1 + 40 * slope ** 2
cost[block] = np.inf
# 底账的锚点：梅塞大道（canon，原样保留）、街区框边上和城市路网接上的口、地标的门、栈桥根
S0 = [f for f in F if f['t'] == 'street']
mese = [f for f in S0 if f['k'] == 'm']
meseL = linemerge([LineString([(f['g'][0], f['g'][1]), (f['g'][2], f['g'][3])]) for f in mese])
mese_lines = list(meseL.geoms) if hasattr(meseL, 'geoms') else [meseL]
ends = []
for f in S0:
    if f['k'] in ('c', 'm'):
        for x, y in ((f['g'][0], f['g'][1]), (f['g'][2], f['g'][3])):
            if min(x, y, W - x, H - y) < 40: ends.append((x, y))
gates = []
for x, y in ends:
    if all(math.hypot(x - a, y - b) > 120 for a, b in gates): gates.append((x, y))
def free_near(x, y, r=30):
    ix, iy = int(x / G), int(y / G); best = None
    for d in range(0, int(r / G)):
        for jy in range(iy - d, iy + d + 1):
            for jx in range(ix - d, ix + d + 1):
                if 0 <= jx < gw and 0 <= jy < gh and np.isfinite(cost[jy, jx]):
                    return (jx * G, jy * G)
    return best
anchors = []   # (x, y, kind, id, year)
for x, y in gates:
    p = free_near(x, y)
    if p: anchors.append((p[0], p[1], 'gate', 'g%d' % len(anchors), 0))
houses0 = [f for f in F if f['t'] == 'house']
hc0 = np.array([[sum(f['p'][0::2]) / 4, sum(f['p'][1::2]) / 4] for f in houses0])
for f in LM:   # 门开在朝人家最多的那一边
    P = lmPoly[f['id']]; c = P.centroid; near = hc0[np.hypot(hc0[:, 0] - c.x, hc0[:, 1] - c.y) < 260]
    tx, ty = (near.mean(0) if len(near) else (W / 2, H / 2))
    door = P.exterior.interpolate(P.exterior.project(Point(tx, ty)))
    dx, dy = door.x - c.x, door.y - c.y; L = math.hypot(dx, dy) or 1
    p = free_near(door.x + dx / L * 5, door.y + dy / L * 5)
    if p: anchors.append((p[0], p[1], 'lm', f['id'], f['y0']))
piers = [f for f in F if f['t'] == 'pier']
roots = []
for f in sorted(piers, key=lambda f: f['y0']):
    x, y = f['g'][0]
    if all(math.hypot(x - a, y - b) > 140 for a, b, _ in roots): roots.append((x, y, f['y0']))
for x, y, y0 in roots:
    p = free_near(x, y, 40)
    if p: anchors.append((p[0], p[1], 'pier', 'p%d' % len(anchors), y0))
log('anchors', collections.Counter(a[2] for a in anchors))

# ③ 干道：锚点之间走最省力的路（代价场上的最短路，WorldGacha 用 A*，这里用 MCP 一次算整片）；
# 先接最便宜的一对（最小生成树），路修好的格子变便宜，后面的路就会并上去；再补几条绕远太多的环路
meseM = np.zeros((gh, gw), np.uint8)
for l in mese_lines: meseM |= raster(l, 1, 6)
cost_t = cost.copy(); cost_t[meseM > 0] = 0.25
def route(c, a, b):
    m = MCP_Geometric(c, fully_connected=True)
    cum, _ = m.find_costs([(int(a[1] / G), int(a[0] / G))], [(int(b[1] / G), int(b[0] / G))])
    tb = m.traceback((int(b[1] / G), int(b[0] / G)))
    return cum[int(b[1] / G), int(b[0] / G)], [(x * G, y * G) for y, x in tb]
pts = [(a[0], a[1]) for a in anchors]
# 用欧氏距离近似挑 MST 边，再用真路径
pairs = sorted(((math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]), i, j) for i in range(len(pts)) for j in range(i + 1, len(pts))))
par = list(range(len(pts)))
def fd(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
trunks = []
for d_, i, j in pairs:
    if fd(i) == fd(j): continue
    cst, path = route(cost_t, pts[i], pts[j])
    if not np.isfinite(cst) or len(path) < 2: continue
    par[fd(i)] = fd(j)
    trunks.append((path, min(anchors[i][4], anchors[j][4]) if anchors[i][2] == 'gate' or anchors[j][2] == 'gate' else max(anchors[i][4], anchors[j][4]), (anchors[i][3], anchors[j][3])))
    for x, y in path: cost_t[int(y / G), int(x / G)] = min(cost_t[int(y / G), int(x / G)], 0.35)
log('trunks', len(trunks))
def smooth(path, tol=3.0, it=2):
    l = LineString(path).simplify(tol); c = list(l.coords)
    for _ in range(it):
        if len(c) < 3: break
        n = [c[0]]
        for a, b in zip(c[:-1], c[1:]): n += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        n.append(c[-1]); c = n
    return c
def wet_line(c):
    for a, b in zip(c[:-1], c[1:]):
        for t in np.linspace(0, 1, max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 2))):
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t; ix, iy = min(gw - 1, int(x / G)), min(gh - 1, int(y / G))
            if not landM[iy, ix]: return True
    return False
def safe_smooth(p, tol=3.0, it=2):   # 抹圆了下水，就退回不抹圆的
    for t_, i_ in ((tol, it), (1.5, 1), (0.8, 0)):
        c = smooth(p, t_, i_)
        if not wet_line(c): return c
    return p
trunk_lines = [(LineString(safe_smooth(p)), y, ids) for p, y, ids in trunks]

# ④ 小街：张量场流线。场 = 干道走向 + 海岸走向 + 等高线走向 + 一个基础格网方向，按 2θ 叠加（方向无正反）
log('tensor field')
cs = 8; tw, th_ = W // cs + 2, H // cs + 2
C2 = np.zeros((th_, tw)); S2 = np.zeros((th_, tw))
ty_, tx_ = np.mgrid[0:th_, 0:tw]; X = tx_ * cs; Y = ty_ * cs
def add_lines(lines, sigma, wmax):
    global C2, S2
    segs = []
    for l in lines:
        c = list(l.coords)
        for a, b in zip(c[:-1], c[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1: continue
            n = max(1, int(L / 10))
            for k in range(n): segs.append(((a[0] + (b[0] - a[0]) * (k + .5) / n), (a[1] + (b[1] - a[1]) * (k + .5) / n), math.atan2(b[1] - a[1], b[0] - a[0])))
    if not segs: return
    sg = np.array(segs); tr = cKDTree(sg[:, :2])
    dd, ii = tr.query(np.c_[X.ravel(), Y.ravel()], k=4)
    for k in range(4):
        th = sg[ii[:, k], 2]; w = wmax * np.exp(-(dd[:, k] / sigma) ** 2) / 4
        C2 += (w * np.cos(2 * th)).reshape(C2.shape); S2 += (w * np.sin(2 * th)).reshape(S2.shape)
add_lines(mese_lines + [l for l, _, _ in trunk_lines], 90, 1.0)
coast = dry.boundary
add_lines([g for g in (coast.geoms if hasattr(coast, 'geoms') else [coast]) if g.length > 30], 60, 0.8)
# 等高线方向 = 垂直坡度方向，坡越陡权越大（街顺着坡走，WorldGacha 一样）
gxs = map_coordinates(gxh, [Y / G, X / G], order=1, mode='nearest'); gys = map_coordinates(gyh, [Y / G, X / G], order=1, mode='nearest')
thc = np.arctan2(gys, gxs) + math.pi / 2; wc = np.clip(np.hypot(gxs, gys) / 0.08, 0, 1) * 0.5
C2 += wc * np.cos(2 * thc); S2 += wc * np.sin(2 * thc)
mth = math.atan2(sum(math.sin(2 * math.atan2(l.coords[-1][1] - l.coords[0][1], l.coords[-1][0] - l.coords[0][0])) * l.length for l in mese_lines),
                 sum(math.cos(2 * math.atan2(l.coords[-1][1] - l.coords[0][1], l.coords[-1][0] - l.coords[0][0])) * l.length for l in mese_lines)) / 2
C2 += 0.25 * math.cos(2 * mth); S2 += 0.25 * math.sin(2 * mth)
# 一点按位置的低频扰动：老城的街不是尺子画的
rn = np.random.default_rng(seed('field')); nz = gaussian_filter(rn.normal(size=C2.shape), 6); nz = nz / (np.abs(nz).max() or 1) * 0.35
th0 = np.arctan2(S2, C2) / 2 + nz; mag = np.hypot(C2, S2); C2 = mag * np.cos(2 * th0); S2 = mag * np.sin(2 * th0)
C2 = gaussian_filter(C2, 1.2); S2 = gaussian_filter(S2, 1.2)
TH = np.arctan2(S2, C2) / 2
def dirAt(x, y, fam):
    t = map_coordinates(C2, [[y / cs], [x / cs]], order=1, mode='nearest')[0], map_coordinates(S2, [[y / cs], [x / cs]], order=1, mode='nearest')[0]
    th = math.atan2(t[1], t[0]) / 2 + (math.pi / 2 if fam else 0)
    return math.cos(th), math.sin(th)

# 需求：底账人家多的地方才长街（街跟着人走，空地不修路）
dem = np.zeros((gh, gw)); np.add.at(dem, (np.clip((hc0[:, 1] / G).astype(int), 0, gh - 1), np.clip((hc0[:, 0] / G).astype(int), 0, gw - 1)), 1.0)
dem = gaussian_filter(dem, 14 / G) * (2 * math.pi * (14 / G) ** 2)   # ≈ 半径 14 像素内的户数
roadAny = np.zeros((gh, gw), np.uint8)
for l in mese_lines: roadAny |= raster(l, 1, 8)
for l, _, _ in trunk_lines: roadAny |= raster(l, 1, 6)
near_fam = [np.zeros((gh, gw), np.uint8), np.zeros((gh, gw), np.uint8)]   # 同一方向族已有街的「勿近」带
sep_fam = [np.zeros((gh, gw), np.uint8), np.zeros((gh, gw), np.uint8)]
def mark(l, fam):
    near_fam[fam] |= raster(l, 1, 2 * NUM['dtest']); sep_fam[fam] |= raster(l, 1, 2 * NUM['dsep'] - 4)
for l in mese_lines + [l for l, _, _ in trunk_lines]:
    for fam in (0, 1):
        # 干道两族都占：小街不贴着干道平行走
        a = math.atan2(l.coords[-1][1] - l.coords[0][1], l.coords[-1][0] - l.coords[0][0])
    for fam in (0, 1): sep_fam[fam] |= raster(l, 1, 2 * NUM['dsep'] - 4)   # 干道只占「间距」带，不占「勿近」带，小街才能从干道上长出去
def ok(x, y):
    ix, iy = int(x / G), int(y / G)
    return 0 <= ix < gw and 0 <= iy < gh and np.isfinite(cost[iy, ix]) and slope[iy, ix] < NUM['max_slope'] * 1.6
def trace(x, y, fam, sgn):
    pts = [(x, y)]; px, py = None, None; st = NUM['step']; joined = False
    for i in range(260):
        dx, dy = dirAt(x, y, fam)
        if px is not None and dx * px + dy * py < 0: dx, dy = -dx, -dy
        elif px is None: dx, dy = dx * sgn, dy * sgn
        nx, ny = x + dx * st, y + dy * st
        if not ok(nx, ny): break
        ix, iy = int(nx / G), int(ny / G)
        if i > 3 and roadAny[iy, ix]:   # 撞上别的街：接上，成一个路口
            pts.append((nx, ny)); joined = True; break
        if i > 3 and near_fam[fam][iy, ix]: break
        if dem[iy, ix] < 0.6: break   # 没人家了：街到头
        pts.append((nx, ny)); x, y, px, py = nx, ny, dx, dy
    return pts, joined
streets = []   # (LineString, fam)
rs = seed('streets')
seeds = collections.deque()
def push_seeds(l, fam_child):
    L = l.length; n = int(L // NUM['dsep'])
    for k in range(1, n + 1):
        t = (k - .5 + .4 * (hf(rs, round(l.coords[0][0]), round(l.coords[0][1]), k) - .5)) / max(n, 1)
        p = l.interpolate(t, normalized=True); seeds.append((p.x, p.y, fam_child))
for l in mese_lines + [l for l, _, _ in trunk_lines]:
    a = math.atan2(l.coords[-1][1] - l.coords[0][1], l.coords[-1][0] - l.coords[0][0])
    cx, cy = l.interpolate(.5, normalized=True).coords[0]; dx, dy = dirAt(cx, cy, 0)
    fam = 1 if abs(math.cos(a) * dx + math.sin(a) * dy) > .7 else 0   # 干道接近哪族，就从它长另一族
    push_seeds(l, fam)
log('streamlines from', len(seeds), 'seeds')
while seeds and len(streets) < 3000:
    x, y, fam = seeds.popleft()
    ix, iy = int(x / G), int(y / G)
    if not (0 <= ix < gw and 0 <= iy < gh) or sep_fam[fam][iy, ix] and not roadAny[iy, ix]: continue
    a, ja = trace(x, y, fam, 1); b, jb = trace(x, y, fam, -1)
    if len(a) < 8 and not ja: a = a[:1]   # 越过母街的小尾巴剪掉：它会挡住母街另一侧的门面
    if len(b) < 8 and not jb: b = b[:1]
    p = b[::-1] + a[1:]
    if len(p) < 2: continue
    for end, jn in ((0, jb), (-1, ja)):   # 没接上的头：16 像素内找最近的街接过去（不留断头缝）
        if jn: continue
        ex_, ey_ = p[end]; ix, iy = int(ex_ / G), int(ey_ / G); r = 8
        y0_, y1_, x0_, x1_ = max(0, iy - r), min(gh, iy + r + 1), max(0, ix - r), min(gw, ix + r + 1)
        win = roadAny[y0_:y1_, x0_:x1_]
        if win.any():
            ys, xs = np.nonzero(win); k = np.argmin((ys + y0_ - iy) ** 2 + (xs + x0_ - ix) ** 2)
            q_ = ((xs[k] + x0_) * G + 1, (ys[k] + y0_) * G + 1)
            if not wet_line([p[end], q_]):
                if end == 0: p.insert(0, q_); jb = True
                else: p.append(q_); ja = True
    if not (ja or jb): continue   # 两头都不挨别的街：孤街不要
    l = LineString(p)
    if l.length < 22: continue
    l = LineString(smooth(list(l.coords), 1.2, 1))
    streets.append((l, fam)); mark(l, fam); roadAny |= raster(l, 1, 4)
    push_seeds(l, 1 - fam)
log('streets', len(streets))

# ⑤ 地块：沿街两边按门面宽、进深切地；干道先切（铺面先占临街），地块不压街、不压地标、不下水
roadW = np.zeros((gh, gw), np.uint8)
for l in mese_lines: roadW |= raster(l, 1, 15)
for l, _, _ in trunk_lines: roadW |= raster(l, 1, 8)
for l, _ in streets: roadW |= raster(l, 1, 5)
occ = roadW.copy() | block.astype(np.uint8)
rl = seed('lots'); lots = []; seq = {}
def cut(l, sid, kind, half):
    L = l.length; s = 0.0
    for side in (1, -1):
        s = 2.0
        while s < L - 4:
            fw_ = NUM['lot_f'][0] + (NUM['lot_f'][1] - NUM['lot_f'][0]) * hf(rl, sid, side, round(s))
            dp = NUM['lot_d'][0] + (NUM['lot_d'][1] - NUM['lot_d'][0]) * hf(rl, sid, side, round(s), 'd')
            a = l.interpolate(s); b = l.interpolate(min(L, s + fw_))
            ux, uy = b.x - a.x, b.y - a.y; ul = math.hypot(ux, uy) or 1; ux /= ul; uy /= ul
            nx, ny = -uy * side, ux * side; off = half + G + 0.6   # 至少隔一格：栅格取整时不咬到街
            P = [(a.x + nx * off, a.y + ny * off), (b.x + nx * off, b.y + ny * off), (b.x + nx * (off + dp), b.y + ny * (off + dp)), (a.x + nx * (off + dp), a.y + ny * (off + dp))]
            A_ = np.array(P) / G; bx0, by0 = np.floor(A_.min(0)).astype(int) - 1; bx1, by1 = np.ceil(A_.max(0)).astype(int) + 2
            if bx0 < 0 or by0 < 0 or bx1 >= gw or by1 >= gh: s += 2.0; continue
            m = np.zeros((by1 - by0, bx1 - bx0), np.uint8); cv2.fillPoly(m, [np.int32(A_ - [bx0, by0])], 1)
            cells = m > 0; sub = occ[by0:by1, bx0:bx1]
            if cells.sum() > 4 and not (sub[cells] > 0).any():
                sub[cells] = 1
                if side == -1: P = [P[1], P[0], P[3], P[2]]   # 统一：P0→P1 是临街边
                lots.append({'p': P, 'sid': sid, 'kind': kind, 'busy': [], 'key': (sid, side, len([1 for l_ in lots if False]))})
                seq[(sid, side)] = seq.get((sid, side), -1) + 1; lots[-1]['key'] = (sid, side, seq[(sid, side)])
                s += fw_ + 0.3
            else: s += 1.0
for i, l in enumerate(mese_lines): cut(l, 'm%d' % i, 'main', 7.5)
if os.environ.get('DBG'):
    import pickle; pickle.dump((occ, roadW, block), open('/tmp/occ.pkl', 'wb'))
for i, (l, _, _) in enumerate(trunk_lines): cut(l, 't%d' % i, 'trunk', 4)
for i, (l, _) in enumerate(streets): cut(l, 's%d' % i, 'street', 2.5)
log('lots', len(lots), collections.Counter(l['kind'] for l in lots))

# ⑥ 入户：底账每户（年份、用途、高度）按年份先后挑离原来位置最近的空地块；铺面、市场优先临干道。
# 同一块地上，一户拆了，后来的人家可以接着盖（年份不重叠）——城的年轮从地块上长出来。
bykey = {l['key']: i for i, l in enumerate(lots)}
def nb_busy(j, a, b):
    s_, sd, k = lots[j]['key']
    return sum(1 for kk in (k - 1, k + 1) if (s_, sd, kk) in bykey and not free(lots[bykey[(s_, sd, kk)]], a, b))
lc = np.array([[sum(x for x, _ in l['p']) / 4, sum(y for _, y in l['p']) / 4] for l in lots]); tr = cKDTree(lc)
order = sorted(range(len(houses0)), key=lambda i: (houses0[i]['y0'], houses0[i]['id']))
placed = {}; unplaced = []
def free(lot, a, b):
    return all(b <= x or a >= y for x, y in lot['busy'])
for i in order:
    f = houses0[i]; a = f['y0']; b = f['y1'] if f['y1'] is not None else 9999
    dd, ii = tr.query(hc0[i], k=min(80, len(lots)), distance_upper_bound=240)
    best = None
    for d_, j in zip(dd, ii):
        if not np.isfinite(d_): break
        lot = lots[j]
        if not free(lot, a, b): continue
        pen = 0.6 * d_ + (0 if lot['kind'] != 'street' or f['fn'] not in ('shops', 'market') else 40) - {'main': 45, 'trunk': 25}.get(lot['kind'], 0) - 30 * nb_busy(j, a, b)   # 临街先填满：干道、挨着人家的地块优先   # 挨着已有人家的地块更好：连成排
        if best is None or pen < best[0]: best = (pen, j)
    if best is None: unplaced.append(f['id']); continue
    lots[best[1]]['busy'].append((a, b)); placed[f['id']] = best[1]
log('placed', len(placed), 'unplaced', len(unplaced))
newH = []
for f in houses0:
    if f['id'] not in placed: continue
    lot = lots[placed[f['id']]]; P = lot['p']
    area = math.hypot(P[1][0] - P[0][0], P[1][1] - P[0][1]) * math.hypot(P[3][0] - P[0][0], P[3][1] - P[0][1])
    fn = f['fn']; fnp = 'homes' if fn in ('dock', 'horrea', 'water') else fn
    ty = HT.pick_type(fn if fn in ('dock', 'horrea') else fnp, 0, area, lot['kind'] != 'street', f['id']) if fn != 'planned' or f['y0'] >= 48 else 'casa'
    ht = HT.type_height(ty, fnp, 0) if ty in HT.TYPE_H else f['ht']
    po = 1 if ty == 'row' and (fn == 'market' or hf(f['id'], 81) < .55) and lot['kind'] != 'street' else 0
    newH.append({'t': 'house', 'id': f['id'], 'y0': f['y0'], 'y1': f['y1'], 'p': [round(c, 1) for xy in P for c in xy], 'fn': fn, 'ht': ht, 'ty': ty, 'fr': 0, 'po': po, 'sid': lot['sid']})

# 街的年份：第一户临街那年前一年修出来；干道按两头锚点；梅塞是 canon（0 年）。没人临街的小街不修。
first = collections.defaultdict(lambda: 9999)
for h in newH: first[h['sid']] = min(first[h['sid']], h['y0'])
outS = []
def segs(l, k, w, y0):
    c = list(l.coords)
    for a, b in zip(c[:-1], c[1:]): outS.append({'t': 'street', 'k': k, 'g': [round(a[0], 1), round(a[1], 1), round(b[0], 1), round(b[1], 1)], 'w': w, 'y0': y0, 'y1': None})
for f in mese: outS.append(f)
for i, (l, y, ids) in enumerate(trunk_lines): segs(l, 'c', 7, min(y, first['t%d' % i] - 1) if first['t%d' % i] < 9999 else y)
built_streets = 0
for i, (l, fam) in enumerate(streets):
    if first['s%d' % i] >= 9999: continue
    built_streets += 1; segs(l, 's' if l.length > 120 else 'l', 5 if l.length > 120 else 4, first['s%d' % i] - 1)

# ⑦ 验收（机器能判的都判）
log('checks')
rep = {}
wet = 0; steep = []; allS = [(s['g'], s['w']) for s in outS]
for g, w in allS:
    for t in (0, .5, 1):
        x = g[0] + (g[2] - g[0]) * t; y = g[1] + (g[3] - g[1]) * t; ix, iy = min(gw - 1, max(0, int(x / G))), min(gh - 1, max(0, int(y / G)))
        if not landM[iy, ix] and not (moles.contains(Point(x, y))): wet += 1
        steep.append(slope[iy, ix])
rep['street_points_on_water'] = wet
rep['street_slope_p95'] = round(float(np.percentile(steep, 95)), 3)
rep['houses_ledger'] = len(houses0); rep['houses_placed'] = len(newH); rep['houses_unplaced'] = len(unplaced)
net = unary_union([LineString([(g[0], g[1]), (g[2], g[3])]).buffer(max(1.5, w / 2)) for g, w in allS])   # 街面按宽度算
comps = list(net.geoms) if hasattr(net, 'geoms') else [net]; big = max(comps, key=lambda c: c.area)
rep['street_components'] = len(comps); rep['main_component_share'] = round(big.area / net.area, 3)
rep['landmarks_reached'] = sum(1 for a in anchors if a[2] == 'lm' and big.distance(Point(a[0], a[1])) < 10); rep['landmarks'] = sum(1 for a in anchors if a[2] == 'lm')
rep['gates_reached'] = sum(1 for a in anchors if a[2] == 'gate' and big.distance(Point(a[0], a[1])) < 10); rep['gates'] = sum(1 for a in anchors if a[2] == 'gate')
dmax = []
for h in newH:
    P = h['p']; fx, fy = (P[0] + P[2]) / 2, (P[1] + P[3]) / 2; dmax.append(net.distance(Point(fx, fy)))
rep['house_front_to_street_max'] = round(max(dmax), 1)
moved = [math.hypot(sum(h['p'][0::2]) / 4 - hc0[i][0], sum(h['p'][1::2]) / 4 - hc0[i][1]) for i, h0 in enumerate(houses0) for h in [None] if False]
idx = {f['id']: i for i, f in enumerate(houses0)}
mv = [math.hypot(sum(h['p'][0::2]) / 4 - hc0[idx[h['id']]][0], sum(h['p'][1::2]) / 4 - hc0[idx[h['id']]][1]) for h in newH]
rep['house_move_median_px'] = round(float(np.median(mv)), 1); rep['house_move_p95_px'] = round(float(np.percentile(mv, 95)), 1)
rep['trunks'] = len(trunk_lines); rep['streets_built'] = built_streets; rep['lots'] = len(lots)
rep['lots_reused_over_years'] = sum(1 for l in lots if len(l['busy']) > 1)
rep['pass'] = wet == 0 and rep['main_component_share'] > .95 and rep['landmarks_reached'] == rep['landmarks'] and rep['houses_unplaced'] <= 0.02 * len(houses0) and rep['house_front_to_street_max'] < 8
print(json.dumps(rep, ensure_ascii=False, indent=1))

# 输出：同一层中间数据，渲染器不用改
hs = cKDTree(np.array([[sum(h['p'][0::2]) / 4, sum(h['p'][1::2]) / 4] for h in newH])); hy = np.array([h['y0'] for h in newH])
trees = []
for t in D['trees']:
    x, y = t[0], t[1]; ix, iy = int(x / G), int(y / G)
    if not (0 <= ix < gw and 0 <= iy < gh) or roadW[iy, ix] or occ[iy, ix] and hs.query((x, y))[0] < 9: continue
    near = hs.query_ball_point((x, y), 12)
    trees.append([x, y, t[2], t[3], int(min(hy[near])) if near else None, t[5]])
keep = [f for f in F if f['t'] not in ('street', 'house')]
ez2 = map_coordinates(hgt, [np.arange(E['h'])[:, None] * E['st'] / G * np.ones((1, E['w'])), np.arange(E['w'])[None, :] * E['st'] / G * np.ones((E['h'], 1))], order=1, mode='nearest')
out = dict(D); out['features'] = keep + outS + newH; out['trees'] = trees
out['elev'] = dict(E, dm=[int(round(v * 10)) for v in ez2.ravel()])
out['net'] = {'report': rep, 'anchors': [[round(a[0]), round(a[1]), a[2], a[3]] for a in anchors]}
json.dump(out, open(os.path.join(O, 'nodes_net.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(rep, open(os.path.join(O, 'net_report.json'), 'w'), ensure_ascii=False, indent=1)
log('wrote', os.path.getsize(os.path.join(O, 'nodes_net.json')))
