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
print(f'规格固定地标 {len(spec_keys)} 座：全对 {n_ok}，画布外 {len(off)}，不对 {len(bad)} 条')
for b in bad: print('❌', b)
for o in off: print('⚠️ 画布外：', o)
print(f'瓦片多出来的 {len(only_ledger) + len(cs_only)} 座：只有底账（规格卡没有）{len(only_ledger)} 座，CS 线自己的（底账也没有）{len(cs_only)} 座')
print('  只有底账：', '、'.join(only_ledger)); print('  CS 线自己的（待上游收录）：', '、'.join(cs_only) or '无')
sys.exit(0 if '--list' in sys.argv or not bad else 1)
