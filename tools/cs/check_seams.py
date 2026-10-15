#!/usr/bin/env python3
"""/goal 5 G1 检查：瓦片无缝。读 docs/living/tiles（meta.alias 解析去重），每一级、每个关键年拼出整张图：
 ① 接缝：沿每条街区归属边界（OWN 换主处）和每条瓦片边，跨线两侧各 2 px 的平均色（沿线 32 px 一段取平均）之差 step，
    和离线 ±8 px 处同样量出的 ctrl 比；step > max(STEP_MIN, K×ctrl) 算一段跳变。每类线跳变段占比 ≤ 1%。
 ② 水陆：底账（engine/terrain.land() 去掉在世的港池 harbor）为水、画上不是水（蓝 > 红+15 且 蓝 > 绿-10），或反之，
    离岸线 2 世界单位以内不算；在级 1 上量，错占 ≤ 0.5%。
 ③ 空洞：整个瓦片格（世界框）内，缺瓦片或 alpha=0 的像素，必须 0。
 街巷级地面 g/<年>（级 0）同样量 ①③。
用法: python3 check_seams.py [--quick] [--gate] [--set-base]（--quick 只量级 1–4 和最后一年；--gate G1 落地前的过渡闸：不比 factory/seams_base.json 差即过）  输出 tools/cs/factory/out/seams.json ——Hark（CS线）"""
import json, os, sys, math
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
T = os.path.join(ROOT, 'docs', 'living', 'tiles'); sys.path.insert(0, os.path.join(ROOT, 'engine'))
M = json.load(open(os.path.join(T, 'meta.json')))
TP = M['tile_px']; S = M['scale']; TU = M['tile_units']; X0, Y0 = M['origin']; NX, NY = M['grid']
STEP_MIN, K, SEG, MAXFAIL, MAXWATER = 6.0, 2.5, 32, 0.01, 0.005
QUICK = '--quick' in sys.argv
YEARS = M['years'][-1:] if QUICK else M['years']
LEVELS = [l for l in sorted(M['levels'], key=int) if not (QUICK and l == '0')]

def key(Y, l, tx, ty, gr=False):
    a = M.get('alias', {}).get(Y if gr else f'{Y}/{l}', {}); r = a.get(f'{tx}_{ty}')
    if gr: return f'{r if r is not None else Y}/{tx}_{ty}'
    return f'{r if r is not None else Y}/{l}/{tx}_{ty}'

def mosaic(Y, l, gr=False):
    l = int(l); W, H = math.ceil(NX * TP / 2 ** l), math.ceil(NY * TP / 2 ** l)
    nx, ny = math.ceil(W / TP), math.ceil(H / TP)
    im = np.zeros((H, W, 4), np.uint8); miss = 0
    for ty in range(ny):
        for tx in range(nx):
            p = os.path.join(T, 'g', _gk(Y, tx, ty) + '.webp') if gr else os.path.join(T, key(Y, l, tx, ty) + '.webp')
            if not os.path.exists(p): miss += 1; continue
            t = np.asarray(Image.open(p).convert('RGBA'))
            h, w = min(t.shape[0], H - ty * TP), min(t.shape[1], W - tx * TP)
            im[ty * TP:ty * TP + h, tx * TP:tx * TP + w] = t[:h, :w]
    return im, miss, nx * ny

def _gk(Y, tx, ty):
    a = M.get('alias', {}).get(f'g/{Y}', {}); r = a.get(f'{tx}_{ty}')
    r = r[2:] if isinstance(r, str) and r.startswith('g/') else r
    return f'{r if r is not None else Y}/{tx}_{ty}'

def own(l):
    """归属图（级 l 分辨率）：tile_bake 的 ORDER/OWN 同一规则，从 meta.quarters 的像素框重建"""
    f = 2 ** int(l); W, H = math.ceil(NX * TP / f), math.ceil(NY * TP / f)
    O = np.full((H, W), -1, np.int8)
    for i, q in enumerate(M['owner_order']):
        ox, oy, w, h = M['quarters'][q]; v = O[round(oy / f):round((oy + h) / f), round(ox / f):round((ox + w) / f)]; v[v < 0] = i
    return O

def segs_step(rgb, lines, axis, al=None):
    """lines: [(c, y0, y1)] 竖线（axis=1，x=c 两侧）或横线（axis=0）。返回 (段数, 跳变段数, 最大 step)"""
    n = bad = 0; mx = 0.0
    H, W = rgb.shape[:2]
    for c, a0, a1 in lines:
        lim = W if axis == 1 else H
        if c - 10 < 0 or c + 10 > lim: continue
        def band(o0, o1):
            return (rgb[a0:a1, c + o0:c + o1] if axis == 1 else rgb[c + o0:c + o1, a0:a1].transpose(1, 0, 2)).mean(1)
        A, B = band(-2, 0), band(0, 2)
        AL = None if al is None else (al[a0:a1, c - 10:c + 10] if axis == 1 else al[c - 10:c + 10, a0:a1].T).all(1)
        CA, CB = band(-10, -8), band(-8, -6); DA, DB = band(6, 8), band(8, 10)
        for s in range(0, a1 - a0 - SEG + 1, SEG):
            sl = slice(s, s + SEG)
            if AL is not None and not AL[sl].all(): continue   # 贴着空洞的段归 ③ 管
            st = float(np.linalg.norm(A[sl].mean(0) - B[sl].mean(0)))
            ct = max(float(np.linalg.norm(CA[sl].mean(0) - CB[sl].mean(0))), float(np.linalg.norm(DA[sl].mean(0) - DB[sl].mean(0))))
            n += 1; mx = max(mx, st)
            if st > max(STEP_MIN, K * ct): bad += 1
    return n, bad, mx

def runs(mask1d):
    out = []; i = 0; L_ = len(mask1d)
    while i < L_:
        if mask1d[i]:
            j = i
            while j < L_ and mask1d[j]: j += 1
            out.append((i, j)); i = j
        else: i += 1
    return out

def seam_lines(O, al):
    """归属边界（两侧都有主、主不同）→ 竖线/横线；只取两侧都有像素的段"""
    V = (O[:, 1:] != O[:, :-1]) & (O[:, 1:] >= 0) & (O[:, :-1] >= 0)
    Hh = (O[1:, :] != O[:-1, :]) & (O[1:, :] >= 0) & (O[:-1, :] >= 0)
    vl = [(x + 1, a, b) for x in np.where(V.any(0))[0] for a, b in runs(V[:, x])]
    hl = [(y + 1, a, b) for y in np.where(Hh.any(1))[0] for a, b in runs(Hh[y, :])]
    return vl, hl

def tile_lines(W, H):
    return [(x, 0, H) for x in range(TP, W, TP)], [(y, 0, W) for y in range(TP, H, TP)]

_LW = {}
def ledger_water(Y, l):
    """底账水面（级 l 分辨率）：land() 外 + 在世港池；附带岸线 2 单位缓冲带（不计）"""
    from terrain import land
    from scipy import ndimage as ndi
    f = 2 ** int(l); W, H = math.ceil(NX * TP / f), math.ceil(NY * TP / f); s = S / f
    if 'land' not in _LW: _LW['land'] = land(); _LW['W'] = json.load(open(os.path.join(ROOT, 'world.json')))
    m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m); Lg = _LW['land']
    for g in (Lg.geoms if hasattr(Lg, 'geoms') else [Lg]):
        d.polygon([((x - X0) * s, (y - Y0) * s) for x, y in g.exterior.coords], fill=255)
        for r in g.interiors: d.polygon([((x - X0) * s, (y - Y0) * s) for x, y in r.coords], fill=0)
    for st in _LW['W']['structures']:
        if st.get('type') == 'harbor' and st['geom']['type'] == 'polygon' and st['built'] <= Y and not (st.get('destroyed') and st['destroyed'] <= Y):
            d.polygon([((x - X0) * s, (y - Y0) * s) for x, y in st['geom']['coords']], fill=0)
    lw = np.asarray(m) == 0
    band = ndi.binary_dilation(lw, iterations=max(1, round(2 * s))) & ndi.binary_dilation(~lw, iterations=max(1, round(2 * s)))
    return lw, band

def main():
    R = {'levels': {}, 'ground': {}, 'fail': []}
    for Y in YEARS:
        for l in LEVELS:
            im, miss, nt = mosaic(Y, l); rgb = im[..., :3].astype(np.float32); al = im[..., 3] > 0
            O = own(l); O = O[:im.shape[0], :im.shape[1]]
            qv, qh = seam_lines(O, al); tv, th = tile_lines(im.shape[1], im.shape[0])
            qs = [a + b for a, b in zip(segs_step(rgb, qv, 1, al), segs_step(rgb, qh, 0, al))][:2]
            ts = [a + b for a, b in zip(segs_step(rgb, tv, 1, al), segs_step(rgb, th, 0, al))][:2]
            holes = int((~al).sum())
            r = {'quarter_seg': qs[0], 'quarter_jump': qs[1], 'tile_seg': ts[0], 'tile_jump': ts[1], 'missing_tiles': miss, 'of_tiles': nt, 'hole_px': holes}
            if l == '1':
                lw, band = ledger_water(int(Y), l); a = rgb
                pw = (a[..., 2] > a[..., 0] + 15) & (a[..., 2] > a[..., 1] - 10)
                ok = al & ~band; r['water_mismatch'] = round(float(((pw != lw) & ok).sum() / max(1, ok.sum())), 4)
            R['levels'][f'{Y}/{l}'] = r
            qf = qs[1] / max(1, qs[0]); tf = ts[1] / max(1, ts[0])
            if qf > MAXFAIL: R['fail'].append(f'{Y}/{l} 街区缝跳变 {qs[1]}/{qs[0]}')
            if tf > MAXFAIL: R['fail'].append(f'{Y}/{l} 瓦片缝跳变 {ts[1]}/{ts[0]}')
            if holes: R['fail'].append(f'{Y}/{l} 空洞 {holes} px（缺 {miss}/{nt} 块）')
            if r.get('water_mismatch', 0) > MAXWATER: R['fail'].append(f'{Y}/{l} 水陆错 {r["water_mismatch"]:.2%}')
            print(Y, l, r, flush=True)
    if not QUICK:
        for Y in M['street']['ground_keys']:
            im, miss, nt = mosaic(Y, 0, gr=True); rgb = im[..., :3].astype(np.float32); al = im[..., 3] > 0
            O = own(0)[:im.shape[0], :im.shape[1]]; qv, qh = seam_lines(O, al)
            qs = [a + b for a, b in zip(segs_step(rgb, qv, 1, al), segs_step(rgb, qh, 0, al))][:2]
            R['ground'][str(Y)] = {'quarter_seg': qs[0], 'quarter_jump': qs[1], 'missing_tiles': miss, 'of_tiles': nt, 'hole_px': int((~al).sum())}
            if qs[1] / max(1, qs[0]) > MAXFAIL: R['fail'].append(f'g/{Y} 街区缝跳变 {qs[1]}/{qs[0]}')
            if miss: R['fail'].append(f'g/{Y} 缺地面瓦片 {miss}/{nt}')
            print('g', Y, R['ground'][str(Y)], flush=True)
    os.makedirs(os.path.join(HERE, 'factory', 'out'), exist_ok=True)
    json.dump(R, open(os.path.join(HERE, 'factory', 'out', 'seams.json'), 'w'), ensure_ascii=False, indent=1)
    print('check_seams:', 'PASS' if not R['fail'] else f'FAIL {len(R["fail"])} 项'); [print(' ', f) for f in R['fail'][:40]]
    BP = os.path.join(HERE, 'factory', 'seams_base.json')
    if '--set-base' in sys.argv: json.dump(R, open(BP, 'w'), ensure_ascii=False, indent=0); print('基线已写', BP)
    if '--gate' in sys.argv and R['fail'] and os.path.exists(BP):
        # 过渡闸（G1 落地前）：不许比立项基线更差；G1 落地后去掉 --gate，要求全过
        B = json.load(open(BP)); worse = []
        for k, r in list(R['levels'].items()) + [('g/' + k, v) for k, v in R['ground'].items()]:
            b = (B['levels'].get(k) if not k.startswith('g/') else B['ground'].get(k[2:]))
            if not b: continue
            for f in ('quarter_jump', 'tile_jump', 'hole_px', 'missing_tiles'):
                if r.get(f, 0) > b.get(f, 0) * 1.05 + 2: worse.append(f'{k} {f} {b.get(f)}→{r.get(f)}')
            if r.get('water_mismatch', 0) > b.get('water_mismatch', 1) + 0.001: worse.append(f'{k} water {b.get("water_mismatch")}→{r["water_mismatch"]}')
        print('闸（不比基线差）:', 'PASS' if not worse else 'FAIL'); [print(' ', w) for w in worse[:20]]
        sys.exit(1 if worse else 0)
    sys.exit(1 if R['fail'] else 0)

if __name__ == '__main__': main()
