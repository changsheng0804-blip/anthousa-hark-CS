"""CS 线 · cs29：取自上游 tanxinhao 线 tools/house_types.py（v24/v25，所有者点名取用）。南港加了码头货栈 dock、仓场 horrea 两种街区：长屋 hall。
House system (房屋体系) phase 1: one geometry source for every house.
Types: row (连排铺面), domus (院宅), insula (公寓楼), yard (作坊院), casa (民居小屋), std (新街坊标准屋), hut (菜园小屋), hall (兵营长屋).
streets_xero.py picks the type per lot (pick_type) and wants its height (TYPE_H); render_xero.py draws geom();
export() writes houses_geom.json, which the page draws as is. Change looks here only."""
import math

def hsh(n, k=0):
    x = (n * 2654435761 + k * 40503) & 0xffffffff
    x ^= x >> 15; x = (x * 2246822519) & 0xffffffff; x ^= x >> 13
    return x / 4294967296
def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
LX, LY = -0.6, -0.8   # light from the north-west

PAL = {  # district -> walls, roofs
    'market': ([(236, 222, 192), (228, 206, 166)], [(198, 104, 58), (206, 118, 64), (188, 96, 56)]),
    'shops': ([(234, 220, 190), (224, 204, 168)], [(192, 100, 60), (180, 92, 56)]),
    'fine': ([(246, 241, 230), (240, 233, 218)], [(204, 114, 66), (194, 106, 62)]),
    'workshop': ([(196, 162, 116), (184, 150, 106), (204, 172, 128)], [(142, 86, 58), (128, 90, 66), (150, 100, 70)]),
    'water': ([(216, 222, 220), (226, 228, 222)], [(176, 98, 66), (166, 92, 64)]),
    'garrison': ([(198, 196, 188), (186, 184, 178)], [(150, 92, 72), (140, 96, 80)]),
    'planned': ([(228, 214, 188)], [(184, 94, 58)]),
    'garden': ([(206, 182, 140), (196, 172, 132)], [(166, 120, 70), (150, 110, 66)]),
    'dock': ([(222, 210, 184), (212, 198, 170), (230, 220, 198)], [(170, 92, 60), (160, 88, 58), (182, 100, 64)]),
    'horrea': ([(232, 222, 200), (224, 212, 188)], [(184, 100, 62), (176, 94, 58)]),
    'homes': ([(228, 212, 182), (216, 194, 156), (238, 228, 206), (204, 176, 136), (224, 204, 172), (210, 200, 184)],
              [(186, 94, 60), (172, 86, 54), (198, 112, 70), (160, 80, 52), (180, 102, 66), (150, 96, 72)]),
}
TYPE_H = {'flat': 4, 'row': 7, 'insula': 11, 'domus': 5.5, 'yard': 3.6, 'casa': 4.6, 'std': 5, 'hut': 3, 'hall': 4.6}

def pick_type(f, rank, area, on_main, hid):
    r = hsh(hid, 31)
    if f == 'market': return 'insula' if rank and r < .4 else 'row'
    if f == 'shops': return ('insula' if r < .25 else 'casa') if rank else ('row' if r < .75 else 'casa')
    if f == 'fine': return 'domus' if area >= 230 else 'casa'
    if f == 'workshop': return 'yard' if (not rank and r < .75) else 'casa'
    if f == 'planned': return 'std'
    if f == 'garden': return 'hut'
    if f == 'garrison': return 'hall' if r < .6 else 'casa'
    if f in ('dock', 'horrea'): return 'hall' if r < .85 else 'flat'
    if on_main and not rank: return 'row'
    return 'insula' if (rank and r < .04) else 'casa'
def type_height(typ, f, rank):
    h = TYPE_H[typ]
    if typ == 'row' and f != 'market': h = 6
    if typ == 'casa' and rank: h = 4
    return h

def row_stretch(fp):
    """row houses reach a little past their lot ends so neighbours' roofs overlap; more on the uphill (north) end,
    where the next house's roof has to cover this one's gable"""
    a0, a1 = fp[0], fp[1]; ex, ey = a1[0] - a0[0], a1[1] - a0[1]; L = math.hypot(ex, ey) or 1; ux, uy = ex / L, ey / L
    e0 = 0.9 if uy > 0 else 0.3   # end at fp[0]/fp[3] lies north when the edge runs southward
    e1 = 0.3 if uy > 0 else 0.9
    return [(fp[0][0] - ux * e0, fp[0][1] - uy * e0), (fp[1][0] + ux * e1, fp[1][1] + uy * e1), (fp[2][0] + ux * e1, fp[2][1] + uy * e1), (fp[3][0] - ux * e0, fp[3][1] - uy * e0)]
def has_garden(h):
    p = h[4]; typ = h[9] if len(h) > 9 else 'casa'
    if typ != 'casa': return False
    dep = math.hypot(p[6] - p[0], p[7] - p[1])
    return dep >= 11 and hsh(h[0], 51) < 0.5 and (h[8] if len(h) > 8 else 'homes') in ('homes', 'water', 'garden', 'garrison')
def split(pts, front, t0, t1, s=0.96):
    """part of the lot between depth t0 and t1 (0 = street edge, 1 = back), as a quad whose edge 0-1 faces the street"""
    cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    lot = [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in pts]; back = (front + 2) % 4
    fa, fb = lot[front], lot[(front + 1) % 4]; ba, bb = lot[(back + 1) % 4], lot[back]
    P = lambda t: [_lerp(fa, ba, t), _lerp(fb, bb, t)]
    q0, q1 = P(t0), P(t1)
    return [q0[0], q0[1], q1[1], q1[0]]
SPLIT = {'yard': (0.5, 1.0), 'hut': (0.0, 0.5), 'garden': (0.0, 0.62)}
def portico(h):
    """a colonnade in front of a row house: (strip on the ground, roof height, outward normal) or None"""
    if len(h) < 13 or not h[12]: return None
    p = h[4]; front = h[10]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]
    cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    a, b = pts[front], pts[(front + 1) % 4]
    ex, ey = b[0] - a[0], b[1] - a[1]; L = math.hypot(ex, ey) or 1; nx, ny = ey / L, -ex / L
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if nx * (mx - cx) + ny * (my - cy) < 0: nx, ny = -nx, -ny
    D = 2.4
    return [a, b, (b[0] + nx * D, b[1] + ny * D), (a[0] + nx * D, a[1] + ny * D)], 3.0, (nx, ny)
def footprint(h):
    """the drawn walls' footprint (what the street audit must keep off the roads)"""
    p = h[4]; typ = h[9] if len(h) > 9 else 'casa'; front = h[10] if len(h) > 10 else 2
    pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]; cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    if typ in ('row', 'std'):
        fp = [(cx + (x - cx) * 0.96, cy + (y - cy) * 0.96) for x, y in pts]
        return row_stretch(fp) if typ == 'row' else fp
    k = 'garden' if has_garden(h) else typ
    if k in SPLIT: return split(pts, front, *SPLIT[k])
    return [(cx + (x - cx) * 0.92, cy + (y - cy) * 0.92) for x, y in pts]
def roof_extra(h):
    """how far the roof rises above the wall top (same formulas as geom) - the street audit adds this to h[7]"""
    p = h[4]; typ = h[9] if len(h) > 9 else 'casa'; hid = h[0]
    fp = footprint(h)
    Lu = math.hypot(fp[1][0] - fp[0][0], fp[1][1] - fp[0][1]); Lv = math.hypot(fp[3][0] - fp[0][0], fp[3][1] - fp[0][1])
    if typ == 'row': return min(3.6, min(Lv / 2, 6.0) * 0.6)
    if typ in ('std', 'hall'): return min(Lv * 0.32, 4.5)
    if typ == 'casa': return min(Lu, Lv) * (0.32 if hsh(hid, 21) < 0.6 else 0.28)
    if typ == 'insula': return min(Lu, Lv) * 0.12
    if typ == 'hut': return min(Lu, Lv) * 0.34
    if typ == 'domus': return 1.6
    return 0.0
def _lerp(a, b, t): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
def _up(P, h): return [(x, y - h) for x, y in P]
def _ny(a, b, c):
    ex, ey = b[0] - a[0], b[1] - a[1]; L = math.hypot(ex, ey) or 1
    nx, ny = ey / L, -ex / L
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if nx * (mx - c[0]) + ny * (my - c[1]) < 0: nx, ny = -nx, -ny
    return nx, ny

def walls(parts, fp, ht, wall, hid, front, door=True, awn=None, windows=0):
    cx = sum(q[0] for q in fp) / 4; cy = sum(q[1] for q in fp) / 4
    for k in range(4):
        a, b = fp[k], fp[(k + 1) % 4]; nx, ny = _ny(a, b, (cx, cy))
        if ny <= 0.02 or ht < 0.6: continue
        parts.append(('fill', 'w', [a, b, (b[0], b[1] - ht), (a[0], a[1] - ht)], shade(wall, 0.80 + 0.18 * (0.5 - 0.5 * nx))))
        ex, ey = b[0] - a[0], b[1] - a[1]
        if windows:
            fl = max(1, int(ht // 3.1)); nw = max(1, int(math.hypot(ex, ey) // 4))
            for s in range(1, fl):
                yy = ht * s / fl + 1.2
                for wv in range(nw):
                    t0 = (wv + 0.35) / nw; t1 = t0 + 0.3 / nw
                    p0 = _lerp(a, b, t0); p1 = _lerp(a, b, t1)
                    parts.append(('fill', 'w', [(p0[0], p0[1] - yy), (p1[0], p1[1] - yy), (p1[0], p1[1] - yy + 1.1), (p0[0], p0[1] - yy + 1.1)], (88, 66, 50)))
        if door and k == front and ny > 0.3 and ht > 2:
            t0 = 0.35 + 0.3 * hsh(hid, 15); dw = min(0.2, 2.2 / (math.hypot(ex, ey) or 1)); dh = min(ht * 0.55, 3.2)
            d0 = _lerp(a, b, t0); d1 = _lerp(a, b, t0 + dw)
            parts.append(('fill', 'w', [d0, d1, (d1[0], d1[1] - dh), (d0[0], d0[1] - dh)], (70, 50, 36)))
        if awn and k == front and ny > 0.3:
            yy = min(ht * 0.62, 3.6)
            parts.append(('fill', 'w', [(a[0] + ex * .04, a[1] + ey * .04 - yy), (a[0] + ex * .96, a[1] + ey * .96 - yy),
                                        (a[0] + ex * .96 + nx * 1.7, a[1] + ey * .96 - yy + ny * 1.7 + .9), (a[0] + ex * .04 + nx * 1.7, a[1] + ey * .04 - yy + ny * 1.7 + .9)], awn))

def roof_faces(parts, faces, roof):
    for poly, (nx, ny) in sorted(faces, key=lambda f: sum(q[1] for q in f[0]) / len(f[0])):
        parts.append(('fill', 'r', poly, shade(roof, 0.86 - 0.22 * (nx * LX + ny * LY))))

def gable(parts, up, roof, wall, lift, front=None, dr=None):
    """ridge along edge 0-1 direction: two long slopes, gable ends in wall colour.
    With front/dr the ridge sits dr from the street edge, so a whole row shares one ridge line."""
    c = (sum(q[0] for q in up) / 4, sum(q[1] for q in up) / 4)
    if front is None or dr is None:
        r0 = _lerp(up[3], up[0], 0.5); r1 = _lerp(up[1], up[2], 0.5)
    else:
        D = math.hypot(up[3][0] - up[0][0], up[3][1] - up[0][1]) or 1; t = min(0.5, dr / D)
        if front == 2: r0 = _lerp(up[3], up[0], t); r1 = _lerp(up[2], up[1], t)
        else: r0 = _lerp(up[0], up[3], t); r1 = _lerp(up[1], up[2], t)
    r0 = (r0[0], r0[1] - lift); r1 = (r1[0], r1[1] - lift)
    faces = [([up[0], up[1], r1, r0], _ny(up[0], up[1], c)), ([up[2], up[3], r0, r1], _ny(up[2], up[3], c))]
    for (a, b, r) in ((up[1], up[2], r1), (up[3], up[0], r0)):
        nx, ny = _ny(a, b, c)
        if ny > 0.02: faces.append(([a, b, r], (nx, ny), ))
    for poly, (nx, ny) in sorted(faces, key=lambda f: sum(q[1] for q in f[0]) / len(f[0])):
        col = shade(wall, 0.9 - 0.12 * nx) if len(poly) == 3 else shade(roof, 0.86 - 0.22 * (nx * LX + ny * LY))
        parts.append(('fill', 'r', poly, col))
    parts.append(('line', 'r', [r0, r1], shade(roof, 0.68)))
    parts.append(('line', 'r', [up[0], up[1]], shade(roof, 0.6))); parts.append(('line', 'r', [up[2], up[3]], shade(roof, 0.6)))

def hip(parts, up, roof, lift_k=0.28):
    ux, uy = up[1][0] - up[0][0], up[1][1] - up[0][1]; vx, vy = up[3][0] - up[0][0], up[3][1] - up[0][1]
    Lu, Lv = math.hypot(ux, uy) or 1, math.hypot(vx, vy) or 1
    tx, ty = sum(q[0] for q in up) / 4, sum(q[1] for q in up) / 4
    if Lu >= Lv: a_ = (ux / Lu, uy / Lu); r = (Lu - Lv) / 2
    else: a_ = (vx / Lv, vy / Lv); r = (Lv - Lu) / 2
    lift = min(Lu, Lv) * lift_k
    r0 = (tx - a_[0] * r, ty - a_[1] * r - lift); r1 = (tx + a_[0] * r, ty + a_[1] * r - lift)
    d2 = lambda p, q: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
    faces = []
    for k in range(4):
        a, b = up[k], up[(k + 1) % 4]
        if r < 0.3: face = [a, b, r0]
        else:
            pa = r0 if d2(a, r0) <= d2(a, r1) else r1; pb = r0 if d2(b, r0) <= d2(b, r1) else r1
            face = [a, b, pb] if pa == pb else [a, b, pb, pa]
        faces.append((face, _ny(a, b, (tx, ty))))
    roof_faces(parts, faces, roof)
    parts.append(('edge', 'r', up, shade(roof, 0.62)))
    if r >= 0.3: parts.append(('line', 'r', [r0, r1], shade(roof, 0.7)))

def _portico(parts, po, roof, wall, hid, fn):
    strip, ph, (nx, ny) = po
    a, b, c, d = strip   # a-b on the house, d-c along the street
    L = math.hypot(c[0] - d[0], c[1] - d[1]); n = max(2, int(L / 2.6) + 1)
    if ny > 0.15 and fn == 'market':   # stalls under the colonnade
        for j in range(n - 1):
            if hsh(hid, 60 + j) < 0.5: continue
            q = _lerp(_lerp(d, c, (j + 0.5) / (n - 1)), _lerp(a, b, (j + 0.5) / (n - 1)), 0.45)
            col = [(182, 64, 48), (60, 96, 120), (196, 150, 60), (230, 222, 200)][int(hsh(hid, 70 + j) * 4)]
            parts.append(('fill', 'g', [(q[0] - .7, q[1] + .3), (q[0] + .7, q[1] + .3), (q[0] + .7, q[1] - 1), (q[0] - .7, q[1] - 1)], col))
    if ny > 0.02:   # columns on the street side
        for j in range(n):
            q = _lerp(d, c, j / (n - 1))
            parts.append(('fill', 'w', [(q[0] - .35, q[1]), (q[0] + .35, q[1]), (q[0] + .35, q[1] - ph), (q[0] - .35, q[1] - ph)], shade(wall, 1.02)))
    top = [(x, y - ph) for x, y in strip]
    parts.append(('fill', 'r', top, shade(roof, 1.08 if ny > 0 else 0.9)))
    parts.append(('line', 'r', [top[3], top[2]], shade(roof, 0.62)))
def geom(h):
    """h: [id, dd, b, e, poly8, fx, t, ht, fn, typ, front]. Returns (by, parts, shadow_pts)."""
    hid = h[0]; p = h[4]; pts = [(p[i], p[i + 1]) for i in range(0, 8, 2)]
    ht = h[7] if len(h) > 7 else 5; fn = h[8] if len(h) > 8 else 'homes'
    typ = h[9] if len(h) > 9 else 'casa'; front = h[10] if len(h) > 10 else 2
    WL, RF = PAL.get(fn, PAL['homes'])
    wall = WL[int(hsh(hid, 11) * len(WL))]; roof = RF[int(hsh(hid, 12) * len(RF))]
    si = h[11] if len(h) > 11 else -1
    if typ == 'std': wall, roof = PAL['planned'][0][0], PAL['planned'][1][0]
    elif typ == 'row' and si >= 0:   # a row is built as one: one roof colour along its street side
        roof = RF[int(hsh(si * 2 + front, 12) * len(RF))]; wall = WL[int(hsh(si * 2 + front, 11) * len(WL))]
    elif hsh(hid, 13) < 0.5: roof = shade(roof, 0.92 + 0.16 * hsh(hid, 14))
    cx = sum(q[0] for q in pts) / 4; cy = sum(q[1] for q in pts) / 4
    lot = [(cx + (x - cx) * 0.96, cy + (y - cy) * 0.96) for x, y in pts]
    parts = []
    # the building's own footprint inside the lot
    back = (front + 2) % 4   # edge opposite the street
    fp = footprint(h)
    gk = 'garden' if has_garden(h) else typ
    if gk == 'yard':
        rest = split(pts, front, 0.0, 0.5)
        parts.append(('fill', 'g', rest, (176, 152, 112))); parts.append(('edge', 'g', rest, (120, 92, 60)))
        for j in range(3):   # stacked jars and timber in the yard, a kiln in one corner
            q = _lerp(_lerp(rest[0], rest[1], 0.2 + 0.25 * j), _lerp(rest[3], rest[2], 0.2 + 0.25 * j), 0.5 + 0.2 * (hsh(hid, 40 + j) - .5))
            parts.append(('fill', 'g', [(q[0] - .8, q[1]), (q[0] + .8, q[1]), (q[0] + .8, q[1] - 1.4), (q[0] - .8, q[1] - 1.4)], (150, 92, 58)))
        if hsh(hid, 19) < 0.6:
            k = _lerp(rest[1], rest[2], 0.5); k = (k[0] * 0.8 + cx * 0.2, k[1] * 0.8 + cy * 0.2)
            parts.append(('fill', 'g', [(k[0] - 1.6, k[1]), (k[0] - 1.1, k[1] - 2.2), (k[0] + 1.1, k[1] - 2.2), (k[0] + 1.6, k[1])], (92, 68, 52)))
    elif gk in ('hut', 'garden'):
        rest = split(pts, front, 0.5 if gk == 'hut' else 0.64, 1.0)
        G = [(128, 150, 76), (140, 156, 82), (118, 140, 70)][int(hsh(hid, 52) * 3)]
        parts.append(('fill', 'g', rest, G))
        n = 4 if gk == 'hut' else 3
        for j in range(1, n):
            a = _lerp(rest[0], rest[3], j / n); b = _lerp(rest[1], rest[2], j / n)
            parts.append(('line', 'g', [_lerp(a, b, .06), _lerp(a, b, .94)], shade(G, 0.78)))
        parts.append(('edge', 'g', rest, (150, 124, 86)))   # low fence / wattle
        if gk == 'garden' and hsh(hid, 53) < 0.4:   # a fig or olive tree at the back
            c = _lerp(_lerp(rest[2], rest[3], 0.3 + 0.4 * hsh(hid, 54)), _lerp(rest[1], rest[0], 0.5), 0.25); rr = 1.6
            parts.append(('fill', 'g', [(c[0] + rr * math.cos(t) + .8, c[1] + .9 + rr * .5 * math.sin(t)) for t in [i * math.pi / 4 for i in range(8)]], (110, 92, 60)))
            parts.append(('fill', 'g', [(c[0] + rr * math.cos(t), c[1] - 1.6 + rr * .85 * math.sin(t)) for t in [i * math.pi / 4 for i in range(8)]], (78, 108, 56)))
    if typ == 'domus':   # garden wall round the whole lot
        wl = [(cx + (x - cx) * 0.99, cy + (y - cy) * 0.99) for x, y in pts]
        parts.append(('fill', 'g', wl, (196, 184, 150))); parts.append(('edge', 'g', wl, shade(wall, 0.7)))
    po = portico(h)
    if po:
        parts.append(('fill', 'g', po[0], (206, 196, 176)))
        if po[2][1] < 0: _portico(parts, po, roof, wall, hid, fn)   # colonnade behind the house: drawn first
    fr_ = 0 if gk in ('yard', 'hut', 'garden') else front
    if gk in ('yard', 'hut', 'garden'): back = 2
    up = _up(fp, ht)
    fcx = sum(q[0] for q in fp) / 4; fcy = sum(q[1] for q in fp) / 4
    shadow = fp + [(x + ht * 0.55 + 1, y + ht * 0.3 + 1) for x, y in fp]
    awn = None
    if typ == 'row' and (fn == 'market' or hsh(hid, 18) < 0.55):
        AW = [(182, 64, 48), (60, 96, 120), (196, 150, 60), (90, 120, 70)]
        awn = AW[int(hsh(hid, 16) * len(AW))]
    walls(parts, fp, ht, wall, hid, fr_, awn=awn, windows=(typ == 'insula'))
    Lu = math.hypot(up[1][0] - up[0][0], up[1][1] - up[0][1]); Lv = math.hypot(up[3][0] - up[0][0], up[3][1] - up[0][1])
    if typ == 'row':
        dr = min(Lv / 2, 6.0); gable(parts, up, roof, wall, min(3.6, dr * 0.6), front, dr)
    elif typ in ('std', 'hall'):
        gable(parts, up, roof, wall, min(Lv * 0.32, 4.5))
    elif typ == 'casa':
        if hsh(hid, 21) < 0.6: gable(parts, up, roof, wall, min(Lv, Lu) * 0.32) if Lu >= Lv else gable(parts, [up[1], up[2], up[3], up[0]], roof, wall, min(Lv, Lu) * 0.32)
        else: hip(parts, up, roof)
    elif typ == 'insula':
        hip(parts, up, roof, 0.12)
    elif typ == 'flat':
        # flat terrace roof: plaster with a darker parapet and a little roof hatch
        parts.append(('fill', 'r', up, shade(wall, 0.9))); parts.append(('edge', 'r', up, shade(wall, 0.6)))
        inn = [(fcx + (x - fcx) * 0.8, fcy - ht + (y - fcy) * 0.8) for x, y in fp]
        parts.append(('edge', 'r', inn, shade(wall, 0.78)))
        q = _lerp(inn[0], inn[2], 0.3); parts.append(('fill', 'r', [(q[0] - .7, q[1] - .4), (q[0] + .7, q[1] - .4), (q[0] + .7, q[1] + .5), (q[0] - .7, q[1] + .5)], (96, 78, 60)))
    elif typ == 'yard':   # lean shed: one slope down toward the yard
        hi = [up[(back) % 4], up[(back + 1) % 4]]
        parts.append(('fill', 'r', up, shade(roof, 0.95))); parts.append(('edge', 'r', up, shade(roof, 0.62)))
        parts.append(('line', 'r', hi, shade(roof, 0.55)))
    elif typ == 'hut':
        hip(parts, up, roof, 0.34)
    elif typ == 'domus':
        # roof ring around an open court; slopes fall inward, the court is a garden with a tree
        tx, ty = sum(q[0] for q in up) / 4, sum(q[1] for q in up) / 4
        inner = [(tx + (x - tx) * 0.5, ty + (y - ty) * 0.5) for x, y in up]
        lift = 1.6
        outer = [(x, y - lift) for x, y in up]
        faces = []
        for k in range(4):
            faces.append(([outer[k], outer[(k + 1) % 4], inner[(k + 1) % 4], inner[k]], _ny(outer[k], outer[(k + 1) % 4], (tx, ty))))
        # outer walls rise a little to the roof edge
        for k in range(4):
            a, b = up[k], up[(k + 1) % 4]; nx, ny = _ny(a, b, (tx, ty))
            if ny > 0.02: parts.append(('fill', 'w', [a, b, outer[(k + 1) % 4], outer[k]], shade(wall, 0.84)))
        # the court floor, seen through the opening
        court = [(x, y + ht * 0.25) for x, y in [(tx + (x - tx) * 0.42, ty + (y - ty) * 0.42) for x, y in up]]
        parts.append(('fill', 'r', inner, shade(wall, 0.62)))
        parts.append(('fill', 'r', court, (150, 168, 96)))
        c = (sum(q[0] for q in court) / 4, sum(q[1] for q in court) / 4); rr = max(1.2, min(Lu, Lv) * 0.12)
        parts.append(('fill', 'r', [(c[0] + rr * math.cos(a), c[1] - 1 + rr * 0.85 * math.sin(a)) for a in [i * math.pi / 4 for i in range(8)]], (72, 104, 54)))
        for poly, (nx, ny) in faces:
            parts.append(('fill', 'r', poly, shade(roof, 0.92 - 0.2 * (-nx * LX - ny * LY))))
        parts.append(('edge', 'r', outer, shade(roof, 0.6))); parts.append(('edge', 'r', inner, shade(roof, 0.55)))
    if po and po[2][1] >= 0: _portico(parts, po, roof, wall, hid, fn)
    by = max(q[1] for q in pts)
    if po: by = max(by, max(q[1] for q in po[0]))
    return by, parts, shadow

def export(HS, path):
    import json
    pal = {}; out = {}
    def ci(c):
        k = '%d,%d,%d' % c
        if k not in pal: pal[k] = len(pal)
        return pal[k]
    KC = {'fill': 0, 'edge': 1, 'line': 2}; LC = {'g': 0, 'w': 1, 'r': 2}
    for h in HS:
        by, parts, sh = geom(h)
        P = []
        for kind, lay, poly, col in parts:
            P.append([KC[kind], LC[lay], ci(col)] + [round(v, 1) for q in poly for v in q])
        out[h[0]] = [round(by, 1), [round(v, 1) for q in sh for v in q], P]
    json.dump(dict(pal=['rgb(%s)' % k for k in pal], H=out), open(path, 'w'), separators=(',', ':'))
