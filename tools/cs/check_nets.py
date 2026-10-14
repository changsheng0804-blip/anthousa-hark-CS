#!/usr/bin/env python3
"""/goal 4 G1/G2 检查：公共设施网（谭线 notes/epic-system.md 的「网络」类）。
水网 tiles/net_water.json：水渠 → 蓄水池/宁芙泉 → 街角喷泉。
 ① 每个蓄水池、宁芙泉、喷泉都有 fed_by，且指向网里存在的上游节点；
 ② 底账节点（world.json 结构）的建成年一字不差读 world.json，不自编；喷泉的建成年 = 它所在房的开工年（houses_street.json）；
 ③ 出水年 wet = max(自己建成, 上游出水)，上游出水 ≤ 下游出水（上游没建，下游不出水）；
 ④ 网里的喷泉 = 全城 houses_street 里 lm:fountain 的房，一一对应；喷泉 ≥ 1。
 ⑤ 脉不露面：网不带画线用的几何（节点只有点），页面不画网线。
 ⑥ 干湿效果（项 2）：烤进瓦片的矢量里，每口出水年 wet 晚于落成（开工+2）的喷泉，水色的池面和水柱只从 wet 年起出现，
    wet 之前画干池（池底色）；出水年读网、不另写。每个 wet 之前的年份，画面里一滴水也没有。
——Hark（CS线）"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles')
W = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'world.json')))['structures']}
bad = []
def need(c, m):
    if not c: bad.append(m)
p = os.path.join(OUT, 'net_water.json')
if not os.path.exists(p): print('❌ 没有 tiles/net_water.json'); sys.exit(1)
N = json.load(open(p)); nodes = {n['id']: n for n in N['nodes']}
M = json.load(open(os.path.join(OUT, 'meta.json'))); QS = M['owner_order']
for n in N['nodes']:
    k = n['kind']
    if n.get('src') == 'world':
        s = W.get(n['id']); need(s is not None, f"{n['id']} 不在 world.json")
        if s: need(n['built'] == s['built'], f"{n['id']} 建成年 {n['built']} ≠ world.json {s['built']}")
    if k in ('cistern', 'nymphaeum', 'fountain', 'bridge'):
        need(n.get('fed_by') in nodes, f"{n['id']} 没有上游 fed_by")
    if n.get('fed_by') in nodes:
        u = nodes[n['fed_by']]
        need(u['wet'] <= n['wet'], f"{n['id']} 出水 {n['wet']} 早于上游 {u['id']} {u['wet']}")
        need(n['wet'] == max(n['built'], u['wet']), f"{n['id']} 出水年 {n['wet']} ≠ max(建成 {n['built']}, 上游 {u['wet']})")
    need(set(n) <= {'id', 'kind', 'src', 'name', 'built', 'wet', 'fed_by', 'q', 'h', 'xy', 'end', 'zh', 'px'}, f"{n['id']} 带了多余字段 {set(n)}")
    need(not isinstance(n.get('xy'), list) or len(n['xy']) == 2, f"{n['id']} 带了几何线")
F = {}
for q in QS:
    for h in json.load(open(os.path.join(LIV, q, 'houses_street.json')))['houses']:
        if h[9] == 'lm:fountain': F[(q, h[0])] = h[2]
NF = {(n['q'], n['h']): n for n in N['nodes'] if n['kind'] == 'fountain'}
need(len(F) >= 1, '全城没有喷泉')
need(set(F) == set(NF), f'喷泉对不上：页面有 {len(F)}，网里 {len(NF)}')
for k, b in F.items():
    if k in NF: need(NF[k]['built'] == b, f'喷泉 {k} 建成年 {NF[k]["built"]} ≠ 房开工 {b}')
# ⑥ 干湿：瓦片 vec 里按底账 id 找这栋喷泉的部件
WATER = {'6096b0', '96c4d6'}; DRY = '8a8272'; vecs = {}
for f in glob.glob(os.path.join(OUT, 'vec', '*.json')):
    for h in json.load(open(f))['h']:
        if isinstance(h[5], str) and h[5].startswith('h'): vecs.setdefault(h[5], []).append(h)
ndry = 0
for n in N['nodes']:
    if n['kind'] != 'fountain': continue
    hs = vecs.get('h%d' % n['h']); need(bool(hs), f"{n['id']} 瓦片里找不到这栋喷泉")
    if not hs: continue
    hs = [x for x in hs if any(p[2] in WATER or p[2] == DRY for p in x[4])]; need(len(hs) == 1, f"{n['id']} 瓦片里的喷泉记录 {len(hs)} 条")
    if not hs: continue
    h = hs[0]; start = n['built'] + 2
    if n['wet'] > start:
        ndry += 1
        wet = [p for p in h[4] if p[2] in WATER]; dry = [p for p in h[4] if p[2] == DRY]
        need(bool(wet) and all(p[3] >= n['wet'] for p in wet), f"{n['id']} 出水年 {n['wet']} 以前画着水（水色部件最早 {min([p[3] for p in wet] or [None])}）")
        need(bool(dry) and all(p[3] <= start and p[4] == n['wet'] for p in dry), f"{n['id']} 没有干池段 [{start},{n['wet']})")
print('干湿 ⑥：有干着年头的喷泉', ndry)
html = open(os.path.join(OUT, 'index.html')).read()
need('net_water' not in html or 'NETLINE' not in html, '页面画了水网线')

# ───── G2 粮网（项 3）：港口 → 粮仓 → 面包台阶（tiles/net_water.json 的 grain 段）
# ⑦ 粮网：港口/粮仓是 world.json 结构、建成年一字不差；台阶 = 全城 houses_street 里 lm:bread_steps 的房，一一对应（≥1）；
#    粮仓 fed_by 港口、台阶 fed_by 粮仓；供粮年 supply = max(自己建成(台阶落成=开工+2), 上游 supply)，上游 ≤ 下游；节点不带线几何
# ⑧ 效果：台阶上摆的面包（谭线 steps 卡的 5 个面包块）只从供粮年起画；页面只在 供粮年 ≤ 当年 < 台阶存续止 且清晨才画排队（breadQueue），
#    供粮年晚于落成的台阶，粮仓没建成之前光秃秃、不排队
G = (N.get('grain') or {}).get('nodes')
need(G is not None and len(G) > 0, '粮网：net_water.json 没有 grain 段')
G = G or []; gn = {n['id']: n for n in G}
GOK = {'id', 'kind', 'src', 'name', 'zh', 'built', 'supply', 'fed_by', 'q', 'h', 'xy', 'end', 'px', 'fx', 'fy'}
for n in G:
    k = n['kind']; need(k in ('harbor', 'granary', 'steps'), f"粮网 {n['id']} 种类 {k} 不认识")
    need(set(n) <= GOK, f"粮网 {n['id']} 带了多余字段 {set(n) - GOK}")
    if n.get('src') == 'world':
        s_ = W.get(n['id']); need(s_ is not None, f"粮网 {n['id']} 不在 world.json")
        if s_: need(n['built'] == s_['built'], f"粮网 {n['id']} 建成年 {n['built']} ≠ world.json {s_['built']}")
    if k == 'harbor': need(n['supply'] == n['built'] and not n.get('fed_by'), f"港口 {n['id']} 供粮年不对")
    if k in ('granary', 'steps'):
        u = gn.get(n.get('fed_by')); need(u is not None, f"粮网 {n['id']} 没有上游 fed_by")
        need(u is None or u['kind'] == ({'granary': 'harbor', 'steps': 'granary'}[k]), f"粮网 {n['id']} 上游种类不对")
        if u:
            need(u['supply'] <= n['supply'], f"粮网 {n['id']} 供粮 {n['supply']} 早于上游 {u['id']} {u['supply']}")
            own = n['built'] + (2 if k == 'steps' else 0)
            need(n['supply'] == max(own, u['supply']), f"粮网 {n['id']} 供粮年 {n['supply']} ≠ max(落成 {own}, 上游 {u['supply']})")
    need(not isinstance(n.get('xy'), list) or len(n['xy']) == 2, f"粮网 {n['id']} 带了几何线")
BS = {}
for q in QS:
    for h in json.load(open(os.path.join(LIV, q, 'houses_street.json')))['houses']:
        if h[9] == 'lm:bread_steps': BS[(q, h[0])] = h[2]
GS = {(n['q'], n['h']): n for n in G if n['kind'] == 'steps'}
need(len(BS) >= 1, '全城没有面包台阶')
need(set(BS) == set(GS), f'台阶对不上：页面有 {len(BS)}，粮网里 {len(GS)}')
for k, b in BS.items():
    if k in GS: need(GS[k]['built'] == b, f'台阶 {k} 建成年 {GS[k]["built"]} ≠ 房开工 {b}')
LOAF = '%02x%02x%02x' % (176, 122, 64); nbare = 0
for n in G:
    if n['kind'] != 'steps': continue
    hs = [x for x in vecs.get('h%d' % n['h'], []) if any(p[2] == LOAF for p in x[4])]
    need(len(hs) == 1, f"{n['id']} 瓦片里的台阶记录 {len(hs)} 条")
    if not hs: continue
    loaves = [p for p in hs[0][4] if p[2] == LOAF]
    need(bool(loaves) and all(p[3] >= n['supply'] for p in loaves), f"{n['id']} 供粮年 {n['supply']} 以前台阶上摆着面包")
    if n['supply'] > n['built'] + 2: nbare += 1
print('粮网 ⑦⑧：台阶', len(GS), '座，其中供粮晚于落成（先光秃）', nbare)
need('breadQueue' in html, '页面没有清晨排队效果（breadQueue）')
need('NETGLINE' not in html, '页面画了粮网线')
kinds = {}
for n in N['nodes']: kinds[n['kind']] = kinds.get(n['kind'], 0) + 1
print('水网', kinds, '干着的喷泉年数', sum(n['wet'] - n['built'] for n in N['nodes'] if n['kind'] == 'fountain'))
print('\n'.join('❌ ' + b for b in bad) or '✅ 全过'); sys.exit(1 if bad else 0)
