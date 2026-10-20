#!/usr/bin/env python3
"""南港 lookdev：两次渲染的数字对不对得上（CS 线，2026-10-20）。

拆模块（第 2 轮第 0 步）用它证明「拆了没变样」；模块代理用它证明「没把别人那几带弄坏」。
  python3 tools/cs/lookdev/match.py --renders /tmp/me                       # 对 baseline/stats.json 的 render 一侧
  python3 tools/cs/lookdev/match.py --renders /tmp/me --against /tmp/before  # 对另一次渲染（同一套指标现算）
  python3 tools/cs/lookdev/match.py --renders /tmp/me --skip water            # 模块代理：跳过自己那几带和全局，只看别人的带
判据（全局 + 每条带）：|ΔL*| < 1，边缘密度相差 < 5%（相对）。不过返回 1。
指标和 compare.py 完全同一套（直接 import 它的 stats）。
"""
import argparse, json, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from compare import stats, SZ, ROOT  # noqa: E402


def load(p):
    return Image.open(p).convert('RGB').resize(SZ, Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--renders', required=True)
    ap.add_argument('--against', default='docs/cs/lookdev/baseline/stats.json', help='stats.json 或一个装 shotN.png 的目录')
    ap.add_argument('--shots', default='docs/living/nodes/nangang/shots.json')
    ap.add_argument('--dl', type=float, default=1.0)
    ap.add_argument('--edge', type=float, default=0.05)
    ap.add_argument('--skip', default='', help='逗号分隔的模块名：owner 含这些名字的带、以及全局行，不算（自己就是要改它们）')
    a = ap.parse_args()
    P = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)
    S = json.load(open(P(a.shots), encoding='utf-8'))
    ref = P(a.against)
    base = {s['id']: s for s in json.load(open(ref, encoding='utf-8'))['shots']} if ref.endswith('.json') else None
    ok, rows = True, []
    for shot in S['shots']:
        tp = os.path.join(P(a.renders), f"shot{shot['id']}.png")
        if not os.path.exists(tp):
            continue
        img = load(tp)
        if base is not None:
            if shot['id'] not in base:
                continue
            b = base[shot['id']]
            pairs = [('global', b['render'], stats(img))] + [(f"{bd['y'][0]:.2f}-{bd['y'][1]:.2f} {bd['owner']}", bd['render'], stats(img, *bd['y'])) for bd in b['bands']]
        else:
            bp = os.path.join(ref, f"shot{shot['id']}.png")
            if not os.path.exists(bp):
                continue
            bi = load(bp)
            pairs = [('global', stats(bi), stats(img))] + [(f"{y0:.2f}-{y1:.2f} {o}", stats(bi, y0, y1), stats(img, y0, y1)) for y0, y1, o in shot.get('bands', [])]
        skip = [k for k in a.skip.split(',') if k]
        if skip:
            pairs = [x for x in pairs if x[0] != 'global' and not any(k in x[0].split(' ', 1)[1] for k in skip)]
        for name, r, t in pairs:
            dl = t['L'][0] - r['L'][0]
            de = (t['edge'] - r['edge']) / max(r['edge'], 1e-3)  # 基线边缘≈0 的带按 0.001 算，免得除零
            good = abs(dl) < a.dl and abs(de) < a.edge
            ok &= good
            rows.append(dict(shot=shot['id'], part=name, L_base=r['L'][0], L_new=round(t['L'][0], 2), dL=round(dl, 2),
                             edge_base=r['edge'], edge_new=t['edge'], dEdge_pct=round(de * 100, 1), ok=good))
            print(f"shot{shot['id']} {name:<30} L* {r['L'][0]:6.2f} -> {t['L'][0]:6.2f} (d {dl:+.2f})   edge {r['edge']:.4f} -> {t['edge']:.4f} ({de*100:+.1f}%)  {'ok' if good else 'FAIL'}")
    json.dump(rows, open(os.path.join(P(a.renders), 'match.json'), 'w'), indent=1)
    print('MATCH' if ok else 'NO MATCH', f'(|dL*|<{a.dl}, |d edge|<{a.edge*100:.0f}%)')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
