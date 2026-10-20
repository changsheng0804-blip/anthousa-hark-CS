#!/usr/bin/env python3
"""南港 lookdev 对照：参考图 vs 渲染图的颜色/细节统计 + 并排图（CS 线，2026-10-20）。

  python3 tools/cs/lookdev/compare.py --renders docs/cs/lookdev/out --out docs/cs/lookdev/baseline

每个机位输出：
  cmp_shotN.jpg   左参考、右渲染、下面一条统计
  stats.json      全部数字（给下一轮的验收用）
指标（两张图先缩到同一尺寸 688×384 再算）：
  Lab 均值/σ（L*, a*, b*）           —— 曝光、色偏
  亮度百分位 p02/p10/p50/p90/p98（L*） —— 反差
  亮度直方图距离 EMD（L*，0–100）     —— 整体亮度分布差多少
  饱和度（HSV S 均值）、色彩丰富度（Hasler–Süsstrunk）
  冷暖：b* 均值、暖像素占比 - 冷像素占比
  边缘密度：Sobel(L*) > 8 的像素占比     —— 细节量的代理
  分带：shots.json 的 bands（按参考构图定的横带 → 模块），每带算 ΔL*、Δ饱和、边缘比
"""
import argparse, json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SZ = (688, 384)


def lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return L, a, b


def sobel(L):
    p = np.pad(L, 1, mode='edge')
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy) / 8


def stats(img, y0=0.0, y1=1.0):
    a = np.asarray(img, dtype=np.float64)
    h = a.shape[0]
    a = a[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h))]
    L, A, B = lab(a)
    mx, mn = a.max(-1), a.min(-1)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    rg = a[..., 0] - a[..., 1]
    yb = 0.5 * (a[..., 0] + a[..., 1]) - a[..., 2]
    colourful = math.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * math.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    chroma = np.hypot(A, B)
    warm = ((B > 8) & (chroma > 10)).mean()
    cool = ((B < -4) & (chroma > 6)).mean()
    E = sobel(L)
    hist = np.histogram(L, bins=50, range=(0, 100))[0].astype(float)
    hist /= max(1, hist.sum())
    pct = np.percentile(L, [2, 10, 50, 90, 98])
    return {
        'L': [round(float(L.mean()), 2), round(float(L.std()), 2)],
        'a': [round(float(A.mean()), 2), round(float(A.std()), 2)],
        'b': [round(float(B.mean()), 2), round(float(B.std()), 2)],
        'pct': [round(float(v), 1) for v in pct],
        'sat': round(float(S.mean()), 4),
        'colourful': round(colourful, 2),
        'warm_minus_cool': round(float(warm - cool), 4),
        'edge': round(float((E > 8).mean()), 4),
        '_hist': hist,
    }


def emd(h1, h2):
    return float(np.abs(np.cumsum(h1) - np.cumsum(h2)).sum() * 2.0)  # 每格 2 个 L* 单位


def strip_text(s_ref, s_ren, d):
    f = lambda v: f'{v:+.1f}'
    return [
        f"L* mean/sd  ref {s_ref['L'][0]:.1f}/{s_ref['L'][1]:.1f}   render {s_ren['L'][0]:.1f}/{s_ren['L'][1]:.1f}   dL {f(d['dL'])}   hist EMD {d['emd']:.1f}",
        f"pct p02..p98  ref {'/'.join(f'{v:.0f}' for v in s_ref['pct'])}   render {'/'.join(f'{v:.0f}' for v in s_ren['pct'])}",
        f"a*/b*  ref {s_ref['a'][0]:.1f}/{s_ref['b'][0]:.1f}   render {s_ren['a'][0]:.1f}/{s_ren['b'][0]:.1f}   warm-cool ref {s_ref['warm_minus_cool']:+.2f} render {s_ren['warm_minus_cool']:+.2f}",
        f"sat ref {s_ref['sat']:.2f} render {s_ren['sat']:.2f}   colourful ref {s_ref['colourful']:.0f} render {s_ren['colourful']:.0f}   edge ref {s_ref['edge']:.3f} render {s_ren['edge']:.3f} (x{d['edge_ratio']:.2f})",
    ]


def font(sz):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', '/System/Library/Fonts/Menlo.ttc', '/Library/Fonts/Courier New.ttf']:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def gaps_for(shot, s_ref, s_ren, bands):
    """把差距打成分（越大越差），每条带上归属模块。分数单位：大约「一个明显的台阶」= 1。"""
    g = []
    dL = s_ren['L'][0] - s_ref['L'][0]
    g.append(('exposure (global L* mean)', abs(dL) / 8, 'sky-atmosphere', f'dL* {dL:+.1f}'))
    dsd = s_ren['L'][1] - s_ref['L'][1]
    g.append(('contrast (global L* sd)', abs(dsd) / 5, 'sky-atmosphere', f'dsd {dsd:+.1f}'))
    db = s_ren['b'][0] - s_ref['b'][0]
    g.append(('warmth (global b*)', abs(db) / 5, 'sky-atmosphere', f'db* {db:+.1f}'))
    dc = s_ren['colourful'] - s_ref['colourful']
    g.append(('colourfulness (global)', abs(dc) / 10, 'sky-atmosphere', f'dcolourful {dc:+.0f}'))
    for b in bands:
        y0, y1, owner = b[:3]
        if 'sky' in owner:
            continue  # 天空带的亮度/色已在全局里算给 sky-atmosphere；这里只看有内容的带
        r, t = b[3], b[4]
        er = (t['edge'] + 1e-3) / (r['edge'] + 1e-3)
        g.append((f'detail density band {y0:.2f}-{y1:.2f}', min(4.0, abs(math.log2(er))), owner, f'edge x{er:.2f}'))  # 封顶 4（=差 16 倍），免得一项吃掉排名
        dLb = t['L'][0] - r['L'][0]
        g.append((f'tone band {y0:.2f}-{y1:.2f}', abs(dLb) / 10, owner, f'dL* {dLb:+.1f}'))
        dsb = t['sat'] - r['sat']
        g.append((f'saturation band {y0:.2f}-{y1:.2f}', abs(dsb) / 0.08, owner, f'dsat {dsb:+.2f}'))
    return [{'shot': shot['id'], 'name': shot['name'], 'gap': n, 'score': round(sc, 2), 'owner': o, 'delta': dd} for n, sc, o, dd in g]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', default='docs/living/nodes/nangang/shots.json')
    ap.add_argument('--refs', default='docs/cs/lookdev/refs')
    ap.add_argument('--renders', default='docs/cs/lookdev/out')
    ap.add_argument('--out', default='docs/cs/lookdev/out')
    a = ap.parse_args()
    P = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)
    S = json.load(open(P(a.shots), encoding='utf-8'))
    os.makedirs(P(a.out), exist_ok=True)
    F, F2 = font(13), font(15)
    allstats, allgaps = [], []
    for shot in S['shots']:
        rp, tp = os.path.join(P(a.refs), shot['ref']), os.path.join(P(a.renders), f"shot{shot['id']}.png")
        if not (os.path.exists(rp) and os.path.exists(tp)):
            print('skip', shot['id'], 'missing', rp if not os.path.exists(rp) else tp)
            continue
        ref = Image.open(rp).convert('RGB').resize(SZ, Image.LANCZOS)
        ren = Image.open(tp).convert('RGB').resize(SZ, Image.LANCZOS)
        s_ref, s_ren = stats(ref), stats(ren)
        d = {'dL': s_ren['L'][0] - s_ref['L'][0], 'emd': emd(s_ref['_hist'], s_ren['_hist']),
             'edge_ratio': (s_ren['edge'] + 1e-3) / (s_ref['edge'] + 1e-3)}
        bands = []
        for y0, y1, owner in shot.get('bands', []):
            r, t = stats(ref, y0, y1), stats(ren, y0, y1)
            for x in (r, t):
                x.pop('_hist')
            bands.append([y0, y1, owner, r, t])
        gaps = gaps_for(shot, s_ref, s_ren, bands)
        allgaps += gaps
        for x in (s_ref, s_ren):
            x.pop('_hist')
        allstats.append({'id': shot['id'], 'name': shot['name'], 'ref': s_ref, 'render': s_ren,
                         'delta': {k: round(v, 3) for k, v in d.items()},
                         'bands': [{'y': [b[0], b[1]], 'owner': b[2], 'ref': b[3], 'render': b[4]} for b in bands]})
        # 并排图
        W, H = SZ
        canvas = Image.new('RGB', (W * 2 + 6, H + 30 + 4 * 19 + 12), (24, 22, 20))
        canvas.paste(ref, (0, 30))
        canvas.paste(ren, (W + 6, 30))
        dr = ImageDraw.Draw(canvas)
        dr.text((8, 7), f"shot {shot['id']} · {shot['name']} · REFERENCE", fill=(235, 225, 205), font=F2)
        dr.text((W + 14, 7), f"RENDER  3d.html?shot={shot['id']}", fill=(235, 225, 205), font=F2)
        for y0, y1, owner in shot.get('bands', []):  # 分带刻度：右图左缘
            yy = 30 + int(y0 * H)
            dr.line([(W + 6, yy), (W + 22, yy)], fill=(255, 210, 120), width=2)
            dr.text((W + 25, yy + 1), owner, fill=(255, 220, 150), font=F)
        for i, line in enumerate(strip_text(s_ref, s_ren, d)):
            dr.text((8, 30 + H + 6 + i * 19), line, fill=(220, 214, 200), font=F)
        fn = os.path.join(P(a.out), f"cmp_shot{shot['id']}.jpg")
        canvas.save(fn, quality=86)
        print('wrote', os.path.relpath(fn, ROOT), f"dL {d['dL']:+.1f} emd {d['emd']:.1f} edge x{d['edge_ratio']:.2f}")
    allgaps.sort(key=lambda g: -g['score'])
    # 按 (模块, 差距种类) 跨机位汇总：同一个病在几个机位都出现，排得更前
    agg = {}
    for g in allgaps:
        kind = g['gap'].split(' band')[0].split(' (')[0]
        k = (g['owner'], kind)
        e = agg.setdefault(k, {'owner': g['owner'], 'kind': kind, 'score': 0.0, 'shots': []})
        e['score'] = round(e['score'] + g['score'], 2)
        e['shots'].append(f"{g['shot']}:{g['delta']}")
    by_kind = sorted(agg.values(), key=lambda e: -e['score'])
    json.dump({'shots': allstats, 'gaps_ranked': allgaps, 'gaps_by_module': by_kind}, open(os.path.join(P(a.out), 'stats.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('by module x kind:')
    for e in by_kind[:8]:
        print(f"  {e['score']:5.2f}  {e['owner']:<20} {e['kind']:<22} {', '.join(e['shots'])}")
    print('top gaps:')
    for g in allgaps[:10]:
        print(f"  {g['score']:5.2f}  shot{g['shot']} {g['gap']:<34} {g['delta']:<16} -> {g['owner']}")


if __name__ == '__main__':
    main()
