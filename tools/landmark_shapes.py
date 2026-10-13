"""Shared shape vocabulary for landmarks (open typology). A landmark house has h[9] = 'lm:<spec id>';
house_types._geom_full hands it here. Every part carries its own year range so a spec's stages grow the building.
Shapes: steps, rect, atrium, basilica (nave + aisles + apse + atrium). Add new primitives here; new types are JSON specs."""
import json, math, os
import house_types as HT
from house_types import shade, _lerp, _ny, walls, gable, hsh, split
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'landmarks')
SPECS = {f[:-5]: json.load(open(os.path.join(D, f))) for f in sorted(os.listdir(D)) if f.endswith('.json')}
FOREVER = 9999

def frame_of(h):
    """lot quad shrunk; M(s,t): s along the long axis from west end (0) to east end (1), t across"""
    p = h[4]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]
    cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    Q = [(cx + (x - cx) * 0.92, cy + (y - cy) * 0.92) for x, y in pts]
    L01 = math.hypot(Q[1][0] - Q[0][0], Q[1][1] - Q[0][1]); L03 = math.hypot(Q[3][0] - Q[0][0], Q[3][1] - Q[0][1])
    if L01 >= L03: a0, a1, b1, b0 = Q[0], Q[1], Q[2], Q[3]
    else: a0, a1, b1, b0 = Q[0], Q[3], Q[2], Q[1]
    if (a1[0] + b1[0]) < (a0[0] + b0[0]): a0, a1, b0, b1 = a1, a0, b1, b0   # s runs west -> east
    def M(s, t): return _lerp(_lerp(a0, a1, s), _lerp(b0, b1, s), t)
    return M, (cx, cy)
def box(M, s0, s1, t0, t1): return [M(s0, t0), M(s1, t0), M(s1, t1), M(s0, t1)]
def tag(P, R): return [q[:4] + (R,) for q in P]

def hall(M, s0, s1, t0, t1, ht, wall, roof, hid, lift):
    P = []; fp = box(M, s0, s1, t0, t1)
    walls(P, fp, ht, wall, hid, 0, door=False)
    up = [(x, y - ht) for x, y in fp]
    gable(P, up, roof, wall, lift)
    return P, sum(q[1] for q in fp) / 4
def lean(M, s0, s1, t0, t1, ht, wall, roof, hid):
    P = []; fp = box(M, s0, s1, t0, t1)
    walls(P, fp, ht, wall, hid, 0, door=False)
    up = [(x, y - ht) for x, y in fp]
    P.append(('fill', 'r', up, shade(roof, 0.92))); P.append(('edge', 'r', up, shade(roof, 0.6)))
    return P, sum(q[1] for q in fp) / 4
def apse(M, s, t0, t1, ht, wall, roof):
    c = M(s, (t0 + t1) / 2); e = M(min(1, s + 0.1), (t0 + t1) / 2)
    ax, ay = e[0] - c[0], e[1] - c[1]; La = math.hypot(ax, ay) or 1; ax, ay = ax / La, ay / La
    w0, w1 = M(s, t0), M(s, t1); r = math.hypot(w1[0] - w0[0], w1[1] - w0[1]) / 2
    nx, ny = (w1[0] - w0[0]) / (2 * r or 1), (w1[1] - w0[1]) / (2 * r or 1)
    pts = [(c[0] + ax * r * math.sin(a) - nx * r * math.cos(a), c[1] + ay * r * math.sin(a) - ny * r * math.cos(a)) for a in [i * math.pi / 8 for i in range(9)]]
    P = []
    for i in range(8):
        a, b = pts[i], pts[i + 1]; vx, vy = _ny(a, b, c)
        if vy > 0.02: P.append(('fill', 'w', [a, b, (b[0], b[1] - ht), (a[0], a[1] - ht)], shade(wall, 0.8 + 0.18 * (0.5 - 0.5 * vx))))
    top = [(x, y - ht) for x, y in pts]
    P.append(('fill', 'r', top + [(c[0], c[1] - ht)], shade(roof, 0.95))); P.append(('line', 'r', top, shade(roof, 0.6)))
    return P, c[1]
def atrium(M, s0, s1, t0, t1, wall, roof):
    fp = box(M, s0, s1, t0, t1); P = [('fill', 'g', fp, (214, 204, 182)), ('edge', 'g', fp, shade(wall, 0.7))]
    inn = box(M, s0 + (s1 - s0) * 0.18, s1 - (s1 - s0) * 0.18, t0 + (t1 - t0) * 0.18, t1 - (t1 - t0) * 0.18)
    for k in range(4):   # columns around the court
        for j in range(4):
            x, y = _lerp(inn[k], inn[(k + 1) % 4], j / 4)
            P.append(('fill', 'w', [(x - .25, y), (x + .25, y), (x + .25, y - 2.2), (x - .25, y - 2.2)], shade(wall, 1.02)))
    c = _lerp(inn[0], inn[2], .5)
    P.append(('fill', 'g', [(c[0] - .8, c[1] - .4), (c[0] + .8, c[1] - .4), (c[0] + .8, c[1] + .4), (c[0] - .8, c[1] + .4)], (110, 150, 168)))   # fountain basin
    return P, sum(q[1] for q in fp) / 4 - 3

def build_church(h, sp, b, E):
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof'])
    st = sp['stages']; y1 = b + 2 + st[1]['from']; y2 = b + 2 + st[2]['from']
    out = []
    def add(R, comps):
        for P, key in sorted(comps, key=lambda c: c[1]): out.extend(tag(P, R))
    if y1 < E: add((b + 2, min(y1, E)), [hall(M, .62, .95, .28, .72, 3.6, wall, roof, hid, 1.4)])
    else: add((b + 2, E), [hall(M, .62, .95, .28, .72, 3.6, wall, roof, hid, 1.4)]); return out
    if y2 < E: add((y1, y2), [hall(M, .38, .95, .22, .78, 4.6, wall, roof, hid, 1.9), atrium(M, .06, .34, .22, .78, wall, roof)])
    else: add((y1, E), [hall(M, .38, .95, .22, .78, 4.6, wall, roof, hid, 1.9), atrium(M, .06, .34, .22, .78, wall, roof)]); return out
    add((y2, E), [atrium(M, .02, .28, .12, .88, wall, roof),
                  lean(M, .3, .88, .1, .9, 4.0, wall, roof, hid),
                  hall(M, .3, .88, .3, .7, 6.0, shade(wall, 1.03), roof, hid, 2.2),
                  apse(M, .88, .32, .68, 4.6, wall, roof)])
    return out
def build_steps(h, sp, b, E):
    hid = h[0]; p = h[4]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]; front = h[10] if len(h) > 10 else 2
    pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); acc = tuple(pal['accent'])
    R = (b + 2, E); out = []
    n = sp['footprint'].get('treads', 5)
    for k in range(n):   # treads climbing from the street to the store
        q = split(pts, front, 0.04 + 0.4 * k / n, 0.04 + 0.4 * (k + 1) / n, 0.92); z = 0.35 * (k + 1)
        out.append(('fill', 'w', [q[0], q[1], (q[1][0], q[1][1] - z), (q[0][0], q[0][1] - z)], shade(acc, 0.74)))
        out.append(('fill', 'w', [(x, y - z) for x, y in q], shade(acc, 1.0 if k % 2 else 0.93)))
    top = split(pts, front, 0.4, 0.44, 0.92); z = 0.35 * n
    for j in range(5):   # loaves set out on the top step
        x, y = _lerp(_lerp(top[0], top[1], .15 + .17 * j), _lerp(top[3], top[2], .15 + .17 * j), .5)
        out.append(('fill', 'w', [(x - .45, y - z - .1), (x + .45, y - z - .1), (x + .45, y - z - .7), (x - .45, y - z - .7)], (176, 122, 64)))
    store = split(pts, front, 0.44, 1.0, 0.92); P = []
    walls(P, store, 4.4, wall, hid, 0, door=True)
    gable(P, [(x, y - 4.4) for x, y in store], roof, wall, 1.8)
    out.extend(tag(P, R))
    return out
BUILD = {'basilica': build_church, 'steps': build_steps}
def spec_of(h): return SPECS[h[9][3:]]
def geom(h, b, E):
    sp = spec_of(h)
    return BUILD[sp['footprint']['shape']](h, sp, b, E)
def height(sp): return {'basilica': 8.4, 'steps': 6.4}[sp['footprint']['shape']]
