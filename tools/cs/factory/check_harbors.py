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

def lines(g):
    for p in (g.geoms if hasattr(g, 'geoms') else [g]):
        if p.is_empty or p.geom_type != 'Polygon': continue
        yield list(p.exterior.coords)
        for r in p.interiors: yield list(r.coords)

def measure(Y=60):
    W = json.load(open(os.path.join(ROOT, 'world.json')))
    hs = [s for s in W['structures'] if s['type'] == 'harbor' and s['built'] <= Y and (s['destroyed'] is None or s['destroyed'] > Y)]
    polys = [Polygon(s['geom']['coords']) for s in hs]
    L = land().difference(unary_union(polys))
    out = []
    for s, p in zip(hs, polys):
        win = p.buffer(1.0)
        tot = st = run = 0.0
        for c in lines(L):
            for a, b in zip(c, c[1:]):
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if not win.contains(__import__('shapely.geometry', fromlist=['Point']).Point(m)): continue
                l = math.hypot(b[0] - a[0], b[1] - a[1]); tot += l
                if abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6: st += l; run = max(run, l)
        out.append((s['id'], tot, st / tot if tot else 0, run))
    return out

if __name__ == '__main__':
    Y = int(sys.argv[1]) if len(sys.argv) > 1 else 60; bad = 0
    for i, t, f, r in measure(Y):
        ok = f <= MAXFRAC and r <= MAXRUN; bad += not ok
        print(f'{"过" if ok else "不过"} {i}: 岸线 {t:.0f} 格，直线占比 {f:.0%}，最长直段 {r:.0f} 格')
    print('D2 方块港池:', '全过' if not bad else f'{bad} 个不过'); sys.exit(1 if bad else 0)
