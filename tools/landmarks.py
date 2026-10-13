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
for h in HS:   # reset any earlier placement
    if isinstance(h[9], str) and h[9].startswith('lm:'): h[9], h[7] = h[13], h[14]; del h[13:]
placed = {}
for sid, sp in LS.SPECS.items():
    si = sp['siting']; lo, hi = si['lot']; e0 = sp['era'][0]; n = sp['instances']['count'][1]
    gap = 300 if sp['size'] == 'small' else 420
    C = []
    for h in HS:
        if len(h) < 13 or h[3] < 900 or h[2] < e0 or h[2] > 40 or not (lo <= area(h) <= hi) or h[12] & 1: continue
        if sid == 'bread_steps':
            if h[8] not in ('market', 'shops') or h[9] not in ('row', 'flat', 'casa'): continue
            fx, fy = front_mid(h)
            if street_kind_at(fx, fy, 'm', h[2] + 2) > 6: continue
            score = (0 if h[8] == 'market' else 1, HT.hsh(h[0], 300))
        else:
            if h[8] not in ('homes', 'fine', 'water', 'garden', 'planned', 'shops') or h[9] not in ('casa', 'domus', 'yard', 'std', 'hall', 'insula'): continue
            score = (-area(h) * (0.6 + 0.4 * HT.hsh(h[0], 301)), 0)
        C.append((score, h))
    C.sort(key=lambda c: c[0]); got = []
    for _, h in C:
        if len(got) >= n: break
        c = ctr(h)
        if any(math.hypot(c[0] - g[0], c[1] - g[1]) < gap for g in got) or any(math.hypot(c[0] - g[0], c[1] - g[1]) < 120 for g in placed.values()): continue
        old9, old7 = h[9], h[7]
        h += [old9, old7]; h[9] = 'lm:' + sid; h[7] = LS.height(sp)
        if ok_strict(h): got.append(c); placed[h[0]] = c; print(sid, h[0], 'built', h[2], 'area', int(area(h)), h[8], [int(v) for v in c])
        else: h[9], h[7] = old9, old7; del h[13:]
json.dump(HD, open('houses.json', 'w'), separators=(',', ':'))
print('landmarks placed', len(placed))
