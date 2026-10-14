#!/usr/bin/env python3
"""/goal 4 G4 检查：狄奥多西广场(57)、大宁芙泉(44)、梅塞柱廊 分期出现。读 vec（页面真正画的那份），不读生成器的中间件。
  ① epic_stage.json 的年份 = world.json（built 不自编）；每行都进了 vec（按 id 对上）。
  ② 建成前没有成品：开工年-1 这一年，这三处在 vec 里一个部件都不画。
  ③ 建成前后各一年画面不同：开工年-1 与 开工年+1 的「在画的部件集」不同。
  ④ 分期：广场 工地年（落成前）部件集 ≠ 落成后；柱廊 立架年 ≠ 落成年；狄奥多西柱 每年部件集不同，直到落成年。
  ⑤ 大宁芙泉 水面从 net_water 出水年起。
——Hark（CS线）"""
import json, os, glob, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); T = os.path.join(ROOT, 'docs/living/tiles')
bad = []; ok = []
def chk(c, m): (ok if c else bad).append(m)
W = json.load(open(os.path.join(ROOT, 'world.json'))); ST = {s['id']: s for s in W['structures']}
P = os.path.join(T, 'epic_stage.json')
if not os.path.exists(P): print('不过：没有 epic_stage.json'); sys.exit(1)
D = json.load(open(P)); E = D['epics']
for k in ('forum_theodosius', 'nymphaeum_maius', 'r_mese'): chk(E[k]['built'] == ST[k]['built'], f'① {k} 开工年 {E[k]["built"]} = world.json {ST[k]["built"]}')
VEC = {}
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    for h in json.load(open(f)).get('h', []):
        if str(h[5]).startswith('epic:'): VEC[h[5]] = h
rows = {r['id']: r for r in D['rows']}
miss = [i for i in rows if i not in VEC]
chk(not miss, f'① 生成的 {len(rows)} 行全进了 vec' + (f'（缺 {len(miss)}：{miss[:4]}）' if miss else ''))
def sig(ids, Y, rng=None):
    s = set()
    for i in ids:
        h = VEC.get(i)
        if not h or not (h[0] <= Y < h[1]): continue
        for j, p in enumerate(h[4]):
            if rng and not (rng[0] <= j < rng[1]): continue
            if len(p) > 4 and p[3] <= Y < p[4]: s.add((i, j))
            elif len(p) <= 4: s.add((i, j))
    return s
G = {'forum_theodosius': [i for i in VEC if i.startswith('epic:forum_theodosius')], 'nymphaeum_maius': [i for i in VEC if i.startswith('epic:nymphaeum_maius')], 'r_mese': [i for i in VEC if i.startswith('epic:mese:')]}
for k, ids in G.items():
    chk(len(ids) > 0, f'② {k}：vec 里有 {len(ids)} 行')
    if not ids: continue
    b = E[k]['built']; chk(not sig(ids, b - 1), f'② {k} {b-1} 年没有任何部件（建成前没有成品）'); a1, a0 = sig(ids, b - 1), sig(ids, b + 1)
    chk(a1 != a0 and len(a0) > 0, f'③ {k} {b-1} 年 ≠ {b+1} 年（{len(a1)} → {len(a0)} 个部件）')
f = E['forum_theodosius']; ids = G['forum_theodosius']
if ids:
    s_site, s_done = sig(ids, f['built']), sig(ids, f['finish'])
    chk(s_site != s_done and len(s_done) > len(s_site), f'④ 广场 工地年 {f["built"]} ({len(s_site)}) ≠ 落成 {f["finish"]} ({len(s_done)})')
    chk(not any(h for h in [VEC.get('epic:forum_theodosius')] if h and any(p[0] == 1 and p[3] < f['finish'] for p in h[4] if len(p) > 4)), '④ 广场 柱廊/铺面在工地年不画（边线都从落成年起）')
    ys = list(range(f['built'], f['column_done'] + 1)); CR = f['column_parts']; FR = ['epic:forum_theodosius']; cs = [sig(FR, y, CR) for y in ys]
    chk(all(cs[i] != cs[i + 1] for i in range(len(cs) - 1)), f'④ 狄奥多西柱 {ys[0]}–{ys[-1]} 年每年多一节（{[len(c) for c in cs]}）')
    chk(sig(FR, f['column_done'] - 1, CR) != sig(FR, f['column_done'], CR) and not [p for p in VEC['epic:forum_theodosius'][4][CR[0]:CR[1]] if p[2] == '7c5c3a' and p[3] <= f['column_done'] < p[4]], '④ 柱 落成后脚手架拆、立像（部件集再变一次）')
    chk(not sig(['epic:forum_theodosius:arch'], f['arch'] - 1) and sig(['epic:forum_theodosius:arch'], f['arch']), f'④ 凯旋门 {f["arch"]} 年起')
m = E['r_mese']; ids = G['r_mese']
if ids:
    chk(sig(ids, m['built']) != sig(ids, m['finish']) and len(sig(ids, m['finish'])) > len(sig(ids, m['built'])), f'④ 柱廊 立架年 {m["built"]} ({len(sig(ids, m["built"]))}) ≠ 落成 {m["finish"]} ({len(sig(ids, m["finish"]))})')
n = E['nymphaeum_maius']; ids = G['nymphaeum_maius']
if ids:
    h = VEC['epic:nymphaeum_maius']; wat = [p for p in h[4] if p[2] == '5896b0' ]
    chk(bool(wat) and all(p[3] >= n['wet'] for p in wat), f'⑤ 大宁芙泉水面从出水年 {n["wet"]} 起（{len(wat)} 段）')
# ⑥ 梅塞柱廊/路面的每个部件，在它画着的年份里不压别的史诗脚印（创城者广场、广场、宁芙泉……）
from shapely.geometry import Polygon
M = json.load(open(os.path.join(T, 'meta.json'))); S = M['scale']; X0, Y0 = M['origin']; nbad = 0; npart = 0
SKIP = {'district', 'farmland', 'wall', 'gate', 'harbor'}
EP = [(e['id'], Polygon([((x - X0) * S, (y - Y0) * S) for x, y in e['geom']['coords']]).buffer(0), e['built'], e['destroyed'] if e['destroyed'] is not None else 9999) for e in W['structures'] if e['geom']['type'] == 'polygon' and e['type'] not in SKIP]
for i, h in VEC.items():
    if not i.startswith('epic:mese:'): continue
    for p in h[4]:
        if p[0] == 2 or len(p[1]) < 6: continue
        Q = Polygon(list(zip(p[1][0::2], p[1][1::2]))).buffer(0); npart += 1
        for eid, P, eb, ee in EP:
            if max(p[3], eb) < min(p[4], ee) and Q.intersects(P) and Q.intersection(P).area > 1e-3 * max(Q.area, 1e-9): nbad += 1; bad.append(f'⑥ {i} 部件（{p[3]}–{p[4]}）压在 {eid}（{eb}）脚印里') if nbad < 6 else None
chk(nbad == 0, f'⑥ 梅塞柱廊 {npart} 个部件在画着的年份里不压别的史诗脚印')
print('\n'.join('过 ' + m for m in ok)); print('\n'.join('不过 ' + m for m in bad)); print(f'{len(ok)} 过 {len(bad)} 不过'); sys.exit(1 if bad else 0)
