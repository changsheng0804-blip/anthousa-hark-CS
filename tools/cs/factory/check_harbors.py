"""D2 方块港池检查：每个在役港池，量它周围岸线里「横平竖直的直线」占比和最长直线长度。
底账港池是矩形，挖掉后岸线四面都是直线 → 占比≈100%。过线：占比 ≤ 40%，最长直段 ≤ 12 格（底账单位）。
用法: python check_harbors.py [年=60]   退出码 0 过 / 1 不过"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'engine')); sys.path.insert(0, HERE)
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from terrain import land
MAXFRAC, MAXRUN = 0.40, 12.0

PPC = 14.21875
def measure(Y=60, carve=True):
    import numpy as np, cv2
    from shapely.geometry import Point
    from harbor_shape import shore_keep
    W = json.load(open(os.path.join(ROOT, 'world.json')))
    hs = [s for s in W['structures'] if s['type'] == 'harbor' and s['built'] <= Y and (s['destroyed'] is None or s['destroyed'] > Y)]
    polys = [Polygon(s['geom']['coords']) for s in hs]
    Lg = land().difference(unary_union(polys))
    out = []
    for s, p in zip(hs, polys):
        x0, y0, x1, y1 = p.buffer(8).bounds
        X0, Y0 = int(x0 * PPC), int(y0 * PPC); Wp, Hp = int((x1 - x0) * PPC), int((y1 - y0) * PPC)
        def ras(g):
            im = np.zeros((Hp, Wp), np.uint8)
            for q in (g.geoms if hasattr(g, 'geoms') else [g]):
                if q.is_empty or q.geom_type != 'Polygon': continue
                cv2.fillPoly(im, [np.array([[(a - x0) * PPC, (b - y0) * PPC] for a, b in q.exterior.coords], np.int32)], 1)
                for r in q.interiors: cv2.fillPoly(im, [np.array([[(a - x0) * PPC, (b - y0) * PPC] for a, b in r.coords], np.int32)], 0)
            return im > 0
        landR, harb = ras(Lg), ras(p)
        keep = shore_keep(landR, harb, X0, Y0, PPC) if carve else ~landR
        shore = (~keep).astype(np.uint8)
        cs, _ = cv2.findContours(shore, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cx, cy = (p.bounds[0] + p.bounds[2]) / 2, (p.bounds[1] + p.bounds[3]) / 2
        win = p.buffer(1.0)
        tot = st = run = 0.0
        for c in cs:
            if len(c) < 8: continue
            ap = cv2.approxPolyDP(c, 0.4 * PPC, True)[:, 0, :].astype(float) / PPC + [x0, y0]
            for a, b in zip(ap, np.vstack([ap[1:], ap[:1]])):
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if not win.contains(Point(m)): continue
                l = math.hypot(b[0] - a[0], b[1] - a[1]); tot += l
                ang = math.degrees(math.atan2(abs(b[1] - a[1]), abs(b[0] - a[0])))
                if min(ang, 90 - ang) < 5: st += l; run = max(run, l)
        out.append((s['id'], tot, st / tot if tot else 0, run))
    return out

if __name__ == '__main__':
    Y = int(sys.argv[1]) if len(sys.argv) > 1 else 60; bad = 0
    for i, t, f, r in measure(Y):
        ok = f <= MAXFRAC and r <= MAXRUN; bad += not ok
        print(f'{"过" if ok else "不过"} {i}: 岸线 {t:.0f} 格，直线占比 {f:.0%}，最长直段 {r:.0f} 格')
    print('D2 方块港池:', '全过' if not bad else f'{bad} 个不过'); sys.exit(1 if bad else 0)
