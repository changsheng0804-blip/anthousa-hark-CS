"""CS 线 · 瓦片街巷层改吃全城节点（2026-10-18）：tiles/vec/<tx>_<ty>.json 的街（s）和房子（h）
不再从九个街区各自的 streets.json / houses_street.json 拼，而是从全城一次长成的 nodes/city/nodes_net.json 取——
瓦片和街景是同一份房子、同一张路网，从瓦片缩进街景时房子不再跳，街区之间也没有接缝。
水格（wg）和史诗部件（id 'epic:…'）原样保留。城坐标 = 瓦片级 0 像素（同一原点 416,192、同一比例）。
用法: python3 tools/cs/nodes/tile_vec_nodes.py   ——Hark（CS线）"""
import json, os, sys, glob, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles'); VD = os.path.join(OUT, 'vec')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'cs', 'factory')); import house_types as HT
M = json.load(open(os.path.join(OUT, 'meta.json'))); TP = M['tile_px']; assert M['origin'] == [416, 192]
GK = M['street']['ground_keys']; WB = (1 << len(GK)) - 1
D = json.load(open(os.path.join(LIV, 'nodes', 'city', 'nodes_net.json')))
R = lambda v: round(v * 2) / 2
KC = {'fill': 0, 'edge': 1, 'line': 2}
vec = {}
for fn in glob.glob(os.path.join(VD, '*.json')):
    v = json.load(open(fn)); k = tuple(map(int, os.path.basename(fn)[:-5].split('_')))
    vec[k] = {'s': [], 'h': [r for r in v['h'] if isinstance(r[5], str) and r[5].startswith('epic:')], **({'wg': v['wg']} if 'wg' in v else {})}
def put(tx, ty, k, it): vec.setdefault((tx, ty), {'s': [], 'h': []})[k].append(it)
ns = nh = 0
for f in D['features']:
    if f['t'] == 'street':
        x0, y0, x1, y1 = f['g']; pad = f['w'] + 2
        it = [R(x0), R(y0), R(x1), R(y1), f['w'], f['k'], f['y0'], f['y1'] or 0, 0, WB]
        for ty in range(int((min(y0, y1) - pad) // TP), int((max(y0, y1) + pad) // TP) + 1):
            for tx in range(int((min(x0, x1) - pad) // TP), int((max(x0, x1) + pad) // TP) + 1): put(tx, ty, 's', it)
        ns += 1
    elif f['t'] == 'house':
        y1 = f['y1'] if f['y1'] is not None else 9999
        hh = [f['id'], 2, f['y0'], y1, f['p'], 0, 1, f.get('ht', 5), f.get('fn', 'homes'), f.get('ty', 'casa'), f.get('fr', 0), 7, f.get('po', 0)]
        if hh[3] <= hh[2] + 1: continue
        by, parts, shadow = HT.geom(hh)
        P = [[KC[q[0]], [c for xy in q[2] for c in (R(xy[0]), R(xy[1]))], '%02x%02x%02x' % tuple(q[3][:3])] + ([min(q[4][0], 9999), min(q[4][1], 9999)] if len(q) > 4 else []) for q in parts]
        sh = [c for xy in shadow for c in (R(xy[0]), R(xy[1]))]
        cx = sum(sh[0::2]) / (len(sh) / 2); cy = sum(sh[1::2]) / (len(sh) / 2)
        put(int(cx // TP), int(cy // TP), 'h', [hh[2], hh[3], R(by), sh, P, 'h%d' % f['id']]); nh += 1
for (tx, ty), v in vec.items():
    v['h'].sort(key=lambda x: x[2])
    json.dump(v, open(os.path.join(VD, f'{tx}_{ty}.json'), 'w'), separators=(',', ':'))
subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'cs', 'factory', 'zsort.py'), VD], check=True)
print('vec tiles', len(vec), 'streets', ns, 'houses', nh)
