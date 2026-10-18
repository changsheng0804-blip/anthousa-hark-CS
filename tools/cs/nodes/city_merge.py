"""CS 线 · 全城底稿（2026-10-18，主人「可以」：路网改成全城一次长、分区只裁）
把 9 个街区的 frame/houses_street/houses_geom/streets 按各自框的偏移拼成一张全城底稿 docs/living/city/，
框 = 瓦片的全城框（meta.json origin + grid×tile_units）。重叠处归 owner_order 里靠前的街区（和 tile_bake 的 OWN 同一条规则）：
房子、街按中心点落在哪个街区的「归属区」决定，结构和后建地标按 id 去重。之后 build.py city → net.py city → water.py city。
——Hark（CS线）"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIV = os.path.join(ROOT, 'docs', 'living'); M = json.load(open(os.path.join(LIV, 'tiles', 'meta.json')))
S = M['scale']; X0, Y0 = M['origin']; TU = M['tile_units']; CW, CH = M['grid'][0] * TU, M['grid'][1] * TU
order = M['owner_order']; boxes = {q: json.load(open(os.path.join(LIV, q, 'frame.json')))['frame'] for q in order}
def owner(xl, yl):   # 底账坐标 → 归属街区
    for q in order:
        x, y, w, h = boxes[q]
        if x <= xl < x + w and y <= yl < y + h: return q
structs, seen, houses, hid, late, streets, pal = [], set(), [], set(), {}, [], None
for q in order:
    Q = os.path.join(LIV, q); fr = json.load(open(os.path.join(Q, 'frame.json'))); x0, y0 = fr['frame'][:2]
    ox, oy = (x0 - X0) * S, (y0 - Y0) * S; mv = lambda p: [round(p[0] + ox, 1), round(p[1] + oy, 1)]
    for s in fr['structures']:
        if s['id'] in seen: continue
        seen.add(s['id']); s = dict(s)
        if 'pts' in s: s['pts'] = [mv(p) for p in s['pts']]
        if 'xy' in s and s['xy']: s['xy'] = mv(s['xy'])
        structs.append(s)
    HS = json.load(open(os.path.join(Q, 'houses_street.json')))
    for h in HS['houses']:
        p = h[4]; cx, cy = sum(p[0::2]) / 4, sum(p[1::2]) / 4
        if h[0] in hid or owner(x0 + cx / S, y0 + cy / S) != q: continue
        hid.add(h[0]); h = list(h); h[4] = [round(v + (ox if i % 2 == 0 else oy), 1) for i, v in enumerate(p)]; houses.append(h)
    for k, v in HS.get('late', {}).items():
        if k not in late: late[k] = {**v, 'p': [mv(p) for p in v['p']]}
    for st in json.load(open(os.path.join(Q, 'streets.json'))):
        cx, cy = (st[0] + st[2]) / 2, (st[1] + st[3]) / 2
        if owner(x0 + cx / S, y0 + cy / S) != q: continue
        st = list(st); st[0] += ox; st[2] += ox; st[1] += oy; st[3] += oy; streets.append([round(v, 1) if isinstance(v, float) else v for v in st])
    if pal is None: pal = json.load(open(os.path.join(Q, 'houses_geom.json')))['pal']
O = os.path.join(LIV, 'city'); os.makedirs(O, exist_ok=True)
json.dump({'frame': [X0, Y0, CW, CH], 'scale': S, 'structures': structs}, open(os.path.join(O, 'frame.json'), 'w'), ensure_ascii=False)
json.dump({'houses': houses, 'late': late, 'pop': {}, 'unplaced': []}, open(os.path.join(O, 'houses_street.json'), 'w'), separators=(',', ':'))
json.dump({'pal': pal, 'H': []}, open(os.path.join(O, 'houses_geom.json'), 'w'))
json.dump(streets, open(os.path.join(O, 'streets.json'), 'w'), separators=(',', ':'))
print('city', [X0, Y0, CW, CH], 'structures', len(structs), 'houses', len(houses), 'late', len(late), 'streets', len(streets))
