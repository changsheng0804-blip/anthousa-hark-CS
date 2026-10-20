import json, math, sys, os, random
sys.path.insert(0, os.path.dirname(__file__))
from graph import StreetGraph, plen, live

Q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Y = int(sys.argv[2]) if len(sys.argv) > 2 else 60
NR = int(sys.argv[3]) if len(sys.argv) > 3 else 700
ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
D = json.load(open(os.path.join(ROOT, 'docs/living/nodes', Q, 'nodes_net.json')))
W, H = D['W'], D['H']; MPP = D['elev']['mpp']
G = StreetGraph(D, Y); F = D['features']
inframe = lambda x, y: 6 < x < W - 6 and 6 < y < H - 6
rng = random.Random(f'{Q}-{Y}-crowd')          # 只用来「抽哪几户当样本」，同一底账永远抽到同样的户

houses = [f for f in F if f['t'] == 'house' and live(f, Y)]
def poly(h): p = h['p']; return list(zip(p[::2], p[1::2]))
def door(h):
    P = poly(h); i = h.get('fr', 0) % len(P); a, b = P[i], P[(i + 1) % len(P)]
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); n = G.nearest(*m, rad=24)
    return (m, n[1]) if n and n[0] < 8 else None
fount = [(f['x'], f['y']) for f in F if f['t'] == 'fountain' and live(f, Y) and inframe(f['x'], f['y'])]
piers = []
for f in F:
    if f['t'] == 'pier' and live(f, Y):
        a, b = f['g']
        for e in (a, b):
            n = G.nearest(*e, rad=30)
            if n and n[0] < 12 and inframe(*e): piers.append(n[1]); break
markets = [h for h in houses if h.get('fn') == 'market']
lms = [f for f in F if f['t'] == 'landmark' and live(f, Y)]
def lm_pt(f):
    g = f['g']; best = None
    for p in g:
        if not inframe(*p): continue
        n = G.nearest(*p, rad=60)
        if n and (best is None or n[0] < best[0]): best = (n[0], n[1])
    return best and best[1]
forum = [lm_pt(f) for f in lms if f['k'] == 'forum']; forum = [p for p in forum if p]
granary = [lm_pt(f) for f in lms if f['k'] == 'granary']; granary = [p for p in granary if p]

def nearest(pt, L): return min(L, key=lambda q: math.dist(pt, q)) if L else None
def rdp(P, eps=.8):
    if len(P) < 3: return P
    a, b = P[0], P[-1]; dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1
    i, dm = 0, -1
    for k in range(1, len(P) - 1):
        d = abs(dy * (P[k][0] - a[0]) - dx * (P[k][1] - a[1])) / L
        if d > dm: i, dm = k, d
    if dm <= eps: return [a, b]
    return rdp(P[:i + 1], eps)[:-1] + rdp(P[i:], eps)

# 用途 → 去处 → 意图（意图决定步态分布和手里的东西）。全部来自底账字段。
def plan_for(h, s):
    fn, ty = h.get('fn'), h.get('ty')
    rich = h.get('po') or (h.get('ht') or 0) >= 14
    harbour = nearest(s, piers); dh = math.dist(s, harbour) if harbour else 1e9
    if fn == 'shops' and rich and forum: return 'forum', nearest(s, forum), 'rich'
    if fn in ('shops', 'market'):
        m = [door(x) for x in rng.sample(markets, min(12, len(markets)))]; m = [d[1] for d in m if d]
        return 'market', nearest(s, m) if m else harbour, 'trader'
    if fn in ('dock', 'horrea') or (fn == 'homes' and dh < 260 and h['id'] % 3 == 0):
        dst = nearest(s, granary) if granary and h['id'] % 2 else harbour
        return 'haul', dst, 'laborer'
    if fn == 'homes':
        f = nearest(s, fount)
        if f and h['id'] % 2 == 0 and math.dist(s, f) < 220: return 'water', f, 'woman'
        m = [door(x) for x in rng.sample(markets, min(8, len(markets)))]; m = [d[1] for d in m if d]
        return 'errand', nearest(s, m) if m else f, 'commoner'
    return None

