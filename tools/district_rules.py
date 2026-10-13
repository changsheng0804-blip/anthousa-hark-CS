"""Shared district (街区) rules: what a block becomes, and how its lots are cut.
Used by streets_xero.py (lot cutting from the full street network) and blocks_xero.py (labels per year)."""
import math, json

X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
W, H = 1820, 2048
_city = json.load(open(X + 'city.json')); LM = {l['id']: l for l in _city['landmarks']}
_late = json.load(open(X + 'houses_v12.json'))['late']
AQ = [(760, 0), (1820, 515)]
def wall_x(y): return 587 - 0.2357 * y
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
def _inter(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9: return None
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    if 0 <= t <= 1 and 0 <= u <= 1: return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
R = [r['pts'] for r in _city['roads']]
MJ = []  # main-road crossings: where markets gather
for i in range(len(R)):
    for j in range(i + 1, len(R)):
        for a, b in zip(R[i][:-1], R[i][1:]):
            for c, d in zip(R[j][:-1], R[j][1:]):
                q = _inter(a, b, c, d)
                if q and 0 < q[0] < W and 0 < q[1] < H: MJ.append(q)
FIRE = _late['fire_ruins']['p']
CIST = {k: v for k, v in _late.items() if k.startswith('cistern')}
import landmark_registry as LR_
INF = LR_.influences()
def cen(p): return (sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p))

FN = {  # code: (label, overlay colour)
    'market': ('市集', (214, 120, 40)), 'shops': ('铺面', (226, 170, 60)), 'water': ('汲水坊', (70, 140, 200)),
    'garrison': ('兵营坊', (120, 120, 130)), 'workshop': ('作坊', (150, 96, 60)), 'fine': ('体面人家', (170, 90, 160)),
    'planned': ('新街坊', (90, 150, 110)), 'garden': ('菜园', (110, 160, 70)), 'homes': ('民居', (200, 180, 140))}

def classify(cx, cy, area, front, density, Y=None):
    """front: share of the block's edge on a main road; density: houses per px² (None = unknown).
    Y=None: the district's character from the full network (all cisterns, fire ground)."""
    for k, z in CIST.items():
        if Y is None or z['built'] <= Y:
            zx, zy = cen(z['p'])
            if math.hypot(cx - zx, cy - zy) < 130: return 'water'
    if (Y is None or Y >= 48) and pip(cx, cy, FIRE): return 'planned'
    if front >= 0.22:
        if front >= 0.3 and any(math.hypot(cx - x, cy - y) < 170 for x, y in MJ): return 'market'
        return 'shops'
    wall_done = False
    for q in INF:   # landmark pulls from the registry (barracks -> garrison, gate/aqueduct -> workshop, baths -> fine)
        o, fn, kind, g, r = q[:5]
        if o == 0: continue
        if o >= 2 and not wall_done:
            wall_done = True
            if cx - wall_x(cy) < 75: return 'workshop'
        if kind == 'pt' and math.hypot(cx - g[0], cy - g[1]) < r: return fn
        if kind == 'line' and segd(cx, cy, *g) < r: return fn
    if not wall_done and cx - wall_x(cy) < 75: return 'workshop'
    if density is not None and area > 5000 and density * 2600 < 1: return 'garden'
    return 'homes'

# how lots are cut along a street in each district: (width range, depth range, gap range, shop share, rear row)
# market: narrow deep shopfronts wall to wall; fine: wide lots with room for a court, no back row;
# workshop: middling lots with a working yard behind (no back row); planned: one standard lot, evenly spaced;
# garden: small cottages far apart among the plots.
LOTS = {
    'market':   dict(wid=(6.5, 8.5), dep=(16, 20), gap=(0.0, 0.25), shop=1.0, rear=True),
    'shops':    dict(wid=(8, 10.5), dep=(14, 17), gap=(0.2, 0.6), shop=0.8, rear=True),
    'fine':     dict(wid=(19, 24), dep=(17, 21), gap=(3, 6), shop=0.0, rear=False),
    'workshop': dict(wid=(12, 15), dep=(10, 13), gap=(2.5, 4.5), shop=0.15, rear=False),
    'planned':  dict(wid=(12, 12), dep=(12, 12), gap=(1.5, 1.5), shop=0.1, rear=True),
    'garden':   dict(wid=(9, 11), dep=(8, 10), gap=(9, 16), shop=0.0, rear=False),
}
