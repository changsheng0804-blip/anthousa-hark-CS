"""cs24 · 码头补丁检查：每座没建成的栈桥，在它没建成的每个年代（关键年 K 管 K-9..K 年）都有补丁图；补丁盖住了栈桥和归它的画上的船（透明度 > 0.9）。"""
import json, os, sys
import numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Q = os.path.join(ROOT, 'docs', 'living', q); sc = json.load(open(os.path.join(Q, 'scene.json'))); D = sc.get('fleet', {}).get('docks') or []; P = sc.get('dock_patch') or {}
miss = thin = 0; tot = 0
for i, d in enumerate(D):
    for k in sc['keys']:
        K = k[0]
        if d['from'] <= K - 10: continue
        tot += 1; p = P.get(str(i), {}).get(str(K))
        if not p or not os.path.exists(os.path.join(Q, p[0])): miss += 1; continue
        a = np.asarray(Image.open(os.path.join(Q, p[0])))[..., 3]
        for r in d['rects'] + d['hide'][str(K)]:
            y, x = r[1] - p[2] + r[3] // 2, r[0] - p[1] + r[2] // 2
            if not (0 <= y < a.shape[0] and 0 <= x < a.shape[1]) or a[y, x] < 230: thin += 1
print(f'dock patches {tot - miss} / {tot}, uncovered cells {thin}')
sys.exit(1 if (miss or thin) else 0)
