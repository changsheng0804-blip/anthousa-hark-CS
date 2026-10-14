"""CS 线 · cs29 地面：把每张关键年画上底账原位置的小房子抹成地面（沙地纹理，色取自画上的空地），
地标、港、栈桥、船都留着；街和房子由页面照 streets.json / houses_geom.json 自己画（做法同上游 render_xero.py 的地面）。
输出 ground_<年>.jpg（每张关键年画一张）。"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'; Q = os.path.join(ROOT, 'docs', 'living', q) + '/'
W, H = 1820, 2048
sc = json.load(open(Q + 'scene.json')); OLD = json.load(open(Q + 'houses.json'))
late = OLD['late']
WK = (sc.get('fleet') or {}).get('walk') or sc['walk']; wat = np.array([c == 'w' for c in WK['quay']]).reshape(WK['H'], WK['W'])
watI = Image.fromarray(wat.astype(np.uint8) * 255).resize((W, H), Image.NEAREST).filter(ImageFilter.MaxFilter(9))
LMT = {'fort', 'forum', 'monument', 'palace', 'hippodrome', 'church', 'granary', 'cistern', 'warehouse', 'gate', 'baths', 'column', 'theatre', 'temple', 'market'}
def keep_at(K):   # 水、这一年已经盖起来的地标不抹（还没盖的地标地皮上画的是旧房子，照样抹）
    lmI = Image.new('L', (W, H), 0); dl = ImageDraw.Draw(lmI)
    for k, v in late.items():
        if v['built'] > K: continue
        p = v['p']; cx = sum(x for x, _ in p) / len(p); cy = sum(y for _, y in p) / len(p); dl.polygon([(cx + (x - cx) * 1.08, cy + (y - cy) * 1.08) for x, y in p], fill=255)
    # cs35：底账上早就站着的地标（竞技场、皇宫……）也留着——以前只留「后建」的，早建的会被当成旧房子抹掉
    for s_ in json.load(open(Q + 'frame.json'))['structures']:
        if s_['type'] not in LMT or s_.get('geom') != 'polygon': continue
        b_, d_ = int(s_['built']), s_.get('destroyed')
        if b_ > K or (d_ not in (None, 'None') and int(d_) <= K): continue
        p = s_['pts']; cx = sum(x for x, _ in p) / len(p); cy = sum(y for _, y in p) / len(p); dl.polygon([(cx + (x - cx) * 1.08, cy + (y - cy) * 1.08) for x, y in p], fill=255)
    return np.maximum(np.asarray(watI), np.asarray(lmI)) > 0
keep = keep_at(0)
PAL = json.load(open(os.path.join(HERE, 'city', 'palette.json')))
import cv2
_wcore = np.asarray(watI.filter(ImageFilter.MinFilter(9)).filter(ImageFilter.MinFilter(15))) > 0   # 水心（统计用）
_wzone = np.asarray(watI.filter(ImageFilter.MaxFilter(25))) > 0                                    # 可能画成水的地方（含没建栈桥的补丁）
def water_to_palette(img):
    # 水面按全城色板做 Lab 均值/方差匹配：保留波纹和深浅，换掉各张画自己的水色；船、栈桥（不偏蓝绿）不动
    a = np.asarray(img).astype(np.uint8)
    if not _wcore.any(): return img
    L = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(float)
    f = a.astype(float); blu = (f[..., 1] > f[..., 0] + 12) & (f[..., 2] > f[..., 0] + 6) & _wzone
    core = _wcore & blu
    if core.sum() < 500: return img
    mu = L[core].mean(0); sd = L[core].std(0) + 1e-6
    tm = np.array(PAL['water_lab_mean'], float); ts = np.array(PAL['water_lab_std'], float)
    sc_ = np.clip(ts / sd, 0.5, 2.0); sc_[1:] = np.minimum(sc_[1:], 1.0)
    N = (L - mu) * sc_ + tm
    out = cv2.cvtColor(np.clip(N, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(float)
    m = np.asarray(Image.fromarray(blu.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(1.5))).astype(float)[..., None] / 255
    return Image.fromarray(np.clip(out * m + f * (1 - m), 0, 255).astype(np.uint8))
# ── cs34 程序水面：水不再取自画，按全城一个规则生成。深浅看离底账岸线多远，起伏和波纹按世界坐标取（跨街区、跨瓦片连得上），
# 岸线一种描边。画上落在水区里、又不是水色的东西（栈桥、港墙、停着的船）算地标，原样留着。
FRm = json.load(open(Q + 'frame.json'))['frame']; PXU = W / FRm[2]
WX0, WY0 = FRm[0] * PXU, FRm[1] * PXU            # 本街区左上角的世界像素坐标
def _hash(ix, iy, s=0):
    h = (ix * 374761393 + iy * 668265263 + s * 2147483647) & 0xffffffff
    h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
    return ((h ^ (h >> 16)) & 0xffff) / 65535.0
def vnoise(cell, s):
    ys, xs = np.mgrid[0:H, 0:W].astype(float); gx = (xs + WX0) / cell; gy = (ys + WY0) / cell
    ix = np.floor(gx).astype(np.int64); iy = np.floor(gy).astype(np.int64); fx = gx - ix; fy = gy - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    h = lambda a, b: _hash(a, b, s)
    return (h(ix, iy) * (1 - fx) + h(ix + 1, iy) * fx) * (1 - fy) + (h(ix, iy + 1) * (1 - fx) + h(ix + 1, iy + 1) * fx) * fy
_land = ~wat
_landI = Image.fromarray(_land.astype(np.uint8) * 255).resize((W, H), Image.NEAREST).filter(ImageFilter.GaussianBlur(3))
_landM = np.asarray(_landI) > 127; _landM0 = _landM.copy()
_dist = cv2.distanceTransform((~_landM).astype(np.uint8), cv2.DIST_L2, 5)      # 离岸像素数
_N1 = vnoise(260, 1) * 0.65 + vnoise(90, 2) * 0.35
WAT = PAL.get('water', {'shallow_lab': [150, 108, 124], 'deep_lab': [104, 114, 126], 'depth_px': 220, 'ripple_cell': 70, 'ripple_p': 0.33})
def proc_water():
    t = np.clip(_dist / WAT['depth_px'], 0, 1) ** 0.7
    t = np.clip(t + (_N1 - 0.5) * 0.35, 0, 1)[..., None]
    lab = np.array(WAT['shallow_lab'], float) * (1 - t) + np.array(WAT['deep_lab'], float) * t
    lab[..., 0] += (vnoise(28, 3) - 0.5) * 6
    rgb = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    im = Image.fromarray(rgb); ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    C = WAT['ripple_cell']
    for gy in range(int(WY0 // C) - 1, int((WY0 + H) // C) + 2):
        for gx in range(int(WX0 // C) - 1, int((WX0 + W) // C) + 2):
            if _hash(gx, gy, 7) > WAT['ripple_p']: continue
            cx = gx * C + _hash(gx, gy, 8) * C - WX0; cy = gy * C + _hash(gx, gy, 9) * C - WY0
            if not (0 <= cx < W and 0 <= cy < H) or _dist[int(cy), int(cx)] < 40: continue
            L_ = 14 + _hash(gx, gy, 10) * 18; a = -0.25 + (_hash(gx, gy, 11) - 0.5) * 0.3
            pts = [(cx + math.cos(a) * L_ * (u - 0.5), cy + math.sin(a) * L_ * (u - 0.5) + math.sin(u * math.pi * 2) * 1.6) for u in [i / 8 for i in range(9)]]
            d.line(pts, fill=(236, 244, 240, 70), width=2)
    im = im.convert('RGBA'); im.alpha_composite(ov.filter(ImageFilter.GaussianBlur(0.6)))
    return np.asarray(im.convert('RGB')).astype(float)
import math
_PW = proc_water()
def water_proc(img):
    a = np.asarray(img).astype(float)
    blu = (a[..., 1] > a[..., 0] + 12) & (a[..., 2] > a[..., 0] + 6) & _wzone          # 画上是水色
    sea = blu & ~_landM                                                                  # 只在底账也是水的地方换
    m = np.asarray(Image.fromarray(sea.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))).astype(float)[..., None] / 255
    out = _PW * m + a * (1 - m)
    # 岸线：底账陆地边上、画上也是水的地方描一道（全城同粗同色）
    edge = (cv2.dilate(_landM.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~_landM & blu
    e = np.asarray(Image.fromarray(edge.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(0.8))).astype(float)[..., None] / 255 * 0.75
    out = out * (1 - e) + np.array([62, 72, 58], float) * e
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
gt = Image.open(Q + 'kits/hill/ground.webp').convert('RGB').resize((48, 48), Image.LANCZOS)
# 三张画的地面颜色不一样（50 年那张偏暗），统一用一种沙色、一张纹理，免得换年代时地面跳色
SAND = None
import tile_years as TY
_KEYS = [tuple(k) for k in sc['keys']]
def _src_of(Y): return min([k for k in _KEYS if Y <= k[0]] or [_KEYS[-1]], key=lambda k: k[0])[1]
# /goal 3 项 6：年份轴上不是关键年的年份（-657、-400、-200、10、20、30、70）也要一张地面（地标只留当年已建成的）——存在 out/ground_y/，不进 docs（体积）
_EXTRA = [(Y, _src_of(Y), None) for Y in TY.TILE_YEARS if Y != 0 and Y not in [k[0] for k in _KEYS]]
for K, f, _ in [(0, sc['keys'][0][1], None)] + _KEYS + _EXTRA:   # ground_0：第一张画把地标也抹掉，给最早那些年用
    A = Image.open(Q + f).convert('RGB').resize((W, H)); a = np.asarray(A).astype(float); keep = keep_at(K)
    if SAND is None:
        SAND = np.array(PAL['sand_rgb'], float)   # cs32：全城一种沙色，不再取各自画上的
    # 整片陆地铺成同一种沙地；留下水、地标、画上的绿（菜园、树）和火烧过的焦土
    green = (a[..., 1] > a[..., 0] + 4) & (a[..., 1] > a[..., 2] + 10)
    dark = (a.sum(2) < 330) & (np.abs(a[..., 0] - a[..., 2]) < 40)
    fire = np.zeros((H, W), bool)
    fr = [l for l in json.load(open(Q + 'city.json'))['landmarks'] if l['id'] == 'fire_ruins']
    if 48 <= K:   # 焦土只留在 48 年真烧掉的那些房子周围
        bm = Image.new('L', (W, H), 0); bd = ImageDraw.Draw(bm)
        for h in OLD['houses']:
            if h[3] == 48:
                p = h[4]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4; bd.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=255)
        fire = (np.asarray(bm.filter(ImageFilter.GaussianBlur(6))) > 100) & dark
    # cs38 港池岸线：底账港池是矩形，把岸线往水里收出弯和圆角（只收水不加水；只动画上是水色的像素）
    from harbor_shape import shore_keep
    hm = Image.new('L', (W, H), 0); hd = ImageDraw.Draw(hm)
    for s_ in json.load(open(Q + 'frame.json'))['structures']:
        if s_['type'] == 'harbor' and int(s_['built']) <= K and s_.get('destroyed') in (None, 'None'): hd.polygon([tuple(p) for p in s_['pts']], fill=255)
    harb = np.asarray(hm) > 0
    _landM = _landM0.copy()
    if harb.any():
        kp = shore_keep(_landM0, harb, WX0, WY0, PXU)
        bl = (a[..., 1] > a[..., 0] + 12) & (a[..., 2] > a[..., 0] + 6)
        carve = ~_landM0 & ~kp & bl
        keep = keep & ~carve
        _landM = _landM0 | carve
    hold = keep | np.asarray(Image.fromarray((green | fire).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))).astype(bool)
    m = Image.fromarray(((~hold) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(2))
    sand = SAND
    g = Image.new('RGB', (W, H))
    for x in range(0, W, 48):
        for y in range(0, H, 48): g.paste(gt, (x, y))
    ga = np.asarray(g).astype(float); ga = ga - ga.reshape(-1, 3).mean(0) + sand
    rs = np.random.RandomState(5); noise = np.asarray(Image.fromarray((rs.rand(H // 64, W // 64) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(float)[..., None]
    ga = ga * 0.5 + sand * 0.5 + (noise - 128) * 0.08
    G = Image.composite(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8)), A, m)
    G = water_proc(G)
    G.save(TY.ground_file(q, K, write=True), quality=88); print('ground', K, 'sand', sand.round())
