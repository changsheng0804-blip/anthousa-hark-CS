"""CS 线 · /goal 3 项 2：地标只有一个来源。
上游规格（tools/landmark_registry.py + tools/landmarks/*.json）里的每一座固定地标，在瓦片页（docs/living/tiles/places.json）里都要有：
  ① 位置差 ≤ 8 像素（规格坐标是干山页的像素，干山页框是世界格 (400,356)，瓦片原点是 meta.json 的 origin，同一个 14.21875 像素/格）；
  ② 建成年（built）一致，毁掉/到期（until）一致；
  ③ 中文名一致。
瓦片里多出来的地标分三类：规格卡没有、但底账（world.json）有 = 「只有底账」；底账也没有 = 「CS 线自己的」→ 必须列进「待上游收录」。
画在瓦片画布外面的规格地标单列「画布外」（瓦片原点之外没有地，补不上）。
用法：python3 tools/cs/check_landmark_src.py        退出码 0 = 全过；--list 只列清单不判。 ——Hark（CS线）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import landmark_registry as R
T = os.path.join(ROOT, 'docs', 'living', 'tiles')
M = json.load(open(os.path.join(T, 'meta.json'))); P = json.load(open(os.path.join(T, 'places.json')))
W = json.load(open(os.path.join(ROOT, 'world.json')))
S = M['scale']; OX, OY = M['origin']; XB = (400, 356)         # 干山页的世界框左上角（格）
CW, CH = M['grid'][0] * M['tile_px'], M['grid'][1] * M['tile_px']
TOL = 8
tile = {l['id']: l for l in P['landmarks']}
PEND = json.load(open(os.path.join(ROOT, 'tools', 'cs', 'factory', 'lm_pending.json')))
world = {s['id']: s for s in W['structures']}
bad, off, notes = [], [], []
n_ok = 0
for sid, sp, it in sorted(R.fixed('xerolophos'), key=lambda t: t[2]['key']):
    k = it['key']; x = (XB[0] - OX) * S + it['xy'][0]; y = (XB[1] - OY) * S + it['xy'][1]
    if not (0 <= x < CW and 0 <= y < CH):
        off.append(f'{k}（{it["name_zh"]}）规格点落在瓦片画布外 ({x:.0f},{y:.0f})')
        if k not in PEND['off_canvas']: bad.append(f'{k} 画布外，又没登记进 lm_pending.json 的 off_canvas')
        continue
    t = tile.get(k)
    if not t: bad.append(f'{k}（{it["name_zh"]}）规格有，瓦片里没有'); continue
    d = ((t['x'] - x) ** 2 + (t['y'] - y) ** 2) ** 0.5; ok = True
    if d > TOL: bad.append(f'{k} 位置差 {d:.0f} 像素 > {TOL}（瓦片 {t["x"]},{t["y"]}，规格 {x:.0f},{y:.0f}）'); ok = False
    ws = world.get(k) or {}
    if 'built' in it and ws.get('built') != it['built'] and t.get('built') != it['built']:
        bad.append(f'{k} 建成年：规格 {it["built"]}，瓦片/底账 {t.get("built", ws.get("built"))}'); ok = False
    if 'built' in it and t.get('built') != it['built']:
        bad.append(f'{k} 瓦片没有带规格的建成年 built={it["built"]}'); ok = False
    if 'until' in it and t.get('until') != it['until']:
        bad.append(f'{k} 到期年：规格 {it["until"]}，瓦片 {t.get("until")}'); ok = False
    if t['name'] != it['name_zh']: bad.append(f'{k} 名字：规格「{it["name_zh"]}」，瓦片「{t["name"]}」'); ok = False
    n_ok += ok
for k, t in tile.items():
    if t.get('built') is None and t.get('src') != 'cs': bad.append(f'{k} 瓦片没有建成年（页面按建成年决定哪年亮标记）')
spec_keys = {it['key'] for _, _, it in R.fixed('xerolophos')}
only_ledger, cs_only = [], []
for k, t in tile.items():
    if k in spec_keys: continue
    (only_ledger if k in world else cs_only).append(f'{k}（{t["name"]}）')
    if k not in world and k not in PEND['cs_only']: bad.append(f'{k} 是 CS 线自己的地标，又没登记进 lm_pending.json 的 cs_only（悄悄留着不行）')

# ---- /goal 3 项 3b：轮廓 + 阶段（建成那一年画面真的变了）----
# ① 轮廓：规格有 poly 的，瓦片管线用的底账地基（world.json 的 geom，换算成瓦片像素）和规格 poly 的重叠率 IoU ≥ 0.9；规格没写 poly 的，底账地基中心离规格点 ≤ 24 像素
# ② 阶段：规格/底账的建成年 b，烤好的年份里「b 之前最近一年」→「第一个 ≥ b 的年份」，地基里的画面要变（平均色差 ≥ 6/255）；
#    建成前的两个烤好的年份，地基里的画面都和建成后不一样（≥6）——地标不能提前画出来；建成前地基上可以有房子（运水人蓄水池 54 年建，50 年那块地上是民房，建池时拆）。读的是烤好的级 0 瓦片，不是配置。
import numpy as np
from PIL import Image
from shapely.geometry import Polygon
YS = M['years']; AL = M.get('alias', {}); TP = M['tile_px']
def tile_px(Y, tx, ty):
    o = AL.get(f'{Y}/0', {}).get(f'{tx}_{ty}'); y2 = o if o is not None else str(Y)
    f = os.path.join(T, y2, '0', f'{tx}_{ty}.webp')
    return np.asarray(Image.open(f).convert('RGB'), dtype=np.int16) if os.path.exists(f) else None
def crop(Y, x0, y0, x1, y1):
    out = np.zeros((y1 - y0, x1 - x0, 3), np.int16)
    for ty in range(y0 // TP, (y1 - 1) // TP + 1):
        for tx in range(x0 // TP, (x1 - 1) // TP + 1):
            t = tile_px(Y, tx, ty)
            if t is None: continue
            a, b = max(x0, tx * TP), max(y0, ty * TP); c, d = min(x1, tx * TP + TP), min(y1, ty * TP + TP)
            out[b - y0:d - y0, a - x0:c - x0] = t[b - ty * TP:d - ty * TP, a - tx * TP:c - tx * TP]
    return out
shape_bad = []; stage_rows = []
from PIL import ImageDraw
for sid, sp, it in sorted(R.fixed('xerolophos'), key=lambda t: t[2]['key']):
    k = it['key']; ws = world.get(k)
    if not ws: continue
    led = Polygon([((px - OX) * S, (py - OY) * S) for px, py in ws['geom']['coords']])
    if not (0 <= led.centroid.x < CW and 0 <= led.centroid.y < CH): continue
    if 'poly' in it:
        sx, sy = (XB[0] - OX) * S, (XB[1] - OY) * S
        spp = Polygon([(a + sx, b + sy) for a, b in it['poly']])
        iou = led.intersection(spp).area / max(1e-9, led.union(spp).area)
        if iou < 0.9: shape_bad.append(f'{k} 轮廓：底账地基和规格 poly 的 IoU {iou:.2f} < 0.9')
        else: notes.append(f'{k} 轮廓 IoU {iou:.2f}')
    else:
        x = (XB[0] - OX) * S + it['xy'][0]; y = (XB[1] - OY) * S + it['xy'][1]
        from shapely.geometry import Point
        dd = led.distance(Point(x, y))      # 水渠桥这种长条，规格点只是它上面的一点：点到地基的距离
        if dd > 24: shape_bad.append(f'{k} 轮廓：规格点离底账地基 {dd:.0f} 像素 > 24')
    b = it.get('built', ws.get('built'))
    if b is None: continue
    b = int(b); bx0, by0, bx1, by1 = [int(v) for v in led.bounds]; bx0 -= 3; by0 -= 3; bx1 += 3; by1 += 3
    mask = Image.new('L', (bx1 - bx0, by1 - by0), 0); ImageDraw.Draw(mask).polygon([(a - bx0, c - by0) for a, c in led.exterior.coords], fill=1); m = np.asarray(mask, bool)
    after = next((y for y in YS if y >= b), None); before = [y for y in YS if y < b]
    if after is None or not before: stage_rows.append(f'{k} 建成 {b}：烤好的年份里没有「之前」一年可比（{YS[0]} 年起就有）'); continue
    pre, a_ = before[-1], after
    d = lambda y1, y2: float(np.abs(crop(y1, bx0, by0, bx1, by1) - crop(y2, bx0, by0, bx1, by1)).sum(-1)[m].mean() / 3)
    TH = 3 if 'line' in sp else 6   # 水渠桥是一条细带（规格里 line），画面变化淡，门槛 3；其余 6
    dd = d(pre, a_); stage_rows.append(f'{k} 建成 {b}：{pre}→{a_} 年地基里色差 {dd:.1f}')
    if dd < TH: shape_bad.append(f'{k} 阶段：建成年 {b}，{pre}→{a_} 年地基里画面几乎没变（色差 {dd:.1f} < {TH}）')
    if len(before) >= 2:
        d0 = d(before[-2], a_); stage_rows[-1] += f'；{before[-2]}→{a_} 色差 {d0:.1f}'
        if d0 < TH: shape_bad.append(f'{k} 阶段：{before[-2]} 年地基里的画面和建成后（{a_} 年）几乎一样（色差 {d0:.1f} < 6），地标像是提前画出来了')
for b_ in shape_bad: bad.append(b_)
print('轮廓/阶段：' + '；'.join(stage_rows))
print(f'规格固定地标 {len(spec_keys)} 座：全对 {n_ok}，画布外 {len(off)}，不对 {len(bad)} 条')
for b in bad: print('❌', b)
for o in off: print('⚠️ 画布外：', o)
print(f'瓦片多出来的 {len(only_ledger) + len(cs_only)} 座：只有底账（规格卡没有）{len(only_ledger)} 座，CS 线自己的（底账也没有）{len(cs_only)} 座')
print('  只有底账：', '、'.join(only_ledger)); print('  CS 线自己的（待上游收录）：', '、'.join(cs_only) or '无')
sys.exit(0 if '--list' in sys.argv or not bad else 1)
