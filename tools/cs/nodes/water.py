"""CS 线 · 水系节点（2026-10-18）：水道桥 → 露天蓄水池 → 街角喷泉，高处人家用井。
接在 net.py 后面跑：读 nodes_net.json（已经有路、房、后院、侵蚀后的高程），把水系写回同一个文件，另出 water_report.json。
规则（每条同时是一条验收）：
  1 水只靠重力走：渠底高程沿水道桥只降不升，坡度取古罗马常用的千分之二左右；
  2 水道桥从街区里地势最高的陆地边进来（城外的水源在山上），挑高处走、绕开人家、可以跨街；
     渠底比地面高出来的那段是拱廊（桥墩落在地上），比地面低的那段埋在地下（看不见）；
  3 蓄水池大小跟人口走（每人约 2.5 立方米，水深约 10 米，参照君士坦丁堡露天池总量/人口），
     放在一块从来没人住过的空地上，池面低于渠到这里的高程；
  4 喷泉放在街边，管子埋地下不画（「脉」只露出效果）；每户 120 像素（约 100 米）内要有取水点；
     喷泉只能放在比池面低 2 米以上的地方，高过池面的人家只能打井；
  5 年份：人口过 6000 那年开始修水道桥，同年蓄水池；喷泉在它管的第一户人家来的那年出现，但不早于水道桥；井按第一户。
种子：recipe.json seeds.net_water（只影响同分时的取舍）。
——Hark（CS线）"""
import json, math, os, sys, time, hashlib
import numpy as np, cv2
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union
from scipy.ndimage import map_coordinates, distance_transform_edt
from scipy.spatial import cKDTree
from skimage.graph import MCP_Geometric
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, file=sys.stderr)
def hf(*a): return int(hashlib.blake2b(repr(a).encode(), digest_size=4).hexdigest(), 16) / 4294967296
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
O = os.path.join(ROOT, 'docs', 'living', 'nodes', q)
P_ = os.path.join(O, 'nodes_net.json'); D = json.load(open(P_))
NUM = dict(grad=0.002, m3_per_person=2.5, depth=10.0, people_per_house=6, start_pop=6000, reach=120, fountain_drop=2.0, arcade_min=1.5)
G = 2; W, H = D['W'], D['H']; gw, gh = W // G + 1, H // G + 1
E = D['elev']; mpp = E['mpp']
ez = np.array(E['dm'], float).reshape(E['h'], E['w']) / 10.0
yy, xx = np.mgrid[0:gh, 0:gw]
hgt = map_coordinates(ez, [yy * G / E['st'], xx * G / E['st']], order=1, mode='nearest')
F = [f for f in D['features'] if f['t'] not in ('aqueduct', 'cistern', 'fountain')]
def mp(g): return MultiPolygon([Polygon(P[0], P[1:]) for P in g]).buffer(0)
def fill(m, pts, v=1): cv2.fillPoly(m, [np.int32(np.array(pts) / G)], v)
land = unary_union([mp(f['g']) for f in F if f['t'] == 'land'])
water = unary_union([mp(f['g']) for f in F if f['t'] == 'water'])
dry = np.zeros((gh, gw), np.uint8)
for p in (land.geoms if hasattr(land, 'geoms') else [land]): fill(dry, p.exterior.coords)
wm = np.zeros((gh, gw), np.uint8)
for p in (water.geoms if hasattr(water, 'geoms') else [water]): fill(wm, p.exterior.coords)
dry = (dry > 0) & (wm == 0)
houses = [f for f in F if f['t'] == 'house']
def house_poly(h, yard=True):
    p = h['p']; P = [(p[0], p[1]), (p[2], p[3]), (p[4], p[5]), (p[6], p[7])]; d = h.get('yd', 0) if yard else 0
    if d:
        bx, by = P[3][0] - P[0][0], P[3][1] - P[0][1]; L = math.hypot(bx, by) or 1; bx /= L; by /= L
        P = [P[0], P[1], (P[2][0] + bx * d, P[2][1] + by * d), (P[3][0] + bx * d, P[3][1] + by * d)]
    return P
hmask = np.zeros((gh, gw), np.uint8)
for h in houses: fill(hmask, house_poly(h))
road = np.zeros((gh, gw), np.uint8)
for s in F:
    if s['t'] == 'street': g = s['g']; cv2.line(road, (int(g[0] / G), int(g[1] / G)), (int(g[2] / G), int(g[3] / G)), 1, max(1, int(round((s['w'] + 2) / G))))
other = np.zeros((gh, gw), np.uint8)
for f in F:
    if f['t'] == 'landmark': fill(other, f['g'])
    if f['t'] == 'pier':
        a, b = f['g']; cv2.line(other, (int(a[0] / G), int(a[1] / G)), (int(b[0] / G), int(b[1] / G)), 1, max(1, int(f['w'] / G) + 2))
free = dry & (hmask == 0) & (road == 0) & (other == 0)
free[:10] = free[-10:] = free[:, :10] = free[:, -10:] = False   # 池子不贴街区框（框外是别的街区）
rep = {}

# 人口曲线
years = range(0, 71)
alive = {Y: sum(1 for h in houses if h['y0'] <= Y and (h['y1'] is None or h['y1'] > Y)) for Y in years}
popY = {Y: alive[Y] * NUM['people_per_house'] for Y in years}
Yaq = next((Y for Y in years if popY[Y] >= NUM['start_pop']), 70)
peak = max(popY.values())
log('aqueduct year', Yaq, 'peak pop', peak)

# ① 入口：陆地边上最高的那格（框边 4 格内）
edge = np.zeros((gh, gw), bool); edge[:4] = edge[-4:] = edge[:, :4] = edge[:, -4:] = True
cand = edge & dry & (hmask == 0)
ei = np.argmax(np.where(cand, hgt, -1e9)); ey, ex = divmod(ei, gw); zin = hgt[ey, ex] + 4.0   # 进城时渠底离地约 4 米
log('entry', ex * G, ey * G, 'ground', round(float(hgt[ey, ex]), 1))

# ② 蓄水池：面积按峰值人口；在空地里找内切够大的、尽量高的点（高 = 能往下供更多喷泉），还要低于渠到那里的高程
A_m2 = peak * NUM['m3_per_person'] / NUM['depth']; A_px = A_m2 / mpp / mpp
dt = distance_transform_edt(free) * G   # 像素
dist_in = np.hypot(xx * G - ex * G, yy * G - ey * G) * mpp
zchan = zin - NUM['grad'] * dist_in * 1.3   # 路要绕，按直线 1.3 倍估
def rect(cxp, cyp, a, L, Wd):
    ca, sa = math.cos(a), math.sin(a); return [(cxp + ca * u - sa * v, cyp + sa * u + ca * v) for u, v in ((-L / 2, -Wd / 2), (L / 2, -Wd / 2), (L / 2, Wd / 2), (-L / 2, Wd / 2))]
def fits(Pts, fr):
    m = np.zeros((gh, gw), np.uint8); fill(m, Pts); c = m > 0
    return c.any() and fr[c].all()
def fit_at(cx, cy, fr, dtv, Aleft):
    bestR = None
    for k in range(12):
        a = math.pi * k / 12
        for Wd in range(int(min(dtv * 2, math.sqrt(Aleft))), 12, -4):
            L = min(Aleft / Wd, Wd * 2.5); Rr = rect(cx * G, cy * G, a, L, Wd)
            if fits(Rr, fr):
                if not bestR or L * Wd > bestR[0]: bestR = (L * Wd, Rr, a)
                break
    return bestR
# 一个池子装不下就再挖一个（最多 3 个）：每个候选点按「能挖多大」和「池面以下能管多少户」打分
hz = map_coordinates(hgt, [[sum(h['p'][1::2]) / 4 / G for h in houses], [sum(h['p'][0::2]) / 4 / G for h in houses]], order=1)
pools = []; fr = free.copy(); Aleft = A_px
from scipy.ndimage import maximum_filter
while Aleft > 400 and len(pools) < 3:
    dt = distance_transform_edt(fr) * G
    pk = (dt >= 14) & (dt == maximum_filter(dt, 9)) & (hgt + 1.0 < zchan)
    ys, xs = np.nonzero(pk)
    if not len(ys): break
    order = np.argsort(-hgt[ys, xs])[:60]
    best = None
    for o in order:
        cy, cx = ys[o], xs[o]; R_ = fit_at(cx, cy, fr, dt[cy, cx], Aleft)
        if not R_: continue
        served = float((hz < hgt[cy, cx] - 0.5 - NUM['fountain_drop']).mean())
        sc = min(1, R_[0] / Aleft) + served
        if not best or sc > best[0]: best = (sc, cx, cy, R_)
    if not best: break
    _, cx, cy, (area, cis, ang) = best
    pools.append({'g': cis, 'area': area, 'lvl': float(hgt[cy, cx]) - 0.5, 'c': (cx, cy)})
    m = np.zeros((gh, gw), np.uint8); fill(m, Polygon(cis).buffer(10).exterior.coords); fr &= m == 0
    Aleft -= area
rep['cistern_area_m2'] = round(sum(p['area'] for p in pools) * mpp * mpp); rep['cistern_target_m2'] = round(A_m2); rep['cisterns'] = len(pools)
log('pools', [(round(p['area'] * mpp * mpp), round(p['lvl'], 1)) for p in pools])

# ③ 水道桥：从入口到第一个池；再从已有渠线分支到其余池。代价 = 低处贵（要搭高拱）+ 人家极贵 + 街可以跨
rise = np.clip(zchan - hgt, 0, None)
cost = 1 + 0.15 * rise + 3000 * (hmask > 0) + 3000 * (other > 0) + 1e4 * (~dry)
cost[road > 0] = np.minimum(cost[road > 0], 2 + 0.15 * rise[road > 0])
for p in pools: m = np.zeros((gh, gw), np.uint8); fill(m, p['g']); cost[m > 0] = 5e3
chan = [((ey, ex), zin)]   # 已有渠的格子和渠底高程
aq = []
for p in pools:
    cx, cy = p['c']
    mcp = MCP_Geometric(cost, fully_connected=True); mcp.find_costs([c for c, _ in chan], [(cy, cx)])
    path = mcp.traceback((cy, cx)); start = path[0]; z0 = dict(chan)[tuple(start)] if tuple(start) in dict(chan) else zin
    raw = LineString([(c * G, r * G) for r, c in path])
    for tol in (6, 4, 2, 1, 0):   # 抹直，但抹直后不能切进人家
        ls = raw.simplify(tol) if tol else raw
        m = np.zeros((gh, gw), np.uint8); cv2.polylines(m, [np.int32(np.array(ls.coords) / G)], False, 1, 1)
        if (hmask[m > 0] > 0).sum() <= (hmask[[r for r, c in path], [c for r, c in path]] > 0).sum(): break
    cut = ls.difference(Polygon(p['g']).buffer(1))
    if cut.geom_type != 'LineString': cut = max(cut.geoms, key=lambda g: g.length) if not cut.is_empty else ls
    co = list(cut.coords)
    if math.hypot(co[0][0] - start[1] * G, co[0][1] - start[0] * G) > math.hypot(co[-1][0] - start[1] * G, co[-1][1] - start[0] * G): co = co[::-1]
    # 渠底：能埋就埋（地面下 1 米），只在洼地搭拱；只降不升，降得最慢也是 grad；还得留够高度流到池边
    dens = []
    for (xa, ya), (xb, yb) in zip(co[:-1], co[1:]):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / 2))
        for k in range(n): t = k / n; dens.append((xa + (xb - xa) * t, ya + (yb - ya) * t))
    dens.append(co[-1]); dens = np.array(dens)
    ds = np.r_[0, np.hypot(*np.diff(dens, axis=0).T)] * mpp; sc_ = np.cumsum(ds)
    gz = map_coordinates(hgt, [dens[:, 1] / G, dens[:, 0] / G], order=1)
    target = min(p['lvl'] + 0.3, z0 - NUM['grad'] * sc_[-1])
    zreq = target + NUM['grad'] * (sc_[-1] - sc_)
    z = np.zeros(len(dens)); z[0] = z0
    for i in range(1, len(dens)): z[i] = min(z[i - 1] - NUM['grad'] * ds[i], max(gz[i] - 1.0, zreq[i]))
    p['lvl'] = min(p['lvl'], z[-1] - 0.3)
    prof = [[round(float(x), 1), round(float(y), 1), round(float(zz), 2), round(float(g), 2)] for (x, y), zz, g in zip(dens[::2], z[::2], gz[::2])]
    if prof[-1][:2] != [round(float(dens[-1][0]), 1), round(float(dens[-1][1]), 1)]: prof.append([round(float(dens[-1][0]), 1), round(float(dens[-1][1]), 1), round(float(z[-1]), 2), round(float(gz[-1]), 2)])
    aq.append(prof)
    for x, y, z, _ in prof: chan.append(((int(y / G), int(x / G)), z))
    # 分支可以从渠线上任意一点出：把整条线都加进去
    for (x0, y0, z0_, _), (x1, y1, z1, _) in zip(prof[:-1], prof[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / G))
        for k in range(n): t = k / n; chan.append(((int((y0 + (y1 - y0) * t) / G), int((x0 + (x1 - x0) * t) / G)), z0_ + (z1 - z0_) * t))
lvl = max(p['lvl'] for p in pools)
rep['aqueduct_len_m'] = round(sum(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pr[:-1], pr[1:])) for pr in aq) * mpp)
arc = samp = 0
for prof in aq:
    for (x0, y0, z0, g0), (x1, y1, z1, g1) in zip(prof[:-1], prof[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 4))
        for k in range(n):
            t = k / n; x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t; gz = float(map_coordinates(hgt, [[y / G], [x / G]], order=1)[0])
            samp += 1; arc += (z0 + (z1 - z0) * t - gz) > NUM['arcade_min']
rep['aqueduct_arcade_share'] = round(arc / max(1, samp), 2)

# ④ 喷泉和井：街上的点做候选，贪心覆盖；喷泉只能在比池面低 fountain_drop 的地方
cands = []
for f in F:
    if f['t'] != 'street': continue
    g = f['g']; L = math.hypot(g[2] - g[0], g[3] - g[1]); n = max(1, int(L / 20))
    for k in range(n + 1):
        t = k / n; x, y = g[0] + (g[2] - g[0]) * t, g[1] + (g[3] - g[1]) * t
        nx, ny = -(g[3] - g[1]) / (L or 1), (g[2] - g[0]) / (L or 1); side = 1 if hf(round(x), round(y)) < .5 else -1
        px, py = x + nx * side * (f['w'] / 2 + 0.8), y + ny * side * (f['w'] / 2 + 0.8)   # 立在街边，不挡路
        ix, iy = int(px / G), int(py / G)
        if 0 <= ix < gw and 0 <= iy < gh and dry[iy, ix] and not hmask[iy, ix] and not other[iy, ix]:
            cands.append((px, py, float(hgt[iy, ix]), f['y0'] or 0))
cands = np.array(cands); log('candidates', len(cands))
hc = np.array([[sum(h['p'][0::2]) / 4, sum(h['p'][1::2]) / 4] for h in houses]); hy0 = np.array([h['y0'] for h in houses])
ct = cKDTree(cands[:, :2]); unserved = set(range(len(houses))); out_f = []
nearH = ct.query_ball_point(hc, NUM['reach'])
cover = [[] for _ in range(len(cands))]
for i, lst in enumerate(nearH):
    for j in lst: cover[j].append(i)
can_f = cands[:, 2] < lvl - NUM['fountain_drop']
for kind in ('fountain', 'well'):
    while True:
        bestj, bestn = -1, 0
        for j in range(len(cands)):
            if kind == 'fountain' and not can_f[j]: continue
            n = sum(1 for i in cover[j] if i in unserved and (kind == 'well' or True))
            if n > bestn or (n == bestn and n and hf(j) > .5): bestj, bestn = j, n
        if bestn == 0: break
        got = [i for i in cover[bestj] if i in unserved]
        if kind == 'fountain':   # 喷泉只管水道桥修好之后还在的人家；之前的人家靠井（下面补）
            got = [i for i in got if houses[i]['y1'] is None or houses[i]['y1'] > Yaq]
            if not got: can_f[bestj] = False; continue
        y0 = int(min(hy0[got])); y0 = max(y0, Yaq) if kind == 'fountain' else y0
        x, y = cands[bestj, :2]
        out_f.append({'t': 'fountain', 'k': kind, 'x': round(float(x), 1), 'y': round(float(y), 1), 'z': round(float(cands[bestj, 2]), 2), 'y0': y0, 'y1': None, 'n': len(got)})
        unserved -= set(got)
        if kind == 'fountain': can_f[bestj] = False
    if kind == 'fountain':   # 水道桥之前就有的人家，在喷泉来之前得有井：再算一遍，只看水道桥之前那些年
        unserved |= {i for i in range(len(houses)) if hy0[i] < Yaq}
rep['fountains'] = sum(1 for f in out_f if f['k'] == 'fountain'); rep['wells'] = sum(1 for f in out_f if f['k'] == 'well')

# ⑤ 验收
chk = {}
chk['gravity_monotone'] = all(b[2] <= a[2] for pr in aq for a, b in zip(pr[:-1], pr[1:]))
chk['channel_above_pool'] = all(pr[-1][2] >= p['lvl'] for pr, p in zip(aq, pools))
chk['fountains_below_pool'] = all(f['z'] < lvl - NUM['fountain_drop'] + 1e-6 for f in out_f if f['k'] == 'fountain')
cm = np.zeros((gh, gw), np.uint8)
for p in pools: fill(cm, p['g'])
chk['cistern_on_free_land'] = bool(free[cm > 0].all())
pier_bad = 0
for prof in aq:
    for (x0, y0, z0, g0), (x1, y1, z1, g1) in zip(prof[:-1], prof[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 4))
        for k in range(n):
            t = k / n; ix, iy = int((x0 + (x1 - x0) * t) / G), int((y0 + (y1 - y0) * t) / G)
            pier_bad += bool(hmask[iy, ix])
chk['aqueduct_cells_on_houses'] = pier_bad
wp = np.array([[f['x'], f['y']] for f in out_f]); wy = np.array([f['y0'] for f in out_f]); wt = cKDTree(wp)
far = 0
for i, h in enumerate(houses):
    near = wt.query_ball_point(hc[i], NUM['reach'] + 1)
    if not any(wy[j] <= max(h['y0'], wy[j] if False else h['y0']) for j in near): far += 1
chk['houses_without_water_point'] = far
rep['checks'] = chk
rep['pass'] = chk['gravity_monotone'] and chk['channel_above_pool'] and chk['fountains_below_pool'] and chk['cistern_on_free_land'] and pier_bad <= 2 and far <= 0.01 * len(houses)
rep.update(aqueduct_year=Yaq, peak_pop=peak, pool_level_m=round(lvl, 2), entry=[int(ex * G), int(ey * G)]); rep['checks'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in chk.items()}; rep['pass'] = bool(rep['pass'])
print(json.dumps(rep, ensure_ascii=False, indent=1))
feats = F + [{'t': 'aqueduct', 'g': pr, 'y0': Yaq, 'y1': None} for pr in aq] + \
    [{'t': 'cistern', 'g': [[round(x, 1), round(y, 1)] for x, y in p['g']], 'lvl': round(p['lvl'], 2), 'open': True, 'y0': Yaq, 'y1': None} for p in pools] + out_f
D['features'] = feats; D['water'] = rep
# 池子底下削成平台（池子是挖在一块平地里的，不能半边悬在坡上）：池边 4 像素内取中位高程，往外 14 像素缓到原地面
st = E['st']; ey_, ex_ = np.mgrid[0:E['h'], 0:E['w']]
for p in pools:
    poly = Polygon(p['g']); inner = poly.buffer(8)
    d = np.array([[inner.distance(Point(x * st, y * st)) for x in range(E['w'])] for y in range(E['h'])]) if False else None
    m = np.zeros((E['h'], E['w']), np.uint8); cv2.fillPoly(m, [np.int32(np.array(inner.exterior.coords) / st)], 1)
    if not m.any(): continue
    lv = float(np.median(ez[m > 0])); dd = distance_transform_edt(m == 0) * st; wgt = np.clip(1 - dd / 28, 0, 1)
    ez = ez * (1 - wgt) + lv * wgt
pp = [Polygon(p['g']).buffer(3) for p in pools]
D['trees'] = [t for t in D['trees'] if not any(P.contains(Point(t[0], t[1])) for P in pp)]   # 池子里不长树
D['elev'] = dict(E, dm=[int(round(v * 10)) for v in ez.ravel()])
json.dump(D, open(P_, 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(rep, open(os.path.join(O, 'water_report.json'), 'w'), ensure_ascii=False, indent=1)
log('wrote')
