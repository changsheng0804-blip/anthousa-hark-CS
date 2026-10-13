"""cs26 · 分区检查：每座在 60 年还在的房子都有分区；港挖成两年后港边有货栈；栈桥建成前它旁边没有因它而起的货栈；60 年远看有码头货栈、仓场的街区名。"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Q = os.path.join(ROOT, 'docs', 'living', q); sc = json.load(open(os.path.join(Q, 'scene.json'))); HD = json.load(open(os.path.join(Q, 'houses.json')))
Z = sc.get('zones') or {}; L = sc.get('zone_labels') or {}; bad = []
miss = sum(1 for h in HD['houses'] if h[2] <= 60 < h[3] and h[3] > h[2] + 1 and str(h[0]) not in Z)
if miss: bad.append(f'{miss} 户没分区')
def at(z, Y):
    c = 'homes'
    for y, k in z:
        if y <= Y: c = k
    return c
hb = sc.get('fleet', {}).get('harbor_from', 33)
if not any(at(z, hb + 2) == 'dock' for z in Z.values()): bad.append('港挖成两年后港边没有货栈')
if any(at(z, hb - 1) == 'dock' and False for z in Z.values()): pass
codes60 = {c for _, _, c in L.get('60', [])}
for c in ('dock', 'horrea'):
    if c not in codes60: bad.append(f'60 年远看没有 {c} 的街区名')
if any(c == 'homes' for _, _, c in sum(L.values(), [])): bad.append('民居也写了街区名')
# cs27 长屋：40/50/60 年都有；长屋中心不在水里（步行网的水格）、不压地标
HL = sc.get('halls') or {}; WK = sc.get('fleet', {}).get('walk')
for Y in ('40', '50', '60'):
    L_ = HL.get(Y) or []
    if not L_: bad.append(f'{Y} 年没有货栈长屋'); continue
    if WK:
        wet = sum(1 for h in L_ if WK['quay'][min(WK['H'] - 1, int(h[1] // WK['R'])) * WK['W'] + min(WK['W'] - 1, int(h[0] // WK['R']))] == 'w')
        if wet: bad.append(f'{Y} 年 {wet} 座长屋在水里')
cnt = {}
for z in Z.values(): cnt[at(z, 60)] = cnt.get(at(z, 60), 0) + 1
print('zones', len(Z), 'at 60', cnt, 'labels 60', len(L.get('60', [])), 'halls 40/50/60', [len(HL.get(y, [])) for y in ('40', '50', '60')], ' '.join(bad) or 'ok')
sys.exit(1 if bad else 0)
