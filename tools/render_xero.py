#!/usr/bin/env python3
"""Render Xerolophos keyframe base images from the street ledger + hill kit sprites,
so the far view and the deep-zoom composed layer are the same drawing."""
import json, math, sys
sys.path.insert(0, '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/gen')
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
W, H = 1820, 2048
D = json.load(open(X + 'houses.json')); HS = D['houses']; late = D['late']
OLD = json.load(open(X + 'houses_v12.json'))['houses']
S = json.load(open(X + 'streets.json'))
K = X + 'kits/hill/'
sheet = Image.open(K + 'houses.webp').convert('RGBA'); HM = json.load(open(K + 'houses.json'))
shops = Image.open(K + 'shops.webp').convert('RGBA'); SM = json.load(open(K + 'shops.json'))
props = Image.open(K + 'props.webp').convert('RGBA'); PM = {m['k']: m for m in json.load(open(K + 'props.json'))}
JU = json.load(open(X + 'junctions.json'))
orig = {k: Image.open(X + f'xero_af{k}_v12.jpg').convert('RGB') for k in (40, 50, 60)}

def hsh(n, k=0):
    x = (n * 2654435761 + k * 40503) & 0xffffffff; x ^= x >> 15; x = (x * 2246822519) & 0xffffffff; x ^= x >> 13
    return x / 2 ** 32
def wall_x(y): return 587 - 0.2357 * y

# ---- terrain: AF40 painting with the old scattered houses wiped to bare ground ----
t = orig[40].copy()
m = Image.new('L', (W, H), 0); md = ImageDraw.Draw(m)
for h in OLD:
    p = h[4]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4
    if cx < wall_x(cy) + 20: continue
    if h[2] <= 40 < h[3]:
        q = [(cx + (p[i] - cx) * 1.9, cy + (p[i + 1] - cy) * 1.9) for i in range(0, 8, 2)]
        md.polygon(q, fill=255)
m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))
# ground fill: hill dust tinted toward the painting's dry-hill colour
a40 = np.asarray(orig[40]).astype(float)
hill = a40[700:1100, 800:1000].reshape(-1, 3).mean(0)
gt = Image.open(K + 'ground.webp').convert('RGB').resize((48, 48), Image.LANCZOS)
g = Image.new('RGB', (W, H))
for x in range(0, W, 48):
    for y in range(0, H, 48): g.paste(gt, (x, y))
ga = np.asarray(g).astype(float); ga = ga - ga.reshape(-1, 3).mean(0) + hill
noise = np.asarray(Image.effect_noise((W // 64, H // 64), 40).resize((W, H), Image.BICUBIC)).astype(float)[..., None]
ga = ga * 0.55 + hill * 0.45 + (noise - 128) * 0.12
g = Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8))
terrain = Image.composite(g, t, m)

# burnt ground for the fire years: the bare terrain charred, no old painted houses
_bn = np.asarray(Image.effect_noise((W // 16, H // 16), 60).resize((W, H), Image.BICUBIC)).astype(float)[..., None]
_ta = np.asarray(terrain).astype(float)
burnt = Image.fromarray(np.clip(_ta * 0.42 + np.array([38, 32, 28]) * 0.5 + (_bn - 128) * 0.25, 0, 255).astype(np.uint8))
def patch(img, src, poly, grow=10, feather=6):
    mm = Image.new('L', (W, H), 0); ImageDraw.Draw(mm).polygon([tuple(p) for p in poly], fill=255)
    mm = mm.filter(ImageFilter.MaxFilter(grow * 2 + 1)).filter(ImageFilter.GaussianBlur(feather))
    return Image.composite(src, img, mm)

STY = {'m': ((118, 104, 86, 190), (174, 163, 144, 255)), 's': ((140, 118, 88, 110), (200, 182, 146, 215)),
       'c': ((140, 118, 88, 90), (203, 186, 150, 190)), 'l': (None, (205, 189, 154, 165))}
def streets_layer(Y):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for pas in (0, 1):
        for q in S:
            x1, y1, x2, y2, w, k, y = q[:7]
            if y > Y or (len(q) > 7 and q[7] and q[7] <= Y): continue
            col = STY[k][pas]
            if col is None: continue
            ww = w + 2 if pas == 0 else w
            d.line([(x1, y1), (x2, y2)], fill=col, width=int(ww))
            r = ww / 2; d.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=col); d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=col)
    return L.filter(ImageFilter.GaussianBlur(0.8))

SHACKS = [(495, 1240), (1140, 1240)]
cache = {}
def sprite(k, w, h):
    key = (k, w, h)
    if key not in cache:
        if k[0] == 'p': mm = PM[k[1]]; src = props
        else: mm = (SM if k[0] else HM)[k[1]]; src = shops if k[0] else sheet
        cache[key] = src.crop((mm['x'], 0, mm['x'] + mm['w'], mm['h'])).resize((w, h), Image.LANCZOS)
    return cache[key]

SS = 2  # supersample
# ---- houses are drawn from their own footprint: walls rise from the lot, the roof sits on top (hip roof along the long side).
# What you see is exactly the body the street audit checks, so a house can never be drawn over a road.
STYLE = {  # block function -> house look (keep in sync with index.html HSTYLE)
    'market': dict(wall=[(236, 222, 192), (228, 206, 166)], roof=[(198, 104, 58), (206, 118, 64), (188, 96, 56)], awn=1.0, flat=0.05),
    'shops': dict(wall=[(234, 220, 190), (224, 204, 168)], roof=[(192, 100, 60), (180, 92, 56)], awn=0.5, flat=0.06),
    'fine': dict(wall=[(244, 238, 226), (238, 230, 214)], roof=[(200, 112, 66), (190, 104, 62)], court=1, flat=0.0),
    'workshop': dict(wall=[(196, 162, 116), (184, 150, 106), (204, 172, 128)], roof=[(142, 86, 58), (128, 90, 66), (150, 100, 70)], flat=0.45, kiln=0.35),
    'water': dict(wall=[(216, 222, 220), (226, 228, 222)], roof=[(176, 98, 66), (166, 92, 64)], flat=0.12),
    'garrison': dict(wall=[(198, 196, 188), (186, 184, 178)], roof=[(150, 92, 72), (140, 96, 80)], flat=0.15),
    'planned': dict(wall=[(228, 214, 188)], roof=[(184, 94, 58)], flat=0.0),
    'garden': dict(wall=[(206, 182, 140), (196, 172, 132)], roof=[(166, 100, 66)], flat=0.5),
}
WALL = [(228, 212, 182), (216, 194, 156), (238, 228, 206), (204, 176, 136), (224, 204, 172), (210, 200, 184)]
ROOF = [(186, 94, 60), (172, 86, 54), (198, 112, 70), (160, 80, 52), (180, 102, 66), (150, 96, 72)]
LX, LY = -0.6, -0.8   # light from the north-west
def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
import house_types as HT_
def house_parts(h):
    by, P, sh = HT_.geom(h)
    M = {'fill': None, 'edge': 'edge', 'line': 'ridge'}
    out = [('shadow', sh)]
    for kind, lay, poly, col in P:
        out.append((M[kind] or ('wall' if lay == 'w' else 'roof'), poly, col))
    return by, out
def draw_parts(d, sd_, parts, a_mul=1.0):
    S_ = lambda poly: [(x * SS, y * SS) for x, y in poly]
    for kind, poly, *c in parts:
        if kind == 'shadow':
            from_ = poly; hl = S_(from_[:4]) + S_(from_[4:])
            sd_.polygon(S_(hullp(poly)), fill=(50, 32, 14, 70))
        elif kind == 'edge': d.line(S_(poly + poly[:1]), fill=c[0] + (int(255 * a_mul),), width=1)
        elif kind == 'ridge': d.line(S_(poly), fill=c[0] + (int(255 * a_mul),), width=2)
        else: d.polygon(S_(poly), fill=c[0] + (int(255 * a_mul),))
def hullp(pts):
    pts = sorted(set(pts))
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p_ in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p_) <= 0: lo.pop()
        lo.append(p_)
    for p_ in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p_) <= 0: up.pop()
        up.append(p_)
    return lo[:-1] + up[:-1]
def render(Y, crop=None):
    base = terrain.copy()
    if Y >= 42:
        for sx, sy in SHACKS: base = patch(base, g, [(sx-95,sy-75),(sx+95,sy-75),(sx+95,sy+75),(sx-95,sy+75)], 4, 12)
    if Y >= 41: base = patch(base, orig[50], late['cistern_modestus']['p'], 14)
    if 48 <= Y < 54: base = patch(base, burnt, late['fire_ruins']['p'], 6, 14)
    if Y >= 52: base = patch(base, orig[60], late['arian_meeting']['p'], 16)
    if Y >= 54: base = patch(base, orig[60], late['cistern_carriers']['p'], 10)
    base = base.convert('RGBA'); base.alpha_composite(streets_layer(Y))
    big = base.resize((W * SS, H * SS), Image.BICUBIC)
    sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sdr = ImageDraw.Draw(sh)
    lay = Image.new('RGBA', big.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    items = []
    for hh_ in HS:
        if not (hh_[2] <= Y < hh_[3]): continue
        by, parts = house_parts(hh_)
        items.append((by, 'h', parts, hh_[2] == Y))
    for jx, jy, jyr, kind in JU:
        if jyr > Y: continue
        ks = {'well': [(16, 0, 0, 8), (15, 6, 3, 6)], 'stall': [((12 if (jx + jy) % 2 else 17), 0, 0, 8)], 'oven': [(0, 0, 0, 8)]}[kind]
        for pk, dx, dy, sz in ks:
            mm = PM[pk]; sc = sz / max(mm['w'], mm['h'])
            items.append((jy + dy + 2, 'p', (jx + dx, mm['w'] * sc, mm['h'] * sc, ('p', pk)), False))
    items.sort(key=lambda t: t[0])
    for by, kind, data, new in items:
        if kind == 'h':
            draw_parts(dl, sdr, [q for q in data if q[0] == 'shadow'])
    big.alpha_composite(sh.filter(ImageFilter.GaussianBlur(1.2)))
    for by, kind, data, new in items:
        if kind == 'h': draw_parts(dl, sdr, [q for q in data if q[0] != 'shadow'], 0.6 if new else 1.0)
        else:
            cx, w, hh, k = data
            sp = sprite(k, max(2, int(w * SS)), max(2, int(hh * SS)))
            lay.alpha_composite(sp, (int((cx - w / 2) * SS), int((by - hh) * SS)))
    big.alpha_composite(lay)
    out = big.resize((W, H), Image.LANCZOS).convert('RGB')
    if crop: return out
    out.save(X + f'xero_af{Y}.jpg', quality=86)
    return len(items)

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'test':
    o = render(50, crop=True); o.crop((380, 950, 780, 1300)).resize((1200, 1050), Image.LANCZOS).save('/tmp/h_close.jpg', quality=90)
    o.crop((450, 150, 1250, 750)).save('/tmp/h_far.jpg', quality=88); sys.exit()
# ---- ground + timed overlays: the page draws streets and houses itself for every single year
def overlay(name, src, poly, grow, feather, y0, y1):
    mm = Image.new('L', (W, H), 0); ImageDraw.Draw(mm).polygon([tuple(p) for p in poly], fill=255)
    mm = mm.filter(ImageFilter.MaxFilter(grow * 2 + 1)).filter(ImageFilter.GaussianBlur(feather))
    bb = mm.getbbox(); rg = src.convert('RGBA'); rg.putalpha(mm)
    rg.crop(bb).save(X + name, quality=82)
    return dict(f=name, x=bb[0], y=bb[1], a=y0, b=y1)
def ground_files():
    terrain.save(X + 'xero_ground.jpg', quality=86)
    OV = [overlay('ov_cistern_modestus.webp', orig[50], late['cistern_modestus']['p'], 14, 6, 41, 999)]
    for i, (sx, sy) in enumerate(SHACKS):
        OV.append(overlay('ov_shack%d.webp' % i, g, [(sx-95,sy-75),(sx+95,sy-75),(sx+95,sy+75),(sx-95,sy+75)], 4, 12, 42, 999))
    OV.append(overlay('ov_fire.webp', burnt, late['fire_ruins']['p'], 6, 14, 48, 54))
    OV.append(overlay('ov_arian.webp', orig[60], late['arian_meeting']['p'], 16, 6, 52, 999))
    OV.append(overlay('ov_cistern_carriers.webp', orig[60], late['cistern_carriers']['p'], 10, 6, 54, 999))
    json.dump(OV, open(X + 'ground.json', 'w'))
ground_files()
HT_.export(HS, X + 'houses_geom.json'); print('houses_geom.json written')
for Y in (40, 50, 60):
    print(Y, render(Y))
