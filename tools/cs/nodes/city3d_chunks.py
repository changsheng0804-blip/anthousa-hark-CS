#!/usr/bin/env python3
"""CS 线 · 全城 3D 分块烘焙（2026-10-20，主人「可以」：南港 3D 渲染器推到全城，分块流式加载）。

输入：docs/living/nodes/city/nodes_net.json（city_merge → build → net → water 的全城节点，17646 户入街）。
输出：docs/living/nodes/city/3d/
  base.json            首屏必取：W/H、elev（同 nodes.json 的 schema）、bands、陆地/海/港池/石堤、29 座地标、水道桥、年份、分块索引
  chunks/f_<i>_<j>.json 近景整块：和 nodes.json 同 schema 的 features（house/street/pier/fountain/cistern）+ trees，全城坐标
  chunks/l_<i>_<j>.json 远景简块：房子 [id,y0,y1,p(8),ht,fn] + 街 [k,w,x0,z0,x1,z1,y0,y1]（远景地面贴图 + 体块用）
分块 = 瓦片格（tiles/meta.json：tile_units × scale = 455 像素，13 × 14），坐标 = 瓦片级 0 像素 = 全城节点像素。
一个要素只进一块：房子按中心、街按中点、栈桥按中点、树按点；跨块的大要素（陆地、海、港池、石堤、地标、水道桥）放 base。
——Hark（CS线）"""
import json, math, os, gzip, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'living', 'nodes', 'city', 'nodes_net.json')
OUT = os.path.join(ROOT, 'docs', 'living', 'nodes', 'city', '3d')
META = json.load(open(os.path.join(ROOT, 'docs', 'living', 'tiles', 'meta.json')))
CS = META['tile_units'] * META['scale']          # 455.0
NI, NJ = META['grid']                             # 13, 14
FN = ['homes', 'shops', 'market', 'workshop', 'garden', 'water', 'garrison', 'dock', 'planned', 'horrea', 'fine']
KS = 'mscl'


def r1(v):
    return round(v, 1)


def dump(path, obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    open(path, 'w', encoding='utf-8').write(s)
    b = s.encode('utf-8')
    return len(b), len(gzip.compress(b, 6))


def main():
    D = json.load(open(SRC, encoding='utf-8'))
    W, H = D['W'], D['H']
    assert abs(NI * CS - W) < 1 and abs(NJ * CS - H) < 1, (W, H, CS)
    cell = lambda x, z: (min(NI - 1, max(0, int(x // CS))), min(NJ - 1, max(0, int(z // CS))))
    full = collections.defaultdict(lambda: {'features': [], 'trees': []})
    low = collections.defaultdict(lambda: {'h': [], 's': []})
    base_f = []
    fn_extra = []
    for f in D['features']:
        t = f['t']
        if t == 'house':
            p = f['p']; c = cell(sum(p[0::2]) / 4, sum(p[1::2]) / 4)
            full[c]['features'].append(f)
            fn = f.get('fn') or 'homes'
            if fn not in FN: FN.append(fn); fn_extra.append(fn)
            low[c]['h'].append([f['id'], f['y0'], -1 if f.get('y1') is None else f['y1'], *[r1(v) for v in p], f.get('ht') or 5, FN.index(fn)])
        elif t == 'street':
            g = f['g']; c = cell((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
            full[c]['features'].append(f)
            low[c]['s'].append([KS.index(f['k']) if f['k'] in KS else 3, f['w'], *[r1(v) for v in g], f['y0'], -1 if f.get('y1') is None else f['y1']])
        elif t == 'pier':
            g = f['g']; full[cell((g[0][0] + g[1][0]) / 2, (g[0][1] + g[1][1]) / 2)]['features'].append(f)
        elif t == 'fountain':
            full[cell(f['x'], f['y'])]['features'].append(f)
        elif t == 'cistern':
            g = f['g']; full[cell(sum(q[0] for q in g) / len(g), sum(q[1] for q in g) / len(g))]['features'].append(f)
        else:   # land / water / mole / landmark / aqueduct：base
            base_f.append(f)
    for tr in D['trees']:
        full[cell(tr[0], tr[1])]['trees'].append(tr)

    os.makedirs(os.path.join(OUT, 'chunks'), exist_ok=True)
    for fn in os.listdir(os.path.join(OUT, 'chunks')):
        os.remove(os.path.join(OUT, 'chunks', fn))
    index = {}
    tot = {'full_raw': 0, 'full_gz': 0, 'low_raw': 0, 'low_gz': 0}
    for c in sorted(set(full) | set(low)):
        i, j = c; k = f'{i}_{j}'
        F = full[c]; L = low[c]
        a = dump(os.path.join(OUT, 'chunks', f'f_{k}.json'), {'i': i, 'j': j, 'x0': r1(i * CS), 'z0': r1(j * CS), 'features': F['features'], 'trees': F['trees']})
        b = dump(os.path.join(OUT, 'chunks', f'l_{k}.json'), {'i': i, 'j': j, 'h': L['h'], 's': L['s']})
        index[k] = {'houses': len(L['h']), 'streets': len(L['s']), 'trees': len(F['trees']), 'feats': len(F['features']),
                    'full': a[0], 'full_gz': a[1], 'low': b[0], 'low_gz': b[1]}
        tot['full_raw'] += a[0]; tot['full_gz'] += a[1]; tot['low_raw'] += b[0]; tot['low_gz'] += b[1]
    base = {'q': 'city', 'W': W, 'H': H, 'elev': D['elev'], 'years': D['years'], 'nodes': D['nodes'], 'bands': D['bands'],
            'features': base_f, 'trees': [], 'pal': [], 'credit': D.get('credit'),
            'chunk': {'size': CS, 'n': [NI, NJ], 'fn': FN, 'ks': KS, 'index': index,
                      'src': 'docs/living/nodes/city/nodes_net.json', 'tool': 'tools/cs/nodes/city3d_chunks.py'}}
    bb = dump(os.path.join(OUT, 'base.json'), base)
    tot['base_raw'], tot['base_gz'] = bb
    tot['chunks'] = len(index)
    hs = sorted(v['houses'] for v in index.values())
    tot['houses_per_chunk_max'] = hs[-1]
    tot['houses'] = sum(hs)
    tot['full_gz_max'] = max(v['full_gz'] for v in index.values())
    print(json.dumps(tot, indent=1))
    json.dump(tot, open(os.path.join(OUT, 'bake.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
