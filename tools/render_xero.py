#!/usr/bin/env python3
"""Render Xerolophos keyframe base images from the street ledger + hill kit sprites,
so the far view and the deep-zoom composed layer are the same drawing."""
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
W, H = 1820, 2048
D = json.load(open(X + 'houses.json')); HS = D['houses']; late = D['late']
OLD = json.load(open(X + 'houses_v12.json'))['houses']
S = json.load(open(X + 'streets.json'))
K = X + 'kits/hill/'
sheet = Image.open(K + 'houses.webp').convert('RGBA'); HM = json.load(open(K + 'houses.json'))
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

def patch(img, src, poly, grow=10, feather=6):
    mm = Image.new('L', (W, H), 0); ImageDraw.Draw(mm).polygon([tuple(p) for p in poly], fill=255)
    mm = mm.filter(ImageFilter.MaxFilter(grow * 2 + 1)).filter(ImageFilter.GaussianBlur(feather))
    return Image.composite(src, img, mm)

STY = {'m': ((118, 104, 86, 190), (174, 163, 144, 255)), 's': ((140, 118, 88, 110), (200, 182, 146, 215)),
       'c': ((140, 118, 88, 90), (203, 186, 150, 190)), 'l': (None, (205, 189, 154, 165))}
def streets_layer(Y):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for pas in (0, 1):
        for x1, y1, x2, y2, w, k, y in S:
            if y > Y: continue
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
        mm = HM[k]; cache[key] = sheet.crop((mm['x'], 0, mm['x'] + mm['w'], mm['h'])).resize((w, h), Image.LANCZOS)
    return cache[key]

SS = 2  # supersample
def render(Y):
    base = terrain.copy()
    if Y >= 42:
        for sx, sy in SHACKS: base = patch(base, g, [(sx-95,sy-75),(sx+95,sy-75),(sx+95,sy+75),(sx-95,sy+75)], 4, 12)
    if Y >= 41: base = patch(base, orig[50], late['cistern_modestus']['p'], 14)
    if 48 <= Y < 54: base = patch(base, orig[50], late['fire_ruins']['p'], 6, 10)
    if Y >= 52: base = patch(base, orig[60], late['arian_meeting']['p'], 16)
    if Y >= 54: base = patch(base, orig[60], late['cistern_carriers']['p'], 10)
    base = base.convert('RGBA'); base.alpha_composite(streets_layer(Y))
    big = base.resize((W * SS, H * SS), Image.BICUBIC)
    sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    items = []
    for hh_ in HS:
        hid, dd, b, e, p = hh_[:5]; fx = hh_[5] if len(hh_) > 5 else 0
        if not (b <= Y < e): continue
        xs = p[0::2]; ys = p[1::2]; cx = sum(xs) / 4; cy = sum(ys) / 4
        bw = max(xs) - min(xs); bh = max(ys) - min(ys)
        k = int(hsh(hid) * len(HM)); mm = HM[k]
        ar = math.hypot(p[0]-p[2], p[1]-p[3]) * math.hypot(p[2]-p[4], p[3]-p[5]); w = math.sqrt(ar) * 1.8; hh = w * mm['h'] / mm['w']; by = cy + bh * .5 + hh * .18
        items.append((by, cx, w, hh, k, b == Y, fx))
        sd.ellipse([(cx + 2 - w * .52) * SS, (by - hh * .22 - hh * .3) * SS, (cx + 2 + w * .52) * SS, (by - hh * .22 + hh * .3) * SS], fill=(50, 32, 14, 56))
    big.alpha_composite(sh)
    items.sort()
    for by, cx, w, hh, k, new, fx in items:
        sp = sprite(k, max(2, int(w * SS)), max(2, int(hh * SS)))
        if fx: sp = ImageOps.mirror(sp)
        if new: sp = sp.copy(); sp.putalpha(sp.getchannel('A').point(lambda v: int(v * .55)))
        big.alpha_composite(sp, (int((cx - w / 2) * SS), int((by - hh) * SS)))
    out = big.resize((W, H), Image.LANCZOS).convert('RGB')
    out.save(X + f'xero_af{Y}.jpg', quality=86)
    return len(items)

for Y in (40, 50, 60):
    print(Y, render(Y))
