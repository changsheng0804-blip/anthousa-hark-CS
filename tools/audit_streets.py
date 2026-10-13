#!/usr/bin/env python3
"""Road-network audit for a quarter: per year, checks that visible roads connect to the main roads,
finds dead ends that nearly touch another road, roads through cisterns/landmarks/outside the wall,
houses sitting on roads, and houses with no road near them. Writes audit.json + audit_YY.jpg overlays."""
import json, math, sys
from PIL import Image, ImageDraw
X = sys.argv[1] if len(sys.argv) > 1 else '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
S = json.load(open(X + 'streets.json')); HD = json.load(open(X + 'houses.json')); HS = HD['houses']; late = HD['late']
city = json.load(open(X + 'city.json')); LM = {l['id']: l for l in city['landmarks']}
def wall_x(y): return 587 - 0.2357 * y
def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
def sd(px, py, s):
    ax, ay, bx, by = s[:4]; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
G = 25
def grid_of(segs):
    g = {}
    for i, s in enumerate(segs):
        for gx in range(int(min(s[0], s[2]) // G) - 1, int(max(s[0], s[2]) // G) + 2):
            for gy in range(int(min(s[1], s[3]) // G) - 1, int(max(s[1], s[3]) // G) + 2):
                g.setdefault((gx, gy), []).append(i)
    return g
def near(g, x, y): return set(g.get((int(x // G), int(y // G)), []))
NB = [(LM[k]['xy'], r, k) for k, r in [('baths_constantius', 55), ('barracks_gate', 60), ('aqb_valley', 30)] if k in LM]
def body(h):
    p = h[4]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]; cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    fp = [(cx + (x - cx) * 0.92, cy + (y - cy) * 0.92) for x, y in pts]; ht = h[7] if len(h) > 7 else 5
    return fp + [(x, y - ht) for x, y in fp]
def _ss(a, b, c, d):
    def cr(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if ((cr(c, d, a) > 0) != (cr(c, d, b) > 0)) and ((cr(a, b, c) > 0) != (cr(a, b, d) > 0)): return 0
    f = lambda P, s: sd(P[0], P[1], (s[0][0], s[0][1], s[1][0], s[1][1]))
    return min(f(a, (c, d)), f(b, (c, d)), f(c, (a, b)), f(d, (a, b)))
def bodyhit(h, segs, g):
    B = body(h); fp, up = B[:4], B[4:]
    polys = [fp, up] + [[fp[k], fp[(k + 1) % 4], up[(k + 1) % 4], up[k]] for k in range(4)]
    cx = sum(q[0] for q in fp) / 4; cy = sum(q[1] for q in fp) / 4
    cand = set()
    for dx in (-G, 0, G):
        for dy in (-G, 0, G): cand |= near(g, cx + dx, cy + dy)
    for j in cand:
        s = segs[j]; a, b = (s[0], s[1]), (s[2], s[3])
        for P in polys:
            if pip(s[0], s[1], P) or pip(s[2], s[3], P): return True
            if min(_ss(P[k], P[(k + 1) % len(P)], a, b) for k in range(len(P))) < s[4] / 2 + 0.3: return True
    return False
def strict_all():
    """every house over its whole life vs every road over its whole life (body = walls + roof)"""
    g = grid_of(S); bad = []
    for h in HS:
        if len(h) < 8: continue
        b, e = h[2], h[3]
        live = [i for i in range(len(S))]
        segs = S
        B = body(h); cx = sum(q[0] for q in B[:4]) / 4; cy = sum(q[1] for q in B[:4]) / 4
        cand = set()
        for dx in (-G, 0, G):
            for dy in (-G, 0, G): cand |= near(g, cx + dx, cy + dy)
        sub = [S[j] for j in cand if (S[j][8] if len(S[j]) > 8 else S[j][6]) < e and not (len(S[j]) > 7 and S[j][7] and S[j][7] <= b)]
        if sub and bodyhit(h, sub, grid_of(sub)): bad.append(h[0])
    return bad
def audit(Y, draw=None):
    segs = [s for s in S if s[6] <= Y and not (len(s) > 7 and s[7] and s[7] <= Y)]; g = grid_of(segs)
    # union-find connectivity: endpoints touching another segment's band
    par = list(range(len(segs)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    deg = {}
    for i, s in enumerate(segs):
        for ex, ey, end in ((s[0], s[1], 0), (s[2], s[3], 1)):
            d = 0
            for j in near(g, ex, ey):
                if j == i: continue
                if sd(ex, ey, segs[j]) <= max(1.5, segs[j][4] / 2 + 0.5):
                    par[f(i)] = f(j)
                    o = segs[j]
                    # a continuation of the same polyline doesn't count as a junction for dead-end purposes
                    d += 1
            deg[(i, end)] = d
    comp_main = {f(i) for i, s in enumerate(segs) if s[5] == 'm' or min(s[0], s[1], s[2], s[3]) < 4 or max(s[0], s[2]) > 1816 or max(s[1], s[3]) > 2044}
    iso = [i for i in range(len(segs)) if f(i) not in comp_main]
    # dead ends that nearly touch another road (gap 2..14 px)
    gaps = []
    for (i, end), d in deg.items():
        if d: continue
        s = segs[i]
        if s[5] == 'm': continue
        ex, ey = (s[0], s[1]) if end == 0 else (s[2], s[3])
        best = min((sd(ex, ey, segs[j]) - segs[j][4] / 2 for j in near(g, ex, ey) if j != i and not ({(segs[j][0], segs[j][1]), (segs[j][2], segs[j][3])} & {(s[0], s[1]), (s[2], s[3])})), default=99)
        if 0.5 < best < 14: gaps.append((ex, ey, round(best, 1)))
    par_close = 0
    for i, s in enumerate(segs):
        if s[5] == 'm': continue
        mx, my = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2; a1 = math.atan2(s[3] - s[1], s[2] - s[0])
        for j in near(g, mx, my):
            if j == i: continue
            o = segs[j]
            if {(o[0], o[1]), (o[2], o[3])} & {(s[0], s[1]), (s[2], s[3])}: continue
            a2 = math.atan2(o[3] - o[1], o[2] - o[0]); da = abs((a1 - a2 + math.pi / 2) % math.pi - math.pi / 2)
            dx, dy = o[2] - o[0], o[3] - o[1]; L2 = dx * dx + dy * dy + 1e-9
            t = ((mx - o[0]) * dx + (my - o[1]) * dy) / L2
            if not (0 <= t <= 1): continue
            perp = abs((mx - o[0]) * dy - (my - o[1]) * dx) / math.sqrt(L2)
            if da < 0.45 and (s[4] + o[4]) / 2 + 0.5 < perp < (s[4] + o[4]) / 2 + 9: par_close += 1; break
    deadends = sum(1 for (i, end), d in deg.items() if d == 0 and segs[i][5] != 'm')
    # forbidden ground
    bad = []
    for s in segs:
        mx, my = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
        if s[5] != 'm' and mx < wall_x(my) + 8: bad.append((mx, my, 'outside wall'))
        for k, z in late.items():
            if k.startswith('cistern') and z['built'] <= Y and pip(mx, my, z['p']) and s[5] != 'm': bad.append((mx, my, k))
        for c, r, k in NB:
            if math.hypot(mx - c[0], my - c[1]) < r and s[5] != 'm': bad.append((mx, my, k))
    # houses
    vis = [h for h in HS if h[2] <= Y < h[3]]
    onroad = []; noroad = []
    for h in vis:
        p = h[4]; pts = [(p[0], p[1]), (p[2], p[3]), (p[4], p[5]), (p[6], p[7])]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4
        cand = near(g, cx, cy)
        if bodyhit(h, segs, g): onroad.append((cx, cy))
        dmin = min((sd(cx, cy, segs[j]) for j in cand), default=99)
        if dmin > 40:
            # wider look
            dmin = min((sd(cx, cy, s) for s in segs if abs(s[0] - cx) < 60 and abs(s[1] - cy) < 60), default=99)
            if dmin > 40 and cx > wall_x(cy): noroad.append((cx, cy))
    R = dict(year=Y, segments=len(segs), isolated_segments=len(iso), isolated_len=round(sum(math.hypot(segs[i][2] - segs[i][0], segs[i][3] - segs[i][1]) for i in iso)),
             dead_ends=deadends, parallel_close=par_close, near_miss_gaps=len(gaps), forbidden=len(bad), forbidden_kinds=sorted({b[2] for b in bad}),
             houses=len(vis), houses_on_road=len(onroad), houses_far_from_road=len(noroad))
    if draw:
        im = Image.open(X + draw).convert('RGB'); d = ImageDraw.Draw(im)
        for i in iso: s = segs[i]; d.line(s[:4], fill=(255, 0, 255), width=5)
        for x, y, _ in gaps: d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(0, 255, 255), width=3)
        for x, y, _ in bad: d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 0, 0))
        for x, y in onroad: d.rectangle((x - 3, y - 3, x + 3, y + 3), outline=(255, 255, 0), width=2)
        for x, y in noroad: d.rectangle((x - 3, y - 3, x + 3, y + 3), outline=(0, 0, 255), width=2)
        im.resize((im.width // 2, im.height // 2)).save('/tmp/audit_%d.jpg' % Y, quality=85)
    return R
if __name__ == '__main__':
    out = [audit(Y, draw=('xero_af%d.jpg' % Y) if Y in (40, 50, 60) else None) for Y in (40, 45, 50, 55, 60)]
    for r in out: print(r)
    sb = strict_all(); print('STRICT houses touching a road at any time:', len(sb), sb[:20])
    json.dump(out, open('/tmp/audit.json', 'w'), indent=1)
