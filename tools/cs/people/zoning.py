"""行当落位（主人 10-20：「规划其实是有规律的」）。
每户房子先算几项「地段」：离码头、粮仓、广场、主街、皇宫、竞技场、教堂、水有多远，在不在下风、在不在城边、地势高低、门面是不是铺面。
每个行当按自己的规律给每户打分（臭的、烧火的往下风和城边去，要水的靠水，细货贴着广场和皇宫，码头的人住码头……），
再加一层低频噪声（每个行当一张，格子 220 像素），同行就会扎堆成片、成街，而不是均匀撒开。
最后按配额分：把（户, 行当）按分数从高到低排，一户只拿一个、一个行当拿满为止；剩下的户是打零工的，自然落在最差的地段。
风向：君士坦丁堡常年刮东北风（poyraz），下风是西南。"""
import math, random
import numpy as np

# 行当: (配额占户数, 打分权重{特征: 权重}, 招牌字, 街名)
# 特征都归一到 0..1，越大越「近 / 越是」
T = {
 # 街坊日用：哪儿都要，铺面和主街加分，跟同行互相排斥（见 SPREAD）
 '面包师':   (.045, {'shop': 1.0, 'main': .5}, '面包', '面包房'),
 '酒馆老板': (.03,  {'shop': .8, 'main': .6, 'dock': .4, 'hipp': .3}, '酒', '酒馆'),
 '卖油的':   (.015, {'shop': 1.0, 'market': .8}, '油', '油坊'),
 '卖果子的': (.015, {'shop': .8, 'market': 1.0, 'edge': .3}, '果', '果子'),
 # 家里干的手艺：哪儿都有，不挑地段，靠噪声扎堆
 '织工':     (.12,  {'low': .3}, '织', '织工'),
 '裁缝':     (.04,  {'shop': .3, 'main': .2}, '衣', '裁缝'),
 '小贩':     (.04,  {'market': .8, 'main': .5, 'rich': -.3}, '', ''),
 '鞋匠':     (.05,  {'shop': .4, 'main': .3}, '鞋', '鞋匠'),
 '木匠':     (.04,  {'edge': .3, 'main': .2}, '木', '木匠'),
 # 烧火的、臭的：下风、城边，要水的再靠水
 '陶匠':     (.03,  {'down': 1.2, 'edge': 1.0, 'low': .5, 'water': .3, 'rich': -1.0}, '陶', '陶匠'),
 '铁匠':     (.02,  {'down': .9, 'edge': .6, 'main': .4, 'rich': -.8}, '铁', '铁匠'),
 '皮匠':     (.015, {'down': 1.6, 'edge': 1.4, 'water': 1.0, 'low': .6, 'rich': -1.5}, '皮', '皮匠'),
 '染匠':     (.015, {'water': 1.4, 'down': 1.0, 'low': .5, 'rich': -1.0}, '染', '染坊'),
 '石匠':     (.015, {'edge': .8, 'lm': .6}, '石', '石匠'),
 # 铜匠扎在大教堂边上（君士坦丁堡的铜匠街就在圣索菲亚背后）
 '铜匠':     (.015, {'church': 1.2, 'market': .5, 'shop': .3}, '铜', '铜匠'),
 # 码头
 '水手':     (.03,  {'dock': 2.0, 'low': .3}, '', ''),
 '搬运工':   (.045, {'dock': 1.6, 'horrea': .8, 'rich': -.8}, '', ''),
 '船匠':     (.015, {'dock': 2.0, 'edge': .4}, '船', '船匠'),
 '绳匠':     (.01,  {'dock': 1.4, 'edge': .6}, '绳', '绳匠'),
 '卖鱼的':   (.015, {'dock': 1.4, 'market': .6, 'shop': .3}, '鱼', '鱼市'),
 '粮商':     (.012, {'horrea': 1.6, 'dock': .6, 'shop': .3}, '粮', '粮行'),
 # 细货：贴着广场、主街、皇宫，地势高的好地段
 '银钱商':   (.01,  {'forum': 1.6, 'main': .8, 'rich': 1.0, 'shop': .5}, '钱', '钱商'),
 '丝绸商':   (.01,  {'forum': 1.4, 'palace': .8, 'rich': 1.0, 'shop': .5}, '丝', '丝绸'),
 '香料商':   (.01,  {'forum': 1.2, 'market': .6, 'main': .6, 'shop': .5}, '香料', '香料'),
 '金匠':     (.008, {'forum': 1.2, 'palace': 1.0, 'rich': 1.0, 'shop': .4}, '金', '金匠'),
 '抄写员':   (.006, {'forum': .8, 'palace': .8, 'church': .5}, '', ''),
 # 大地标养着的人
 '宫廷侍卫': (.01,  {'palace': 2.4}, '', ''),
 '宦官仆役': (.008, {'palace': 2.4, 'rich': .4}, '', ''),
 '马夫':     (.01,  {'hipp': 2.0, 'edge': .3}, '', ''),
 '战车匠':   (.005, {'hipp': 2.0}, '车', '车匠'),
 '执事':     (.007, {'church': 2.0}, '', ''),
 '圣像画匠': (.005, {'church': 1.6, 'forum': .4}, '画', '画匠'),
 # 水边
 '运水人':   (.02,  {'fount': 1.2, 'high': .8, 'rich': -.5}, '', ''),
 # 城边种地的
 '菜农':     (.03,  {'edge': 2.0, 'down': .2, 'rich': -.5}, '', ''),
}
REST = '打零工的'   # 没分到的户
SPREAD = {'面包师': 70, '酒馆老板': 60, '卖油的': 90, '卖果子的': 80}   # 街坊铺子：这么多像素里不开第二家
NOISE = 1.0      # 扎堆的强度
WIND = (-1 / math.sqrt(2), 1 / math.sqrt(2))   # 下风方向（页面坐标 y 朝下）：西南


def _near(pts, P, scale):
    """每户到一组点的距离 → exp(-d/scale)，0..1"""
    if not pts: return np.zeros(len(P))
    Q = np.array(pts, float); out = np.full(len(P), 1e9)
    for i in range(0, len(Q), 400):
        d = np.sqrt(((P[:, None, :] - Q[None, i:i + 400, :]) ** 2).sum(-1)).min(1); out = np.minimum(out, d)
    return np.exp(-out / scale)


def _rank(v):
    r = np.argsort(np.argsort(v)); return r / max(1, len(v) - 1)


def _noise(seed, P, cell=220):
    """每个行当一张低频值噪声：同一片的户分数一起高、一起低 → 扎堆"""
    rnd = random.Random(seed); cache = {}
    def g(i, j):
        k = (i, j)
        if k not in cache: cache[k] = rnd.random() if False else random.Random(f'{seed}:{i}:{j}').random()
        return cache[k]
    out = np.empty(len(P))
    for n, (x, y) in enumerate(P):
        gx, gy = x / cell, y / cell; i, j = int(gx), int(gy); fx, fy = gx - i, gy - j
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        out[n] = (g(i, j) * (1 - fx) + g(i + 1, j) * fx) * (1 - fy) + (g(i, j + 1) * (1 - fx) + g(i + 1, j + 1) * fx) * fy
    return out


def zone(POOL, D, Y, piers, fount, elev, q):
    F = D['features']; live = lambda f: f.get('y0', 0) <= Y and (f.get('y1') is None or f['y1'] > Y)
    P = np.array([h['_door'][0] for h in POOL], float); N = len(P)
    lmk = [f for f in F if f['t'] == 'landmark' and live(f)]
    cen = lambda f: (sum(p[0] for p in f['g']) / len(f['g']), sum(p[1] for p in f['g']) / len(f['g']))
    edge_pts = lambda kinds: [tuple(p) for f in lmk if f['k'] in kinds for p in f['g']] + [cen(f) for f in lmk if f['k'] in kinds]
    houses = [f for f in F if f['t'] == 'house' and live(f)]
    hc = np.array([(sum(f['p'][::2]) / (len(f['p']) / 2), sum(f['p'][1::2]) / (len(f['p']) / 2)) for f in houses])
    mains = [p for f in F if f['t'] == 'street' and f.get('k') == 'm' and live(f) for p in zip(f['g'][::2], f['g'][1::2])]
    water = []
    for f in F:
        if f['t'] in ('cistern',) and live(f): water += [tuple(p) for p in f['g']]
    # 海岸：高程格里 ≤0 的格子挨着 >0 的格子
    E = D['elev']; w, hh, st = E['w'], E['h'], E['st']; dm = E['dm']
    for j in range(1, hh - 1, 2):
        for i in range(1, w - 1, 2):
            if dm[j * w + i] <= 0 and (dm[j * w + i + 1] > 0 or dm[(j + 1) * w + i] > 0 or dm[j * w + i - 1] > 0 or dm[(j - 1) * w + i] > 0): water.append((i * st, j * st))
    # 城边：方圆 150 像素里的房子少 = 城边
    dens = np.zeros(N)
    for i in range(0, N, 300):
        d2 = ((P[i:i + 300, None, :] - hc[None, :, :]) ** 2).sum(-1); dens[i:i + 300] = (d2 < 150 ** 2).sum(1)
    el = np.array([elev(x, y) for x, y in P])
    c0 = P.mean(0); down = (P - c0) @ np.array(WIND)
    fe = {
        'dock': _near(piers, P, 70), 'horrea': _near(edge_pts(('granary', 'warehouse')) + [tuple(h['_door'][0]) for h in POOL if h.get('fn') == 'horrea'], P, 90),
        'forum': _near(edge_pts(('forum', 'agora')), P, 130), 'market': _near(edge_pts(('market',)) + [tuple(h['_door'][0]) for h in POOL if h.get('fn') == 'market'], P, 80),
        'main': _near(mains, P, 25), 'palace': _near(edge_pts(('palace',)), P, 90), 'hipp': _near(edge_pts(('hippodrome',)), P, 90),
        'church': _near(edge_pts(('church',)), P, 90), 'lm': _near([cen(f) for f in lmk if f.get('y0', 0) > Y - 8], P, 150),
        'water': _near(water, P, 60), 'fount': _near(fount, P, 40),
        'edge': 1 - _rank(dens), 'down': _rank(down), 'high': _rank(el), 'low': 1 - _rank(el),
        'shop': np.array([1.0 if h.get('fn') in ('shops', 'market') or h.get('ty') == 'row' else 0.0 for h in POOL]),
    }
    fe['rich'] = np.clip(.45 * fe['forum'] + .45 * fe['palace'] + .25 * fe['main'] + .3 * fe['high'] - .4 * fe['down'] * fe['edge'], 0, 1)
    # 靠某个地标吃饭的行当：这一节点没有那个地标（或离得都远），配额按挨得上的户的比例缩，没有就是 0（南港没有皇宫就没有宫廷侍卫）
    ANCH = {'dock', 'horrea', 'forum', 'palace', 'hipp', 'church'}
    names = list(T); S = np.zeros((len(names), N)); QT = {}
    for t in names:
        a = [f for f in T[t][1] if f in ANCH and T[t][1][f] >= 1.2]
        QT[t] = T[t][0] * (min(1.0, min(float((fe[f] > .15).mean()) / .02 for f in a)) if a else 1.0)
    for k, t in enumerate(names):
        quota, wts = T[t][0], T[t][1]
        s = sum(v * fe[f] for f, v in wts.items()) if wts else np.zeros(N)
        S[k] = s + NOISE * _noise(f'{q}-{t}', P) + 0.15 * np.array([random.Random(f'{q}{t}{h["id"]}').random() for h in POOL])
    # 配额分配：分数从高到低（行当之间用分数排名比，避免某一行当权重大就全吃掉）
    R = np.vstack([_rank(S[k]) for k in range(len(names))])
    left = {t: int(round(QT[t] * N)) for t in names}; out = {}
    order = np.argsort(-R, axis=None)
    taken = {t: [] for t in SPREAD}
    for flat in order:
        k, i = divmod(int(flat), N); t = names[k]
        if left[t] <= 0 or POOL[i]['id'] in out: continue
        if t in SPREAD and any(math.dist(P[i], q2) < SPREAD[t] for q2 in taken[t]): continue
        out[POOL[i]['id']] = t; left[t] -= 1
        if t in SPREAD: taken[t].append(tuple(P[i]))
        if len(out) >= N: break
    for h in POOL: out.setdefault(h['id'], REST)
    return out, fe


SIGN = {t: v[2] for t, v in T.items() if v[2]}
STREET = {t: v[3] for t, v in T.items() if v[3]}
