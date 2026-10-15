#!/usr/bin/env python3
"""/goal 4 G4 检查：狄奥多西广场(57)、大宁芙泉(44)、梅塞柱廊 分期出现。读 vec（页面真正画的那份），不读生成器的中间件。
  ① epic_stage.json 的年份 = world.json（built 不自编）；每行都进了 vec（按 id 对上）。
  ② 建成前没有成品：开工年-1 这一年，这三处在 vec 里一个部件都不画。
  ③ 建成前后各一年画面不同：开工年-1 与 开工年+1 的「在画的部件集」不同。
  ④ 分期：广场 工地年（落成前）部件集 ≠ 落成后；柱廊 立架年 ≠ 落成年；狄奥多西柱 每年部件集不同，直到落成年。
  ⑤ 大宁芙泉 水面从 net_water 出水年起。
  ⑦ 帝国中心 8 座按底账 phases 分期（年份只用 phases、每期画面变、整座落成前盖住栅格成品、落成后露出、不出脚印、不压别的史诗）。
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
    fr_ = f.get('frame', f['finish'])   # 454707e：59 起架 = 铺地、柱廊起墙
    chk(not any(h for h in [VEC.get('epic:forum_theodosius')] if h and any(p[0] == 1 and p[3] < fr_ for p in h[4] if len(p) > 4)), f'④ 广场 柱廊/铺面在工地年不画（边线都从起架年 {fr_} 起）')
    ys = f['column_years']; CR = f['column_parts']; FR = ['epic:forum_theodosius']; cs = [sig(FR, y, CR) for y in ys]   # e45f0ab 起柱子只按分期年长（57/60/64）
    chk(ys == sorted({q['year'] for q in ST['forum_theodosius']['phases']}) and all(cs[i] != cs[i + 1] for i in range(len(cs) - 1)), f'④ 狄奥多西柱 只在分期年 {ys} 长高（{[len(c) for c in cs]}）')
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

from shapely.ops import unary_union
# ⑦ 帝国中心分期（底账 structures[].phases，谭线 fbc65d4）：读 vec 里 'epic:<id>' 这一行
INF = 9999
PH = [e for e in W['structures'] if e.get('phases')]
chk(len(PH) >= 8, f'⑦ world.json 里带 phases 的结构 {len(PH)} 座（engine/build_all.py 生成的 world.json 已含分期）')
GM = M['grid']; TPX0 = M['tile_px']
def in_map(e):
    g = e['geom']; cs = [g['coords']] if g['type'] == 'point' else g['coords']; xs = [(c[0] - X0) * S for c in cs]; ys = [(c[1] - Y0) * S for c in cs]
    return max(xs) > 0 and min(xs) < GM[0] * TPX0 and max(ys) > 0 and min(ys) < GM[1] * TPX0
SELF = {'forum_theodosius', 'wall_founder', 'aq_great'} | {e['id'] for e in W['structures'] if e['type'] == 'harbor'}
for e in PH:
    k = e['id']; i = 'epic:' + k; h = VEC.get(i); ph = e['phases']; ys = sorted({p['year'] for p in ph}); dst = e['destroyed'] if e['destroyed'] is not None else INF
    wd = min(p['year'] for p in ph if p['stage'] == 'done' and not p.get('part'))
    chk(E.get(k, {}).get('phases') == [[p['year'], p['stage'], p.get('part')] for p in ph], f'⑦ {k} epic_stage 的分期 = world.json')
    ids = [j for j in VEC if j == i or j.startswith(i + ':')]
    if not in_map(e): chk(not ids, f'⑦ {k} 整座在图外，不画'); continue
    if k in SELF:   # 自己画成品的（广场、港、城墙、水道）：年份只用分期年、开工前不画、每期画面变、完工后成品一直画
        chk(bool(ids), f'⑦ {k} 进了 vec（{len(ids)} 行）')
        yrs = {v for j in ids for p in VEC[j][4] for v in p[3:5]} | {VEC[j][0] for j in ids}; extra = yrs - set(ys) - {INF, dst}
        chk(not extra, f'⑦ {k} 部件年份段只用底账的分期年 {ys}' + (f'（多出 {sorted(extra)}）' if extra else ''))
        chk(not sig(ids, ys[0] - 1) and bool(sig(ids, ys[0])), f'⑦ {k} {ys[0]-1} 年不画、{ys[0]} 年（开工）起画')
        seq = [sig(ids, y) for y in ys]
        chk(all(seq[j] != seq[j + 1] for j in range(len(seq) - 1)), f'⑦ {k} 每个分期年画面都变（{ys}：{[len(x) for x in seq]} 个部件）')
        chk(bool(sig(ids, wd + 5)), f'⑦ {k} 完工后成品一直画（{wd + 5} 年 {len(sig(ids, wd + 5))} 个部件；栅格里没有这些成品）')
        continue
    chk(h is not None, f'⑦ {k} 进了 vec')
    if not h: continue
    yrs = {v for p in h[4] for v in p[3:5]}; extra = yrs - set(ys) - {INF, dst}
    import re   # 分期原文里写明的逐年区间（斑岩柱「2—4 年各加两节」）也算底账年份
    for p in ph:
        for a, b in re.findall(r'(\d+)\s*[—–-]\s*(\d+)\s*年', p.get('note', '')): extra -= set(range(int(a), int(b) + 1))
    chk(not extra, f'⑦ {k} 部件年份段只用底账的分期年 {ys}' + (f'（多出 {sorted(extra)}）' if extra else ''))
    chk(not sig([i], ys[0] - 1), f'⑦ {k} {ys[0]-1} 年（开工前）不画')
    seq = [sig([i], y) for y in ys]
    chk(all(seq[j] != seq[j + 1] for j in range(len(seq) - 1)), f'⑦ {k} 每个分期年画面都变（{ys}：{[len(x) for x in seq]} 个部件）')
    if e['geom']['type'] == 'polygon':
        P = Polygon([((x - X0) * S, (y - Y0) * S) for x, y in e['geom']['coords']]).buffer(0)
        cov = [p for p in h[4] if p[0] == 0 and p[3] == ys[0] and p[4] == wd]
        C = Polygon(list(zip(cov[0][1][0::2], cov[0][1][1::2]))).buffer(0) if cov else None
        chk(bool(C) and C.buffer(0.6).contains(P.difference(unary_union([q for eid, q, eb, ee in EP if eid != k and max(ys[0], eb) < min(wd, ee)])) if True else P) and C.difference(P.buffer(P.length * 0.02 + 4)).area < 1, f'⑦ {k} 整座落成前有一块盖住脚印、不超出脚印 2%+4 px（{ys[0]}–{wd}，面积 ×{(C.area / P.area) if C else 0:.2f}）把栅格成品挡住')
        live = [p for p in h[4] if p[3] <= wd < p[4]]
        chk(all(p[3] >= wd for p in live), f'⑦ {k} {wd} 年（整座 done）起只剩整座之后的部件（局部工地；营房成品由 vec 画），开工期的工地全撤（{len(live)} 个部件还画）')
        out = 0
        for p in h[4]:
            if len(p[1]) >= 6:
                Q = Polygon(list(zip(p[1][0::2], p[1][1::2]))).buffer(0)
                if Q.difference(P.buffer(P.length * 0.02 + 3)).area > 0.5: out += 1
        chk(out == 0, f'⑦ {k} 部件都在脚印里（放宽 2%+3 px），出界 {out}')
        nb = 0
        for eid, Q2, eb, ee in EP:
            if eid == k: continue
            if max(ys[0], eb) < min(wd, ee) and (C or P).difference(P).intersection(Q2).area > 2: nb += 1; bad.append(f'⑦ {k} 工地压 {eid}') if nb < 4 else None
        chk(nb == 0, f'⑦ {k} 工地期（{ys[0]}–{wd}）不压当年站着的别的史诗脚印')
    else:
        chk(bool(sig([i], wd + 5)), f'⑦ {k} 是点、栅格无小图：整座落成后柱子一直画')

# ⑧ 谭线交接 ③：港（碎石堤/码头前沿/堤头灯塔）、创城者城墙、卫队营房。年份 = world.json；不压当年房子；城墙不被街穿；堤与码头不下水
from shapely.geometry import LineString as _LS, Point as _Pt
HS = []   # 普通房子（非 epic 行）的脚印与年份
STR = []
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    v = json.load(open(f))
    for h in v.get('h', []):
        if not str(h[5]).startswith('epic:') and len(h[3]) >= 8: HS.append((Polygon(list(zip(h[3][0:8:2], h[3][1:8:2]))).buffer(0), h[0], h[1]))
    for st in v.get('s', []): STR.append(st)
def parts_poly(i, Y):
    h = VEC.get(i); out = []
    if not h: return out
    for p in h[4]:
        if p[0] == 0 and len(p[1]) >= 6 and (len(p) <= 4 or p[3] <= Y < p[4]): out.append(Polygon(list(zip(p[1][0::2], p[1][1::2]))).buffer(0))
    return out
TPX = M['tile_px']; WC = M['water_cell']; WN = M['water_cells_n']; _wgc = {}
def wat(x, y, K=60):
    tx, ty = int(x // TPX), int(y // TPX); k = (tx, ty)
    if k not in _wgc:
        f = os.path.join(T, 'vec', f'{tx}_{ty}.json'); _wgc[k] = (json.load(open(f)).get('wg', {}) if os.path.exists(f) else {}).get(str(K))
    g = _wgc[k]; i, j = int((x - tx * TPX) // WC), int((y - ty * TPX) // WC)
    return bool(g) and 0 <= i < WN and 0 <= j < WN and g[j * WN + i] == '1'
for k in ('wall_founder', 'barracks_gate', 'harbor_julian', 'harbor_theodosius', 'harbor_neorion', 'aq_great'):
    ids = [i for i in VEC if i == 'epic:' + k or i.startswith('epic:' + k + ':')]; b = ST[k]['built']; s0 = ST[k]['phases'][0]['year'] if ST[k].get('phases') else b   # e45f0ab 起有分期：从开工年画
    chk(len(ids) > 0 and E.get(k, {}).get('built') == b, f'⑧ {k}：vec 里 {len(ids)} 行，built = world.json {b}')
    chk(min(VEC[i][0] for i in ids) == s0 and not sig(ids, s0 - 1) and sig(ids, s0), f'⑧ {k} {s0-1} 年不画、{s0} 年（开工）起画')
    Y = max(b, 60); P = [q for i in ids for q in parts_poly(i, Y)]
    if k != 'harbor_julian' and k != 'harbor_theodosius':
        hit = sum(1 for H, hb, he in HS if hb <= Y < he and any(H.intersection(q).area > 2 for q in P if q.bounds[0] - 30 < H.bounds[2] and H.bounds[0] - 30 < q.bounds[2] and q.bounds[1] - 30 < H.bounds[3] and H.bounds[1] - 30 < q.bounds[3]))
        chk(hit == 0, f'⑧ {k} {Y} 年不压房子（压了 {hit} 栋）')
wl = _LS([((x - X0) * S, (y - Y0) * S) for x, y in ST['wall_founder']['geom']['coords']])
cross = [st for st in STR if _LS([(st[0], st[1]), (st[2], st[3])]).intersects(wl)]
chk(not cross, f'⑧ 创城者城墙不被街穿过（{len(cross)} 段）')
chk(E['wall_founder']['towers'] >= 20, f'⑧ 城墙方塔 {E["wall_founder"]["towers"]} 座（每 64 px 一座）')
for k in ('harbor_julian', 'harbor_theodosius'):
    mol = [i for i in VEC if i.startswith(f'epic:{k}:mole')]; qu = [i for i in VEC if i.startswith(f'epic:{k}:quay')]
    def wet_share(ids):
        n = w = 0
        for i in ids:
            for p in VEC[i][4]:
                if p[0] == 2:
                    for a in range(0, len(p[1]), 2): n += 1; w += wat(p[1][a], p[1][a + 1])
                elif p[0] == 0 and len(p[1]) >= 6 and p[2] == '%02x%02x%02x' % (168, 158, 138):
                    c = Polygon(list(zip(p[1][0::2], p[1][1::2]))).centroid; n += 1; w += wat(c.x, c.y)
        return w / max(1, n), n
    if mol: r, n = wet_share(mol); chk(r <= 0.1, f'⑧ {k} 碎石堤落在陆带上（{n} 处，水里占 {r:.0%}）')
    if qu: r, n = wet_share(qu); chk(r <= 0.1, f'⑧ {k} 码头前沿在岸上（{n} 点，水里占 {r:.0%}）')
chk(E['harbor_julian']['moles'] > 0, f'⑧ 尤里安港有碎石堤（底账：Moles of rubble enclose a harbor）{E["harbor_julian"]["moles"]} 段')
print('\n'.join('过 ' + m for m in ok)); print('\n'.join('不过 ' + m for m in bad)); print(f'{len(ok)} 过 {len(bad)} 不过'); sys.exit(1 if bad else 0)
