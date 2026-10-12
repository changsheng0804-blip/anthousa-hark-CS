#!/usr/bin/env python3
"""Street names for Xerolophos. Names come from what the ledger says is on/near the street:
story households (their trade or origin), landmarks, wells/ovens at its junctions, the fire (rebuilt grid = numbered new streets),
the town wall, and for the rest a pool chosen by the street's age (old winding lanes get folk names, planned streets trade/saint names).
Names change only when history changes the street (fire 48, carriers' cistern 54). Writes xerolophos/streetnames.json:
[{n, k, a:[[x,y,ang,year]..] label anchors, p:[[x,y]..] polyline, r:[[name,y0,y1]..] (names over time), y:first year}]"""
import json, math, hashlib
G = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/gen/'; X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
meta = json.load(open(G + '_streets_meta.json')); SI = meta['si']; ST = meta['streets']
SEG = json.load(open(X + 'streets.json')); HD = json.load(open(X + 'houses.json')); late = HD['late']
stories = json.load(open(X + 'stories.json')); JU = json.load(open(X + 'junctions.json')); city = json.load(open(X + 'city.json'))
LM = {l['id']: l for l in city['landmarks']}
H = {h[0]: h for h in HD['houses']}
def hh(*a): return int(hashlib.md5(repr(a).encode()).hexdigest()[:8], 16)
def wall_x(y): return 587 - 0.2357 * y
def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
def sd(px, py, s):
    ax, ay, bx, by = s[:4]; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
# segments per street
segs = {}
for i, s in enumerate(SEG[:len(SI)]):
    if SI[i] >= 0: segs.setdefault(SI[i], []).append(s)
info = {}
for si, L_ in segs.items():
    ln = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in L_)
    mx = sum((s[0] + s[2]) / 2 for s in L_) / len(L_); my = sum((s[1] + s[3]) / 2 for s in L_) / len(L_)
    ys = sorted(s[6] for s in L_)
    info[si] = dict(len=ln, mx=mx, my=my, y=ys[0], y20=ys[len(ys) // 5], k=ST[si]['k'])
def street_of(x, y, kinds=('street', 'cross', 'lane')):
    best = None
    for si, L_ in segs.items():
        if ST[si]['k'] not in kinds: continue
        for s in L_:
            d = sd(x, y, s)
            if best is None or d < best[0]: best = (d, si)
    return best
names = {}; renames = {}; used = set()
def give(si, n, force=False):
    if si in names and not force: return False
    base = n; k = 1
    while n in used:
        k += 1; n = (base[:-1] + '二三四五六七八九'[k - 2] + base[-1]) if base[-1] in '巷街' and k < 10 else base + str(k)
    names[si] = n; used.add(n); return True
# 1. main roads (order in city.json roads)
MAIN = {'r_mese': '梅塞大道', 'r_north3': '水渠大街', 'r_west_s': '下港坡路', 'r_mese_north': '北梅塞路'}
mains = [i for i, s in enumerate(ST) if s['k'] == 'main']
for i, r in zip(mains, city['roads']): give(i, MAIN.get(r['id'], '大路'))
# 2. story households name their street
STORY = {'12231': '运水人巷', '13068': '织工巷', '13654': '铜匠街', '13821': '面包炉巷', '16975': '石匠巷', '14251': '哥特人巷',
         '12482': '卡帕多西亚巷', '12250': '台阶巷', '13196': '菜园巷', '17084': '埃及人巷'}
for hid, n in STORY.items():
    h = H.get(int(hid))
    if not h: continue
    p = h[4]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4
    b = street_of(cx, cy)
    if b and b[0] < 40 and info.get(b[1], {}).get('len', 0) > 40: give(b[1], n)
# 3. landmarks
LMN = {'cistern_modestus': '水池街', 'baths_constantius': '浴场后街', 'aqb_valley': '渠桥巷', 'barracks_gate': '兵营街', 'gate_founder': '城门里街'}
for k, n in LMN.items():
    if k not in LM: continue
    x, y = LM[k]['xy']
    c = sorted((math.hypot(v['mx'] - x, v['my'] - y), si) for si, v in info.items() if v['k'] != 'main' and v['len'] > 60 and si not in names)
    if c and c[0][0] < 220: give(c[0][1], n)
# 4. the street along the wall
c = sorted((abs(v['mx'] - wall_x(v['my'])), si) for si, v in info.items() if v['k'] in ('street', 'lane') and v['len'] > 200 and si not in names)
if c and c[0][0] < 90: give(c[0][1], '城墙根街')
# 5. rebuilt fire grid: numbered new streets, west to east
fp = late['fire_ruins']['p']
fire = sorted((v['mx'], si) for si, v in info.items() if v['k'] != 'main' and pip(v['mx'], v['my'], fp) and v['len'] > 110)
nums = '一二三四五六七八九十'
cn = lambda k: nums[k - 1] if k <= 10 else '十' + nums[k - 11]
FIRE = {si: '新' + cn(j + 1) + '街' for j, (_, si) in enumerate(fire)}
used.update(FIRE.values())
# 6. wells and ovens at junctions
for x, y, yr, kind in JU:
    b = street_of(x, y)
    if not b or b[0] > 12 or b[1] in names or info[b[1]]['len'] < 60: continue
    o = info[b[1]]['y20'] < 36
    opts = {'well': ['老井巷', '双井巷'] if o else ['井台巷', '新井巷'], 'oven': ['炉子巷', '烤炉巷'], 'stall': ['摊子巷', '集市巷']}[kind]
    opts = [n for n in opts if n not in used]
    if opts: give(b[1], opts[0])
# 7. the rest: old winding streets get folk names, planned ones trades / saints / origins
OLD = ['羊肠巷', '驴子巷', '无花果巷', '老橄榄巷', '鹅卵石巷', '瞎子巷', '黑狗巷', '寡妇巷', '弯弯巷', '石榴巷', '山羊坡', '刺山柑巷', '酸酒巷', '跛子巷', '乌鸦巷', '牧羊人巷', '风口巷', '野蜂巷', '三棵松巷', '破瓮巷']
NEW = ['陶匠街', '鞋匠街', '皮匠巷', '绳匠巷', '木匠街', '染坊街', '灯油巷', '蜡烛巷', '羊毛街', '酒馆巷', '马夫巷', '抄写员巷', '圣莫基乌斯街', '圣阿卡基奥斯巷', '圣狄俄墨得斯巷',
       '比提尼亚人巷', '色雷斯人街', '叙利亚人巷', '亚美尼亚人巷', '腌鱼巷', '香料巷', '铁匠巷', '箍桶匠巷', '磨坊巷', '亚麻巷', '石灰巷', '瓦匠街', '银匠巷', '旧衣巷', '大麦街']
for si in sorted(info, key=lambda s: -info[s]['len']):
    v = info[si]
    if si in names or v['k'] == 'main': continue
    need = {'street': 120, 'cross': 90, 'lane': 110}[v['k']]
    if v['len'] < need: continue
    pool = OLD if v['y20'] < 36 else NEW
    free_ = [n for n in pool if n not in used]
    if not free_: free_ = pool
    give(si, free_[hh(si) % len(free_)])
# carriers' cistern (54): the named street nearest it is renamed for the carriers
cx, cy = LM['cistern_carriers']['xy']
c = sorted((min(sd(cx, cy, s) for s in segs[si]), si) for si in names if ST[si]['k'] != 'main')
if c and c[0][0] < 80: renames[c[0][1]] = ('运水人池街', 54)
# anchors and output
out = []
for si in FIRE:
    if si not in names: names[si] = None
for si, n in names.items():
    L_ = sorted(segs[si], key=lambda s: SEG.index(s) if False else 0)
    k = ST[si]['k']; step = {'main': 420, 'street': 300, 'cross': 220, 'lane': 200}[k]
    anchors = []; acc = step * 0.45
    for s in segs[si]:
        L = math.hypot(s[2] - s[0], s[3] - s[1]); acc += L
        if acc >= step and L > 6:
            acc = 0; ang = math.atan2(s[3] - s[1], s[2] - s[0])
            if ang > math.pi / 2: ang -= math.pi
            if ang < -math.pi / 2: ang += math.pi
            mx, my = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
            if 20 < mx < 1800 and 20 < my < 2030: anchors.append([round(mx, 1), round(my, 1), round(ang, 3), s[6]])
    if not anchors:
        s = segs[si][len(segs[si]) // 2]; ang = math.atan2(s[3] - s[1], s[2] - s[0])
        if ang > math.pi / 2: ang -= math.pi
        if ang < -math.pi / 2: ang += math.pi
        anchors = [[round((s[0] + s[2]) / 2, 1), round((s[1] + s[3]) / 2, 1), round(ang, 3), s[6]]]
    poly = [[round(s[0]), round(s[1])] for s in segs[si][::2]] + [[round(segs[si][-1][2]), round(segs[si][-1][3])]]
    r = [[n, info[si]['y'], 999]]
    if si in renames:
        nn, yr = renames[si]
        if nn == '焦':
            burnt = sum(1 for v in used if v.startswith('焦'))
            if burnt >= 4: nn = None
            else: nn = ['焦巷', '焦二巷', '焦三巷', '焦四巷'][burnt]; used.add(nn)
        if nn: r = [[n, info[si]['y'], yr], [nn, yr, 999]] if yr > info[si]['y'] else [[nn, yr, 999]]
    if si in FIRE:
        nf = FIRE[si]
        r = [[n, info[si]['y'], 48], [nf, 48, 999]] if (n and info[si]['y'] < 48) else [[nf, max(48, info[si]['y']), 999]]
        n = n or nf
    out.append(dict(n=n, k=k[0], a=anchors, p=poly, r=r, y=info[si]['y'], ys=[[s[6]] for s in []]))
for o in out: o.pop('ys')
json.dump(out, open(X + 'streetnames.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(out), 'named;', sum(1 for o in out if len(o['r']) > 1), 'renamed over time')
for o in sorted(out, key=lambda o: o['y'])[:8]: print(o['n'], o['k'], o['y'], o['r'])
print([o['r'] for o in out if len(o['r']) > 1][:12])
