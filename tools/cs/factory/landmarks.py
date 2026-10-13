"""CS 线 · cs35 地标单画：AI 只画地标，每个地标一张，全城共用、各年份共用。
python3 landmarks.py <q> drafts   → raw/landmarks/<id>_draft.png（外接矩形摆正后的地基形状）+ PROMPTS.txt，列出缺的
python3 landmarks.py <q> place    → 把画好的 raw/landmarks/<id>.png 按底账地基（最小外接矩形 + 角度）贴回去，供 compose 用
地标种类的画法写在 TYPES 里，是全城一张表；不许按街区写。"""
import json, os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LM = os.path.join(HERE, 'raw', 'landmarks')
BUILD = {'fort', 'forum', 'monument', 'palace', 'hippodrome', 'church', 'granary', 'cistern', 'warehouse', 'gate', 'baths', 'column', 'theatre', 'temple', 'market'}
TYPES = {
 'hippodrome': 'a late-Roman hippodrome: a very long racetrack with one rounded end (sphendone) and starting gates at the flat end, a long central spina with obelisks and statues, tiered stone seating all around, sandy track',
 'palace': 'a late-Roman imperial palace complex: several courtyards with colonnades, gardens with trees, terracotta-roofed halls, a small domed hall, enclosed by a stone wall',
 'forum': 'a late-Roman forum: an open paved stone plaza surrounded by colonnaded porticoes with terracotta roofs, a statue or column in the middle',
 'church': 'an early Christian basilica: long rectangular terracotta-tiled roof with a lower aisle roof on each side, an atrium courtyard with a fountain at the entrance end',
 'granary': 'a Roman horrea granary: a large rectangular warehouse block around a central courtyard, rows of terracotta roofs, thick stone walls',
 'warehouse': 'a Roman harbour warehouse: long rectangular terracotta-roofed storehouses side by side with a loading yard',
 'cistern': 'the top of an underground Roman cistern: a paved stone square with small low domes and well-heads in a regular grid, a little shrine',
 'fort': 'an old Greek acropolis citadel: stone curtain walls with square towers on a rocky hill, a small temple and courtyard inside',
 'monument': 'a Roman tetrapylon milestone monument: a square four-way arch with a small dome, standing on a paved square',
 'gate': 'a Roman city gate with two towers',
 'column': 'a tall honorific column on a paved base',
}
ID = {'church_megale': 'a very large early Christian basilica (the Great Church) with a wooden terracotta roof, two aisles each side, and a big colonnaded atrium',
      'tower_horn': 'a single square stone harbour watchtower with a flat terrace roof and battlements',
      'nymphaeum_great': 'a monumental Roman nymphaeum: a semicircular fountain facade with niches and a long rectangular water basin in front, paved surroundings'}
STYLE = ('Top-down orthographic view seen from directly above, exactly in the painterly map style of the reference image (warm sandstone, terracotta roofs, soft shadows to the lower right). '
         'The building fills the whole picture edge to edge; it fits exactly the grey shape of the first image. Nothing outside the building: pure chroma green #00FF00 background around it. '
         'No text, no labels, no people, no border, no perspective, no horizon.')
def lms(q):
    Q = os.path.join(ROOT, 'docs', 'living', q); F = json.load(open(os.path.join(Q, 'frame.json')))
    fx, fy, fw, fh = F['frame']; S = 1820 / fw; out = []
    for s in F['structures']:
        if s['type'] not in BUILD or s['geom'] != 'polygon': continue
        P = np.array(s['pts'], np.float32)   # frame.json 里已经是街区像素
        if P.shape[0] < 3: continue
        (cx, cy), (w, h), ang = cv2.minAreaRect(P)
        if w < h: w, h, ang = h, w, ang + 90     # 长边当宽
        out.append(dict(id=s['id'], type=s['type'], built=s['built'], destroyed=s.get('destroyed'), poly=P.tolist(), c=[cx, cy], w=w, h=h, ang=ang))
    return out
def draft(L):
    # 把地基转到摆正的外接矩形里，画在 1536 宽的图上（长宽比照地基）
    W = 1536; H = max(256, int(W * L['h'] / L['w'])); im = Image.new('RGB', (W, H), (0, 255, 0)); d = ImageDraw.Draw(im)
    a = -math.radians(L['ang']); cx, cy = L['c']; k = W / L['w']
    pts = [((math.cos(a) * (x - cx) - math.sin(a) * (y - cy)) * k + W / 2, (math.sin(a) * (x - cx) + math.cos(a) * (y - cy)) * k + H / 2) for x, y in L['poly']]
    d.polygon(pts, fill=(200, 200, 200)); return im
def sprite(id_):
    """读 AI 画的地标：去掉抠图剩下的绿边，裁到不透明的外框。"""
    a = np.asarray(Image.open(os.path.join(LM, id_ + '.webp')).convert('RGBA')).astype(np.int16)
    g = (a[..., 1] > a[..., 0] + 30) & (a[..., 1] > a[..., 2] + 30)
    a[g, 3] = 0
    al = cv2.erode((a[..., 3] > 128).astype(np.uint8), np.ones((3, 3), np.uint8))
    a[..., 3] = (cv2.GaussianBlur(al.astype(np.float32), (3, 3), 0) * 255).astype(np.int16)
    ys, xs = np.where(a[..., 3] > 20)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8)


def place(L, W=1820, H=2048):
    """把地标图按底账地基（最小外接矩形 + 角度）贴到 W×H 的透明层上，再用地基形状（放宽 6%）裁一遍。"""
    sp = sprite(L['id']); h, w = sp.shape[:2]
    a = math.radians(L['ang']); cx, cy = L['c']; hw, hh = L['w'] / 2, L['h'] / 2
    ca, sa = math.cos(a), math.sin(a)
    dst = np.float32([[cx + ca * x - sa * y, cy + sa * x + ca * y] for x, y in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]])
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    out = cv2.warpPerspective(sp, cv2.getPerspectiveTransform(src, dst), (W, H), flags=cv2.INTER_AREA, borderValue=(0, 0, 0, 0))
    m = Image.new('L', (W, H), 0); P = L['poly']; px = sum(p[0] for p in P) / len(P); py = sum(p[1] for p in P) / len(P)
    ImageDraw.Draw(m).polygon([(px + (x - px) * 1.06, py + (y - py) * 1.06) for x, y in P], fill=255)
    out[..., 3] = np.minimum(out[..., 3], np.asarray(m)); return out


def compose(q, keys, pre):
    """一张关键年的「画」不再要 AI 整张画：底账草图（房子位置一栋不差）+ 地面沙色 + 水色 + 当年站着的地标图。
    后面 ground_ng 会把沙地、水面换成全城规则生成的，房子由页面画，所以这里只要地标是 AI 画的。"""
    Q = os.path.join(ROOT, 'docs', 'living', q); raw = os.path.join(HERE, 'raw', q); os.makedirs(raw, exist_ok=True)
    PAL = json.load(open(os.path.join(HERE, 'city', 'palette.json'))); sand = np.array(PAL['sand_rgb'])
    wat = cv2.cvtColor(np.uint8([[PAL['water_lab_mean']]]), cv2.COLOR_LAB2RGB)[0, 0]
    LS = lms(q); miss = [L['id'] for L in LS if not os.path.exists(os.path.join(LM, L['id'] + '.webp')) and (L['destroyed'] in (None, 'None') or int(L['destroyed']) > min(keys))]
    for Y in keys:
        b = np.asarray(Image.open(os.path.join(Q, f'base_{Y}.png')).convert('RGB').resize((1820, 2048), Image.NEAREST)).astype(np.int16)
        water = (b[..., 2] > b[..., 0] + 30) & (b[..., 2] > 100) & (b[..., 1] < b[..., 2])
        house = (b[..., 0] > b[..., 1] + 40) & (b[..., 0] > 140)
        out = np.where(water[..., None], wat, sand).astype(np.uint8)
        out[house] = b[house].astype(np.uint8)
        im = Image.fromarray(out).convert('RGBA')
        for L in sorted(LS, key=lambda L: -L['w'] * L['h']):
            if int(L['built']) > Y or (L['destroyed'] not in (None, 'None') and int(L['destroyed']) <= Y): continue
            if L['id'] in miss: continue
            im.alpha_composite(Image.fromarray(place(L)))
        f = os.path.join(raw, f'{pre}{Y}_ai_c1.png'); im.convert('RGB').save(f); print('compose', Y, f)
    if miss: print('缺地标图：', miss)


if __name__ == '__main__':
    q, mode = sys.argv[1], sys.argv[2]; os.makedirs(LM, exist_ok=True)
    if mode == 'drafts':
        miss = []
        for L in lms(q):
            if L['destroyed'] not in (None, 'None') and int(L['destroyed']) <= 40: continue
            if os.path.exists(os.path.join(LM, L['id'] + '.webp')): continue
            draft(L).save(os.path.join(LM, L['id'] + '_draft.png'))
            miss.append(f"{L['id']}\t{L['w']:.0f}x{L['h']:.0f}\tA {ID.get(L['id']) or TYPES[L['type']]}. {STYLE}")
        open(os.path.join(LM, 'PROMPTS.txt'), 'w').write('\n'.join(miss) + '\n'); print('\n'.join(miss)); print('缺', len(miss))
    elif mode == 'compose':
        R = json.load(open(os.path.join(HERE, 'quarters', q + '.json'))); compose(q, R['keys'], {'nangang': 'ng'}.get(q, q[:2]))

