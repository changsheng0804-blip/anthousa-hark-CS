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
    pts = [P(u + amp * math.sin(v / 210 + ph), v) for v in np.arange(vmin, vmax + 1, 30)]
    longs.append((u, w, pts, ph, amp)); u += random.uniform(64, 82); i += 1
def ulong(L, v): u, w, pts, ph, amp = L; return u + amp * math.sin(v / 210 + ph)
# break long lanes randomly (dead ends) - lanes only
for (u0, w, pts, ph, amp) in longs:
    if w == 8:
        streets.append(dict(w=w, kind='street', pts=pts))
    else:
        cur = []
        for p in pts:
            if random.random() < 0.05 and len(cur) > 3:
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
            streets.append(dict(w=6, kind='cross', pts=[P(ua, vv), P(ub, vv + tilt * (b[0] - a[0]))]))
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

# road raster for collision
road = Image.new('L', (W, H), 0); rd = ImageDraw.Draw(road)
for s in streets:
    rd.line([tuple(p) for p in s['pts']], fill=255, width=int(s['w'] + 3), joint='curve')
road = np.asarray(road) > 0
lotmap = np.zeros((H, W), bool)

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
                shop = kd == 'main' or (kd == 'street' and random.random() < 0.3)
                if shop: wid = random.uniform(10.5, 13); dep = random.uniform(13, 16)
                else: wid = random.uniform(11, 17); dep = random.uniform(9, 14)
                off = s['w'] / 2 + 3 + dep / 2
                cx = ax + ux * (t + wid / 2) - uy * off * side; cy = ay + uy * (t + wid / 2) + ux * off * side
                lot = try_lot(rect(cx, cy, ux, uy, wid / 2, dep / 2), 0, s['kind'], si)
                if lot: lot['t'] = 1 if shop else 0; lot['door'] = side; lot['fx'] = 1 if (uy * side) < -0.15 else 0; lots.append(lot)
                t += wid + (random.uniform(0.2, 0.6) if shop else random.uniform(0.8, 2.6))
front = len(lots)
# rear row (houses reached through yards): fills capacity behind the street fronts
for L0 in list(lots[:front]):
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
        if lot: lot['t'] = 0; lot['fx'] = 1 - L0['fx']; lots.append(lot); break
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
for s_ in streets:
    k = s_['kind'][0]
    for (ax, ay), (bx, by) in zip(s_['pts'][:-1], s_['pts'][1:]):
        L = math.hypot(bx - ax, by - ay); nseg = max(1, int(L // 18))
        for j in range(nseg):
            x1, y1 = ax + (bx - ax) * j / nseg, ay + (by - ay) * j / nseg
            x2, y2 = ax + (bx - ax) * (j + 1) / nseg, ay + (by - ay) * (j + 1) / nseg
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if k == 'm': y = 0
            else:
                y = 999
                for ix in (int(mx // 30) - 1, int(mx // 30), int(mx // 30) + 1):
                    for iy in (int(my // 30) - 1, int(my // 30), int(my // 30) + 1):
                        for hx, hy, hb in hg.get((ix, iy), []):
                            if math.hypot(hx - mx, hy - my) < s_['w'] / 2 + 16: y = min(y, hb)
                if y == 999: continue
            outS.append([round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1), s_['w'], k, max(y, -99)])
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
D2 = dict(D); D2['houses'] = newH
json.dump(D2, open(X + 'houses.json', 'w'), separators=(',', ':'))
json.dump(outS, open(X + 'streets.json', 'w'), separators=(',', ':'))
print('dropped', far[:20], len(far), 'streets out', len(outS), file=sys.stderr)
