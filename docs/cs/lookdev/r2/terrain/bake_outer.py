#!/usr/bin/env python3
"""南港 3D · terrain 区外烘焙（lookdev 第 2 轮，CS 线，2026-10-20）

把「南港框外」的真实地理烘成一个小 JS 模块，3d/terrain.js 运行时直接 import（页面不能读仓库根的 data/）：
  1. 区外陆地：data/land.geojson（OSM 海岸，和 tools/cs/nodes/build.py 同一来源，同样开运算去掉现代填海细条）
     + data/elev_grid20.json（SRTM，engine/terrain.elevation 同一函数）→ 一张粗网格（LOD：近 64 像素、远 192 像素一格）的
     顶点高度（和 core ground() 同一公式：海底 -6 → 陆地 elevPx，岸按覆盖率平滑），外加简化海岸线（地面贴图画陆地/沙岸用）。
  2. 城市肌理：docs/living/nodes/city/nodes.json 全城底账房屋 → 24 像素格的覆盖率 + 半数房屋建成的年份
     （地面贴图在城里画成「远看的屋顶色斑」，年份跟着 ctx.year 走；不建任何房子）。
  3. 远岸剖面：远平面（core 的 far=9000 像素≈7.6 km）之外的真实地物——王子群岛、亚洲岸（卡德柯伊—马尔泰佩—卡尔塔尔—图兹拉）、
     马尔马拉南岸萨曼勒山/阿尔穆特卢半岛、乌卢达山、欧洲岸西段——按方位每 0.5° 存（最近岸距、最高有效高度及其距离），
     有效高度扣掉地球曲率（k=7/6 折光）。点位和高度是按公开地理常识手填的近似值（±50 m、±1 km 量级），只求轮廓方位对。
用法（仓库根）：PYTHONPATH=<含 shapely/numpy/PIL 的目录> python3 docs/cs/lookdev/r2/terrain/bake_outer.py
输出：docs/living/nodes/nangang/3d/terrain/outer_data.js
"""
import base64, json, math, os, sys, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import shape, box, Polygon
from shapely import affinity

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from terrain import elevation, LON0, LAT0, KX, KY  # noqa: E402

FR = json.load(open(os.path.join(ROOT, 'docs/living/nangang/frame.json')))
X0, Y0, FW, FH = FR['frame']; S = FR['scale']
W, H = round(FW * S), round(FH * S)            # 1820 × 2048
EX, MPP = 1.3, 12 / S                            # 和 core.js 一致
toP = lambda u, v: ((u - X0) * S, (v - Y0) * S)
OUT = os.path.join(ROOT, 'docs/living/nodes/nangang/3d/terrain/outer_data.js')

# ---------- 1. 区外陆地 ----------
L = shape(json.load(open(os.path.join(ROOT, 'data/land.geojson'))))
P = affinity.affine_transform(L, [S, 0, 0, S, -X0 * S, -Y0 * S]).buffer(0)
AR = 22   # 同 recipe ancient_r：去掉宽不到 44 像素的现代填海细条
P = P.buffer(-AR, join_style=1).buffer(AR, join_style=1).buffer(0)
BX = (-6400, -6000, 10800, 5600)                 # 全城图范围（页面像素）
P = P.intersection(box(*BX)).buffer(0)

# 覆盖率栅格（16 像素一格），糊一下，用来定顶点高度（同 core：c→smoothstep→-6..陆地）
RS = 16
rw, rh = int((BX[2] - BX[0]) / RS), int((BX[3] - BX[1]) / RS)
im = Image.new('L', (rw, rh), 0); dr = ImageDraw.Draw(im)
for g in (P.geoms if hasattr(P, 'geoms') else [P]):
    dr.polygon([((x - BX[0]) / RS, (z - BX[1]) / RS) for x, z in g.exterior.coords], fill=255)
    for r in g.interiors:
        dr.polygon([((x - BX[0]) / RS, (z - BX[1]) / RS) for x, z in r.coords], fill=0)
cov = np.asarray(im.filter(ImageFilter.GaussianBlur(1.6)), dtype=np.float32) / 255


def cover(x, z):
    fx = min(max((x - BX[0]) / RS - .5, 0), rw - 1.001); fz = min(max((z - BX[1]) / RS - .5, 0), rh - 1.001)
    i, j = int(fx), int(fz); a, b = fx - i, fz - j
    return (cov[j, i] * (1 - a) + cov[j, i + 1] * a) * (1 - b) + (cov[j + 1, i] * (1 - a) + cov[j + 1, i + 1] * a) * b


def elev_px(x, z):
    return elevation(X0 + x / S, Y0 + z / S) / MPP * EX


def ground(x, z):
    c = cover(x, z); t = min(1, max(0, (c - .3) / .4)); s = t * t * (3 - 2 * t)
    return -6 + (elev_px(x, z) + 7.5) * s


def lines(a, b, forced, near_lo, near_hi, fine=64, coarse=192):
    """网格线：near 区间里 fine 一格，外面 coarse 一格，强制线（框边）一定在。"""
    v = set(forced); x = a
    while x <= b:
        v.add(x); x += fine if near_lo <= x < near_hi else coarse
    v.add(b)
    v = sorted(v); out = []
    for t in v:
        if t in forced or not out or (t - out[-1] >= 24 and not any(abs(t - f) < 24 and t != f for f in forced)):
            out.append(t)
    return out


xs = lines(BX[0], BX[2], {0, W}, -2600, W + 3400)
zs = lines(BX[1], BX[3], {0, H}, -2600, H + 2200)
nx, nz = len(xs), len(zs)
hgt = np.zeros((nz, nx), np.float32); keep = np.zeros((nz, nx), np.uint8)
for j, z in enumerate(zs):
    for i, x in enumerate(xs):
        hgt[j, i] = ground(x, z)
# 框内的格子不建（区内网格归原来的 4 像素网格）；海里远离岸的格子也不建（海面平面盖住）
cell = np.zeros((nz - 1, nx - 1), np.uint8)
for j in range(nz - 1):
    for i in range(nx - 1):
        x0, x1, z0, z1 = xs[i], xs[i + 1], zs[j], zs[j + 1]
        if x0 >= 0 and x1 <= W and z0 >= 0 and z1 <= H: continue
        if max(hgt[j, i], hgt[j, i + 1], hgt[j + 1, i], hgt[j + 1, i + 1]) > -5.5: cell[j, i] = 1
# 海岸线（地面贴图用）：简化到 6 像素
Ps = P.simplify(6)
rings = []
for g in (Ps.geoms if hasattr(Ps, 'geoms') else [Ps]):
    if g.area < 3000: continue
    rings.append([[round(x), round(z)] for x, z in g.exterior.coords])
    for r in g.interiors:
        if Polygon(r).area > 3000: rings.append([[round(x), round(z)] for x, z in r.coords])

# ---------- 2. 城市肌理（全城底账房屋 → 覆盖率格） ----------
CF = json.load(open(os.path.join(ROOT, 'docs/living/city/frame.json')))
CX0, CY0 = CF['frame'][0], CF['frame'][1]
OX, OZ = (X0 - CX0) * S, (Y0 - CY0) * S          # 城市页面像素 → 南港页面像素：减去它
CD = json.load(open(os.path.join(ROOT, 'docs/living/nodes/city/nodes.json')))
US = 24
ub = (-800, -3400, 4400, 2400)
uw, uh = (ub[2] - ub[0]) // US, (ub[3] - ub[1]) // US
area = np.zeros((uh, uw), np.float32); yrs = [[[] for _ in range(uw)] for _ in range(uh)]
for f in CD['features']:
    if f['t'] != 'house': continue
    p = f['p']; pts = [(p[k] - OX, p[k + 1] - OZ) for k in range(0, len(p), 2)]
    cx = sum(q[0] for q in pts) / len(pts); cz = sum(q[1] for q in pts) / len(pts)
    if 0 <= cx <= W and 0 <= cz <= H: continue     # 南港自己的房子由 buildings 建
    i, j = int((cx - ub[0]) // US), int((cz - ub[1]) // US)
    if not (0 <= i < uw and 0 <= j < uh): continue
    a = abs(Polygon(pts).area); area[j, i] += a
    yrs[j][i].append((f['y0'], f.get('y1'), a))
cov_u = np.clip(area / (US * US), 0, 1)
u_c = np.zeros((uh, uw), np.uint8); u_y = np.zeros((uh, uw), np.uint8)
for j in range(uh):
    for i in range(uw):
        if not yrs[j][i]: continue
        hs = sorted(yrs[j][i], key=lambda q: q[0]); tot = sum(a for _, _, a in hs); acc = 0
        for y0, y1, a in hs:
            acc += a
            if acc >= tot / 2: break
        u_c[j, i] = int(round(cov_u[j, i] * 255)); u_y[j, i] = int(min(250, max(0, y0 + 100)))   # 年份 +100 存（-100 以前 = 0）

# ---------- 3. 远岸剖面 ----------
LAT_C, LON_C = LAT0 - (Y0 + FH / 2) / KY, LON0 + (X0 + FW / 2) / KX      # 南港框中心
R_E, KR = 6371000.0, 7 / 6
mx = math.cos(math.radians(LAT_C)) * 111320; my = 110574


def local(lat, lon):     # 米：x 东，z 南（同页面）
    return (lon - LON_C) * mx, (LAT_C - lat) * my


# 岛：中心、半径 km、最高 m；岸线：折线 (lat, lon, h) 点距 0.3 km 加密，每点画成半径 r km 的小丘
ISLANDS = [  # 王子群岛
    (40.910, 29.050, .75, 115, 'Kinaliada'), (40.881, 29.066, .85, 165, 'Burgazada'), (40.877, 29.093, 1.2, 136, 'Heybeliada'),
    (40.858, 29.120, 1.7, 202, 'Buyukada'), (40.852, 29.143, .4, 50, 'Sedef'), (40.887, 28.995, .25, 40, 'Yassiada'), (40.875, 28.970, .3, 60, 'Sivriada')]
RIDGES = {
    'near': [  # 亚洲岸，从海达尔帕夏往东南到盖布泽；欧洲岸西段；北面色雷斯台地（多半被近处地形挡住）
        [(41.000, 29.020, 40), (40.983, 29.026, 45), (40.968, 29.040, 25), (40.975, 29.065, 70), (40.958, 29.100, 60), (40.940, 29.130, 110),
         (40.950, 29.260, 537), (40.905, 29.190, 90), (40.880, 29.250, 130), (40.835, 29.300, 120), (40.800, 29.430, 330), (40.780, 29.600, 400)],
        [(41.027, 29.070, 268), (41.000, 29.060, 120)],
        [(40.975, 28.870, 30), (40.957, 28.820, 35), (40.980, 28.750, 60), (41.010, 28.640, 70), (41.020, 28.580, 90)],
        [(41.090, 28.700, 120), (41.090, 28.850, 130), (41.085, 29.000, 140), (41.080, 29.040, 120)]],
    'far': [  # 马尔马拉南岸：赫尔塞克岬—亚洛瓦—萨曼勒山—阿尔穆特卢半岛；乌卢达山
        [(40.540, 28.740, 250), (40.525, 28.850, 600), (40.560, 29.000, 750), (40.600, 29.100, 800), (40.580, 29.300, 950), (40.570, 29.500, 1150),
         (40.600, 29.700, 1300), (40.620, 29.900, 1500)],
        [(40.650, 29.270, 150), (40.720, 29.520, 60)],
        [(40.100, 28.950, 1500), (40.070, 29.220, 2543), (40.050, 29.450, 1800), (40.100, 29.700, 1200)]]}


def samples():
    for lat, lon, rkm, h, _ in ISLANDS:
        n = max(6, int(rkm * 10))
        for a in range(n):
            for b in range(n):
                u, v = (a + .5) / n * 2 - 1, (b + .5) / n * 2 - 1; rr = math.hypot(u, v)
                if rr > 1: continue
                yield 'near', lat + v * rkm / 111.0, lon + u * rkm / (111.0 * math.cos(math.radians(lat))), h * max(.05, 1 - rr ** 1.6)
    for layer, rl in RIDGES.items():
        for line in rl:
            for (a1, o1, h1), (a2, o2, h2) in zip(line, line[1:]):
                d = math.hypot((a2 - a1) * 111, (o2 - o1) * 84); n = max(2, int(d / .3))
                for k in range(n + 1):
                    t = k / n; lat, lon, h = a1 + (a2 - a1) * t, o1 + (o2 - o1) * t, h1 + (h2 - h1) * t
                    for dk in (-1.5, -.75, 0, .75):   # 往岸里/岸外散一点：给剖面厚度
                        yield layer, lat + dk / 111 * .5, lon + dk / 84 * .5, h * (1 - abs(dk) * .25)


NA = 720
prof = {k: {'d0': [0] * NA, 'H': [0] * NA, 'dH': [0] * NA} for k in ('near', 'far')}
for layer, lat, lon, h in samples():
    x, z = local(lat, lon); d = math.hypot(x, z)
    if d < 6000: continue
    az = math.degrees(math.atan2(x, z)) % 360          # 0 = 正南，90 = 正东（页面 x 向东、z 向南）
    k = int(az * 2) % NA
    he = h - d * d / (2 * KR * R_E)
    pr = prof[layer]
    if pr['d0'][k] == 0 or d < pr['d0'][k]: pr['d0'][k] = d
    if pr['dH'][k] == 0 or he / d > pr['H'][k] / pr['dH'][k]: pr['H'][k], pr['dH'][k] = he, d
for layer in prof:   # 填 0.5° 的小缝
    pr = prof[layer]
    for k in range(NA):
        if pr['d0'][k] == 0:
            a, b = pr['d0'][k - 1], pr['d0'][(k + 1) % NA]
            if a and b:
                for key in ('d0', 'H', 'dH'):
                    pr[key][k] = (pr[key][k - 1] + pr[key][(k + 1) % NA]) / 2


def b64(a):
    return base64.b64encode(zlib.compress(a.tobytes(), 9)).decode()


data = dict(
    note='bake_outer.py 生成，勿手改。坐标 = 南港页面像素；高度 = 像素（同 core ground()）。',
    W=W, H=H, xs=xs, zs=zs,
    hgt=b64(np.round(hgt * 8).astype(np.int16)), cell=b64(cell),
    rings=rings,
    urban=dict(box=list(ub), cs=US, w=uw, h=uh, c=b64(u_c), y=b64(u_y)),
    prof={k: {kk: [round(v) for v in vv] for kk, vv in pr.items()} for k, pr in prof.items()},
    mpp=MPP, src='data/land.geojson (OSM) + data/elev_grid20.json (SRTM) + docs/living/nodes/city/nodes.json + 手填远岸点位')
js = '/* 南港 terrain 区外烘焙数据：docs/cs/lookdev/r2/terrain/bake_outer.py 生成，勿手改。 */\nexport default ' + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';\n'
open(OUT, 'w', encoding='utf-8').write(js)
print('grid', nx, 'x', nz, 'cells', int(cell.sum()), 'rings', len(rings), sum(len(r) for r in rings), 'pts', 'urban', uw, uh, int((u_c > 0).sum()),
      'bytes', len(js))
for layer in prof:
    pr = prof[layer]; on = [k / 2 for k in range(NA) if pr['d0'][k]]
    print(layer, 'az covered', len(on) / 2, 'deg; e.g. az', on[:3], '...', on[-3:])
