"""规则预演 v1 · 引擎：不生成边，直接找交叉点。

v0：每年把 13 条规则的弱关系边全部生成成 Python 元组（干山 94 万条），再在边上找交叉模式。
v1：交叉点 = 模式；每个模式 = 一个「承载关系」 ∧ 几个户属性条件。做法：
  1. 户属性来自 prep 的状态矩阵（一次性向量化算好，每年只是切一列），不再逐户跑 household_state。
  2. 先用最便宜的户属性条件把候选户筛到很少（有丧/缺男丁的租户、两户都缺男丁、过了容量的同行……），
     再只在候选户周围用 cKDTree 做 k 近邻（分组 = 坐标平移到互不相交的「组平面」，一棵树做完所有组的组内近邻）。
  3. 同乡链：每户可能投奔的同乡候选（同籍贯、早 1–8 年来、300px 内，按距离排好）一次性预计算成 CSR，
     每年只要找「第一个今年还在住的候选」——这是增量的：只有候选里有人搬走/死绝才会变。
  4. 房东 / 恩主 / 债这三条「容量分配」本质是顺序贪心，保留 Python 循环但只跑在租户/门客/借债户上（每年几百户），
     房东分配在「在住户集合与街没变」的年份直接沿用上一年（增量）。
  5. 运水人、信仰同堂、面包同排、同行同街四类「背景」边不进模式，只在给交叉点打分（compat 模式，要与 v0 等价）
     或现算某一户自我网时按需查。
交叉点按年维护：每个 (模式, 甲, 乙) 记下命中的年份，最后合成起止年区间。
"""
import os, sys, math, collections, json, time
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prep  # noqa: E402

ARIAN, NICENE, PAGAN = 0, 1, 2
INF = float('inf')

PAIR_PATTERNS = ['同乡异信', '同水异粮', '火后同行对头', '正统房东·阿里乌派租户', '债主欠债同街', '恩主门客异信',
                 '房东兼债主/恩主', '同井施舍分线', '学徒拜异派师傅']
HOUSE_PATTERNS = ['运水人摊上公家的事', '儿子当兵·家里无男丁无施舍']


def knn_group(x, y, g, k, q=None, bound=None, extra=3, tk=None, tree=None):
    """组内 k 近邻（不含自己）：把每组平移到互不相交的平面上，一棵 cKDTree 做完所有组。
    q：只查这些下标（None = 全部）。返回 (nq, k) 的邻居下标（-1 = 没有），按 (距离, 下标) 排序——与 v0 的稳定排序同序。
    距离用原坐标重算，不受平移的浮点误差影响。tk：同距离时的先后（v0 用 Grid 遍历顺序的规则传网格序，默认下标=房序）。"""
    n = len(x)
    q = np.arange(n) if q is None else np.asarray(q)
    out = np.full((len(q), k), -1, np.int64)
    if n == 0 or len(q) == 0: return out
    OFF = 1e5
    pts = np.c_[x + g * OFF, y]
    t = tree if tree is not None else cKDTree(pts)
    kk = min(k + 1 + extra, n)
    d, i = t.query(pts[q], k=kk, distance_upper_bound=(bound * 1.0001 + 1e-6) if bound else INF)
    if kk == 1: i = i[:, None]
    ok = (i < n)
    ic = np.where(ok, i, 0)
    ok &= (ic != q[:, None]) & (g[ic] == g[q][:, None])
    dd = np.hypot(x[ic] - x[q][:, None], y[ic] - y[q][:, None])
    if bound: ok &= dd <= bound
    dd = np.where(ok, dd, INF)
    # 每行按 (距离, 下标) 排序。先只按距离排；只有前 k+1 名里出现完全相等的距离的行才再按下标细排（极少）
    idx = np.argsort(dd, axis=1, kind='stable')
    dd2 = np.take_along_axis(dd, idx, 1); ic2 = np.take_along_axis(ic, idx, 1); ok2 = np.take_along_axis(ok, idx, 1)
    m = min(k + 1, dd2.shape[1])
    tie = ((dd2[:, 1:m] == dd2[:, :m - 1]) & (dd2[:, 1:m] < INF)).any(1) if m > 1 else np.zeros(len(q), bool)
    for r in np.nonzero(tie)[0]:
        o = np.lexsort(((tk[ic2[r]] if tk is not None else ic2[r]), dd2[r])); dd2[r] = dd2[r][o]; ic2[r] = ic2[r][o]; ok2[r] = ok2[r][o]
    ic3 = ic2[:, :k]; ok3 = ok2[:, :k]
    out[:, :ic3.shape[1]] = np.where(ok3, ic3, -1)
    return out


class Engine:
    def __init__(self, scope, P, mode='compat'):
        self.scope = scope; self.P = P; self.mode = mode
        self.stats = collections.Counter(); self.tm = collections.Counter()
        D = prep.load(scope)
        self.D = D; M = D['main']; self.M = M
        self.YR0 = D['YR0']
        fh = M['fh']
        self.fx = M['hx'][fh]; self.fy = M['hy'][fh]; self.flx = M['hlx'][fh]; self.fly = M['hly'][fh]
        self.fdest = M['hdest'][fh]; self.ffn = M['hfn'][fh]
        self.fn_names = M['fn_names']
        self.owner = (M['fi'] == 0) & (M['fB'] <= P['bread']['owner_before'])
        self.keys = M['keys']
        kr = np.empty(len(self.keys), np.int64); kr[np.argsort(np.array(self.keys, dtype=object), kind='stable')] = np.arange(len(self.keys))
        self.keyrank = kr                      # v0 的若干分配按户键字符串排序
        self.tr = {n: i for i, n in enumerate(M['trades'])}
        self.carrier_t = self.tr.get('运水人', -99)
        self.lender_t = np.array([self.tr[t] for t in P['debt']['lender_trades'] if t in self.tr])
        self.local_t = M['origins'].index('本城生') if '本城生' in M['origins'] else -99
        self.water = D['water']; self.ovens = D['ovens']
        self.wx = np.array([w['x'] for w in self.water]); self.wy = np.array([w['y'] for w in self.water])
        self.wb = np.array([w['built'] for w in self.water]); self.wwell = np.array([w['kind'] == 'well' for w in self.water])
        self.ox = np.array([o['x'] for o in self.ovens]); self.oy = np.array([o['y'] for o in self.ovens]); self.ob = np.array([o['built'] for o in self.ovens])
        self.hard_years, self.rates = self._hard_years()
        self._chain_csr()
        self._ll_prev = None

    # ------------------------------------------------------------ 一次性预计算
    def _hard_years(self):
        F = self.D.get('full', self.M)
        lo, hi = self.P['debt']['base_years']; rate = {}
        for Y in range(lo, hi + 1):
            yi = Y - self.YR0; pr = F['present'][:, yi]
            dead = F['deaths'][pr, yi].sum(); ppl = F['size'][pr, yi].sum() + dead
            rate[Y] = dead / max(ppl, 1)
        v = list(rate.values()); m = sum(v) / len(v); sd = (sum((x - m) ** 2 for x in v) / len(v)) ** .5
        return sorted(Y for Y, r in rate.items() if r > m + self.P['debt']['z'] * sd), {Y: round(float(r), 4) for Y, r in rate.items()}

    def _chain_csr(self):
        """同乡带同乡：每户可能投奔的同乡候选，按 (距离, 房序) 排好，CSR 存。一次算完，逐年只查谁还在。"""
        M = self.M; R = self.P['chain']['radius']; gap = self.P['chain']['max_gap']
        cp = os.path.join(prep.CACHE, f'rules_v1_{self.scope}_chain_{R}_{gap}.npz')   # 不变属性：一次算好缓存（prep 的一部分）
        if os.path.exists(cp):
            z = np.load(cp); self.ch_s, self.ch_t = z['s'], z['t']; self.stats['chain_candidates'] = len(self.ch_s); return
        n = len(M['fB']); g = M['fo'].astype(float)
        # 坐标第三维放搬入年：同籍贯（平移分平面）、300px 内、早 1–8 年，分块球查询，边查边筛，内存有界
        t = cKDTree(np.c_[self.fx + g * 1e5, self.fy])
        AA, BB, DD = [], [], []
        src = np.nonzero(M['fo'] != self.local_t)[0]
        for c0 in range(0, len(src), 4000):
            q = src[c0:c0 + 4000]
            res = t.query_ball_point(np.c_[self.fx[q] + g[q] * 1e5, self.fy[q]], R * 1.0001 + 1e-6)
            ln = np.fromiter((len(r) for r in res), np.int64, len(res))
            a = np.repeat(q, ln); b = np.fromiter((j for r in res for j in r), np.int64, int(ln.sum()))
            dd = np.hypot(self.fx[a] - self.fx[b], self.fy[a] - self.fy[b]); dB = M['fB'][a] - M['fB'][b]
            ok = (M['fo'][a] == M['fo'][b]) & (dd <= R) & (dB > 0) & (dB <= gap)
            AA.append(a[ok]); BB.append(b[ok]); DD.append(dd[ok])
        a = np.concatenate(AA); b = np.concatenate(BB); dd = np.concatenate(DD)
        o = np.lexsort((b, np.floor(self.fy[b] / 150), np.floor(self.fx[b] / 150), dd, a))   # 同距离按 v0 Grid(150) 遍历序
        self.ch_s, self.ch_t = a[o], b[o]
        np.savez(cp, s=self.ch_s, t=self.ch_t)
        self.stats['chain_candidates'] = len(a)

    # ------------------------------------------------------------ 一年
    def year(self, Y, need_pairtypes=True):
        M = self.M; P = self.P; yi = Y - self.YR0
        self._t = time.perf_counter(); self._tn = '户状态切片'
        S = np.nonzero(M['present'][:, yi])[0]          # 本年在住户（全局下标，房序）
        n = len(S)
        loc = np.full(len(M['fB']), -1, np.int64); loc[S] = np.arange(n)
        x, y, lx, ly = self.fx[S], self.fy[S], self.flx[S], self.fly[S]
        st = M['hstreet'][M['fh'][S], yi]; trade = M['ft'][S]; faith = M['ff'][S]; B = M['fB'][S]
        own = self.owner[S]; size = M['size'][S, yi]; men = M['men'][S, yi]; kids = M['kids'][S, yi]
        dth = M['deaths'][S, yi] > 0; needy = (men == 0) & (kids > 0); fnn = self.ffn[S]
        ref = (B >= 48) & (B <= 50)
        tk = np.empty(n, np.int64); tk[np.lexsort((np.arange(n), np.floor(y / 120), np.floor(x / 120)))] = np.arange(n)  # v0 Grid(120) 遍历序
        Yd = dict(Y=Y, S=S, tk=tk, loc=loc, n=n, x=x, y=y, st=st, trade=trade, faith=faith, own=own, needy=needy, dth=dth, B=B)

        self._tick('喝哪口水（井')
        # ---- 喝哪口水（井 140px，否则蓄水池 420px）
        Wp = P['water']
        wsrc = np.full(n, -1); wd = np.full(n, INF)
        wm = np.nonzero(self.wwell & (self.wb <= Y))[0]
        if len(wm):
            kk = min(3, len(wm))
            d, i = cKDTree(np.c_[self.wx[wm], self.wy[wm]]).query(np.c_[x, y], k=kk, distance_upper_bound=Wp['well_reach'] * 1.0001)
            i = np.asarray(i).reshape(n, -1); ok = i < len(wm); wi = wm[np.where(ok, i, 0)]
            dd = np.where(ok, np.hypot(self.wx[wi] - x[:, None], self.wy[wi] - y[:, None]), INF)
            dd = np.where(dd <= Wp['well_reach'], dd, INF)
            # 同距离按 v0 Grid(140) 遍历序：(格 x, 格 y, 井序)
            gr = np.floor(self.wx[wi] / 140) * 1e9 + np.floor(self.wy[wi] / 140) * 1e4 + wi
            j = np.lexsort((gr, dd), axis=1)[:, 0]
            pick = wi[np.arange(n), j]; pd_ = dd[np.arange(n), j]; ok = pd_ < INF
            wsrc[ok] = pick[ok]; wd[ok] = pd_[ok]
        cm = np.nonzero(~self.wwell & (self.wb <= Y))[0]
        if len(cm):
            rest = np.nonzero(wsrc < 0)[0]
            dc = np.hypot(self.wx[cm][None, :] - lx[rest, None], self.wy[cm][None, :] - ly[rest, None])
            j = np.argmin(dc, 1); dj = dc[np.arange(len(rest)), j]; ok = dj <= Wp['cistern_reach']
            wsrc[rest[ok]] = cm[j[ok]]; wd[rest[ok]] = dj[ok]
        Yd['wsrc'] = wsrc; Yd['wd'] = wd

        self._tick('同一口水：组内最近')
        # ---- 同一口水：组内最近 4 户（交叉模式要用它，且要反向：别人的 4 近邻里有我）
        nbg = self._water_knn_incremental(Yd, wsrc, Wp['k'])        # (n, k) 全局下标
        a = np.repeat(np.arange(n), Wp['k']); b = loc[np.maximum(nbg.ravel(), 0)]
        ok = (nbg.ravel() >= 0); a, b = a[ok], b[ok]
        lo_, hi_ = np.minimum(a, b), np.maximum(a, b)
        wcode = np.unique(lo_ * n + hi_)
        wa, wb_ = wcode // n, wcode % n
        Yd['wcode'] = wcode
        self.stats['water_pairs_transient'] += len(wcode)

        self._tick('施舍从哪来')
        # ---- 施舍从哪来
        C = P['church']
        alms_none = np.ones(n, bool); alms_src = np.full(n, '', object)
        if Y >= C['xenon_from']: src = np.full(n, '@寡妇孤儿之家', object)
        else:
            src = np.full(n, '', object)
            if Y >= C['nicene_church_from']: src[faith == NICENE] = '@阿纳斯塔西娅的执事'
            if Y < C['arian_out_from']: src[faith == ARIAN] = '@城里的阿里乌派教堂'
            elif Y >= C['arian_church_from']: src[faith == ARIAN] = '@城门外砖堂'
        alms_src[needy] = src[needy]; alms_none = alms_src == ''

        hits = []   # (模式, 全局甲, 全局乙)
        def add(name, A, Bb):   # 命中留成 numpy 数组（全局户下标），不逐条造 Python 元组
            if len(A): hits.append((PAIR_PATTERNS.index(name), S[np.asarray(A)], S[np.asarray(Bb)]))

        # 同水异粮：一家有房一家租，租的那家当年有丧或缺男丁（先按户属性筛，再看是不是同一口水的近邻）
        m = own[wa] != own[wb_]
        t = np.where(own[wa], wb_, wa)
        m &= dth[t] | needy[t]
        add('同水异粮', wa[m], wb_[m])
        # 同井施舍分线：两家都缺男丁，一家领得到本派施舍、一家领不到
        m = needy[wa] & needy[wb_] & (alms_none[wa] != alms_none[wb_])
        add('同井施舍分线', wa[m], wb_[m])

        self._tick('同乡链：第一个今年还在住的候选（CSR，增量）')
        # ---- 同乡链：第一个今年还在住的候选（CSR，增量）
        cs, ct = self.ch_s, self.ch_t
        ok = M['present'][cs, yi] & M['present'][ct, yi]
        cs2, ct2 = cs[ok], ct[ok]
        first = np.r_[True, cs2[1:] != cs2[:-1]] if len(cs2) else np.zeros(0, bool)
        par_s, par_t = loc[cs2[first]], loc[ct2[first]]
        parent = np.full(n, -1); parent[par_s] = par_t
        Yd['parent'] = parent
        if Y >= 51:
            m = ((faith[par_t] == ARIAN) & (faith[par_s] == NICENE)) | ((faith[par_t] == NICENE) & (faith[par_s] == ARIAN))
            add('同乡异信', par_t[m], par_s[m])

        self._tick('同行对头：同街同行多过街区容量，最近的同行（80px')
        # ---- 同行对头：同街同行多过街区容量，最近的同行（80px 内）
        Rp = P['rival']
        hs = st >= 0
        gkey = np.where(hs, st.astype(np.int64) * 1000 + trade, -1)
        u, inv, cnt = np.unique(gkey, return_inverse=True, return_counts=True)
        gc = cnt[inv]
        capv = np.array([Rp['cap'].get(f, Rp['cap']['default']) for f in self.fn_names])[fnn]
        q = np.nonzero(hs & (gc > capv))[0]
        # （试过按 (街,行当) 组缓存做增量：85% 的组可沿用，但 Python 逐组比签名的开销抵掉了收益，故保留整年向量化一次查询）
        rival = np.full(n, -1)
        if len(q):
            ii = np.nonzero(hs)[0]
            nb = knn_group(x[ii], y[ii], gkey[ii].astype(float), 1, q=np.searchsorted(ii, q), bound=Rp['dist'], tk=tk[ii])
            rival[q] = np.where(nb[:, 0] >= 0, ii[np.maximum(nb[:, 0], 0)], -1)
        rq = np.nonzero(rival >= 0)[0]
        ra, rb = rq, rival[rq]
        rc = np.unique(np.minimum(ra, rb) * n + np.maximum(ra, rb))
        ra, rb = rc // n, rc % n
        m = ref[ra] | ref[rb]
        add('火后同行对头', ra[m], rb[m])
        Yd['rival'] = rival

        self._tick('房东（增量：在住户集合与街没变就沿用）')
        # ---- 房东（增量：在住户集合与街没变就沿用）
        landlord = self._landlord(Yd)
        T = np.nonzero(landlord >= 0)[0]; L = landlord[T]
        if Y >= 51:
            m = (faith[L] == NICENE) & (faith[T] == ARIAN)
            add('正统房东·阿里乌派租户', L[m], T[m])

        self._tick('恩主')
        # ---- 恩主
        patron = self._patron(Yd, size, dth, fnn, B, Y)
        Cc = np.nonzero(patron >= 0)[0]; Pp = patron[Cc]
        m = faith[Pp] != faith[Cc]
        add('恩主门客异信', Pp[m], Cc[m])

        self._tick('债（灾年借粮，债拖')
        # ---- 债（灾年借粮，债拖 4 年）
        debts = []
        for hy in self.hard_years:
            if Y - P['debt']['years'] < hy <= Y:
                for lg, bg in self._debt_of(hy):
                    if loc[lg] >= 0 and loc[bg] >= 0: debts.append((loc[lg], loc[bg]))
        debts = list(dict.fromkeys(debts))
        Yd['debts'] = debts
        for lo2, bo2 in debts:
            if st[lo2] >= 0 and st[lo2] == st[bo2]: add('债主欠债同街', [lo2], [bo2])
        dset = set(debts)
        # 房东兼债主/恩主
        m = (patron[T] == L) | np.array([(l, t) in dset for l, t in zip(L, T)], bool).reshape(-1)
        add('房东兼债主/恩主', L[m], T[m])

        self._tick('学徒：没有成年男人、有')
        # ---- 学徒：没有成年男人、有 12–15 岁男孩的人家，跟 300px 内最近的同行师傅（否则最近的师傅）
        Ap = P['apprentice']
        app = np.full(n, -1)
        q = np.nonzero((men == 0) & M['boy'][S, yi])[0]
        if len(q):
            mm = np.nonzero(men > 0)[0]
            if len(mm):
                # 师傅集合 = 有成年男人的在住户；先找同行（行当平移到不同平面），找不到再找最近的
                tm = cKDTree(np.c_[x[mm] + trade[mm] * 1e5, y[mm]])
                d1, i1 = tm.query(np.c_[x[q] + trade[q] * 1e5, y[q]], k=min(4, len(mm)), distance_upper_bound=Ap['radius'] * 1.0001)
                ta = cKDTree(np.c_[x[mm], y[mm]])
                d2, i2 = ta.query(np.c_[x[q], y[q]], k=min(4, len(mm)), distance_upper_bound=Ap['radius'] * 1.0001)
                i1 = np.asarray(i1).reshape(len(q), -1); i2 = np.asarray(i2).reshape(len(q), -1)
                for r_, s_ in enumerate(q):
                    best = self._nearest(i1[r_], mm, x[s_], y[s_], x, y, Ap['radius'], same=trade[s_], trade=trade, tk=tk)
                    if best < 0: best = self._nearest(i2[r_], mm, x[s_], y[s_], x, y, Ap['radius'], tk=tk)
                    app[s_] = best
        Aq = np.nonzero(app >= 0)[0]; Am = app[Aq]
        m = faith[Am] != faith[Aq]
        add('学徒拜异派师傅', Am[m], Aq[m])
        Yd['app'] = app; Yd['landlord'] = landlord; Yd['patron'] = patron

        self._tick('单户')
        # ---- 单户 × 机构
        node = self._nodes(Yd, alms_src, men, dth, needy, lx, ly)
        Yd['node'] = node
        hits_h = []
        isc = trade == self.carrier_t
        sold = M['fsold'][S] <= Y
        for s_ in np.nonzero(isc | sold)[0]:
            nd = node[s_]
            if not nd: continue
            kinds = {k for k, _ in nd}
            if isc[s_] and (('evicted' in kinds or 'corvee' in kinds) or ('levy' in kinds and (needy[s_] or dth[s_]))):
                hits_h.append(('运水人摊上公家的事', int(S[s_]), nd[0][1]))
            if sold[s_] and needy[s_] and 'alms' not in kinds:
                hits_h.append(('儿子当兵·家里无男丁无施舍', int(S[s_]), nd[0][1]))
        self._tick('end')
        Yd['hits'] = hits; Yd['hits_h'] = hits_h
        return Yd

    # ------------------------------------------------------------ 增量：组内近邻只重算受影响的户
    def _water_knn_incremental(self, Yd, wsrc, k):
        """同一口水的组内 k 近邻，逐年增量维护（结果与每年从头算完全相同）。
        受影响的户 = 新来的/换了水源的户 ∪ 上一年近邻里有人走了的户 ∪ 新来户落在其第 k 近距离以内的老户 ∪ 不满 k 个邻居而组里来了新户的老户。
        其余户的近邻集合（含同距离的先后）不可能变，直接沿用。"""
        S, n, x, y = Yd['S'], Yd['n'], Yd['x'], Yd['y']; NF = len(self.keys)
        g_now = np.full(NF, -1); g_now[S] = wsrc
        st = getattr(self, '_wk', None)
        hasw = np.nonzero(wsrc >= 0)[0]
        gw = wsrc[hasw].astype(float)
        tree = cKDTree(np.c_[x[hasw] + gw * 1e5, y[hasw]]) if len(hasw) else None
        if st is None:
            aff = hasw
            nbrs = np.full((NF, k), -1, np.int64); kth = np.full(NF, INF)
        else:
            g_prev, nbrs, kth = st
            changed = g_now != g_prev
            added = changed & (g_now >= 0); removed = changed & (g_prev >= 0)
            stable = (g_now >= 0) & ~changed
            rm = np.r_[removed, False]                                   # -1 → 末位 False
            hit = stable & rm[nbrs].any(1)
            grp_added = np.zeros(int(wsrc.max()) + 2 if len(wsrc) else 1, bool)
            ga = g_now[added]; grp_added[ga] = True
            hit |= stable & ~np.isfinite(kth) & grp_added[np.maximum(g_now, 0)] & (g_now >= 0)
            A = np.nonzero(added)[0]
            if len(A) and tree is not None:
                fin = stable & np.isfinite(kth)
                gmax = np.zeros(len(grp_added)); np.maximum.at(gmax, g_now[fin], kth[fin])
                la = Yd['loc'][A]
                for a_, l_ in zip(A, la):
                    r = gmax[g_now[a_]]
                    if r <= 0: continue
                    for j in tree.query_ball_point([x[l_] + g_now[a_] * 1e5, y[l_]], r * 1.0001 + 1e-6):
                        p = S[hasw[j]]
                        if stable[p] and math.hypot(self.fx[p] - self.fx[a_], self.fy[p] - self.fy[a_]) <= kth[p]: hit[p] = True
            aff = Yd['loc'][np.nonzero(added | hit)[0]]
            nbrs = nbrs.copy(); kth = kth.copy()
            nbrs[changed] = -1; kth[changed] = INF
        self.stats['water_knn_requeried'] += len(aff); self.stats['water_knn_total'] += len(hasw)
        if len(aff):
            qi = np.searchsorted(hasw, aff)
            nb = knn_group(x[hasw], y[hasw], gw, k, q=qi, tree=tree)
            ng = np.where(nb >= 0, S[hasw[np.maximum(nb, 0)]], -1)
            nbrs[S[aff]] = ng
            last = ng[:, -1]
            kth[S[aff]] = np.where(last >= 0, np.hypot(self.fx[np.maximum(last, 0)] - self.fx[S[aff]], self.fy[np.maximum(last, 0)] - self.fy[S[aff]]), INF)
        self._wk = (g_now, nbrs, kth)
        return nbrs[S]

    def _tick(self, name):
        t = time.perf_counter(); self.tm[self._tn] += t - self._t; self._t = t; self._tn = name

    @staticmethod
    def _nearest(cand, mm, sx, sy, x, y, R, same=None, trade=None, tk=None):
        best = -1; bd = INF
        for c in cand:
            if c >= len(mm): continue
            j = mm[c]
            if same is not None and trade[j] != same: continue
            d = math.hypot(x[j] - sx, y[j] - sy)
            if d <= R and (d < bd or (d == bd and tk[j] < tk[best])): bd, best = d, j
        return best

    # ------------------------------------------------------------ 容量分配（顺序贪心）
    def _landlord(self, Yd):
        """房东：租户按户键顺序，向同街「住得最久（搬入最早）、同年里最近」且未满 6 家的有房户租；
        这条街没有有房户（或没有街名）才退到 250px 内。顺序贪心不可并行，但：
        - 每条街的有房户按搬入年排好，满了就从街表里删（摊还 O(1) 跳过满员房东）；
        - 退到半径的租户一次批量 KD 球查询；
        - 增量：在住户集合与各户街名都和上一年相同，就直接沿用上一年的分配。"""
        S, n, x, y, st, own, B = Yd['S'], Yd['n'], Yd['x'], Yd['y'], Yd['st'], Yd['own'], Yd['B']
        sig = (S.tobytes(), st.tobytes())
        if self._ll_prev is not None and self._ll_prev[0] == sig:
            self.stats['landlord_reused'] += 1
            return self._ll_prev[1]
        self.stats['landlord_recomputed'] += 1
        Lp = self.P['landlord']; cap = Lp['cap']; R = Lp['radius']
        out = np.full(n, -1)
        O = np.nonzero(own)[0]
        Ol = O[np.lexsort((O, B[O]))].tolist()
        by = collections.defaultdict(list)
        stl = st.tolist(); Bl = B.tolist(); xl = x.tolist(); yl = y.tolist()
        for o in Ol: by[stl[o]].append(o)
        by.pop(-1, None)
        tenants = np.nonzero(~own)[0]
        tenants = tenants[np.argsort(self.keyrank[S[tenants]], kind='stable')].tolist()
        fb = [t for t in tenants if not by.get(stl[t])]
        balls = {}
        if fb and len(O):
            # 退到半径的租户：一次批量球查询，候选按 (搬入年, 距离, 房序) 排好，贪心时取第一个没满的
            res = cKDTree(np.c_[x[O], y[O]]).query_ball_point(np.c_[x[fb], y[fb]], R * 1.0001)
            ln = np.fromiter((len(r) for r in res), np.int64, len(res))
            rr = np.repeat(np.arange(len(fb)), ln); oo = O[np.fromiter((j for r in res for j in r), np.int64, int(ln.sum()))]
            fbt = np.array(fb)[rr]
            dd = np.hypot(x[oo] - x[fbt], y[oo] - y[fbt]); ok = dd <= R
            rr, oo, dd = rr[ok], oo[ok], dd[ok]
            o = np.lexsort((oo, dd, B[oo], rr)); rr, oo = rr[o], oo[o]
            cut = np.searchsorted(rr, np.arange(len(fb) + 1))
            ool = oo.tolist()
            for k_, t in enumerate(fb): balls[t] = ool[cut[k_]:cut[k_ + 1]]
            self.stats['landlord_fallback'] += len(fb)
        load = [0] * n
        hyp = math.hypot
        for t in tenants:
            pool = by.get(stl[t])
            best = -1
            if pool:
                bb = None; bd = 0.0; j = 0
                while j < len(pool):
                    o = pool[j]
                    if load[o] >= cap: pool.pop(j); continue
                    if bb is not None and Bl[o] > bb: break
                    d = hyp(xl[o] - xl[t], yl[o] - yl[t])
                    if bb is None or d < bd or (d == bd and o < best): best, bb, bd = o, Bl[o], d
                    j += 1
            else:
                for o in balls.get(t, ()):
                    if load[o] < cap: best = o; break
            if best < 0: continue
            load[best] += 1; out[t] = best
        self._ll_prev = (sig, out)
        return out

    def _patron(self, Yd, size, dth, fnn, B, Y):
        """恩主：门客按户键顺序，找 250px 内未满 5 家、同派优先的最近恩主。批量 KD 取每户最近 24 个候选，
        只有 24 个都在半径内且都没找到同派空位时才退回整球查询（结果与 v0 完全相同）。"""
        S, n, x, y, own, faith, needy = Yd['S'], Yd['n'], Yd['x'], Yd['y'], Yd['own'], Yd['faith'], Yd['needy']
        Pp = self.P['patron']; tenure = Y - B; R = Pp['radius']; cap = Pp['cap']
        fine = self.fn_names.index('fine') if 'fine' in self.fn_names else -99
        pats = (fnn == fine) | (own & (tenure >= Pp['min_tenure']) & (size >= Pp['min_size']))
        cl = ~pats & (needy | (~own & (dth | (tenure <= 3))))
        out = np.full(n, -1)
        PI = np.nonzero(pats)[0]; CI = np.nonzero(cl)[0]
        if not len(PI) or not len(CI): return out
        CI = CI[np.argsort(self.keyrank[S[CI]], kind='stable')]
        t = cKDTree(np.c_[x[PI], y[PI]])
        K = min(24, len(PI))
        d, i = t.query(np.c_[x[CI], y[CI]], k=K, distance_upper_bound=R * 1.0001)
        i = np.asarray(i).reshape(len(CI), -1); ok = i < len(PI)
        oi = PI[np.where(ok, i, 0)]
        dd = np.where(ok, np.hypot(x[oi] - x[CI][:, None], y[oi] - y[CI][:, None]), INF)
        dd = np.where(dd <= R, dd, INF)
        tk = Yd['tk']
        pre = np.argsort(np.where(dd < INF, tk[oi], n + 1), axis=1, kind='stable')
        dd = np.take_along_axis(dd, pre, 1); oi = np.take_along_axis(oi, pre, 1)
        o2 = np.argsort(dd, axis=1, kind='stable')
        dd = np.take_along_axis(dd, o2, 1); oi = np.take_along_axis(oi, o2, 1)
        trunc = (dd[:, -1] < INF) & (K < len(PI))
        load = [0] * n; fl = faith.tolist(); same = Pp['prefer_same_faith']
        OI = oi.tolist(); DD = dd.tolist()
        for r, c in enumerate(CI.tolist()):
            first = -1; best = -1
            for o, dv in zip(OI[r], DD[r]):
                if dv == INF: break
                if load[o] >= cap: continue
                if first < 0: first = o
                if not same or fl[o] == fl[c]: best = o; break
            if best < 0 and trunc[r]:
                self.stats['patron_ball_fallback'] += 1
                bs = None
                for j in t.query_ball_point([x[c], y[c]], R * 1.0001):
                    o = PI[j]
                    if load[o] >= cap: continue
                    dv = math.hypot(x[o] - x[c], y[o] - y[c])
                    if dv > R: continue
                    k = ((fl[o] != fl[c]) if same else 0, dv, tk[o])
                    if bs is None or k < bs: bs = k; best = o
            elif best < 0: best = first
            if best < 0: continue
            load[best] += 1; out[c] = best
        return out

    _debt_cache = None
    def _debt_of(self, hy):
        """灾年 hy 结下的债：(债主全局下标, 借债户全局下标)。只在那一年算一次（v0 每年重算 4 次）。"""
        if self._debt_cache is None: self._debt_cache = {}
        if hy in self._debt_cache: return self._debt_cache[hy]
        M = self.M; P = self.P['debt']; yi = hy - self.YR0
        S = np.nonzero(M['present'][:, yi])[0]
        x, y = self.fx[S], self.fy[S]; own = self.owner[S]
        tk = np.empty(len(S), np.int64); tk[np.lexsort((np.arange(len(S)), np.floor(y / 120), np.floor(x / 120)))] = np.arange(len(S))
        men = M['men'][S, yi]; kids = M['kids'][S, yi]; needy = (men == 0) & (kids > 0)
        dth = M['deaths'][S, yi] > 0; size = M['size'][S, yi]
        L = np.nonzero(own & np.isin(M['ft'][S], self.lender_t) & ~needy)[0]
        Bw = np.nonzero(~own & (dth | needy | (size >= 6)))[0]
        Bw = Bw[np.argsort(self.keyrank[S[Bw]], kind='stable')]
        out = []
        if len(L):
            t = cKDTree(np.c_[x[L], y[L]]); load = collections.Counter()
            for b, lst in zip(Bw, t.query_ball_point(np.c_[x[Bw], y[Bw]], P['radius'] * 1.0001)):
                best = None; bs = None
                for i in lst:
                    o = L[i]
                    if load[o] >= P['cap']: continue
                    d = math.hypot(x[o] - x[b], y[o] - y[b])
                    if d > P['radius']: continue
                    if bs is None or (d, tk[o]) < bs: best, bs = o, (d, tk[o])
                if best is None: continue
                load[best] += 1; out.append((int(S[best]), int(S[b])))
        self._debt_cache[hy] = out
        return out

    def _nodes(self, Yd, alms_src, men, dth, needy, lx, ly):
        """单户 × 机构：施舍、拆房、凑铜板、征工、兵营（顺序与 v0 RULES 相同，交叉点记第一个机构）。"""
        Y = Yd['Y']; S = Yd['S']; n = Yd['n']; M = self.M; Po = self.P['office']
        node = [None] * n
        def put(i, kind, name):
            if node[i] is None: node[i] = []
            node[i].append((kind, name))
        for i in np.nonzero(alms_src != '')[0]: put(i, 'alms', alms_src[i])
        dest = self.fdest[S]
        for i in np.nonzero(dest == Y + 1)[0]:
            site = {54: '运水人蓄水池', 57: '狄奥多西广场', 62: '运水人台阶路'}.get(int(dest[i]), '公家工程')
            put(i, 'evicted', '@拆房:' + site)
        ly_ = Po['levy_years'].get(str(Y))
        if ly_:
            c = next((w for w in self.water if w['id'] == ly_), None)
            if c:
                d = np.hypot(c['x'] - lx, c['y'] - ly)
                m = (d <= Po['levy_radius']) & ((Yd['trade'] == self.carrier_t) | ((Y == 62) & (ly < c['y'])))
                for i in np.nonzero(m)[0]: put(i, 'levy', '@凑铜板:' + ly_)
        if Y == Po['corvee_year']:
            st = Yd['st']; by = collections.defaultdict(list)
            for i in np.nonzero(~Yd['own'] & (men >= 1) & (st >= 0))[0]: by[st[i]].append(i)
            for l in by.values():
                for i in sorted(l, key=lambda i: (-men[i], self.keyrank[S[i]]))[:Po['corvee_per_street']]:
                    put(i, 'corvee', '@征工:' + Po['corvee_site'])
        b = self.D['barracks']; Pg = self.P['garrison']
        fg = self.fn_names.index('garrison') if 'garrison' in self.fn_names else -99
        gar = self.ffn[S] == fg
        if b is not None: gar |= np.hypot(b[0] - lx, b[1] - ly) <= Pg['radius']
        gar |= M['fsold'][S] <= Y
        for i in np.nonzero(gar)[0]: put(i, 'garrison', '@城门兵营')
        return node

    # ------------------------------------------------------------ 按需：一对人家这一年之间有哪些弱关系（只给交叉点打分用）
    TBITS = dict(water=1, bread=2, faith=4, trade=8, hometown=16, landlord=32, patron=64, apprentice=128, rival=256, debt=512, carrier=1024)

    def pair_types(self, Yd, A, Bb, carrier=True, need=None):
        """A, Bb：本地下标数组。返回每对的类型位掩码（int 数组）。背景类（面包/信仰/同行/运水人）只在这里、只对交叉点两端按需查。"""
        n = Yd['n']; x, y = Yd['x'], Yd['y']; P = self.P; TB = self.TBITS
        A = np.asarray(A); Bb = np.asarray(Bb)
        need = np.full(len(A), -1, np.int64) if need is None else np.asarray(need)   # 每对还需要查的类型位（模式本身已蕴含的规则不用再查）
        bits = np.zeros(len(A), np.int64)
        code = np.minimum(A, Bb) * n + np.maximum(A, Bb)
        bits |= np.where(np.isin(code, Yd['wcode']), TB['water'], 0)
        def knn_member(mask_ok, g, k, bound=None, tk=None, bit=0):
            # 最便宜的条件先筛：两端要同组（同派/同街同行/同一座炉的有房户），且（有半径时）在半径内
            sel = ((need & bit) != 0) & mask_ok[A] & mask_ok[Bb] & (g[A] == g[Bb])
            if bound: sel &= np.hypot(x[A] - x[Bb], y[A] - y[Bb]) <= bound
            if not sel.any(): return np.zeros(len(A), bool)
            ends = np.unique(np.r_[A[sel], Bb[sel]])
            ii = np.nonzero(mask_ok)[0]
            q = ends[mask_ok[ends]]
            if not len(q) or not len(ii): return np.zeros(len(A), bool)
            nb = knn_group(x[ii], y[ii], g[ii].astype(float), k, q=np.searchsorted(ii, q), bound=bound, tk=(tk[ii] if tk is not None else None))
            nbg = np.where(nb >= 0, ii[np.maximum(nb, 0)], -1)
            row = np.full(n, -1); row[q] = np.arange(len(q))
            def has(a, b):
                r = row[a]; ok = r >= 0
                return ok & (nbg[np.maximum(r, 0)] == b[:, None]).any(1)
            return sel & (has(A, Bb) | has(Bb, A))
        own = Yd['own']
        om = np.nonzero(self.ob <= Yd['Y'])[0]
        if len(om) and ((need & TB['bread']) != 0).any():
            # 组内近邻要知道全体有房户各在哪座炉（有房户 ~2k，一次 KD 查询），近邻本身只查端点
            ow = np.nonzero(own)[0]
            kk = min(3, len(om))
            _, oi2 = cKDTree(np.c_[self.ox[om], self.oy[om]]).query(np.c_[x[ow], y[ow]], k=kk)
            oi2 = om[np.asarray(oi2).reshape(len(ow), -1)]
            dd = np.hypot(self.ox[oi2] - x[ow][:, None], self.oy[oi2] - y[ow][:, None])
            j = np.lexsort((oi2, dd), axis=1)[:, 0]          # v0：min() 取炉表里第一个最近的
            g = np.full(n, -1.0); g[ow] = oi2[np.arange(len(ow)), j]
            bits |= np.where(knn_member(own, g, P['bread']['k'], bit=TB['bread']), TB['bread'], 0)
        bits |= np.where(knn_member(np.ones(n, bool), Yd['faith'], P['faith']['k'], bound=P['faith']['radius'], tk=Yd['tk'], bit=TB['faith']), TB['faith'], 0)
        st, tr = Yd['st'], Yd['trade']
        bits |= np.where(knn_member(st >= 0, st.astype(np.int64) * 1000 + tr, P['trade_street']['k'], bit=TB['trade']), TB['trade'], 0)
        for name, arr in (('hometown', Yd['parent']), ('landlord', Yd['landlord']), ('patron', Yd['patron']), ('apprentice', Yd['app']), ('rival', Yd['rival'])):
            bits |= np.where((arr[Bb] == A) | (arr[A] == Bb), TB[name], 0)
        if Yd['debts']:
            dc = np.array([l * n + b for l, b in Yd['debts']])
            bits |= np.where(np.isin(A * n + Bb, dc) | np.isin(Bb * n + A, dc), TB['debt'], 0)
        if carrier:
            # 运水人只贡献「同一口水」这条规则名：已有同水边的对不用查
            tr_ = Yd['trade']; isc = tr_ == self.carrier_t
            needc = ((isc[A] != isc[Bb])) & ((bits & TB['water']) == 0) & ((need & TB['carrier']) != 0)
            if needc.any():
                Pc = self.P['carrier']
                far = np.nonzero(~isc & ((Yd['wsrc'] < 0) | (Yd['wd'] > Pc['far'])))[0]
                cs = np.unique(np.where(isc[A], A, Bb)[needc])
                cust = {}
                if len(far):
                    kk = min(Pc['max_customers'] + 3, len(far))
                    d, i = cKDTree(np.c_[x[far], y[far]]).query(np.c_[x[cs], y[cs]], k=kk, distance_upper_bound=Pc['radius'] * 1.0001)
                    i = np.asarray(i).reshape(len(cs), -1); ok = i < len(far); ic = far[np.where(ok, i, 0)]
                    dd = np.where(ok, np.hypot(x[ic] - x[cs][:, None], y[ic] - y[cs][:, None]), INF)
                    dd = np.where(dd <= Pc['radius'], dd, INF)
                    for r, c in enumerate(cs):
                        o = np.lexsort((Yd['tk'][ic[r]], dd[r]))
                        cust[int(c)] = set(int(ic[r][j]) for j in o[:Pc['max_customers']] if dd[r][j] < INF)
                for r in np.nonzero(needc)[0]:
                    c, o = (A[r], Bb[r]) if isc[A[r]] else (Bb[r], A[r])
                    if o in cust.get(int(c), ()): bits[r] |= TB['carrier']
        return bits
