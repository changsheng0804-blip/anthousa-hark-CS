"""规则预演 v1 · 单户「此刻的自我网」按需现算（不建全城的边表）。

ego(户, 年) 返回这户这一年的全部关系：
  强关系（读存的）：交叉点（起止年区间）、制度分配（租约 / 门客 / 债的起止年区间）
  弱关系（现算）：同一口水、面包同排、信仰同堂、同乡链、同街同行、同行对头、学徒、施舍 / 官府 / 兵营、亲家（v1 新增）
每类弱关系都只在这户附近现算，包括「反向」——别人把我算进他的 k 近邻（v0 的边是无向去重的，所以两头都要）。
每户不变的属性（坐标、籍贯/信仰/行当、有房、喝哪口水与哪座炉随「井/炉建成」分几段、同乡候选表）一次性预计算并缓存。
运行：python3 ego.py SCOPE [年]   → 核对（与 v0 那一年的全量边逐户逐类比对）+ 计时 + 浏览器下发字节估算
"""
import os, sys, json, time, math, pickle, collections, gzip
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prep
from engine import ARIAN, NICENE

# 关系重要度（分级）：数字越大越重要。交叉点永远排最前（它就是强关系）。
TIER = dict(cross=9, kin=4, landlord=4, debt=4, patron=4,
            alms=3, faith=3, apprentice=3, evicted=3, levy=3, corvee=3, garrison=3,
            hometown=2, rival=2,
            water=1, bread=1, trade=1)
COST_ORDER = ['cross', 'assign', 'kin', 'node', 'apprentice', 'hometown', 'rival', 'faith', 'water', 'bread', 'trade']   # 从便宜/重要到贵/背景


class Ego:
    def __init__(self, scope, mode='v1', P=None):
        self.scope = scope
        self.P = P or json.load(open(os.path.join(HERE, '..', 'rules_v0', 'rules.json')))
        D = prep.load(scope); M = D['main']; self.D = D; self.M = M
        self.YR0 = D['YR0']
        fh = M['fh']
        self.fx = M['hx'][fh]; self.fy = M['hy'][fh]; self.flx = M['hlx'][fh]; self.fly = M['hly'][fh]
        self.NF = len(fh)
        self.owner = (M['fi'] == 0) & (M['fB'] <= self.P['bread']['owner_before'])
        self.fn = M['hfn'][fh]; self.fn_names = M['fn_names']; self.dest = M['hdest'][fh]
        self.keys = M['keys']; self.key2f = {k: i for i, k in enumerate(self.keys)}
        self.carrier_t = M['trades'].index('运水人') if '运水人' in M['trades'] else -99
        # v0 Grid(120) 遍历序（坐标不变，所以是每户不变的属性）
        tk = np.empty(self.NF, np.int64)
        tk[np.lexsort((np.arange(self.NF), np.floor(self.fy / 120), np.floor(self.fx / 120)))] = np.arange(self.NF)
        self.tk = tk
        z = np.load(os.path.join(prep.CACHE, f"rules_v1_{scope}_chain_{self.P['chain']['radius']}_{self.P['chain']['max_gap']}.npz"))
        self.ch_s, self.ch_t = z['s'], z['t']
        self.ch_ptr = np.searchsorted(self.ch_s, np.arange(self.NF + 1))
        o = np.argsort(self.ch_t, kind='stable'); self.rch_s = self.ch_s[o]; self.rch_t = self.ch_t[o]
        self.rch_ptr = np.searchsorted(self.rch_t, np.arange(self.NF + 1))
        st = pickle.load(open(os.path.join(prep.CACHE, f'rules_v1_strong_{scope}_{mode}.pkl'), 'rb'))
        self.cross = st['cross']; self.assign = st['assign']
        self.cx_of = collections.defaultdict(list)
        for i, (fa, fb, node, sc, pats, ivs) in enumerate(self.cross):
            self.cx_of[fa].append(i)
            if fb >= 0: self.cx_of[fb].append(i)
        self.as_of = collections.defaultdict(list)
        for i, (k, a, b, y0, y1) in enumerate(self.assign):
            self.as_of[a].append(i); self.as_of[b].append(i)
        self.kin_of = collections.defaultdict(list)
        for i, (a, b, y0, y1) in enumerate(M['kin'].tolist()):
            self.kin_of[a].append(i); self.kin_of[b].append(i)
        W = D['water']
        self.wx = np.array([w['x'] for w in W]); self.wy = np.array([w['y'] for w in W]); self.wb = np.array([w['built'] for w in W])
        self.wwell = np.array([w['kind'] == 'well' for w in W]); self.wid = [w['id'] for w in W]
        O = D['ovens']
        self.ox = np.array([o['x'] for o in O]); self.oy = np.array([o['y'] for o in O]); self.ob = np.array([o['built'] for o in O])
        self._wcache = {}; self._ocache = {}; self._ycache = {}
        self.counter = collections.Counter()

    # ---------------- 每户不变属性（按井/炉建成分段缓存）
    def water_of_all(self, Y):
        """所有户在 Y 年喝哪口水 / 距离。只取决于哪些井、池已建成，按「建成集合」缓存。"""
        key = (tuple(np.nonzero(self.wb <= Y)[0]))
        if key in self._wcache: return self._wcache[key]
        x, y, lx, ly = self.fx, self.fy, self.flx, self.fly; n = self.NF; R = self.P['water']
        wsrc = np.full(n, -1); wd = np.full(n, np.inf)
        wm = np.nonzero(self.wwell & (self.wb <= Y))[0]
        if len(wm):
            kk = min(3, len(wm))
            d, i = cKDTree(np.c_[self.wx[wm], self.wy[wm]]).query(np.c_[x, y], k=kk, distance_upper_bound=R['well_reach'] * 1.0001)
            i = np.asarray(i).reshape(n, -1); ok = i < len(wm); wi = wm[np.where(ok, i, 0)]
            dd = np.where(ok, np.hypot(self.wx[wi] - x[:, None], self.wy[wi] - y[:, None]), np.inf)
            dd = np.where(dd <= R['well_reach'], dd, np.inf)
            gr = np.floor(self.wx[wi] / 140) * 1e9 + np.floor(self.wy[wi] / 140) * 1e4 + wi
            j = np.lexsort((gr, dd), axis=1)[:, 0]
            pick = wi[np.arange(n), j]; pd_ = dd[np.arange(n), j]; ok = pd_ < np.inf
            wsrc[ok] = pick[ok]; wd[ok] = pd_[ok]
        cm = np.nonzero(~self.wwell & (self.wb <= Y))[0]
        if len(cm):
            rest = np.nonzero(wsrc < 0)[0]
            dc = np.hypot(self.wx[cm][None, :] - lx[rest, None], self.wy[cm][None, :] - ly[rest, None])
            j = np.argmin(dc, 1); dj = dc[np.arange(len(rest)), j]; ok = dj <= R['cistern_reach']
            wsrc[rest[ok]] = cm[j[ok]]; wd[rest[ok]] = dj[ok]
        self._wcache[key] = (wsrc, wd)
        return wsrc, wd

    def oven_of_all(self, Y):
        key = tuple(np.nonzero(self.ob <= Y)[0])
        if key in self._ocache: return self._ocache[key]
        om = np.nonzero(self.ob <= Y)[0]; out = np.full(self.NF, -1)
        if len(om):
            kk = min(3, len(om))
            _, oi = cKDTree(np.c_[self.ox[om], self.oy[om]]).query(np.c_[self.fx, self.fy], k=kk)
            oi = om[np.asarray(oi).reshape(self.NF, -1)]
            dd = np.hypot(self.ox[oi] - self.fx[:, None], self.oy[oi] - self.fy[:, None])
            out = oi[np.arange(self.NF), np.lexsort((oi, dd), axis=1)[:, 0]]
        self._ocache[key] = out
        return out

    def year_ctx(self, Y):
        """切年：一列在住户 + 几个按户属性（不是边）。切换年份时做一次。"""
        if Y in self._ycache: return self._ycache[Y]
        M = self.M; yi = Y - self.YR0
        pres = M['present'][:, yi]
        men = M['men'][:, yi]; kids = M['kids'][:, yi]
        ctx = dict(Y=Y, yi=yi, pres=pres, S=np.nonzero(pres)[0], men=men, needy=(men == 0) & (kids > 0), dth=M['deaths'][:, yi] > 0,
                   st=M['hstreet'][M['fh'], yi], size=M['size'][:, yi], boy=M['boy'][:, yi])
        ctx['wsrc'], ctx['wd'] = self.water_of_all(Y)
        ctx['oven'] = self.oven_of_all(Y)
        if len(self._ycache) > 4: self._ycache.pop(next(iter(self._ycache)))
        self._ycache[Y] = ctx
        return ctx

    # ---------------- 组内 k 近邻（含反向）：只在这户所在的组里现算
    def _group_knn(self, F, G, k, bound=None, tie=None):
        """G：组员（全局下标，含 F）。返回 (F 的 k 近邻, 把 F 算进自己 k 近邻的组员)。"""
        if len(G) <= 1: return [], []
        x, y = self.fx[G], self.fy[G]
        tie = G if tie is None else tie[G]
        kk = min(k + 4, len(G))
        t = cKDTree(np.c_[x, y])
        d, i = t.query(np.c_[x, y], k=kk)
        i = np.asarray(i).reshape(len(G), -1)
        dd = np.hypot(x[i] - x[:, None], y[i] - y[:, None])
        self_ = i == np.arange(len(G))[:, None]
        dd = np.where(self_, np.inf, dd)
        if bound is not None: dd = np.where(dd <= bound, dd, np.inf)
        o = np.lexsort((tie[i], dd), axis=1)
        i = np.take_along_axis(i, o, 1)[:, :k]; dd = np.take_along_axis(dd, o, 1)[:, :k]
        nb = np.where(dd < np.inf, G[i], -1)
        fi = int(np.nonzero(G == F)[0][0])
        mine = [int(v) for v in nb[fi] if v >= 0]
        rev = [int(G[r]) for r in np.nonzero((nb == F).any(1))[0]]
        self.counter['knn_points'] += len(G)
        return mine, rev

    # ---------------- 自我网
    def ego(self, F, Y, budget=None, only=None):
        """F：户下标（或户键）。budget：最多要几条（按重要度从高到低算，够数就停，背景类最后算）。only：只算这些类。"""
        if isinstance(F, str): F = self.key2f[F]
        c = self.year_ctx(Y); P = self.P
        if not c['pres'][F]: return []
        out = []
        def emit(o, t, note=''):
            out.append((o, t, TIER[t], note))
        def full(): return budget is not None and len(out) >= budget
        S = c['S']
        for step in COST_ORDER:
            if only and step not in only: continue
            if full(): break
            if step == 'cross':
                for i in self.cx_of.get(F, ()):
                    fa, fb, node, sc, pats, ivs = self.cross[i]
                    if any(a <= Y <= b for a, b in ivs):
                        o = node if fb < 0 else (fb if fa == F else fa)
                        out.append((o, 'cross', 9 + sc / 100, '+'.join(pats)))
                out.sort(key=lambda r: -r[2])
            elif step == 'assign':
                for i in self.as_of.get(F, ()):
                    k, a, b, y0, y1 = self.assign[i]
                    if y0 <= Y <= y1: emit(b if a == F else a, k, '房东' if (k == 'landlord' and a == F) else '')
            elif step == 'kin':
                for i in self.kin_of.get(F, ()):
                    a, b, y0, y1 = self.M['kin'][i]
                    if y0 <= Y < y1 and c['pres'][a] and c['pres'][b]: emit(int(b if a == F else a), 'kin', '嫁女')
            elif step == 'node':
                self._nodes(F, c, emit)
            elif step == 'apprentice':
                self._apprentice(F, c, emit)
            elif step == 'hometown':
                p = self._parent(F, c)
                if p >= 0: emit(p, 'hometown', '投奔')
                for j in range(self.rch_ptr[F], self.rch_ptr[F + 1]):
                    s = int(self.rch_s[j])
                    if c['pres'][s] and self._parent(s, c) == F: emit(s, 'hometown', '来投')
            elif step == 'rival':
                self._rival(F, c, emit)
            elif step == 'faith':
                fa = self.M['ff']; R = P['faith']['radius']
                Sx = S[(fa[S] == fa[F])]
                d = np.hypot(self.fx[Sx] - self.fx[F], self.fy[Sx] - self.fy[F])
                G = Sx[d <= 2 * R]                        # 反向只可能来自 90px 内的人，他们的近邻又都在 180px 内
                G2 = G[np.hypot(self.fx[G] - self.fx[F], self.fy[G] - self.fy[F]) <= R]
                mine, rev = self._group_knn(F, G, P['faith']['k'], bound=R, tie=self.tk)
                g2 = set(G2.tolist()); rev = [r for r in rev if r in g2]   # 只有 90px 内的人的近邻表是完整的
                for o in dict.fromkeys(mine + rev): emit(o, 'faith')
            elif step == 'water':
                w = c['wsrc'][F]
                if w >= 0:
                    G = S[c['wsrc'][S] == w]
                    mine, rev = self._group_knn(F, G, P['water']['k'])
                    for o in dict.fromkeys(mine + rev): emit(o, 'water', self.wid[w])
            elif step == 'bread':
                if self.owner[F]:
                    G = S[self.owner[S] & (c['oven'][S] == c['oven'][F])]
                    mine, rev = self._group_knn(F, G, P['bread']['k'])
                    for o in dict.fromkeys(mine + rev): emit(o, 'bread')
            elif step == 'trade':
                stF = c['st'][F]
                if stF >= 0:
                    G = S[(c['st'][S] == stF) & (self.M['ft'][S] == self.M['ft'][F])]
                    mine, rev = self._group_knn(F, G, P['trade_street']['k'])
                    for o in dict.fromkeys(mine + rev): emit(o, 'trade')
        self.counter['relations'] += len(out)
        return out[:budget] if budget is not None else out

    def _parent(self, s, c):
        for j in range(self.ch_ptr[s], self.ch_ptr[s + 1]):
            t = self.ch_t[j]
            if c['pres'][t]: return int(t)
        return -1

    def _rival(self, F, c, emit):
        stF = c['st'][F]
        if stF < 0: return
        S = c['S']; Rp = self.P['rival']
        G = S[(c['st'][S] == stF) & (self.M['ft'][S] == self.M['ft'][F])]
        cnt = len(G)
        cap = lambda f: Rp['cap'].get(self.fn_names[self.fn[f]], Rp['cap']['default'])
        def near(s):
            d = np.hypot(self.fx[G] - self.fx[s], self.fy[G] - self.fy[s]); d[G == s] = np.inf
            d = np.where(d <= Rp['dist'], d, np.inf)
            if not np.isfinite(d).any(): return -1
            j = np.lexsort((self.tk[G], d))[0]
            return int(G[j]) if np.isfinite(d[j]) else -1
        if cnt > cap(F):
            t = near(F)
            if t >= 0: emit(t, 'rival')
        for s in G:
            if s != F and cnt > cap(s) and np.hypot(self.fx[s] - self.fx[F], self.fy[s] - self.fy[F]) <= Rp['dist'] and near(s) == F:
                emit(int(s), 'rival')

    def _master_of(self, s, c, S_m):
        Ap = self.P['apprentice']; ft = self.M['ft']
        d = np.hypot(self.fx[S_m] - self.fx[s], self.fy[S_m] - self.fy[s])
        ok = d <= Ap['radius']
        if not ok.any(): return -1
        same = ok & (ft[S_m] == ft[s])
        m = same if same.any() else ok
        dd = np.where(m, d, np.inf)
        return int(S_m[np.lexsort((self.tk[S_m], dd))[0]])

    def _apprentice(self, F, c, emit):
        S = c['S']; Ap = self.P['apprentice']
        d = np.hypot(self.fx[S] - self.fx[F], self.fy[S] - self.fy[F])
        near = S[d <= Ap['radius'] * 2]
        S_m = near[c['men'][near] > 0]
        if c['men'][F] == 0 and c['boy'][F]:
            m = self._master_of(F, c, S_m)
            if m >= 0: emit(m, 'apprentice', '拜师')
        if c['men'][F] > 0:
            near1 = S[d <= Ap['radius']]
            for s in near1[(c['men'][near1] == 0) & c['boy'][near1]]:
                if self._master_of(int(s), c, S_m) == F: emit(int(s), 'apprentice', '收徒')

    def _nodes(self, F, c, emit):
        Y = c['Y']; P = self.P; C = P['church']; fa = self.M['ff'][F]
        if c['needy'][F]:
            src = None
            if Y >= C['xenon_from']: src = '@寡妇孤儿之家'
            elif fa == NICENE and Y >= C['nicene_church_from']: src = '@阿纳斯塔西娅的执事'
            elif fa == ARIAN: src = '@城里的阿里乌派教堂' if Y < C['arian_out_from'] else ('@城门外砖堂' if Y >= C['arian_church_from'] else None)
            if src: emit(src, 'alms')
        if self.dest[F] == Y + 1:
            emit('@拆房:' + {54: '运水人蓄水池', 57: '狄奥多西广场', 62: '运水人台阶路'}.get(int(self.dest[F]), '公家工程'), 'evicted')
        Po = P['office']; ly_ = Po['levy_years'].get(str(Y))
        if ly_ and ly_ in self.wid:
            w = self.wid.index(ly_)
            if math.hypot(self.wx[w] - self.flx[F], self.wy[w] - self.fly[F]) <= Po['levy_radius'] and \
                    (self.M['ft'][F] == self.carrier_t or (Y == 62 and self.fly[F] < self.wy[w])):
                emit('@凑铜板:' + ly_, 'levy')
        if Y == Po['corvee_year'] and not self.owner[F] and c['men'][F] >= 1 and c['st'][F] >= 0:
            S = c['S']; G = S[(c['st'][S] == c['st'][F]) & ~self.owner[S] & (c['men'][S] >= 1)]
            kr = np.argsort(np.argsort(np.array([self.keys[g] for g in G], dtype=object)))
            top = G[np.lexsort((kr, -c['men'][G]))[:Po['corvee_per_street']]]
            if F in top: emit('@征工:' + Po['corvee_site'], 'corvee')
        b = self.D['barracks']; fg = self.fn_names.index('garrison') if 'garrison' in self.fn_names else -99
        if self.fn[F] == fg or (b is not None and math.hypot(b[0] - self.flx[F], b[1] - self.fly[F]) <= P['garrison']['radius']) or self.M['fsold'][F] <= Y:
            emit('@城门兵营', 'garrison')


# ---------------------------------------------------------------- 核对 + 计时 + 字节
HARD = dict(sample=[45, 51], xero=[45, 51], city=[44])   # 与 v0/v1 同一推法得到的灾年（见 out/*_compat.json hard_years）


def verify_against_v0(scope, Y, n_check=400, seed=1):
    """拿 v0 那一年的全量边（rules_v0.rules.edges_of_year）逐户逐类比对。"""
    sys.path.insert(1, os.path.join(HERE, '..', 'rules_v0'))
    import data as D0, rules as R0
    P = json.load(open(os.path.join(HERE, '..', 'rules_v0', 'rules.json')))
    R0.OWNER_BEFORE = P['bread']['owner_before']
    W = D0.load_xero() if scope != 'city' else D0.load_city()
    if scope == 'sample':
        ids = set(json.load(open(os.path.join(HERE, '..', 'rules_v0', 'sample.json')))['houses'])
        W = dict(W, houses=[h for h in W['houses'] if h['id'] in ids])
    E = Ego(scope, 'compat')
    states = [s for s in (R0.household_state(h, Y) for h in W['houses']) if s]
    full = W['houses']
    sc = {}
    def states_of(y):
        if y not in sc: sc[y] = [s for s in (R0.household_state(h, y) for h in full) if s]
        return sc[y]
    G = dict(water=W['water'], ovens=W['ovens'], places=W['places'], hard_years=HARD[scope], states_of=states_of)
    edges, _ = R0.edges_of_year(states, Y, P, G, only={'water', 'bread', 'faith', 'hometown', 'trade', 'rival', 'apprentice', 'alms', 'office', 'garrison', 'landlord', 'patron', 'debt'})
    nb = collections.defaultdict(set)
    for a, b, t, note in edges:
        nb[(a, t)].add(b)
        if not b.startswith('@'): nb[(b, t)].add(a)
    rng = np.random.default_rng(seed)
    keys = [s['key'] for s in states]
    pick = rng.choice(len(keys), min(n_check, len(keys)), replace=False)
    bad = collections.Counter(); ex = []
    T_OF = dict(landlord='landlord', patron='patron', debt='debt', water='water', bread='bread', faith='faith', hometown='hometown', trade='trade', rival='rival', apprentice='apprentice',
                alms='alms', evicted='evicted', levy='levy', corvee='corvee', garrison='garrison')
    for p in pick:
        k = keys[p]; F = E.key2f[k]
        got = collections.defaultdict(set)
        for o, t, tier, note in E.ego(F, Y, only=['assign', 'node', 'apprentice', 'hometown', 'rival', 'faith', 'water', 'bread', 'trade']):
            got[t].add(o if isinstance(o, str) else E.keys[o])
        for t in T_OF:
            want = nb.get((k, t), set())
            if got.get(t, set()) != want:
                bad[t] += 1
                if len(ex) < 5: ex.append((k, t, sorted(want), sorted(got.get(t, set()))))
    return dict(year=Y, checked=len(pick), mismatched_by_type=dict(bad), examples=ex)


def bench(scope, Y=55, n=1000, seed=2):
    E = Ego(scope, 'v1')
    t = time.perf_counter(); E.year_ctx(Y); t_ctx = time.perf_counter() - t
    S = E.year_ctx(Y)['S']
    rng = np.random.default_rng(seed); pick = rng.choice(S, min(n, len(S)), replace=False)
    ts = []; nrel = []
    for F in pick:
        a = time.perf_counter(); r = E.ego(int(F), Y); ts.append(time.perf_counter() - a); nrel.append(len(r))
    ts = np.array(ts) * 1000
    tb = []
    for F in pick[:300]:
        a = time.perf_counter(); E.ego(int(F), Y, budget=4); tb.append(time.perf_counter() - a)
    tb = np.array(tb) * 1000
    return dict(scope=scope, year=Y, year_switch_ms=round(t_ctx * 1000, 1), households_in_year=int(len(S)), n=len(pick),
                full_ego_ms=dict(mean=round(ts.mean(), 2), p50=round(np.median(ts), 2), p95=round(np.percentile(ts, 95), 2), max=round(ts.max(), 2)),
                relations_per_household=dict(mean=round(float(np.mean(nrel)), 1), max=int(np.max(nrel))),
                top4_ego_ms=dict(mean=round(tb.mean(), 3), p95=round(np.percentile(tb, 95), 3)))


def browser_bytes(scope, mode='v1'):
    """估算浏览器要下发多少字节才能在 JS 里现算自我网：每户不变属性 + 每户每年的状态位 + 强关系（交叉点、制度分配）。"""
    E = Ego(scope, mode); M = E.M; NF = E.NF; NH = len(M['hid'])
    y0, y1 = 40, 70; ny = y1 - y0 + 1
    house = np.zeros(NH, dtype=[('x', '<i2'), ('y', '<i2'), ('lx', '<i2'), ('ly', '<i2'), ('built', 'i1'), ('dest', 'i1'), ('fn', 'u1')])
    house['x'] = np.round(M['hx']); house['y'] = np.round(M['hy']); house['lx'] = np.round(M['hlx']); house['ly'] = np.round(M['hly'])
    house['built'] = np.clip(M['hbuilt'], -128, 127); house['dest'] = np.clip(M['hdest'], -128, 127); house['fn'] = M['hfn']
    # 街：每房按年份变化的段（多数房只有 1 段）
    seg = []
    for i in range(NH):
        row = M['hstreet'][i]; ch = np.r_[0, np.nonzero(np.diff(row))[0] + 1]
        for c_ in ch: seg.append((i, row[c_] & 0xffff, y0 + c_))
    segs = np.array(seg, dtype=[('house', '<u2'), ('street', '<u2'), ('from', 'i1')])   # 每房按年份变化的街段（多数房只有 1 段）
    fam = np.zeros(NF, dtype=[('house', '<u2'), ('B', 'i1'), ('ofa', '<u2'), ('trade', 'u1'), ('sold', 'i1')])
    fam['house'] = M['fh']; fam['B'] = np.clip(M['fB'], -128, 127); fam['ofa'] = M['fo'] * 4 + M['ff']; fam['trade'] = M['ft']; fam['sold'] = np.clip(M['fsold'], -128, 127)
    yi = slice(0, ny)
    st = (M['present'][:, yi].astype(np.uint16) | ((M['men'][:, yi] > 0) << 1) | ((M['kids'][:, yi] > 0) << 2) | ((M['deaths'][:, yi] > 0) << 3)
          | (M['boy'][:, yi] << 4) | ((M['size'][:, yi] >= 5) << 5) | ((M['size'][:, yi] >= 6) << 6))
    state = st.astype(np.uint8)               # 每户每年 1 字节（在住、有成年男人、有小孩、有丧、有 12–15 岁男孩、≥5 口、≥6 口）
    cross = np.zeros(sum(len(c[5]) for c in E.cross), dtype=[('a', '<u2'), ('b', '<u2'), ('y0', 'i1'), ('y1', 'i1'), ('pat', '<u2'), ('score', 'u1')])
    i = 0
    for fa, fb, node, sc, pats, ivs in E.cross:
        for a, b in ivs:
            cross[i] = (fa, fb if fb >= 0 else 65535, a, b, 0, min(255, int(sc * 10))); i += 1
    asg = np.zeros(len(E.assign), dtype=[('k', 'u1'), ('a', '<u2'), ('b', '<u2'), ('y0', 'i1'), ('y1', 'i1')])
    for j, (k, a, b, y0_, y1_) in enumerate(E.assign): asg[j] = ({'landlord': 0, 'patron': 1, 'debt': 2}[k], a, b, y0_, y1_)
    kin = M['kin'].astype('<u2') if len(M['kin']) else np.zeros((0, 4), '<u2')
    parts = dict(houses=house.tobytes(), streets=segs.tobytes(), families=fam.tobytes(), state_by_year=state.tobytes(),
                 crossings=cross.tobytes(), assignments=asg.tobytes(), kin=kin.tobytes())
    raw = {k: len(v) for k, v in parts.items()}
    gz = {k: len(gzip.compress(v, 6)) for k, v in parts.items()}
    tot = sum(raw.values()); tgz = sum(gz.values())
    return dict(scope=scope, houses=NH, families=NF, raw_bytes=raw, gzip_bytes=gz, total_raw=tot, total_gzip=tgz,
                bytes_per_house_raw=round(tot / NH, 1), bytes_per_house_gzip=round(tgz / NH, 1),
                note='同乡候选表、喝哪口水、哪座炉都可在浏览器里从坐标现算，不必下发；街名字符串表另计（干山 87 条）')


if __name__ == '__main__':
    scope = sys.argv[1]; Y = int(sys.argv[2]) if len(sys.argv) > 2 else 55
    res = dict(bench=bench(scope, Y), bytes=browser_bytes(scope))
    if scope != 'city' or '--verify' in sys.argv:
        res['verify_v0'] = verify_against_v0(scope, Y)
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, 'out', f'ego_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
