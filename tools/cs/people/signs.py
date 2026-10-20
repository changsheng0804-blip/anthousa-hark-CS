"""街名、路牌、招牌（2026-10-20，CS线）。
街名不手写，从街上住的人推出来：
  1. 把底账里一段段的街按首尾相接串成整条街。
  2. 每栋房子按临街边归到最近那条街；folk_h.json 给出这户的行当和籍贯。
  3. 起名的先后：同一行当占四成以上 → 陶匠街、鞋匠巷；外地同乡占四成半以上 → 亚历山大里亚人街；
     挨着地标 → 粮仓街、泉宫街；巷子里有口喷泉 → 泉巷；陡 → 石阶巷；都不是 → 按房号哈希从圣徒名和俗名里挑。
     重名的加东西南北。
  4. 路牌：每条有名字的街两头各立一块（街口往里一点、靠一边），带年份，街修起来才有。
  5. 招牌：铺面和作坊人家门口挂一块，写行当的一两个字。
写 signs.json（scroll.html 读）。
  python3 tools/cs/people/signs.py nangang
——Hark（CS线）"""
import json, math, os, sys, collections, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
Q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
D = os.path.join(ROOT, 'docs/living/nodes', Q)
WD = json.load(open(os.path.join(D, 'nodes_net.json')))
FH = {r[0]: (r[1], r[2], r[3], r[4]) for r in json.load(open(os.path.join(D, 'folk_h.json')))}
E = WD['elev']; MPP = E['mpp']
F = WD['features']
by = collections.defaultdict(list)
for f in F: by[f['t']].append(f)
H = lambda *a: int(hashlib.md5('|'.join(map(str, a)).encode()).hexdigest()[:8], 16) / 0xffffffff

def elev(x, y):
    s = E['st']; gx = max(0, min(E['w'] - 1.001, x / s)); gy = max(0, min(E['h'] - 1.001, y / s)); i, j = int(gx), int(gy); fx, fy = gx - i, gy - j
    g = lambda a, b: E['dm'][b * E['w'] + a] / 10
    return ((g(i, j) * (1 - fx) + g(i + 1, j) * fx) * (1 - fy) + (g(i, j + 1) * (1 - fx) + g(i + 1, j + 1) * fx) * fy)  # 米

# ---------- 1. 串街 ----------
chains = []
for f in by['street']:
    g = f['g']
    c = chains[-1] if chains else None
    if c and c['k'] == f['k'] and abs(c['pts'][-1][0] - g[0]) < .05 and abs(c['pts'][-1][1] - g[1]) < .05:
        c['pts'].append((g[2], g[3])); c['y0'] = min(c['y0'], f['y0'])
    else:
        chains.append({'k': f['k'], 'w': f['w'], 'pts': [(g[0], g[1]), (g[2], g[3])], 'y0': f['y0']})
# 同一行的街在路口被切成两段、方向差不多的，接回一条（一条街一个名字）
def ang(u, v): return abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
def dvec(a, b): L = math.dist(a, b) or 1; return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
merged = True
while merged:
    merged = False; ends = collections.defaultdict(list)
    for i, c in enumerate(chains):
        if c is None: continue
        ends[(round(c['pts'][0][0]), round(c['pts'][0][1]))].append((i, 0)); ends[(round(c['pts'][-1][0]), round(c['pts'][-1][1]))].append((i, 1))
    for key, L_ in ends.items():
        best = None
        for x in range(len(L_)):
            for y in range(x + 1, len(L_)):
                (i, ei), (j, ej) = L_[x], L_[y]
                if i == j or chains[i] is None or chains[j] is None or chains[i]['k'] != chains[j]['k']: continue
                A = chains[i]['pts'] if ei == 1 else chains[i]['pts'][::-1]; B = chains[j]['pts'] if ej == 0 else chains[j]['pts'][::-1]
                a = ang(dvec(A[-2], A[-1]), dvec(B[0], B[1]))
                if a < .6 and (best is None or a < best[0]): best = (a, i, j, A, B)
        if best:
            _, i, j, A, B = best; chains[i]['pts'] = A + B[1:]; chains[i]['y0'] = min(chains[i]['y0'], chains[j]['y0']); chains[j] = None; merged = True; break
chains = [c for c in chains if c]
for c in chains:
    c['L'] = sum(math.dist(a, b) for a, b in zip(c['pts'], c['pts'][1:]))
G = 24; SG = collections.defaultdict(list)
for ci, c in enumerate(chains):
    for a, b in zip(c['pts'], c['pts'][1:]):
        for t in range(0, int(math.dist(a, b) / 8) + 2):
            u = min(1, t * 8 / max(.01, math.dist(a, b))); x = a[0] + (b[0] - a[0]) * u; y = a[1] + (b[1] - a[1]) * u
            SG[(int(x // G), int(y // G))].append((ci, a, b))
def near_chain(x, y, R=16):
    best = None
    for gx in range(int(x // G) - 1, int(x // G) + 2):
        for gy in range(int(y // G) - 1, int(y // G) + 2):
            for ci, a, b in SG.get((gx, gy), ()):
                dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy or 1; t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
                d = math.dist((x, y), (a[0] + dx * t, a[1] + dy * t))
                if d < R and (not best or d < best[0]): best = (d, ci)
    return best[1] if best else None

# ---------- 2. 房子归街 ----------
for c in chains: c['h'] = []
houses = [h for h in by['house'] if h['y1'] is None]
for h in houses:
    p = h['p']; pt = [(p[0], p[1]), (p[2], p[3]), (p[4], p[5]), (p[6], p[7])]; fr = h.get('fr', 0) or 0
    a, b = pt[fr], pt[(fr + 1) % 4]; m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    ci = near_chain(*m)
    if ci is not None: chains[ci]['h'].append(h)

# ---------- 3. 起名 ----------
TST = {'陶匠': '陶匠', '鞋匠': '鞋匠', '织工': '织工', '面包师': '面包房', '酒馆老板': '酒馆', '船匠': '船匠', '卖鱼的': '鱼市',
       '粮商': '粮行', '卖布的': '布行', '卖油的': '油坊', '香料商': '香料', '银钱商': '钱商', '丝绸商': '丝绸', '卖陶器的': '陶器', '运水人': '运水'}
from zoning import STREET as _ZS, SIGN as _ZG
TST.update(_ZS)   # zoning.py 里新添的行当也能起街名
LMN = {'granary': '粮仓', 'nymphaeum': '泉宫', 'forum': '广场', 'cistern': '水窖', 'xenon': '孤寡院', 'palace': '皇宫', 'hippodrome': '竞技场', 'church': '教堂', 'baths': '浴场', 'market': '市场', 'warehouse': '货栈'}
SAINT = ['圣伊琳娜', '圣莫基乌斯', '圣阿卡奇乌斯', '圣狄奥米德斯', '圣波利尤克托斯', '圣塞尔吉乌斯', '圣福卡斯', '圣米纳斯', '圣潘泰莱蒙',
         '圣科斯马斯', '圣尼古拉', '圣塞奥多尔', '圣普罗科匹乌斯', '圣阿纳斯塔西娅', '圣塞克拉', '圣乔治', '圣狄奥尼修斯', '圣斯特凡']
PLAIN = ['无花果', '老橄榄', '灯笼', '鸽子', '葡萄架', '白墙', '柏树', '蜜蜂', '驴', '盐', '红门', '铜铃', '石榴', '月桂', '三拱', '旧墙', '燕子',
         '黑石', '晒网', '酒糟', '芦苇', '麦秸', '牛角', '马厩', '风口', '油灯', '香桃木', '瓦片', '鱼骨', '纺锤', '陶片', '青苔',
         '羊皮', '铁环', '水罐', '扁豆', '洋葱', '野蔷薇', '石狮', '断柱', '双井', '鹳巢', '苦橙', '杏树', '麻绳', '桶匠', '老磨', '炭灰', '海螺',
         '牡蛎', '芝麻', '蓝门', '矮墙', '拱门', '石槽', '狗', '公鸡', '猫', '琥珀', '乳香', '木屐', '亚麻', '黄土', '松脂', '金雀花', '薄荷',
         '茴香', '橡树', '槐树', '醋', '蜡烛', '藤筐', '车辙', '回声', '晚钟', '小桥', '水沟', '石凳', '骆驼', '渔火', '帆布', '铃铛']
GRAND = ['柱廊', '凯旋', '奥古斯塔', '狄奥多西', '海门', '铜门', '君士坦丁', '瓦伦斯', '胜利', '和平', '皇后', '新墙', '格拉提安', '金门']
SUF = {'m': '大道', 'c': '大街', 's': '街', 'l': '巷'}
# 地标的专名：路按「通到哪儿」起名，街按「挨着哪儿」起名，专名比「教堂」「粮仓」这种通名不容易撞（10-20 街名清理）
LMS = {'horrea_theodosius': '狄奥多西粮仓', 'nymphaeum_maius': '大泉宫', 'horrea_alexandrina': '亚历山大粮仓', 'forum_theodosius': '狄奥多西广场',
       'cistern_slope': '坡下水窖', 'xenon_xerolophos': '干山孤寡院', 'church_apostles': '圣使徒', 'market_embers': '余烬市场', 'gate_old_thracian': '色雷斯旧门',
       'fort_acropolis': '卫城', 'agora_tetrastoon': '四柱廊', 'forum_founder': '斑岩柱', 'milion': '里程碑', 'palace_great': '皇宫', 'hippodrome': '竞技场',
       'church_peace': '圣伊琳娜', 'granary_founder': '老粮仓', 'cistern_founder': '奠基者水池', 'nymphaeum_great': '泉宫', 'warehouse_horn': '金角货栈',
       'tower_horn': '金角塔', 'church_megale': '大教堂', 'horrea_troadensia': '特罗阿德粮仓', 'church_anastasia': '阿纳斯塔西娅', 'baths_constantius': '浴场',
       'cistern_modestus': '莫德斯图斯水窖', 'cistern_carriers': '挑水人水窖', 'aqb_valley': '水渠', 'barracks_gate': '兵营门'}
lms = [(f, LMS.get(f.get('id'), LMN.get(f['k'], ''))) for f in by['landmark']]
def lm_c(f): g = f['g']; return (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))
fountains = [(f['x'], f['y']) for f in by['fountain']]
piers = [((f['g'][0][0] + f['g'][1][0]) / 2, (f['g'][0][1] + f['g'][1][1]) / 2) for f in by.get('pier', [])]
used = {}; BASE = {}
def mid(c):
    s = c['L'] / 2
    for a, b in zip(c['pts'], c['pts'][1:]):
        d = math.dist(a, b)
        if s <= d: u = s / max(d, .01); return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        s -= d
    return c['pts'][-1]
def mind(c, P):
    return min((min(math.dist(q, p) for q in c['pts'][::2] + [c['pts'][-1]]) for p in P), default=1e9)
def slope(c):
    a, b = c['pts'][0], c['pts'][-1]; return abs(elev(*a) - elev(*b)) / max(1, c['L'] * MPP)
def cands(ci, c):
    k = c['k']; suf = SUF[k]; out = []
    tr = collections.Counter(FH[h['id']][0] for h in c['h'] if h['id'] in FH)
    og = collections.Counter(FH[h['id']][1] for h in c['h'] if h['id'] in FH and FH[h['id']][1] != '本城生')
    n = sum(1 for h in c['h'] if h['id'] in FH)
    if k == 'm' and ci == max(range(len(chains)), key=lambda i: chains[i]['L'] if chains[i]['k'] == 'm' else 0): out.append('梅塞大道')
    if tr and n >= 3:
        t, m = tr.most_common(1)[0]
        m2 = tr.most_common(2)[1][1] if len(tr) > 1 else 0
        if m >= 3 and t in TST and (m / n >= .4 or (m / n >= .28 and m >= 1.7 * m2)): out.append(TST[t] + suf)
    if og and n >= 3:
        o, m = og.most_common(1)[0]
        if m / n >= .45 and m >= 3: out.append(o + '人' + suf)
    for f, nm in lms:
        if nm and mind(c, [lm_c(f)]) < 90: out.append(nm + suf)
    if k in ('m', 'c', 's'):   # 通到哪儿：哪一头 260 像素内有地标，就叫「去那儿的路」
        for f, nm in sorted(lms, key=lambda q: min(math.dist(lm_c(q[0]), c['pts'][0]), math.dist(lm_c(q[0]), c['pts'][-1]))):
            if nm and min(math.dist(lm_c(f), c['pts'][0]), math.dist(lm_c(f), c['pts'][-1])) < 260: out.append(nm + suf)
    if k in ('m', 'c') and piers and mind(c, piers) < 60: out.append('码头' + suf)
    if k in ('s', 'l') and mind(c, fountains) < 8: out.append('泉' + suf)
    if k == 'l':
        hs = sorted((FH[h['id']][3] for h in c['h'] if h['id'] in FH and FH[h['id']][2] and FH[h['id']][3] <= 30), key=lambda x: x)
        old = sorted(((FH[h['id']][3], FH[h['id']][2]) for h in c['h'] if h['id'] in FH and FH[h['id']][2]))
        for _, nm_ in old[:3]: out.append(nm_ + '家' + suf)   # 巷子按住得最久那户叫
    if tr and n >= 3:   # 放宽一档：街上最多的行当有三户以上，也拿来起名（排在专名后、俗名前）
        for t, m in tr.most_common(2):
            if m >= 3 and t in TST: out.append(TST[t] + suf)
    if og and n >= 4:
        o, m = og.most_common(1)[0]
        if m >= 3: out.append(o + '人' + suf)
    if slope(c) > .08: out.append('石阶' + suf if k == 'l' else '上坡' + suf)
    if k == 'm':
        for j in range(len(GRAND)): out.append(GRAND[(int(H('gm', ci) * len(GRAND)) + j) % len(GRAND)] + suf)
        return out
    if k in ('s', 'c'):
        for j in range(3): out.append(SAINT[(int(H('st', ci) * len(SAINT)) + j * 7) % len(SAINT)] + suf)
    if k == 'c':
        for j in range(3): out.append(GRAND[(int(H('gc', ci) * len(GRAND)) + j * 5) % len(GRAND)] + suf)
    for j in range(len(PLAIN)): out.append(PLAIN[(int(H('pl', ci) * len(PLAIN)) + j * 11) % len(PLAIN)] + suf)   # 整个俗名池都试一遍，免得落到「新X街」
    return out
DIR = lambda p, q: ('东' if q[0] > p[0] else '西') if abs(q[0] - p[0]) > abs(q[1] - p[1]) else ('南' if q[1] > p[1] else '北')
order = sorted(range(len(chains)), key=lambda i: ({'m': 0, 'c': 1, 's': 2, 'l': 3}[chains[i]['k']], -chains[i]['L']))
for ci in order:
    c = chains[ci]
    if c['L'] < 30: c['n'] = None; continue
    nm = None
    # 小街小巷的俗名隔得够远（不同街区）可以重名，真城里也一样；大道、大街全城不重
    far = lambda L: c['k'] in ('s', 'l') and all(math.dist(mid(chains[j]), mid(c)) > 1500 for j in L)
    for x in cands(ci, c):
        b = x[:-len(SUF[c['k']])]
        if (x not in used or far(used[x])) and (b not in BASE or far(BASE[b])): nm = x; break
    if nm is None:
        x = cands(ci, c)[-1]; d = DIR(mid(chains[used[x][0]]), mid(c)) if x in used else ''
        for y in ('后' + x, '新' + x, d + x, '二' + x):
            if y not in used: nm = y; break
    c['n'] = nm
    if nm: used.setdefault(nm, []).append(ci); BASE.setdefault(nm[:-len(SUF[c['k']])] if nm.endswith(SUF[c['k']]) else nm, []).append(ci)

# ---------- 4. 路牌 ----------
quads = []
for h in houses:
    p = h['p']; quads.append([(p[0], p[1]), (p[2], p[3]), (p[4], p[5]), (p[6], p[7])])
QG = collections.defaultdict(list)
for q in quads:
    xs = [a[0] for a in q]; ys = [a[1] for a in q]
    for gx in range(int(min(xs) // G), int(max(xs) // G) + 1):
        for gy in range(int(min(ys) // G), int(max(ys) // G) + 1): QG[(gx, gy)].append(q)
def inq(x, y, q, pad=.6):
    s = None
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]; cr = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if s is None: s = cr > 0
        elif (cr > 0) != s: return False
    return True
def blocked(x, y):
    return any(inq(x, y, q) for q in QG.get((int(x // G), int(y // G)), ()))
posts = []
def on_street(x, y, me):
    for ci2, a, b in SG.get((int(x // G), int(y // G)), ()):
        if ci2 == me: continue
        c2 = chains[ci2]; dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy or 1; t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        if math.dist((x, y), (a[0] + dx * t, a[1] + dy * t)) < c2['w'] / 2 + .4: return True
    return False
for ci, c in enumerate(chains):
    if not c['n']: continue
    for end in (0, 1):
        P = c['pts'] if end == 0 else c['pts'][::-1]
        a, b = P[0], P[1]; L = math.dist(a, b) or 1; ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        ok = False
        for s in (9, 12, 15, 6, 19):
            for side in ((1, -1) if H('sd', ci, end) < .5 else (-1, 1)):
                if s > c['L'] - 4: continue
                # 沿街走 s 像素，靠一边站在街沿上
                acc = 0; px, pz = a; qx, qz = ux, uz
                for p0, p1 in zip(P, P[1:]):
                    d = math.dist(p0, p1)
                    if acc + d >= s: u = (s - acc) / max(d, .01); px, pz = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u; qx, qz = (p1[0] - p0[0]) / max(d, .01), (p1[1] - p0[1]) / max(d, .01); break
                    acc += d
                off = c['w'] / 2 + .5
                x, z = px - qz * off * side, pz + qx * off * side
                if blocked(x, z) or on_street(x, z, ci) or any(math.dist((x, z), (o[1], o[2])) < 10 for o in posts): continue
                posts.append([c['n'], round(x, 2), round(z, 2), round(qx, 3), round(qz, 3), c['y0']]); ok = True; break
            if ok: break

# ---------- 5. 招牌 ----------
SL = {'面包师': '面包', '酒馆老板': '酒', '陶匠': '陶', '织工': '织', '鞋匠': '鞋', '粮商': '粮', '船匠': '船', '卖布的': '布', '卖油的': '油',
      '卖陶器的': '陶器', '卖鱼的': '鱼', '卖果子的': '果', '香料商': '香料', '银钱商': '钱', '丝绸商': '丝'}
SL.update(_ZG)
shops = {}
for h in houses:
    if h['id'] not in FH: continue
    t = FH[h['id']][0]
    if t not in SL: continue
    if h.get('fn') in ('shops', 'market') or h.get('ty') == 'row' or H('sh', h['id']) < .45: shops[h['id']] = SL[t]

out = {'streets': [[c['n'], c['k'], [[round(p[0], 1), round(p[1], 1)] for p in c['pts'][::max(1, len(c['pts']) // 12)] + [c['pts'][-1]]]] for c in chains if c['n']],
       'posts': posts, 'shops': shops, 'fields': 'posts: 街名 x z 沿街方向ux uz 修起来那年；shops: 房号 → 招牌字',
       'note': '街名从住户推出来（行当、同乡、地标、喷泉、坡），不手写。——Hark（CS线）'}
json.dump(out, open(os.path.join(D, 'signs.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
nm = [c['n'] for c in chains if c['n']]
print('街', len(chains), '有名字', len(nm), '路牌', len(posts), '招牌', len(shops), os.path.getsize(os.path.join(D, 'signs.json')), '字节')
print(collections.Counter(n[-1] for n in nm)); print(nm[:60])
print(collections.Counter(shops.values()))
