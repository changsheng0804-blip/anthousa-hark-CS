"""Place landmarks from gen/landmarks/*.json specs onto lots (run in living/<quarter>/ after streets_xero + audit fixpo).
A chosen lot becomes h[9] = 'lm:<id>', h[7] = landmark height; must pass the strict road audit or the next candidate is tried."""
import json, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import house_types as HT, landmark_shapes as LS
import audit_streets as A   # loads houses.json / streets.json of the cwd
HD = A.HD; HS = HD['houses']; S = A.S
def area(h):
    p = h[4]; return abs(sum(p[2 * i] * p[(2 * i + 3) % 8] - p[(2 * i + 2) % 8] * p[2 * i + 1] for i in range(4))) / 2
def ctr(h): p = h[4]; return ((p[0] + p[2] + p[4] + p[6]) / 4, (p[1] + p[3] + p[5] + p[7]) / 4)
def front_mid(h):
    p = h[4]; f = h[10] if len(h) > 10 else 2; a = (p[2 * f], p[2 * f + 1]); b = (p[(2 * f + 2) % 8], p[(2 * f + 3) % 8])
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
def street_kind_at(x, y, kinds, Y):
    best = 1e9
    for s in S:
        if s[5] in kinds and s[6] <= Y and not (s[7] and s[7] <= Y): best = min(best, A.sd(x, y, s) - s[4] / 2)
    return best
def ok_strict(h):
    b, e = h[2], h[3]; B = A.body(h); cx = sum(q[0] for q in B[:4]) / 4; cy = sum(q[1] for q in B[:4]) / 4
    sub = [s for s in S if abs((s[0] + s[2]) / 2 - cx) < 140 and abs((s[1] + s[3]) / 2 - cy) < 140
           and (s[8] if len(s) > 8 else s[6]) < e and not (len(s) > 7 and s[7] and s[7] <= b)]
    return not (sub and A.bodyhit(h, sub, A.grid_of(sub)))
for h in HS:   # reset any earlier placement (landmark lots and the neighbours they absorbed)
    if len(h) > 13 and h[13] == 'merged': h[3] = h[14]; del h[13:]
    elif isinstance(h[9], str) and h[9].startswith('lm:'):
        h[9], h[7] = h[13], h[14]
        if len(h) > 15: h[4] = h[15]
        del h[13:]
BYID = {h[0]: h for h in HS}
PROTECT = set(int(k) for k in json.load(open('stories.json')))
for sc in json.load(open('scenes.json')):
    for c in sc.get('cast', []):
        if len(c) > 3 and c[3]: PROTECT.add(c[3])
def pts_of(h): p = h[4]; return [(p[i], p[i + 1]) for i in range(0, 8, 2)]
GRID = {}
for h in HS:
    c = ctr(h); GRID.setdefault((int(c[0] // 40), int(c[1] // 40)), []).append(h)
def merge_options(h):
    """neighbour lots sharing a side edge with h (not the street side): (neighbour, merged poly8)"""
    P = pts_of(h); f = h[10] if len(h) > 10 else 2; c = ctr(h); out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for n in GRID.get((int(c[0] // 40) + dx, int(c[1] // 40) + dy), []):
                if n is h or n[0] in PROTECT or len(n) < 13 or n[3] < 900 or (n[12] & 1) or str(n[9]).startswith('lm:') or len(n) > 13: continue
                Q = pts_of(n)
                for k in range(4):
                    if k == f: continue
                    a, b = P[k], P[(k + 1) % 4]
                    ia = [i for i in range(4) if math.hypot(Q[i][0] - a[0], Q[i][1] - a[1]) < 1.6]
                    ib = [i for i in range(4) if math.hypot(Q[i][0] - b[0], Q[i][1] - b[1]) < 1.6]
                    if not ia or not ib: continue
                    ia, ib = ia[0], ib[0]
                    if (ia - ib) % 4 not in (1, 3): continue
                    d = 1 if (ia - ib) % 4 == 3 else -1   # walk away from the shared edge
                    fa = Q[(ia - d) % 4]; fb = Q[(ib + d) % 4]
                    R = list(P); R[k] = fa; R[(k + 1) % 4] = fb
                    out.append((n, [v for q in R for v in q]))
    return out
placed = {}
for sid, sp in LS.SPECS.items():
    if sp.get('instances', {}).get('rule') == 'fixed' or 'siting' not in sp: continue   # historic fixed landmarks: landmark_registry
    si = sp['siting']; lo, hi = si['lot']; e0 = sp['era'][0]; nmax = sp['instances']['count'][1]
    gap = si.get('gap', 300 if sp['size'] == 'small' else 420)
    C = []
    for h in HS:
        if len(h) < 13 or h[3] < 900 or h[2] < e0 or not ((lo if sp['size'] == 'small' else lo * 0.45) <= area(h) <= hi) or h[12] & 1 or h[0] in PROTECT: continue
        # generic siting from the spec: block function, lot type, street kind in front, latest build year
        if h[8] not in si['fn'] or h[9] not in si['typ'] or h[2] > si.get('built_by', 40): continue
        if si.get('front_on'):
            fx, fy = front_mid(h)
            if street_kind_at(fx, fy, si['front_on'], h[2] + 2) > si.get('front_dist', 6): continue
        pf = si.get('prefer_fn', [])
        rank = pf.index(h[8]) if h[8] in pf else len(pf)
        score = (rank, -area(h) * (0.6 + 0.4 * HT.hsh(h[0], 301)) if si.get('prefer') == 'large' else HT.hsh(h[0], 300))
        C.append((score, h))
    C.sort(key=lambda c: c[0]); got = []
    for _, h in C:
        if len(got) >= nmax: break
        c = ctr(h)
        if any(math.hypot(c[0] - g[0], c[1] - g[1]) < gap for g in got) or any(math.hypot(c[0] - g[0], c[1] - g[1]) < 120 for g in placed.values()): continue
        old9, old7, old4 = h[9], h[7], h[4]
        opts = [(None, old4)]
        if sp['size'] != 'small' and area(h) < lo: opts = [o for o in merge_options(h)]
        elif sp['size'] != 'small': opts += merge_options(h)
        for nb, poly in opts:
            h[4] = poly
            if area(h) < lo or area(h) > hi * 1.6: continue
            h += [old9, old7, old4]; h[9] = 'lm:' + sid; h[7] = LS.height(sp)
            if ok_strict(h):
                if nb is not None:   # the parish buys the plot next door; that house comes down when the church starts (or is never built)
                    nb += ['merged', nb[3]]; nb[3] = max(nb[2], h[2])
                got.append(c); placed[h[0]] = c
                print(sid, h[0], 'built', h[2], 'area', int(area(h)), h[8], [int(v) for v in c], 'merged', nb[0] if nb else '-')
                break
            h[9], h[7] = old9, old7; del h[13:]
        else:
            h[4] = old4; continue
        if h[4] != old4 and len(h) <= 13: h[4] = old4
json.dump(HD, open('houses.json', 'w'), separators=(',', ':'))
print('landmarks placed', len(placed))
