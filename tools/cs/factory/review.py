#!/usr/bin/env python3
"""查收图：在底账水陆蒙版上标出两版之间改了哪里。 ——Hark（CS线）

用法：python review.py <q> [--base <git ref 或 csN>] [--head <ref>] [--year 50] [--max 6]
  --base csN  = 创建 docs/living/csN 的那次提交（所有者上次看过的版本）
输出：tools/cs/factory/out/<q>_review.jpg

底图：年代画压暗去色；蒙版：蓝 = 底账和画都认的水，红斜线 = 底账和画对不上的岸（定律一的风险区）。
改动按「种类」分：人走的网、街、站位、船的水路、画面像素。改动点聚成团，按大小排序，
先保证每一种改动至少出一个样例，再按大小补满 --max 个编号圈；右栏放每个编号的放大对照（左旧右新）。
其余的团只在角落计数，不画圈——内容再多，所有者也只看几个样例。
"""
import json, os, subprocess, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from scipy import ndimage

ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
Q = sys.argv[1]; YEAR = arg('--year', '50'); MAXN = int(arg('--max', '6'))
LIV = f'docs/living/{Q}'


def ref_of(r):
    if r and r.startswith('cs') and r[2:].isdigit():
        out = subprocess.check_output(['git', 'log', '--diff-filter=A', '--format=%H', '--', f'docs/living/{r}'], cwd=ROOT, text=True).split()
        return out[-1] if out else None
    return r


BASE = ref_of(arg('--base')) or subprocess.check_output(['git', 'rev-parse', 'HEAD~1'], cwd=ROOT, text=True).strip()
HEAD = ref_of(arg('--head', 'HEAD'))


def show(ref, path, binary=False):
    try: b = subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError: return None
    return b if binary else json.loads(b)


def img(ref, path):
    import io
    b = show(ref, path, True); return Image.open(io.BytesIO(b)).convert('RGB') if b else None


sc0, sc1 = show(BASE, f'{LIV}/scene.json') or {}, show(HEAD, f'{LIV}/scene.json')
cj0, cj1 = show(BASE, f'{LIV}/city.json') or {}, show(HEAD, f'{LIV}/city.json')
F0, F1 = sc0.get('fleet', {}), sc1['fleet']
paint1 = img(HEAD, f'{LIV}/ng_af{YEAR}.jpg'); Wp, Hp = paint1.size
W1 = F1['walk']; R = W1['R']; GW, GH = W1['W'], W1['H']

# ---------- 蒙版 ----------
g1 = np.array(list(W1['quay'])).reshape(GH, GW)
water = g1 == 'w'; clash = g1 == 'x'
walk1 = ~np.isin(g1, ['w', 'x'])
if F0.get('walk') and F0['walk'].get('W') == GW and F0['walk'].get('H') == GH:
    g0 = np.array(list(F0['walk']['quay'])).reshape(GH, GW); walk0 = ~np.isin(g0, ['w', 'x'])
else: walk0 = walk1.copy()

# ---------- 改动点（世界像素坐标） ----------
KINDS = {'walk': ('新能走', (60, 200, 90)), 'unwalk': ('不再能走', (255, 60, 60)), 'road': ('街', (245, 200, 40)), 'spot': ('站位', (255, 140, 30)),
         'ship': ('船的水路', (80, 200, 255)), 'paint': ('画面', (230, 70, 230))}
pts = {k: [] for k in KINDS}
for j, i in zip(*np.nonzero(~walk0 & walk1)): pts['walk'].append((i * R + R / 2, j * R + R / 2))
for j, i in zip(*np.nonzero(walk0 & ~walk1)): pts['unwalk'].append((i * R + R / 2, j * R + R / 2))


def poly_pts(P, step=6):
    out = []
    for a, b in zip(P, P[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        out += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n + 1)]
    return out


def rasterize(polys):
    m = np.zeros((GH, GW), bool)
    for P in polys:
        for x, y in poly_pts(P):
            j, i = int(y // R), int(x // R)
            if 0 <= j < GH and 0 <= i < GW: m[j, i] = True
    return m


r0 = rasterize([r['pts'] for r in cj0.get('roads', [])]); r1 = rasterize([r['pts'] for r in cj1.get('roads', [])])
for j, i in zip(*np.nonzero(r0 ^ r1)): pts['road'].append((i * R + R / 2, j * R + R / 2))
S0 = {tuple(p) for k in ('spots', 'pier_spots') for p in F0.get(k, [])}
S1 = {tuple(p) for k in ('spots', 'pier_spots') for p in F1.get(k, [])}
pts['spot'] = [p for p in S0 ^ S1]
sh0 = rasterize([s['path'] for s in F0.get('ships', []) if 'path' in s]); sh1 = rasterize([s['path'] for s in F1.get('ships', []) if 'path' in s])
for j, i in zip(*np.nonzero(sh0 ^ sh1)): pts['ship'].append((i * R + R / 2, j * R + R / 2))
paint0 = img(BASE, f'{LIV}/ng_af{YEAR}.jpg')
if paint0 is not None and paint0.size == paint1.size:
    d = np.abs(np.asarray(paint0, int) - np.asarray(paint1, int)).sum(2) > 60
    d = ndimage.binary_opening(d, iterations=2)
    for j, i in zip(*np.nonzero(d[::R, ::R])): pts['paint'].append((i * R, j * R))

# ---------- 聚团 ----------
clusters = []
for k, P in pts.items():              # 每种改动各自聚团，避免一条长街把全图连成一团
    m = np.zeros((GH, GW), bool)
    for x, y in P:
        j, i = int(y // R), int(x // R)
        if 0 <= j < GH and 0 <= i < GW: m[j, i] = True
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=2))
    for c in range(1, n + 1):
        jj, ii = np.nonzero((lab == c) & m)
        if not len(jj): continue
        clusters.append({'n': len(jj), 'kinds': {k}, 'bbox': [ii.min() * R, jj.min() * R, (ii.max() + 1) * R, (jj.max() + 1) * R],
                         'cx': (ii.min() + ii.max() + 1) / 2 * R, 'cy': (jj.min() + jj.max() + 1) / 2 * R})
clusters.sort(key=lambda c: -c['n'])
picked, covered = [], set()
for c in clusters:                      # 先保证每一种改动都有样例
    if len(picked) < MAXN and c['kinds'] - covered: picked.append(c); covered |= c['kinds']
for c in clusters:                      # 再按大小补满
    if len(picked) < MAXN and c not in picked: picked.append(c)
rest = [c for c in clusters if c not in picked]

# ---------- 画 ----------
FONT = next((p for p in [os.path.join(ROOT, 'tools/cs/factory/fonts/NotoSansSC.otf'), '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                         '/usr/share/fonts/truetype/arphic/uming.ttc'] if os.path.exists(p)), None)
font = lambda s: ImageFont.truetype(FONT, s) if FONT else ImageFont.load_default()


def overlay(paint, walk_grid_old=None):
    base = ImageEnhance.Brightness(ImageEnhance.Color(paint).enhance(.35)).enhance(.75).convert('RGBA')
    m = np.zeros((GH, GW, 4), np.uint8)
    m[water] = (40, 90, 200, 90)
    hatch = ((np.add.outer(np.arange(GH), np.arange(GW)) % 3) == 0)
    m[clash & hatch] = (230, 40, 40, 200); m[clash & ~hatch] = (230, 40, 40, 70)
    base.alpha_composite(Image.fromarray(m, 'RGBA').resize((GW * R, GH * R), Image.NEAREST).crop((0, 0, Wp, Hp)))
    return base


def draw_changes(im, which):
    d = ImageDraw.Draw(im, 'RGBA')
    src = cj1 if which == 1 else cj0; F = F1 if which == 1 else F0
    for r in src.get('roads', []): d.line([tuple(p) for p in r['pts']], fill=(245, 200, 40, 200), width=5)
    for s in F.get('ships', []):
        if 'path' in s: d.line([tuple(p) for p in s['path']], fill=(80, 200, 255, 220), width=4)
    for k in ('spots', 'pier_spots'):
        for x, y in F.get(k, []): d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 140, 30, 255), width=4)
    if which == 1:
        for x, y in pts['walk']: d.rectangle([x - R / 2, y - R / 2, x + R / 2, y + R / 2], fill=(60, 200, 90, 150))
        for x, y in pts['unwalk']: d.rectangle([x - R / 2, y - R / 2, x + R / 2, y + R / 2], fill=(255, 60, 60, 120))
    else:
        for x, y in pts['unwalk']: d.rectangle([x - R / 2, y - R / 2, x + R / 2, y + R / 2], fill=(60, 200, 90, 150))
        for x, y in pts['paint']: d.rectangle([x, y, x + R, y + R], outline=(230, 70, 230, 160))
    return im


new = draw_changes(overlay(paint1), 1)
old = draw_changes(overlay(paint0 if paint0 is not None else paint1), 0)
def focus(c):   # 大团（比如整张街网）只取离团中心最近的那一段做样例
    P = [p for p in pts[next(iter(c['kinds']))] if c['bbox'][0] <= p[0] <= c['bbox'][2] and c['bbox'][1] <= p[1] <= c['bbox'][3]]
    if c['bbox'][2] - c['bbox'][0] <= 500 and c['bbox'][3] - c['bbox'][1] <= 500: return c['cx'], c['cy'], max(c['bbox'][2] - c['bbox'][0], c['bbox'][3] - c['bbox'][1])
    x, y = min(P, key=lambda p: (p[0] - c['cx']) ** 2 + (p[1] - c['cy']) ** 2); return x, y, 300
marked = new.copy(); d = ImageDraw.Draw(marked, 'RGBA')
for k, c in enumerate(picked, 1):
    c['fx'], c['fy'], ext = focus(c); r = max(45, ext / 2 + 25)
    d.ellipse([c['fx'] - r, c['fy'] - r, c['fx'] + r, c['fy'] + r], outline=(255, 255, 255, 255), width=6)
    d.ellipse([c['fx'] + r * .7 - 30, c['fy'] - r * .7 - 30, c['fx'] + r * .7 + 30, c['fy'] - r * .7 + 30], fill=(200, 30, 30, 255))
    d.text((c['fx'] + r * .7, c['fy'] - r * .7), str(k), font=font(44), fill='white', anchor='mm')
for c in rest: d.ellipse([c['cx'] - 6, c['cy'] - 6, c['cx'] + 6, c['cy'] + 6], fill=(255, 255, 255, 150))

# 左：全图；右：编号放大（左旧右新）
MAIN_H = 1400; sc = MAIN_H / Hp; mainW = int(Wp * sc)
CW = 330; colW = CW * 2 + 30; rows = max(1, len(picked))
cellH = min(330, (MAIN_H - 40) // rows)
sheet = Image.new('RGB', (max(mainW + colW + 40, 1260), MAIN_H + 230), (20, 17, 13))
sheet.paste(marked.convert('RGB').resize((mainW, MAIN_H)), (0, 0))
sd = ImageDraw.Draw(sheet)
for k, c in enumerate(picked, 1):
    side = min(600, max(260, max(c['bbox'][2] - c['bbox'][0], c['bbox'][3] - c['bbox'][1]) + 120)) if 'fx' not in c or (c['fx'], c['fy']) == (c['cx'], c['cy']) else 420
    box = [int(c['fx'] - side / 2), int(c['fy'] - side / 2), int(c['fx'] + side / 2), int(c['fy'] + side / 2)]
    y = 20 + (k - 1) * cellH; s_ = cellH - 30
    for m, im in enumerate((old, new)):
        sheet.paste(im.convert('RGB').crop(box).resize((s_, s_)), (mainW + 20 + m * (s_ + 20), y))
    lab_ = '、'.join(KINDS[x][0] for x in sorted(c['kinds']))
    sd.text((mainW + 20, y + s_ + 2), f'{k}  {lab_}  （左旧 右新）', font=font(18), fill=(240, 225, 190))
ly = MAIN_H + 15
title = f'{Q} 查收图 · {YEAR} 年画 · {subprocess.check_output(["git","rev-parse","--short",BASE],cwd=ROOT,text=True).strip()} → {subprocess.check_output(["git","rev-parse","--short",HEAD],cwd=ROOT,text=True).strip()}'
sd.text((20, ly), title, font=font(28), fill=(246, 231, 196))
tot = {k: len(v) for k, v in pts.items()}
sd.text((20, ly + 45), f'共 {len(clusters)} 处改动，圈出 {len(picked)} 处样例（每种改动至少一处）；其余 {len(rest)} 处只点白点。', font=font(22), fill=(230, 215, 180))
sd.text((20, ly + 80), '蓝 = 底账和画都认的水　红斜线 = 底账和画对不上的岸（人和船都不许去）', font=font(22), fill=(230, 215, 180))
x = 20
for k, (nm, col) in KINDS.items():
    sd.rectangle([x, ly + 125, x + 22, ly + 147], fill=col); sd.text((x + 30, ly + 122), f'{nm} {tot[k]}', font=font(22), fill=(230, 215, 180)); x += 200
sd.text((20, ly + 170), f'人走网岸边取整：{int(clash.sum())} 格（8 像素格，只报数；定律四按 4 像素格量底账陆地画成水，见 laws.py）', font=font(22), fill=(255, 150, 140))
os.makedirs(os.path.join(ROOT, 'tools/cs/factory/out'), exist_ok=True)
outp = os.path.join(ROOT, f'tools/cs/factory/out/{Q}_review.jpg'); sheet.save(outp, quality=88)
print(json.dumps({'out': outp, 'clusters': len(clusters), 'picked': [(sorted(c['kinds']), c['n']) for c in picked], 'clash': int(clash.sum()), 'per_kind': tot}, ensure_ascii=False))
