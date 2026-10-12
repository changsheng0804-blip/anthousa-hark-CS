"""CS 线 · 街区生产线（心跳选址）—— 心跳的位置从底账自己长出来，不再手标
借自 castle-town-sim 的「中心按规则放」：码头离水近、和粮仓同岸、离粮仓最近、前面水够深。
从底账（陆地、港口多边形、粮仓、路、房子）算出：
  泊位 / 系缆桩 / 大船停靠点与朝向、其余船的锚地、每艘船从图边进港的水路、
  码头上人站的地方、孩子爬的港墙、扛包的人从码头到粮仓走的路。
写进 scene.json 的 fleet（句子、钟点不动），另出一张目检图 out/<q>_heart.jpg。
用法: python tools/cs/factory/heart.py <quarter_id> [--dry]"""
import heapq, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from terrain import land
PW, PH, R = 1820, 2048, 4          # 寻路栅格 4 像素一格
GW, GH = PW // R, PH // R


def standing(s, Y):
    return s['built'] <= Y and not (s['destroyed'] is not None and s['destroyed'] <= Y)


def dijkstra(cost, src):
    """cost: GH×GW，inf 不可走；src: [(j,i)]；返回距离和前驱"""
    D = np.full(cost.shape, np.inf); P = np.full(cost.shape + (2,), -1, int); h = []
    for s in src: D[s] = 0; heapq.heappush(h, (0.0, s))
    nb = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (1, 1, 1.414), (-1, 1, 1.414), (1, -1, 1.414)]
    while h:
        d, (j, i) = heapq.heappop(h)
        if d > D[j, i]: continue
        for dj, di, w in nb:
            a, b = j + dj, i + di
            if 0 <= a < GH and 0 <= b < GW and cost[a, b] < np.inf:
                nd = d + w * (cost[j, i] + cost[a, b]) / 2
                if nd < D[a, b]: D[a, b] = nd; P[a, b] = (j, i); heapq.heappush(h, (nd, (a, b)))
    return D, P


def back(P, t):
    out = [t]
    while P[out[-1]][0] >= 0: out.append(tuple(P[out[-1]]))
    return out


def rdp(pts, eps):
    import sys as _s; _s.setrecursionlimit(10000)
    if len(pts) < 3: return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float); ab = b - a; L = np.hypot(*ab) or 1
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / L for p in pts[1:-1]]
    k = int(np.argmax(d)) + 1
    if d[k - 1] > eps: return rdp(pts[:k + 1], eps)[:-1] + rdp(pts[k:], eps)
    return [pts[0], pts[-1]]


def main():
    q = sys.argv[1]; Q = os.path.join(ROOT, 'docs', 'living', q)
    sc = json.load(open(os.path.join(Q, 'scene.json'))); C = sc['fleet']
    fr = json.load(open(os.path.join(Q, 'frame.json'))); hs = json.load(open(os.path.join(Q, 'houses.json')))['houses']
    x0, y0, _, _ = fr['frame']; S = fr['scale']; Y = max(k[0] for k in sc['keys'])
    # 1. 水：底账陆地以外 + 已建的港口
    m = Image.new('L', (GW, GH), 0); d = ImageDraw.Draw(m); L = land()
    for g in (L.geoms if hasattr(L, 'geoms') else [L]):
        d.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in g.exterior.coords], fill=255)
        for r in g.interiors: d.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in r.coords], fill=0)
    harb = Image.new('L', (GW, GH), 0); dh = ImageDraw.Draw(harb)
    for s in fr['structures']:
        if s['type'] == 'harbor' and standing(s, Y):
            d.polygon([(x / R, y / R) for x, y in s['pts']], fill=0); dh.polygon([(x / R, y / R) for x, y in s['pts']], fill=255)
    landm = np.asarray(m) > 0; water = ~landm; harb = np.asarray(harb) > 0
    # 2. 房子和路
    hm = Image.new('L', (GW, GH), 0); dd = ImageDraw.Draw(hm)
    for h in hs:
        if h[2] <= Y < h[3]: dd.polygon([(h[4][i] / R, h[4][i + 1] / R) for i in range(0, len(h[4]), 2)], fill=255)
    rm = Image.new('L', (GW, GH), 0); dr = ImageDraw.Draw(rm)
    for s in fr['structures']:
        if s['type'] == 'road' and standing(s, Y): dr.line([(x / R, y / R) for x, y in s['pts']], fill=255, width=4)
    house = np.asarray(hm) > 0; road = np.asarray(rm) > 0
    # 画上的水：每张年代画都算一遍（页面在两张画之间渐变，两张都得对）。人只走底账和画都算陆地的地方，船只走两边都是水的地方
    pw = np.zeros((GH, GW), bool); pall = np.ones((GH, GW), bool)
    for k in sc['keys']:
        a_ = np.asarray(Image.open(os.path.join(Q, k[1])).convert('RGB').resize((GW, GH), Image.BOX)).astype(int)
        wk = (a_[..., 2] > a_[..., 0] + 15) & (a_[..., 2] > a_[..., 1] - 10)
        wk = ndi.binary_fill_holes(ndi.binary_closing(wk, iterations=1))   # 画上的船、浪花四面是水，不算陆地
        pw |= ndi.binary_opening(wk, iterations=1); pall &= wk
    band = np.zeros((GH, GW), bool); band[:30], band[-30:], band[:, :30], band[:, -30:] = True, True, True, True   # 画边有晕边，图边一圈只看底账
    shipwater = water & (ndi.binary_erosion(pall, iterations=2) | band)
    clear = ndi.distance_transform_edt(water) * R          # 水面离岸多远（像素）
    shore_d = ndi.distance_transform_edt(landm) * R        # 陆地离水多远
    # 3. 粮仓：底账里最大的那座（页面上按年份换）
    grs = [s for s in fr['structures'] if s['type'] == 'granary' and s['geom'] == 'polygon']
    g0 = min(grs, key=lambda s: s['built']); gc = np.mean(g0['pts'], 0)
    # 4. 陆上寻路：路 1、空地 2、穿房子 9
    lc = np.where(landm, np.where(road, 1.0, np.where(house, 9.0, 2.0)), np.inf)
    gj, gi = int(gc[1] / R), int(gc[0] / R)
    Dg, Pg = dijkstra(lc, [(gj, gi)])
    # 5. 水上寻路：从图边的水出发，离岸越近越贵（大船不贴岸走）
    wc = np.where(shipwater, 1 + 40.0 / np.maximum(clear, 4), np.inf)
    edge = [(j, i) for j in range(GH) for i in (0, GW - 1) if water[j, i]] + [(j, i) for i in range(GW) for j in (0, GH - 1) if water[j, i]]
    # 港墙：底账的港口多边形四周是墙，船只能从口子进；口子开在离粮仓最近、外面是开阔水面的那段墙上（陆上的墙不算）
    wallm = Image.new('L', (GW, GH), 0); dwm = ImageDraw.Draw(wallm); gates = []
    gc0 = np.mean(min([s for s in fr['structures'] if s['type'] == 'granary' and s['geom'] == 'polygon'], key=lambda s: s['built'])['pts'], 0)
    for s in fr['structures']:
        if s['type'] == 'harbor' and standing(s, Y):
            P = s['pts'] + [s['pts'][0]]; dwm.line([(x / R, y / R) for x, y in P], fill=255, width=3)
            cx, cy = np.mean(s['pts'], 0); best_g = None; cands = []
            for p, q2 in zip(P, P[1:]):
                for t in np.linspace(0.08, 0.92, 24):
                    x, y = p[0] + (q2[0] - p[0]) * t, p[1] + (q2[1] - p[1]) * t
                    ox, oy = x + (x - cx) / (np.hypot(x - cx, y - cy) or 1) * 24, y + (y - cy) / (np.hypot(x - cx, y - cy) or 1) * 24
                    oj, oi = int(oy / R), int(ox / R)
                    if 0 <= oj < GH and 0 <= oi < GW and water[oj, oi] and not harb[oj, oi] and clear[oj, oi] >= 20:
                        dg = np.hypot(x - gc0[0], y - gc0[1])
                        # cs14：口子按画来定——画上围墙在这一点是水（缺口）才算；整座港都没有缺口时才退回只看底账
                        pj_, pi_ = min(max(int(y / R), 0), GH - 1), min(max(int(x / R), 0), GW - 1)
                        cands.append((0 if pall[pj_, pi_] else 1, dg, x, y))
            if cands:
                bb = min(cands); best_g = (bb[1], bb[2], bb[3])
            if best_g: gates.append(best_g[1:]); dwm.ellipse([best_g[1] / R - 6, best_g[2] / R - 6, best_g[1] / R + 6, best_g[2] / R + 6], fill=0)
    wallA = np.asarray(wallm) > 0
    wc = np.where(wallA, np.inf, wc)
    Dw, Pw = dijkstra(wc, edge)
    # 6. 泊位：岸边 ≤8 像素的陆地，前面 30 像素处水深 ≥24、能从海上开进来；码头不压房子；离粮仓走得最近；港口里的岸加分
    best = None
    ys, xs = np.nonzero(landm & (shore_d <= 8) & ~ndi.binary_dilation(house, iterations=2))
    gy, gx = np.gradient(ndi.gaussian_filter(clear, 3))
    for j, i in zip(ys, xs):
        # 朝水的法向
        sj, si = max(0, min(GH - 1, j)), max(0, min(GW - 1, i))
        nx, ny = gx[sj, si], gy[sj, si]
        nl = math.hypot(nx, ny)
        if nl < 1e-6: continue
        nx, ny = nx / nl, ny / nl
        fj, fi = int(round(j + ny * 30 / R)), int(round(i + nx * 30 / R))
        if not (0 <= fj < GH and 0 <= fi < GW) or not water[fj, fi] or clear[fj, fi] < 24 or not np.isfinite(Dw[fj, fi]): continue
        sc_ = Dg[j, i] * R - (120 if harb[fj, fi] else 0)
        if not np.isfinite(sc_): continue
        if best is None or sc_ < best[0]: best = (sc_, j, i, nx, ny, fj, fi)
    _, bj, bi, nx, ny, fj, fi = best
    bol = [int(bi * R), int(bj * R)]; ang = round(math.atan2(ny, nx) + math.pi / 2, 2)
    main_at = [int(bol[0] + nx * 30), int(bol[1] + ny * 30)]
    # 7. 其余船：锚地（水深 ≥40、能开进来、离泊位 ≤600、彼此 ≥110），再加一个紧挨着的第二泊位
    cand = [(math.hypot(i * R - bol[0], j * R - bol[1]), j, i) for j, i in zip(*np.nonzero(water & (clear >= 40) & np.isfinite(Dw))) if math.hypot(i * R - bol[0], j * R - bol[1]) < 600]
    cand.sort(); anchors = []
    for dd_, j, i in cand:
        p = [i * R, j * R]
        if dd_ > 90 and all(math.hypot(p[0] - a[0], p[1] - a[1]) >= 110 for a in anchors + [main_at]): anchors.append(p)
        if len(anchors) >= 7: break
    def wpath(p):
        t = (int(p[1] / R), int(p[0] / R)); pts = [(i * R, j * R) for j, i in back(Pw, t)][::-1]
        return [list(map(int, v)) for v in rdp(pts, 10)]
    ships = []
    for k, a in enumerate(anchors[:4] + [main_at] + anchors[4:7]):
        ism = a is main_at
        ships.append({'at': a, 'ang': ang if ism else round(((k * 0.37) % 0.8) - 0.4, 2), **({'main': True} if ism else {}), 'path': wpath(a)})
    # cs14 · backlog 1：港口的口子按画来定。画上围墙的缺口（三张画在墙线上都是水的那几段）= 口子；口子要和算出来的口子对上，至少一艘船停在港里，水路穿过口子
    if '--mouth' in sys.argv:
        from shapely.geometry import Polygon, Point
        mp_, ins, thru = [], 0, 0
        for s in fr['structures']:
            if s['type'] == 'harbor' and standing(s, Y):
                P = s['pts'] + [s['pts'][0]]
                for p, q2 in zip(P, P[1:]):
                    n = max(1, int(math.hypot(q2[0] - p[0], q2[1] - p[1]) / 4))
                    for t in range(n + 1):
                        x, y = p[0] + (q2[0] - p[0]) * t / n, p[1] + (q2[1] - p[1]) * t / n
                        if 0 <= x < PW - 120 and 0 <= y < PH and pall[int(y / R), int(x / R)] and not band[int(y / R), int(x / R)]: mp_.append((x, y))
                poly = Polygon(s['pts'])
                if math.hypot(poly.centroid.x - bol[0], poly.centroid.y - bol[1]) > 600: continue   # 只看泊位旁边的那座港
                for sh_ in ships:
                    if poly.contains(Point(sh_['at'])):
                        ins += 1
                        pp = sh_['path']; segs = pp + [[(pp[k][0] + pp[k + 1][0]) // 2, (pp[k][1] + pp[k + 1][1]) // 2] for k in range(len(pp) - 1)]
                        if mp_ and any(min(math.hypot(a[0] - m[0], a[1] - m[1]) for m in mp_) < 40 for a in segs): thru += 1
        gok = sum(1 for g in gates if mp_ and min(math.hypot(g[0] - m[0], g[1] - m[1]) for m in mp_) <= 30)
        print(f'harbor mouth painted {len(mp_)} pts, gates on mouth {gok} / {len(gates)}, ships inside {ins}, ships entering via mouth {thru}'); return
    # 8. 码头上站人的地方：泊位两边沿岸 ≤140 像素、不压房子，彼此 ≥24
    spots = []
    sp = sorted([(math.hypot(i * R - bol[0], j * R - bol[1]), j, i) for j, i in zip(*np.nonzero(landm & (shore_d <= 14) & ~house))])
    for dd_, j, i in sp:
        if dd_ > 140: break
        p = [int(i * R), int(j * R)]
        if all(math.hypot(p[0] - s[0], p[1] - s[1]) >= 24 for s in spots): spots.append(p)
        if len(spots) >= 7: break
    # 9. 孩子爬的港墙：已建港口的边，离泊位最近的一段（没有港口就用更远一点的岸）
    wall = []
    for s in fr['structures']:
        if s['type'] == 'harbor' and standing(s, Y):
            P = s['pts'] + [s['pts'][0]]
            for a, b in zip(P, P[1:]):
                n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 30))
                for t in range(n + 1): wall.append([int(a[0] + (b[0] - a[0]) * t / n), int(a[1] + (b[1] - a[1]) * t / n)])
    wall = [p for p in wall if 160 <= math.hypot(p[0] - bol[0], p[1] - bol[1]) and all(math.hypot(p[0] - g[0], p[1] - g[1]) > 30 for g in gates)]
    wall.sort(key=lambda p: math.hypot(p[0] - bol[0], p[1] - bol[1])); wall = wall[:4] or [s for s in spots[-4:]]
    # 10. 扛包的路：码头 → 粮仓，沿街走
    rt = [(i * R, j * R) for j, i in back(Pg, (bj, bi))]
    route = [list(map(int, v)) for v in rdp(rt, 14)][1:-1]
    # 11. 人走的网：陆地 + 港墙顶（港墙就是街道伸进海里的那一截）；水里不能走。8 像素一格，存成方向场
    R8 = 8; H8, W8 = PH // R8, PW // R8
    def pool(mk, f): return np.array(Image.fromarray(mk.astype('uint8') * 255).resize((W8, H8), Image.BOX)) / 255.0
    land8 = pool(landm, 0) >= 0.5; wall8 = pool(wallA, 0) > 0.05
    road8 = pool(road, 0) > 0.2; house8 = pool(house, 0) > 0.5
    pw8 = pool(pw, 0) > 0.3
    walk8 = (land8 | wall8) & ~pw8
    # cs13 · 栈桥：画上画了、底账没有的栈桥（三张画都是陆地、在底账的水里、离岸 ≤ 120 像素、至少 8 像素宽、连着岸）。人要走得上去
    band2 = np.zeros((GH, GW), bool); band2[:30], band2[-30:], band2[:, :30], band2[:, -30:] = True, True, True, True
    pc = ~pw & ~landm & ~band2 & (clear <= 120)
    pc = ndi.binary_opening(pc, structure=np.ones((2, 2), bool))
    pier_px = ndi.binary_propagation(ndi.binary_dilation(landm, iterations=2) & pc, mask=pc)
    pier8 = pool(pier_px, 0) >= 0.4
    if not os.environ.get('PIER_OFF'): walk8 = walk8 | pier8
    if '--piers' in sys.argv:
        pj, pi_ = np.nonzero(pier_px); ok_ = walk8[np.minimum(pj * R // R8, H8 - 1), np.minimum(pi_ * R // R8, W8 - 1)]
        print(f'piers walkable {int(ok_.sum())} / {len(pj)}'); return
    cost8 = np.where(walk8, np.where(road8 | wall8, 1.0, np.where(house8, 6.0, 2.0)), np.inf)
    def field(srcs):
        global GH, GW
        oh, ow = GH, GW; GH, GW = H8, W8
        src = []
        for p in srcs:
            j, i = int(p[1] / R8), int(p[0] / R8)
            if 0 <= j < H8 and 0 <= i < W8 and walk8[j, i]: src.append((j, i))
        D, Pp = dijkstra(cost8, src); GH, GW = oh, ow
        dirs = {(-1, 0): '0', (1, 0): '1', (0, -1): '2', (0, 1): '3', (-1, -1): '4', (1, 1): '5', (-1, 1): '6', (1, -1): '7'}
        rows = []
        for j in range(H8):
            r_ = []
            for i in range(W8):
                if not walk8[j, i]: r_.append('w' if not land8[j, i] else 'x')
                elif not np.isfinite(D[j, i]): r_.append('u')   # 能走、只是走不到码头
                elif Pp[j, i][0] < 0: r_.append('s')
                else: r_.append(dirs[(Pp[j, i][0] - j, Pp[j, i][1] - i)])
            rows.append(''.join(r_))
        return ''.join(rows)
    walk = {'R': R8, 'W': W8, 'H': H8, 'quay': field(spots), 'wall': field(wall)}
    I = lambda v: [I(x) for x in v] if isinstance(v, (list, tuple)) else int(v)
    ships = [{**s, 'at': I(s['at']), 'path': I(s['path'])} for s in ships]; spots, wall, route, bol = I(spots), I(wall), I(route), I(bol)
    out = {'quay': bol, 'bollard': bol, 'ships': ships, 'spots': spots, 'wall': wall, 'route': route,
           'drift': [int(nx * 20), int(ny * 20)], 'walk': walk, 'derived': f'heart.py 从底账算（建城 {Y} 年的陆地、港口、粮仓 {g0["id"]}、路、房子）'}
    out.pop('enter', None)
    # 目检图
    base = Image.open(os.path.join(Q, f'ng_af{Y}.jpg' if os.path.exists(os.path.join(Q, f'ng_af{Y}.jpg')) else 'bare.jpg')).convert('RGB').resize((PW, PH))
    dv = ImageDraw.Draw(base)
    for s in ships:
        dv.line([tuple(p) for p in s['path']], fill=(255, 230, 0), width=3); x, y = s['at']; r = 30 if s.get('main') else 20
        dv.ellipse([x - r, y - 9, x + r, y + 9], outline=(255, 0, 0), width=4)
    dv.line([tuple(bol)] + [tuple(p) for p in route] + [tuple(map(int, gc))], fill=(255, 0, 255), width=4)
    for p in spots: dv.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(0, 255, 0))
    for p in wall: dv.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(0, 255, 255))
    dv.rectangle([bol[0] - 6, bol[1] - 6, bol[0] + 6, bol[1] + 6], fill=(255, 255, 255))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True); base.resize((910, 1024)).save(os.path.join(HERE, 'out', f'{q}_heart.jpg'), quality=85)
    print('gates', [list(map(int, g)) for g in gates]); print(json.dumps({k: v for k, v in out.items() if k not in ('ships', 'walk')}, ensure_ascii=False)); print('ships', [(s['at'], len(s['path'])) for s in ships])
    # 12. 街：城里走动的人和摊子沿 city.json 的 roads 走。roads 也从底账长：已建的路，切掉落在水里（底账或画）的那几截
    croads = []
    for st in fr['structures']:
        if st['type'] != 'road' or not standing(st, Y): continue
        run = []
        P = st['pts']
        for a_, b_ in zip(P, P[1:]):
            n = max(1, int(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) / 8))
            for t in range(n):
                x, y = a_[0] + (b_[0] - a_[0]) * t / n, a_[1] + (b_[1] - a_[1]) * t / n
                j, i = math.floor(y / R8), math.floor(x / R8)
                ok_ = 0 <= j < H8 and 0 <= i < W8 and walk8[j, i]
                if ok_: run.append((x, y))
                else:
                    if len(run) >= 6: croads.append((st['id'], run))
                    run = []
        if len(run) >= 6: croads.append((st['id'], run))
    # cs12：画上沙色的宽街（底账没有这条路）。中线从画上量，存在 scene.json 的 wide_street；只留人走得上的几截
    WS = sc.get('wide_street') or []
    run = []
    for a_, b_ in zip(WS, WS[1:]):
        n = max(1, int(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) / 8))
        for t in range(n + 1):
            x, y = a_[0] + (b_[0] - a_[0]) * t / n, a_[1] + (b_[1] - a_[1]) * t / n
            j, i = math.floor(y / R8), math.floor(x / R8)
            if 0 <= j < H8 and 0 <= i < W8 and walk8[j, i]: run.append((x, y))
            else:
                if len(run) >= 6: croads.append(('wide', run))
                run = []
    if len(run) >= 6: croads.append(('wide', run))
    city_roads = [{'id': f'{i}' if k == 0 else f'{i}_{k}', 'pts': [[int(x), int(y)] for x, y in rdp(r_, 2)]} for k, (i, r_) in enumerate(croads)]
    if '--json' in sys.argv:
        print(json.dumps({**out, '_roads': city_roads}, ensure_ascii=False)); return
    if '--dry' not in sys.argv:
        for k in ('enter', 'mouth'): C.pop(k, None)
        C.update(out); json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
        cj = json.load(open(os.path.join(Q, 'city.json'))); cj['roads'] = city_roads
        json.dump(cj, open(os.path.join(Q, 'city.json'), 'w'), ensure_ascii=False); print('roads', [(r_['id'], len(r_['pts'])) for r_ in city_roads])


if __name__ == '__main__':
    main()
