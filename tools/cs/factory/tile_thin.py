#!/usr/bin/env python3
"""全城级栅格减档（叠层 · 2026-10-14）：看不出差别的年份瓦片不再单独存，指回上一份。

字节去重（tile_bake.dedupe）只合并字节全同的瓦片；这里再合并"肉眼看不出"的：
同一级同一位置，和当前根瓦片比，差得明显的像素（任一通道差 >DIFF）占比 < FRAC，
且任何 16×16 小块里这样的像素都不超过 BLOCK（不让一座新房/新地标被并掉）。
只动级 ≥ MIN_LEVEL（全城级；级 0 是最贴近的栅格，一栋房子就几个像素，不碰）。
被并掉的文件删除，meta.alias[<年>/<级>][x_y] 指向根年份——页面原有的别名机制直接生效。

  python3 tools/cs/factory/tile_thin.py            # 就地处理 docs/living/tiles，写 meta.json
  python3 tools/cs/factory/tile_thin.py --dry      # 只报数，不删
tile_bake.py 在字节去重之后调用 thin()，重烤不会把减掉的档又放回来。
"""
import json, os, sys
import numpy as np
from PIL import Image

DIFF, FRAC, BLOCK, MIN_LEVEL = 24, 0.005, 0.04, 1


def _img(p): return np.asarray(Image.open(p).convert('RGB'), np.int16)


def near(a, b):
    if a.shape != b.shape: return False, 1.0
    d = np.abs(a - b).max(2) > DIFF
    f = float(d.mean())
    if f >= FRAC: return False, f
    h, w = d.shape; hh, ww = h // 16 * 16, w // 16 * 16
    blk = d[:hh, :ww].reshape(hh // 16, 16, ww // 16, 16).mean((1, 3))
    return bool(blk.max() <= BLOCK), f


def thin(OUT, years, levels, alias, dry=False):
    """years 升序；alias 就地更新。返回 (省下字节, 报告行)。"""
    saved = 0; rep = []
    for l in sorted(levels, key=int):
        if int(l) < MIN_LEVEL: continue
        ks = set()
        for Y in years:
            d = os.path.join(OUT, str(Y), l)
            if os.path.isdir(d): ks |= {f[:-5] for f in os.listdir(d) if f.endswith('.webp')}
        for xy in sorted(ks):
            root = None; rimg = None; remap = {}   # remap: 被并掉的年份 → 新根
            for Y in years:
                key = f'{Y}/{l}'; p = os.path.join(OUT, str(Y), l, xy + '.webp')
                if os.path.exists(p):
                    im = _img(p)
                    if root is not None:
                        ok, f = near(im, rimg)
                        if ok:
                            b = os.path.getsize(p); saved += b; rep.append((l, Y, xy, root, round(f * 100, 3), b))
                            remap[str(Y)] = root; alias.setdefault(key, {})[xy] = root
                            if not dry: os.remove(p)
                            continue
                    root, rimg = str(Y), im
                else:
                    r = alias.get(key, {}).get(xy)
                    if r is not None and r in remap: alias[key][xy] = remap[r]
    return saved, rep


if __name__ == '__main__':
    OUT = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'living', 'tiles')
    M = json.load(open(os.path.join(OUT, 'meta.json')))
    dry = '--dry' in sys.argv
    al = M.setdefault('alias', {})
    sv, rep = thin(OUT, [str(y) for y in M['years']], list(M['levels']), al, dry)
    by = {}
    for r in rep: by.setdefault(r[0], [0, 0]); by[r[0]][0] += 1; by[r[0]][1] += r[5]
    print('thin', {l: f'{n} 块 {b // 1024}K' for l, (n, b) in sorted(by.items())}, '共', sv // 1024, 'K')
    json.dump(rep, open('/tmp/thin_report.json', 'w'))
    if not dry:
        M['thin'] = {'rule': f'diff>{DIFF} 像素占比<{FRAC*100}% 且 16px 小块≤{BLOCK*100}%，级≥{MIN_LEVEL}', 'tiles': len(rep), 'saved_bytes': sv}
        json.dump(M, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
