"""规则预演 v0 · 13 条「这座城自己的制度」。
每条规则是一个小函数：rule(hh, Y, ctx) -> [(a, b, 类型, 备注)]，a/b 是户键（"房号:搬入年"）或机构（"@名字"）。
弱关系现算不存：每年从户的状态（页面家谱推演）+ 空间事实 + 账本大事重新算出，不写进任何数据文件。
分组类规则（房东分配、债、征工）要先看全年的人家才能决定，由 ctx 在本年第一次被问到时算好、缓存在 ctx 里（只活一年）。
参数全在 rules.json。
"""
import math, collections
from data import street_at, home, fam_at, LEDGER_EVENTS

# ------------------------------------------------------------------ 户的状态（每年现算）

OWNER_BEFORE = 41  # run.py 用 rules.json bread.owner_before 覆盖


def household_state(h, Y):
    if not (h['built'] <= Y < h['destroyed']): return None
    f, fi = fam_at(h, Y)
    if f is None: return None
    mem = [p for p in f['people'] if home(p, Y)]
    if not mem: return None
    st, num = street_at(h, Y)
    age = lambda p: Y - p['b']
    men = [p for p in mem if p['s'] == 'm' and age(p) >= 16]
    kids = [p for p in mem if age(p) < 12]
    deaths = [p for p in f['people'] if p['d'] == Y and home(p, Y - 1)]
    soldier = [(y, t) for y, t in h['ev'] if '当了兵' in t and f['B'] <= y <= Y]
    head = max(men, key=age) if men else max(mem, key=age)
    return dict(key=f"{h['id']}:{f['B']}", hid=h['id'], h=h, fi=fi, x=h['x'], y=h['y'], lx=h['lx'], ly=h['ly'],
                street=st, num=num, fn=h['fn'], trade=f['trade'], faith=f['faith'], origin=f['origin'], B=f['B'],
                tenure=Y - f['B'], owner=(fi == 0 and f['B'] <= OWNER_BEFORE), mem=mem, men=len(men), kids=len(kids), needy=(len(men) == 0 and len(kids) > 0),
                deaths=deaths, boys=[p for p in mem if p['s'] == 'm'], size=len(mem), refugee=(48 <= f['B'] <= 50),
                soldier=soldier, head=head['n'], head_age=age(head))


def D(a, b): return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


class Grid:
    def __init__(self, items, cell=120):
        self.c = cell; self.g = collections.defaultdict(list)
        for it in items: self.g[(int(it['x'] // cell), int(it['y'] // cell))].append(it)

    def near(self, x, y, r):
        c = self.c; out = []
        for i in range(int((x - r) // c), int((x + r) // c) + 1):
            for j in range(int((y - r) // c), int((y + r) // c) + 1):
                for it in self.g.get((i, j), ()):
                    if math.hypot(it['x'] - x, it['y'] - y) <= r: out.append(it)
        return out


class Ctx:
    """一年的上下文：本年所有在住户 + 规则参数 + 全局底账。缓存只活一年。"""
    def __init__(self, states, Y, P, G):
        self.S = states; self.Y = Y; self.P = P; self.G = G
        self.by_key = {s['key']: s for s in states}
        self.grid = Grid(states)
        self._c = {}

    def once(self, name, fn):
        if name not in self._c: self._c[name] = fn()
        return self._c[name]

    def knn_in_group(self, group_of, k, mode):
        """分组规则的公共部分：同组内连边。mode=clique 全连接，knn 每户只连组内最近 k 户。"""
        def build():
            groups = collections.defaultdict(list)
            for s in self.S:
                g = group_of(s)
                if g is not None: groups[g].append(s)
            nb = collections.defaultdict(list)
            for g, mem in groups.items():
                for s in mem:
                    others = [o for o in mem if o is not s]
                    if mode == 'knn':
                        others = sorted(others, key=lambda o: D(s, o))[:k]
                    nb[s['key']] = [(o, g) for o in others]
            return nb
        return build


# ------------------------------------------------------------------ 基础五条

def water_source(s, ctx):
    """这户这年喝哪一口水：可用的最近井（井有效半径内），否则最近蓄水池（半径内），否则没有。"""
    P = ctx.P['water']
    def build():
        out = {}
        srcs = [w for w in ctx.G['water'] if w['built'] <= ctx.Y]
        wells = [w for w in srcs if w['kind'] == 'well']; cis = [w for w in srcs if w['kind'] == 'cistern']
        wg = Grid([dict(w, x=w['xy'][0], y=w['xy'][1]) for w in wells], 140)
        for t in ctx.S:
            best = None
            for w in wg.near(t['x'], t['y'], P['well_reach']):
                d = math.hypot(w['x'] - t['x'], w['y'] - t['y'])
                if best is None or d < best[0]: best = (d, w)
            if best is None:
                for w in cis:
                    d = math.hypot(w['xy'][0] - t['lx'], w['xy'][1] - t['ly'])
                    if d <= P['cistern_reach'] and (best is None or d < best[0]): best = (d, w)
            out[t['key']] = best
        return out
    return ctx.once('water_src', build).get(s['key'])


def r_same_water(s, Y, ctx):
    """1 同一口水：喝同一口井/蓄水池的人家是一个打水圈。"""
    P = ctx.P['water']
    nb = ctx.once('water_nb', ctx.knn_in_group(lambda t: (water_source(t, ctx) or (None, {'id': None}))[1]['id'], P['k'], P['mode']))
    return [(s['key'], o['key'], 'water', g) for o, g in nb.get(s['key'], [])]


def r_carrier(s, Y, ctx):
    """1b 运水人与主顾：离水远的人家靠附近的运水人挑水上门。"""
    P = ctx.P['carrier']
    if s['trade'] != '运水人': return []
    cands = []
    for o in ctx.grid.near(s['x'], s['y'], P['radius']):
        if o is s or o['trade'] == '运水人': continue
        ws = water_source(o, ctx)
        if ws is None or ws[0] > P['far']: cands.append(o)
    cands.sort(key=lambda o: D(s, o))
    return [(s['key'], o['key'], 'carrier', '挑水上门') for o in cands[:P['max_customers']]]


def r_bread(s, Y, ctx):
    """2 面包跟着房子走：君士坦丁的房屋面包配给，有房的户在同一座炉/面包台阶领面包；租户没有。"""
    P = ctx.P['bread']
    if not s['owner']: return []
    def oven_of(t):
        if not t['owner']: return None
        ov = [o for o in ctx.G['ovens'] if o['built'] <= ctx.Y]
        if not ov: return None
        return min(ov, key=lambda o: math.hypot(o['xy'][0] - t['x'], o['xy'][1] - t['y']))['id']
    nb = ctx.once('bread_nb', ctx.knn_in_group(oven_of, P['k'], P['mode']))
    return [(s['key'], o['key'], 'bread', g) for o, g in nb.get(s['key'], [])]


def r_faith(s, Y, ctx):
    """3 信仰分线：附近同派的人家一起去做礼拜（51 年后阿里乌派一起走出奠基者城门）。"""
    P = ctx.P['faith']
    o = sorted((t for t in ctx.grid.near(s['x'], s['y'], P['radius']) if t is not s and t['faith'] == s['faith']), key=lambda t: D(s, t))
    note = '同出城门' if s['faith'] == '阿里乌派' and Y >= ctx.P['church']['arian_out_from'] else '同堂'
    return [(s['key'], t['key'], 'faith', note) for t in o[:P['k']]]


def r_hometown(s, Y, ctx):
    """4 同乡带同乡：外地来的人家，投奔的是搬来时附近已住着、早几年来的同乡。"""
    P = ctx.P['chain']
    if s['origin'] == '本城生': return []
    grids = ctx.once('origin_grids', lambda: {o: Grid([t for t in ctx.S if t['origin'] == o], 150)
                                               for o in {t['origin'] for t in ctx.S}})
    best = None
    for t in grids[s['origin']].near(s['x'], s['y'], P['radius']):
        if t is s: continue
        if not (0 < s['B'] - t['B'] <= P['max_gap']): continue
        d = D(s, t)
        if best is None or d < best[0]: best = (d, t)
    return [(best[1]['key'], s['key'], 'hometown', s['origin'])] if best else []


def r_trade_street(s, Y, ctx):
    """5 同行聚街：同一条街上同行当的人家。"""
    P = ctx.P['trade_street']
    nb = ctx.once('trade_nb', ctx.knn_in_group(lambda t: (t['street'], t['trade']) if t['street'] else None, P['k'], P['mode']))
    return [(s['key'], o['key'], 'trade', s['street']) for o, g in nb.get(s['key'], [])]


# ------------------------------------------------------------------ 经济

def landlord_map(ctx):
    P = ctx.P['landlord']
    def build():
        load = collections.Counter(); out = {}
        owners = [t for t in ctx.S if t['owner']]
        by_street = collections.defaultdict(list)
        for t in owners: by_street[t['street']].append(t)
        for t in sorted((t for t in ctx.S if not t['owner']), key=lambda t: t['key']):
            pool = [o for o in by_street.get(t['street'], []) if t['street']] or [o for o in owners if D(o, t) <= P['radius']]
            pool = [o for o in pool if load[o['key']] < P['cap']]
            if not pool: continue
            o = max(pool, key=lambda o: (o['tenure'], -D(o, t)))
            load[o['key']] += 1; out[t['key']] = o
        return out
    return ctx.once('landlord', build)


def r_landlord(s, Y, ctx):
    """6 房东与租户：住进旧房子的后来户向同街的老住户租房（假设）。"""
    o = landlord_map(ctx).get(s['key'])
    return [(o['key'], s['key'], 'landlord', '租房')] if o else []


def debt_map(ctx):
    """灾年借粮：灾年里有丧事/缺男丁/人口多的租户，向附近有房的面包师或酒馆老板借；债拖 years 年。"""
    P = ctx.P['debt']
    def build():
        out = {}
        S = ctx.S
        for hy in ctx.G['hard_years']:
            if not (ctx.Y - P['years'] < hy <= ctx.Y): continue
            # 债在借的那年结下：用那一年的人家判断谁借谁；仍都在住才算还欠着
            Sy = ctx.G['states_of'](hy)
            load = collections.Counter()
            lenders = [t for t in Sy if t['owner'] and t['trade'] in P['lender_trades'] and not t['needy']]
            g = Grid(lenders)
            for t in sorted(Sy, key=lambda t: t['key']):
                if t['owner'] or not (t['deaths'] or t['needy'] or t['size'] >= 6): continue
                c = [o for o in g.near(t['x'], t['y'], P['radius']) if load[o['key']] < P['cap']]
                if not c: continue
                o = min(c, key=lambda o: D(o, t)); load[o['key']] += 1
                if o['key'] in ctx.by_key and t['key'] in ctx.by_key:
                    out.setdefault(t['key'], []).append((o['key'], hy))
        return out
    return ctx.once('debt', build)


def r_debt(s, Y, ctx):
    """7 借贷与债：灾年（以死亡率推，假设）借粮，债主是有房的面包师/酒馆老板。"""
    return [(o, s['key'], 'debt', f'{hy}年借粮') for o, hy in debt_map(ctx).get(s['key'], [])]


def r_apprentice(s, Y, ctx):
    """8 工钱与学徒：没有成年男人的人家，12–15 岁的儿子跟附近同行当的师傅学手艺（找不到同行就跟最近的师傅）。"""
    P = ctx.P['apprentice']
    if s['men'] > 0: return []
    boys = [p for p in s['boys'] if P['age'][0] <= Y - p['b'] <= P['age'][1]]
    if not boys: return []
    near = [t for t in ctx.grid.near(s['x'], s['y'], P['radius']) if t is not s and t['men'] > 0]
    if not near: return []
    same = [t for t in near if t['trade'] == s['trade']]
    m = min(same or near, key=lambda t: D(s, t))
    return [(m['key'], s['key'], 'apprentice', boys[0]['n'])]


def r_rival(s, Y, ctx):
    """9 行会/同行竞争：一条街上同行超过这类街区容得下的数目，最近的那一家就是对头。"""
    P = ctx.P['rival']
    def build():
        cnt = collections.Counter((t['street'], t['trade']) for t in ctx.S if t['street'])
        return cnt
    cnt = ctx.once('rival_cnt', build)
    if not s['street']: return []
    cap = P['cap'].get(s['fn'], P['cap']['default'])
    if cnt[(s['street'], s['trade'])] <= cap: return []
    o = [t for t in ctx.grid.near(s['x'], s['y'], P['dist']) if t is not s and t['trade'] == s['trade'] and t['street'] == s['street']]
    if not o: return []
    t = min(o, key=lambda t: D(s, t))
    return [(s['key'], t['key'], 'rival', s['street'])]


# ------------------------------------------------------------------ 政治体制

def patron_map(ctx):
    P = ctx.P['patron']
    def build():
        pats = [t for t in ctx.S if t['fn'] == 'fine' or (t['owner'] and t['tenure'] >= P['min_tenure'] and t['size'] >= P['min_size'])]
        g = Grid(pats); load = collections.Counter(); out = {}
        pk = {t['key'] for t in pats}
        for t in sorted(ctx.S, key=lambda t: t['key']):
            if t['key'] in pk: continue
            if not (t['needy'] or (not t['owner'] and (t['deaths'] or t['tenure'] <= 3))): continue
            c = [o for o in g.near(t['x'], t['y'], P['radius']) if load[o['key']] < P['cap']]
            if not c: continue
            if P['prefer_same_faith'] and any(o['faith'] == t['faith'] for o in c): c = [o for o in c if o['faith'] == t['faith']]
            o = min(c, key=lambda o: D(o, t)); load[o['key']] += 1; out[t['key']] = o
        return out
    return ctx.once('patron', build)


def r_patron(s, Y, ctx):
    """10 恩主与门客：有地位的人家罩着附近缺男丁、有丧、刚来的穷户（同派优先，假设）。"""
    o = patron_map(ctx).get(s['key'])
    return [(o['key'], s['key'], 'patron', '门客')] if o else []


def alms_source(s, Y, P):
    if not s['needy']: return None
    if Y >= P['xenon_from']: return '@寡妇孤儿之家'
    if s['faith'] == '尼西亚派' and Y >= P['nicene_church_from']: return '@阿纳斯塔西娅的执事'
    if s['faith'] == '阿里乌派':
        if Y < P['arian_out_from']: return '@城里的阿里乌派教堂'
        if Y >= P['arian_church_from']: return '@城门外砖堂'
    return None


def r_church(s, Y, ctx):
    """11 教会层级：执事管施舍，只给本派缺男丁的人家；51 年后阿里乌派在城里领不到；65 年后寡妇孤儿之家不分派。"""
    a = alms_source(s, Y, ctx.P['church'])
    return [(s['key'], a, 'alms', '施舍')] if a else []


def r_office(s, Y, ctx):
    """12 官府：拆房让路（账本）、修蓄水池凑铜板（账本：54 运水人、62 上坡人家）、57 年修广场按街征工（假设）。"""
    P = ctx.P['office']; out = []
    h = s['h']
    if h['destroyed'] == Y + 1:
        site = {54: '运水人蓄水池', 57: '狄奥多西广场', 62: '运水人台阶路'}.get(h['destroyed'], '公家工程')
        out.append((s['key'], '@拆房:' + site, 'evicted', f'{h["destroyed"]}年拆'))
    ly = P['levy_years'].get(str(Y))
    if ly:
        c = next((w for w in ctx.G['water'] if w['id'] == ly), None)
        if c:
            d = math.hypot(c['xy'][0] - s['lx'], c['xy'][1] - s['ly'])
            uphill = Y == 62 and s['ly'] < c['xy'][1]
            if d <= P['levy_radius'] and (s['trade'] == '运水人' or uphill):
                out.append((s['key'], '@凑铜板:' + ly, 'levy', str(Y)))
    if Y == P['corvee_year']:
        def build():
            by = collections.defaultdict(list)
            for t in ctx.S:
                if not t['owner'] and t['men'] >= 1 and t['street']: by[t['street']].append(t)
            pick = set()
            for st, l in by.items():
                for t in sorted(l, key=lambda t: (-t['men'], t['key']))[:P['corvee_per_street']]: pick.add(t['key'])
            return pick
        if s['key'] in ctx.once('corvee', build):
            out.append((s['key'], '@征工:' + P['corvee_site'], 'corvee', '假设'))
    return out


def r_garrison(s, Y, ctx):
    """13 军营：兵营坊里/城门兵营附近的人家，和有儿子当了兵的人家，都跟兵营连着。"""
    P = ctx.P['garrison']
    b = ctx.G['places'].get('barracks_gate')
    out = []
    near = b and math.hypot(b['xy'][0] - s['lx'], b['xy'][1] - s['ly']) <= P['radius']
    if s['fn'] == 'garrison' or near: out.append((s['key'], '@城门兵营', 'garrison', '兵营边上'))
    if s['soldier']: out.append((s['key'], '@城门兵营', 'garrison', s['soldier'][-1][1]))
    return out[:1] if len(out) == 2 and out[0][3] == out[1][3] else out


RULES = [
    ('基础', 'water', r_same_water), ('基础', 'carrier', r_carrier), ('基础', 'bread', r_bread), ('基础', 'faith', r_faith),
    ('基础', 'hometown', r_hometown), ('基础', 'trade', r_trade_street),
    ('经济', 'landlord', r_landlord), ('经济', 'debt', r_debt), ('经济', 'apprentice', r_apprentice), ('经济', 'rival', r_rival),
    ('政治', 'patron', r_patron), ('政治', 'alms', r_church), ('政治', 'office', r_office), ('政治', 'garrison', r_garrison),
]
UNDIRECTED = {'water', 'bread', 'faith', 'trade', 'rival'}


def edges_of_year(states, Y, P, G, only=None):
    ctx = Ctx(states, Y, P, G)
    seen = set(); out = []
    for layer, name, fn in RULES:
        if only and name not in only: continue
        for s in states:
            for a, b, t, note in fn(s, Y, ctx):
                k = (t, *sorted((a, b))) if t in UNDIRECTED else (t, a, b)
                if k in seen: continue
                seen.add(k); out.append((a, b, t, note))
    return out, ctx
