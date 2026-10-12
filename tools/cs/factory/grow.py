"""CS 线 · 街区生产线（第一段：底账 → 街区数据 + 给画师的底图）
用法: python tools/cs/factory/grow.py <quarter_id> <x0> <y0> <key years...>
  从 world.json 截一个 128×144 的世界框（与城东尖角、克塞罗洛福斯同一比例），输出到 docs/living/<quarter_id>/：
  houses.json  —— 每栋房子 [id, 区, 建成, 拆毁, 页面坐标多边形]，与底账逐栋一致
  frame.json   —— 世界框、比例、框内的公共建筑（给 city.json 写地标用）
  base_<Y>.png —— 引擎底图：地形、海、港、路、公共建筑、当年站着的每一栋房子（画师照着画的「草稿」）
  mask_<Y>.png —— 房子 / 水 的掩码（自动评画用）
需要先跑 python engine/build_all.py 生成 world.json。"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from terrain import land, elevation
from shapely.geometry import box, Polygon, LineString

S = 1820 / 128.0
FW, FH = 128, 144
PW, PH = 1820, 2048
BUILD = {"palace", "forum", "church", "market", "fort", "granary", "cistern", "temple", "hippodrome", "baths",
         "monument", "column", "monastery", "barracks", "warehouse", "gate", "aqueduct_bridge"}


def main():
    qid, x0, y0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    keys = [int(k) for k in sys.argv[4:]] or [40, 50, 60]
    w = json.load(open(os.path.join(ROOT, 'world.json')))
    out = os.environ.get('GROW_OUT') or os.path.join(ROOT, 'docs', 'living', qid)
    os.makedirs(out, exist_ok=True)
    T = lambda x, y: ((x - x0) * S, (y - y0) * S)
    fr = box(x0 - 2, y0 - 2, x0 + FW + 2, y0 + FH + 2)
    dist = {d['id']: i for i, d in enumerate([s for s in w['structures'] if s['type'] == 'district'])}

    hs = []
    for h in w['houses']:
        P = Polygon(h['p'])
        if not fr.contains(P.centroid):
            continue
        pts = [round(c) for x, y in h['p'] for c in T(x, y)]
        hs.append([int(h['id'][1:]), dist.get(h['d'], 0), h['built'], h['destroyed'] if h['destroyed'] is not None else 9999, pts])
    late, struct = {}, []
    for s in w['structures']:
        g = s['geom']
        if g['type'] == 'polygon':
            G = Polygon(g['coords'])
        elif g['type'] == 'line':
            G = LineString(g['coords'])
        else:
            continue
        if not G.intersects(fr):
            continue
        c = G.centroid
        rec = {'id': s['id'], 'type': s['type'], 'name': s.get('name'), 'built': s['built'], 'destroyed': s.get('destroyed'),
               'xy': [round(v) for v in T(c.x, c.y)], 'geom': g['type'], 'width': s.get('width'),
               'pts': [[round(v) for v in T(x, y)] for x, y in (g['coords'] if g['type'] == 'line' else g['coords'])],
               'history': s.get('history', [])}
        struct.append(rec)
        if s['type'] in BUILD and s['built'] > 1 and g['type'] == 'polygon':
            late[s['id']] = {'built': s['built'], 'p': rec['pts']}
    pop = {str(e['to'] if 'to' in e else e.get('year')): e['stats']['population'] for e in w['eras'] if 'stats' in e}
    json.dump({'houses': hs, 'late': late, 'pop': pop}, open(os.path.join(out, 'houses.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'frame': [x0, y0, FW, FH], 'scale': S, 'structures': struct}, open(os.path.join(out, 'frame.json'), 'w'), ensure_ascii=False, indent=1)

    # terrain layer (shared by every year)
    L = land()
    R = 4
    lm = Image.new('L', (PW // R, PH // R), 0); dl = ImageDraw.Draw(lm)
    for g in (L.geoms if hasattr(L, 'geoms') else [L]):
        dl.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in g.exterior.coords], fill=255)
        for r in g.interiors:
            dl.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in r.coords], fill=0)
    ter = Image.new('RGB', (PW // R, PH // R)); px = ter.load(); lp = lm.load()
    for j in range(PH // R):
        for i in range(PW // R):
            x, y = x0 + i * R / S, y0 + j * R / S
            if lp[i, j]:
                e = elevation(x, y)
                ex = elevation(x + .6, y) - elevation(x - .6, y)
                ey = elevation(x, y + .6) - elevation(x, y - .6)
                sh = max(-1, min(1, -(ex + ey) * 0.08))
                base = (196 + int(e * .25), 178 + int(e * .2), 132 + int(e * .1))
                px[i, j] = tuple(max(0, min(255, int(c * (1 + sh * .18)))) for c in base)
            else:
                px[i, j] = (70, 104, 118)
    ter = ter.resize((PW, PH), Image.BILINEAR)
    stats = {}
    for Y in [0] + keys:
        im = ter.copy(); d = ImageDraw.Draw(im)
        mk = Image.new('L', (PW, PH), 0); dm = ImageDraw.Draw(mk)
        for s in struct:
            if s['built'] > Y or (s['destroyed'] is not None and s['destroyed'] <= Y):
                continue
            if s['type'] == 'harbor':
                d.polygon([tuple(p) for p in s['pts']], fill=(70, 104, 118), outline=(120, 110, 90))
                d.line([tuple(p) for p in s['pts']] + [tuple(s['pts'][0])], fill=(150, 140, 115), width=10)
                dm.polygon([tuple(p) for p in s['pts']], fill=128)
        for s in struct:
            if s['built'] > Y or (s['destroyed'] is not None and s['destroyed'] <= Y):
                continue
            if s['type'] == 'road':
                wd = max(10, int((s['width'] or 2) * S))
                d.line([tuple(p) for p in s['pts']], fill=(222, 206, 168), width=wd, joint='curve')
            elif s['type'] in ('wall', 'seawall', 'aqueduct'):
                d.line([tuple(p) for p in s['pts']], fill=(140, 120, 95), width=int(1.6 * S))
        if Y > 0:
            for h in hs:
                if h[2] <= Y < h[3]:
                    p = h[4]; P = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
                    d.polygon(P, fill=(178, 92, 58), outline=(110, 60, 40)); dm.polygon(P, fill=255)
                elif h[3] <= Y and h[3] == 48 and Y - 48 < 6:  # 火烧过的空地（六年后清成空地）
                    p = h[4]; P = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
                    d.polygon(P, fill=(70, 62, 55))
        for s in struct:
            if s['type'] in BUILD and s['geom'] == 'polygon' and s['built'] <= Y and not (s['destroyed'] is not None and s['destroyed'] <= Y):
                d.polygon([tuple(p) for p in s['pts']], fill=(215, 210, 198), outline=(90, 80, 70))
        if Y == 0:
            im.resize((PW // 2, PH // 2)).save(os.path.join(out, 'bare.jpg'), quality=85)
        else:
            im.save(os.path.join(out, f'base_{Y}.png')); mk.save(os.path.join(out, f'mask_{Y}.png'))
            stats[Y] = sum(1 for h in hs if h[2] <= Y < h[3])
    print(qid, 'houses', len(hs), 'standing', stats, 'late', list(late), 'structures', len(struct))


_cache = {}
def _isl(L, x, y):
    from shapely.geometry import Point
    return L.contains(Point(x, y))


if __name__ == '__main__':
    main()
