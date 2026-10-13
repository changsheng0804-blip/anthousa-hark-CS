"""CS 线 · cs24 码头逐年长 · 盖栈桥的补丁
没建成的栈桥（连同靠在边上的画上的船）要从画上藏掉。heart.py 已算好每座栈桥、每张关键年画的 rects/hide/borrow；
这里从同一张画上把 borrow 偏移处的干净海面挪过来，按目标四周海面的平均色校正（借来的水常常深一点），边缘羽化，
存成 docs/living/<q>/docks/d<i>_<K>.png（带透明度）。页面 buildBase 直接把它贴到底图上。
用法：python dock_patch.py <q>   （heart.py 写完 scene.json 会自动调用）"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1]; Q = os.path.join(ROOT, 'docs', 'living', q); sc = json.load(open(os.path.join(Q, 'scene.json')))
F = sc.get('fleet', {}); D = F.get('docks') or []
os.makedirs(os.path.join(Q, 'docks'), exist_ok=True)
W, H = sc.get('W', 1820), sc.get('H', 2048); P = {}   # 放在 scene.dock_patch，不进 fleet（fleet 要和 heart.py 重算的一模一样，定律三）
for k in sc['keys']:
    K = k[0]; KI = Image.open(os.path.join(Q, k[1])).convert('RGB').resize((W, H)); A = np.asarray(KI).astype(float)
    for i, d in enumerate(D):
        o = (d.get('borrow') or {}).get(str(K))
        if not o or d['from'] <= K - 10: continue
        R_ = d['rects'] + (d.get('hide') or {}).get(str(K), [])
        x0 = max(0, min(r[0] for r in R_) - 16); y0 = max(0, min(r[1] for r in R_) - 16)
        x1 = min(W, max(r[0] + r[2] for r in R_) + 16); y1 = min(H, max(r[1] + r[3] for r in R_) + 16)
        m = Image.new('L', (x1 - x0, y1 - y0), 0); dm = ImageDraw.Draw(m)
        for r in R_: dm.rectangle([r[0] - x0 - 6, r[1] - y0 - 5, r[0] + r[2] - x0 + 6, r[1] + r[3] - y0 + 5], fill=255)
        hard = np.asarray(m) > 0; m = m.filter(ImageFilter.GaussianBlur(4))
        src = A[y0 + o[1]:y1 + o[1], x0 + o[0]:x1 + o[0]]; tgt = A[y0:y1, x0:x1]
        if src.shape != tgt.shape: continue
        # 色差校正：目标四周（补丁外沿一圈、画上是水的像素）对借来那块的同一圈
        from scipy import ndimage as ndi
        ring = ndi.binary_dilation(hard, iterations=10) & ~ndi.binary_dilation(hard, iterations=3)
        isw = lambda a: (a[..., 2] > a[..., 0] + 15) & (a[..., 2] > a[..., 1] - 10)
        rr = ring & isw(tgt) & isw(src)
        if rr.sum() > 30: src = np.clip(src + (tgt[rr].mean(0) - src[rr].mean(0)), 0, 255)
        im = Image.fromarray(src.astype('uint8')).convert('RGBA'); im.putalpha(m)
        fn = f'd{i}_{K}.png'; im.save(os.path.join(Q, 'docks', fn), optimize=True)
        P.setdefault(str(i), {})[str(K)] = [f'docks/{fn}', x0, y0]
sc['dock_patch'] = P
json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
print('dock patches', sum(len(v) for v in P.values()))
