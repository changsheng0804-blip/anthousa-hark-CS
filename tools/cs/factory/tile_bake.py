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
stat['total_s'] = round(time.time() - t_all, 1)
json.dump(stat, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
for l, v in stat['levels'].items(): print('level', l, v)
