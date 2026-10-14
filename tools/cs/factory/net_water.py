#!/usr/bin/env python3
"""/goal 4 G1 水网（设计来源：谭线 notes/epic-system.md「公共设施做成网络」，handoff-cs 19b633d）。
水渠 → 蓄水池 / 宁芙泉 → 街角喷泉。节点年份全读底账：world.json 结构的 built；喷泉 = 全城 houses_street 里 lm:fountain 的房，
建成年 = 那栋房的开工年（谭线 fountain 卡，landmarks_city.py 放）。world.json 一字不动。
连法（就近取水，不自编）：
  · 渠桥 → 离它最近的水渠；
  · 蓄水池、宁芙泉 → 离它最近的水渠（优先它建成时已有的渠）；
  · 喷泉 → REACH 世界单位内、喷泉建成时已出水的最近水源；没有就取最近的水源，等那口水源出水才有水（干着）。
出水年 wet = max(建成, 上游 wet)。脉在地下：输出只有节点（点、年份、上游），不带任何画线几何，页面只读「这口泉哪年有水」。
  python3 tools/cs/factory/net_water.py   → docs/living/tiles/net_water.json
——Hark（CS线）"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles')
REACH = 45   # 世界单位（≈ 640 页面 px）：一口喷泉最远从多远的池子引水
M = json.load(open(os.path.join(OUT, 'meta.json'))); S = M['scale']; QS = M['owner_order']
W = json.load(open(os.path.join(ROOT, 'world.json')))['structures']
def cen(s):
    c = s['geom']['coords']; return (sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c))
def dseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
def dline(p, s): c = s['geom']['coords']; return min(dseg(p, c[i], c[i + 1]) for i in range(len(c) - 1))
def end(s): return s.get('destroyed') or None
def main():
    nodes = []; AQ = [s for s in W if s['type'] == 'aqueduct']
    for s in AQ:
        nodes.append({'id': s['id'], 'kind': 'aqueduct', 'src': 'world', 'name': s['name'], 'built': s['built'], 'wet': s['built'], 'fed_by': None, 'end': end(s)})
    by = {n['id']: n for n in nodes}
    def best_aq(p, yr):
        early = [a for a in AQ if a['built'] <= yr]
        return min(early or AQ, key=lambda a: dline(p, a))
    for s in W:
        if s['type'] == 'aqueduct_bridge': k = 'bridge'
        elif s['type'] == 'cistern': k = 'nymphaeum' if s['id'].startswith('nymphaeum') else 'cistern'
        elif s['id'].startswith('nymphaeum'): k = 'nymphaeum'
        else: continue
        p = cen(s); a = best_aq(p, s['built']); u = by[a['id']]
        n = {'id': s['id'], 'kind': k, 'src': 'world', 'name': s['name'], 'built': s['built'], 'wet': max(s['built'], u['wet']), 'fed_by': a['id'],
             'xy': [round(p[0], 1), round(p[1], 1)], 'end': end(s)}
        nodes.append(n); by[n['id']] = n
    SRC = [n for n in nodes if n['kind'] in ('cistern', 'nymphaeum')]
    for q in QS:
        f = json.load(open(os.path.join(LIV, q, 'frame.json')))['frame']
        for h in json.load(open(os.path.join(LIV, q, 'houses_street.json')))['houses']:
            if h[9] != 'lm:fountain': continue
            P = h[4]; cx = sum(P[0::2]) / 4; cy = sum(P[1::2]) / 4; p = (f[0] + cx / S, f[1] + cy / S)
            d = lambda n: math.hypot(p[0] - n['xy'][0], p[1] - n['xy'][1])
            near = [n for n in SRC if d(n) <= REACH and n['wet'] <= h[2]]
            u = min(near or SRC, key=d)
            nodes.append({'id': f'{q}:h{h[0]}', 'kind': 'fountain', 'src': 'houses_street', 'q': q, 'h': h[0], 'built': h[2],
                          'wet': max(h[2], u['wet']), 'fed_by': u['id'], 'xy': [round(p[0], 1), round(p[1], 1)], 'end': h[3] if h[3] < 9000 else None})
    json.dump({'src': 'tools/cs/factory/net_water.py（设计：谭线 notes/epic-system.md；年份：world.json、houses_street.json）', 'reach': REACH, 'nodes': nodes},
              open(os.path.join(OUT, 'net_water.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    for n in nodes: print(n['kind'], n['id'], n['built'], '→出水', n['wet'], '←', n['fed_by'])
if __name__ == '__main__': main()
