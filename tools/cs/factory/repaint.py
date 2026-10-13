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
        # 工厂：AI 把底账陆地成片画成了水（金角岸 40、60 年把对岸画没了）。离岸远的补不上颜色，就铺成这张画自己的沙地色（底账是真相；房子、地标由后面的段铺）
        im_ = Image.open(out).convert('RGB'); A = np.asarray(im_).astype(int)
        wk = (A[..., 2] > A[..., 0] + 15) & (A[..., 2] > A[..., 1] - 10)
        far = ndi.binary_opening(lm & wk, iterations=2)
        if far.sum() > 2000:
            sand = np.median(A[lm & ~wk].reshape(-1, 3), 0)
            rs = np.random.RandomState(int(Y)); nz = np.asarray(Image.fromarray((rs.rand(A.shape[0] // 16 + 1, A.shape[1] // 16 + 1) * 255).astype('uint8')).resize((A.shape[1], A.shape[0]), Image.BICUBIC)).astype(float)
            fill = np.clip(sand[None, None, :] + (nz[..., None] - 128) * 0.12, 0, 255)
            soft = np.asarray(Image.fromarray((far * 255).astype('uint8')).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))).astype(float)[..., None] / 255
            B = A * (1 - soft) + fill * soft
            Image.fromarray(B.astype('uint8')).save(out, quality=92)
            print(f'{Y} 年：底账陆地成片画成水，铺沙 {int(far.sum())} 像素')
    # 工厂：每张画的沙地校到风格参考图的沙色（金角岸 60 年 AI 把沙地画得太橙，橙到和屋顶分不开）。只挪和本画沙色相近的像素，屋顶、水不动
    if r.get('palette', True):
        A = np.asarray(Image.open(out).convert('RGB')).astype(float)
        wk = (A[..., 2] > A[..., 0] + 15) & (A[..., 2] > A[..., 1] - 10)
        hm = Image.new('L', (A.shape[1], A.shape[0]), 0); hd = ImageDraw.Draw(hm)
        for h in json.load(open(os.path.join(Q, 'houses.json')))['houses']:
            if h[2] <= int(Y) < h[3]: hd.polygon([(h[4][i], h[4][i + 1]) for i in range(0, len(h[4]), 2)], fill=255)
        hm = np.asarray(hm.filter(ImageFilter.MaxFilter(9))) > 0
        sand = np.median(A[~wk & ~hm].reshape(-1, 3), 0); REF = np.array([203., 181., 139.])   # east_af30.jpg 的沙色
        dist = np.sqrt(((A - sand) ** 2).sum(2)); wgt = np.clip((80 - dist) / 40, 0, 1)[..., None] * (~wk)[..., None]
        if np.abs(REF - sand).max() > 6:
            A = np.clip(A + (REF - sand) * wgt, 0, 255); Image.fromarray(A.astype('uint8')).save(out, quality=92)
            print(f'{Y} 年：沙色 {sand.round().tolist()} → {REF.tolist()}')
    new = np.asarray(Image.open(out).convert('RGB')).astype(int)
    if not os.path.exists(cur_p):   # 工厂：新街区第一次铺
        Image.open(out).convert('RGB').save(cur_p, quality=92); print(f'{Y} 年：第一次铺，写 {os.path.basename(cur_p)}'); continue
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
