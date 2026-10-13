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
WK = sc['fleet']['walk']; wat = np.array([c == 'w' for c in WK['quay']]).reshape(WK['H'], WK['W'])
watI = Image.fromarray(wat.astype(np.uint8) * 255).resize((W, H), Image.NEAREST).filter(ImageFilter.MaxFilter(9))
lmI = Image.new('L', (W, H), 0); dl = ImageDraw.Draw(lmI)
for k, v in late.items():
    p = v['p']; cx = sum(x for x, _ in p) / len(p); cy = sum(y for _, y in p) / len(p); dl.polygon([(cx + (x - cx) * 1.08, cy + (y - cy) * 1.08) for x, y in p], fill=255)
keep = np.maximum(np.asarray(watI), np.asarray(lmI)) > 0      # 水、地标不抹
gt = Image.open(Q + 'kits/hill/ground.webp').convert('RGB').resize((48, 48), Image.LANCZOS)
# 三张画的地面颜色不一样（50 年那张偏暗），统一用一种沙色、一张纹理，免得换年代时地面跳色
SAND = None
for K, f, _ in sc['keys']:
    A = Image.open(Q + f).convert('RGB').resize((W, H)); a = np.asarray(A).astype(float)
    if SAND is None:
        land = a[~keep]; land = land[(land[:, 0] - land[:, 2] < 70) & (land.sum(1) > 420)]; SAND = np.median(land, 0)
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
    G.save(Q + f'ground_{K}.jpg', quality=88); print('ground', K, 'sand', sand.round())
