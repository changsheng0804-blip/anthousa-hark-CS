"""v10 社会关系：亲属/婚姻/市场三类新焦点 + 逐年连续（AF40 初始化，AF41–70 只做增量）。
输入全部来自 data.py（v7 逐年户籍、v8 逐年职位名册、账本房屋、市场类节点）。v9 的焦点/接受率/Dunbar 分层思路沿用（../social_foci_v9/foci.py），但改成按"来源记录"维护的状态机。
——Hark（刘线）"""
import collections, json, os, zlib
import numpy as np
from scipy.spatial import cKDTree
import data

HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = ['亲属', '婚姻', '近邻', '门口路口', '街段', '坊', '行会', '教堂会众', '井/水池', '市场', '职位上下级',
         '职位辖民:坊长', '职位辖民:行会头', '职位辖民:堂区长老（尼西亚）', '职位辖民:会众长老（阿里乌）', '职位辖民:哨长', '职位辖民:水役头', '职位辖民:粮仓主管', '三元闭合']
T = {t: i for i, t in enumerate(TYPES)}
GROUP = ['门口路口', '街段', '坊', '行会', '教堂会众', '井/水池', '市场']
HUB = {'fang_head': ('职位辖民:坊长', 'fang'), 'guild_head': ('职位辖民:行会头', 'guild'), 'parish_elder': ('职位辖民:堂区长老（尼西亚）', 'parish'),
       'arian_elder': ('职位辖民:会众长老（阿里乌）', 'arian_parish'), 'watch_head': ('职位辖民:哨长', 'watch'), 'water_head': ('职位辖民:水役头', 'water'),
       'granary_head': ('职位辖民:粮仓主管', 'grain')}
KIN_LABEL = {1: '父子', 2: '兄弟/祖孙', 3: '叔侄/曾祖'}
GEN = 25   # v8：户主 25 年一代，相位 crc32(房屋 id) mod 25


def crc(*k):
    return zlib.crc32('|'.join(map(str, k)).encode())


def rng_of(seed, *k):
    return np.random.default_rng(crc(seed, *k))


# ======================================================================= 静态世界
class World:
    def __init__(self):
        D = data.load(); Hs = data.houses()
        self.D, self.Hs = D, Hs
        self.ids = Hs['ids']; self.N = len(self.ids); self.pos = {h: k for k, h in enumerate(self.ids)}
        self.xy = Hs['xy']; self.built = Hs['built']; self.dest = Hs['dest']
        self.markets = data.market_nodes(Hs)
        self.offices = {o['id']: o for o in D['offices']}
        # 身份代理：房屋面积三分位（账本一屋一户，无房契/租约 → 房主/租户不可得）
        q = np.quantile(self.Hs['area'], [1 / 3, 2 / 3])
        self.size_cls = np.digitize(self.Hs['area'], q)
        self.codes = collections.defaultdict(dict)   # 类型 -> 字符串 -> 码
        self.names = collections.defaultdict(list)
        self.mem = {}
        for Y in range(data.Y0, data.Y1 + 1):
            self.mem[Y] = self._members(Y)

    def code(self, typ, s):
        d = self.codes[typ]
        if s not in d:
            d[s] = len(d); self.names[typ].append(s)
        return d[s]

    def _members(self, Y):
        recs = self.D['years'][Y]; J = self.D['junc'][Y]; N = self.N
        M = {t: np.full(N, -1, np.int32) for t in GROUP + ['市场2', '区', '街']}
        faith = np.zeros(N, np.int8); stand = np.zeros(N, bool)
        rec = {}
        for h in sorted(recs, key=lambda h: self.pos[h]):
            r = recs[h]; u = self.pos[h]; stand[u] = True; rec[u] = r
            d, fang, water, parish, arian, watch, grain, guild, street = r
            if h in J: M['门口路口'][u] = self.code('门口路口', J[h])
            x, y = self.xy[u]
            M['街段'][u] = self.code('街段', f'{street}@{int(x // 80)},{int(y // 80)}')
            if fang: M['坊'][u] = self.code('坊', fang)
            if guild: M['行会'][u] = self.code('行会', f'{d}×{guild}')
            M['教堂会众'][u] = self.code('教堂会众', arian if arian else parish)
            if water: M['井/水池'][u] = self.code('井/水池', water)
            M['区'][u] = self.code('区', d); M['街'][u] = self.code('街', str(street))
            faith[u] = 1 if arian else 0
        # 市场：当年站着的市场类节点，直线距离（步行距离代理）最近 1–2 个；第二个仅当距离 ≤ 1.5×最近
        mk = [m for m in self.markets if m[5] <= Y < m[6]]
        P = np.array([[m[3], m[4]] for m in mk])
        S = np.where(stand)[0]
        dd = np.hypot(self.xy[S, None, 0] - P[None, :, 0], self.xy[S, None, 1] - P[None, :, 1])
        o = np.argsort(dd, 1, kind='stable')
        c1 = np.array([self.code('市场', mk[i][0]) for i in o[:, 0]])
        c2 = np.array([self.code('市场', mk[i][0]) for i in o[:, 1]])
        second = dd[np.arange(len(S)), o[:, 1]] <= 1.5 * dd[np.arange(len(S)), o[:, 0]]
        M['市场'][S] = c1; M['市场2'][S[second]] = c2[second]
        # 近邻 k 户（自我焦点）+ 保持圈 2k
        tree = cKDTree(self.xy[S] + rng_of(0, 'jit').normal(0, 0.5, (len(S), 2)))
        _, nb = tree.query(self.xy[S] + rng_of(0, 'jit').normal(0, 0.5, (len(S), 2)), k=13)
        knn = S[nb[:, 1:]]
        # 职位：holder 与辖民
        hold = self.D['holders'][Y]
        hub_mem = {}; hub_holder = {}
        for oid, (tname, scope) in HUB.items():
            arr = np.full(N, -1, np.int32); hh = {}
            for u, r in rec.items():
                k = jkey(scope, r)
                if k is not None: arr[u] = self.code(tname, k)
            for (o2, k), h in hold.items():
                if o2 == oid: hh[self.code(tname, k)] = self.pos[h]
            hub_mem[tname] = arr; hub_holder[tname] = hh
        sup = set()
        for (oid, k), h in hold.items():
            s = self.offices[oid]['superior']
            if s is None: continue
            sk = jkey(self.offices[s]['scope'], recs[h])
            hs = hold.get((s, sk))
            if hs is not None and hs != h:
                a, b = sorted((self.pos[h], self.pos[hs])); sup.add((a, b, self.code('职位', f'{oid}→{s}')))
        return dict(M=M, faith=faith, stand=stand, knn=knn, S=S, hub_mem=hub_mem, hub_holder=hub_holder, sup=sorted(sup))


def jkey(scope, r):
    d, fang, water, parish, arian, watch, grain, guild, street = r
    if scope == 'city': return '全城'
    if scope == 'arian_city': return '全城' if arian else None
    if scope == 'district': return d
    if scope == 'guild': return f'{d}×{guild}' if guild else None
    if scope == 'parish': return None if arian else parish
    if scope == 'arian_parish': return arian
    return {'fang': fang, 'water': water, 'watch': watch, 'grain': grain}[scope]


# ======================================================================= 亲属：子户分出成链
def build_lineage(W, cfg):
    """按建成年顺序给每栋 40–70 年间站过的房屋找父户：
    父户候选 = 该年站着、户主在 [b−窗口, b] 内换代（v8 的 25 年一代）、本代分出子户 < 上限 的户；
    优先级：同坊 > 邻坊（新屋最近 12 栋站着房屋的坊）> 同街 > 同区（来源代理）；同级取最近；
    以 p_immigrant（hash 决定）为外来户无父户。b<40 用 AF40 户籍（时代错置，见 REPORT）。"""
    seed = cfg['seed']; win = cfg['kin_window']; maxk = cfg['kin_max_children']
    alive = np.array([W.dest[u] > data.Y0 and W.built[u] <= data.Y1 for u in range(W.N)])
    U = np.where(alive)[0]
    order = U[np.lexsort((np.array([int(W.ids[u][1:]) for u in U]), W.built[U]))]
    parent = np.full(W.N, -1, np.int64); kids = collections.Counter()
    off = np.array([zlib.crc32(h.encode()) % GEN for h in W.ids])
    def mem(Y):
        return W.mem[min(max(Y, data.Y0), data.Y1)]
    placed = np.zeros(0, np.int64)
    dstr = np.array(W.Hs['d'])
    for u in order:
        b = int(W.built[u])
        if (crc(seed, 'imm', W.ids[u]) % 10000) / 10000 < cfg['p_immigrant']:
            continue
        C = placed[W.dest[placed] > b]
        placed = np.append(placed, u)
        if not len(C): continue
        last = b - ((b - W.built[C] + off[C]) % GEN)
        ok = (last > W.built[C]) & (b - last <= win)
        C = C[ok]
        if not len(C): continue
        gk = (b - W.built[C] + off[C]) // GEN
        ok = np.array([kids[(c, g)] < maxk for c, g in zip(C.tolist(), gk.tolist())])
        C, gk = C[ok], gk[ok]
        if not len(C): continue
        m = mem(b); M = m['M']
        fu, su, du = M['坊'][u], M['街'][u], dstr[u]
        dd = np.hypot(*(W.xy[C] - W.xy[u]).T)
        S = m['S']
        near = S[np.argpartition(np.hypot(*(W.xy[S] - W.xy[u]).T), 13)[:13]]
        nf = list(set(M['坊'][near].tolist()) - {-1})
        tier = np.full(len(C), 9)
        tier[dstr[C] == du] = 3
        tier[(M['街'][C] == su) & (su >= 0)] = 2
        tier[np.isin(M['坊'][C], nf)] = 1
        tier[(M['坊'][C] == fu) & (fu >= 0)] = 0
        best = np.lexsort((np.array([crc(seed, W.ids[c], W.ids[u]) for c in C.tolist()]), dd, tier))[0]
        if tier[best] <= 3:
            p = int(C[best]); parent[u] = p; kids[(p, int(gk[best]))] += 1
    return parent


def kin_pairs(W, parent, maxd):
    """亲属树里距离 ≤ maxd 的户对（父子 1、兄弟/祖孙 2、叔侄/曾祖 3）。返回 (u,v,dist)。"""
    anc = {}
    for u in range(W.N):
        a = []; p = parent[u]
        while p >= 0 and len(a) < maxd:
            a.append(int(p)); p = parent[p]
        anc[u] = a
    desc = collections.defaultdict(list)
    for u in range(W.N):
        for k, a in enumerate(anc[u]): desc[a].append((u, k + 1))
    out = {}
    for u in range(W.N):
        chain = [(u, 0)] + [(a, k + 1) for k, a in enumerate(anc[u])]
        for a, da in chain:
            if a != u and da <= maxd:
                key = (min(u, a), max(u, a)); out[key] = min(out.get(key, 99), da)
            for v, dv in desc.get(a, []):
                if v != u and da + dv <= maxd:
                    key = (min(u, v), max(u, v)); out[key] = min(out.get(key, 99), da + dv)
    if not out: return np.zeros((0, 3), np.int64)
    return np.array([(a, b, d) for (a, b), d in sorted(out.items())], np.int64)


# ======================================================================= 记录表
FIELDS = ('typ', 'u', 'v', 'fid', 'born', 'dorm', 'w')
DT = dict(typ=np.int16, u=np.int32, v=np.int32, fid=np.int32, born=np.int16, dorm=np.int16, w=np.float32)


def empty():
    return {f: np.zeros(0, DT[f]) for f in FIELDS}


def make(typ, u, v, fid, born, w):
    n = len(u); a = np.minimum(u, v); b = np.maximum(u, v)
    return dict(typ=np.full(n, typ, np.int16), u=a.astype(np.int32), v=b.astype(np.int32), fid=np.asarray(fid, np.int32) * np.ones(n, np.int32),
                born=np.asarray(born, np.int16) * np.ones(n, np.int16), dorm=np.full(n, -1, np.int16), w=np.full(n, w, np.float32))


def cat(*rs):
    rs = [r for r in rs if len(r['u'])]
    if not rs: return empty()
    return {f: np.concatenate([r[f] for r in rs]) for f in FIELDS}


def sel(R, m):
    return {f: R[f][m] for f in FIELDS}


def dedupe(R, N):
    k = (R['u'].astype(np.int64) * N + R['v']) * 64 + R['typ']
    o = np.lexsort((R['fid'], k))
    k2, f2 = k[o], R['fid'][o]
    keep = np.ones(len(o), bool); keep[1:] = (k2[1:] != k2[:-1]) | (f2[1:] != f2[:-1])
    return sel(R, np.sort(o[keep]))


# ======================================================================= 生成
def accept(W, cfg, m, I, J, d0=None, dist=True, gamma=None):
    a = np.ones(len(I))
    if dist:
        d = np.hypot(*(W.xy[I] - W.xy[J]).T)
        a = (1.0 + d / (d0 or cfg['dist_d0'])) ** (-(gamma or cfg['dist_gamma']))
    F = m['faith']; G = m['M']['行会']
    a = a * np.where(F[I] != F[J], 1 - cfg['homophily_faith'], 1.0)
    a = a * np.where((G[I] >= 0) & (G[J] >= 0) & (G[I] != G[J]), 1 - cfg['homophily_guild'], 1.0)
    return a


def pairs_within(Mem, p, rng):
    s = len(Mem)
    if s < 2 or p <= 0: return np.zeros(0, int), np.zeros(0, int)
    if s <= 80:
        iu, ju = np.triu_indices(s, 1); k = rng.random(len(iu)) < p
        return Mem[iu[k]], Mem[ju[k]]
    n = rng.poisson(p * s * (s - 1) / 2)
    a = rng.integers(0, s, n); b = rng.integers(0, s, n); ok = a != b
    return Mem[a[ok]], Mem[b[ok]]


def pairs_between(A, B, p, rng):
    if len(A) == 0 or len(B) == 0 or p <= 0: return np.zeros(0, int), np.zeros(0, int)
    if len(A) * len(B) <= 6400:
        I, J = np.meshgrid(A, B, indexing='ij'); I, J = I.ravel(), J.ravel(); k = rng.random(len(I)) < p
        I, J = I[k], J[k]
    else:
        n = rng.poisson(p * len(A) * len(B))
        I, J = A[rng.integers(0, len(A), n)], B[rng.integers(0, len(B), n)]
    ok = I != J
    return I[ok], J[ok]


def focus_p(cfg, typ, s):
    if typ == '市场':
        return min(1.0, cfg['market_strength'] / max(1, s))
    return min(1.0, cfg['c'] * cfg['base'].get(typ, 1.0) * s ** (-cfg['a']))


def group_members(m, typ):
    """typ -> {fid: 成员数组}（市场含第二市场）。"""
    M = m['M']; S = m['S']
    col = M[typ][S]
    out = collections.defaultdict(list)
    ok = col >= 0
    if typ == '市场':
        c2 = M['市场2'][S]; ok2 = c2 >= 0
        f = np.concatenate([col[ok], c2[ok2]]); u = np.concatenate([S[ok], S[ok2]])
    else:
        f, u = col[ok], S[ok]
    o = np.lexsort((u, f)); f, u = f[o], u[o]
    if len(f) == 0: return {}
    cut = np.flatnonzero(np.diff(f)) + 1
    return {int(ff[0]): uu for ff, uu in zip(np.split(f, cut), np.split(u, cut))}


def gen_year(W, cfg, Y, prev_m, m, R, init=False):
    """一年的新生：各焦点内 δ·p 的新关系；新入焦点的户与老成员按 p 生成；init 时整焦点按 p 生成（并给出稳态年龄）。"""
    seed = cfg['seed']; TW = cfg['tie_weight']; out = []
    for typ in GROUP:
        rng = rng_of(seed, typ, Y)
        G = group_members(m, typ)
        Gp = group_members(prev_m, typ) if prev_m is not None else {}
        d0 = cfg['market_d0'] if typ == '市场' else cfg['dist_d0']
        gm = cfg['market_gamma'] if typ == '市场' else None
        delta = cfg['turnover'][typ]
        for fid in sorted(G):
            Mem = G[fid]; p = focus_p(cfg, typ, len(Mem))
            if init:
                I, J = pairs_within(Mem, p, rng)
            else:
                old = Gp.get(fid, np.zeros(0, int)); newc = np.setdiff1d(Mem, old); stay = np.intersect1d(Mem, old)
                I1, J1 = pairs_within(stay, p * delta, rng)
                I2, J2 = pairs_between(newc, stay, p, rng)
                I3, J3 = pairs_within(newc, p, rng)
                I, J = np.concatenate([I1, I2, I3]), np.concatenate([J1, J2, J3])
            if len(I) == 0: continue
            k = rng.random(len(I)) < accept(W, cfg, m, I, J, d0, gamma=gm)
            I, J = I[k], J[k]
            born = (Y - rng.geometric(delta, len(I)) + 1) if init else Y
            out.append(make(T[typ], I, J, fid, born, TW[typ]))
    # 近邻 k 户
    rng = rng_of(seed, '近邻', Y); k = cfg['knn_k']; S = m['S']
    pk = min(1.0, cfg['c'] * cfg['base']['近邻'] * (k + 1) ** (-cfg['a']))
    I = np.repeat(S, k); J = m['knn'][:, :k].ravel()
    if init:
        pr = np.full(len(I), pk)
    else:
        newu = ~prev_m['stand'][I] if prev_m is not None else np.ones(len(I), bool)
        pr = np.where(newu, pk, pk * cfg['turnover']['近邻'])
    keep = rng.random(len(I)) < pr * accept(W, cfg, m, I, J, dist=False)
    born = (Y - rng.geometric(cfg['turnover']['近邻'], keep.sum()) + 1) if init else Y
    out.append(make(T['近邻'], I[keep], J[keep], 0, born, TW['近邻']))
    # 职位辖民（官员 hub）：容量/辖民数 × 接受率^0.5；新任官员或新辖民按全概率，否则 δ
    for tname, arr in sorted(m['hub_mem'].items()):
        rng = rng_of(seed, tname, Y); hh = m['hub_holder'][tname]
        S = m['S']; col = arr[S]
        for fid in sorted(hh):
            o = hh[fid]; subs = S[(col == fid) & (S != o)]
            if len(subs) == 0: continue
            ph = min(1.0, cfg['office_hub_capacity'] / len(subs))
            if init or prev_m is None or prev_m['hub_holder'][tname].get(fid) != o:
                pr = np.full(len(subs), ph)
            else:
                was = prev_m['hub_mem'][tname][subs] == fid
                pr = np.where(was, ph * cfg['turnover']['职位辖民'], ph)
            keep = rng.random(len(subs)) < pr * accept(W, cfg, m, np.full(len(subs), o), subs) ** 0.5
            out.append(make(T[tname], np.full(keep.sum(), o), subs[keep], fid, Y if not init else Y - rng.geometric(cfg['turnover']['职位辖民'], keep.sum()) + 1, TW['职位辖民']))
    # 职位上下级（结构性，必连）
    if m['sup']:
        A = np.array(m['sup'])
        out.append(make(T['职位上下级'], A[:, 0], A[:, 1], A[:, 2], Y, TW['职位上下级']))
    return cat(*out)


def still_in_focus(W, m, R):
    """各记录当年是否仍在其焦点里。"""
    typ, u, v, fid = R['typ'], R['u'], R['v'], R['fid']
    ok = np.zeros(len(u), bool)
    M = m['M']
    for t in GROUP:
        s = typ == T[t]
        if not s.any(): continue
        if t == '市场':
            inu = (M['市场'][u[s]] == fid[s]) | (M['市场2'][u[s]] == fid[s])
            inv = (M['市场'][v[s]] == fid[s]) | (M['市场2'][v[s]] == fid[s])
        else:
            inu = M[t][u[s]] == fid[s]; inv = M[t][v[s]] == fid[s]
        ok[s] = inu & inv
    s = typ == T['近邻']
    if s.any():   # 保持圈：任一方仍在对方最近 12 户内
        K = m['knn']; S = m['S']; N = W.N
        keys = np.unique(np.minimum(np.repeat(S, K.shape[1]), K.ravel()).astype(np.int64) * N + np.maximum(np.repeat(S, K.shape[1]), K.ravel()))
        ok[s] = np.isin(u[s].astype(np.int64) * N + v[s], keys)
    for tname, arr in m['hub_mem'].items():
        s = typ == T[tname]
        if not s.any(): continue
        hh = m['hub_holder'][tname]
        hold = np.array([hh.get(int(f), -1) for f in fid[s]])
        uu, vv = u[s], v[s]
        ok[s] = ((hold == uu) & (arr[vv] == fid[s])) | ((hold == vv) & (arr[uu] == fid[s]))
    s = typ == T['职位上下级']
    if s.any() and m['sup']:
        A = np.array(m['sup'], np.int64)
        keys = (A[:, 0] * W.N + A[:, 1]) * 4096 + A[:, 2]
        ok[s] = np.isin((u[s].astype(np.int64) * W.N + v[s]) * 4096 + fid[s], keys)
    return ok


# ======================================================================= 婚姻
def marriages(W, cfg, years, kinset):
    """每户每代（v8 换代年）以 p_marry 配一户：同信仰内，按距离衰减、同身份（面积三分位、行会）加权；
    跨信仰按 p_cross_faith 折扣；排除自身与亲属距离 ≤2。返回 [(t,u,v)]。"""
    seed = cfg['seed']; out = []
    off = np.array([zlib.crc32(h.encode()) % GEN for h in W.ids])
    for t in years:
        m = W.mem[min(max(t, data.Y0), data.Y1)]
        S = m['S']; S = S[(W.built[S] <= t) & (W.dest[S] > t)]
        turn = S[((t - W.built[S] + off[S]) % GEN == 0) & (W.built[S] < t)]
        rng = rng_of(seed, '婚姻', t)
        F = m['faith']; G = m['M']['行会']
        for u in turn.tolist():
            if rng.random() >= cfg['p_marry']: continue
            d = np.hypot(*(W.xy[S] - W.xy[u]).T)
            w = (1 + d / cfg['marry_d0']) ** (-cfg['dist_gamma'])
            w = w * np.where(F[S] != F[u], cfg['p_cross_faith'], 1.0)
            w = w * np.where(W.size_cls[S] == W.size_cls[u], 1.0, cfg['marry_status_disc'])
            w = w * np.where((G[S] >= 0) & (G[S] == G[u]), cfg['marry_guild_boost'], 1.0)
            w[S == u] = 0
            tot = w.sum()
            if tot <= 0: continue
            v = int(S[np.searchsorted(np.cumsum(w), rng.random() * tot)])
            if (min(u, v), max(u, v)) in kinset: continue
            out.append((t, u, v))
    return out


# ======================================================================= 合并、分层
def strengths(cfg, R, Y):
    w = R['w'].astype(np.float64)
    age = np.clip(Y - R['born'], 0, 10)
    focus = (R['typ'] != T['亲属']) & (R['typ'] != T['婚姻'])
    w = np.where(focus, w * (1 + cfg['age_boost'] * age / 10), w)
    dorm = R['dorm'] >= 0
    w = np.where(dorm, w * 0.5 ** (Y - R['dorm'] + 1), w)
    kin = R['typ'] == T['亲属']; w = np.where(kin, w * 0.5 ** ((Y - R['born']) / 50), w)
    mar = R['typ'] == T['婚姻']; w = np.where(mar, w * 0.5 ** ((Y - R['born']) / GEN), w)
    return w


def union(W, cfg, R, Y):
    k = R['u'].astype(np.int64) * W.N + R['v']
    w = strengths(cfg, R, Y)
    uk, inv = np.unique(k, return_inverse=True)
    s = np.bincount(inv, w)
    return uk, s, inv


def topk_neighbors(W, uk, s, K):
    u = uk // W.N; v = uk % W.N
    a = np.concatenate([u, v]); b = np.concatenate([v, u]); ss = np.concatenate([s, s])
    o = np.lexsort((b, -ss, a)); a, b, ss = a[o], b[o], ss[o]
    start = np.r_[0, np.flatnonzero(np.diff(a)) + 1]
    rank = np.arange(len(a)) - np.repeat(start, np.diff(np.r_[start, len(a)]))
    return a, b, ss, rank


def dunbar(W, cfg, uk, s):
    L = cfg['dunbar_layers']
    tb = ((uk * 2654435761) % 100000) / 1e9
    a, b, ss, rank = topk_neighbors(W, uk, s + tb, 10 ** 9)
    # rank of edge for each endpoint
    ka = np.minimum(a, b) * W.N + np.maximum(a, b)
    r_end = np.full((len(uk), 2), 10 ** 9)
    pos = np.searchsorted(uk, ka)
    first = a < b
    r_end[pos[first], 0] = rank[first]; r_end[pos[~first], 1] = rank[~first]
    worst = r_end.max(1)
    tier = np.digitize(worst, L)          # 0..3，4 = 超出 150
    return tier


def closure_births(W, cfg, R, Y, m, rate):
    uk, s, _ = union(W, cfg, R, Y)
    a, b, ss, rank = topk_neighbors(W, uk, s, cfg['closure_top_k'])
    keep = rank < cfg['closure_top_k']; a, b, ss = a[keep], b[keep], ss[keep]
    start = np.r_[0, np.flatnonzero(np.diff(a)) + 1]; cnt = np.diff(np.r_[start, len(a)])
    rng = rng_of(cfg['seed'], '闭合', Y)
    V, X, Z, WT = [], [], [], []
    K = cfg['closure_top_k']
    iu, ju = np.triu_indices(K, 1)
    for c in range(2, K + 1):
        g = np.flatnonzero(cnt == c)
        if len(g) == 0: continue
        m_ = (iu < c) & (ju < c); I, J = iu[m_], ju[m_]
        st = start[g]
        P1 = st[:, None] + I[None, :]; P2 = st[:, None] + J[None, :]
        hit = rng.random(P1.shape) < rate
        V.append(np.repeat(a[st], hit.sum(1))); X.append(b[P1[hit]]); Z.append(b[P2[hit]]); WT.append(np.minimum(ss[P1[hit]], ss[P2[hit]]))
    if not V: return empty()
    via, x, z, wt = map(np.concatenate, (V, X, Z, WT))
    kk = np.minimum(x, z).astype(np.int64) * W.N + np.maximum(x, z)
    new = ~np.isin(kk, uk)
    ok = new & (rng.random(len(x)) < accept(W, cfg, m, x, z, dist=False))
    r = make(T['三元闭合'], x[ok], z[ok], via[ok], Y, 0)
    r['w'] = (cfg['closure_weight_factor'] * np.minimum(wt[ok], cfg['closure_w_cap'])).astype(np.float32)
    return r


def closure_alive(W, R, uk):
    s = R['typ'] == T['三元闭合']
    if not s.any(): return np.ones(0, bool), s
    via = R['fid'][s].astype(np.int64); u = R['u'][s].astype(np.int64); v = R['v'][s].astype(np.int64)
    k1 = np.minimum(via, u) * W.N + np.maximum(via, u); k2 = np.minimum(via, v) * W.N + np.maximum(via, v)
    return np.isin(k1, uk) & np.isin(k2, uk), s


# ======================================================================= 主循环
class Sim:
    def __init__(self, W, cfg):
        self.W, self.cfg = W, cfg
        import pickle
        key = crc(cfg['seed'], cfg['kin_window'], cfg['kin_max_children'], cfg['p_immigrant'])
        fn = os.path.join(HERE, '.cache', f'lineage_{key}.npy')
        if os.path.exists(fn):
            self.parent = np.load(fn)
        else:
            self.parent = build_lineage(W, cfg); np.save(fn, self.parent)
        self.kin = kin_pairs(W, self.parent, cfg['kin_maxdist'])
        kinset2 = {(int(a), int(b)) for a, b, d in self.kin if d <= 2}
        self.mar = np.array(marriages(W, cfg, range(data.Y0 - 2 * GEN, data.Y1 + 1), kinset2), np.int64).reshape(-1, 3)
        self.log = {}

    def event_records(self, Y, m):
        W, cfg = self.W, self.cfg; st = m['stand']
        K = self.kin
        ok = st[K[:, 0]] & st[K[:, 1]]
        kb = np.maximum(W.built[K[:, 0]], W.built[K[:, 1]])
        r1 = make(T['亲属'], K[ok, 0], K[ok, 1], K[ok, 2], np.minimum(kb[ok], Y), 0)
        r1['w'] = np.array([cfg['kin_weight'][str(d)] for d in K[ok, 2]], np.float32)
        Mr = self.mar
        ok = (Mr[:, 0] <= Y) & (Y - Mr[:, 0] < 2 * GEN) & st[Mr[:, 1]] & st[Mr[:, 2]]
        r2 = make(T['婚姻'], Mr[ok, 1], Mr[ok, 2], Mr[ok, 0], Mr[ok, 0], cfg['tie_weight']['婚姻'])
        return cat(r1, r2)

    def step(self, Y, R, prev_m):
        W, cfg = self.W, self.cfg; m = W.mem[Y]; st = m['stand']
        init = prev_m is None
        if R is None: R = empty()
        if not init:
            # 1 拆户：其关系整体移除
            gone = ~(st[R['u']] & st[R['v']]); R = sel(R, ~gone)
            # 2 事件型（亲属/婚姻）每年按名单重算
            ev = (R['typ'] == T['亲属']) | (R['typ'] == T['婚姻']); R = sel(R, ~ev)
            # 3 焦点型：仍在焦点 → 以 δ 解体；离开焦点 → 休眠，按 p_lost 解体、强度每年减半
            rng = rng_of(cfg['seed'], '存续', Y)
            foc = R['typ'] != T['三元闭合']
            inf = still_in_focus(W, m, R)
            delta = np.zeros(len(R['u']))
            for t in GROUP + ['近邻']: delta[R['typ'] == T[t]] = cfg['turnover'][t]
            for tname in m['hub_mem']: delta[R['typ'] == T[tname]] = cfg['turnover']['职位辖民']
            R['dorm'] = np.where(foc & inf, -1, np.where(foc & (R['dorm'] < 0), Y, R['dorm'])).astype(np.int16)
            die = foc & np.where(inf, rng.random(len(delta)) < delta, rng.random(len(delta)) < cfg['p_lost'])
            die |= (R['typ'] == T['职位上下级']) & ~inf
            R = sel(R, ~die)
        # 4 新生
        newR = gen_year(W, cfg, Y, prev_m, m, R, init=init)
        R = dedupe(cat(R, newR, self.event_records(Y, m)), W.N)
        # 5 三元闭合：存续检查 + 新生
        uk0, _, _ = union(W, cfg, sel(R, R['typ'] != T['三元闭合']), Y)
        alive, s = closure_alive(W, R, uk0)
        rng = rng_of(cfg['seed'], '闭合存续', Y)
        die = np.zeros(len(R['u']), bool)
        die[s] = ~alive | (rng.random(s.sum()) < cfg['closure_decay'])
        R = sel(R, ~die)
        rate = min(1.0, cfg['q_closure'] / cfg['closure_decay']) if init else cfg['q_closure']
        R = dedupe(cat(R, closure_births(W, cfg, R, Y, m, rate)), W.N)
        return R, m

    def output(self, R, Y):
        uk, s, inv = union(self.W, self.cfg, R, Y)
        tier = dunbar(self.W, self.cfg, uk, s)
        keep = tier < 4
        self.latent = (uk, s)
        return uk[keep], s[keep], tier[keep], inv, keep


def sources_of(W, R, uk_out, inv, keep, uk_all):
    """每条输出边的来源标签（类型:焦点 id 名）。"""
    names = W.names
    lab = []
    for t, f in zip(R['typ'].tolist(), R['fid'].tolist()):
        tn = TYPES[t]
        if tn == '亲属': lab.append(f'亲属:{KIN_LABEL[f]}')
        elif tn == '婚姻': lab.append(f'婚姻:AF{f}')
        elif tn == '近邻': lab.append('近邻')
        elif tn == '三元闭合': lab.append(f'三元闭合:{W.ids[f]}')
        elif tn == '职位上下级': lab.append(f'职位上下级:{names["职位"][f]}')
        else: lab.append(f'{tn}:{names[tn][f]}')
    out = collections.defaultdict(list)
    idx_keep = np.full(len(keep), -1); idx_keep[np.flatnonzero(keep)] = np.arange(keep.sum())
    for r, e in enumerate(inv.tolist()):
        j = idx_keep[e]
        if j >= 0: out[j].append(lab[r])
    return out
