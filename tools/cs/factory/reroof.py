"""CS 线 · 街区生产线（第四段：重铺屋顶）
AI 画得美，但它会把房子「自作主张地排整齐」，和底账里的房子对不上。
这一步：从 AI 自己的画里把每一个屋顶剪下来当零件，把画上原来的房子抹成地面，
再按底账里的每一栋房子（位置、大小、朝向）一个一个铺回去。
结果：画风百分之百是 AI 的，房子百分之百是底账的。
用法: python tools/cs/factory/reroof.py <quarter_id> <year> <ai_img> <out_name>"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIV = os.path.join(ROOT, 'docs', 'living')
PW, PH = 1820, 2048
PAD_L, PAD_B, ASH_D = int(os.environ.get('PAD_L', 11)), int(os.environ.get('PAD_B', 4)), int(os.environ.get('ASH_D', 10))


def main():
    qid, Y, src, outn = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    Q = os.path.join(LIV, qid)
    hs = json.load(open(os.path.join(Q, 'houses.json')))['houses']
    fr = json.load(open(os.path.join(Q, 'frame.json')))
    im = Image.open(src).convert('RGB').resize((PW, PH), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # 屋顶：红陶色（红明显高于蓝，偏暖偏深）
    roof = (r - b > 70) & (r > 120) & (g < r * 0.78)
    roof = ndi.binary_opening(roof, iterations=1)
    # 保护区：公共建筑、港口、水、火烧地 —— 这些保留 AI 的原画
    keep = Image.new('L', (PW, PH), 0); kd = ImageDraw.Draw(keep)
    for s in fr['structures']:
        if s['geom'] == 'polygon' and s['type'] not in ('district', 'farmland') and s['built'] <= Y and not (s['destroyed'] and s['destroyed'] <= Y):
            kd.polygon([tuple(p) for p in s['pts']], fill=255)
    # 验收（accept.py）发现：保护区按圆圈和 15 像素外扩，会把火场和粮仓旁边还站着的房子一起「保护」成 AI 的灰和空地。
    # 改为：公共建筑只外扩 5 像素；火场只保护底账里真正烧掉的那些地块
    keep = np.asarray(keep.filter(ImageFilter.MaxFilter(PAD_L))) > 0
    bk = Image.new('L', (PW, PH), 0); bkd = ImageDraw.Draw(bk)
    for h in hs:
        if h[3] == 48 and Y >= 48:
            bkd.polygon([(h[4][i], h[4][i + 1]) for i in range(0, len(h[4]), 2)], fill=255)
    keepL = keep.copy()   # 公共建筑 + 水：房子不铺进去
    keep |= ndi.binary_dilation(np.asarray(bk) > 0, iterations=PAD_B)
    # AI 画的火烧地如果比底账里真正烧掉的地块大，多出来的部分不算数
    burnt = Image.new('L', (PW, PH), 0); bd = ImageDraw.Draw(burnt)
    for h in hs:
        if h[3] == 48 and Y >= 48 and Y - 48 < 6:
            bd.polygon([(h[4][i], h[4][i + 1]) for i in range(0, len(h[4]), 2)], fill=255)
    bdist = ndi.distance_transform_edt(~(np.asarray(burnt) > 0))
    ash_extra = (np.asarray(Image.fromarray(np.uint8(a.mean(2).clip(0,255))).filter(ImageFilter.GaussianBlur(4))) < 95) & (bdist > ASH_D) & ~(b > r + 15)
    ash_extra = ndi.binary_opening(ash_extra, iterations=3)
    blue = (b > r + 15)
    keep |= ndi.binary_dilation(blue, iterations=6)
    keepL |= ndi.binary_dilation(blue, iterations=6)

    # 1) 零件库：AI 画上的每一个屋顶
    lab, n = ndi.label(roof & ~keep)
    objs = ndi.find_objects(lab)
    lib = []
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = (lab[sl] == i + 1).sum()
        if 10 <= hgt <= 60 and 10 <= wid <= 60 and area > 0.55 * hgt * wid:
            lib.append((max(hgt, wid), min(hgt, wid) / max(hgt, wid), sl, i + 1))
    LA = np.array([[x[0], x[1]] for x in lib], float)

    # 2) 地面：把原来的房子（连阴影）抹掉，用周围的地面色补
    shadow = (a.mean(2) < 95) & ~blue
    dark = (a.mean(2) < 135) & ~blue
    near = ndi.binary_dilation(roof, iterations=6)
    erase = ndi.binary_dilation(roof | (near & dark), iterations=2) & ~keep
    erase |= ndi.binary_dilation(ash_extra, iterations=4) & ~keep
    # AI 自己多画出来的石头铺地 / 柱廊（底账里那里没有公共建筑）也抹掉
    sat = a.max(2) - a.min(2)
    stone = (sat < 52) & (a.mean(2) > 110) & ~blue
    lmk = Image.new('L', (PW, PH), 0); ld = ImageDraw.Draw(lmk)
    for s_ in fr['structures']:
        if s_['geom'] == 'polygon' and s_['type'] not in ('district', 'farmland', 'harbor') and s_['built'] <= Y:
            ld.polygon([tuple(p) for p in s_['pts']], fill=255)
    lmk = np.asarray(lmk) > 0
    dl = ndi.distance_transform_edt(~lmk)
    stray = stone & (dl < 160) & (dl > 6)
    stray = ndi.binary_opening(stray, iterations=2)
    keep &= ~(stray & ~ndi.binary_dilation(blue, iterations=6))
    erase |= ndi.binary_dilation(stray, iterations=3) & (dl > 6)
    ground = a.copy()
    okm = ~erase
    acc = np.zeros_like(a); wsum = np.zeros(a.shape[:2])
    for rad in (6, 14, 30, 70):
        k = ndi.uniform_filter(okm.astype(float), size=2 * rad + 1)
        v = np.stack([ndi.uniform_filter(a[..., c] * okm, size=2 * rad + 1) for c in range(3)], -1)
        fill = v / np.maximum(k, 1e-3)[..., None]
        need = (wsum < 0.5) & (k > (0.15 if rad < 70 else 0.01))
        acc[need] = fill[need]; wsum[need] = 1
    med = np.median(a[okm & ~keep & ~blue], 0)
    acc[wsum < 0.5] = med
    ground[erase] = acc[erase]
    # 给补上的地加一点颗粒，不要太平
    noise = np.random.default_rng(7).normal(0, 6, a.shape[:2])[..., None]
    ground[erase] += noise[erase]
    canvas = Image.fromarray(ground.clip(0, 255).astype('uint8'))
    # 保护区先贴回 AI 原画，再铺房子：火场里幸存的房子也照底账铺上（验收发现原来会被灰盖掉）
    km = Image.fromarray((keep * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(4))
    canvas = Image.composite(im, canvas, km)
    # 公共建筑可以从另一张候选「借」：一张画的火场好、另一张画的粮仓对（DONOR=候选图 DONOR_IDS=id,id）
    if os.environ.get('DONOR'):
        dn = Image.open(os.environ['DONOR']).convert('RGB').resize((PW, PH), Image.LANCZOS)
        dm = Image.new('L', (PW, PH), 0); dd = ImageDraw.Draw(dm)
        for s in fr['structures']:
            if s['id'] in os.environ.get('DONOR_IDS', '').split(','):
                dd.polygon([tuple(p) for p in s['pts']], fill=255)
        dm = dm.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(3))
        canvas = Image.composite(dn, canvas, dm)

    # 3) 按底账铺回每一栋房子（由北往南，南边的压住北边的阴影）
    items = []
    for h in hs:
        if h[2] <= Y < h[3]:
            P = np.array(h[4], float).reshape(-1, 2)
            items.append((P[:, 1].mean(), h, P))
    items.sort(key=lambda t: t[0])
    placed = 0
    for _, h, P in items:
        c = P.mean(0)
        if keepL[int(min(PH - 1, max(0, c[1]))), int(min(PW - 1, max(0, c[0])))]:
            continue
        e1, e2 = P[1] - P[0], P[2] - P[1]
        L1, L2 = np.hypot(*e1), np.hypot(*e2)
        L, l = max(L1, L2), min(L1, L2)
        ang = math.degrees(math.atan2(e1[1], e1[0]))
        d = np.abs(LA[:, 0] - L * 1.05) / L + np.abs(LA[:, 1] - l / L)
        cand = np.argsort(d)[:10]
        _, _, sl, lid = lib[int(cand[(h[0] * 2654435761) % len(cand)])]
        y0, y1, x0, x1 = sl[0].start - 2, sl[0].stop + 6, sl[1].start - 2, sl[1].stop + 6  # 带上右下的阴影
        y0, x0 = max(0, y0), max(0, x0)
        piece = Image.fromarray(a[y0:y1, x0:x1].clip(0, 255).astype('uint8'))
        pm = ((lab[y0:y1, x0:x1] == lid) | (shadow[y0:y1, x0:x1] & ndi.binary_dilation(lab[y0:y1, x0:x1] == lid, iterations=5)))
        pmI = Image.fromarray((pm * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.7))
        sx = (L * 1.12) / max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        nw, nh = max(2, int(piece.width * sx)), max(2, int(piece.height * sx))
        piece, pmI = piece.resize((nw, nh), Image.BICUBIC), pmI.resize((nw, nh), Image.BICUBIC)
        rot = ((ang + 45) % 90) - 45
        if abs(rot) > 2:
            piece = piece.rotate(-rot, Image.BICUBIC, expand=True); pmI = pmI.rotate(-rot, Image.BICUBIC, expand=True)
        canvas.paste(piece, (int(c[0] - piece.width / 2 + 2), int(c[1] - piece.height / 2 + 2)), pmI)
        placed += 1
    canvas.save(os.path.join(Q, outn), quality=88)
    print(outn, 'library', len(lib), 'placed', placed)


if __name__ == '__main__':
    main()
