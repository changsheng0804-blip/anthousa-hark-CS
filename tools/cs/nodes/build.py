"""CS 线 · 节点流水线（2026-10-17，主人「可以」：底账→节点→渲染器，先在南港做样板，不用一张栅格图）
学 WorldGacha 的方法（只学方法，不抄代码）：节点按顺序跑，每个节点有自己的种子，同一份配方永远得到同一个街区；
输出一层「OSM 形状 + 年份」的中间数据，渲染器只吃这一层，不管它从哪来。

节点：① 地（底账真实海岸 + SRTM 高程 → 陆地面、等高带）② 水（海、按年挖出的港池，岸线用位置噪声收）
      ③ 栈桥（港池的码头边按规则长出，年份随港口逐年加）④ 街（streets.json，底账长出）⑤ 房（houses_street + houses_geom，底账）
      ⑥ 地标（底账多边形 + 类型 → 页面里的参数化代码部件画）⑦ 空地（没房没街的陆地按位置哈希种树、园子）
用法: python3 tools/cs/nodes/build.py nangang   → docs/living/nodes/nangang/{world.json,recipe.json}
配方 recipe.json 只记节点种子和参数；改一个节点的种子只重算它和它下游。"""
import json, math, os, sys, hashlib
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box, mapping
from shapely.ops import unary_union
from shapely import affinity
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from terrain import land, elevation

NODES = ['land', 'water', 'piers', 'streets', 'houses', 'landmarks', 'open']
LMT = {'forum', 'granary', 'cistern', 'monastery', 'monument', 'nymphaeum', 'xenon', 'church', 'baths', 'column', 'market', 'warehouse', 'palace', 'gate', 'fort', 'theatre', 'temple', 'hippodrome'}


def h32(*a):
    return int(hashlib.blake2b(repr(a).encode(), digest_size=4).hexdigest(), 16)


def hf(*a):   # 位置决定的随机数 0–1：动一处不牵连别处
    return h32(*a) / 4294967296


def node_seed(R, name):
    return R['seeds'].get(name, h32(R['seed'], name))


def rings(g, nd=1):
    out = []
    for p in (g.geoms if hasattr(g, 'geoms') else [g]):
        if p.is_empty or p.geom_type != 'Polygon': continue
        out.append([[[round(x, nd), round(y, nd)] for x, y in p.exterior.coords]] + [[[round(x, nd), round(y, nd)] for x, y in r.coords] for r in p.interiors])
    return out


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
    Q = os.path.join(ROOT, 'docs', 'living', q); O = os.path.join(ROOT, 'docs', 'living', 'nodes', q); os.makedirs(O, exist_ok=True)
    rp = os.path.join(O, 'recipe.json')
    R = json.load(open(rp)) if os.path.exists(rp) else {'q': q, 'seed': 1, 'seeds': {}, 'num': {'contour_m': 5, 'pier_gap': 46, 'pier_every': 4, 'tree_cell': 26}}
    fr = json.load(open(os.path.join(Q, 'frame.json'))); x0, y0, fw, fh = fr['frame']; S = fr['scale']
    W, H = round(fw * S), round(fh * S)
    toP = lambda x, y: ((x - x0) * S, (y - y0) * S)
    FR = box(0, 0, W, H)
    HS = json.load(open(os.path.join(Q, 'houses_street.json'))); late = HS.get('late', {})
    years = sorted({0, 70} | {int(s['built']) for s in fr['structures'] if s['built'] is not None and s['built'] >= 0} | {int(v['built']) for v in late.values()})
    F = []   # 特征：{t:类型, k:细类, g:几何, y0:建成, y1:毁/止(None), ...}

    # ① 地
    L = land(); Lp = []
    for g in (L.geoms if hasattr(L, 'geoms') else [L]):
        if not g.intersects(box(x0 - 2, y0 - 2, x0 + fw + 2, y0 + fh + 2)): continue
        Lp.append(Polygon([toP(*c) for c in g.exterior.coords], [[toP(*c) for c in r.coords] for r in g.interiors]))
    landP = unary_union(Lp).intersection(FR).buffer(0)
    # 古岸：OSM 海岸是今天的，带现代填海的细长防波堤；开运算去掉宽不到 2×ancient_r 的细条（老城的岸是圆的，不是一根根堤）
    ar = R['num'].setdefault('ancient_r', 22); landP = landP.buffer(-ar, join_style=1).buffer(ar, join_style=1).intersection(FR).buffer(0)
    # 等高带：每 contour_m 米一档，渲染器用来上色和描线（全是矢量，不是图）
    st = 8; gx = np.arange(0, W + st, st); gy = np.arange(0, H + st, st)
    E = np.array([[elevation(x0 + x / S, y0 + y / S) for x in gx] for y in gy])
    import cv2
    cm = R['num']['contour_m']; bands = []
    Eu = cv2.resize(E.astype(np.float32), (len(gx) * 2, len(gy) * 2), interpolation=cv2.INTER_CUBIC); k = st / 2
    for lv in np.arange(cm, max(cm, E.max()) + cm, cm):
        m = (Eu >= lv).astype(np.uint8)
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        for i, c in enumerate(cs):
            if hier[0][i][3] != -1 or len(c) < 4: continue
            sh = Polygon((c[:, 0, :] * k).tolist())
            holes = [Polygon((cs[j][:, 0, :] * k).tolist()) for j in range(len(cs)) if hier[0][j][3] == i and len(cs[j]) >= 4]
            for hh in holes: sh = sh.difference(hh)
            if sh.area > 400: polys.append(sh.buffer(0).simplify(2))
        g = unary_union(polys).intersection(landP) if polys else None
        if g is not None and not g.is_empty: bands.append({'lv': float(lv), 'g': rings(g)})
    F.append({'t': 'land', 'g': rings(landP.simplify(1)), 'y0': -9999})

    # ② 水：海 = 框减陆地；港池 = 底账港口多边形，从建成那年起挖成水，岸线按位置噪声往水里收、磨圆角
    sw = node_seed(R, 'water'); basins = []; molesP = []
    for s in fr['structures']:
        if s['type'] != 'harbor' or s.get('geom') != 'polygon': continue
        P = Polygon(s['pts']).buffer(0)   # frame.json 的结构已是页面像素
        r0 = 10
        P2 = P.buffer(-r0).buffer(r0, join_style=1)   # 磨掉直角
        pts = []
        ext = P2.exterior; Ln = ext.length
        for i in range(int(Ln // 6)):
            p = ext.interpolate(i * 6); n = hf(sw, s['id'], round(p.x / 30), round(p.y / 30)) * .7 + hf(sw, s['id'], round(p.x / 11), round(p.y / 11)) * .3
            pts.append((p.x, p.y, n))
        cx, cy = P2.centroid.x, P2.centroid.y
        sh = Polygon([(x + (cx - x) * (3 + 9 * n) / max(1, math.hypot(cx - x, cy - y)), y + (cy - y) * (3 + 9 * n) / max(1, math.hypot(cx - x, cy - y))) for x, y, n in pts]).buffer(0)
        # 防波堤：港池落在海里的那一圈边筑成石堤，朝外海最远的一处留口子让船进出
        ring = sh.buffer(9, join_style=2).difference(sh).difference(landP)
        if ring.area > 200:
            far = max(sh.exterior.coords, key=lambda c: Point(c).distance(landP)); gapP = Point(far).buffer(16)
            mole = ring.difference(gapP).buffer(0)
            F.append({'t': 'mole', 'harbor': s['id'], 'g': rings(mole.simplify(.8)), 'y0': int(s['built'])})
            molesP.append(mole)
        basins.append((s, sh))
        F.append({'t': 'water', 'k': 'harbor', 'id': s['id'], 'name': s.get('name'), 'g': rings(sh.simplify(1)), 'y0': int(s['built']), 'y1': s.get('destroyed')})
    seaP = FR.difference(landP)
    F.append({'t': 'water', 'k': 'sea', 'g': rings(seaP.simplify(1)), 'y0': -9999})

    # ③ 栈桥：港池贴着老陆地的那几段岸（码头边）上，按间距长出伸进水里的栈桥；第一座随港口建成，之后每 pier_every 年加一座
    sp = node_seed(R, 'piers'); gap = R['num']['pier_gap']; every = R['num']['pier_every']
    for s, sh in basins:
        b0 = int(s['built']); cand = []
        ext = sh.exterior; Ln = ext.length; cx, cy = sh.centroid.x, sh.centroid.y
        for i in range(int(Ln // gap)):
            d = i * gap + gap / 2; p = ext.interpolate(d); a = ext.interpolate(d - 4); b = ext.interpolate(d + 4)
            tx, ty = b.x - a.x, b.y - a.y; tl = math.hypot(tx, ty) or 1; nx, ny = -ty / tl, tx / tl
            if (cx - p.x) * nx + (cy - p.y) * ny < 0: nx, ny = -nx, ny * -1
            Lp_ = 26 + 34 * hf(sp, s['id'], i)
            tip = (p.x + nx * Lp_, p.y + ny * Lp_)
            ln = LineString([(p.x - nx * 3, p.y - ny * 3), tip])
            if not sh.buffer(-4).contains(Point(tip)): continue
            if not unary_union([landP] + molesP).buffer(2).contains(Point(p.x - nx * 6, p.y - ny * 6)): continue   # 根要在陆地或石堤上
            if any(ln.distance(c['ln']) < 18 for c in cand): continue
            cand.append({'ln': ln, 'w': 5 + 3 * hf(sp, s['id'], i, 'w'), 'r': hf(sp, s['id'], i, 'o')})
        cand.sort(key=lambda c: c['r'])
        for j, c in enumerate(cand):
            F.append({'t': 'pier', 'g': [[round(v, 1) for v in xy] for xy in c['ln'].coords], 'w': round(c['w'], 1), 'y0': b0 + j * every, 'harbor': s['id']})

    # ④ 街：底账长出来的街（streets.json：x1 y1 x2 y2 宽 类 建成 收掉）
    for qd in json.load(open(os.path.join(Q, 'streets.json'))):
        F.append({'t': 'street', 'k': qd[5], 'g': [qd[0], qd[1], qd[2], qd[3]], 'w': qd[4], 'y0': qd[6], 'y1': qd[7] or None})

    # ⑤ 房：底账户，按街排好的位置；港池建成那年压在池里的户算拆掉（底账一致：人不住水里）
    HG = json.load(open(os.path.join(Q, 'houses_geom.json')))
    for h in HS['houses']:
        id_, d_, b, de, p = h[:5]
        if de <= 1 or de <= b + 1: continue
        cxh = sum(p[0::2]) / 4; cyh = sum(p[1::2]) / 4
        for s, sh in basins:
            if sh.buffer(2).contains(Point(cxh, cyh)): de = min(de, int(s['built']))
        if de <= b: continue
        F.append({'t': 'house', 'id': id_, 'y0': b, 'y1': None if de >= 9999 else de, 'p': p, 'fn': h[8] if len(h) > 8 else 'homes', 'ht': h[7] if len(h) > 7 else 5})

    # ⑥ 地标：底账多边形 + 类型；页面的部件库按类型和种子画（像 WorldGacha 的城堡：是代码，不是图）
    sl = node_seed(R, 'landmarks'); seen = set()
    for s in fr['structures']:
        if s.get('geom') == 'polygon' and s['type'] in LMT:
            P = s['pts']; seen.add(s['id'])
            kk = 'nymphaeum' if 'nymph' in s['id'] else 'xenon' if 'xenon' in s['id'] else s['type']
            F.append({'t': 'landmark', 'k': kk, 'id': s['id'], 'name': s.get('name'), 'g': [[round(a, 1), round(b_, 1)] for a, b_ in P], 'y0': int(s['built']), 'y1': s.get('destroyed'), 'seed': h32(sl, s['id'])})
        elif s.get('geom') == 'line' and s['type'] == 'aqueduct':
            F.append({'t': 'aqueduct', 'id': s['id'], 'g': s['pts'], 'y0': int(s['built']), 'seed': h32(sl, s['id'])})
    for k_, v in late.items():
        if k_ in seen: continue
        typ = 'forum' if 'forum' in k_ else 'granary' if 'horrea' in k_ else 'nymphaeum' if 'nymph' in k_ else 'cistern' if 'cistern' in k_ else 'xenon' if 'xenon' in k_ else 'monument'
        F.append({'t': 'landmark', 'k': typ, 'id': k_, 'g': v['p'], 'y0': int(v['built']), 'seed': h32(sl, k_)})

    # ⑦ 空地：陆地上离房、街、地标都远的格子，按位置哈希种树（柏树、橄榄、园子）；年份 = 周围最早有人住的年份
    so = node_seed(R, 'open'); cell = R['num']['tree_cell']
    from scipy.spatial import cKDTree
    hc = np.array([[sum(f['p'][0::2]) / 4, sum(f['p'][1::2]) / 4] for f in F if f['t'] == 'house'])
    hy = np.array([f['y0'] for f in F if f['t'] == 'house'])
    sc_ = np.array([[(f['g'][0] + f['g'][2]) / 2, (f['g'][1] + f['g'][3]) / 2] for f in F if f['t'] == 'street'])
    lmP = unary_union([Polygon(f['g']).buffer(14) for f in F if f['t'] == 'landmark'] + [sh.buffer(6) for _, sh in basins])
    th, ts = cKDTree(hc), cKDTree(sc_)
    landI = landP.buffer(-6); trees = []
    for gy_ in range(0, H, cell):
        for gx_ in range(0, W, cell):
            x = gx_ + cell * hf(so, gx_, gy_, 'x'); y = gy_ + cell * hf(so, gx_, gy_, 'y')
            if not landI.contains(Point(x, y)) or lmP.contains(Point(x, y)): continue
            dh, ih = th.query((x, y)); ds, _ = ts.query((x, y))
            if dh < 13 or ds < 11: continue
            r = hf(so, gx_, gy_, 'k'); kind = 'cypress' if r < .3 else 'olive' if r < .8 else 'garden'
            # 离房越近越晚才种（园子跟着人家来）；荒地上的树从一开始就在，直到被房子占掉
            y0_ = -9999   # 树一开始就在；房子盖到跟前那年被砍（年份层：城长大，树退）
            y1_ = None
            near = th.query_ball_point((x, y), 12)
            if near: y1_ = int(min(hy[near]))
            trees.append([round(x), round(y), kind, y0_, y1_, round(2.6 + 2.6 * hf(so, gx_, gy_, 's'), 1)])
    out = {'q': q, 'W': W, 'H': H, 'years': years, 'nodes': NODES, 'bands': bands, 'features': F, 'trees': trees, 'pal': HG['pal'],
           'credit': '底账 world.json（tanxinhao 线）；海岸 OSM，高程 SRTM；方法学自 WorldGacha（oyasumi-gamedev），未用其代码'}
    json.dump(out, open(os.path.join(O, 'world.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    json.dump(R, open(rp, 'w'), indent=1, ensure_ascii=False)
    import collections
    print('features', collections.Counter(f['t'] for f in F), 'trees', len(trees), 'bands', len(bands), 'bytes', os.path.getsize(os.path.join(O, 'world.json')))


if __name__ == '__main__':
    main()
