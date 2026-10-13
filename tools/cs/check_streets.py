"""cs29 · 按街道重排的检查：
1 重排只挪位置：houses_street.json 和底账 houses.json 一户不多一户不少，建成、拆毁年份一样；
2 不下水、不上栈桥：房子中心不在水格里，不压在栈桥上；
3 街不下水：街段中点在水里的 ≤ 1%；
4 分区跟着地块：每户都有分区；40/50/60 年都有货栈长屋（hall）；60 年远看有码头货栈、仓场的街区名，民居不写；
5 地面图每张关键年画都有。"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Q = os.path.join(ROOT, 'docs', 'living', q) + '/'; sc = json.load(open(Q + 'scene.json')); SL = sc.get('street_layout')
if not SL: print('no street layout, skip'); sys.exit(0)
bad = []
L0 = {h[0]: (h[2], h[3]) for h in json.load(open(Q + 'houses.json'))['houses']}
HS = json.load(open(Q + SL['houses']))['houses']; L1 = {h[0]: (h[2], h[3]) for h in HS}
if L0 != L1: bad.append(f'重排后户数/年份和底账不一致（底账 {len(L0)}，重排 {len(L1)}，不同 {sum(1 for k in L0 if L1.get(k) != L0[k])}）')
WK = sc['fleet']['walk']
def wet(x, y):
    gx, gy = int(x // WK['R']), int(y // WK['R'])
    return 0 <= gx < WK['W'] and 0 <= gy < WK['H'] and WK['quay'][gy * WK['W'] + gx] == 'w'
PI = [r for d in sc['fleet'].get('docks', []) for r in d['rects']]
nw = npier = 0; nofn = 0; hall = {40: 0, 50: 0, 60: 0}
for h in HS:
    if h[3] <= h[2] + 1 or h[3] <= 1: continue
    p = h[4]; x, y = sum(p[0::2]) / 4, sum(p[1::2]) / 4
    if wet(x, y) and h[3] > sc['fleet'].get('harbor_from', 33): nw += 1   # 挖港时拆掉的房子原来就站在后来的水里
    if any(r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3] for r in PI): npier += 1
    if len(h) <= 8: nofn += 1
    elif len(h) > 9 and h[9] == 'hall':
        for Y in hall:
            if h[2] <= Y < h[3]: hall[Y] += 1
if nw: bad.append(f'{nw} 户在水里')
if npier: bad.append(f'{npier} 户盖在栈桥上')
if nofn: bad.append(f'{nofn} 户没分区')
for Y, n in hall.items():
    if n < 5: bad.append(f'{Y} 年货栈长屋只有 {n} 座')
ST = json.load(open(Q + SL['streets'])); sw = sum(1 for s in ST if wet((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))
if sw > 0.01 * len(ST): bad.append(f'{sw}/{len(ST)} 段街在水里')
L = sc.get('zone_labels') or {}; c60 = {c for _, _, c in L.get('60', [])}
for c in ('dock', 'horrea'):
    if c not in c60: bad.append(f'60 年远看没有 {c} 的街区名')
if any(c == 'homes' for _, _, c in sum(L.values(), [])): bad.append('民居也写了街区名')
for k in sc['keys']:
    if not os.path.exists(Q + SL['ground'].replace('{K}', str(k[0]))): bad.append(f'缺 {k[0]} 年地面图')
print('houses', len(L1), 'streets', len(ST), 'in water', nw, 'on piers', npier, 'street segs in water', sw, 'halls 40/50/60', list(hall.values()), 'labels 60', len(L.get('60', [])), ' '.join(bad) or 'ok')
sys.exit(1 if bad else 0)
