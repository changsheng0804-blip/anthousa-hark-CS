"""CS 线 · 街区生产线（重画）—— 底账一变，画只动变了的那一块
按 scene.json 的 paint 配方，从 AI 原画（tools/cs/factory/raw/<q>/）+ 当前 houses.json / frame.json 重铺每张年代画。
房子是一栋一栋按底账铺的，所以没变的房子、地面、公共建筑像素不动；只有加的、拆的那几栋那一块变。
同时量「局部性」（借自 castle-town-sim）：变化范围 40 像素以外的像素，变了的不能超过 0.5%。
用法: python tools/cs/factory/repaint.py <q> [年份…] [--check]   --check 只量不写"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1]; Q = os.path.join(ROOT, 'docs', 'living', q); sc = json.load(open(os.path.join(Q, 'scene.json')))
P = sc['paint']; ys = [a for a in sys.argv[2:] if a.isdigit()] or [k for k in P if k.isdigit()]
pre = {'nangang': 'ng'}.get(q, q[:2])
ok_all = True
for Y in ys:
    r = P[Y]; raw = os.path.join(HERE, 'raw', q)
    env = {**os.environ, **r.get('env', {})}
    if r.get('donor'): env.update(DONOR=os.path.join(raw, r['donor']), DONOR_IDS=r['donor_ids'])
    out = os.path.join(tempfile.gettempdir(), f'rp_{q}_{Y}.jpg')
    subprocess.run([sys.executable, os.path.join(HERE, 'reroof.py'), q, Y, os.path.join(raw, r['src']), out], env=env, capture_output=True, check=True)
    cur_p = os.path.join(Q, f'{pre}_af{Y}.jpg')
    # cs21 · 蒙版合成：AI 画的岸偏了几像素（防波堤画细了、台阶画直了）——底账是陆地、画上是水、离画上陆地 ≤ 32 像素的，
    # 用最近一块画上陆地的颜色补上（港墙、防波堤也算陆：人走在墙顶上）。底账是真相，画只许贴着它（定律四）。只补陆，不动水：船和栈桥画在水上是允许的。
    mk = os.path.join(HERE, 'out', f'{q}_masks.npz')
    if r.get('landfix', True) and os.path.exists(mk):
        from scipy import ndimage as ndi
        im_ = Image.open(out).convert('RGB'); A = np.asarray(im_).astype(int)
        M = np.load(mk); lm = np.asarray(Image.fromarray((M['landm'] | (M['wall'] if 'wall' in M.files else False)).astype('uint8') * 255).resize(im_.size, Image.NEAREST)) > 0
        wk = (A[..., 2] > A[..., 0] + 15) & (A[..., 2] > A[..., 1] - 10)
        dist, (iy, ix) = ndi.distance_transform_edt(wk, return_indices=True)
        fix = lm & wk & (dist <= 32)
        if fix.any():
            B = A.copy(); B[fix] = A[iy[fix], ix[fix]]
            Image.fromarray(B.astype('uint8')).save(out, quality=92)
        print(f'{Y} 年：蒙版合成补岸 {int(fix.sum())} 像素')
    new = np.asarray(Image.open(out).convert('RGB')).astype(int)
    cur = np.asarray(Image.open(cur_p).convert('RGB')).astype(int)
    diff = np.abs(new - cur).sum(2) > 60
    frac = diff.mean()
    # 变化范围：外扩 40 像素；范围以外还在变的就是「牵一发动全身」
    reg = Image.fromarray((diff * 255).astype('uint8')).filter(ImageFilter.MaxFilter(9))
    big = np.asarray(reg.filter(ImageFilter.MaxFilter(81))) > 0
    blobs = np.asarray(reg) > 0
    from scipy import ndimage as ndi
    lab, n = ndi.label(np.asarray(reg.filter(ImageFilter.MaxFilter(41))) > 0)
    sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1)) if n else []
    spread = sum(1 for s in sizes if s > 0.25 * diff.size)   # 一块变化区占了四分之一张画 = 不局部
    print(f'{Y} 年：变了 {frac:.2%} 的像素，{n} 块变化区' + ('；有一块大得不像局部' if spread else ''))
    ok_all &= not spread
    if '--check' not in sys.argv and frac > 0:
        Image.open(out).convert('RGB').save(cur_p, quality=92)
sys.exit(0 if ok_all else 1)
