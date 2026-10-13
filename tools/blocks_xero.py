#!/usr/bin/env python3
"""Blocks (街区) grow out of the street network: every year, the ground fully enclosed by streets
(plus the wall, the aqueduct and the big public buildings) splits into blocks. A block keeps its
identity while its outline is unchanged. Each block takes a function from what it touches:
main-road frontage -> market / shopfronts, a cistern -> water carriers, the barracks -> garrison,
the gate or the wall -> workshops, the baths -> better houses, burnt ground -> the planned new quarter,
thin settlement -> gardens, otherwise ordinary homes.
Writes blocks.json and stamps each house with the function of its block (houses.json row index 8).
Run after streets_xero.py."""
import json, math
import numpy as np
import cv2
from scipy import ndimage

X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
W, H = 1820, 2048; SC = 0.5; w_, h_ = int(W * SC), int(H * SC)
S = json.load(open(X + 'streets.json')); HD = json.load(open(X + 'houses.json')); HS = HD['houses']; late = HD['late']
city = json.load(open(X + 'city.json')); LM = {l['id']: l for l in city['landmarks']}
def wall_x(y): return 587 - 0.2357 * y
AQ = [(760, 0), (1820, 515)]
def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
def segd(px, py, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
# where main roads cross: market squares grow there
MJ = []
R = [r['pts'] for r in city['roads']]
def inter(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9: return None
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    if 0 <= t <= 1 and 0 <= u <= 1: return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
for i in range(len(R)):
    for j in range(i + 1, len(R)):
        for a, b in zip(R[i][:-1], R[i][1:]):
            for c, d in zip(R[j][:-1], R[j][1:]):
                q = inter(a, b, c, d)
                if q and 0 < q[0] < W and 0 < q[1] < H: MJ.append(q)
FIRE = late['fire_ruins']['p']
CIST = {k: v for k, v in late.items() if k.startswith('cistern')}
def cen(p): return (sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p))

import sys; sys.path.insert(0, '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/gen')
import district_rules as DR
FN = DR.FN
def function(Y, comp, ring, mainm, cx, cy, area, nh, hs):
    fs = [h[8] for h in hs if len(h) > 8]
    if len(fs) >= 3:   # a block is what its houses are
        from collections import Counter
        return Counter(fs).most_common(1)[0][0]
    front = (ring & mainm).sum() / max(1, ring.sum())
    return DR.classify(cx, cy, area, front, nh / area, Y)

base = np.zeros((h_, w_), np.uint8)
ys = np.arange(h_)[:, None] / SC; xs = np.arange(w_)[None, :] / SC
base[xs < wall_x(ys) + 6] = 1
cv2.line(base, (int(AQ[0][0] * SC), int(AQ[0][1] * SC)), (int(AQ[1][0] * SC), int(AQ[1][1] * SC)), 1, 6)
for k, r in (('baths_constantius', 46),):
    x, y = LM[k]['xy']; cv2.circle(base, (int(x * SC), int(y * SC)), int(r * SC), 1, -1)
HC = [(h, sum(h[4][0::2]) / 4, sum(h[4][1::2]) / 4) for h in HS]

blocks = []; live = {}  # key -> block index
house_fn = {}
prev_sig = None
for Y in range(1, 61):
    segs = [q for q in S if q[6] <= Y and not (q[7] and q[7] <= Y)]
    sig = len(segs)
    m = base.copy(); mainm = np.zeros_like(m)
    for k, z in CIST.items():
        if z['built'] <= Y: cv2.fillPoly(m, [np.int32([[p[0] * SC, p[1] * SC] for p in z['p']])], 1)
    for q in segs:
        a = (int(round(q[0] * SC)), int(round(q[1] * SC))); b = (int(round(q[2] * SC)), int(round(q[3] * SC)))
        cv2.line(m, a, b, 1, max(1, int(round(q[4] * SC))))
        if q[5] == 'm': cv2.line(mainm, a, b, 1, max(1, int(round(q[4] * SC)) + 2))
    lab, n = ndimage.label(m == 0)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(n + 1))
    # houses standing this year, by block label
    hl = {}
    for h, cx, cy in HC:
        if h[2] <= Y < h[3]:
            L = lab[min(h_ - 1, int(cy * SC)), min(w_ - 1, int(cx * SC))]
            hl.setdefault(L, []).append(h)
    seen = set()
    objs = ndimage.find_objects(lab)
    for L in range(1, n + 1):
        area = sizes[L] / SC / SC
        if area < 250 or area > 70000: continue
        sl = objs[L - 1]; y0, y1 = max(0, sl[0].start - 3), min(h_, sl[0].stop + 3); x0, x1 = max(0, sl[1].start - 3), min(w_, sl[1].stop + 3)
        comp = (lab[y0:y1, x0:x1] == L)
        yy, xx = np.nonzero(comp); cx = (xx.mean() + x0) / SC; cy = (yy.mean() + y0) / SC
        key = (int(sizes[L]), int(cx), int(cy))
        seen.add(key)
        nh = len(hl.get(L, []))
        if key in live:
            bi = live[key]; blocks[bi]['b'] = Y + 1
        else:
            ring = cv2.dilate(comp.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~comp
            f = function(Y, comp, ring, mainm[y0:y1, x0:x1].astype(bool), cx, cy, area, nh, hl.get(L, []))
            cs, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c = max(cs, key=cv2.contourArea); c = cv2.approxPolyDP(c, 0.8, True)
            poly = [round(float(v), 1) for pt in c[:, 0, :] for v in ((pt[0] + x0 + .5) / SC, (pt[1] + y0 + .5) / SC)]
            blocks.append(dict(p=poly, a=Y, b=Y + 1, f=f, c=[round(cx), round(cy)], A=round(area)))
            live[key] = len(blocks) - 1
    for k_ in [k_ for k_ in live if k_ not in seen]: del live[k_]
for b in blocks:
    if b['b'] > 60: b['b'] = 999
json.dump(dict(fn={k: [v[0], v[1]] for k, v in FN.items()}, blocks=blocks), open(X + 'blocks.json', 'w'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
for Y in (30, 40, 50, 60):
    act = [b for b in blocks if b['a'] <= Y < b['b']]
    print(Y, 'blocks', len(act), Counter(b['f'] for b in act).most_common())
print('records', len(blocks))
