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
sys.path.insert(0, HERE); import tile_years as TY
YS = [int(y) for y in sys.argv[1:]] or TY.TILE_YEARS   # 年份轴整套一起烤（去重要看全部年份）
stat = {'tile_units': TU, 'tile_px': TP, 'scale': S, 'quarters': {}, 'years': YS, 'levels': {}}
# 世界范围（所有街区框的并集，对齐到 32 单位网格）
FR = {q: json.load(open(os.path.join(LIV, q, 'frame.json')))['frame'] for q in QS}
X0 = min(math.floor(f[0] / TU) * TU for f in FR.values()); Y0 = min(math.floor(f[1] / TU) * TU for f in FR.values())
X1 = max(math.ceil((f[0] + f[2]) / TU) * TU for f in FR.values()); Y1 = max(math.ceil((f[1] + f[3]) / TU) * TU for f in FR.values())
NX, NY = (X1 - X0) // TU, (Y1 - Y0) // TU
stat['origin'] = [X0, Y0]; stat['grid'] = [NX, NY]
# cs36 地皮归属：街区框可以互相叠（全城补齐时框放不严），叠着的地方归先长的街区——地面、街、房子都只从归属的街区取一份。
# 地标是全城共用的同一张图、贴在同一个世界位置，所以两块地接缝处的地标两边一模一样，切开看不出来。
ORDER = ['nangang', 'jinjiao', 'gucheng', 'siqiu', 'dongjia', 'xipo', 'qiangwai', 'jiaowan', 'nanan']
QS = sorted(QS, key=lambda q: ORDER.index(q) if q in ORDER else len(ORDER))
OWN = np.full((NY * TP, NX * TP), -1, np.int8)
for i, q in enumerate(QS):
    f = FR[q]; ox, oy = round((f[0] - X0) * S), round((f[1] - Y0) * S); w, h = round(f[2] * S), round(f[3] * S)
    v = OWN[oy:oy + h, ox:ox + w]; v[v < 0] = i
def owns(q, x, y):
    x, y = int(x), int(y)
    return 0 <= y < OWN.shape[0] and 0 <= x < OWN.shape[1] and OWN[y, x] == QS.index(q)
def own_mask(q, ox, oy, w, h): return Image.fromarray(((OWN[oy:oy + h, ox:ox + w] == QS.index(q)) * 255).astype(np.uint8))
stat['owner_order'] = QS

# /goal 2 · 2a 补洞：街区框没盖严的角落（例：南港底边、墙外右边、南岸左边三块之间）在拼图里是透明的，
# 放大缩小时透明洞会漏出底色——整格补成「最近的已画像素」再柔化，只补有内容的瓦片格里的洞；世界外的整格空瓦片不动。
from scipy import ndimage as ndi
def fill_holes(im):
    a = np.asarray(im).copy(); al = a[..., 3] > 0; H_, W_ = al.shape; todo = []
    for ty in range(math.ceil(H_ / TP)):
        for tx in range(math.ceil(W_ / TP)):
            c = al[ty * TP:(ty + 1) * TP, tx * TP:(tx + 1) * TP]
            if c.any() and not c.all(): todo.append((tx, ty))
    n = 0
    for tx, ty in todo:
        x0, y0 = max(0, (tx - 1) * TP), max(0, (ty - 1) * TP); x1, y1 = min(W_, (tx + 2) * TP), min(H_, (ty + 2) * TP)
        cr = a[y0:y1, x0:x1]; v = cr[..., 3] > 0
        if not v.any(): continue
        d, (iy, ix) = ndi.distance_transform_edt(~v, return_indices=True)
        near = cr[iy, ix].astype(np.float32); blur = np.stack([ndi.gaussian_filter(near[..., k], 28) for k in range(3)], -1)
        w = np.clip(d / 24.0, 0, 1)[..., None]; out = near[..., :3] * (1 - w) + blur * w
        cx0, cy0, cx1, cy1 = tx * TP - x0, ty * TP - y0, min(W_, (tx + 1) * TP) - x0, min(H_, (ty + 1) * TP) - y0
        m = ~v; m[:cy0] = False; m[cy1:] = False; m[:, :cx0] = False; m[:, cx1:] = False
        cr[..., :3][m] = np.clip(out, 0, 255).astype(np.uint8)[m]; cr[..., 3][m] = 255; n += int(m.sum())
    return Image.fromarray(a), n
t_all = time.time()
for Y in YS:
    t0 = time.time()
    mos = Image.new('RGBA', (NX * TP, NY * TP), (0, 0, 0, 0))
    psnr = {}
    for q in QS:
        subprocess.run([sys.executable, os.path.join(HERE, 'render_ng.py'), q, str(Y)], check=True, capture_output=True)
        im = Image.open(os.path.join(HERE, 'out', f'{q}_render_{Y}.jpg')).convert('RGBA')
        f = FR[q]; ox, oy = round((f[0] - X0) * S), round((f[1] - Y0) * S)
        mos.paste(im, (ox, oy), own_mask(q, ox, oy, im.width, im.height))
        stat['quarters'][q] = [ox, oy, im.width, im.height]
    mos, nfill = fill_holes(mos); stat.setdefault('filled_px', {})[str(Y)] = nfill
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
        om = np.asarray(own_mask(q, ox, oy, w, h)) > 0; mse = ((a - b) ** 2)[om].mean(); psnr[q] = round(10 * math.log10(255 ** 2 / max(mse, 1e-9)), 1)
    stat.setdefault('time', {})[str(Y)] = {'render_s': round(t_render, 1), 'tiles_s': round(t_tiles, 1)}
    stat.setdefault('psnr', {})[str(Y)] = psnr
    print(Y, stat['time'][str(Y)], psnr, flush=True)
# ── 街巷级：地面瓦片（不含街和房子）+ 每块矢量数据（街 + 房子几何，带建成/拆毁年，换年份不用重下）
t2 = time.time(); sys.path.insert(0, HERE); import house_types as HT
GK = sorted({TY.ground_year(q, Y) for q in QS for Y in YS})
gb = {}; WM = {}   # 每个关键年的水面蒙版（地面画上：绿蓝压过红 = 水）
for K in GK:
    mos = Image.new('RGBA', (NX * TP, NY * TP), (0, 0, 0, 0))
    for q in QS:
        ox, oy, w, h = stat['quarters'][q]; mos.paste(Image.open(TY.ground_file(q, K)).convert('RGBA').resize((w, h)), (ox, oy), own_mask(q, ox, oy, w, h))
    mos, _ = fill_holes(mos); a = np.asarray(mos).astype(np.int16); WM[K] = (a[..., 3] > 0) & ((a[..., 1] - a[..., 0]) > 15)
    d = os.path.join(OUT, 'g', str(K)); os.makedirs(d, exist_ok=True); A = a[..., 3]; nb = 0
    for ty in range(NY):
        for tx in range(NX):
            if A[ty * TP:(ty + 1) * TP, tx * TP:(tx + 1) * TP].max() == 0: continue
            bio = io.BytesIO(); mos.crop((tx * TP, ty * TP, (tx + 1) * TP, (ty + 1) * TP)).save(bio, 'WEBP', quality=82, method=4)
            open(os.path.join(d, f'{tx}_{ty}.webp'), 'wb').write(bio.getvalue()); nb += len(bio.getvalue())
    gb[str(K)] = nb
COV = A > 0
R = lambda v: round(v * 2) / 2
vec = {}
def put(tx, ty, k, item): vec.setdefault((tx, ty), {'s': [], 'h': []})[k].append(item)
KC = {'fill': 0, 'edge': 1, 'line': 2}
for q in QS:
    ox, oy, w, h = stat['quarters'][q]; Q = os.path.join(LIV, q) + '/'
    for st in json.load(open(Q + 'streets.json')):
        x0, y0, x1, y1 = st[0] + ox, st[1] + oy, st[2] + ox, st[3] + oy; pad = st[4] + 2
        if not owns(q, (x0 + x1) / 2, (y0 + y1) / 2): continue
        # 定律 1：人只走地面画上是陆地的街——每 4 像素取一点，全是陆地才给这一关键年的走位（位掩码，按 GK 顺序）
        L = max(1, int(math.hypot(x1 - x0, y1 - y0) / 4)); wb = 0
        for i, K in enumerate(GK):
            ok = True
            for j in range(L + 1):
                px, py = int(x0 + (x1 - x0) * j / L), int(y0 + (y1 - y0) * j / L)
                if not (0 <= py < WM[K].shape[0] and 0 <= px < WM[K].shape[1]) or WM[K][py, px] or not COV[py, px]: ok = False; break
            if ok: wb |= 1 << i
        it = [R(x0), R(y0), R(x1), R(y1), st[4], st[5], st[6], st[7], st[8], wb]
        for ty in range(int((min(y0, y1) - pad) // TP), int((max(y0, y1) + pad) // TP) + 1):
            for tx in range(int((min(x0, x1) - pad) // TP), int((max(x0, x1) + pad) // TP) + 1): put(tx, ty, 's', it)
    for hh in json.load(open(Q + 'houses_street.json'))['houses']:
        if hh[3] <= hh[2] + 1: continue
        by, parts, shadow = HT.geom(hh)
        P = [[KC[k], [c for xy in poly for c in (R(xy[0] + ox), R(xy[1] + oy))], '%02x%02x%02x' % tuple(col[:3])] for k, lay, poly, col in parts]
        sh = [c for xy in shadow for c in (R(xy[0] + ox), R(xy[1] + oy))]
        cx = sum(sh[0::2]) / (len(sh) / 2); cy = sum(sh[1::2]) / (len(sh) / 2)
        if not owns(q, cx, cy): continue
        put(int(cx // TP), int(cy // TP), 'h', [hh[2], hh[3], R(by + oy), sh, P])
# 定律 2：船只在水格里走——每块瓦片按 8 像素格记水格（格里 ≥95% 是水才算），每个关键年一串 0/1
WC = 8; NC = math.ceil(TP / WC); nwater = 0
for ty in range(NY):
    for tx in range(NX):
        for K in GK:
            m = WM[K][ty * TP:(ty + 1) * TP, tx * TP:(tx + 1) * TP]
            if m.sum() < WC * WC * 9: continue
            pm = np.zeros((NC * WC, NC * WC), bool); pm[:m.shape[0], :m.shape[1]] = m
            cells = pm.reshape(NC, WC, NC, WC).mean(axis=(1, 3)) >= 0.95
            if cells.sum() < 9: continue
            vec.setdefault((tx, ty), {'s': [], 'h': []}).setdefault('wg', {})[str(K)] = ''.join('1' if c else '0' for c in cells.flatten()); nwater += 1
stat['water_cell'] = WC; stat['water_cells_n'] = NC
d = os.path.join(OUT, 'vec'); os.makedirs(d, exist_ok=True); import gzip; vb = []; vg = []; nh = []
for (tx, ty), v in vec.items():
    v['h'].sort(key=lambda x: x[2]); b = json.dumps(v, separators=(',', ':')).encode()
    open(os.path.join(d, f'{tx}_{ty}.json'), 'wb').write(b); vb.append(len(b)); vg.append(len(gzip.compress(b))); nh.append(len(v['h']))
# /goal 3 项 6 内容哈希去重：同一位置、同一级、字节全同的瓦片只留最早那份，后面的年份在 meta.alias 里指过去
# alias[<年>/<级>][x_y] = 根年份；alias['g/<关键年>'][x_y] = 'g/<根关键年>'；页面按别名换成根文件的地址（内存里也只存一份）
import hashlib
def dedupe(dirs, sub):   # dirs: [(键, 目录)] 按时间升序；sub: 级 或 ''
    al = {}; prev = {}; saved = 0
    for key, base in dirs:
        d = os.path.join(base, sub) if sub != '' else base
        if not os.path.isdir(d): continue
        m = {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.webp'): continue
            b = open(os.path.join(d, fn), 'rb').read(); h = hashlib.md5(b).hexdigest(); xy = fn[:-5]
            if xy in prev and prev[xy][0] == h:
                m[xy] = prev[xy][1]; saved += len(b); os.remove(os.path.join(d, fn))
            else: prev[xy] = (h, key)
        if m: al[key + ('/' + sub if sub != '' else '')] = m
    return al, saved
ALIAS = {}; SAVED = 0
for lvl in sorted(stat['levels'], key=int):
    a, sv = dedupe([(str(Y), os.path.join(OUT, str(Y))) for Y in sorted(YS)], lvl); ALIAS.update(a); SAVED += sv
a, sv = dedupe([(f'g/{K}', os.path.join(OUT, 'g', str(K))) for K in GK], ''); ALIAS.update(a); SAVED += sv
stat['alias'] = ALIAS; stat['dedupe_saved_bytes'] = SAVED
stat['street'] = {'ground_keys': GK, 'ground_bytes': gb, 'vec_tiles': len(vb), 'vec_bytes': sum(vb), 'vec_gzip': sum(vg), 'vec_max_gzip': max(vg), 'max_houses_tile': max(nh), 'seconds': round(time.time() - t2, 1)}
print('street', stat['street'])
stat['total_s'] = round(time.time() - t_all, 1)
json.dump(stat, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
for l, v in stat['levels'].items(): print('level', l, v)
