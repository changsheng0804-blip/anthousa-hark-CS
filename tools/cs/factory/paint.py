"""CS 线 · 街区生产线（第二段：盖章画）
用已经画好的街区当「零件库」：每一栋已画好的房子（屋顶、阴影、脚下的土）都是一个零件，
按底账里新街区每一栋房子的位置、大小、朝向，挑一个形状最像的零件盖上去。地面、街、海、火烧地也从画里取样。
结果和底账逐栋对齐（点哪栋就是哪栋），风格和已有的画一致，零人工。
用法: python tools/cs/factory/paint.py <quarter_id> <year> [donor_dir donor_img donor_year] [variant_seed]"""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIV = os.path.join(ROOT, 'docs', 'living')
PW, PH = 1820, 2048


def polys(hs, Y):
    for h in hs:
        if h[2] <= Y < h[3]:
            p = h[4]
            yield h, [(p[i], p[i + 1]) for i in range(0, len(p), 2)]


def feat(P):
    a = np.array(P, float); c = a.mean(0)
    e = a[1] - a[0]; L1 = np.hypot(*e); L2 = np.hypot(*(a[2] - a[1]))
    ang = math.atan2(e[1], e[0]) % (math.pi / 2)
    return c, max(L1, L2), min(L1, L2), ang


def patch(img, box_, size):
    return img.crop(box_).resize(size, Image.BICUBIC)


def tile(tex, size, seed=0):
    r = random.Random(seed); out = Image.new('RGB', size)
    tw, th = tex.size
    for y in range(-r.randrange(th), size[1], th):
        for x in range(-r.randrange(tw), size[0], tw):
            out.paste(tex, (x, y))
    return out


def main():
    qid, Y = sys.argv[1], int(sys.argv[2])
    ddir, dimg, dY = (sys.argv[3], sys.argv[4], int(sys.argv[5])) if len(sys.argv) > 5 else ('xerolophos', 'xero_af50.jpg', 50)
    seed = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    rnd = random.Random(seed)
    Q = os.path.join(LIV, qid)
    hs = json.load(open(os.path.join(Q, 'houses.json')))['houses']
    fr = json.load(open(os.path.join(Q, 'frame.json')))
    base = Image.open(os.path.join(Q, f'base_{Y}.png')).convert('RGB')
    src = Image.open(os.path.join(LIV, ddir, dimg)).convert('RGB')
    dhs = json.load(open(os.path.join(LIV, ddir, 'houses.json')))['houses']
    east = Image.open(os.path.join(LIV, 'east_af30.jpg')).convert('RGB')

    # --- 零件库：已画好的房子 ---
    lib = []
    for h, P in polys(dhs, dY):
        c, L, l, ang = feat(P)
        if L < 8 or c[0] < 30 or c[1] < 30 or c[0] > PW - 30 or c[1] > PH - 30:
            continue
        lib.append((L, l / L, ang, c, P))
    LA = np.array([[x[0], x[1], x[2]] for x in lib])

    # --- 地面：底图的地形明暗 × 画里取样的土 ---
    srcA = np.asarray(src).astype(float)
    dm = Image.new('L', src.size, 0); dd = ImageDraw.Draw(dm)
    for h, P in polys(dhs, dY):
        dd.polygon(P, fill=255)
    dm = dm.filter(ImageFilter.MaxFilter(31))
    # 找一块没有房子的土地当纹理
    best = None
    for _ in range(400):
        x, y = rnd.randrange(0, PW - 160), rnd.randrange(0, PH - 160)
        if np.asarray(dm.crop((x, y, x + 160, y + 160))).max() == 0:
            p = srcA[y:y + 160, x:x + 160]
            g = p.mean(2).mean()
            if best is None or abs(g - 175) < abs(best[0] - 175):
                best = (g, (x, y))
    gx, gy = best[1]
    ground = src.crop((gx, gy, gx + 160, gy + 160))
    ground = tile(ground, (PW, PH), seed)
    baseA = np.asarray(base).astype(float)
    water = (np.abs(baseA[..., 0] - 70) < 4) & (np.abs(baseA[..., 2] - 118) < 4)
    shade = np.asarray(base.convert('L').filter(ImageFilter.GaussianBlur(6))).astype(float)
    gA = np.asarray(ground).astype(float) * (0.78 + 0.32 * (shade / max(shade[~water].mean(), 1)))[..., None].clip(0.7, 1.15)
    # 海：从城东尖角的画里取一块海
    sea = tile(east.crop((1640, 1700, 1800, 1860)), (PW, PH), seed + 1)
    out = np.where(water[..., None], np.asarray(sea).astype(float), gA)
    canvas = Image.fromarray(out.clip(0, 255).astype('uint8'))
    d = ImageDraw.Draw(canvas)

    # 街：底图里的路色 → 浅土 + 轮辙
    road = (np.abs(baseA[..., 0] - 222) < 3) & (np.abs(baseA[..., 1] - 206) < 3)
    rm = Image.fromarray((road * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(3))
    roadtex = ImageEnhance.Brightness(ground).enhance(1.18)
    canvas = Image.composite(roadtex, canvas, rm)

    # 港：石砌防波堤
    for s in fr['structures']:
        if s['type'] == 'harbor' and s['built'] <= Y:
            pts = [tuple(p) for p in s['pts']] + [tuple(s['pts'][0])]
            ImageDraw.Draw(canvas).line(pts, fill=(158, 146, 120), width=14)
            ImageDraw.Draw(canvas).line(pts, fill=(120, 108, 88), width=4)

    # 火烧地：从画里取一块灰烬
    ash = None
    if Y >= 48:
        burnt = [P for h, P in ((h, [(h[4][i], h[4][i + 1]) for i in range(0, len(h[4]), 2)]) for h in hs) if h[3] == 48 and h[3] <= Y]
        if burnt:
            am = Image.new('L', (PW, PH), 0); ad = ImageDraw.Draw(am)
            for P in burnt:
                c = np.array(P).mean(0); ad.ellipse([c[0] - 22, c[1] - 22, c[0] + 22, c[1] + 22], fill=255)
            am = am.filter(ImageFilter.GaussianBlur(14))
            ashA = np.asarray(canvas).astype(float) * 0.38 + np.array([22, 18, 15])
            ash = Image.fromarray(ashA.clip(0, 255).astype('uint8'))
            fade = min(1.0, max(0.25, 1 - (Y - 48) / 14))  # 灰烬随年月淡去
            canvas = Image.composite(ash, canvas, am.point(lambda v: int(v * fade)))

    # --- 盖章：每一栋房子 ---
    items = sorted(polys(hs, Y), key=lambda t: np.array(t[1])[:, 1].mean())
    for h, P in items:
        c, L, l, ang = feat(P)
        q = np.array([L, l / L, ang])
        dist = np.abs(LA[:, 0] - L) / max(L, 1) * 2 + np.abs(LA[:, 1] - q[1]) * 1.5 + np.abs(LA[:, 2] - ang) * 1.2
        cand = np.argsort(dist)[:12]
        L0, r0, a0, c0, P0 = lib[int(cand[(h[0] * 7919 + seed) % len(cand)])]
        k = 1.7
        sb = [c0[0] - L0 * k / 2, c0[1] - L0 * k / 2, c0[0] + L0 * k / 2, c0[1] + L0 * k / 2]
        tb = [c[0] - L * k / 2, c[1] - L * k / 2, c[0] + L * k / 2, c[1] + L * k / 2]
        tw, th = max(2, int(tb[2] - tb[0])), max(2, int(tb[3] - tb[1]))
        piece = src.crop(tuple(int(v) for v in sb)).resize((tw, th), Image.BICUBIC)
        rot = math.degrees(ang - a0)
        if abs(rot) > 1:
            piece = piece.rotate(-rot, Image.BICUBIC)
        m = Image.new('L', (tw, th), 0); md = ImageDraw.Draw(m)
        md.polygon([((x - tb[0]) , (y - tb[1])) for x, y in P], fill=255)
        m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
        # 阴影
        sh = Image.new('L', (tw, th), 0); ImageDraw.Draw(sh).polygon([((x - tb[0]) + 3, (y - tb[1]) + 4) for x, y in P], fill=90)
        sh = sh.filter(ImageFilter.GaussianBlur(2.5))
        ox, oy = int(tb[0]), int(tb[1])
        canvas.paste((40, 28, 18), (ox, oy), sh)
        canvas.paste(piece, (ox, oy), m)

    # 公共建筑：石灰色、带阴影和柱廊线（以后换成 AI 画的建筑零件）
    d = ImageDraw.Draw(canvas)
    for s in fr['structures']:
        if s['geom'] == 'polygon' and s['type'] not in ('harbor', 'district', 'farmland') and s['built'] <= Y and not (s['destroyed'] and s['destroyed'] <= Y):
            pts = [tuple(p) for p in s['pts']]
            d.polygon([(x + 6, y + 8) for x, y in pts], fill=(60, 45, 30))
            d.polygon(pts, fill=(226, 214, 190), outline=(110, 92, 70))
            a = np.array(pts, float); x0, y0 = a.min(0); x1, y1 = a.max(0)
            for t in np.linspace(0.12, 0.88, 7):
                d.line([(x0 + (x1 - x0) * t, y0 + 6), (x0 + (x1 - x0) * t, y1 - 6)], fill=(196, 180, 150), width=2)
    name = f'{qid}_af{Y}_s{seed}.jpg'
    canvas.save(os.path.join(Q, name), quality=88)
    print(name)


if __name__ == '__main__':
    main()
