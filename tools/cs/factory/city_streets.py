"""CS 线 · 全城街网（cs31）：先按底账给整座城长一张街网，街区只从里面裁窗口。
用法: python tools/cs/factory/city_streets.py      → tools/cs/factory/city/streets.json（世界坐标）

规则分层（只读上层，不写回；底账在最上）：
  L0 地形   陆/水（engine/terrain land）、坡度（elevation）
  L1 骨架   底账的大道、城墙、地标——原样，不生成
  L3 街     方向场 = 附近大道走向（按距离加权）+ 近岸贴岸 + 近墙顺墙 + 坡上顺等高线；
            横街从大道上分叉出去（一族），顺街平行于大道（另一族），碰到大道/墙/水/地标/别的街就停（T 字口）
  旧区（建城前、未被 48 年火烧过）方向场叠一层按世界坐标定的弯；新区直。
全城一张参数表（P），没有任何街区专用的数；随机只按世界坐标取，不按街区。"""
import json, math, os, sys
import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import LineString, Polygon, Point
from shapely import contains_xy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from terrain import land, elevation

P = dict(  # 全城唯一参数表（世界单位，1 单位 = 12 m；街区页面 1 单位 ≈ 14.2 px）
    along_sep=5.0,    # 顺街间距（≈ 71 px，街/巷交替）
    branch_sep=10.5,  # 横街间距（≈ 150 px）
    road_sigma=14, road_far=60.0, shore_sigma=4.0, wall_sigma=5.0,
    slope_grade=0.08, slope_w=0.6, old_bend=0.45, step=0.5, min_len=3.0, snap=1.6,
    settle_r=3.0, lane_break_old=0.05, lane_break_new=0.006)
BUILD = {"palace", "forum", "church", "market", "fort", "granary", "cistern", "temple", "hippodrome", "baths",
         "monument", "column", "monastery", "barracks", "warehouse", "aqueduct_bridge", "harbor"}


def h01(*a):  # 世界坐标上的确定性随机
    x = math.sin(sum(v * k for v, k in zip(a, (12.9898, 78.233, 37.719)))) * 43758.5453
    return x - math.floor(x)


def main():
    w = json.load(open(os.path.join(ROOT, 'world.json')))
    HP = np.array([p for h in w['houses'] for p in h['p']])
    X0, Y0 = np.floor(HP.min(0)) - 12; X1, Y1 = np.ceil(HP.max(0)) + 12
    R = 0.5  # 网格 0.5 单位
    gx = np.arange(X0, X1, R); gy = np.arange(Y0, Y1, R); NX, NY = len(gx), len(gy)
    XX, YY = np.meshgrid(gx + R / 2, gy + R / 2)
    L = land(); landm = contains_xy(L, XX, YY)
    roads = [s for s in w['structures'] if s['type'] == 'road']
    walls = [s for s in w['structures'] if s['type'] == 'wall']
    MS = [s for s in w['structures'] if s['type'] in BUILD and s['geom']['type'] == 'polygon']
    marks = [Polygon(s['geom']['coords']) for s in MS]
    HC = np.array([np.mean(h['p'], 0) for h in w['houses']]); HB_ = np.array([h['built'] for h in w['houses']])
    block = np.zeros_like(landm)
    for s_, M in zip(MS, marks):
        # 地标盖起来之前地皮上住过人：那时有街，先长出来，到它盖起来那年再由街区收掉（cs29b）
        if (contains_xy(M, HC[:, 0], HC[:, 1]) & (HB_ < s_['built'])).sum() > 2: continue
        block |= contains_xy(M, XX, YY)
    water = ~landm
    dwat = ndi.distance_transform_edt(~water) * R
    # 有人住过的地方（任何一年）
    occ = np.zeros((NY, NX), int); yb = np.full((NY, NX), 9999.0); ys_all = {}
    burnt = np.zeros((NY, NX), bool)
    for h in w['houses']:
        c = np.mean(h['p'], 0); i, j = int((c[1] - Y0) / R), int((c[0] - X0) / R)
        if 0 <= i < NY and 0 <= j < NX:
            occ[i, j] += 1; yb[i, j] = min(yb[i, j], h['built'])
            if h.get('destroyed') == 48: burnt[i, j] = True
    settle = ndi.binary_dilation(occ > 0, iterations=int(P['settle_r'] / R)) & landm & ~block
    # 年代：附近最早的房子；建城（1 年）前的为旧区
    yb_s = ndi.minimum_filter(yb, size=int(8 / R))
    burnt_s = ndi.binary_dilation(burnt, iterations=int(4 / R))
    old = np.clip((1 - yb_s) / 60.0 + 0.5, 0, 1) * (yb_s < 1) * ~burnt_s
    old = ndi.gaussian_filter(old.astype(float), 4)
    # ---- L3 方向场（张量）
    Tc = np.zeros((NY, NX)); Ts = np.zeros((NY, NX))
    def add_line(coords, sig, wt, far=0.0):
        for a, b in zip(coords[:-1], coords[1:]):
            a = np.array(a, float); b = np.array(b, float); d = b - a; Ld = np.linalg.norm(d)
            if Ld < 1e-6: continue
            t = np.clip(((XX - a[0]) * d[0] + (YY - a[1]) * d[1]) / Ld ** 2, 0, 1)
            dist = np.hypot(XX - a[0] - t * d[0], YY - a[1] - t * d[1])
            th = math.atan2(d[1], d[0]); ww = wt * (np.exp(-(dist / sig) ** 2) + far * np.exp(-(dist / P['road_far']) ** 2))
            Tc[:] += ww * math.cos(2 * th); Ts[:] += ww * math.sin(2 * th)
    # 大道之间不相加：两条相互垂直的大道在张量里会相互抵消（45° 乱街）。每处只听最近、最粗的那条大道
    best_w = np.zeros((NY, NX)); best_c = np.zeros((NY, NX)); best_s = np.zeros((NY, NX))
    for r in roads:
        Tc[:] = 0; Ts[:] = 0
        add_line(r['geom']['coords'], P['road_sigma'], r.get('width') or 1.2, far=0.15)
        m_ = np.hypot(Tc, Ts); upd = m_ > best_w
        best_w[upd] = m_[upd]; best_c[upd] = Tc[upd]; best_s[upd] = Ts[upd]
    Tc[:] = best_c; Ts[:] = best_s
    for s in walls: add_line(s['geom']['coords'], P['wall_sigma'], 1.5)
    # 岸：等距线切向
    gyw, gxw = np.gradient(dwat)
    thr = np.arctan2(gyw, gxw) + math.pi / 2; wsh = 2.0 * np.exp(-(dwat / P['shore_sigma']) ** 2) * (dwat > 0)
    Tc += wsh * np.cos(2 * thr); Ts += wsh * np.sin(2 * thr)
    # 坡：等高线切向
    ex = np.arange(X0, X1, 4.0); ey = np.arange(Y0, Y1, 4.0)
    E = np.array([[elevation(x, y) for x in ex] for y in ey])
    E = ndi.zoom(E, (NY / len(ey), NX / len(ex)), order=1)[:NY, :NX]
    E = ndi.gaussian_filter(E, 6)
    gey, gex = np.gradient(E, R)
    grade = np.hypot(gex, gey) / 12.0
    # 冲突优先级：大道 > 坡。大道跟前顺大道，离大道远了才顺等高线
    rm = np.ones((NY, NX), bool)
    for r in roads:
        for a, b in zip(r['geom']['coords'][:-1], r['geom']['coords'][1:]):
            n_ = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / R))
            for k in range(n_ + 1):
                i_, j_ = int((a[1] + (b[1] - a[1]) * k / n_ - Y0) / R), int((a[0] + (b[0] - a[0]) * k / n_ - X0) / R)
                if 0 <= i_ < NY and 0 <= j_ < NX: rm[i_, j_] = False
    droad = ndi.distance_transform_edt(rm) * R
    thc = np.arctan2(gey, gex) + math.pi / 2; wsl = P['slope_w'] * np.clip(grade / P['slope_grade'], 0, 1) * np.hypot(Tc, Ts).clip(0.2, 1.0) * (1 - np.exp(-(droad / P['road_sigma']) ** 2))
    Tc += wsl * np.cos(2 * thc); Ts += wsl * np.sin(2 * thc)
    Tc = ndi.gaussian_filter(Tc, 2); Ts = ndi.gaussian_filter(Ts, 2)
    TH = 0.5 * np.arctan2(Ts, Tc)
    bend = (np.sin(XX / 7.3 + 1.7 * np.sin(YY / 11.0)) + np.sin(YY / 5.9 + 1.3 * np.cos(XX / 9.1))) * 0.5
    TH = TH + P['old_bend'] * old * bend

    def cell(x, y):
        j, i = int((x - X0) / R), int((y - Y0) / R)
        return (i, j) if 0 <= i < NY and 0 <= j < NX else None
    def dirv(x, y, fam, prev):
        c = cell(x, y)
        if c is None: return None
        th = TH[c] + (math.pi / 2 if fam == 1 else 0.0)
        v = np.array([math.cos(th), math.sin(th)])
        if prev is not None and v @ prev < 0: v = -v
        return v
    # 占位网格（按族），存线号
    CS = 1.0
    grids = [{}, {}]; artgrid = {}
    def gkey(x, y): return (int(x // CS), int(y // CS))
    def near(gr, x, y, r, skip=None):
        k = gkey(x, y); n = int(math.ceil(r / CS))
        for a in range(-n, n + 1):
            for b in range(-n, n + 1):
                for (px, py, lid) in gr.get((k[0] + a, k[1] + b), ()):
                    if lid != skip and (px - x) ** 2 + (py - y) ** 2 < r * r: return True
        return False
    def put(gr, pts, lid):
        for x, y in pts: gr.setdefault(gkey(x, y), []).append((x, y, lid))
    ART = []
    for r in roads:
        cs = r['geom']['coords']
        for a, b in zip(cs[:-1], cs[1:]):
            n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.5))
            for k in range(n + 1):
                ART.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, r['id']))
    for x, y, rid in ART: artgrid.setdefault(gkey(x, y), []).append((x, y, rid))
    put(grids[0], [(x, y) for x, y, _ in ART], 'art')   # 大道本身算顺街族：第一排顺街离它一个间距
    wallL = [LineString(s['geom']['coords']) for s in walls]

    def ok(x, y):
        c = cell(x, y)
        return c is not None and settle[c] and dwat[c] > 0.6
    lines = []
    def trace(x, y, fam, lid, sep, d0=None):
        out = []
        for sgn in (1, -1):
            pts = []; px, py = x, y; prev = None if d0 is None else d0 * sgn; Ltot = 0
            while True:
                v = dirv(px, py, fam, prev)
                if v is None: break
                if prev is None: v = v * sgn
                mx, my = px + v[0] * P['step'] / 2, py + v[1] * P['step'] / 2
                v2 = dirv(mx, my, fam, v)
                if v2 is None: break
                nx, ny = px + v2[0] * P['step'], py + v2[1] * P['step']
                if not ok(nx, ny): break
                if any(Wl.distance(Point(nx, ny)) < 0.4 for Wl in wallL): break
                if Ltot > 1.5 and near(artgrid, nx, ny, 0.7): pts.append((nx, ny)); break   # 碰到大道：T 字口
                if Ltot > 1.0 and near(grids[fam], nx, ny, sep * 0.48, skip=lid): break
                pts.append((nx, ny)); prev = v2; px, py = nx, ny; Ltot += P['step']
                if Ltot > 400: break
            out.append(pts)
        pts = out[1][::-1] + [(x, y)] + out[0]
        return pts
    def snap_end(pts, lid):
        # 端头差一点就接上别的街/大道：顺手接上（T 字口）
        for end in (0, -1):
            x, y = pts[end]; best = None
            k = gkey(x, y)
            for gr in (artgrid, grids[0], grids[1]):
                for a in (-2, -1, 0, 1, 2):
                    for b in (-2, -1, 0, 1, 2):
                        for (qx, qy, ql) in gr.get((k[0] + a, k[1] + b), ()):
                            if ql == lid: continue
                            d = math.hypot(qx - x, qy - y)
                            if 0.2 < d < P['snap'] and (best is None or d < best[0]): best = (d, qx, qy)
            if best:
                if end == 0: pts.insert(0, (best[1], best[2]))
                else: pts.append((best[1], best[2]))
        return pts
    # 种子：横街（族 1）从大道上每隔 branch_sep 分出去
    from collections import deque
    Q = deque()
    for r in roads:
        ls = LineString(r['geom']['coords']); n = int(ls.length / P['branch_sep'])
        for k in range(n + 1):
            p = ls.interpolate((k + 0.5) * P['branch_sep'] if n else ls.length / 2)
            Q.append((p.x, p.y, 1))
    seen = 0
    def run_queue():
        nonlocal seen
        while Q:
            x, y, fam = Q.popleft()
            sep = P['along_sep'] if fam == 0 else P['branch_sep']
            if not ok(x, y) or near(grids[fam], x, y, sep * 0.9): continue
            lid = len(lines)
            pts = trace(x, y, fam, lid, sep)
            Ld = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:]))
            if Ld < P['min_len']: continue
            put(grids[fam], pts, lid)
            lines.append(dict(fam=fam, pts=pts, seed=(x, y)))
            # 沿新线两侧撒下一族/同族种子
            step = P['branch_sep'] if fam == 0 else P['along_sep']
            acc = 0
            for a, b in zip(pts[:-1], pts[1:]):
                acc += math.hypot(b[0] - a[0], b[1] - a[1])
                if acc >= step:
                    acc = 0
                    Q.append((b[0], b[1], 1 - fam))
                    v = dirv(b[0], b[1], fam, None)
                    if v is not None:
                        nrm = np.array([-v[1], v[0]])
                        for s_ in (1, -1): Q.append((b[0] + nrm[0] * sep * s_, b[1] + nrm[1] * sep * s_, fam))
    run_queue()
    # 没有大道够得着的有人区：补种子（从最近已有街接出去）
    for it in range(3):
        cover = np.zeros_like(settle)
        for ln in lines:
            for x, y in ln['pts'][::4]:
                c = cell(x, y)
                if c: cover[max(0, c[0] - 12):c[0] + 12, max(0, c[1] - 12):c[1] + 12] = True
        miss = settle & ~cover & (occ > 0)
        lab, n = ndi.label(miss)
        if not n: break
        for k in range(1, n + 1):
            ii, jj = np.nonzero(lab == k)
            if len(ii) < 6: continue
            m = len(ii) // 2; Q.append((X0 + jj[m] * R + R / 2, Y0 + ii[m] * R + R / 2, 0))
        run_queue()
    out = []
    for lid, ln in enumerate(lines):
        pts = snap_end(list(ln['pts']), lid)
        pts = pts[::2] + ([pts[-1]] if len(pts) % 2 == 0 else [])
        o = float(np.mean([old[cell(x, y)] if cell(x, y) else 0 for x, y in pts]))
        sx, sy = ln['seed']
        if ln['fam'] == 1: kind = 'cross'
        else: kind = 'street' if h01(round(sx), round(sy)) < 0.5 or near(artgrid, sx, sy, P['along_sep'] * 1.3) else 'lane'
        pieces = [pts]
        if kind == 'lane':   # 巷子断成死巷：旧区多，新区少；按世界坐标定
            pieces = []; cur = []
            for x, y in pts:
                c = cell(x, y); oo = old[c] if c else 0
                if len(cur) > 8 and h01(round(x * 2), round(y * 2), 3) < P['lane_break_new'] + P['lane_break_old'] * oo:
                    pieces.append(cur); cur = []; continue
                cur.append((x, y))
            pieces.append(cur)
        for pc in pieces:
            if len(pc) > 2: out.append(dict(kind=kind, old=round(o, 2), pts=[[round(x, 2), round(y, 2)] for x, y in pc]))
    od = os.path.join(HERE, 'city'); os.makedirs(od, exist_ok=True)
    json.dump(dict(rules=P, note='世界坐标；全城一张网，街区只裁窗口（cs31）', streets=out),
              open(os.path.join(od, 'streets.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    print('streets', len(out), Counter(s['kind'] for s in out))
    # 预览
    from PIL import Image, ImageDraw
    S = 4; im = Image.new('RGB', (NX * R * S // 1 if False else int((X1 - X0) * S), int((Y1 - Y0) * S)), (90, 120, 140))
    dr = ImageDraw.Draw(im)
    lm = Image.fromarray((landm * 255).astype('uint8')).resize(im.size)
    im.paste((222, 205, 170), mask=lm)
    st = Image.fromarray((settle * 255).astype('uint8')).resize(im.size); im.paste((236, 220, 188), mask=st)
    T_ = lambda p: ((p[0] - X0) * S, (p[1] - Y0) * S)
    for M in marks:
        if M.intersects(Polygon([(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])): dr.polygon([T_(p) for p in M.exterior.coords], fill=(190, 160, 120))
    col = {'street': (120, 80, 50), 'lane': (160, 120, 90), 'cross': (60, 90, 150)}
    for s in out: dr.line([T_(p) for p in s['pts']], fill=col[s['kind']], width=2 if s['kind'] != 'lane' else 1)
    for r in roads: dr.line([T_(p) for p in r['geom']['coords']], fill=(200, 30, 30), width=5)
    for s in walls: dr.line([T_(p) for p in s['geom']['coords']], fill=(40, 40, 40), width=4)
    for q, (bx, by) in (('nangang', (445, 418)), ('jinjiao', (440, 210))):
        dr.rectangle([T_((bx, by)), T_((bx + 128, by + 144))], outline=(0, 160, 0), width=3)
    im.save(os.path.join(HERE, 'out', 'city_streets.jpg'), quality=85)


if __name__ == '__main__':
    main()
