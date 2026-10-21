"""规则预演 v2 · 检验「只用经济政治骨架」能复现多少 v1 交叉点。

三档（逐档叠加），都不生成、不存任何户与户之间的弱关系网：
  A 纯骨架：交叉模式的承载关系本身就是骨架的父指针（房东/债/恩主/师傅/官府事件/兵营/施舍）。
  B 骨架 + 在骨架触发点现推：
      「同水异粮」只从「有丧或缺男丁的租户」（恩主/债的门客候选，骨架已经标出）出发，
      「同井施舍分线」只从「缺男丁的人家」（教区施舍槽位已标出）出发，
      「火后同行对头」只在「超过容量、且有 48–50 年搬来户的 街×行会 组」里现查；
      用的是坐标索引（每口水一组的 KD 树）和每户的「喝哪口水」星形槽位，不是户与户的网。
  C B + 同乡链（静态候选表一次预计算，逐年查第一个在住的同乡）——它不是经济政治关系，单列。
打分：v1 的公式（run.score_v1），但「同一口水 / 面包 / 信仰 / 同行聚街」这四类背景规则名不再用 k 近邻，
      而用骨架星形的共属关系近似：同一个水源、同一个配给点的两家有房户、同派且 90px 内、同街同行。
usage: python3 reproduce.py sample|xero|city [--rev=150]
"""
import os, sys, json, time, collections, math, resource
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econpol as EP  # noqa: E402
from engine import Engine, ARIAN, NICENE, INF, knn_group, PAIR_PATTERNS  # noqa: E402
import importlib.util as _iu  # noqa: E402
_sp = _iu.spec_from_file_location('run_v1', os.path.join(EP.V1, 'run.py')); RUN = _iu.module_from_spec(_sp); _sp.loader.exec_module(RUN)  # v1 打分，只读复用
import prep  # noqa: E402

TB = Engine.TBITS


class Repro(EP.EconPol):
    def __init__(self, scope, P, level, rev):
        self.level = level; self.rev = rev
        super().__init__(scope, P, 'v1')
        if level >= 3: Engine._chain_csr(self)   # 3 = C, 4 = A+（都要同乡候选表）
        if level == 4: pass
        self.work = collections.Counter()

    def water_src(self, Yd):
        """每户「喝哪口水」：星形槽位（户 → 井/蓄水池），与 v1 同规则（井 140px，否则蓄水池 420px）。"""
        x, y, n, Y = Yd['x'], Yd['y'], Yd['n'], Yd['Y']; S = Yd['S']; lx, ly = self.flx[S], self.fly[S]
        Wp = self.P['water']; wsrc = np.full(n, -1)
        wm = np.nonzero(self.wwell & (self.wb <= Y))[0]
        if len(wm):
            kk = min(3, len(wm))
            d, i = cKDTree(np.c_[self.wx[wm], self.wy[wm]]).query(np.c_[x, y], k=kk, distance_upper_bound=Wp['well_reach'] * 1.0001)
            i = np.asarray(i).reshape(n, -1); ok = i < len(wm); wi = wm[np.where(ok, i, 0)]
            dd = np.where(ok, np.hypot(self.wx[wi] - x[:, None], self.wy[wi] - y[:, None]), INF)
            dd = np.where(dd <= Wp['well_reach'], dd, INF)
            gr = np.floor(self.wx[wi] / 140) * 1e9 + np.floor(self.wy[wi] / 140) * 1e4 + wi
            j = np.lexsort((gr, dd), axis=1)[:, 0]
            pick = wi[np.arange(n), j]; pd_ = dd[np.arange(n), j]; ok = pd_ < INF
            wsrc[ok] = pick[ok]
        cm = np.nonzero(~self.wwell & (self.wb <= Y))[0]
        if len(cm):
            rest = np.nonzero(wsrc < 0)[0]
            dc = np.hypot(self.wx[cm][None, :] - lx[rest, None], self.wy[cm][None, :] - ly[rest, None])
            j = np.argmin(dc, 1); dj = dc[np.arange(len(rest)), j]; ok = dj <= Wp['cistern_reach']
            wsrc[rest[ok]] = cm[j[ok]]
        return wsrc

    def hits_year(self, Y):
        R = self.year_ep(Y); Yd = R['Yd']; n = Yd['n']; S = Yd['S']; M = self.M
        faith, own, needy, dth, st, trade, x, y, B = (Yd[k] for k in ('faith', 'own', 'needy', 'dth', 'st', 'trade', 'x', 'y', 'B'))
        hits = []
        def add(name, A, Bb):
            A = np.asarray(A, np.int64); Bb = np.asarray(Bb, np.int64)
            if len(A): hits.append((PAIR_PATTERNS.index(name), S[A], S[Bb]))
        L = R['landlord']; T = np.nonzero(L >= 0)[0]; Lt = L[T]
        if Y >= 51:
            m = (faith[Lt] == NICENE) & (faith[T] == ARIAN); add('正统房东·阿里乌派租户', Lt[m], T[m])
        Pp = R['patron']; Cc = np.nonzero(Pp >= 0)[0]; m = faith[Pp[Cc]] != faith[Cc]; add('恩主门客异信', Pp[Cc][m], Cc[m])
        for lo, bo in R['debts']:
            if st[lo] >= 0 and st[lo] == st[bo]: add('债主欠债同街', [lo], [bo])
        dset = set(R['debts'])
        m = (Pp[T] == Lt) | np.array([(l, t) in dset for l, t in zip(Lt.tolist(), T.tolist())], bool).reshape(-1)
        add('房东兼债主/恩主', Lt[m], T[m])
        app = R['app']; Aq = np.nonzero(app >= 0)[0]; m = faith[app[Aq]] != faith[Aq]; add('学徒拜异派师傅', app[Aq][m], Aq[m])
        hits_h = []
        isc = trade == self.carrier_t; sold = M['fsold'][S] <= Y
        for s_ in np.nonzero(isc | sold)[0]:
            nd = R['node'][s_]
            if not nd: continue
            kinds = {k for k, _ in nd}
            if isc[s_] and (('evicted' in kinds or 'corvee' in kinds) or ('levy' in kinds and (needy[s_] or dth[s_]))):
                hits_h.append(('运水人摊上公家的事', int(S[s_]), nd[0][1]))
            if sold[s_] and needy[s_] and 'alms' not in kinds:
                hits_h.append(('儿子当兵·家里无男丁无施舍', int(S[s_]), nd[0][1]))
        wsrc = None; rival = np.full(n, -1); parent = np.full(n, -1)
        if self.level in (2, 3):
            wsrc = self.water_src(Yd); Wk = self.P['water']['k']
            hasw = np.nonzero(wsrc >= 0)[0]; gw = wsrc[hasw].astype(float)
            tree = cKDTree(np.c_[x[hasw] + gw * 1e5, y[hasw]]) if len(hasw) else None
            pos = np.full(n, -1); pos[hasw] = np.arange(len(hasw))
            def knn_of(q):    # q：本地下标（都有水源）→ (len(q), k) 邻居本地下标
                if not len(q): return np.zeros((0, Wk), np.int64)
                nb = knn_group(x[hasw], y[hasw], gw, Wk, q=pos[q], tree=tree)
                self.work['water_knn_queries'] += len(q)
                return np.where(nb >= 0, hasw[np.maximum(nb, 0)], -1)
            # 同水异粮：触发 = 有丧或缺男丁的租户
            trig = np.nonzero(~own & (dth | needy) & (wsrc >= 0))[0]
            # 同井施舍分线：触发 = 缺男丁的人家
            trig2 = np.nonzero(needy & (wsrc >= 0))[0]
            # 反向：触发户附近 rev px 内同一水源的有房户，算它们的近邻看是否含触发户
            cand = np.zeros(0, np.int64)
            if len(trig) and self.rev > 0:
                res = tree.query_ball_point(np.c_[x[trig] + wsrc[trig] * 1e5, y[trig]], self.rev)
                cand = np.unique(hasw[np.fromiter((j for r in res for j in r), np.int64)]) if sum(map(len, res)) else cand
                cand = cand[own[cand]]
            Q = np.unique(np.r_[trig, trig2, cand])
            nb = knn_of(Q); row = np.full(n, -1); row[Q] = np.arange(len(Q))
            self.work['triggers_water'] += len(np.unique(np.r_[trig, trig2])); self.work['reverse_candidates'] += len(cand)
            pr = set()
            for t in np.unique(np.r_[trig, trig2]).tolist():
                for o in nb[row[t]].tolist():
                    if o >= 0: pr.add((min(t, o), max(t, o)))
            for o in cand.tolist():
                for t in nb[row[o]].tolist():
                    if t >= 0: pr.add((min(t, o), max(t, o)))
            if pr:
                pa = np.array(sorted(pr)); wa, wb_ = pa[:, 0], pa[:, 1]
                m = own[wa] != own[wb_]; tt = np.where(own[wa], wb_, wa); m &= dth[tt] | needy[tt]
                add('同水异粮', wa[m], wb_[m])
                an = R['alms_src'] == ''
                m = needy[wa] & needy[wb_] & (an[wa] != an[wb_]); add('同井施舍分线', wa[m], wb_[m])
                Yd['wcode'] = np.unique(wa * n + wb_)
            # 火后同行对头：只在「超容量 ∧ 组里有 48–50 年搬来户」的 街×行会 组里现查
            Rp = self.P['rival']; hs = st >= 0
            gkey = np.where(hs, st.astype(np.int64) * 1000 + trade, -1)
            u, inv, cnt = np.unique(gkey, return_inverse=True, return_counts=True)
            capv = np.array([Rp['cap'].get(f, Rp['cap']['default']) for f in self.fn_names])[self.ffn[S]]
            ref = (B >= 48) & (B <= 50)
            gref = np.zeros(len(u), bool); np.logical_or.at(gref, inv, ref)
            q = np.nonzero(hs & (cnt[inv] > capv) & gref[inv])[0]
            self.work['rival_groups'] += int(len(np.unique(gkey[q]))); self.work['rival_queries'] += len(q)
            if len(q):
                ii = np.nonzero(hs & gref[inv])[0]
                nb1 = knn_group(x[ii], y[ii], gkey[ii].astype(float), 1, q=np.searchsorted(ii, q), bound=Rp['dist'], tk=Yd['tk'][ii])
                rival[q] = np.where(nb1[:, 0] >= 0, ii[np.maximum(nb1[:, 0], 0)], -1)
            rq = np.nonzero(rival >= 0)[0]; ra, rb = rq, rival[rq]
            rc = np.unique(np.minimum(ra, rb) * n + np.maximum(ra, rb)); ra, rb = rc // n, rc % n
            m = ref[ra] | ref[rb]; add('火后同行对头', ra[m], rb[m])
        if self.level == 4:
            self._anchored(R, Yd, add, wsrc_out := {})
            wsrc = wsrc_out.get('wsrc'); rival = wsrc_out.get('rival', rival); parent = wsrc_out.get('parent', parent)
        if self.level == 3:
            loc = Yd['loc']; yi = Y - self.YR0
            cs, ct = self.ch_s, self.ch_t
            ok = M['present'][cs, yi] & M['present'][ct, yi]; cs2, ct2 = cs[ok], ct[ok]
            first = np.r_[True, cs2[1:] != cs2[:-1]] if len(cs2) else np.zeros(0, bool)
            ps, pt = loc[cs2[first]], loc[ct2[first]]; parent[ps] = pt
            if Y >= 51:
                m = ((faith[pt] == ARIAN) & (faith[ps] == NICENE)) | ((faith[pt] == NICENE) & (faith[ps] == ARIAN))
                add('同乡异信', pt[m], ps[m])
        R.update(hits=hits, hits_h=hits_h, wsrc=wsrc, rival=rival, parent=parent)
        return R

    def _anchored(self, R, Yd, add, out):
        """A+：弱模式只在骨架边（房东/恩主/债/师傅）的两端上反推——每条骨架边查两端的同水近邻、同行对头、同乡链，别处一律不算。"""
        n = Yd['n']; S = Yd['S']; M = self.M; Y = Yd['Y']
        faith, own, needy, dth, st, trade, x, y, B = (Yd[k] for k in ('faith', 'own', 'needy', 'dth', 'st', 'trade', 'x', 'y', 'B'))
        L = R['landlord']; Pp = R['patron']; app = R['app']
        pa = [np.nonzero(L >= 0)[0], np.nonzero(Pp >= 0)[0], np.nonzero(app >= 0)[0]]
        A_ = np.r_[pa[0], pa[1], pa[2], np.array([b for a, b in R['debts']], np.int64)]
        B_ = np.r_[L[pa[0]], Pp[pa[1]], app[pa[2]], np.array([a for a, b in R['debts']], np.int64)]
        if not len(A_): return
        code = np.unique(np.minimum(A_, B_) * n + np.maximum(A_, B_)); A_, B_ = code // n, code % n
        ends = np.unique(np.r_[A_, B_]); self.work['anchored_edges'] += len(A_); self.work['anchored_endpoints'] += len(ends)
        wsrc = self.water_src(Yd); out['wsrc'] = wsrc; Wk = self.P['water']['k']
        hasw = np.nonzero(wsrc >= 0)[0]; gw = wsrc[hasw].astype(float)
        if len(hasw):
            tree = cKDTree(np.c_[x[hasw] + gw * 1e5, y[hasw]]); pos = np.full(n, -1); pos[hasw] = np.arange(len(hasw))
            q = ends[wsrc[ends] >= 0]
            nb = knn_group(x[hasw], y[hasw], gw, Wk, q=pos[q], tree=tree); nb = np.where(nb >= 0, hasw[np.maximum(nb, 0)], -1)
            self.work['water_knn_queries'] += len(q)
            row = np.full(n, -1); row[q] = np.arange(len(q))
            def has(a, b):
                r = row[a]; ok = r >= 0
                return ok & (nb[np.maximum(r, 0)] == b[:, None]).any(1)
            w = (wsrc[A_] == wsrc[B_]) & (wsrc[A_] >= 0) & (has(A_, B_) | has(B_, A_))
            wa, wb_ = A_[w], B_[w]
            m = own[wa] != own[wb_]; tt = np.where(own[wa], wb_, wa); m &= dth[tt] | needy[tt]; add('同水异粮', wa[m], wb_[m])
            an = R['alms_src'] == ''; m = needy[wa] & needy[wb_] & (an[wa] != an[wb_]); add('同井施舍分线', wa[m], wb_[m])
        # 同行对头：只查骨架边两端
        Rp = self.P['rival']; hs = st >= 0
        gkey = np.where(hs, st.astype(np.int64) * 1000 + trade, -1)
        u, inv, cnt = np.unique(gkey, return_inverse=True, return_counts=True)
        capv = np.array([Rp['cap'].get(f, Rp['cap']['default']) for f in self.fn_names])[self.ffn[S]]
        q = ends[hs[ends] & (cnt[inv][ends] > capv[ends])]
        rival = np.full(n, -1)
        if len(q):
            ii = np.nonzero(hs)[0]
            nb1 = knn_group(x[ii], y[ii], gkey[ii].astype(float), 1, q=np.searchsorted(ii, q), bound=Rp['dist'], tk=Yd['tk'][ii])
            rival[q] = np.where(nb1[:, 0] >= 0, ii[np.maximum(nb1[:, 0], 0)], -1); self.work['rival_queries'] += len(q)
        ref = (B >= 48) & (B <= 50)
        m = ((rival[A_] == B_) | (rival[B_] == A_)) & (ref[A_] | ref[B_]); add('火后同行对头', A_[m], B_[m])
        out['rival'] = rival
        # 同乡链：只查骨架边两端在静态候选表里的第一个在住同乡
        parent = np.full(n, -1)
        if len(self.ch_s) and Y >= 51:
            yi = Y - self.YR0; loc = Yd['loc']
            g = S[ends]; lo_ = np.searchsorted(self.ch_s, g, 'left'); hi_ = np.searchsorted(self.ch_s, g, 'right')
            for e, l_, h_ in zip(ends.tolist(), lo_.tolist(), hi_.tolist()):
                for t in self.ch_t[l_:h_].tolist():
                    if M['present'][t, yi]: parent[e] = loc[t]; break
            self.work['chain_lookups'] += len(ends)
            m = ((parent[A_] == B_) | (parent[B_] == A_))
            fa, fb = faith[A_], faith[B_]
            m &= ((fa == ARIAN) & (fb == NICENE)) | ((fa == NICENE) & (fb == ARIAN))
            par = np.where(parent[A_] == B_, B_, A_); chi = np.where(parent[A_] == B_, A_, B_)
            add('同乡异信', par[m], chi[m])
        out['parent'] = parent

    def pair_types_approx(self, R, A, Bb):
        """只用骨架星形的共属关系给交叉点打分（不查任何 k 近邻）。"""
        Yd = R['Yd']; n = Yd['n']; bits = np.zeros(len(A), np.int64)
        for name, arr in (('landlord', R['landlord']), ('patron', R['patron']), ('apprentice', R['app']), ('rival', R['rival']), ('hometown', R['parent'])):
            bits |= np.where((arr[Bb] == A) | (arr[A] == Bb), TB[name], 0)
        if R['debts']:
            dc = np.array([l * n + b for l, b in R['debts']])
            bits |= np.where(np.isin(A * n + Bb, dc) | np.isin(Bb * n + A, dc), TB['debt'], 0)
        if R['wsrc'] is not None:
            bits |= np.where((R['wsrc'][A] == R['wsrc'][Bb]) & (R['wsrc'][A] >= 0), TB['water'], 0)
        ra = R['ration']; bits |= np.where((ra[A] == ra[Bb]) & (ra[A] >= 0), TB['bread'], 0)
        f = Yd['faith']; bits |= np.where((f[A] == f[Bb]) & (np.hypot(Yd['x'][A] - Yd['x'][Bb], Yd['y'][A] - Yd['y'][Bb]) <= self.P['faith']['radius']), TB['faith'], 0)
        st, tr = Yd['st'], Yd['trade']; bits |= np.where((st[A] == st[Bb]) & (st[A] >= 0) & (tr[A] == tr[Bb]), TB['trade'], 0)
        return bits


def score_rows(E, by_pair, ptu, y0, y1):
    """与 rules_v1/run.py main() 的打分段相同（v1 模式）。"""
    M = E.M; keys = E.keys; NF = len(keys)
    yi0 = y0 - E.YR0; yi1 = y1 - E.YR0 + 1
    pres = M['present'][:, yi0:yi1]; dth = (M['deaths'][:, yi0:yi1] > 0) & pres
    nd_ = ((M['men'][:, yi0:yi1] == 0) & (M['kids'][:, yi0:yi1] > 0)) & pres
    demol = (E.fdest <= y1 + 1).tolist(); arian = (M['ff'] == ARIAN).tolist(); hasflag = pres.any(1).tolist()
    w = (1 << np.arange(y1 - y0 + 1)).astype(np.int64)
    dmask = (dth * w).sum(1).tolist(); nmask = (nd_ * w).sum(1).tolist()
    rows = []
    for k, prs in by_pair.items():
        ys = sorted({y for _, yy in prs for y in yy}); ym = 0
        for y_ in ys: ym |= 1 << (y_ - y0)
        fams = [k[0]] if isinstance(k[1], str) else list(k); snap = {}
        for F in fams:
            if not hasflag[F]: continue
            snap[keys[F]] = dict(died_in=bool(dmask[F] & ym), was_needy=bool(nmask[F] & ym), demolished=demol[F], arian=arian[F])
        pc = None if isinstance(k[1], str) else k[0] * NF + k[1]
        sc, rl, dur, ev = RUN.score_v1(prs, RUN.bits2types(ptu.get(pc, 0)), snap, y0, y1)
        rows.append(dict(a=keys[k[0]], b=(k[1] if isinstance(k[1], str) else keys[k[1]]), fa=int(k[0]), fb=(-1 if isinstance(k[1], str) else int(k[1])),
                         patterns=sorted(n for n, _ in prs), years=ys, score=sc, rules=rl))
    rows.sort(key=lambda r: (-r['score'], r['a'], r['b']))
    return rows


def picks8(E, rows):
    M = E.M; arian = M['ff'] == ARIAN
    def skel(r):
        tr = [M['ft'][r['fa']]] + ([M['ft'][r['fb']]] if r['fb'] >= 0 else ['@'])
        fa = sorted(('阿' if arian[f] else '非') if f >= 0 else '@' for f in (r['fa'], r['fb']))
        return '|'.join(r['patterns']) + ('|同行' if tr[0] == tr[1] else '|异行') + '|' + ''.join(fa)
    used = set(); usk = collections.Counter(); out = []
    for r in rows:
        ks = {r['a'], r['b']} - ({r['b']} if r['b'].startswith('@') else set())
        if ks & used or usk[skel(r)] >= 2: continue
        out.append(r); used |= ks; usk[skel(r)] += 1
        if len(out) == 8: break
    return out


def run_level(scope, level, rev):
    t0 = time.time()
    P = json.load(open(os.path.join(EP.V0, 'rules.json')))
    E = Repro(scope, P, level, rev); y0, y1 = P['years']
    NF = len(E.keys); KR = E.keyrank
    occ = collections.defaultdict(lambda: collections.defaultdict(set)); ptu = {}
    t_rules = 0.0
    for Y in range(y0, y1 + 1):
        a = time.perf_counter(); R = E.hits_year(Y); t_rules += time.perf_counter() - a
        if R['hits']:
            pid = np.concatenate([np.full(len(p), i) for i, p, q in R['hits']])
            p = np.concatenate([p for i, p, q in R['hits']]); q = np.concatenate([q for i, p, q in R['hits']])
            sw = KR[p] > KR[q]; a_ = np.where(sw, q, p); b_ = np.where(sw, p, q)
            code = a_.astype(np.int64) * NF + b_
            for c, pi in zip(code.tolist(), pid.tolist()): occ[(c // NF, c % NF)][PAIR_PATTERNS[pi]].add(Y)
            uc = np.unique(code); loc = R['Yd']['loc']
            bits = E.pair_types_approx(R, loc[uc // NF], loc[uc % NF])
            for c, bt in zip(uc.tolist(), bits.tolist()): ptu[c] = ptu.get(c, 0) | bt
        for name, p, nd in R['hits_h']: occ[(p, nd)][name].add(Y)
    by_pair = {k: [(nm, sorted(ys)) for nm, ys in v.items()] for k, v in occ.items()}
    rows = score_rows(E, by_pair, ptu, y0, y1)
    sec = time.time() - t0
    return E, rows, dict(seconds_total=round(sec, 3), seconds_rules=round(t_rules, 3), work=dict(E.work),
                         peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1))


def compare(E, rows, ref, ref_picks):
    key = lambda r: (r['a'], r['b'])
    mine = {key(r): r for r in rows}; refd = {key(r): r for r in ref}
    def stat(sub):
        pair = sum(1 for r in sub if key(r) in mine)
        pat = sum(1 for r in sub if key(r) in mine and mine[key(r)]['patterns'] == sorted(r['patterns']))
        exact = sum(1 for r in sub if key(r) in mine and mine[key(r)]['patterns'] == sorted(r['patterns']) and mine[key(r)]['years'] == r['years'])
        return dict(n=len(sub), pair_found=pair, same_patterns=pat, same_patterns_and_years=exact)
    out = dict(all=stat(ref), top100=stat(ref[:100]), top8_picks=stat(ref_picks))
    # 漏掉的类：v1 交叉点里，按模式统计没找回来的（模式·对）
    miss = collections.Counter(); have = collections.Counter()
    for r in ref:
        got = set(mine[key(r)]['patterns']) if key(r) in mine else set()
        for p in r['patterns']:
            have[p] += 1
            if p not in got: miss[p] += 1
    out['missing_by_pattern'] = {p: [miss[p], have[p]] for p in have}
    extra = [r for r in rows if key(r) not in refd]
    out['extra_pairs'] = len(extra)
    # 排名：用骨架近似打分重新排，前 100 / 前 8 与 v1 重合多少
    mt100 = {key(r) for r in rows[:100]}; rt100 = {key(r) for r in ref[:100]}
    mp = picks8(E, rows)
    out['rank'] = dict(top100_overlap=len(mt100 & rt100), picks8_overlap=len({key(r) for r in mp} & {key(r) for r in ref_picks}),
                       my_picks=[[r['a'], r['b'], r['patterns'], r['score']] for r in mp])
    # 分数差（对找回来的、模式相同的交叉点）
    d = [mine[key(r)]['score'] - r['score'] for r in ref if key(r) in mine and mine[key(r)]['patterns'] == sorted(r['patterns'])]
    if d:
        d = np.array(d); out['score_diff'] = dict(mean=round(float(d.mean()), 3), abs_mean=round(float(np.abs(d).mean()), 3), zero_share=round(float((d == 0).mean()), 3),
                                                  max_up=round(float(d.max()), 2), max_down=round(float(d.min()), 2))
    return out


def main(scope, rev):
    ref = json.load(open(os.path.join(prep.CACHE, f'rules_v1_cross_{scope}_v1.json')))
    ref_picks = json.load(open(os.path.join(HERE, '..', 'rules_v1', 'out', f'{scope}_v1.json')))['picks']
    res = dict(scope=scope, v1_crossings=len(ref), reverse_radius_px=rev, levels={})
    names = {1: 'A 纯骨架', 4: 'A+ 只在骨架边两端反推弱模式', 2: 'B 骨架+触发点现推', 3: 'C B+同乡链'}
    for lv in (1, 4, 2, 3):
        E, rows, meta = run_level(scope, lv, rev)
        c = compare(E, rows, ref, ref_picks)
        res['levels'][names[lv]] = dict(crossings=len(rows), **meta, **c)
        print(names[lv], json.dumps(dict(crossings=len(rows), **meta, all=c['all'], top100=c['top100'], top8=c['top8_picks'], rank={k: v for k, v in c['rank'].items() if k != 'my_picks'}, score_diff=c.get('score_diff')), ensure_ascii=False))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, 'out', f'reproduce_{scope}.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    rev = int(next((x[6:] for x in sys.argv if x.startswith('--rev=')), 300))
    main(a[0], rev)
