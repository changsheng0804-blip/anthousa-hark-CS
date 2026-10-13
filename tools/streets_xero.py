#!/usr/bin/env python3
"""Xerolophos re-layout: streets first -> lots along streets -> houses assigned to lots.
Keeps every house id + built/destroyed years; moves each house to the nearest street lot
(same special zone). Writes houses.json, streets.json, and helper data. Seeded, repeatable."""
import json, math, random, sys
import numpy as np
from PIL import Image, ImageDraw

X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
SRC = X + 'houses_v12.json'   # original ledger layout (kept)
random.seed(7)
W, H = 1820, 2048
D = json.load(open(SRC))
houses = D['houses']; late = D['late']
city = json.load(open(X + 'city.json'))
LM = {l['id']: l for l in city['landmarks']}

def wall_x(y): return 587 - 0.2357 * y
def interior(x, y, m=30): return x > wall_x(y) + m and -5 < x < W + 5 and -5 < y < H + 5

def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c

ZONES = {k: v['p'] for k, v in late.items() if k != 'arian_meeting'}
def zone_of(x, y):
    for k, p in ZONES.items():
        if pip(x, y, p): return k
    return None

# no-build zones (static landmarks, aqueduct)
NB = [(LM[k]['xy'], r) for k, r in [('baths_constantius', 62), ('barracks_gate', 70), ('gate_founder', 55), ('aqb_valley', 40)] if k in LM]
AQ = [(760, 0), (1820, 515)]
def seg_d(px, py, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
def nobuild(x, y):
    if any(math.hypot(x - c[0], y - c[1]) < r for c, r in NB): return True
    if seg_d(x, y, *AQ) < 16: return True
    return False

# ---------------- settlement age: old quarters wind, new quarters are straight ----------------
AG = 40; agrid = {}
for h in houses:
    pp = h[4]; hx = sum(pp[0::2]) / 4; hy = sum(pp[1::2]) / 4
    agrid.setdefault((int(hx // AG), int(hy // AG)), []).append(h[2])
def age(x, y):
    ys = []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1): ys += agrid.get((int(x // AG) + i, int(y // AG) + j), [])
    if len(ys) < 4: return 45
    ys.sort(); return ys[len(ys) // 5]
def old(x, y):
    if pip(x, y, ZONES['fire_ruins']): return 0.0   # burnt ground re-laid as a planned grid after 48
    return max(0.0, min(1.0, (38 - age(x, y)) / 28))
# ---------------- streets ----------------
streets = []  # dict(w, kind, pts)
for r in city['roads']:
    streets.append(dict(w=15, kind='main', pts=[list(map(float, p)) for p in r['pts']]))
d = np.array([-0.2357, 1.0]); d /= np.linalg.norm(d); n = np.array([d[1], -d[0]])
if n[0] < 0: n = -n
corners = [(0, 0), (W, 0), (0, H), (W, H)]
us = [np.dot(c, n) for c in corners]; vs = [np.dot(c, d) for c in corners]
umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
def P(u, v): return (n * u + d * v).tolist()
# long streets (parallel to the wall), alternating street / lane
longs = []
u = umin + 40; i = 0
while u < umax:
    w = 8 if i % 2 == 0 else 5
    ph = random.random() * 6.28; amp = random.uniform(3, 9)
    ph2, ph3 = random.random() * 6.28, random.random() * 6.28
    pts = []
    for v in np.arange(vmin, vmax + 1, 15):
        bx, by = P(u + amp * math.sin(v / 210 + ph), v); o = old(bx, by)
        pts.append(P(u + amp * math.sin(v / 210 + ph) * (1 - 0.8 * (o == 0)) + o * (14 * math.sin(v / 60 + ph2) + 7 * math.sin(v / 23 + ph3)), v))
    longs.append((u, w, pts, ph, amp)); u += random.uniform(64, 82); i += 1
def ulong(L, v): u, w, pts, ph, amp = L; return u + amp * math.sin(v / 210 + ph)
# break long lanes randomly (dead ends) - lanes only
for (u0, w, pts, ph, amp) in longs:
    if w == 8:
        streets.append(dict(w=w, kind='street', pts=pts))
    else:
        cur = []
        for p in pts:
            if random.random() < 0.025 + 0.09 * old(*p) and len(cur) > 6:
                streets.append(dict(w=w, kind='lane', pts=cur)); cur = []
                continue
            cur.append(p)
        if len(cur) > 1: streets.append(dict(w=w, kind='lane', pts=cur))
# cross streets: pieces between consecutive long streets
v = vmin + 60
while v < vmax:
    tilt = random.uniform(-0.12, 0.12)
    for a, b in zip(longs[:-1], longs[1:]):
        if random.random() < 0.72:
            vv = v + tilt * a[0]
            ua, ub = ulong(a, vv), ulong(b, vv + tilt * (b[0] - a[0]))
            A_, B_ = P(ua, vv), P(ub, vv + tilt * (b[0] - a[0]))
            o = old((A_[0] + B_[0]) / 2, (A_[1] + B_[1]) / 2)
            if o < 0.15:   # planned: square to the long streets
                vm = vv + tilt * (b[0] - a[0]) / 2; A_, B_ = P(ua, vm), P(ub, vm)
                streets.append(dict(w=7, kind='cross', pts=[A_, B_]))
            else:          # old: kinked alley, plus stray short alleys
                km = random.uniform(-22, 22) * o
                M_ = P((ua + ub) / 2 + random.uniform(-8, 8) * o, vv + tilt * (b[0] - a[0]) / 2 + km)
                streets.append(dict(w=6 - 2 * o, kind='cross', pts=[A_, M_, B_]))
                if random.random() < 0.8 * o:
                    v2 = vv + random.uniform(40, 100); u2 = ua + random.uniform(10, 25)
                    streets.append(dict(w=4, kind='lane', pts=[P(ulong(a, v2), v2), P(u2 + random.uniform(15, 30), v2 + random.uniform(-25, 25)), P(u2 + random.uniform(30, 45), v2 + random.uniform(-30, 30))]))
    v += random.uniform(130, 175)

# clip streets to interior
def clip(st):
    out = []; cur = []
    for p in st['pts']:
        if interior(p[0], p[1], 12) and not any(math.hypot(p[0] - c[0], p[1] - c[1]) < r - 15 for c, r in NB[:2]):
            cur.append(p)
        else:
            if len(cur) > 1: out.append(dict(st, pts=cur))
            cur = []
    if len(cur) > 1: out.append(dict(st, pts=cur))
    return out
S2 = []
for s in streets:
    if s['kind'] == 'main':
        S2.append(s)  # main roads run through the gate
    else:
        S2 += clip(s)
streets = S2

# ---- audit fix E: two roads never run side by side a few steps apart; the lesser one gives way
RANK = {'main': 0, 'street': 1, 'cross': 2, 'lane': 3}
def resample(pts, step=6):
    out = [list(pts[0])]
    for a, b in zip(pts[:-1], pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(L // step))
        for j in range(1, n + 1): out.append([a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n])
    return out
def _sd0(px, py, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
SG0 = {}
for si, s_ in enumerate(streets):
    for a, b in zip(s_['pts'][:-1], s_['pts'][1:]):
        for gx in range(int(min(a[0], b[0]) // 40) - 1, int(max(a[0], b[0]) // 40) + 2):
            for gy in range(int(min(a[1], b[1]) // 40) - 1, int(max(a[1], b[1]) // 40) + 2):
                SG0.setdefault((gx, gy), []).append((si, a, b))
S3 = []; trimmed = 0
for si, s_ in enumerate(streets):
    if s_['kind'] == 'main': S3.append(s_); continue
    R_ = resample(s_['pts']); keep = []
    for k_, p_ in enumerate(R_):
        q0 = R_[max(0, k_ - 1)]; q1 = R_[min(len(R_) - 1, k_ + 1)]
        ang = math.atan2(q1[1] - q0[1], q1[0] - q0[0])
        bad = False
        for sj, a, b in SG0.get((int(p_[0] // 40), int(p_[1] // 40)), []):
            if sj == si: continue
            o = streets[sj]
            if (RANK[o['kind']], sj) > (RANK[s_['kind']], si): continue  # only a greater road pushes this one aside
            d_ = _sd0(p_[0], p_[1], a, b)
            if d_ < (o['w'] + s_['w']) / 2 + 9:
                a2 = math.atan2(b[1] - a[1], b[0] - a[0]); da = abs((ang - a2 + math.pi / 2) % math.pi - math.pi / 2)
                if da < 0.45: bad = True; break
        keep.append(not bad)
    if all(keep): S3.append(s_); continue
    trimmed += 1; cur = []
    for k_, p_ in enumerate(R_):
        if keep[k_]: cur.append(p_)
        else:
            if len(cur) > 1 and math.hypot(cur[-1][0] - cur[0][0], cur[-1][1] - cur[0][1]) > 24: S3.append(dict(s_, pts=cur))
            cur = []
    if len(cur) > 1 and math.hypot(cur[-1][0] - cur[0][0], cur[-1][1] - cur[0][1]) > 24: S3.append(dict(s_, pts=cur))
streets = S3
print('parallel-trimmed streets', trimmed, file=sys.stderr)
# ---- audit fix A: a lane end that stops just short of another street is joined to it
def _sd(px, py, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy), (ax + t * dx, ay + t * dy)
SG = {}
for si, s in enumerate(streets):
    for a, b in zip(s['pts'][:-1], s['pts'][1:]):
        for gx in range(int(min(a[0], b[0]) // 40) - 1, int(max(a[0], b[0]) // 40) + 2):
            for gy in range(int(min(a[1], b[1]) // 40) - 1, int(max(a[1], b[1]) // 40) + 2):
                SG.setdefault((gx, gy), []).append((si, a, b))
snapped = 0
for si, s in enumerate(streets):
    if s['kind'] == 'main': continue
    for end in (0, -1):
        ex, ey = s['pts'][end]
        best = None
        for sj, a, b in SG.get((int(ex // 40), int(ey // 40)), []):
            if sj == si: continue
            dd, q = _sd(ex, ey, a, b)
            if best is None or dd < best[0]: best = (dd, q)
        if best and 0.5 < best[0] < 22 and not nobuild(*best[1]):
            if end == 0: s['pts'].insert(0, list(best[1]))
            else: s['pts'].append(list(best[1]))
            snapped += 1
print('snapped lane ends', snapped, file=sys.stderr)
# road raster for collision
road = Image.new('L', (W, H), 0); rd = ImageDraw.Draw(road)
for s in streets:
    rd.line([tuple(p) for p in s['pts']], fill=255, width=int(s['w'] + 3), joint='curve')
road = np.asarray(road) > 0
lotmap = np.zeros((H, W), bool)
# ---- districts (街区): the ground the full street network encloses, each with a character that decides how its lots are cut
sys.path.insert(0, '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/gen')
import cv2
from scipy import ndimage
import district_rules as DR
SCD = 0.5; wd_, hd_ = int(W * SCD), int(H * SCD)
dm = np.zeros((hd_, wd_), np.uint8); mainm = np.zeros_like(dm)
_ys = np.arange(hd_)[:, None] / SCD; _xs = np.arange(wd_)[None, :] / SCD
dm[_xs < wall_x(_ys) + 6] = 1
cv2.line(dm, (int(DR.AQ[0][0] * SCD), int(DR.AQ[0][1] * SCD)), (int(DR.AQ[1][0] * SCD), int(DR.AQ[1][1] * SCD)), 1, 6)
_bx, _by = LM['baths_constantius']['xy']; cv2.circle(dm, (int(_bx * SCD), int(_by * SCD)), int(46 * SCD), 1, -1)
for _z in DR.CIST.values(): cv2.fillPoly(dm, [np.int32([[q[0] * SCD, q[1] * SCD] for q in _z['p']])], 1)
for s in streets:
    _p = np.int32([[q[0] * SCD, q[1] * SCD] for q in s['pts']])
    cv2.polylines(dm, [_p], False, 1, max(1, int(round(s['w'] * SCD))))
    if s['kind'] == 'main': cv2.polylines(mainm, [_p], False, 1, max(1, int(round(s['w'] * SCD)) + 2))
DLAB, _nd = ndimage.label(dm == 0)
_cnt = {}
for h in houses:
    _cx = sum(h[4][0::2]) / 4; _cy = sum(h[4][1::2]) / 4
    if 0 <= _cx < W and 0 <= _cy < H: _L = DLAB[int(_cy * SCD), int(_cx * SCD)]; _cnt[_L] = _cnt.get(_L, 0) + 1
DFN = {0: 'homes'}
_objs = ndimage.find_objects(DLAB)
for _L in range(1, _nd + 1):
    _sl = _objs[_L - 1]
    _y0, _y1 = max(0, _sl[0].start - 3), min(hd_, _sl[0].stop + 3); _x0, _x1 = max(0, _sl[1].start - 3), min(wd_, _sl[1].stop + 3)
    _c = DLAB[_y0:_y1, _x0:_x1] == _L
    _area = _c.sum() / SCD / SCD
    if _area > 70000: DFN[_L] = 'homes'; continue
    _yy, _xx = np.nonzero(_c)
    _ring = cv2.dilate(_c.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~_c
    _front = (_ring & mainm[_y0:_y1, _x0:_x1].astype(bool)).sum() / max(1, _ring.sum())
    DFN[_L] = DR.classify((_xx.mean() + _x0) / SCD, (_yy.mean() + _y0) / SCD, _area, _front, _cnt.get(_L, 0) / _area)
def district(x, y):
    if not (0 <= x < W and 0 <= y < H): return 'homes'
    return DFN.get(int(DLAB[int(y * SCD), int(x * SCD)]), 'homes')
from collections import Counter as _C
print('districts', _nd, _C(DFN.values()).most_common(), file=sys.stderr)

def rect(cx, cy, ux, uy, a, b):  # center, unit along-street, half sizes
    vx, vy = -uy, ux
    return [(cx + ux * a + vx * b, cy + uy * a + vy * b), (cx - ux * a + vx * b, cy - uy * a + vy * b),
            (cx - ux * a - vx * b, cy - uy * a - vy * b), (cx + ux * a - vx * b, cy + uy * a - vy * b)]
def rect_mask(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    x0, x1 = int(min(xs)), int(max(xs)) + 1; y0, y1 = int(min(ys)), int(max(ys)) + 1
    if x0 < 0 or y0 < 0 or x1 >= W or y1 >= H: return None
    im = Image.new('L', (x1 - x0 + 1, y1 - y0 + 1), 0)
    ImageDraw.Draw(im).polygon([(p[0] - x0, p[1] - y0) for p in poly], fill=1)
    return x0, y0, np.asarray(im).astype(bool)
def try_lot(poly, rank, kind, si):
    cx = sum(p[0] for p in poly) / 4; cy = sum(p[1] for p in poly) / 4
    if not interior(cx, cy, 22) or nobuild(cx, cy): return None
    sh = [(cx + (x - cx) * 0.9, cy + (y - cy) * 0.9) for x, y in poly]
    rm = rect_mask(sh)
    if rm is None: return None
    x0, y0, m = rm; h_, w_ = m.shape
    if (road[y0:y0 + h_, x0:x0 + w_] & m).any() or (lotmap[y0:y0 + h_, x0:x0 + w_] & m).any(): return None
    lotmap[y0:y0 + h_, x0:x0 + w_] |= m
    return dict(p=poly, cx=cx, cy=cy, rank=rank, kind=kind, si=si, z=zone_of(cx, cy), occ=[])

lots = []
order = sorted(range(len(streets)), key=lambda i: {'main': 0, 'street': 1, 'cross': 2, 'lane': 3}[streets[i]['kind']])
for si in order:
    s = streets[si]; pts = s['pts']
    for side in (1, -1):
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            if L < 1: continue
            ux, uy = (bx - ax) / L, (by - ay) / L
            t = random.uniform(0, 4)
            while t < L:
                kd = s['kind']
                _pr = s['w'] / 2 + 9
                dfn = district(ax + ux * (t + 5) - uy * _pr * side, ay + uy * (t + 5) + ux * _pr * side)
                LR = DR.LOTS.get(dfn)
                if LR:
                    shop = random.random() < LR['shop'] or (kd == 'main' and dfn != 'fine')
                    wid = random.uniform(*LR['wid']); dep = random.uniform(*LR['dep'])
                else:
                    shop = kd == 'main' or (kd == 'street' and random.random() < 0.3)
                    if shop: wid = random.uniform(10.5, 13); dep = random.uniform(13, 16)
                    else: wid = random.uniform(11, 17); dep = random.uniform(9, 14)
                off = s['w'] / 2 + 3 + dep / 2
                _py = ux * side   # >0: the lot lies south of (below) its street, so its roof would lean over it
                if _py > 0.2: off += _py * {'market': 10, 'shops': 9, 'fine': 7}.get(dfn, 5)
                cx = ax + ux * (t + wid / 2) - uy * off * side; cy = ay + uy * (t + wid / 2) + ux * off * side
                lot = try_lot(rect(cx, cy, ux, uy, wid / 2, dep / 2), 0, s['kind'], si)
                if lot: lot['t'] = 1 if shop else 0; lot['door'] = side; lot['fx'] = 1 if (uy * side) < -0.15 else 0; lot['f'] = dfn; lots.append(lot)
                t += wid + (random.uniform(*LR['gap']) if LR else random.uniform(0.2, 0.6) if shop else random.uniform(0.8, 2.6))
front = len(lots)
# rear row (houses reached through yards): fills capacity behind the street fronts
for L0 in list(lots[:front]):
    if not DR.LOTS.get(L0['f'], {'rear': True})['rear']: continue
    p = L0['p']; cx, cy = L0['cx'], L0['cy']
    s = streets[L0['si']]
    # vector from street to lot = perpendicular; approximate via first edge
    ex, ey = p[0][0] - p[1][0], p[0][1] - p[1][1]; el = math.hypot(ex, ey); ux, uy = ex / el, ey / el
    for sg in (1, -1):
        vx, vy = -uy * sg, ux * sg
        dep = random.uniform(9, 13)
        nx, ny = cx + vx * (13 + dep / 2), cy + vy * (13 + dep / 2)
        # pick the direction pointing away from the street: the lot must not be nearer the street
        if road[int(min(H - 1, max(0, ny))), int(min(W - 1, max(0, nx)))]: continue
        lot = try_lot(rect(nx, ny, ux, uy, el / 2 - 0.5, dep / 2), 1, 'rear', L0['si'])
        if lot: lot['t'] = 0; lot['fx'] = 1 - L0['fx']; lot['f'] = L0['f']; lots.append(lot); break
print('streets', len(streets), 'front lots', front, 'rear', len(lots) - front, file=sys.stderr)

# ---------------- assign houses ----------------
G = 40
grid = {}
for i, l in enumerate(lots): grid.setdefault((int(l['cx'] // G), int(l['cy'] // G)), []).append(i)
KP = {'main': -45, 'street': -20, 'cross': -6, 'lane': 0, 'rear': 12}
for i, l in enumerate(lots):
    gx, gy = int(l['cx'] // G), int(l['cy'] // G)
    l['nb'] = [j for ix in (gx - 1, gx, gx + 1) for iy in (gy - 1, gy, gy + 1) for j in grid.get((ix, iy), []) if j != i and math.hypot(lots[j]['cx'] - l['cx'], lots[j]['cy'] - l['cy']) < 21]
def free(l, b, e): return all(e <= ob or b >= oe for ob, oe in l['occ'])
assigned = {}; kept = 0; far = []
hs = sorted(houses, key=lambda h: (h[2], h[0]))
for h in hs:
    hid, dd, b, e, poly = h
    ox = sum(poly[0::2]) / 4; oy = sum(poly[1::2]) / 4
    if not interior(ox, oy, 0):
        kept += 1; continue
    z = zone_of(ox, oy)
    gx, gy = int(ox // G), int(oy // G); best = None
    for rr in range(0, 14):
        cand = []
        for ix in range(gx - rr, gx + rr + 1):
            for iy in range(gy - rr, gy + rr + 1):
                if max(abs(ix - gx), abs(iy - gy)) != rr: continue
                for li in grid.get((ix, iy), []):
                    l = lots[li]
                    if l['z'] != z or not free(l, b, e): continue
                    nb = sum(1 for j in l['nb'] if not free(lots[j], b, b + 1))
                    dist = 0.6 * math.hypot(l['cx'] - ox, l['cy'] - oy) + l['rank'] * 18 + KP[l['kind']] - 22 * min(nb, 2)
                    cand.append((dist, li))
        if cand:
            best = min(cand)
            if rr >= 2: break
    if best is None:
        far.append(hid); continue
    l = lots[best[1]]; l['occ'].append((b, e)); assigned[hid] = best[1]
print('assigned', len(assigned), 'kept outside', kept, 'unplaced', len(far), file=sys.stderr)

HB = {h[0]: h for h in houses}
newH = []
for h in houses:
    hid, dd, b, e, poly = h
    if hid in assigned:
        l = lots[assigned[hid]]
        newH.append([hid, dd, b, e, [round(c, 1) for p in l['p'] for c in p], l['fx'], l['t']])
    elif hid in far:
        continue  # dropped: no room on any street (counted)
    else:
        newH.append(h)
# street segments appear when the first house beside them appears
hg = {}
for h in newH:
    p = h[4]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4
    hg.setdefault((int(cx // 30), int(cy // 30)), []).append((cx, cy, h[2]))
outS = []
for si_, s_ in enumerate(streets):
    k = s_['kind'][0]
    for (ax, ay), (bx, by) in zip(s_['pts'][:-1], s_['pts'][1:]):
        L = math.hypot(bx - ax, by - ay); nseg = max(1, int(L // 18))
        for j in range(nseg):
            x1, y1 = ax + (bx - ax) * j / nseg, ay + (by - ay) * j / nseg
            x2, y2 = ax + (bx - ax) * (j + 1) / nseg, ay + (by - ay) * (j + 1) / nseg
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if k == 'm': y = 0
            elif True:
                y = 999
            else:
                y = 999
                for ix in (int(mx // 30) - 1, int(mx // 30), int(mx // 30) + 1):
                    for iy in (int(my // 30) - 1, int(my // 30), int(my // 30) + 1):
                        for hx, hy, hb in hg.get((ix, iy), []):
                            if math.hypot(hx - mx, hy - my) < s_['w'] / 2 + 16: y = min(y, hb)
            outS.append([round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1), s_['w'], k, y, si_])
# ---- audit fix B: every house's own street exists by the year the house is built
SGG = {}
for i, q in enumerate(outS): SGG.setdefault((int((q[0] + q[2]) / 2 // 30), int((q[1] + q[3]) / 2 // 30)), []).append(i)
def segd(px, py, q):
    return _sd(px, py, (q[0], q[1]), (q[2], q[3]))[0]
for hid, li in assigned.items():
    l = lots[li]; b = next(h[2] for h in [HB[hid]])
    best = None
    for ix in range(int(l['cx'] // 30) - 2, int(l['cx'] // 30) + 3):
        for iy in range(int(l['cy'] // 30) - 2, int(l['cy'] // 30) + 3):
            for i in SGG.get((ix, iy), []):
                if outS[i][7] != l['si']: continue
                dd = segd(l['cx'], l['cy'], outS[i])
                if best is None or dd < best[0]: best = (dd, i)
    if best: outS[best[1]][6] = min(outS[best[1]][6], b)
# ---- audit fix C: a road never appears cut off; the shortest way to the network appears with it
import heapq
nbr = [[] for _ in outS]
for i, q in enumerate(outS):
    for ex, ey in ((q[0], q[1]), (q[2], q[3])):
        for ix in (int(ex // 30) - 1, int(ex // 30), int(ex // 30) + 1):
            for iy in (int(ey // 30) - 1, int(ey // 30), int(ey // 30) + 1):
                for j in SGG.get((ix, iy), []):
                    if j != i and segd(ex, ey, outS[j]) <= max(1.5, outS[j][4] / 2 + 0.5):
                        nbr[i].append(j); nbr[j].append(i)
def edge(q): return min(q[0], q[2], q[1], q[3]) < 4 or max(q[0], q[2]) > W - 4 or max(q[1], q[3]) > H - 4
conn = [q[5] == 'm' or edge(q) for q in outS]  # a road leaving the quarter's edge joins the rest of the city
# spread connectivity through segments already present
def spread(seed, Y):
    st = [seed]
    while st:
        i = st.pop()
        for j in nbr[i]:
            if not conn[j] and outS[j][6] <= Y: conn[j] = True; st.append(j)
for i in range(len(outS)):
    if conn[i]: spread(i, 0)
unreach = []
order_ = sorted([i for i in range(len(outS)) if outS[i][6] < 999], key=lambda i: outS[i][6])
for i in order_:
    if conn[i]: continue
    Y = outS[i][6]
    dist = {i: 0}; prev = {}; pq = [(0, i)]; tgt = None
    while pq:
        d0, a = heapq.heappop(pq)
        if d0 > dist.get(a, 1e9): continue
        if conn[a] and outS[a][6] <= Y: tgt = a; break
        for b2 in nbr[a]:
            q = outS[b2]; L = math.hypot(q[2] - q[0], q[3] - q[1]) * (1 if q[6] <= Y else 3)
            if d0 + L < dist.get(b2, 1e9): dist[b2] = d0 + L; prev[b2] = a; heapq.heappush(pq, (d0 + L, b2))
    if tgt is None: unreach.append(i); continue
    a = tgt
    while a != i: a = prev[a]; outS[a][6] = min(outS[a][6], Y); conn[a] = True
    conn[i] = True; spread(i, Y)
# ---- audit fix F: no short holes inside a street; a gap under ~45 px between two visible stretches is paved with the later of them
from itertools import groupby
holes = 0
for si_k, grp in groupby(range(len(outS)), key=lambda i: outS[i][7]):
    idx = list(grp)
    vis_ = [k for k, i in enumerate(idx) if outS[i][6] < 999]
    for a_, b_ in zip(vis_[:-1], vis_[1:]):
        if b_ - a_ < 2: continue
        run = idx[a_ + 1:b_]
        L = sum(math.hypot(outS[i][2] - outS[i][0], outS[i][3] - outS[i][1]) for i in run)
        Y0 = max(outS[idx[a_]][6], outS[idx[b_]][6])
        if L < 45 or all(outS[i][6] <= Y0 for i in run):
            for i in run: outS[i][6] = min(outS[i][6], Y0)
            holes += 1
        else:
            for i in run:
                if outS[i][6] > Y0: pass
print('holes filled', holes, file=sys.stderr)
# ---- fix J: streets close into blocks. A street that has grown to within ~90 px of the road it runs into
# (or a hole of up to ~90 px inside it) is walked through two years after both sides are there.
def end_touch(i_, ex, ey, si_):
    best = None
    for ix in (int(ex // 30) - 1, int(ex // 30), int(ex // 30) + 1):
        for iy in (int(ey // 30) - 1, int(ey // 30), int(ey // 30) + 1):
            for j in SGG.get((ix, iy), []):
                if outS[j][7] == si_ or outS[j][6] >= 999: continue
                if segd(ex, ey, outS[j]) <= outS[j][4] / 2 + 2:
                    if best is None or outS[j][6] < best: best = outS[j][6]
    return best
closed = 0
for _pass in range(3):
    ch = 0
    for si_k, grp in groupby(sorted(range(len(outS)), key=lambda i: (outS[i][7], i)), key=lambda i: outS[i][7]):
        idx = list(grp)
        if si_k < 0 or outS[idx[0]][5] == 'm': continue
        yrs = [outS[i][6] for i in idx]
        # virtual anchors at both ends: the road this street runs into
        a0 = end_touch(idx[0], outS[idx[0]][0], outS[idx[0]][1], si_k)
        a1 = end_touch(idx[-1], outS[idx[-1]][2], outS[idx[-1]][3], si_k)
        ext = [a0 if a0 is not None else 999] + yrs + [a1 if a1 is not None else 999]
        vis_ = [k for k, y in enumerate(ext) if y < 999]
        for a_, b_ in zip(vis_[:-1], vis_[1:]):
            if b_ - a_ < 2: continue
            run = idx[a_:b_ - 1]   # ext index k maps to idx[k-1]
            L = sum(math.hypot(outS[i][2] - outS[i][0], outS[i][3] - outS[i][1]) for i in run)
            Y0 = max(ext[a_], ext[b_]) + 2
            if L <= 90 and Y0 <= 60 and any(outS[i][6] > Y0 for i in run):
                for i in run: outS[i][6] = min(outS[i][6], Y0)
                ch += 1
    closed += ch
    if not ch: break
print('fixJ gaps closed into blocks', closed, file=sys.stderr)
# ---- audit fix C2: islands with no way to the network get a short connecting lane, or are dropped
fixed = 0; dropped_isl = 0
for i in unreach:
    if conn[i]: continue
    # collect island
    isl = {i}; st = [i]
    while st:
        a_ = st.pop()
        for b2 in nbr[a_]:
            if b2 not in isl: isl.add(b2); st.append(b2)
    best = None
    for a_ in isl:
        q = outS[a_]
        for ex, ey in ((q[0], q[1]), (q[2], q[3])):
            for ix in range(int(ex // 30) - 2, int(ex // 30) + 3):
                for iy in range(int(ey // 30) - 2, int(ey // 30) + 3):
                    for j in SGG.get((ix, iy), []):
                        if j in isl or not conn[j]: continue
                        dd, pq_ = _sd(ex, ey, (outS[j][0], outS[j][1]), (outS[j][2], outS[j][3]))
                        if best is None or dd < best[0]: best = (dd, ex, ey, pq_, j)
    Ymin = min(outS[a_][6] for a_ in isl)
    if best and best[0] < 60 and not nobuild((best[1] + best[3][0]) / 2, (best[2] + best[3][1]) / 2):
        _, ex, ey, (px, py), j = best
        outS.append([round(ex, 1), round(ey, 1), round(px, 1), round(py, 1), 4, 'l', Ymin, -1]); nbr.append([j]); conn.append(True)
        for a_ in isl:
            conn[a_] = True; outS[a_][6] = max(outS[a_][6], Ymin) if outS[a_][6] < 999 else 999
        # connecting lane appears with the island's first house; island's other segments keep their years but now need the path inside the island too
        for a_ in isl:
            if outS[a_][6] < 999: outS[a_][6] = min(outS[a_][6], max(Ymin, outS[a_][6]))
        fixed += 1
    else:
        for a_ in isl: outS[a_][6] = 999
        dropped_isl += 1
print('islands joined', fixed, 'dropped', dropped_isl, file=sys.stderr)
# ---- audit fix G: any road end stopping within ~16 px of another road is joined by a short stub
GG = {}
for i, q in enumerate(outS):
    if q[6] >= 999: continue
    for ix in range(int(min(q[0], q[2]) // 30) - 1, int(max(q[0], q[2]) // 30) + 2):
        for iy in range(int(min(q[1], q[3]) // 30) - 1, int(max(q[1], q[3]) // 30) + 2):
            GG.setdefault((ix, iy), []).append(i)
stubs = []
for i, q in enumerate(outS):
    if q[6] >= 999 or q[5] == 'm': continue
    for ex, ey in ((q[0], q[1]), (q[2], q[3])):
        cand = GG.get((int(ex // 30), int(ey // 30)), [])
        if any(j != i and segd(ex, ey, outS[j]) <= max(1.5, outS[j][4] / 2 + 0.5) for j in cand): continue
        best = None
        for j in cand:
            if j == i: continue
            o = outS[j]
            if {(o[0], o[1]), (o[2], o[3])} & {(q[0], q[1]), (q[2], q[3])}: continue
            dd, pp = _sd(ex, ey, (o[0], o[1]), (o[2], o[3]))
            if dd - o[4] / 2 < 16 and (best is None or dd < best[0]): best = (dd, pp, j)
        if best and not nobuild(*best[1]):
            o = outS[best[2]]
            stubs.append([round(ex, 1), round(ey, 1), round(best[1][0], 1), round(best[1][1], 1), min(q[4], o[4], 5), 'l', max(q[6], o[6]), -2])
outS += stubs
print('stubs', len(stubs), file=sys.stderr)
# ---- audit fix D: roads close when a cistern is dug over them
for q in outS:
    mx, my = (q[0] + q[2]) / 2, (q[1] + q[3]) / 2
    for k, zz in late.items():
        if k.startswith('cistern') and q[5] != 'm' and pip(mx, my, zz['p']):
            if zz['built'] <= q[6]: q[6] = 999
            else: q.append(zz['built'])
# ---- audit fix H (hard rule): no building, walls or roof, ever stands on a road that exists while it stands
def endy(q): return q[8] if len(q) > 8 else 99999
HG = {}
def hg_add(i, q):
    for ix in range(int(min(q[0], q[2]) // 20) - 1, int(max(q[0], q[2]) // 20) + 2):
        for iy in range(int(min(q[1], q[3]) // 20) - 1, int(max(q[1], q[3]) // 20) + 2):
            HG.setdefault((ix, iy), []).append(i)
for i, q in enumerate(outS):
    if q[6] < 999: hg_add(i, q)
def _segseg(a, b, c, d_):
    def cr(o, p_, q_): return (p_[0] - o[0]) * (q_[1] - o[1]) - (p_[1] - o[1]) * (q_[0] - o[0])
    d1, d2, d3, d4 = cr(c, d_, a), cr(c, d_, b), cr(a, b, c), cr(a, b, d_)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)): return 0.0
    return min(_sd0(a[0], a[1], c, d_), _sd0(b[0], b[1], c, d_), _sd0(c[0], c[1], a, b), _sd0(d_[0], d_[1], a, b))
def hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3: return pts
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p_ in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p_) <= 0: lo.pop()
        lo.append(p_)
    for p_ in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p_) <= 0: up.pop()
        up.append(p_)
    return lo[:-1] + up[:-1]
def foot(flat):
    pts = [(flat[i], flat[i + 1]) for i in range(0, 8, 2)]; cx = sum(p_[0] for p_ in pts) / 4; cy = sum(p_[1] for p_ in pts) / 4
    return [(cx + (x - cx) * 0.92, cy + (y - cy) * 0.92) for x, y in pts]
def volume(fp, hgt): return hull(fp + [(x, y - hgt) for x, y in fp])
def clashes(vol, b, e, margin=0.8, out=None):
    vol = list(vol)
    xs = [p_[0] for p_ in vol]; ys = [p_[1] for p_ in vol]
    cand = set()
    for ix in range(int(min(xs) // 20), int(max(xs) // 20) + 1):
        for iy in range(int(min(ys) // 20), int(max(ys) // 20) + 1): cand.update(HG.get((ix, iy), ()))
    hit = []
    for j in cand:
        q = outS[j]
        if q[6] >= 999 or q[6] >= e or endy(q) <= b: continue
        a_, b_ = (q[0], q[1]), (q[2], q[3])
        inside = pip(q[0], q[1], vol) or pip(q[2], q[3], vol)
        dmin = 0 if inside else min(_segseg(vol[k], vol[(k + 1) % len(vol)], a_, b_) for k in range(len(vol)))
        if dmin < q[4] / 2 + margin: hit.append(j)
    return hit
def forbidden(vol, b, e):
    for x, y in vol:
        if wall_x(y) - 40 < x < wall_x(y) + 8: return True
        if nobuild(x, y): return True
        for k, zz in late.items():
            if k.startswith('cistern') and zz['built'] < e and pip(x, y, zz['p']): return True
    return False
HT = {}
newIdx = {h[0]: i for i, h in enumerate(newH)}
moved = dropped_seg = lowered = stuck = 0
import house_types as HT_
def front_edge(l):
    P = l['p']; best = (99, 2)
    for e in (0, 2):
        a, b = P[e], P[(e + 1) % 4]; mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        cx_, cy_ = l['cx'], l['cy']; dx, dy = mx - cx_, my - cy_; L = math.hypot(dx, dy) or 1
        for k in range(1, 22):
            x_, y_ = int(mx + dx / L * k), int(my + dy / L * k)
            if 0 <= x_ < W and 0 <= y_ < H and road[y_, x_]:
                if k < best[0]: best = (k, e)
                break
    return best[1]
HTYP = {}
def lot_type(l, hid):
    f = l.get('f', 'homes')
    if f == 'planned' and HB[hid][2] < 48: f = 'homes'
    P = l['p']; area = math.hypot(P[1][0] - P[0][0], P[1][1] - P[0][1]) * math.hypot(P[3][0] - P[0][0], P[3][1] - P[0][1])
    typ = HT_.pick_type(f, l['rank'], area, l['kind'] == 'main', hid)
    if 'front' not in l: l['front'] = front_edge(l)
    HTYP[hid] = (f, typ, l['front'], l['si'])
    return HT_.type_height(typ, f, l['rank'])
def want_h(l, hid=None): return lot_type(l, hid)
for hid, li in sorted(assigned.items(), key=lambda kv: HB[kv[0]][2]):
    hb, he = HB[hid][2], HB[hid][3]
    l = lots[li]; fp = foot([c for p_ in l['p'] for c in p_])
    if clashes(fp, hb, he) or forbidden(fp, hb, he):
        # move to the nearest free lot whose footprint is clear for the house's whole life
        best = None
        gx, gy = int(l['cx'] // G), int(l['cy'] // G)
        for ix in range(gx - 3, gx + 4):
            for iy in range(gy - 3, gy + 4):
                for lj in grid.get((ix, iy), []):
                    L2 = lots[lj]
                    if lj == li or L2['z'] != l['z'] or not free(L2, hb, he): continue
                    f2 = foot([c for p_ in L2['p'] for c in p_])
                    if clashes(volume(f2, 2), hb, he) or forbidden(f2, hb, he): continue
                    dd = math.hypot(L2['cx'] - l['cx'], L2['cy'] - l['cy'])
                    if best is None or dd < best[0]: best = (dd, lj)
        if best:
            l['occ'].remove((hb, he)); li = best[1]; l = lots[li]; l['occ'].append((hb, he)); assigned[hid] = li
            newH[newIdx[hid]][4] = [round(c, 1) for p_ in l['p'] for c in p_]; newH[newIdx[hid]][5] = l['fx']; newH[newIdx[hid]][6] = l['t']
            fp = foot([c for p_ in l['p'] for c in p_]); moved += 1
        else:
            # the road gives way instead: late connector stubs / lanes open only after the house is gone
            for j in clashes(fp, hb, he):
                q = outS[j]
                if q[5] in ('l', 'c') and he < 999: q[6] = max(q[6], he)
                elif q[5] in ('l',): q[6] = 999
                dropped_seg += 1
            if clashes(fp, hb, he): stuck += 1
    hgt = want_h(l, hid)
    def _row(hg_):
        f_, t_, fr_, si_ = HTYP[hid]
        return [hid, 0, 0, 0, [c for p_ in l['p'] for c in p_], 0, 0, hg_, f_, t_, fr_, si_]
    def _ex(hg_): return HT_.roof_extra(_row(hg_))
    fpd = HT_.footprint(_row(hgt))
    if HTYP[hid][1] == 'row' and (clashes(fpd, hb, he, 0.6) or forbidden(fpd, hb, he)):   # no room to run wall to wall here
        f_, t_, fr_, si_ = HTYP[hid]; HTYP[hid] = (f_, 'casa', fr_, si_); hgt = HT_.type_height('casa', f_, l['rank']); fpd = HT_.footprint(_row(hgt))
    while hgt > 0 and clashes(volume(fpd, hgt + _ex(hgt)), hb, he, 0.6): hgt -= 0.5
    if hgt <= 1.5 and HTYP[hid][1] not in ('flat', 'yard'):   # no room for a pitched roof here: a low flat-roofed house instead
        f_, t_, fr_, si_ = HTYP[hid]; HTYP[hid] = (f_, 'flat', fr_, si_); hgt = 4
        fpd = HT_.footprint(_row(hgt))
        while hgt > 0 and clashes(volume(fpd, hgt), hb, he, 0.6): hgt -= 0.5
    if hgt < HT_.type_height(HTYP[hid][1], HTYP[hid][0], l['rank']): lowered += 1
    hgt = max(0, hgt)
    HT[hid] = hgt
for h in newH:
    if h[0] in HT:
        while len(h) < 7: h.append(0)
        h[7:] = [HT[h[0]]]
# houses beyond the wall keep clear of the wall itself
wall_moved = 0
for h in newH:
    if h[0] in HT: continue
    p_ = h[4]; xs = p_[0::2]; ys = p_[1::2]
    if any(wall_x(y) - 40 < x < wall_x(y) + 8 for x, y in zip(xs, ys)):
        sh_ = max(x - (wall_x(y) - 42) for x, y in zip(xs, ys))
        h[4] = [round(c - sh_, 1) if i % 2 == 0 else c for i, c in enumerate(p_)]; wall_moved += 1
kept_moved = 0
for h in newH:
    if h[0] in HT: continue
    b_, e_ = h[2], h[3]
    best = None
    for r_ in (0, 3, 6, 9, 12, 16):
        for k_ in range(8 if r_ else 1):
            dx_, dy_ = r_ * math.cos(k_ * math.pi / 4), r_ * math.sin(k_ * math.pi / 4)
            fl = [c + (dx_ if i % 2 == 0 else dy_) for i, c in enumerate(h[4])]
            fp_ = foot(fl)
            if not clashes(volume(fp_, 4), b_, e_) and not any(wall_x(y) - 40 < x < wall_x(y) + 8 for x, y in fp_): best = fl; break
        if best: break
    if best is None: best = h[4]
    elif best != h[4]: kept_moved += 1
    h[4] = [round(c, 1) for c in best]
    while len(h) < 7: h.append(0)
    h[7:] = [4]
print('kept outside moved', kept_moved, file=sys.stderr)
print('fixH moved', moved, 'roads gave way', dropped_seg, 'lowered', lowered, 'stuck', stuck, 'wall', wall_moved, file=sys.stderr)
# ---- roads grow: a trodden track is walked in a few years before a street is laid (streets 3, lanes 2),
# only where no standing house is in the way, and never earlier than the track it branches from.
LEAD = {'s': 3, 'c': 2, 'l': 2}
HOUSEG = {}
for h in newH:
    p_ = h[4]; cx_ = sum(p_[0::2]) / 4; cy_ = sum(p_[1::2]) / 4
    HOUSEG.setdefault((int(cx_ // 20), int(cy_ // 20)), []).append(h)
def track_ok(q, a, b):
    """True if no house body standing at any time in [a,b) touches segment q"""
    mx, my = (q[0] + q[2]) / 2, (q[1] + q[3]) / 2
    for ix in range(int(mx // 20) - 2, int(mx // 20) + 3):
        for iy in range(int(my // 20) - 2, int(my // 20) + 3):
            for h in HOUSEG.get((ix, iy), []):
                if h[3] <= a or h[2] >= b: continue
                fp_ = foot(h[4]); ht_ = h[7] if len(h) > 7 else 4
                vol = volume(fp_, ht_)
                if pip(q[0], q[1], vol) or pip(q[2], q[3], vol): return h
                if min(_segseg(vol[k], vol[(k + 1) % len(vol)], (q[0], q[1]), (q[2], q[3])) for k in range(len(vol))) < q[4] / 2 + 0.8: return h
    return None
# ---- fix K: after houses settled, no stretch of road is ever cut off in any year: an island gets a short lane
# to the nearest connected road (only where no house ever stands on it from then on)
def _vis(q, Y): return q[6] <= Y and not (len(q) > 8 and q[8] and q[8] <= Y)
def _edge(q): return min(q[0], q[2], q[1], q[3]) < 4 or max(q[0], q[2]) > W - 4 or max(q[1], q[3]) > H - 4
kfix = kfail = 0
for Y in range(1, 61):
    vs = [i for i, q in enumerate(outS) if _vis(q, Y)]
    g_ = {}
    for i in vs:
        q = outS[i]; g_.setdefault((int((q[0] + q[2]) / 2 // 30), int((q[1] + q[3]) / 2 // 30)), []).append(i)
    par = {i: i for i in vs}
    def fd(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i in vs:
        q = outS[i]
        for ex, ey in ((q[0], q[1]), (q[2], q[3])):
            for ix in (int(ex // 30) - 1, int(ex // 30), int(ex // 30) + 1):
                for iy in (int(ey // 30) - 1, int(ey // 30), int(ey // 30) + 1):
                    for j in g_.get((ix, iy), []):
                        if j != i and _sd(ex, ey, (outS[j][0], outS[j][1]), (outS[j][2], outS[j][3]))[0] <= outS[j][4] / 2 + 2: par[fd(i)] = fd(j)
    good = {fd(i) for i in vs if outS[i][5] == 'm' or _edge(outS[i])}
    comps = {}
    for i in vs:
        r_ = fd(i)
        if r_ not in good: comps.setdefault(r_, []).append(i)
    for r_, isl in comps.items():
        iss = set(isl); cands = []
        for a_ in isl:
            q = outS[a_]
            for ex, ey in ((q[0], q[1]), (q[2], q[3])):
                for ix in range(int(ex // 30) - 2, int(ex // 30) + 3):
                    for iy in range(int(ey // 30) - 2, int(ey // 30) + 3):
                        for j in g_.get((ix, iy), []):
                            if j in iss or fd(j) not in good: continue
                            dd, pq_ = _sd(ex, ey, (outS[j][0], outS[j][1]), (outS[j][2], outS[j][3]))
                            if dd < 60: cands.append((dd, ex, ey, pq_))
        done_ = False
        for dd, ex, ey, (px, py) in sorted(cands)[:12]:
            st_ = [round(ex, 1), round(ey, 1), round(px, 1), round(py, 1), 4, 'l', Y, -2]
            if nobuild((ex + px) / 2, (ey + py) / 2) or track_ok(st_, Y, 9999): continue
            outS.append(st_); kfix += 1; done_ = True; break
        if not done_: kfail += 1
print('fixK islands joined', kfix, 'could not', kfail, file=sys.stderr)
ntr = 0
for q in outS:
    while len(q) < 10: q.append(0)
    if q[6] >= 999 or q[5] == 'm': q[9] = q[6]; continue
    ts = max(1, q[6] - LEAD[q[5]])
    while ts < q[6]:
        h = track_ok(q, ts, q[6])
        if h is None: break
        ts = min(q[6], h[3])
    q[9] = ts
    if ts < q[6]: ntr += 1
# a track never shows before the way it hangs from: relax over neighbours
for _ in range(6):
    ch = 0
    for i, q in enumerate(outS):
        if q[6] >= 999 or q[5] == 'm' or q[9] >= q[6]: continue
        # earliest any connected neighbour is walkable
        nb_ = [outS[j][9] for j in nbr[i] if j < len(outS) and outS[j][6] < 999] if i < len(nbr) else []
        if nb_ and min(nb_) > q[9]: q[9] = min(q[6], min(nb_)); ch += 1
    if not ch: break
print('tracks leading their street', ntr, file=sys.stderr)
json.dump({'si': [q[7] for q in outS if q[6] < 999], 'streets': [dict(k=st['kind'], w=st['w'], pts=[[round(c, 1) for c in p_] for p_ in st['pts']]) for st in streets]}, open('/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/gen/_streets_meta.json', 'w'))
outS = [q[:7] + [q[8], q[9]] for q in outS if q[6] < 999]
# junctions: where two different streets meet; wells, stalls, ovens grow there
cell = {}
for si_, s_ in enumerate(streets):
    for (ax, ay), (bx, by) in zip(s_['pts'][:-1], s_['pts'][1:]):
        L = math.hypot(bx - ax, by - ay)
        for j in range(int(L // 3) + 1):
            x = ax + (bx - ax) * j / max(1, L // 3); y = ay + (by - ay) * j / max(1, L // 3)
            cell.setdefault((int(x // 10), int(y // 10)), set()).add(si_)
jc = []
for (cx_, cy_), ss in cell.items():
    if len(ss) >= 2:
        x, y = cx_ * 10 + 5, cy_ * 10 + 5
        if all(math.hypot(x - a, y - b) > 40 for a, b in jc): jc.append((x, y))
segy = {}
for q in outS: segy.setdefault((int(q[0] // 30), int(q[1] // 30)), []).append(q)
JU = []
for x, y in jc:
    ys = [q[6] for ix in (int(x // 30) - 1, int(x // 30), int(x // 30) + 1) for iy in (int(y // 30) - 1, int(y // 30), int(y // 30) + 1) for q in segy.get((ix, iy), []) if q[5] != 'm' and math.hypot(q[0] - x, q[1] - y) < 25]
    if len(ys) < 3: continue
    yy = sorted(ys)[min(len(ys) - 1, 2)] + 2  # a few years after the lanes fill in
    r = random.random(); kind = 'well' if r < .45 else 'stall' if r < .8 else 'oven'
    JU.append([round(x), round(y), yy, kind])
json.dump(JU, open(X + 'junctions.json', 'w'))
print('junctions', len(JU), file=sys.stderr)
# each house takes the character of the district its lot was cut for (the new quarter only after the fire)
for h in newH:
    while len(h) < 8: h.append(4)
    f, typ, fr, si_ = HTYP.get(h[0], ('homes', 'casa', 2, -1))
    h[8:] = [f, typ, fr, si_]
print('houses by district', _C(h[8] for h in newH).most_common(), file=sys.stderr)
print('houses by type', _C(h[9] for h in newH).most_common(), file=sys.stderr)
D2 = dict(D); D2['houses'] = newH
json.dump(D2, open(X + 'houses.json', 'w'), separators=(',', ':'))
json.dump(outS, open(X + 'streets.json', 'w'), separators=(',', ':'))
print('dropped', far[:20], len(far), 'streets out', len(outS), file=sys.stderr)
