#!/usr/bin/env python3
"""创城者城墙让房（派生表）。底账里房子都离 wall_founder 至少 1 个世界单位（≥14 px），是派生街网（streets_ng 按街重排）把 39 栋挪到了墙线上/墙边。
城墙在瓦片里画成 20 px 宽（epic_stage wall_rows，半宽 9 px），这里把压墙的房子沿墙的法线推回它在底账里所在的那一侧，推到刚好离墙带 1 px，
且不压别的房子、不压街；推 30 px 还放不下的，标「不建」（h[3]=h[2]）。底账 world.json 一字不动。
  · houses_street.json（各街区）：被推的房 h[13:]=['wall', 原四角, 原拆毁年]，幂等：先撤上一次再重做；
  · vec：同一行按同样位移平移（不必整套重烤），之后 zsort。
  python3 tools/cs/factory/wall_clear.py
——Hark（CS线）"""
import json, os, glob, math, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
from shapely.geometry import LineString, Polygon, Point
from shapely.strtree import STRtree
LIV = os.path.join(ROOT, 'docs', 'living'); T = os.path.join(LIV, 'tiles'); M = json.load(open(os.path.join(T, 'meta.json'))); S = M['scale']; X0, Y0 = M['origin']
W = json.load(open(os.path.join(ROOT, 'world.json'))); ST = {s['id']: s for s in W['structures']}; WH = {h['id']: h for h in W['houses']}
WALL = ST['wall_founder']; WB = WALL['built']; WE = WALL['destroyed'] if WALL['destroyed'] is not None else 9999
def wp(x, y): return ((x - X0) * S, (y - Y0) * S)
LN = LineString([wp(*c) for c in WALL['geom']['coords']]); BAND = LN.buffer(10, cap_style=2)
(ax, ay), (bx, by) = LN.coords[0], LN.coords[-1]; L = math.hypot(bx - ax, by - ay); NX, NY = (by - ay) / L, -(bx - ax) / L
def side(x, y): return 1 if (x - ax) * NX + (y - ay) * NY >= 0 else -1
QS = M['owner_order']
REST = {}
# 1) 先撤 houses_street 里上一次的记号（vec 不用撤：它总是由上一次结果平移来，再跑一遍时已经让开，不会再动）
for q in QS:
    p = os.path.join(LIV, q, 'houses_street.json'); D = json.load(open(p)); n = 0
    for h in D['houses']:
        if len(h) > 13 and h[13] == 'wall': h[4] = h[14]; h[3] = h[15]; del h[13:]; n += 1; REST['h%d' % h[0]] = h[3]
    if n: json.dump(D, open(p, 'w'), separators=(',', ':'))
# 2) vec 也撤上一次（按 wall_cleared.json 平移回去、恢复拆毁年），再在 vec 里找压墙的房
WC = os.path.join(T, 'wall_cleared.json'); OLD = json.load(open(WC)) if os.path.exists(WC) else {'moved': {}, 'unbuilt': {}}
if isinstance(OLD.get('unbuilt'), list): OLD['unbuilt'] = {k: REST.get(k, 9999) for k in OLD['unbuilt']}
V = {}; rows = []
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    v = json.load(open(f)); V[f] = v
    for h in v['h']:
        k = str(h[5])
        if k in OLD['moved']:
            dx, dy = -OLD['moved'][k][0], -OLD['moved'][k][1]
            h[3] = [round(c + (dx if i % 2 == 0 else dy), 1) for i, c in enumerate(h[3])]
            for p in h[4]: p[1] = [round(c + (dx if i % 2 == 0 else dy), 1) for i, c in enumerate(p[1])]
            h[2] = round(h[2] + dy, 1)
        if k in OLD['unbuilt']: h[1] = OLD['unbuilt'][k]
    for h in v['h']:
        if str(h[5]).startswith('epic:') or len(h[3]) < 8: continue
        rows.append((f, h, Polygon(list(zip(h[3][0:8:2], h[3][1:8:2]))).buffer(0)))
# 各街区自己的 streets.json（街区本地像素 + 街区左上角偏移）也算：check_roads 按街区查，同一栋房在别的街区副本旁的街也不许压
QOFF = {q: (M['quarters'][q][0], M['quarters'][q][1]) for q in QS}
QSEG = []
for q in QS:
    ox, oy = QOFF[q]
    for s_ in json.load(open(os.path.join(LIV, q, 'streets.json'))): QSEG.append([s_[0] + ox, s_[1] + oy, s_[2] + ox, s_[3] + oy] + list(s_[4:]))
ALLS = [s_ for v in V.values() for s_ in v['s']] + QSEG
segs = [LineString([(s_[0], s_[1]), (s_[2], s_[3])]).buffer(max(1.0, s_[4] / 2) + 0.5, cap_style=2) for s_ in ALLS]
SEG = list(zip(segs, ALLS))
segtree = STRtree([g for g, _ in SEG]); feet = [r[2] for r in rows]; foottree = STRtree(feet)
def clash(P, me, b, e):
    for i in foottree.query(P):
        f, h, F = rows[i]
        if h is me or not (h[0] < e and b < h[1]): continue
        if F.intersection(P).area > 0.5: return True
    for i in segtree.query(P):
        g, s_ = SEG[i]
        if g.intersection(P).area > 0.05: return True
    return False
# 街区里的房轮廓（houses_street，比 vec 的脚印宽一点）：每个副本平移后也不许压街、不许压墙带
QPOLY = {}
for q in QS:
    ox, oy = QOFF[q]
    for h in json.load(open(os.path.join(LIV, q, 'houses_street.json')))['houses']:
        QPOLY.setdefault('h%d' % h[0], []).append(Polygon([(h[4][i] + ox, h[4][i + 1] + oy) for i in range(0, 8, 2)]).buffer(0))
def street_hit(P):
    return any(SEG[i][0].intersection(P).area > 0.05 for i in segtree.query(P))
moved = {}; unbuilt = {}
for f, h, F in rows:
    if not (h[0] < WE and h[1] > WB) or h[1] <= h[0] or F.intersection(BAND).area <= 0.5: continue
    lh = WH.get(str(h[5])); c = Polygon([wp(x, y) for x, y in lh['p']]).centroid if lh else F.centroid
    sg = side(c.x, c.y); best = None
    for d in range(1, 31):
        dx, dy = NX * sg * d, NY * sg * d; P = Polygon([(x + dx, y + dy) for x, y in F.exterior.coords])
        cps = [Polygon([(x + dx, y + dy) for x, y in C.exterior.coords]) for C in QPOLY.get(str(h[5]), [])]
        if P.intersection(BAND).area <= 0.5 and not clash(P, h, max(h[0], WB), h[1]) and not any(C.intersection(BAND).area > 0.5 or street_hit(C) for C in cps): best = (dx, dy); break
    if best is None: unbuilt[h[5]] = h[1]; h[1] = max(h[0], WB); continue
    dx, dy = best
    h[3] = [round(v + (dx if i % 2 == 0 else dy), 1) for i, v in enumerate(h[3])]
    for p in h[4]: p[1] = [round(v + (dx if i % 2 == 0 else dy), 1) for i, v in enumerate(p[1])]
    h[2] = round(h[2] + dy, 1); moved[h[5]] = (dx, dy)
    rows_i = [i for i, r in enumerate(rows) if r[1] is h][0]; feet[rows_i] = Polygon(list(zip(h[3][0:8:2], h[3][1:8:2])))
# 3) 写回 vec（行留在原瓦片：位移 ≤30 px，页面按瓦片取行，不影响画）
for f, v in V.items(): open(f, 'w').write(json.dumps(v, separators=(',', ':')))
subprocess.run([sys.executable, os.path.join(HERE, 'zsort.py'), os.path.join(T, 'vec')], check=True)
# 4) 记进 houses_street（各街区同 id 的那一行同样平移，下次整套重烤一致）
nq = 0
for q in QS:
    p = os.path.join(LIV, q, 'houses_street.json'); D = json.load(open(p)); ch = False
    for h in D['houses']:
        k = 'h%d' % h[0]
        if k in moved and len(h) <= 13:
            dx, dy = moved[k]; h += ['wall', list(h[4]), h[3]]; h[4] = [round(v + (dx if i % 2 == 0 else dy), 1) for i, v in enumerate(h[4])]; ch = True; nq += 1
        elif k in unbuilt and len(h) <= 13: h += ['wall', list(h[4]), h[3]]; h[3] = max(h[2], WB); ch = True; nq += 1
    if ch: json.dump(D, open(p, 'w'), separators=(',', ':'))
json.dump({'moved': {k: [round(a, 1), round(b, 1)] for k, (a, b) in moved.items()}, 'unbuilt': unbuilt, 'src': 'tools/cs/factory/wall_clear.py'}, open(os.path.join(T, 'wall_cleared.json'), 'w'), ensure_ascii=False, indent=0)
print('推开', len(moved), '不建', len(unbuilt), '街区行', nq)
