"""CS 线 · cs29 预览：照页面的画法（地面 + 街 + houses_geom）在 Python 里画一张某年的全图，验收和审图用。
python3 render_ng.py nangang 60 [x0 y0 x1 y1] → out/<q>_render_<年>.jpg"""
import json, os, sys, subprocess
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE); import house_types as HT
q = sys.argv[1]; Y = int(sys.argv[2]); Q = os.path.join(ROOT, 'docs', 'living', q) + '/'
W, H = 1820, 2048; S = 2
sc = json.load(open(Q + 'scene.json')); D = json.load(open(Q + 'houses_street.json')); ST = json.load(open(Q + 'streets.json'))
import tile_years as TY
K = TY.ground_year(q, Y)
if not os.path.exists(TY.ground_file(q, K)): subprocess.run([sys.executable, os.path.join(HERE, 'ground_ng.py'), q], check=True, capture_output=True)
G = Image.open(TY.ground_file(q, K)).convert('RGB').resize((W * S, H * S), Image.BICUBIC)
L = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
STY = {'m': ((118, 104, 86, 190), (174, 163, 144, 255)), 's': ((140, 118, 88, 110), (200, 182, 146, 215)), 'c': ((140, 118, 88, 90), (203, 186, 150, 190)), 'l': (None, (205, 189, 154, 165))}
for q_ in ST:
    if q_[8] <= Y < q_[6]: d.line([(q_[0] * S, q_[1] * S), (q_[2] * S, q_[3] * S)], fill=(150, 126, 92, 128), width=int(1.8 * S))
for pas in (0, 1):
    for k in 'lcsm':
        col = STY[k][pas]
        if not col: continue
        for q_ in ST:
            if q_[5] != k or q_[6] > Y or (q_[7] and q_[7] <= Y): continue
            w = (q_[4] + (0 if pas else 2)) * S; r = w / 2
            d.line([(q_[0] * S, q_[1] * S), (q_[2] * S, q_[3] * S)], fill=col, width=int(w))
            d.ellipse([q_[2] * S - r, q_[3] * S - r, q_[2] * S + r, q_[3] * S + r], fill=col)
G.paste(L, (0, 0), L)
hs = [h for h in D['houses'] if h[2] <= Y < h[3] and h[3] > h[2] + 1]
geo = [HT.geom(h) for h in hs]
sh = Image.new('L', (W * S, H * S), 0); ds = ImageDraw.Draw(sh)
for by, parts, shadow in geo: ds.polygon([(x * S, y * S) for x, y in shadow], fill=70)
G.paste((50, 32, 14), (0, 0), sh)
d = ImageDraw.Draw(G)
for by, parts, shadow in sorted(geo, key=lambda g: g[0]):
    for kind, lay, poly, col in parts:
        P = [(x * S, y * S) for x, y in poly]
        if kind == 'fill' and len(P) >= 3: d.polygon(P, fill=tuple(col))
        elif kind == 'edge': d.line(P + [P[0]], fill=tuple(col), width=1)
        elif kind == 'line': d.line(P, fill=tuple(col), width=1)
G = G.resize((W, H), Image.LANCZOS)
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
box = tuple(map(int, sys.argv[3:7])) if len(sys.argv) >= 7 else None
(G.crop(box) if box else G).save(os.path.join(HERE, 'out', f'{q}_render_{Y}.jpg'), quality=88)
print('houses', len(hs))
