#!/usr/bin/env python3
"""合流①检查：全城生成型地标（谭线 v31 卡）——①每座都过严格不压路 ②被并入的邻居都记在 cleared_cs.json、拆除年=地标开工年
③墓地都在创城者城墙外、其它都在墙内 ④vec 每栋房都有底账 id 且在 world.json 里。——Hark（CS线）"""
import json, os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'factory'))
import landmarks_city as L
R = L.ROOT; bad = []
W = {h['id'] for h in json.load(open(os.path.join(R, 'world.json')))['houses']}
C = json.load(open(os.path.join(L.OUT, 'cleared_cs.json')))['cleared']; CI = {c['id']: c for c in C}
n = 0
for q in L.QS:
    HS = json.load(open(os.path.join(L.LIV, q, 'houses_street.json')))['houses']; ST = json.load(open(os.path.join(L.LIV, q, 'streets.json')))
    by = {h[0]: h for h in HS}
    for h in HS:
        if isinstance(h[9], str) and h[9][3:] in L.KINDS:
            n += 1; wx, wy = L.to_world(q, *L.ctr(h)); out = wx < L.wall_world_x(wy)
            if not L.ok_strict(h, ST): bad.append(f'{q} h{h[0]} {h[9]} 压路')
            if (h[9] == 'lm:cemetery') != out: bad.append(f'{q} h{h[0]} {h[9]} 墙内外不对')
        if len(h) > 15 and h[13] == 'merged' and h[15] in L.KINDS:
            c = CI.get('h%d' % h[0])
            if not c or c['year'] != h[3]: bad.append(f'{q} h{h[0]} 并入未记或年份不符')
nid = miss = 0
for f in glob.glob(os.path.join(L.OUT, 'vec', '*.json')):
    for r in json.load(open(f))['h']:
        nid += 1
        if len(r) < 6 or r[5] not in W: miss += 1
if miss: bad.append(f'vec 缺 id {miss}/{nid}')
print(f'地标 {n} 座，并入 {len(C)} 栋，vec {nid} 栋带 id')
print('\n'.join('❌ ' + b for b in bad) or '✅ 全过'); sys.exit(1 if bad else 0)
