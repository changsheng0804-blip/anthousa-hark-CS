"""规则预演 v3 · 户籍册 + 治理分层（编册 = 每年一次向量化；关系 = 共享户籍字段的 O(1) 查询，不再计算）。

每户（family F = 页面房子里的一家，键「房号:搬入年」）每年一条户籍记录：
  登记房屋 reg（账本房屋下标，prep3 底册）· 房主/租户 role · 房东 = 本屋房主 · 区（账本街区）· 街（页面街名）· 坊（≈5 条街，Notitia 比例）
  · 面包簿（随登记房屋：一栋账本房屋一本，屋里按 房主→租户（搬入先后）分口粮）· 教区（按信仰分线）· 行会（行当）· 征工组（= 坊）
  · 兵营关系 · 籍贯 · 缺男丁（14 岁口径）
治理树（每层节点都是一户，皇帝任命的城市长官与两派主教是机构）：
  民政：城市长官 → 区长（每区 1）→ 坊长（每坊 1，vicomagister）→ 房主 → 租户
  教会：尼西亚派主教 / 阿里乌派主教 → 教区 → 教区长老（每 派×坊 1）→ 户
  行会：行会 → 行会头（每 区×行当 1）→ 户；军营：城门兵营 → 兵户
选任（假设 G1）：现任还在、还够格就连任；出缺时在本组够格的户里选「屋里人家最多 → 搬来最早 → 户键」的一户。
  区长、坊长、行会头要：房主 + 家里有成年男人；教区长老要：本派 + 有成年男人（不要求有房）。坊长不与区长同户。
usage: python3 registry.py sample|xero|city|scale [--bench]
"""
import os, sys, json, time, resource, collections, math, pickle, gzip
T0 = time.time()
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(HERE, '..', 'rules_v1'); V0 = os.path.join(HERE, '..', 'rules_v0')
sys.path.insert(0, HERE); sys.path.insert(1, V1); sys.path.insert(2, V0)
import prep  # noqa: E402
import prep3  # noqa: E402
T_IMPORT = time.time() - T0
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
ARIAN, NICENE, PAGAN = 0, 1, 2
FAITHS = ['阿里乌派', '尼西亚派', '还拜旧神']
DNAME = {'d_forum': '广场区', 'd_harbor': '港口区', 'd_xerolophos': '干山区', 'd_byzas': '拜扎斯区', 'd_exokionion': '城墙外新区'}
VICI_PER_FANG = 5          # Notitia Urbis Constantinopolitanae：全城 322 条街（vici）、65 个 vicomagistri ≈ 每 5 条街一个（假设 G2）


def food_cap(Y): return 193202 if Y >= 55 else 173202 if Y >= 46 else 153202      # 账本（chronicle），v2 topdown 同


def hilbert(x, y, n=1024):
    x = x.astype(np.int64).copy(); y = y.astype(np.int64).copy(); d = np.zeros(len(x), np.int64); s = n // 2
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64); ry = ((y & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ ry)
        m = ry == 0; sw = m & (rx == 1)
        x[sw] = s - 1 - x[sw]; y[sw] = s - 1 - y[sw]
        t = x[m].copy(); x[m] = y[m]; y[m] = t
        s //= 2
    return d


def parish_of(faith, Y):
    """教区（节点 id, 名称）。账本：尼西亚派 49 年起阿纳斯塔西娅；阿里乌派 51 年被请出城里教堂、52 起城外木院、64 起城门外砖堂。"""
    if faith == NICENE: return (1, '阿纳斯塔西娅') if Y >= 49 else (0, '城里的尼西亚派教堂')
    if faith == ARIAN:
        if Y < 51: return (2, '城里的阿里乌派教堂')
        if Y == 51: return (-1, '（51 年：被请出教堂，尚无去处）')
        return (4, '城门外砖堂') if Y >= 64 else (3, '城外木院')
    return (-1, '（不入教区）')


PARISH_NAMES = {0: '城里的尼西亚派教堂', 1: '阿纳斯塔西娅', 2: '城里的阿里乌派教堂', 3: '城外木院', 4: '城门外砖堂'}


class Registry:
    def __init__(self, scope, tile=1):
        t0 = time.time()
        self.scope = scope
        base = 'xero' if scope == 'scale' else scope
        D = prep.load(base); M = D['main']; R3 = prep3.load(base)
        self.P = json.load(open(os.path.join(V0, 'rules.json')))
        self.YR0 = D['YR0']; self.NY = M['present'].shape[1]
        self.WL = R3['WL']
        # 城里站着的账本房屋数（配给：每本簿口粮 = 粮食上限 ÷ 全城账本房屋数，假设 T2）；规模测试拼接前算
        self.Hc = {Y: int(((self.WL['built'] <= Y) & (self.WL['dest'] > Y)).sum()) for Y in range(self.YR0, self.YR0 + self.NY)}
        if tile > 1: M, R3 = self._tile(M, R3, tile)
        self.M = M; self.names = R3['names']; self.kids14 = R3['kids14']; self.reg = R3['reg']; self.hostedM = R3['hosted']
        fh = M['fh']; self.fh = fh
        self.NF = len(M['fB'])
        kr = np.empty(self.NF, np.int64); kr[np.argsort(np.array(M['keys'], dtype=object), kind='stable')] = np.arange(self.NF); self.keyrank = kr
        self.flx = M['hlx'][fh]; self.fly = M['hly'][fh]
        self.trades = M['trades']; self.carrier_t = M['trades'].index('运水人') if '运水人' in M['trades'] else -99
        self.origins = M['origins']
        self.barracks = D['barracks']; self.fg = M['fn_names'].index('garrison') if 'garrison' in M['fn_names'] else -99
        self.water = D['water']
        self._static()
        self.t_load = time.time() - t0

    def _tile(self, M, R3, k):
        """规模测试：把干山户籍拼接 k 份（房子/户下标平移，账本房屋下标平移），只用来测编册的时间与内存。"""
        Hn = len(M['hid']); NFb = len(M['fB']); NW = len(self.WL['ids'])
        M2 = dict(M)
        M2['fh'] = np.concatenate([M['fh'] + i * Hn for i in range(k)])
        for key in ('fB', 'fBn', 'fo', 'ff', 'ft', 'fsold', 'fi'): M2[key] = np.tile(M[key], k)
        for key in ('present', 'size', 'men', 'kids', 'deaths', 'boy'): M2[key] = np.tile(M[key], (k, 1))
        for key in ('hlx', 'hly', 'hx', 'hy'): M2[key] = np.concatenate([M[key] + i * 4000 for i in range(k)])
        for key in ('hbuilt', 'hdest', 'hfn'): M2[key] = np.tile(M[key], k)
        M2['hstreet'] = np.concatenate([np.where(M['hstreet'] >= 0, M['hstreet'] + i * len(M['st_names']), -1) for i in range(k)])
        M2['st_names'] = [f'{s}#{i}' for i in range(k) for s in M['st_names']]
        M2['keys'] = [f'{i}/{x}' for i in range(k) for x in M['keys']]
        M2['hid'] = [f'{i}/{x}' for i in range(k) for x in M['hid']]
        R = dict(R3)
        R['kids14'] = np.tile(R3['kids14'], (k, 1)); R['names'] = R3['names'] * k
        R['reg'] = np.concatenate([R3['reg'] + i * NW for i in range(k)]); R['hosted'] = np.tile(R3['hosted'], (k, 1))
        WL = self.WL
        self.WL = dict(ids=[f'{i}/{x}' for i in range(k) for x in WL['ids']], d=np.concatenate([WL['d']] * k), built=np.tile(WL['built'], k),
                       dest=np.tile(WL['dest'], k), px=np.concatenate([WL['px'] + i * 4000 for i in range(k)]), py=np.tile(WL['py'], k))
        return M2, R

    def _static(self):
        """不变的户籍字段：页面房子的区（登记账本房屋街区的众数）、主街、坊。"""
        M = self.M; Hn = len(M['hid'])
        dn = sorted(set(self.WL['d'].tolist())); self.dnames = dn; di = {d: i for i, d in enumerate(dn)}
        WLd = np.array([di[d] for d in self.WL['d']], np.int16); self.WLd = WLd
        y0 = 50 - self.YR0
        R = self.reg[:, y0:]; dd = np.where(R >= 0, WLd[np.maximum(R, 0)], -1)
        hd = np.full(Hn, -1, np.int16)
        for i in range(Hn):
            v = dd[i][dd[i] >= 0]
            if len(v): hd[i] = np.bincount(v).argmax()
            else:
                v = self.reg[i][self.reg[i] >= 0]
                hd[i] = WLd[v[-1]] if len(v) else 0
        self.hdist = hd
        st = M['hstreet'][:, y0:]
        hs = np.full(Hn, -1, np.int64)
        for i in range(Hn):
            v = st[i][st[i] >= 0]
            if len(v): hs[i] = np.bincount(v).argmax()
        known = np.nonzero(hs >= 0)[0]
        if len(known) < Hn:                    # 没街名的房子：取最近有街名房子的街（v0 已知 138 栋无街名）
            un = np.nonzero(hs < 0)[0]
            _, j = cKDTree(np.c_[M['hlx'][known], M['hly'][known]]).query(np.c_[M['hlx'][un], M['hly'][un]])
            hs[un] = hs[known[j]]
        self.hmainst = hs
        # 坊：每个区里按 (区, 街) 的中心点做 Hilbert 排序，每 5 条街一坊
        vic = collections.defaultdict(list)
        for i in range(Hn): vic[(int(hd[i]), int(hs[i]))].append(i)
        keys = list(vic); cx = np.array([np.mean(M['hlx'][vic[k]]) for k in keys]); cy = np.array([np.mean(M['hly'][vic[k]]) for k in keys])
        lo = np.array([cx.min(), cy.min()]); span = max(cx.max() - lo[0], cy.max() - lo[1], 1)
        hv = hilbert((cx - lo[0]) / span * 1023, (cy - lo[1]) / span * 1023)
        fang_of_vic = {}; self.fang_dist = []; self.fang_vici = []
        for d in sorted({k[0] for k in keys}):
            ks = sorted([i for i, k in enumerate(keys) if k[0] == d], key=lambda i: hv[i])
            for c in range(0, len(ks), VICI_PER_FANG):
                fid = len(self.fang_dist); self.fang_dist.append(d); self.fang_vici.append([keys[i][1] for i in ks[c:c + VICI_PER_FANG]])
                for i in ks[c:c + VICI_PER_FANG]: fang_of_vic[keys[i]] = fid
        hf = np.array([fang_of_vic[(int(hd[i]), int(hs[i]))] for i in range(Hn)], np.int32)
        self.hfang = hf; self.NFang = len(self.fang_dist); self.fang_dist = np.array(self.fang_dist, np.int16)
        self.fdist = hd[self.fh]; self.ffang = hf[self.fh]

    # ------------------------------------------------------------------ 编册（一年）
    def year(self, Y, prev=None):
        M = self.M; yi = Y - self.YR0
        S = np.nonzero(M['present'][:, yi])[0]; n = len(S)
        h = self.fh[S]; rh = self.reg[h, yi]; hosted = self.hostedM[h, yi]
        B = M['fB'][S]; kr = self.keyrank[S]; size = M['size'][S, yi].astype(np.int32); men = M['men'][S, yi]
        kids14 = self.kids14[S, yi]; needy = (men == 0) & (kids14 > 0)
        faith = M['ff'][S]; trade = M['ft'][S]; dist = self.fdist[S]; fang = self.ffang[S]
        # ---- 房主 / 租户：同一账本房屋里，非暂挂 → 搬来最早 → 户键 的那一户是房主（假设 R3）
        o = np.lexsort((kr, B, hosted, rh))
        rs = rh[o]; first = np.r_[True, rs[1:] != rs[:-1]] if n else np.zeros(0, bool)
        grp = np.cumsum(first) - 1                              # 组号（按 o 的顺序）
        head = o[first]                                          # 每组房主（本地下标）
        owner_loc = np.empty(n, np.int64); owner_loc[o] = head[grp]
        own = owner_loc == np.arange(n)
        gsize = np.bincount(grp); hh_in_house = np.empty(n, np.int64); hh_in_house[o] = gsize[grp]
        # ---- 面包簿：一栋账本房屋一本，口粮 = 粮食上限 ÷ 全城账本房屋数（T2）；屋里按 房主 → 租户（搬来先后）分（T2c）
        q = food_cap(Y) / self.Hc[Y]
        so = size[o]; cs = np.cumsum(so); gstart = np.r_[0, cs[first.nonzero()[0][1:] - 1]] if n else np.zeros(0)
        before = cs - so - gstart[grp]
        fed_o = np.clip(q - before, 0, so); fed = np.empty(n); fed[o] = fed_o
        # ---- 施舍（教区）：缺男丁（14 岁口径）∧ 本派那年有施舍的地方（规则 11，年份同 v0/v1）
        C = self.P['church']
        if Y >= C['xenon_from']: has_alms = np.ones(n, bool)
        else:
            has_alms = np.zeros(n, bool)
            if Y >= C['nicene_church_from']: has_alms |= faith == NICENE
            if Y < C['arian_out_from'] or Y >= C['arian_church_from']: has_alms |= faith == ARIAN
        alms = needy & has_alms
        par = np.array([parish_of(f, Y)[0] for f in range(3)])[faith]
        # ---- 兵营
        gar = (M['fsold'][S] <= Y) | (M['hfn'][h] == self.fg)
        if self.barracks is not None: gar |= np.hypot(self.barracks[0] - self.flx[S], self.barracks[1] - self.fly[S]) <= self.P['garrison']['radius']
        # ---- 选任：区长、坊长、教区长老、行会头
        ok_civil = own & (men >= 1)
        inc = prev['offices'] if prev else {}
        loc = np.full(self.NF, -1, np.int64); loc[S] = np.arange(n)
        def pick(gkey, cand, ngroups, incumbent):
            out = np.full(ngroups, -1, np.int64)
            c = np.nonzero(cand)[0]
            if len(c):
                oo = c[np.lexsort((kr[c], B[c], -hh_in_house[c], gkey[c]))]
                g = gkey[oo]; f = np.r_[True, g[1:] != g[:-1]]
                out[g[f]] = S[oo[f]]
            if incumbent is not None:
                li = np.where(incumbent >= 0, loc[np.maximum(incumbent, 0)], -1)
                valid = (li >= 0)
                valid[valid] &= cand[li[valid]] & (gkey[li[valid]] == np.nonzero(valid)[0])
                out = np.where(valid, incumbent, out)
            return out
        ND = len(self.dnames)
        dz = pick(dist.astype(np.int64), ok_civil, ND, inc.get('district'))
        isdz = np.zeros(n, bool); l_ = loc[dz[dz >= 0]]; isdz[l_[l_ >= 0]] = True
        fz = pick(fang.astype(np.int64), ok_civil & ~isdz, self.NFang, inc.get('fang'))
        pk = fang.astype(np.int64) * 3 + faith
        ez = pick(pk, (men >= 1) & (faith != PAGAN), self.NFang * 3, inc.get('elder'))
        NT = len(self.trades)
        gk = dist.astype(np.int64) * NT + trade
        gz = pick(gk, ok_civil, ND * NT, inc.get('guild'))
        return dict(Y=Y, S=S, loc=loc, rh=rh, hosted=hosted, owner=S[owner_loc], own=own, hh_in_house=hh_in_house, size=size, men=men,
                    needy=needy, fed=fed, q=q, alms=alms, parish=par, garrison=gar, dist=dist, fang=fang, faith=faith, trade=trade,
                    offices=dict(district=dz, fang=fz, elder=ez, guild=gz))

    def build(self, y0=50, y1=70, keep=True):
        t = time.perf_counter(); prev = None; out = {}
        for Y in range(y0, y1 + 1):
            R = self.year(Y, prev); prev = R
            if keep: out[Y] = R
        return out, time.perf_counter() - t


# ---------------------------------------------------------------------- O(1) 查询
class Query:
    """户籍册编好之后：一户的全部关系 = 读自己的户籍字段 + 读对应节点的现任（数组下标），两户之间 = 比字段。全部 O(1)。"""
    def __init__(self, G, years):
        self.G = G; NF = G.NF
        self.T = {}
        for Y, R in years.items():
            S = R['S']
            full = lambda arr, fill=-1: (lambda a: (a.__setitem__(S, arr), a)[1])(np.full(NF, fill, np.int64))
            self.T[Y] = dict(rh=full(R['rh']).tolist(), owner=full(R['owner']).tolist(), fed=full(np.round(R['fed']).astype(np.int64)).tolist(),
                             size=full(R['size']).tolist(), alms=full(R['alms'].astype(np.int64), 0).tolist(), par=full(R['parish']).tolist(),
                             gar=full(R['garrison'].astype(np.int64), 0).tolist(),
                             dz=R['offices']['district'].tolist(), fz=R['offices']['fang'].tolist(), ez=R['offices']['elder'].tolist(), gz=R['offices']['guild'].tolist())
        self.dist = G.fdist.tolist(); self.fang = G.ffang.tolist(); self.faith = G.M['ff'].tolist(); self.trade = G.M['ft'].tolist()
        self.origin = G.M['fo'].tolist(); self.NT = len(G.trades)
        self.street = G.M['hstreet'][G.fh].tolist()

    def rec(self, F, Y):
        T = self.T[Y]; G = self.G
        if T['rh'][F] < 0: return None
        d = self.dist[F]; fg = self.fang[F]; fa = self.faith[F]; o = T['owner'][F]
        return dict(house=T['rh'][F], landlord=(o if o != F else None), role='房主' if o == F else '租户',
                    district=d, district_head=T['dz'][d], fang=fg, fang_head=T['fz'][fg], street=self.street[F][Y - G.YR0],
                    bread=T['fed'][F], size=T['size'][F], parish=T['par'][F], elder=T['ez'][fg * 3 + fa] if fa != PAGAN else -1,
                    guild=self.trade[F], guild_head=T['gz'][d * self.NT + self.trade[F]], corvee_group=fg, garrison=T['gar'][F],
                    origin=self.origin[F], alms=T['alms'][F])

    def rel(self, F, Gg, Y):
        """两户之间的全部政治经济关系：共享哪些户籍字段 / 谁是谁的上级。"""
        T = self.T[Y]; out = []
        if T['rh'][F] < 0 or T['rh'][Gg] < 0: return out
        if T['rh'][F] == T['rh'][Gg]: out.append('同屋')
        if T['owner'][Gg] == F and F != Gg: out.append('房东')
        if T['owner'][F] == Gg and F != Gg: out.append('租户之东')
        if self.fang[F] == self.fang[Gg]: out.append('同坊/同征工组')
        if T['fz'][self.fang[Gg]] == F: out.append('坊长')
        if T['dz'][self.dist[Gg]] == F: out.append('区长')
        if self.faith[F] == self.faith[Gg] and T['par'][F] >= 0 and T['par'][F] == T['par'][Gg]: out.append('同教区')
        if self.trade[F] == self.trade[Gg]: out.append('同行会')
        if self.origin[F] == self.origin[Gg]: out.append('同乡')
        if T['rh'][F] >= 0 and T['owner'][F] == T['owner'][Gg]: out.append('同一面包簿')
        return out


def registry_bytes(G, years):
    """户籍册新增的存储：底册（页面房子→账本房屋，按区间）、每屋房主（按区间）、各层现任（按区间）、每户每年口粮状态（2 bit）。"""
    raw = bytearray()
    def iv_rows(mat):        # mat: 行 = 实体，列 = 年 → 区间 (实体, 值, 起, 止)
        rows = 0
        for i in range(mat.shape[0]):
            v = mat[i]; s = 0
            for j in range(1, len(v) + 1):
                if j == len(v) or v[j] != v[s]:
                    if v[s] >= 0: raw.extend(int(i).to_bytes(3, 'little') + int(v[s]).to_bytes(3, 'little') + bytes([s, j - 1])); rows += 1
                    s = j
        return rows
    Ys = sorted(years); yi0 = Ys[0] - G.YR0; yi1 = Ys[-1] - G.YR0 + 1
    used = np.unique(np.concatenate([years[Y]['S'] for Y in Ys]))
    hs = np.unique(G.fh[used])
    n_reg = iv_rows(G.reg[hs, yi0:yi1])
    houses = np.unique(np.concatenate([years[Y]['rh'] for Y in Ys])); hidx = {h: i for i, h in enumerate(houses.tolist())}
    om = np.full((len(houses), len(Ys)), -1, np.int64)
    for j, Y in enumerate(Ys):
        R = years[Y]; f = R['own']; om[[hidx[h] for h in R['rh'][f].tolist()], j] = R['S'][f]
    n_own = iv_rows(om)
    n_off = 0
    for k in ('district', 'fang', 'elder', 'guild'):
        mat = np.stack([years[Y]['offices'][k] for Y in Ys], 1); n_off += iv_rows(mat)
    # 静态：每栋页面房子的 区(1B)+坊(2B)；每户的 籍贯/信仰/行当/搬入年 v1 已有
    raw.extend(G.hdist[hs].astype(np.int8).tobytes() + G.hfang[hs].astype(np.int16).tobytes())
    st = np.zeros((len(used), len(Ys)), np.uint8)
    loc = {F: i for i, F in enumerate(used.tolist())}
    for j, Y in enumerate(Ys):
        R = years[Y]; s = np.where(R['fed'] >= R['size'] - 1e-9, 3, np.where(R['fed'] > 0, 2, 1))
        st[[loc[F] for F in R['S'].tolist()], j] = s
    packed = np.packbits(np.unpackbits(st[:, :, None], axis=2)[:, :, -2:].reshape(len(used), -1), axis=1)
    raw.extend(packed.tobytes())
    gz = len(gzip.compress(bytes(raw), 9))
    return dict(families=len(used), reg_intervals=n_reg, owner_intervals=n_own, office_intervals=n_off, raw=len(raw), gzip=gz,
                per_family_raw=round(len(raw) / len(used), 2), per_family_gzip=round(gz / len(used), 2))


def summarize(G, years):
    out = {}
    for Y in (50, 51, 54, 55, 57, 60, 62, 65, 70):
        if Y not in years: continue
        R = years[Y]; S = R['S']; n = len(S); own = R['own']
        hh = np.bincount(R['hh_in_house'][own]) if own.any() else np.zeros(1)
        fully = int((R['fed'] >= R['size'] - 1e-9).sum()); none = int((R['fed'] <= 0).sum())
        dz = R['offices']['district']; fz = R['offices']['fang']; ez = R['offices']['elder']; gz = R['offices']['guild']
        out[Y] = dict(households=n, people=int(R['size'].sum()), ledger_houses_registered=int(own.sum()),
                      by_district={DNAME.get(G.dnames[d], G.dnames[d]): dict(households=int((R['dist'] == d).sum()), houses=int((own & (R['dist'] == d)).sum())) for d in np.unique(R['dist']).tolist()},
                      households_per_house=dict(mean=round(n / max(int(own.sum()), 1), 2), max=int(R['hh_in_house'].max()) if n else 0, hist=dict(enumerate(hh.tolist()))),
                      owners=int(own.sum()), tenants=int((~own).sum()), hosted=int(R['hosted'].sum()),
                      bread=dict(books=int(own.sum()), portions_per_book=round(R['q'], 2), portions_total=round(R['q'] * int(own.sum())),
                                 people_fed=int(np.round(R['fed']).sum()), households_full=fully, households_partial=n - fully - none, households_none=none),
                      needy14=int(R['needy'].sum()), needy14_with_alms=int(R['alms'].sum()),
                      parish={PARISH_NAMES.get(p, '无'): int((R['parish'] == p).sum()) for p in np.unique(R['parish']).tolist()},
                      garrison=int(R['garrison'].sum()),
                      offices=dict(district_heads=int((dz >= 0).sum()), fang_heads=int((fz >= 0).sum()), fang_total=G.NFang,
                                   elders=int((ez >= 0).sum()), guild_heads=int((gz >= 0).sum())))
    # 连任：各层现任逐年换人的次数
    Ys = sorted(years); ch = collections.Counter()
    for a, b in zip(Ys, Ys[1:]):
        for k in ('district', 'fang', 'elder', 'guild'):
            x, y = years[a]['offices'][k], years[b]['offices'][k]
            ch[k] += int(((x != y) & (x >= 0) & (y >= 0)).sum())
    return out, dict(ch)


def bench_query(G, years, nq=20000):
    Qa = time.perf_counter(); Q = Query(G, years); t_idx = time.perf_counter() - Qa
    rng = np.random.default_rng(3); Ys = sorted(years)
    picks = []
    for _ in range(nq):
        Y = Ys[rng.integers(len(Ys))]; S = years[Y]['S']; picks.append((int(S[rng.integers(len(S))]), int(S[rng.integers(len(S))]), Y))
    a = time.perf_counter()
    for F, _, Y in picks: Q.rec(F, Y)
    t_rec = (time.perf_counter() - a) / nq
    a = time.perf_counter()
    for F, Gg, Y in picks: Q.rel(F, Gg, Y)
    t_rel = (time.perf_counter() - a) / nq
    # 与编册结果核对：房东 / 坊长 / 区长 / 口粮
    bad = 0
    for F, _, Y in picks[:3000]:
        r = Q.rec(F, Y); R = years[Y]; i = R['loc'][F]
        exp_ll = int(R['owner'][i]) if not R['own'][i] else None
        bad += (r['landlord'] != exp_ll) or (r['fang_head'] != int(R['offices']['fang'][R['fang'][i]])) or (r['bread'] != int(round(R['fed'][i])))
    return dict(index_build_s=round(t_idx, 3), rec_us=round(t_rec * 1e6, 2), rel_us=round(t_rel * 1e6, 2), verify_checked=3000, verify_mismatch=bad)


def main(scope, bench=False):
    t0 = time.time()
    tile = 7 if scope == 'scale' else 1
    G = Registry(scope, tile)
    years, t_build = G.build(50, 70)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    summ, changes = summarize(G, years)
    hy = sum(len(R['S']) for R in years.values())
    out = dict(scope=scope, tile=tile, household_years=hy, families=G.NF, fang=G.NFang, districts=[DNAME.get(d, d) for d in G.dnames],
               seconds=dict(python_import=round(T_IMPORT, 3), load=round(G.t_load, 3), build_21y=round(t_build, 3), per_year_ms=round(t_build / 21 * 1000, 2)),
               peak_rss_mb_after_build=round(rss, 1), office_changes_50_70=changes, years=summ)
    if scope != 'scale':
        out['bytes'] = registry_bytes(G, years)
    if bench or scope != 'scale':
        out['query'] = bench_query(G, years)
    out['peak_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    out['seconds']['total_in_process'] = round(time.time() - t0, 3)
    json.dump(out, open(os.path.join(HERE, 'out', f'registry_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in out if k != 'years'}, ensure_ascii=False))
    print(json.dumps(summ.get(60), ensure_ascii=False))
    return G, years


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(a[0], '--bench' in sys.argv)
