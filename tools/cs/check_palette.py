"""CS 线 · 全城色板检查（cs32，CITY_RULES L7）。用法: python tools/cs/check_palette.py <q> [其它街区…]
1 每个年份的沙地离全城色板 ΔE ≤ sand_dE；水面 ≤ water_dE
2 同一街区前后年份之间，沙地、水面 ΔE ≤ year_dE（换年代不跳色）
3 和其它已长成的街区比，同一年份沙地、水面 ΔE ≤ quarter_dE"""
import json, os, sys
import numpy as np, cv2
from PIL import Image, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAL = json.load(open(os.path.join(ROOT, 'tools', 'cs', 'factory', 'city', 'palette.json'))); T = PAL['tol']
LIV = os.path.join(ROOT, 'docs', 'living')
def lab(c): return cv2.cvtColor(np.uint8([[np.clip(c, 0, 255)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float) * [100 / 255, 1, 1] - [0, 128, 128]
def dE(a, b): return float(np.linalg.norm(lab(a) - lab(b)))
def stats(q):
    Q = os.path.join(LIV, q); sc = json.load(open(os.path.join(Q, 'scene.json')))
    if not sc.get('street_layout'): return None
    WK = (sc.get('fleet') or {}).get('walk') or sc['walk']; wat = np.array([c == 'w' for c in WK['quay']]).reshape(WK['H'], WK['W'])
    wI = Image.fromarray(wat.astype(np.uint8) * 255).resize((1820, 2048), Image.NEAREST)
    lc = np.asarray(wI.filter(ImageFilter.MaxFilter(15))) == 0
    # cs35：水面按离岸远近生成（深浅是规则的一部分），所以各街区只比同一段离岸距离（30–110 像素）的水，不拿港池的浅水比外海
    dist = cv2.distanceTransform((np.asarray(wI) > 0).astype(np.uint8), cv2.DIST_L2, 5); wc = (dist >= 30) & (dist <= 110)
    out = {}
    for K in [0] + [k[0] for k in sc['keys']]:
        a = np.asarray(Image.open(os.path.join(Q, f'ground_{K}.jpg')).convert('RGB')).astype(float)
        f = a; blu = (f[..., 1] > f[..., 0] + 12) & (f[..., 2] > f[..., 0] + 6)
        out[K] = (np.median(a[lc], 0), np.median(a[wc & blu], 0) if (wc & blu).sum() > 500 else None)
    return out
qs = sys.argv[1:]; S = {q: stats(q) for q in qs + [d for d in sorted(os.listdir(LIV)) if d not in qs and os.path.exists(os.path.join(LIV, d, 'scene.json'))]}
S = {k: v for k, v in S.items() if v}
q = qs[0]; me = S[q]; bad = 0; out = []
def rep(ok, name, info):
    global bad; bad += not ok; out.append(('✅ ' if ok else '❌ ') + name + '  —— ' + info)
wt = cv2.cvtColor(np.uint8([[np.array(PAL['water_lab_mean'])]]), cv2.COLOR_LAB2RGB)[0, 0].astype(float)
ds = max(dE(s, PAL['sand_rgb']) for s, _ in me.values()); dw = max([dE(w, wt) for _, w in me.values() if w is not None] or [0])
rep(ds <= T['sand_dE'] and dw <= T['water_dE'], '地面颜色在全城色板上', f'沙地最大 ΔE {ds:.1f}（≤{T["sand_dE"]}），水面最大 ΔE {dw:.1f}（≤{T["water_dE"]}）')
ks = sorted(me); yj = 0
for a, b in zip(ks[:-1], ks[1:]):
    yj = max(yj, dE(me[a][0], me[b][0]), dE(me[a][1], me[b][1]) if me[a][1] is not None and me[b][1] is not None else 0)
rep(yj <= T['year_dE'], '换年代地面不跳色', f'相邻年份最大 ΔE {yj:.1f}（≤{T["year_dE"]}）')
qj = 0; who = []
for o, st in S.items():
    if o == q: continue
    for K in set(st) & set(me):
        d = max(dE(st[K][0], me[K][0]), dE(st[K][1], me[K][1]) if st[K][1] is not None and me[K][1] is not None else 0)
        if d > qj: qj = d
    who.append(o)
rep(qj <= T['quarter_dE'], '和别的街区是同一座城的颜色', f'对 {who or "无"} 最大 ΔE {qj:.1f}（≤{T["quarter_dE"]}）')
print('\n'.join(out)); sys.exit(1 if bad else 0)
