#!/usr/bin/env python3
"""/goal 4 G4 史诗分期画法：谭线 render_xero.py 的 epic_ground / epic_tall / mese_portico 搬进瓦片画法（来源：谭线 handoff-cs 19b633d）。
不画栅格：每处史诗是一批「带年份段的部件」，以伪房子行的形式进 vec（页面零代码；行的 id = 'epic:<史诗 id>[:k]'，h[5]）。
  · 狄奥多西广场 forum_theodosius（世界账本 built 57）：57–58 年工地（碎石、石堆）→ 59 起铺面、柱廊、雕像、铜牛、布棚；
    狄奥多西柱 57 起每年立一节（8 节，64 年落成、立像、脚手架拆除）；60 起凯旋门。
  · 大宁芙泉 nymphaeum_maius（built 44，账本「完工」年）：44 起池、半圆壁龛柱廊；水面从 net_water 的出水年起（之前干池）。
  · 梅塞柱廊 r_mese（built 1）：1–2 年立架（石板路面 + 立柱），3 起瓦顶落成；沿梅塞每 ~64 px 一行；
    梅塞在派生城里路宽 15 px、房子贴到 ~10 px，柱廊收窄到 7.6–10.2 px（谭线原图是 30 px 宽的路），让开房子、支路口断开、进广场前停下。
年份全读 world.json（built），tools 里不自编。输出 tiles/epic_stage.json（rows + 每处史诗的 built/finish 年），tile_bake 读它写进 vec。
  python3 tools/cs/factory/epic_stage.py
——Hark（CS线）"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, substring
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles')
M = json.load(open(os.path.join(OUT, 'meta.json'))); S = M['scale']; X0, Y0 = M['origin']; QS = M['owner_order']
W = json.load(open(os.path.join(ROOT, 'world.json'))); ST = {s['id']: s for s in W['structures']}
INF = 9999
def wp(x, y): return ((x - X0) * S, (y - Y0) * S)
def poly_px(e): return Polygon([wp(*c) for c in ST[e]['geom']['coords']])
FORUM = poly_px('forum_theodosius'); NYMPH = poly_px('nymphaeum_maius')
FOUNDER = poly_px('forum_founder')
MESE = LineString([wp(*c) for c in ST['r_mese']['geom']['coords']])
B_FORUM, B_NYMPH, B_MESE = ST['forum_theodosius']['built'], ST['nymphaeum_maius']['built'], ST['r_mese']['built']
NW = {n['id']: n for n in json.load(open(os.path.join(OUT, 'net_water.json')))['nodes']}
WET_NYMPH = NW['nymphaeum_maius']['wet']
MARBLE = (236, 230, 216); TILE = (186, 108, 72); TILE_D = (138, 74, 48)
FORUM_SITE = 2; MESE_SITE = 2; COLUMN_COURSES = 8; ARCH_Y = 60   # 工地年数、柱节数、凯旋门年（谭线：AF57 起、AF64 落成、AF60 凯旋门）
def hx(c): return '%02x%02x%02x' % tuple(c)
def hsh(n, k=0):
    x = (n * 2654435761 + k * 40503) & 0xffffffff; x ^= x >> 15; x = (x * 2246822519) & 0xffffffff; x ^= x >> 13
    return x / 2 ** 32
class Row:
    def __init__(s, id, built, foot, key=None):
        s.id = id; s.built = built; s.parts = []; s.foot = foot; s.key = key
    def fill(s, pts, col, y0, y1=INF):
        pts = list(pts); 
        if len(pts) >= 3: s.parts.append((0, pts, col, y0, y1))
    def edge(s, pts, col, y0, y1=INF):
        if len(pts) >= 3: s.parts.append((1, list(pts), col, y0, y1))
    def line(s, pts, col, y0, y1=INF): s.parts.append((2, list(pts), col, y0, y1))
    def rect(s, x0, y0_, x1, y1_, col, ya, yb=INF): s.fill([(x0, y0_), (x1, y0_), (x1, y1_), (x0, y1_)], col, ya, yb)
    def ell(s, cx, cy, rx, ry, col, ya, yb=INF, n=8): s.fill([(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)], col, ya, yb)
    def polys(s, g, col, ecol, ya, yb=INF):
        for pg in polys(g):
            c = list(pg.simplify(0.15).exterior.coords)[:-1]
            if len(c) >= 3: s.fill(c, col, ya, yb); s.edge(c, ecol, ya, yb) if ecol else None
    def out(s):
        sh = [c for xy in s.foot for c in xy] + [c for xy in s.foot for c in (xy[0] + 1.4, xy[1] + 1.6)]
        ay = max(xy[1] for xy in s.foot)
        P = [[k, [round(v * 2) / 2 for xy in p for v in xy], hx(c), y0, y1] for k, p, c, y0, y1 in s.parts]
        return {'id': s.id, 'built': s.built, 'end': INF, 'by': round(ay * 2) / 2, 'shadow': [round(v * 2) / 2 for v in sh], 'parts': P}
def polys(g):
    if g.is_empty: return []
    return [g] if g.geom_type == 'Polygon' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']
def quad(pg): c = list(pg.minimum_rotated_rectangle.exterior.coords)[:4]; return c
def ring_band(poly, d0, d1): return poly.buffer(-d0, join_style=2).difference(poly.buffer(-d1, join_style=2))

def mese_y_at(x):   # 梅塞穿广场处的 y
    return MESE.interpolate(MESE.project(Point(x, (FORUM.bounds[1] + FORUM.bounds[3]) / 2))).y

COLR = [None]
def forum_rows():
    rows = []; x0, y0, x1, y1 = FORUM.bounds; ex = FORUM.exterior.coords; my_ = mese_y_at((x0 + x1) / 2)
    mz = MESE.buffer(9, cap_style=2)
    R = Row('epic:forum_theodosius', B_FORUM, quad(FORUM)); a, f = B_FORUM, B_FORUM + FORUM_SITE   # a=开工(账本 built)；f=铺面落成
    # 工地：整片清空的碎石地 + 石堆
    R.fill(list(ex)[:-1], (170, 150, 118), a, f)
    for i in range(14): R.ell(x0 + 8 + hsh(i, 1) * (x1 - x0 - 16), y0 + 8 + hsh(i, 2) * (y1 - y0 - 16), 3, 2, (206, 198, 180), a, f, 6)
    # 落成：铺面、石缝、梅塞磨出的旧路、内线
    R.fill(list(ex)[:-1], (214, 204, 184), f)
    inn = FORUM.buffer(-10, join_style=2); ix0, iy0, ix1, iy1 = inn.bounds
    for k in range(1, int((iy1 - iy0) // 4)): R.line([(ix0, iy0 + k * 4), (ix1, iy0 + k * 4)], (190, 180, 158), f)
    R.rect(ix0, my_ - 7, ix1, my_ + 7, (205, 195, 175), f)
    R.line([(ix0, my_ - 7), (ix1, my_ - 7)], (176, 164, 142), f); R.line([(ix0, my_ + 7), (ix1, my_ + 7)], (176, 164, 142), f)
    R.edge(list(inn.exterior.coords)[:-1], (170, 156, 132), f)
    # 雕像（基座 + 像）与铜牛（Forum Tauri）
    for i, (fx, fy) in enumerate(((0.2, 0.3), (0.8, 0.3), (0.2, 0.84), (0.8, 0.84), (0.36, 0.3), (0.64, 0.3))):
        sx, sy = x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)
        R.rect(sx - 2, sy - 1.5, sx + 2, sy + 1.5, (190, 180, 160), f); R.rect(sx - 2, sy - 3, sx + 2, sy - 1.5, (214, 206, 188), f); R.ell(sx, sy - 5.5, 1, 2.6, (120, 104, 70), f, INF, 6)
    bx, by = x0 + 0.5 * (x1 - x0), y0 + 0.78 * (y1 - y0)
    R.rect(bx - 6, by - 2.5, bx + 6, by + 2.5, (196, 186, 166), f); R.rect(bx - 6, by - 4, bx + 6, by - 2.5, (218, 210, 192), f)
    R.ell(bx - 0.5, by - 6, 4, 2, (92, 74, 46), f, INF, 8); R.ell(bx + 4, by - 7.5, 1.5, 1.5, (92, 74, 46), f, INF, 6)
    for lx in (-3.5, -1.5, 1.2, 3): R.rect(bx + lx - 0.4, by - 4.8, bx + lx + 0.4, by - 3.6, (92, 74, 46), f)
    # 柱廊下的布棚
    for i in range(10):
        side = i % 2; t = 0.12 + 0.76 * hsh(i, 21); ax = ix0 + t * (ix1 - ix0); ay = (iy0 + 2) if side == 0 else (iy1 - 6)
        if abs(ay - my_) < 10: continue
        R.rect(ax, ay, ax + 7, ay + 4, [(196, 74, 52), (214, 184, 120), (110, 132, 160), (226, 222, 210)][i % 4], f)
    # 四面柱廊（梅塞穿过处断开）
    band = ring_band(FORUM, 0, 9).difference(mz)
    R.polys(band, TILE, TILE_D, f)
    rid = FORUM.buffer(-4.5, join_style=2).exterior.intersection(band)
    for seg in ([rid] if rid.geom_type == 'LineString' else getattr(rid, 'geoms', [])):
        if seg.geom_type == 'LineString': R.line(list(seg.coords), TILE_D, f)
    inr = FORUM.buffer(-9.4, join_style=2).exterior; bb = band.buffer(0.8)
    for i in range(int(inr.length // 3.6)):
        pt = inr.interpolate(i * 3.6)
        if bb.contains(pt): R.rect(pt.x - 0.9, pt.y - 0.9, pt.x + 0.9, pt.y + 0.9, MARBLE, f)
    rows.append(R)
    # 狄奥多西柱：每年立一节，64 年（courses 节）落成立像、脚手架拆除
    C = R; COL0 = len(R.parts)   # 柱的部件接在广场行末尾（同一行内按部件次序画，柱压在铺面和北面柱廊之上；分行的话拓扑排序会把铺面排到柱前面）
    cx, cy = (x0 + x1) / 2, y0 + 26; n = COLUMN_COURSES; dz = 52.0 / n; top = 9 + 52; done = B_FORUM + n - 1
    C.fill([(cx + 3, cy + 3), (cx + 30, cy + 14), (cx + 32, cy + 10), (cx + 5, cy - 1)], (203, 195, 188), a)   # 长影
    C.rect(cx - 5, cy - 5, cx + 5, cy + 5, (196, 188, 170), a); C.rect(cx - 5, cy + 5 - 9, cx + 5, cy + 5, (206, 198, 182), a)
    C.rect(cx - 5, cy - 9 - 5, cx + 5, cy - 9 + 5, MARBLE, a)
    for k in range(n):   # 第 k 节：账本 built+k 年起
        yk = B_FORUM + k; zb, zt = 9 + k * dz, 9 + (k + 1) * dz
        C.rect(cx - 3.2, cy - zt, cx + 3.2, cy - zb, MARBLE, yk); C.rect(cx + 1.0, cy - zt, cx + 3.2, cy - zb, (196, 188, 170), yk)
        z = zb
        while z < zt - 0.5: C.line([(cx - 3.2, cy - z), (cx + 3.2, cy - z - 2.4)], (160, 146, 120), yk); z += 3.0
        for sx in (-4, 4): C.line([(cx + sx, cy - zb), (cx + sx, cy - zt - 3)], (124, 92, 58), yk, done)   # 脚手架立杆
        zz = 11
        while zz <= zt + 2:
            if zz > zb + 2: C.line([(cx - 4, cy - zz), (cx + 4, cy - zz)], (124, 92, 58), yk, done)
            zz += 4
    d1 = done; C.rect(cx - 3.4, cy - top - 1.6, cx + 3.4, cy - top, MARBLE, d1)
    C.fill([(cx - 1.3, cy - top - 1.6), (cx + 1.3, cy - top - 1.6), (cx + 0.8, cy - top - 8), (cx - 0.8, cy - top - 8)], (176, 144, 70), d1); C.ell(cx, cy - top - 9, 1, 1, (176, 144, 70), d1, INF, 6)
    COLR[0] = (COL0, len(R.parts))
    # 凯旋门（梅塞入广场西口）
    A = Row('epic:forum_theodosius:arch', ARCH_Y, [(x0 - 5, my_ + 17), (x0 + 5, my_ + 17), (x0 + 5, my_ + 12), (x0 - 5, my_ + 12)])
    ax0, ax1, ay0, ay1, h = x0 - 5, x0 + 5, my_ - 17, my_ + 17, 18
    A.fill([(ax0 + 2, ay0 + 2), (ax1 + 6, ay0 + 2), (ax1 + 6, ay1 + 3), (ax0 + 2, ay1 + 3)], (203, 195, 188), ARCH_Y)
    A.rect(ax0, ay1 - h, ax1, ay1, (214, 206, 188), ARCH_Y); A.rect(ax0, ay0 - h, ax1, ay1 - h, MARBLE, ARCH_Y)
    for fr in (0.25, 0.5, 0.75): yy = ay0 + (ay1 - ay0) * fr - h; A.line([(ax0, yy), (ax1, yy)], (196, 186, 166), ARCH_Y)
    rows.append(A)
    return rows
def nymph_rows():
    c = NYMPH.centroid; x0, y0, x1, y1 = NYMPH.bounds; b = B_NYMPH; wet = WET_NYMPH
    R = Row('epic:nymphaeum_maius', b, quad(NYMPH))
    R.fill(list(NYMPH.buffer(5, join_style=2).exterior.coords)[:-1], (210, 200, 180), b); R.fill(list(NYMPH.exterior.coords)[:-1], (226, 218, 200), b)
    basin = box(x0 + 5, c.y - 1, x1 - 7, y1 - 6).intersection(NYMPH.buffer(-4, join_style=2))
    if not basin.is_empty:
        R.fill(list(basin.exterior.coords)[:-1], MARBLE, b); wat = list(basin.buffer(-2.2, join_style=2).exterior.coords)[:-1]
        if wet > b: R.fill(wat, (138, 130, 114), b, wet)   # 出水前干池（和街角喷泉同一规矩，读 net_water）
        R.fill(wat, (88, 150, 176), wet)
        for i in range(5): wx = x0 + 10 + i * (x1 - x0 - 20) / 4; R.rect(wx - 0.5, c.y + 4, wx + 0.5, c.y + 9, (214, 236, 244), wet)
    r = (x1 - x0) / 2 - 3; cx, cy = c.x, c.y; h = 16
    arc = [(cx + r * math.cos(a), cy + 0.55 * r * math.sin(a)) for a in [math.pi + i * math.pi / 24 for i in range(25)]]
    R.fill([(cx + r, cy), (cx + r + 5, cy + 3), (cx + r + 5, cy - 0.55 * r + 3)], (203, 195, 188), b)
    R.fill(arc + [(x, y - h) for x, y in arc[::-1]], (222, 210, 188), b)
    for i in range(1, 24, 3):
        x, y = arc[i]; R.rect(x - 1.2, y - 13, x + 1.2, y - 9, (150, 136, 112), b); R.rect(x - 1.2, y - 6, x + 1.2, y - 2, (150, 136, 112), b)
    for i in range(0, 25, 2):
        x, y = arc[i]
        for z0, z1 in ((0, 7.5), (8.5, 15.5)): R.rect(x - 0.7, y - z1, x + 0.7, y - z0, MARBLE, b)
    R.line([(x, y - 8) for x, y in arc], (170, 154, 130), b)
    dome = [(cx + r * 0.92 * math.cos(a), cy - 2 + 0.5 * r * math.sin(a)) for a in [math.pi + i * math.pi / 24 for i in range(25)]]
    R.fill([(x, y - h) for x, y in dome] + [(cx, cy - 2 - h - 7)], (150, 150, 146), b); R.line([(x, y - h) for x, y in arc], (120, 110, 96), b)
    return [R]
def street_data():
    """梅塞 15 px 路上的 'm' 街段（年份）、支路 'c'、房子脚印（让路用）。"""
    import house_types as HT
    mseg = []; cuts = []; hs = []; near = MESE.buffer(20)
    for q in QS:
        ox, oy = M['quarters'][q][:2]
        for st in json.load(open(os.path.join(LIV, q, 'streets.json'))):
            sg = LineString([(st[0] + ox, st[1] + oy), (st[2] + ox, st[3] + oy)])
            if not sg.intersects(near): continue
            if st[5] == 'm': mseg.append((sg, st[6]))
            elif sg.distance(MESE) < 17: cuts.append(sg.buffer(st[4] / 2 + 1.2, cap_style=2))
        for h in json.load(open(os.path.join(LIV, q, 'houses_street.json')))['houses']:
            if h[3] <= h[2] or len(h) > 13 and h[13] == 'epic' and h[3] <= h[2]: continue
            P = Polygon([(x + ox, y + oy) for x, y in HT.footprint(h)])
            if P.intersects(near): hs.append(P.buffer(0.3))
    return mseg, unary_union(cuts), unary_union(hs)
def mese_rows():
    mseg, cut, houses = street_data(); rows = []; L = MESE.length; CH = 64.0
    mz_all = unary_union([s for s, _ in mseg]).buffer(5) if mseg else None
    forum_cl = FORUM.buffer(1); fnd = FOUNDER.buffer(1)   # 梅塞穿过创城者广场（账本 1 年，椭圆）：柱廊/铺面在那里断开，路仍是原来的路
    for i in range(int(L // CH) + 1):
        sub = substring(MESE, i * CH, min(L, (i + 1) * CH))
        if sub.length < 8 or sub.geom_type != 'LineString': continue
        mid = sub.interpolate(0.5, normalized=True)
        if mz_all is None or not mz_all.contains(mid): continue
        # 梅塞街段的建成年（取附近最早的）；柱廊开工 = max(账本 1 年, 街段年)
        ys = [y for s, y in mseg if s.distance(mid) < 6]; y0 = max(B_MESE, min(ys)) if ys else B_MESE; f = y0 + MESE_SITE
        foot = quad(sub.buffer(1.2, cap_style=2))
        R = Row('epic:mese:%d' % i, y0, foot)
        pave = sub.buffer(7.4, cap_style=2).difference(fnd); pin = pave.intersection(forum_cl); pout = pave.difference(forum_cl)
        R.polys(pout, None, None, y0) if False else None
        for pg in polys(pout): R.fill(list(pg.simplify(0.15).exterior.coords)[:-1], (214, 204, 184), y0)
        for pg in polys(pin): R.fill(list(pg.simplify(0.15).exterior.coords)[:-1], (214, 204, 184), y0, B_FORUM)   # 进广场的一段：广场落成前是梅塞的路面
        band = sub.buffer(10.2, cap_style=2).difference(sub.buffer(7.6, cap_style=2)).difference(cut).difference(houses).difference(fnd)
        bin_ = band.intersection(forum_cl); bout = band.difference(forum_cl)
        R.polys(bout, TILE, TILE_D, f); R.polys(bin_, TILE, TILE_D, f, B_FORUM)
        # 立柱：街缘每 5 px 一根（立架年就有，瓦顶落成才盖）
        cols = unary_union([sub.parallel_offset(7.8, 'left'), sub.parallel_offset(7.8, 'right')])
        bb = band.buffer(0.6)
        for ln in ([cols] if cols.geom_type == 'LineString' else getattr(cols, 'geoms', [])):
            if ln.geom_type != 'LineString': continue
            for k in range(int(ln.length // 5)):
                pt = ln.interpolate(2.5 + k * 5)
                if not bb.contains(pt) or fnd.contains(pt): continue
                ye = B_FORUM if forum_cl.contains(pt) else INF
                R.rect(pt.x - 0.9, pt.y - 0.9, pt.x + 0.9, pt.y + 0.9, MARBLE, y0, ye)
        if R.parts: rows.append(R)
    return rows

# ── 帝国中心分期（谭线 2026-10-14 fbc65d4 写进底账 structures[].phases，inbox/TO_CS.md）──
# 规则：年份只读 phases；成品是栅格里的 AI 小图（landmarks.py），页面在关键年之间拿「下一个关键年」的栅格，
# 所以整座 done 之前用一块盖住脚印（放宽 8%，小图裁在 6%）的工地画面把小图挡住：site = 清场地 + 桩线 + 石堆；
# frame = 墙线 + 脚手架格；带 part 的 done = 那一部分先铺成屋顶。整座 done 起这批部件全部停画，栅格小图露出来。
# 斑岩柱 col_founder 底账是点，栅格里没有小图：整根柱子都由这里画（基座 → 鼓石逐年加高的影子 → 立像）。
PH_IDS = [s_['id'] for s_ in W['structures'] if s_.get('phases')]
SITE_C = (176, 154, 120); STAKE_C = (112, 88, 62); STONE_C = (206, 198, 180); WALL_C = (214, 206, 188); SCAF_C = (124, 92, 58)
def whole_done(e): return min(p_['year'] for p_ in ST[e]['phases'] if p_['stage'] == 'done' and not p_.get('part'))
def scale_poly(P, k):
    c = P.centroid; return Polygon([(c.x + (x - c.x) * k, c.y + (y - c.y) * k) for x, y in P.exterior.coords])
def lattice(R, P, step, col, ya, yb):
    x0, y0, x1, y1 = P.bounds; n = 0
    for v in list(range(int(x0) + 3, int(x1), step)):
        g = P.intersection(LineString([(v, y0 - 1), (v, y1 + 1)]))
        for ln in ([g] if g.geom_type == 'LineString' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'LineString']):
            if ln.length > 2: R.line(list(ln.coords), col, ya, yb); n += 1
    for v in list(range(int(y0) + 3, int(y1), step)):
        g = P.intersection(LineString([(x0 - 1, v), (x1 + 1, v)]))
        for ln in ([g] if g.geom_type == 'LineString' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'LineString']):
            if ln.length > 2: R.line(list(ln.coords), col, ya, yb); n += 1
    return n
def part_region(e, part, P):
    """带 part 的局部落成画在脚印里的哪一块：宫殿三级台地按离竞技场远近切三条（上台地挨着竞技场，向海跌落；谭线 epic_core）；
    圣使徒陵墓圆堂在东端（谭线：东端创城者陵墓圆堂）；皇帝包厢在竞技场朝大皇宫那一侧（谭线：东侧 kathisma 朝向大皇宫）。"""
    if e == 'palace_great':
        hc = poly_px('hippodrome').centroid; c = P.centroid; dx, dy = c.x - hc.x, c.y - hc.y; L = math.hypot(dx, dy); dx, dy = dx / L, dy / L
        q4 = quad(P); ax = []   # 台地沿宫殿自己的边走：取外接矩形里最朝竞技场反方向的那条轴
        for i in (0, 1):
            ux, uy = q4[i + 1][0] - q4[i][0], q4[i + 1][1] - q4[i][1]; l = math.hypot(ux, uy); ux, uy = ux / l, uy / l
            if ux * dx + uy * dy < 0: ux, uy = -ux, -uy
            ax.append((ux * dx + uy * dy, ux, uy))
        _, dx, dy = max(ax)
        pr = [(x - c.x) * dx + (y - c.y) * dy for x, y in P.exterior.coords]; a, b = min(pr), max(pr); k = {'upper': 0, 'middle': 1, 'lower': 2}[part]
        lo, hi = a + (b - a) * k / 3, a + (b - a) * (k + 1) / 3; big = 2000
        band = Polygon([(c.x + dx * lo - dy * big, c.y + dy * lo + dx * big), (c.x + dx * lo + dy * big, c.y + dy * lo - dx * big),
                        (c.x + dx * hi + dy * big, c.y + dy * hi - dx * big), (c.x + dx * hi - dy * big, c.y + dy * hi + dx * big)])
        return P.intersection(band)
    if e == 'church_apostles':
        x0, y0, x1, y1 = P.bounds; east = P.intersection(box(x1 - (x1 - x0) * 0.3, y0, x1, y1)); c = east.centroid
        return Point(c.x, c.y).buffer(min(x1 - x0, y1 - y0) * 0.16, 12).intersection(P)
    if e == 'hippodrome':
        pc = poly_px('palace_great').centroid; from shapely.ops import nearest_points
        q = nearest_points(P.exterior, pc)[0]; return Point(q.x, q.y).buffer(22, 8).intersection(P)
    return None
def phase_rows():
    rows = []; meta = {}
    for e in PH_IDS:
        ph = ST[e]['phases']; wd = whole_done(e); site = ph[0]['year']; dst = ST[e].get('destroyed') or INF
        fr = [p_['year'] for p_ in ph if p_['stage'] == 'frame']; fy = fr[0] if fr else wd
        meta[e] = {'built': ST[e]['built'], 'phases': [[p_['year'], p_['stage'], p_.get('part')] for p_ in ph], 'done': wd}
        if ST[e]['geom']['type'] == 'point':
            x, y = wp(*ST[e]['geom']['coords']); R = Row('epic:' + e, site, [(x - 4, y - 4), (x + 4, y - 4), (x + 4, y + 4), (x - 4, y + 4)])
            R.rect(x - 4, y - 4, x + 4, y + 4, WALL_C, site, dst); R.edge([(x - 4, y - 4), (x + 4, y - 4), (x + 4, y + 4), (x - 4, y + 4)], (176, 164, 142), site, dst)
            ys = sorted(p_['year'] for p_ in ph); DR = 7     # 谭线：基座 + 7 节斑岩鼓石；2—4 年各两节，5 年立像
            for i, Y in enumerate(range(fy, wd + 1)):
                y1 = Y + 1 if Y < wd else dst; n = DR if Y >= wd else min(DR, 2 * (i + 1)); L = 40 * n / DR + (4 if Y >= wd else 0)
                R.fill([(x + 1, y - 1), (x + 1 + L * 0.72, y - 1 + L * 0.69), (x - 1 + L * 0.72, y + 1 + L * 0.69), (x - 1, y + 1)], (150, 134, 112), Y, y1)
            R.ell(x, y, 2.2, 2.2, (122, 52, 60), fy, dst, 10)
            R.edge([(x - 6, y - 6), (x + 6, y - 6), (x + 6, y + 6), (x - 6, y + 6)], SCAF_C, fy, wd)
            R.ell(x, y, 1, 1, (212, 170, 60), wd, dst, 6)
            rows.append(R); continue
        P = poly_px(e).buffer(0); C = scale_poly(P, 1.08).union(P.buffer(3, join_style=2)).simplify(0.2); R = Row('epic:' + e, site, quad(P))
        for o in W['structures']:   # 放宽的那 8% 不伸进工地期里站着的别的史诗脚印（底账自己的重叠不管）
            if o['id'] == e or o['geom']['type'] != 'polygon' or o['type'] in ('district', 'farmland', 'wall', 'gate', 'harbor'): continue
            if max(site, o['built']) < min(wd, o.get('destroyed') or INF): C = C.difference(poly_px(o['id']).buffer(1.0).difference(P))   # 1 px 余量：vec 坐标取整到半像素
        C = max(polys(C.buffer(0)), key=lambda g: g.area)
        cc = list(C.exterior.coords)[:-1]
        R.fill(cc, SITE_C, site, wd)                                    # 盖住栅格小图：整座 done 前一直在
        R.edge(list(P.simplify(0.2).exterior.coords)[:-1], STAKE_C, site, fy)   # 放线桩
        x0, y0, x1, y1 = P.bounds; n_ = max(4, int(P.area / 1500))
        for i in range(min(n_, 18)):
            for t in range(20):
                px, py = x0 + hsh(i + len(e) * 31, 2 * t + 1) * (x1 - x0), y0 + hsh(i + len(e) * 31, 2 * t + 2) * (y1 - y0)
                if P.buffer(-3).contains(Point(px, py)): R.ell(px, py, 2.6, 1.8, STONE_C, site, wd, 6); break
        if fy < wd:
            R.edge(list(P.buffer(-1.5, join_style=2).simplify(0.2).exterior.coords)[:-1], WALL_C, fy, wd)
            inn = P.buffer(-4, join_style=2)
            if not inn.is_empty and inn.geom_type == 'Polygon': R.edge(list(inn.simplify(0.2).exterior.coords)[:-1], WALL_C, fy, wd)
            lattice(R, P.buffer(-1), max(7, int(P.area ** 0.5 / 14)), SCAF_C, fy, wd)
        for p_ in ph:
            if p_['stage'] != 'done' or not p_.get('part'): continue
            g = part_region(e, p_['part'], P)
            if g is None or g.is_empty: continue
            if p_['year'] < wd:                                               # 局部先落成：那一块先铺好
                if e == 'palace_great':   # 台地：大理石地坪 + 一圈殿宇屋顶 + 中间庭院花园（谭线 epic_core：每级一排殿宇、列柱庭院带花园）
                    R.polys(g, MARBLE, (176, 164, 142), p_['year'], wd)
                    R.polys(g.difference(g.buffer(-11, join_style=2)), TILE, TILE_D, p_['year'], wd)
                    R.polys(g.buffer(-19, join_style=2), (128, 150, 96), (96, 118, 70), p_['year'], wd)
                else: R.polys(g, TILE, TILE_D, p_['year'], wd)
            else:                                                             # 整座之后才落成的局部（竞技场皇帝包厢）：之前那块还是工地
                ga = g.buffer(1.5).intersection(C); R.polys(ga, SITE_C, None, wd, p_['year']); lattice(R, g, 5, SCAF_C, wd, p_['year'])
        rows.append(R)
    return rows, meta
def build():
    pr, pm = phase_rows()
    rows = forum_rows() + nymph_rows() + mese_rows() + pr
    meta = {'forum_theodosius': {'built': B_FORUM, 'finish': B_FORUM + FORUM_SITE, 'column_done': B_FORUM + COLUMN_COURSES - 1, 'arch': ARCH_Y, 'column_parts': list(COLR[0])},
            'nymphaeum_maius': {'built': B_NYMPH, 'finish': B_NYMPH, 'wet': WET_NYMPH},
            'r_mese': {'built': B_MESE, 'finish': B_MESE + MESE_SITE}}
    meta.update(pm)
    return {'src': 'tools/cs/factory/epic_stage.py（谭线 render_xero.py epic_ground/epic_tall/mese_portico，年份读 world.json）', 'epics': meta, 'rows': [r.out() for r in rows]}
if __name__ == '__main__':
    D = build(); json.dump(D, open(os.path.join(OUT, 'epic_stage.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    n = sum(len(r['parts']) for r in D['rows']); print('rows', len(D['rows']), 'parts', n, 'bytes', os.path.getsize(os.path.join(OUT, 'epic_stage.json')))
    for k in ('forum_theodosius', 'nymphaeum_maius'): print(k, [r['id'] for r in D['rows'] if k in r['id']], [len(r['parts']) for r in D['rows'] if k in r['id']])
    print('mese rows', sum(1 for r in D['rows'] if 'mese' in r['id']))
