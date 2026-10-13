"""CS 线 · 瓦片实验（cs33 推演）：把已长成的街区按世界坐标烤成固定瓦片金字塔。
python3 tools/cs/factory/tile_bake.py [年 ...]   → docs/living/tiles/<年>/<级>/<tx>_<ty>.webp + tiles/meta.json
级 0 = 一块瓦片 32×32 世界单位（455 px，和街区页面同一比例）；每升一级一块瓦片管 2 倍边长。
瓦片只从「画法」来（render_ng 同一套画法：地面 + 街 + 房子），浏览器只拼图。
同时量：烤的时间、每级瓦片数和字节、和整张街区图逐像素比（PSNR）。"""
import json, os, sys, time, io, math, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles')
TU = 32; S = 1820 / 128.0; TP = round(TU * S)   # 455 px
QS = [q for q in sorted(os.listdir(LIV)) if os.path.exists(os.path.join(LIV, q, 'scene.json')) and json.load(open(os.path.join(LIV, q, 'scene.json'))).get('street_layout')]
YS = [int(y) for y in sys.argv[1:]] or [40, 50, 60]
stat = {'tile_units': TU, 'tile_px': TP, 'scale': S, 'quarters': {}, 'years': YS, 'levels': {}}
# 世界范围（所有街区框的并集，对齐到 32 单位网格）
FR = {q: json.load(open(os.path.join(LIV, q, 'frame.json')))['frame'] for q in QS}
X0 = min(math.floor(f[0] / TU) * TU for f in FR.values()); Y0 = min(math.floor(f[1] / TU) * TU for f in FR.values())
X1 = max(math.ceil((f[0] + f[2]) / TU) * TU for f in FR.values()); Y1 = max(math.ceil((f[1] + f[3]) / TU) * TU for f in FR.values())
NX, NY = (X1 - X0) // TU, (Y1 - Y0) // TU
stat['origin'] = [X0, Y0]; stat['grid'] = [NX, NY]
t_all = time.time()
for Y in YS:
    t0 = time.time()
    mos = Image.new('RGBA', (NX * TP, NY * TP), (0, 0, 0, 0))
    psnr = {}
    for q in QS:
        subprocess.run([sys.executable, os.path.join(HERE, 'render_ng.py'), q, str(Y)], check=True, capture_output=True)
        im = Image.open(os.path.join(HERE, 'out', f'{q}_render_{Y}.jpg')).convert('RGBA')
        f = FR[q]; ox, oy = round((f[0] - X0) * S), round((f[1] - Y0) * S)
        mos.paste(im, (ox, oy))
        stat['quarters'][q] = [ox, oy, im.width, im.height]
    t_render = time.time() - t0
    # 金字塔
    lvl = 0; cur = mos; t1 = time.time()
    while True:
        n_x, n_y = math.ceil(cur.width / TP), math.ceil(cur.height / TP)
        d = os.path.join(OUT, str(Y), str(lvl)); os.makedirs(d, exist_ok=True)
        nb = 0; nt = 0; sizes = []
        A = np.asarray(cur)[..., 3]
        for ty in range(n_y):
            for tx in range(n_x):
                box = (tx * TP, ty * TP, min(cur.width, (tx + 1) * TP), min(cur.height, (ty + 1) * TP))
                if A[box[1]:box[3], box[0]:box[2]].max() == 0: continue   # 空瓦片不存
                t = Image.new('RGBA', (TP, TP), (0, 0, 0, 0)); t.paste(cur.crop(box), (0, 0))
                bio = io.BytesIO(); t.save(bio, 'WEBP', quality=80, method=4); b = bio.getvalue()
                open(os.path.join(d, f'{tx}_{ty}.webp'), 'wb').write(b); nb += len(b); nt += 1; sizes.append(len(b))
        stat['levels'].setdefault(str(lvl), {})[str(Y)] = {'tiles': nt, 'bytes': nb, 'max_tile': max(sizes or [0]), 'grid': [n_x, n_y]}
        if n_x <= 1 and n_y <= 1: break
        cur = cur.resize((math.ceil(cur.width / 2), math.ceil(cur.height / 2)), Image.LANCZOS); lvl += 1
    t_tiles = time.time() - t1
    # 逐像素比：级 0 瓦片拼回去 vs 原图
    for q in QS:
        ox, oy, w, h = stat['quarters'][q]
        back = Image.new('RGBA', (NX * TP, NY * TP))
        for fn in os.listdir(os.path.join(OUT, str(Y), '0')):
            tx, ty = map(int, fn[:-5].split('_'))
            if (tx + 1) * TP <= ox or tx * TP >= ox + w or (ty + 1) * TP <= oy or ty * TP >= oy + h: continue
            back.paste(Image.open(os.path.join(OUT, str(Y), '0', fn)), (tx * TP, ty * TP))
        a = np.asarray(back.crop((ox, oy, ox + w, oy + h)).convert('RGB')).astype(float)
        b = np.asarray(Image.open(os.path.join(HERE, 'out', f'{q}_render_{Y}.jpg')).convert('RGB')).astype(float)
        mse = ((a - b) ** 2).mean(); psnr[q] = round(10 * math.log10(255 ** 2 / max(mse, 1e-9)), 1)
    stat.setdefault('time', {})[str(Y)] = {'render_s': round(t_render, 1), 'tiles_s': round(t_tiles, 1)}
    stat.setdefault('psnr', {})[str(Y)] = psnr
    print(Y, stat['time'][str(Y)], psnr, flush=True)
# ── 街巷级：地面瓦片（不含街和房子）+ 每块矢量数据（街 + 房子几何，带建成/拆毁年，换年份不用重下）
t2 = time.time(); sys.path.insert(0, HERE); import house_types as HT
GK = sorted({min([k[0] for k in json.load(open(os.path.join(LIV, q, 'scene.json')))['keys'] if Y <= k[0]] or [max(k[0] for k in json.load(open(os.path.join(LIV, q, 'scene.json')))['keys'])]) for q in QS for Y in YS})
gb = {}
for K in GK:
    mos = Image.new('RGBA', (NX * TP, NY * TP), (0, 0, 0, 0))
    for q in QS:
        ox, oy, w, h = stat['quarters'][q]; mos.paste(Image.open(os.path.join(LIV, q, f'ground_{K}.jpg')).convert('RGBA').resize((w, h)), (ox, oy))
    d = os.path.join(OUT, 'g', str(K)); os.makedirs(d, exist_ok=True); A = np.asarray(mos)[..., 3]; nb = 0
    for ty in range(NY):
        for tx in range(NX):
            if A[ty * TP:(ty + 1) * TP, tx * TP:(tx + 1) * TP].max() == 0: continue
            bio = io.BytesIO(); mos.crop((tx * TP, ty * TP, (tx + 1) * TP, (ty + 1) * TP)).save(bio, 'WEBP', quality=82, method=4)
            open(os.path.join(d, f'{tx}_{ty}.webp'), 'wb').write(bio.getvalue()); nb += len(bio.getvalue())
    gb[str(K)] = nb
R = lambda v: round(v * 2) / 2
vec = {}
def put(tx, ty, k, item): vec.setdefault((tx, ty), {'s': [], 'h': []})[k].append(item)
KC = {'fill': 0, 'edge': 1, 'line': 2}
for q in QS:
    ox, oy, w, h = stat['quarters'][q]; Q = os.path.join(LIV, q) + '/'
    for st in json.load(open(Q + 'streets.json')):
        x0, y0, x1, y1 = st[0] + ox, st[1] + oy, st[2] + ox, st[3] + oy; pad = st[4] + 2
        it = [R(x0), R(y0), R(x1), R(y1), st[4], st[5], st[6], st[7], st[8]]
        for ty in range(int((min(y0, y1) - pad) // TP), int((max(y0, y1) + pad) // TP) + 1):
            for tx in range(int((min(x0, x1) - pad) // TP), int((max(x0, x1) + pad) // TP) + 1): put(tx, ty, 's', it)
    for hh in json.load(open(Q + 'houses_street.json'))['houses']:
        if hh[3] <= hh[2] + 1: continue
        by, parts, shadow = HT.geom(hh)
        P = [[KC[k], [c for xy in poly for c in (R(xy[0] + ox), R(xy[1] + oy))], '%02x%02x%02x' % tuple(col[:3])] for k, lay, poly, col in parts]
        sh = [c for xy in shadow for c in (R(xy[0] + ox), R(xy[1] + oy))]
        cx = sum(sh[0::2]) / (len(sh) / 2); cy = sum(sh[1::2]) / (len(sh) / 2)
        put(int(cx // TP), int(cy // TP), 'h', [hh[2], hh[3], R(by + oy), sh, P])
d = os.path.join(OUT, 'vec'); os.makedirs(d, exist_ok=True); import gzip; vb = []; vg = []; nh = []
for (tx, ty), v in vec.items():
    v['h'].sort(key=lambda x: x[2]); b = json.dumps(v, separators=(',', ':')).encode()
    open(os.path.join(d, f'{tx}_{ty}.json'), 'wb').write(b); vb.append(len(b)); vg.append(len(gzip.compress(b))); nh.append(len(v['h']))
stat['street'] = {'ground_keys': GK, 'ground_bytes': gb, 'vec_tiles': len(vb), 'vec_bytes': sum(vb), 'vec_gzip': sum(vg), 'vec_max_gzip': max(vg), 'max_houses_tile': max(nh), 'seconds': round(time.time() - t2, 1)}
print('street', stat['street'])
stat['total_s'] = round(time.time() - t_all, 1)
json.dump(stat, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
for l, v in stat['levels'].items(): print('level', l, v)
