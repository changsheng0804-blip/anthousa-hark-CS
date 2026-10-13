#!/usr/bin/env python3
"""工厂定律：任何街区上线前都要过的通用检查（不针对某个街区写死）。 ——Hark（CS线）

定律一 · 站得住：会走的东西只站在「底账和画都认作陆地」的地方；画上有、底账没有的只许是窄栈桥（≤ PIER_W 像素宽），
         不许是一大片（那是船或者画错）。
定律二 · 浮得住：船只走「底账和画都认作水」的地方。
定律三 · 推得出：场景里的位置（泊位、水路、站位、街）都由 heart.py 从底账推出来；重跑 heart.py 结果必须一致，不许手抄。
定律四 · 对得上：底账和画对不上的岸（walk 网里的 x 格）要越来越少；蒙版生成上线后应为 0。现在只报数，不判死。

用法：python laws.py <q>   → 打印每条定律 ✅/❌，退出码 = 不过的条数。accept.py 会调用它。
"""
import json, os, subprocess, sys
import numpy as np
from scipy import ndimage as ndi

ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
q = sys.argv[1]; LIV = os.path.join(ROOT, 'docs/living', q); FAC = os.path.join(ROOT, 'tools/cs/factory')
PIER_W = int(os.environ.get('PIER_W', 22))
sc = json.load(open(os.path.join(LIV, 'scene.json'))); F = sc.get('fleet', {})
res = []

if not F.get('walk'):
    print(f'{q}: 没有会动的东西（scene.fleet.walk 不存在），定律跳过'); sys.exit(0)

# 定律三先跑：重算一次，顺便拿到底账/画的蒙版
before = json.dumps([F, json.load(open(os.path.join(LIV, 'city.json'))).get('roads')], sort_keys=True)
out = subprocess.run([sys.executable, os.path.join(FAC, 'heart.py'), q, '--json', '--masks'], cwd=ROOT, capture_output=True, text=True)
try:
    now_ = json.loads(out.stdout.strip().splitlines()[-1]); roads = now_.pop('_roads', None)
    same = all(F.get(k) == v for k, v in now_.items()) and (roads is None or roads == json.load(open(os.path.join(LIV, 'city.json'))).get('roads'))
except Exception as e:
    same = False; now_ = {}
res.append(('定律三 · 推得出：重跑 heart.py，位置与街和线上一致', same, '' if same else '有位置不是从底账推出来的，或底账变了没重算 → accept.py --fix'))

M = np.load(os.path.join(FAC, 'out', f'{q}_masks.npz'))
landm, pw = M['landm'], M['pw']           # 底账陆地（像素），画上的水（像素）
W = F['walk']; R = W['R']; g = np.array(list(W['quay'])).reshape(W['H'], W['W'])
walk = ~np.isin(g, ['w', 'x'])
PH, PW = landm.shape


RM = int(M['R'])                          # 蒙版一格 RM 像素；walk 网一格 R 像素
from PIL import Image


def cell_frac(mk):                        # 和 heart.py 的 pool 完全同一种缩法，免得边上差一格
    return np.array(Image.fromarray(mk.astype('uint8') * 255).resize((W['W'], W['H']), Image.BOX)) / 255.0


ledger_water = cell_frac(~landm) > 0.5
paint_water = cell_frac(pw) > 0.5
# 定律一 a：能走的格不许在画上的水里
a = int((walk & paint_water).sum())
res.append(('定律一 · 站得住：能走的格不在画上的水里', a == 0, f'{a} 格能走却画成了水'))
# 定律一 b：在底账水里的能走格（=画上的栈桥）必须窄
over = walk & ledger_water & ~(cell_frac(M['wall']) > 0.05)   # 底账里的港墙、码头本来就能走
dt = ndi.distance_transform_edt(over) * R
lab, n = ndi.label(over); fat = []
for c in range(1, n + 1):
    w_ = dt[lab == c].max() * 2
    if w_ > PIER_W + 2 * R: fat.append((c, int(w_), int((lab == c).sum())))   # 8 像素一格的量化误差留一格
res.append((f'定律一 · 站得住：底账水里能走的只许是窄栈桥（≤{PIER_W + 2 * R}px）', not fat,
            '' if not fat else f'{len(fat)} 团太宽：' + '，'.join(f'{a_}px×{b_}格' for _, a_, b_ in fat[:4])))
# 定律二：船的水路每个点都在底账水 + 画上水
bad = tot = 0
for s in F.get('ships', []):
    P = s.get('path', [])
    for p0, p1 in zip(P, P[1:]):
        L = max(1, int(np.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 4))
        for t in range(L + 1):
            x = p0[0] + (p1[0] - p0[0]) * t / L; y = p0[1] + (p1[1] - p0[1]) * t / L
            i, j = int(x // RM), int(y // RM)
            if min(x, y, PW * RM - x, PH * RM - y) < 30: continue   # 船从图外驶入，图边 30 像素不算
            tot += 1
            if not (0 <= j < PH and 0 <= i < PW) or landm[j, i] or not pw[j, i]: bad += 1
res.append(('定律二 · 浮得住：船的水路都在底账和画都认的水上', bad == 0 and tot > 0, f'{bad}/{tot} 个点不在两边都认的水上'))
# 定律四：只报数
x = int((g == 'x').sum())
res.append((f'定律四 · 对得上：底账和画对不上的岸 {x} 格（目标 0，只报数）', True, ''))

for name, ok, why in res: print(('✅ ' if ok else '❌ ') + name + ('' if ok or not why else f'  —— {why}'))
sys.exit(sum(1 for _, ok, _ in res if not ok))
