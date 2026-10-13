"""CS 线 · 工厂 · 「地」：任何街区都要的那一层，不管有没有港
1. 走得上的网（定律一）：底账是陆地、每张年代画也是陆地的格才能走；底账以外是 w，底账陆地但画成水是 x，能走是 u。8 像素一格，写进 scene.walk。
2. 城里的街：底账里已建的路，切掉落在走不上的格里的几截，写进 city.json roads（定律三：从底账长，不抄）。
3. out/<q>_masks.npz：底账陆地 / 画上的水，给 repaint.py 的蒙版合成用。
有港的街区（scene.fleet）由 heart.py 另算 fleet.walk（带码头方向场），这里照样写 scene.walk，两边一致。
用法: python land.py <q> [--masks-only]   （--masks-only：还没有画时，只写底账陆地蒙版）"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'engine')); sys.path.insert(0, HERE)
from terrain import land
from heart import standing, rdp
PW, PH, R, R8 = 1820, 2048, 4, 8
GW, GH, W8, H8 = PW // R, PH // R, PW // R8, PH // R8


def pool(mk): return np.array(Image.fromarray(mk.astype('uint8') * 255).resize((W8, H8), Image.BOX)) / 255.0


def main():
    q = sys.argv[1]; Q = os.path.join(ROOT, 'docs', 'living', q)
    sc = json.load(open(os.path.join(Q, 'scene.json'))); fr = json.load(open(os.path.join(Q, 'frame.json')))
    x0, y0, _, _ = fr['frame']; S = fr['scale']; Y = max(k[0] for k in sc['keys'])
    m = Image.new('L', (GW, GH), 0); d = ImageDraw.Draw(m); L = land()
    for g in (L.geoms if hasattr(L, 'geoms') else [L]):
        d.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in g.exterior.coords], fill=255)
        for r in g.interiors: d.polygon([((x - x0) * S / R, (y - y0) * S / R) for x, y in r.coords], fill=0)
    for s in fr['structures']:
        if s['type'] == 'harbor' and standing(s, Y): d.polygon([(x / R, y / R) for x, y in s['pts']], fill=0)
    landm = np.asarray(m) > 0
    pw = np.zeros((GH, GW), bool)
    have = [k for k in sc['keys'] if os.path.exists(os.path.join(Q, k[1]))]
    if '--masks-only' not in sys.argv:
        for k in have:
            a_ = np.asarray(Image.open(os.path.join(Q, k[1])).convert('RGB').resize((GW, GH), Image.BOX)).astype(int)
            wk = (a_[..., 2] > a_[..., 0] + 15) & (a_[..., 2] > a_[..., 1] - 10)
            wk = ndi.binary_fill_holes(ndi.binary_closing(wk, iterations=1))
            pw |= ndi.binary_opening(wk, iterations=1)
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    np.savez_compressed(os.path.join(HERE, 'out', f'{q}_masks.npz'), landm=landm, pw=pw, pier=np.zeros_like(landm), fat=np.zeros_like(landm), R=R, wall=np.zeros_like(landm))
    if '--masks-only' in sys.argv:
        print('masks', q, 'land', int(landm.sum())); return
    land8 = pool(landm) >= 0.5
    walk8 = land8 & ~(pool(pw) > 0.3)
    walk = {'R': R8, 'W': W8, 'H': H8, 'quay': ''.join('w' if not land8[j, i] else ('u' if walk8[j, i] else 'x') for j in range(H8) for i in range(W8))}
    if sc.get('fleet', {}).get('walk'):   # 有港：heart.py 的方向场为准，形状必须一样
        walk = sc['fleet']['walk']
    sc['walk'] = {k: walk[k] for k in ('R', 'W', 'H', 'quay')}
    croads = []
    for st in fr['structures']:
        if st['type'] != 'road' or not standing(st, Y): continue
        run = []; P = st['pts']
        for a_, b_ in zip(P, P[1:]):
            n = max(1, int(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) / 8))
            for t in range(n + 1):
                x, y = a_[0] + (b_[0] - a_[0]) * t / n, a_[1] + (b_[1] - a_[1]) * t / n
                j, i = math.floor(y / R8), math.floor(x / R8)
                if 0 <= j < H8 and 0 <= i < W8 and walk8[j, i]: run.append((x, y))
                else:
                    if len(run) >= 6: croads.append((st['id'], run))
                    run = []
        if len(run) >= 6: croads.append((st['id'], run))
    city_roads = [{'id': f'{i}' if k == 0 else f'{i}_{k}', 'pts': [[int(x), int(y)] for x, y in rdp(r_, 2)]} for k, (i, r_) in enumerate(croads)]
    if '--json' in sys.argv:   # 定律三：只算不写，给 laws.py 比
        print(json.dumps({'walk': sc['walk'], '_roads': None if sc.get('fleet') else city_roads}, ensure_ascii=False)); return
    json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
    if not sc.get('fleet'):   # 有港的街区 city roads 归 heart.py
        cj = json.load(open(os.path.join(Q, 'city.json'))); cj['roads'] = city_roads
        json.dump(cj, open(os.path.join(Q, 'city.json'), 'w'), ensure_ascii=False)
        print('roads', [(r_['id'], len(r_['pts'])) for r_ in city_roads])
    print('walk', q, 'walkable', int(walk8.sum()), 'painted-water-on-land', int((land8 & ~walk8).sum()), 'paintings', len(have))


if __name__ == '__main__':
    main()
