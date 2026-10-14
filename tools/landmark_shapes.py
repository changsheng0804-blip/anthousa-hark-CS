"""Shared shape vocabulary for landmarks (open typology). A landmark house has h[9] = 'lm:<spec id>';
house_types._geom_full hands it here. Every part carries its own year range so a spec's stages grow the building.
Shapes: steps, rect, atrium, basilica (nave + aisles + apse + atrium), fountain, granary, inn, macellum (tholos), kiln, cemetery. Add new primitives here; new types are JSON specs."""
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
def build_fountain(h, sp, b, E):
    """nymphaeum: a curved back wall (exedra) with niches, a long basin in front, water spouts"""
    hid = h[0]; p = h[4]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]; front = h[10] if len(h) > 10 else 2
    pal = sp['palette']; wall = tuple(pal['wall']); acc = tuple(pal['accent']); R = (b + 2, E); out = []
    pave = split(pts, front, 0.0, 1.0, 0.92); out.append(('fill', 'g', pave, (208, 200, 186)))
    basin = split(pts, front, 0.18, 0.5, 0.78)
    out.append(('fill', 'w', [basin[0], basin[1], (basin[1][0], basin[1][1] - .8), (basin[0][0], basin[0][1] - .8)], shade(wall, .8)))
    out.append(('fill', 'w', [(x, y - .8) for x, y in basin], acc)); out.append(('edge', 'w', [(x, y - .8) for x, y in basin], shade(wall, .95)))
    back = split(pts, front, 0.55, 0.95, 0.86)
    a, c = back[3], back[2]; m = _lerp(back[0], back[1], .5); mid = _lerp(a, c, .5)
    dx, dy = m[0] - mid[0], m[1] - mid[1]
    arc = [_lerp(a, c, i / 8) for i in range(9)]
    arc = [(x + dx * 0.5 * math.sin(math.pi * i / 8), y + dy * 0.5 * math.sin(math.pi * i / 8)) for i, (x, y) in enumerate(arc)]
    ht = 4.6
    for i in range(8):   # exedra wall, inner face toward the street
        q0, q1 = arc[i], arc[i + 1]
        out.append(('fill', 'w', [q0, q1, (q1[0], q1[1] - ht), (q0[0], q0[1] - ht)], shade(wall, 0.84 + 0.12 * math.sin(math.pi * (i + .5) / 8))))
        if i % 2 == 1:
            n0 = _lerp(q0, q1, .3); n1 = _lerp(q0, q1, .7)
            out.append(('fill', 'w', [(n0[0], n0[1] - 1.6), (n1[0], n1[1] - 1.6), (n1[0], n1[1] - 3.6), (n0[0], n0[1] - 3.6)], shade(wall, 0.62)))
    out.append(('line', 'w', [(x, y - ht) for x, y in arc], shade(wall, 0.6)))
    for j in range(3):   # spouts
        q = arc[2 + 2 * j]; t = _lerp(q, _lerp(basin[2], basin[3], .2 + .3 * j), .5)
        out.append(('line', 'w', [(q[0], q[1] - 2.2), (t[0], t[1] - .9)], (150, 196, 214)))
    return [o if len(o) > 4 else o + (R,) for o in out]
def build_granary(h, sp, b, E):
    """horrea: long low hall, buttresses along the walls, small high vents; first half, then lengthened"""
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); acc = tuple(pal['accent'])
    y1 = b + 2 + sp['stages'][1]['from']; out = []
    def gran(s1, R):
        P, _ = hall(M, .04, s1, .14, .86, 4.2, wall, roof, hid, 1.6)
        fp = box(M, .04, s1, .14, .86); bays = sp['footprint'].get('bays', 6)
        for k in (0, 2):
            a, c = fp[k], fp[(k + 1) % 4]; nx, ny = _ny(a, c, _lerp(fp[0], fp[2], .5))
            if ny <= .02: continue
            for j in range(1, bays):
                x, y = _lerp(a, c, j / bays)
                P.append(('fill', 'w', [(x - .35, y + ny * .8), (x + .35, y + ny * .8), (x + .35, y - 3.6), (x - .35, y - 3.6)], shade(wall, .7)))
                v = _lerp(a, c, (j - .5) / bays); P.append(('fill', 'w', [(v[0] - .5, v[1] - 3.4), (v[0] + .5, v[1] - 3.4), (v[0] + .5, v[1] - 2.8), (v[0] - .5, v[1] - 2.8)], (70, 54, 40)))
        out.extend(tag(P, R))
    if y1 < E: gran(.55, (b + 2, y1)); gran(.96, (y1, E))
    else: gran(.55, (b + 2, E))
    return out
def build_inn(h, sp, b, E):
    """pandocheion: rooms around a yard, a stable lean-to along one side, a gate to the street"""
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); R = (b + 2, E)
    comps = [((([('fill', 'g', box(M, .06, .94, .08, .92), (178, 156, 118))]), 0))]
    comps.append(hall(M, .06, .94, .08, .3, 4.8, wall, roof, hid, 1.8))         # rooms on one side
    comps.append(hall(M, .06, .94, .7, .92, 4.8, wall, roof, hid, 1.8))         # rooms on the other
    comps.append(hall(M, .06, .26, .3, .7, 4.8, wall, roof, hid, 1.8))          # hall at the west end
    comps.append(lean(M, .74, .94, .3, .7, 2.8, shade(wall, .9), shade(roof, .85), hid))   # stable
    out = []
    g = comps.pop(0)[0]; out.extend(tag(g, R))
    for P, key in sorted(comps, key=lambda c: c[1]): out.extend(tag(P, R))
    for j in range(3):   # a cart and bales in the yard
        x, y = M(.4 + .12 * j, .5 + .08 * (j - 1))
        out.append(('fill', 'g', [(x - .9, y - .3), (x + .9, y - .3), (x + .9, y + .5), (x - .9, y + .5)], (190, 160, 90) if j else (120, 84, 56), R))
    return out

def ring(c, rx, ry, n=16): return [(c[0] + rx * math.cos(2 * math.pi * i / n), c[1] + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
def drum(c, rx, ht, wall, roof, cone=0.0, top=None):
    """round building seen from above-south: front-facing wall strips, then a cone / flat roof"""
    ry = rx * 0.62; base = ring(c, rx, ry); P = []
    for i in range(16):
        a, b = base[i], base[(i + 1) % 16]
        if (a[1] + b[1]) / 2 >= c[1] - ry * 0.2:   # the half facing the viewer
            k = 0.78 + 0.2 * (0.5 - 0.5 * math.cos(2 * math.pi * (i + .5) / 16 + 0.9))
            P.append(('fill', 'w', [a, b, (b[0], b[1] - ht), (a[0], a[1] - ht)], shade(wall, k)))
    up = [(x, y - ht) for x, y in base]
    if cone:
        apex = (c[0], c[1] - ht - cone)
        for i in range(16):
            a, b = up[i], up[(i + 1) % 16]
            k = 0.8 + 0.22 * (0.5 - 0.5 * math.cos(2 * math.pi * (i + .5) / 16 + 0.9))
            P.append(('fill', 'r', [a, b, apex], shade(roof, k)))
    else:
        P.append(('fill', 'r', up, top or shade(roof, 0.95)))
    P.append(('line', 'r', up + [up[0]], shade(roof, 0.6)))
    return P, c[1]

def build_macellum(h, sp, b, E):
    """macellum: a paved square ringed by shop rows, a round tholos for the fish and meat sellers in the middle.
    Stage 0: open square with awning stalls; later the shop rows and the tholos."""
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); acc = tuple(pal['accent'])
    y1 = b + 2 + sp['stages'][1]['from']; out = []
    pave = [('fill', 'g', box(M, .04, .96, .06, .94), (206, 194, 170)), ('edge', 'g', box(M, .04, .96, .06, .94), shade(wall, .7))]
    out.extend(tag(pave, (b + 2, E)))
    if y1 > b + 2:   # first years: awnings over trestle stalls
        R = (b + 2, min(y1, E))
        for i in range(3):
            for j in range(3):
                s0 = .14 + .27 * i; t0 = .16 + .26 * j
                q = box(M, s0, s0 + .16, t0, t0 + .14)
                out.append(('fill', 'w', [q[2], q[3], (q[3][0], q[3][1] - 1.6), (q[2][0], q[2][1] - 1.6)], shade(acc, .7), R))
                cl = (196, 160, 96) if (i + j) % 2 else (176, 86, 60)
                out.append(('fill', 'r', [(x, y - 1.8) for x, y in q], cl, R))
    if y1 < E:
        R = (y1, E); comps = []
        comps.append(lean(M, .04, .96, .06, .24, 3.6, wall, roof, hid))     # shops along the north side
        comps.append(lean(M, .04, .2, .24, .94, 3.6, wall, roof, hid))      # west side
        comps.append(lean(M, .8, .96, .24, .94, 3.6, wall, roof, hid))      # east side
        Ls = math.dist(M(0, .5), M(1, .5)); Lt = math.dist(M(.5, 0), M(.5, 1)); rx = 0.2 * min(Ls, Lt)
        comps.append(drum(M(.5, .6), rx, 3.4, shade(wall, 1.05), roof, cone=3.2))   # tholos
        for P, key in sorted(comps, key=lambda c: c[1]): out.extend(tag(P, R))
        c = M(.5, .6)   # columns of the tholos porch
        for i in range(8):
            a = math.pi * (0.1 + 0.8 * i / 7)
            x, y = c[0] + rx * 1.28 * math.cos(a), c[1] + rx * 1.28 * 0.62 * math.sin(a)
            out.append(('fill', 'w', [(x - .3, y), (x + .3, y), (x + .3, y - 3.4), (x - .3, y - 3.4)], shade(wall, 1.08), R))
    return out

def build_kiln(h, sp, b, E):
    """brick and pot kilns: round domed kilns with a dark fire mouth, a drying shed, stacks of bricks; a second kiln later"""
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); acc = tuple(pal['accent'])
    y1 = b + 2 + sp['stages'][1]['from']; R0 = (b + 2, E); out = []
    out.extend(tag([('fill', 'g', box(M, .04, .96, .08, .92), (170, 140, 104))], R0))
    def kiln(s, t, R):
        Ls = math.dist(M(0, .5), M(1, .5)); Lt = math.dist(M(.5, 0), M(.5, 1)); rk = min(6.2, 0.16 * min(Ls * 1.6, Lt))
        c = M(s, t); P, _ = drum(c, rk, 3.0, wall, shade(wall, .82), top=shade(wall, .7))
        P.append(('fill', 'r', ring((c[0], c[1] - 3.0), 2.2, 1.4, 10), (60, 44, 36)))     # open top / flue
        P.append(('fill', 'w', [(c[0] - 1.1, c[1] + 3.8), (c[0] + 1.1, c[1] + 3.8), (c[0] + 1.1, c[1] + 2.0), (c[0] - 1.1, c[1] + 2.0)], (40, 26, 20)))   # fire mouth
        out.extend(tag(P, R))
    kiln(.3, .45, R0)
    if y1 < E: kiln(.56, .5, (y1, E))
    P, _ = lean(M, .74, .96, .14, .86, 2.6, shade(wall, .95), roof, hid); out.extend(tag(P, R0))   # drying shed
    for j in range(4):   # stacks of fired bricks
        x, y = M(.12 + .14 * j, .82)
        for k in range(3):
            out.append(('fill', 'w', [(x - 1.2, y - .5 * k), (x + 1.2, y - .5 * k), (x + 1.2, y - .5 * (k + 1)), (x - 1.2, y - .5 * (k + 1))], shade(acc, .85 + .08 * (k % 2)), R0))
    return out

def build_cemetery(h, sp, b, E):
    """burial ground outside the walls: a low enclosure, rows of stelae that fill in year by year, a small tomb house, cypresses"""
    hid = h[0]; M, _ = frame_of(h); pal = sp['palette']; wall = tuple(pal['wall']); roof = tuple(pal['roof']); acc = tuple(pal['accent'])
    R0 = (b + 2, E); out = []
    fp = box(M, .03, .97, .05, .95)
    out.append(('fill', 'g', fp, (150, 150, 104), R0)); out.append(('edge', 'g', fp, shade(wall, .6), R0))
    for k in range(4):   # low enclosure wall, front-facing sides only
        a, c = fp[k], fp[(k + 1) % 4]; nx, ny = _ny(a, c, _lerp(fp[0], fp[2], .5))
        if ny > .02: out.append(('fill', 'w', [a, c, (c[0], c[1] - .9), (a[0], a[1] - .9)], shade(wall, .8 + .15 * ny), R0))
    P, _ = hall(M, .72, .92, .14, .4, 3.2, wall, roof, hid, 1.4); out.extend(tag(P, R0))   # family tomb house
    n = 0; span = max(4, min(E, 9999) - b - 4) if E < 9999 else 60
    for row in range(5):
        for i in range(9):
            if row < 2 and i > 5: continue   # leave room for the tomb house
            s = .08 + .085 * i; t = .2 + .15 * row
            x, y = M(s, t); y0 = b + 2 + int(span * HT.hsh(hid * 31 + n, 77) * 0.9)   # each grave its own year
            out.append(('fill', 'w', [(x - .35, y), (x + .35, y), (x + .35, y - 1.3), (x - .35, y - 1.3)], shade(acc, .9 + .1 * HT.hsh(n, 78)), (y0, E)))
            n += 1
    for (s, t) in ((.06, .1), (.5, .12), (.62, .9), (.95, .7)):   # cypresses
        x, y = M(s, t)
        out.append(('fill', 'w', [(x, y - 7.5), (x + 1.2, y - 3.5), (x + .8, y), (x - .8, y), (x - 1.2, y - 3.5)], (52, 78, 50), R0))
    return out
BUILD = {'basilica': build_church, 'steps': build_steps, 'fountain': build_fountain, 'granary': build_granary, 'inn': build_inn,
         'macellum': build_macellum, 'kiln': build_kiln, 'cemetery': build_cemetery}
def spec_of(h): return SPECS[h[9][3:]]
def geom(h, b, E):
    sp = spec_of(h)
    return BUILD[sp['footprint']['shape']](h, sp, b, E)
def height(sp): return {'basilica': 8.4, 'steps': 6.4, 'fountain': 5.0, 'granary': 6.0, 'inn': 6.8, 'macellum': 6.6, 'kiln': 4.0, 'cemetery': 4.0}[sp['footprint']['shape']]
