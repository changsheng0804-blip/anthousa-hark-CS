"""CS 线 · 街区生产线（第三段：自动评画）
不用人眼，先用底账给每张画打分：
  houses —— 画上「像屋顶」的地方，和底账里当年站着的房子对得上多少（相关系数，越高越准；点哪栋就是哪栋）
  water  —— 画上的水，和底账里的海、港对得上多少（交并比）
  burn   —— 火烧过的地块是不是黑的
用法: python tools/cs/factory/critic.py <quarter_dir> <year> <img> [<img> ...]
      python tools/cs/factory/critic.py xerolophos 50 xero_af50.jpg   # 拿上游已有的画当基准"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIV = os.path.join(ROOT, 'docs', 'living')
PW, PH = 1820, 2048; R = 1


def masks(qdir, Y):
    hs = json.load(open(os.path.join(LIV, qdir, 'houses.json')))['houses']
    m = Image.new('L', (PW // R, PH // R), 0); d = ImageDraw.Draw(m)
    b = Image.new('L', (PW // R, PH // R), 0); db = ImageDraw.Draw(b)
    for h in hs:
        P = [(h[4][i] / R, h[4][i + 1] / R) for i in range(0, len(h[4]), 2)]
        if h[2] <= Y < h[3]:
            d.polygon(P, fill=255)
        elif h[3] <= Y and h[3] == 48 and Y - 48 < 8:
            db.polygon(P, fill=255)
    w = None
    bp = os.path.join(LIV, qdir, f'base_{Y}.png')
    if os.path.exists(bp):
        a = np.asarray(Image.open(bp).convert('RGB').resize((PW // R, PH // R), Image.NEAREST)).astype(int)
        w = (abs(a[..., 0] - 70) < 6) & (abs(a[..., 2] - 118) < 6)
    return m, b, w


def score(qdir, Y, img):
    m, b, w = masks(qdir, Y)
    im = Image.open(img if os.path.isabs(img) else os.path.join(LIV, qdir, img)).convert('RGB').resize((PW // R, PH // R), Image.BICUBIC)
    a = np.asarray(im).astype(float)
    r, g, bl = a[..., 0], a[..., 1], a[..., 2]
    roof = (r - bl > 60) & (r > 110) & (g < r * 0.8)
    mm = np.asarray(m) > 0
    # 命中率：底账里的房子，画上那里有没有屋顶；精确率：画上的屋顶，有多少落在底账的房子上
    hit = float(roof[mm].mean()) if mm.any() else 0
    from scipy import ndimage as ndi
    gap = ~ndi.binary_dilation(mm, iterations=3)
    if w is not None:
        gap &= ~ndi.binary_dilation(w, iterations=4)
    prec = float(1 - roof[gap].mean())   # 房子之间的空地上，不该有屋顶
    houses = 2 * hit * prec / max(1e-6, hit + prec)
    out = {'houses': round(houses, 3), 'hit': round(hit, 3), 'prec': round(prec, 3)}
    if w is not None and w.any():
        blue = (a[..., 2] > a[..., 0] + 15)
        out['water'] = round(float((blue & w).sum() / max(1, (blue | w).sum())), 3)
    bb = np.asarray(b) > 0
    if bb.any():
        lum = a.mean(2)
        out['burn'] = round(float((lum[bb] < 90).mean()), 3)
    return out


if __name__ == '__main__':
    q, Y = sys.argv[1], int(sys.argv[2])
    for f in sys.argv[3:]:
        print(os.path.basename(f), json.dumps(score(q, Y, f)))
