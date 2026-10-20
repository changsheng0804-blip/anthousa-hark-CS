#!/usr/bin/env python3
"""地标轮廓/比例对照（CS 线，landmark 试点，2026-10-20）。

颜色统计（compare.py）看不出「柱子太粗、像太小、基座太高」，这个工具专看形：
  1. 渲染一侧的蒙版：3d.html?shot=N&only=landmarks&lmmask=1 —— landmarks 模块把自己的材质全换成纯品红（不吃色调映射和雾），
     抠品红像素（render.py --param "only=landmarks&lmmask=1"）。
  2. 参考一侧的蒙版：手工/半自动做好的黑白 png（白 = 地标），和参考图同尺寸，存在参考图旁边。
  3. 比：包围盒高宽比；按行宽剖面切出 基座 / 柱身（含柱础）/ 柱头 / 像（含像座）四段的高度占比；
     IoU 两种对齐：(a) 两个包围盒各自缩放到同一个框（只比形状），(b) 只按高度等比缩放、底边中点对齐（形状 + 粗细）。
用法：
  python3 tools/cs/lookdev/silhouette.py --ref-mask docs/cs/lookdev/landmarks/column/refs/ref1_mask.png \\
      --render /tmp/x/shot5.png --out /tmp/x/silhouette   # → silhouette.json + silhouette.png（左参考蒙版 | 右渲染蒙版 | 叠合）
分段规则（行宽 w(y) = 该行蒙版像素数）：w_s = 柱身中段（高 35–65%）行宽中位数；
  基座 = 从底往上（先跳过 3/4 视角下的底角窄行）w > 1.8·w_s 的连续段；柱头 = 以柱身 30–38% 高的宽 w_t 为准，顶板 = 上部 35% 里最宽的行，往上到 w ≤ 1.25·w_t、往下到 w ≤ 1.1·w_t；像 = 柱头顶以上全部（含像座）。
"""
import argparse, json, os
import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def mask_from_render(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)
    return (a[..., 0] > 170) & (a[..., 1] < 90) & (a[..., 2] > 170)


def mask_from_png(p):
    a = np.asarray(Image.open(p).convert('L'))
    return a > 127


def bbox(m):
    ys, xs = np.nonzero(m)
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1


def parts(m):
    y0, y1, x0, x1 = bbox(m)
    sub = m[y0:y1, x0:x1]
    H = sub.shape[0]
    w = sub.sum(1).astype(float)
    ws = np.median(w[int(H * .35):int(H * .65)])
    # 基座：自底往上。3/4 视角下基座最底是一个尖角（行很窄），先跳过最多 12% 高的窄行，再一路走到不宽为止（容忍 3 行的缝）
    i = H - 1
    while i > H * .88 and w[i] <= 1.8 * ws:
        i -= 1
    gap = 0
    while i > 0 and gap <= 3:
        gap = gap + 1 if w[i] <= 1.8 * ws else 0
        i -= 1
    ped_top = i + gap + 1
    # 柱头：以柱身上段（高 30–38%）的宽 w_t 为准；顶板 = 上部 35% 里最宽的一行；往上 w > 1.25·w_t、往下 w > 1.1·w_t（都容忍 3 行缝）
    wt = np.median(w[int(H * .30):int(H * .38)])
    ab = int(np.argmax(w[:int(H * .35)]))
    k, gap = ab, 0
    while k > 0 and gap <= 3:
        gap = gap + 1 if w[k] <= 1.25 * wt else 0
        k -= 1
    cap_top = k + gap + 1
    j, gap = ab, 0
    while j < H - 1 and gap <= 3:
        gap = gap + 1 if w[j] <= 1.1 * wt else 0
        j += 1
    cap_bot = j - gap
    seg = {'statue': cap_top, 'capital': cap_bot - cap_top, 'shaft': ped_top - cap_bot, 'pedestal': H - ped_top}
    return {
        'bbox_px': [int(x0), int(y0), int(x1), int(y1)],
        'height_px': int(H), 'width_px': int(x1 - x0), 'h_to_w': round(H / (x1 - x0), 3),
        'shaft_width_px': round(float(ws), 1), 'shaft_slenderness': round((ped_top - cap_bot) / max(ws, 1), 2),
        'pedestal_width_px': round(float(np.median(w[ped_top:])) if ped_top < H else 0, 1),
        'pedestal_to_shaft_width': round(float(np.median(w[ped_top:])) / ws, 2) if ped_top < H else None,
        'frac': {k_: round(v / H, 3) for k_, v in seg.items()},
        'rows': {'cap_top': int(cap_top), 'cap_bot': int(cap_bot), 'ped_top': int(ped_top)},
    }


def norm_box(m, size):
    y0, y1, x0, x1 = bbox(m)
    return np.asarray(Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).resize(size, Image.BILINEAR)) > 127


def norm_height(m, H, canvasW):
    """按高度等比缩放到 H，底边中点对齐，放进 canvasW 宽的画布"""
    y0, y1, x0, x1 = bbox(m)
    s = H / (y1 - y0)
    W = max(1, int(round((x1 - x0) * s)))
    im = np.asarray(Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
    out = np.zeros((H, canvasW), bool)
    # 以基座（最底 10% 行）的中点对齐
    cols = np.nonzero(im[int(H * .9):].any(0))[0]
    cx = (cols.min() + cols.max()) / 2 if len(cols) else W / 2
    off = int(round(canvasW / 2 - cx))
    xs0, xs1 = max(0, off), min(canvasW, off + W)
    out[:, xs0:xs1] = im[:, xs0 - off:xs1 - off]
    return out


def masked_stats(img_path, m):
    """蒙版里面的 L*/b*/饱和/边缘（同 compare.py 的公式，不缩图，蒙版先收 2 像素避开边）"""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from compare import lab, sobel
    a = np.asarray(Image.open(img_path).convert('RGB').resize((m.shape[1], m.shape[0]))).astype(float)
    L, A, B = lab(a)
    E = sobel(L)
    k = m.copy()
    for _ in range(2):
        k = k & np.roll(k, 1, 0) & np.roll(k, -1, 0) & np.roll(k, 1, 1) & np.roll(k, -1, 1)
    mx, mn = a.max(-1), a.min(-1)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return {'L_mean': round(float(L[k].mean()), 1), 'L_sd': round(float(L[k].std()), 1), 'L_p10_p90': [round(float(np.percentile(L[k], q)), 1) for q in (10, 90)],
            'b_mean': round(float(B[k].mean()), 1), 'sat': round(float(S[k].mean()), 3), 'edge': round(float((E[k] > 8).mean()), 3), 'px': int(k.sum())}


def iou(a, b):
    return float((a & b).sum() / max(1, (a | b).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref-mask', required=True)
    ap.add_argument('--render', required=True, help='lmmask 渲染出来的 png（品红 = 地标）')
    ap.add_argument('--out', required=True, help='输出前缀（.json / .png）')
    ap.add_argument('--ref-img', default=None, help='可选：参考图，配 --render-img 时在两个蒙版里各算一次颜色统计（只看地标本身的颜色）')
    ap.add_argument('--render-img', default=None, help='可选：同机位的全量渲染（不带 lmmask）')
    a = ap.parse_args()
    P = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)
    rm, tm = mask_from_png(P(a.ref_mask)), mask_from_render(P(a.render))
    if not tm.any():
        raise SystemExit('渲染蒙版是空的：页面要带 only=landmarks&lmmask=1')
    R, Tt = parts(rm), parts(tm)
    rb = R['bbox_px']
    size = (rb[2] - rb[0], rb[3] - rb[1])
    i_box = iou(norm_box(rm, size), norm_box(tm, size))
    Hn, Wn = 600, 400
    ra, ta = norm_height(rm, Hn, Wn), norm_height(tm, Hn, Wn)
    i_h = iou(ra, ta)
    out = {'ref': R, 'render': Tt, 'iou_bbox_aligned': round(i_box, 3), 'iou_height_aligned': round(i_h, 3),
           'delta_frac': {k: round(Tt['frac'][k] - R['frac'][k], 3) for k in R['frac']},
           'delta_h_to_w': round(Tt['h_to_w'] - R['h_to_w'], 3),
           'ref_mask': a.ref_mask, 'render_png': a.render}
    if a.ref_img and a.render_img:
        out['in_mask_colour'] = {'ref': masked_stats(P(a.ref_img), rm), 'render': masked_stats(P(a.render_img), tm)}
    os.makedirs(os.path.dirname(P(a.out)) or '.', exist_ok=True)
    json.dump(out, open(P(a.out) + '.json', 'w'), ensure_ascii=False, indent=1)
    # 图：参考蒙版 | 渲染蒙版 | 叠合（白 = 都有，红 = 只参考有，青 = 只渲染有）+ 分段线
    def vis(m, info):
        im = np.stack([m * 230] * 3, -1).astype(np.uint8)
        for k_, c in [('cap_top', (255, 200, 0)), ('cap_bot', (255, 120, 0)), ('ped_top', (0, 160, 255))]:
            y = int(round((info['rows'][k_]) / info['height_px'] * Hn))
            im[max(0, min(Hn - 1, y)), :] = c
        return im
    ov = np.zeros((Hn, Wn, 3), np.uint8)
    ov[ra & ta] = (235, 235, 235); ov[ra & ~ta] = (230, 60, 60); ov[~ra & ta] = (40, 200, 220)
    strip = np.concatenate([vis(ra, R), np.full((Hn, 6, 3), 90, np.uint8), vis(ta, Tt), np.full((Hn, 6, 3), 90, np.uint8), ov], 1)
    Image.fromarray(strip).save(P(a.out) + '.png')
    print(json.dumps({k: out[k] for k in ('iou_bbox_aligned', 'iou_height_aligned', 'delta_h_to_w', 'delta_frac')}, ensure_ascii=False))
    print('ref   ', R['frac'], 'h:w', R['h_to_w'], 'slender', R['shaft_slenderness'], 'ped/shaft', R['pedestal_to_shaft_width'])
    print('render', Tt['frac'], 'h:w', Tt['h_to_w'], 'slender', Tt['shaft_slenderness'], 'ped/shaft', Tt['pedestal_to_shaft_width'])


if __name__ == '__main__':
    main()
