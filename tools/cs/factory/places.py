"""CS 线 · /goal 2 项 3：飞行落点表。python3 places.py → docs/living/tiles/places.json
地标 = 九块 city.json 里的 landmarks（同 id 取第一块，各块给的世界坐标应一致，差 >3 px 就报错）；
事件 = 编年史里的大事（48 年南港大火 → 看 50 年那张画）；九块中心 = tile_bake 的框中心。
坐标都是瓦片页的 0 级像素（和 meta.json 的 quarters 同一套）。只读，不碰底账。——Hark（CS线）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
L = os.path.join(ROOT, 'docs', 'living'); M = json.load(open(os.path.join(L, 'tiles', 'meta.json')))
NZ = json.load(open(os.path.join(HERE, 'city', 'names_zh.json')))
FALLBACK = {'warehouse_horn': '金角仓库'}   # city.json 只有英文名、names_zh 里又没有的
QN = {'nangang': '南港', 'jinjiao': '金角岸', 'gucheng': '古城', 'siqiu': '第四丘', 'dongjia': '东岬', 'xipo': '西坡', 'qiangwai': '墙外', 'jiaowan': '角湾', 'nanan': '南岸'}
lm = {}; bad = []
for q in M['owner_order']:
    bx, by, bw, bh = M['quarters'][q]
    for l in json.load(open(os.path.join(L, q, 'city.json')))['landmarks']:
        if l['id'].startswith('homes_'): continue          # 「东岬」「南岸」这种居住区标记不是地标，用九块中心代替
        x, y = bx + l['xy'][0], by + l['xy'][1]
        if l['id'] in lm:
            if abs(lm[l['id']]['x'] - x) > 3 or abs(lm[l['id']]['y'] - y) > 3: bad.append((l['id'], q))
            continue
        lm[l['id']] = dict(id=l['id'], name=NZ.get(l['id']) or FALLBACK.get(l['id']) or l['name'], x=round(x), y=round(y), q=q)
out = dict(landmarks=list(lm.values()),
           quarters=[dict(q=q, name=QN[q], x=round(M['quarters'][q][0] + M['quarters'][q][2] / 2), y=round(M['quarters'][q][1] + M['quarters'][q][3] / 2)) for q in M['owner_order']],
           events=[dict(id='fire48', name='48 年南港大火', year=48, show_year=50, x=lm['fire_ruins']['x'], y=lm['fire_ruins']['y'], z=1.6)])
json.dump(out, open(os.path.join(L, 'tiles', 'places.json'), 'w'), ensure_ascii=False, indent=0)
print(len(out['landmarks']), '座地标', len(out['quarters']), '块中心', len(out['events']), '件事', '坐标不一致:', bad)
sys.exit(1 if bad else 0)
