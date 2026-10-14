"""CS 线 · /goal 2 项 3：飞行落点表。python3 places.py → docs/living/tiles/places.json
地标 = 九块 city.json 里的 landmarks（同 id 取第一块，各块给的世界坐标应一致，差 >3 px 就报错）；
事件 = 编年史里的大事（48 年南港大火 → 看 50 年那张画）；九块中心 = 这一块「归它的」60 年房子的中位点，再吸到最近的一栋房子上（框中心在角湾、墙外这种块上是空海，飞过去落在水里；框重叠带归 tile_bake ORDER 里靠前的那块）。
坐标都是瓦片页的 0 级像素（和 meta.json 的 quarters 同一套）。只读，不碰底账。——Hark（CS线）"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lm_src import spec as _spec   # /goal 3：上游规格卡里的地标，名字、位置、建成年、到期年一律从规格读
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
L = os.path.join(ROOT, 'docs', 'living'); M = json.load(open(os.path.join(L, 'tiles', 'meta.json')))
NZ = json.load(open(os.path.join(HERE, 'city', 'names_zh.json')))
FALLBACK = {'warehouse_horn': '金角仓库'}   # city.json 只有英文名、names_zh 里又没有的
QN = {'nangang': '南港', 'jinjiao': '金角岸', 'gucheng': '古城', 'siqiu': '第四丘', 'dongjia': '东岬', 'xipo': '西坡', 'qiangwai': '墙外', 'jiaowan': '角湾', 'nanan': '南岸'}
LS = _spec(); WS = {t['id']: t for t in json.load(open(os.path.join(ROOT, 'world.json')))['structures']}
lm = {}; bad = []
for q in M['owner_order']:
    bx, by, bw, bh = M['quarters'][q]
    for l in json.load(open(os.path.join(L, q, 'city.json')))['landmarks']:
        if l['id'].startswith('homes_'): continue          # 「东岬」「南岸」这种居住区标记不是地标，用九块中心代替
        x, y = bx + l['xy'][0], by + l['xy'][1]
        if l['id'] in lm:
            if abs(lm[l['id']]['x'] - x) > 3 or abs(lm[l['id']]['y'] - y) > 3: bad.append((l['id'], q))
            continue
        d = dict(id=l['id'], name=NZ.get(l['id']) or FALLBACK.get(l['id']) or l['name'], x=round(x), y=round(y), q=q)
        if l['id'] in LS:
            sp = LS[l['id']]; d.update(name=sp['name'], x=round(sp['tile_xy'][0]), y=round(sp['tile_xy'][1]), src='spec')
            b = sp['built'] if sp['built'] is not None else WS.get(l['id'], {}).get('built')   # 规格卡没写建成年就用底账的
            if b is not None: d['built'] = b
            if sp['until'] is not None: d['until'] = sp['until']
        else:
            d['src'] = 'ledger' if l['id'] in WS else 'cs'; ws = WS.get(l['id'], {})
            if ws.get('built') is not None: d['built'] = ws['built']
            if ws.get('destroyed') is not None: d['until'] = ws['destroyed']
        lm[l['id']] = d
def heart_of(q):
    import statistics
    order = M['owner_order']; bx, by, bw, bh = M['quarters'][q]
    HJ = json.load(open(os.path.join(L, q, 'houses_street.json')))['houses']; pts = []
    for r in HJ:
        if r[1] > 60 or r[3] <= 60: continue
        p = r[4]; x = bx + sum(p[0::2]) / 4; y = by + sum(p[1::2]) / 4
        if any(M['quarters'][e][0] < x < M['quarters'][e][0] + M['quarters'][e][2] and M['quarters'][e][1] < y < M['quarters'][e][1] + M['quarters'][e][3] for e in order[:order.index(q)]): continue
        pts.append((x, y))
    mx, my = statistics.median(a for a, _ in pts), statistics.median(b for _, b in pts)
    x, y = min(pts, key=lambda t: (t[0] - mx) ** 2 + (t[1] - my) ** 2); return round(x), round(y)
# /goal 3 项 7：事件 = chron_events.py 从编年史生成的 events.json（58 件），show_year = 烤好的年份里 ≥ 事件年的第一个（48 年火灾 → 看 50 年那张）
EVS = []
for v in json.load(open(os.path.join(L, 'tiles', 'events.json')))['events']:
    sy = next((y for y in M['years'] if y >= v['year']), M['years'][-1])
    EVS.append(dict(id=v['id'], name=v['name'], kind=v['kind'], year=v['year'], show_year=sy, x=v['x'], y=v['y'], z=v['z'], text=v['text'], off=v['off']))
out = dict(landmarks=list(lm.values()),
           quarters=[dict(q=q, name=QN[q], x=heart_of(q)[0], y=heart_of(q)[1]) for q in M['owner_order']],
           events=EVS)
json.dump(out, open(os.path.join(L, 'tiles', 'places.json'), 'w'), ensure_ascii=False, indent=0)
print(len(out['landmarks']), '座地标', len(out['quarters']), '块中心', len(out['events']), '件事', '坐标不一致:', bad)
sys.exit(1 if bad else 0)
