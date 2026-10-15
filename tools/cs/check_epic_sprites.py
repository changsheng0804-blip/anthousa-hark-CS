#!/usr/bin/env python3
"""谭线史诗画（ep.json / ep/*.webp ← tools/cs/factory/epic_sprites.py）验收：
  ① 索引里每个文件都在；总量、单块上限（街道级预算 ≤12 MB 里它占多少）。
  ② 每座结构（图内）：开工前一年脚印里一个像素都不画；开工那年画了；每个分期年（含 part 局部落成）脚印块的画面都变。年份只读 world.json。
  ③ 竞技场四刻：完工后四种时刻的块互不相同；完工前（工地）没有观众差别也行。
  ④ 不压当年的房子：60 年，房子（vec 普通房）中心点被史诗画不透明（α>200）盖住的栋数 ≤ 上限（史诗脚印外 3 格以内的不算，那是谭线的铺地/院墙）。
——Hark（CS线）"""
import json, os, glob, sys
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, LineString, Point
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); T = os.path.join(ROOT, 'docs/living/tiles')
ok, bad = [], []
def chk(c, m): (ok if c else bad).append(m)
M = json.load(open(os.path.join(T, 'meta.json'))); S = M['scale']; X0, Y0 = M['origin']; TP = M['tile_px']
W = json.load(open(os.path.join(ROOT, 'world.json'))); ST = {s['id']: s for s in W['structures']}
p = os.path.join(T, 'ep.json')
if not os.path.exists(p): print('不过 没有 ep.json'); sys.exit(1)
D = json.load(open(p))
files = {f for seq in D['t'].values() for _, f in seq if f} | {f for seq in D['race'].values() for _, m in seq for f in m.values() if f}
miss = [f for f in files if not os.path.exists(os.path.join(T, 'ep', f))]
chk(not miss, f'① 索引的 {len(files)} 个文件都在' + (f'（缺 {len(miss)}）' if miss else ''))
sz = {f: os.path.getsize(os.path.join(T, 'ep', f)) for f in files if f not in miss}
tot = sum(sz.values()); mx = max(sz.values()) if sz else 0
chk(tot <= 8e6 and mx <= 400e3, f'① 共 {tot/1e6:.2f} MB、单块最大 {mx/1e3:.0f} KB（≤8 MB、≤400 KB；按需只下视口里当年那几块）')
IM = {}
def img(f):
    if f not in IM: IM[f] = np.asarray(Image.open(os.path.join(T, 'ep', f)).convert('RGBA'))
    return IM[f]
def at(seq, Y):
    r = None
    for y, f in seq or []:
        if y <= Y: r = f
        else: break
    return r
def wp(x, y): return ((x - X0) * S, (y - Y0) * S)
def foot(s, lw=6):
    g = s['geom']
    if g['type'] == 'polygon': return Polygon([wp(*c) for c in g['coords']]).buffer(0)
    if g['type'] == 'line': return LineString([wp(*c) for c in g['coords']]).buffer(lw)
    return Point(wp(*g['coords'])).buffer(6)
def alpha_in(P, Y, key='t'):
    """脚印 P 里，年份 Y 的史诗画不透明像素数；以及各块当年用的文件签名"""
    n = 0; sig = []
    x0, y0, x1, y1 = P.bounds
    for ty in range(max(0, int(y0 // TP)), int(y1 // TP) + 1):
        for tx in range(max(0, int(x0 // TP)), int(x1 // TP) + 1):
            f = at(D[key].get(f'{tx}_{ty}'), Y)
            if key == 'race': f = f and f.get('race')
            sig.append(f)
            if not f: continue
            a = img(f)[..., 3]
            from shapely.geometry import box
            Q = P.intersection(box(tx * TP, ty * TP, tx * TP + TP, ty * TP + TP))
            if Q.is_empty: continue
            mk = Image.new('L', (TP, TP), 0); dr = ImageDraw.Draw(mk)   # 只数多边形里面的（不是外接框）
            for g in getattr(Q, 'geoms', [Q]):
                if g.geom_type == 'Polygon' and not g.is_empty:
                    dr.polygon([(x - tx * TP, y - ty * TP) for x, y in g.exterior.coords], fill=255)
                    for r in g.interiors: dr.polygon([(x - tx * TP, y - ty * TP) for x, y in r.coords], fill=0)
            n += int(((a > 40) & (np.asarray(mk) > 0)).sum())
    return n, sig
GW, GH = M['grid'][0] * TP, M['grid'][1] * TP
for view, ids in D['views'].items():
    for k in ids:
        s = ST[k]; P = foot(s)
        if P.bounds[2] < 0 or P.bounds[0] > GW or P.bounds[3] < 0 or P.bounds[1] > GH: continue
        ph = s.get('phases') or []
        y0 = min([s['built']] + [q['year'] for q in ph])
        if y0 > -657:
            Q = P.buffer(-3) if P.area > 400 else P
            for o in W['structures']:   # 邻座当年已在画（院墙、铺地、渠桥）伸进这块脚印的，不算它
                if o['id'] != k and o['type'] not in ('district', 'farmland', 'road') and o['built'] <= y0 - 1 and (o.get('destroyed') is None or o['destroyed'] > y0 - 1) and any(o['id'] in v for v in list(D['views'].values()) + [['hippodrome']]):
                    Q = Q.difference(foot(o, 40).buffer(24))   # 城墙带塔、斜投影抬高，线状的按 40 px 算
            n0, _ = alpha_in(Q, y0 - 1) if not Q.is_empty else (0, [])
            chk(n0 == 0, f'② {k} {y0 - 1} 年（开工前）脚印里不画（{n0} px）')
        n1, _ = alpha_in(P, y0); chk(n1 > 0, f'② {k} {y0} 年（{"开工" if ph else "落成"}）起画（{n1} px）')
        ys = sorted({q['year'] for q in ph})
        if len(ys) > 1:
            sg = [alpha_in(P, y)[1] for y in ys]
            same = [ys[j + 1] for j in range(len(ys) - 1) if sg[j] == sg[j + 1]]
            chk(not same, f'② {k} 每个分期年 {ys} 画面都变' + (f'（{same} 年没变）' if same else ''))
hp = foot(ST['hippodrome']); hd = min(q['year'] for q in ST['hippodrome']['phases'] if q['stage'] == 'done' and not q.get('part'))
x0, y0, x1, y1 = hp.bounds; keys = [f'{tx}_{ty}' for ty in range(int(y0 // TP), int(y1 // TP) + 1) for tx in range(int(x0 // TP), int(x1 // TP) + 1)]
for Y in (hd, 60):
    ms = [tuple((at(D['race'].get(k_), Y) or {}).get(m) for k_ in keys) for m in ('dawn', 'filling', 'race', 'dusk')]
    chk(len(set(ms)) == 4 and all(any(x) for x in ms), f'③ 竞技场 {Y} 年 清晨/入场/开赛/散场 四刻画面各不相同')
EPF = [foot(s, 40) for s in W['structures'] if any(s['id'] in v for v in D['views'].values()) or s['id'] == 'hippodrome']
from shapely.strtree import STRtree
EPT = STRtree([f.buffer(40) for f in EPF])   # 谭线按外接框画、立面向北抬高：脚印外 40 px（约 3 格）内算贴着
Y = 60; hit = 0; near = 0; n = 0
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    for h in json.load(open(f))['h']:
        if str(h[5]).startswith('epic:') or len(h[3]) < 8 or not (h[0] <= Y < h[1]): continue
        cx, cy = sum(h[3][0:8:2]) / 4, sum(h[3][1:8:2]) / 4; tx, ty = int(cx // TP), int(cy // TP); n += 1
        fl = [at(D['t'].get(f'{tx}_{ty}'), Y), (at(D['race'].get(f'{tx}_{ty}'), Y) or {}).get('race')]
        cov = any(ff and img(ff)[min(TP - 1, int(cy - ty * TP)), min(TP - 1, int(cx - tx * TP)), 3] > 200 for ff in fl)
        if not cov: continue
        if len(EPT.query(Point(cx, cy), predicate='intersects')): near += 1
        else: hit += 1; print('  盖住', h[5] if len(h) > 5 else '', round(cx), round(cy), [x for x in fl if x])
chk(hit == 0, f'④ {Y} 年 {n} 栋房里，史诗画盖住中心的：离史诗 3 格外 {hit} 栋（须 0），贴着史诗的 {near} 栋（谭线铺地/院墙，记数）')
AQ = LineString([wp(*c) for c in ST['aq_great']['geom']['coords']])
for b_ in ('aqb_outer', 'aqb_middle', 'aqb_valley', 'nymphaeum_great'): AQ = AQ.difference(foot(ST[b_]).buffer(8))
band = AQ.buffer(3); on = 0; cov = 0
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    for h in json.load(open(f))['h']:
        if str(h[5]).startswith('epic') or len(h[3]) < 8 or not (h[0] <= Y < h[1]): continue
        cx, cy = sum(h[3][0:8:2]) / 4, sum(h[3][1:8:2]) / 4
        if not band.contains(Point(cx, cy)): continue
        on += 1; tx, ty = int(cx // TP), int(cy // TP); ff = at(D['t'].get(f'{tx}_{ty}'), Y)
        if ff and img(ff)[int(cy - ty * TP), int(cx - tx * TP), 3] > 40: cov += 1
chk(cov == 0, f'⑤ {Y} 年 大水道埋地段上的 {on} 栋房子，暗渠不画在它们身上（盖住 {cov}）')
print('\n'.join('过 ' + m for m in ok)); print('\n'.join('不过 ' + m for m in bad)); print(f'{len(ok)} 过 {len(bad)} 不过'); sys.exit(1 if bad else 0)
