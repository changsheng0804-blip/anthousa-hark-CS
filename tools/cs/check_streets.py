"""cs29 · 按街道重排的检查：
1 重排只挪位置：houses_street.json 和底账 houses.json 一户不多一户不少，建成、拆毁年份一样；
2 不下水、不上栈桥：房子中心不在水格里，不压在栈桥上；
3 街不下水：街段中点在水里的 ≤ 1%；
4 分区跟着地块：每户都有分区；40/50/60 年都有货栈长屋（hall）；60 年远看有码头货栈、仓场的街区名，民居不写；
5 地面图每张关键年画都有；
6 街上没地方、留在原处的 ≤ 5 户；地标盖起来以后，它的地皮上不再有人家、不再有街。"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Q = os.path.join(ROOT, 'docs', 'living', q) + '/'; sc = json.load(open(Q + 'scene.json')); SL = sc.get('street_layout')
if not SL: print('no street layout, skip'); sys.exit(0)
bad = []
L0 = {h[0]: (h[2], h[3]) for h in json.load(open(Q + 'houses.json'))['houses']}
HS = json.load(open(Q + SL['houses']))['houses']; L1 = {h[0]: (h[2], h[3]) for h in HS}
# 合流①/②以后：派生表按记账清场（cleared_cs.json 地标卡、epic_cleared.json 史诗脚印）和空地新地标（id ≥ 900000）是允许的差，
# 但必须每一户都对得上账：开始年不变、结束年 = 记账的清场年；没记账的差照样红。
CLR = {}
for fn in ('cleared_cs.json', 'epic_cleared.json'):
    fp = os.path.join(ROOT, 'docs', 'living', 'tiles', fn)
    if os.path.exists(fp):
        for r in json.load(open(fp))['cleared']: CLR.setdefault(int(str(r['id']).lstrip('h')), set()).add(r['year'])
def ok_diff(k):
    a, b = L0.get(k), L1.get(k)
    if a is None: return b is not None and k >= 900000
    if b is None: return False
    return a[0] == b[0] and b[1] in CLR.get(k, ())
D = [k for k in set(L0) | set(L1) if L0.get(k) != L1.get(k)]; U = [k for k in D if not ok_diff(k)]
if U: bad.append(f'重排后户数/年份和底账不一致且没记账（底账 {len(L0)}，重排 {len(L1)}，没记账的差 {len(U)}：{sorted(U)[:8]}）')
elif D: print(f'记账清场 {len(D)} 户（都对得上 cleared_cs/epic_cleared）')
WK = (sc.get('fleet') or {}).get('walk') or sc['walk']
def wet(x, y):
    gx, gy = int(x // WK['R']), int(y // WK['R'])
    return 0 <= gx < WK['W'] and 0 <= gy < WK['H'] and WK['quay'][gy * WK['W'] + gx] == 'w'
PI = [r for d in sc.get('fleet', {}).get('docks', []) for r in d['rects']]
nw = npier = 0; nofn = 0; hall = {40: 0, 50: 0, 60: 0}
for h in HS:
    if h[3] <= h[2] + 1 or h[3] <= 1: continue
    p = h[4]; x, y = sum(p[0::2]) / 4, sum(p[1::2]) / 4
    if wet(x, y) and h[3] > sc.get('fleet', {}).get('harbor_from', 33): nw += 1   # 挖港时拆掉的房子原来就站在后来的水里
    if any(r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3] for r in PI): npier += 1
    if len(h) <= 8: nofn += 1
    elif len(h) > 9 and h[9] == 'hall':
        for Y in hall:
            if h[2] <= Y < h[3]: hall[Y] += 1
if nw: bad.append(f'{nw} 户在水里')
if npier: bad.append(f'{npier} 户盖在栈桥上')
if nofn: bad.append(f'{nofn} 户没分区')
HAS_PORT = bool(sc.get('fleet'))   # 工厂：没港的街区不要求货栈长屋 / 码头、仓场街区名
for Y, n in hall.items():
    if HAS_PORT and n < 5: bad.append(f'{Y} 年货栈长屋只有 {n} 座')
ST = json.load(open(Q + SL['streets'])); sw = sum(1 for s in ST if wet((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))
if sw > 0.01 * len(ST): bad.append(f'{sw}/{len(ST)} 段街在水里')
L = sc.get('zone_labels') or {}; c60 = {c for _, _, c in L.get('60', [])}
for c in (('dock', 'horrea') if HAS_PORT else ()) + (('market',) if any('market' in k for k in json.load(open(Q + 'houses.json'))['late']) else ()):
    if c not in c60: bad.append(f'60 年远看没有 {c} 的街区名')
if any(c == 'homes' for _, _, c in sum(L.values(), [])): bad.append('民居也写了街区名')
HD1 = json.load(open(Q + SL['houses'])); late = HD1['late']
if len(HD1.get('unplaced', [])) > 5: bad.append(f"{len(HD1['unplaced'])} 户街上没地方")
def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
onlm = sum(1 for h in HS for k, v in late.items() if h[3] > v['built'] + 0 and h[3] > h[2] + 1 and pip(sum(h[4][0::2]) / 4, sum(h[4][1::2]) / 4, v['p']) and h[3] > v['built'])
if onlm: bad.append(f'{onlm} 户在地标盖起来以后还住在它的地皮上')
onst = sum(1 for q in ST for k, v in late.items() if (not q[7] or q[7] > v['built']) and pip((q[0] + q[2]) / 2, (q[1] + q[3]) / 2, v['p']))
if onst: bad.append(f'{onst} 段街在地标盖起来以后还压在它上面')
for k in [[0]] + sc['keys']:
    if not os.path.exists(Q + SL['ground'].replace('{K}', str(k[0]))): bad.append(f'缺 {k[0]} 年地面图')
print('houses', len(L1), 'unplaced', len(HD1.get('unplaced', [])), 'streets', len(ST), 'in water', nw, 'on piers', npier, 'street segs in water', sw, 'halls 40/50/60', list(hall.values()), 'labels 60', len(L.get('60', [])), ' '.join(bad) or 'ok')
sys.exit(1 if bad else 0)
