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
def keep_at(K):   # 水、这一年已经盖起来的地标不抹（还没盖的地标地皮上画的是旧房子，照样抹）
    lmI = Image.new('L', (W, H), 0); dl = ImageDraw.Draw(lmI)
    for k, v in late.items():
        if v['built'] > K: continue
        p = v['p']; cx = sum(x for x, _ in p) / len(p); cy = sum(y for _, y in p) / len(p); dl.polygon([(cx + (x - cx) * 1.08, cy + (y - cy) * 1.08) for x, y in p], fill=255)
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
gt = Image.open(Q + 'kits/hill/ground.webp').convert('RGB').resize((48, 48), Image.LANCZOS)
# 三张画的地面颜色不一样（50 年那张偏暗），统一用一种沙色、一张纹理，免得换年代时地面跳色
SAND = None
for K, f, _ in [(0, sc['keys'][0][1], None)] + [tuple(k) for k in sc['keys']]:   # ground_0：第一张画把地标也抹掉，给最早那些年用
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
    G = water_to_palette(G)
    G.save(Q + f'ground_{K}.jpg', quality=88); print('ground', K, 'sand', sand.round())
