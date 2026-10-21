"""规则预演 v1 · 关系分级 + 视野驱动（注意力预算）。

不同时要所有关系：每类关系有重要度（ego.TIER），只算眼前能呈现的。
  query(bbox, zoom, year, budget) → 应显示的关系 / 交叉点
    zoom 0 全城：只读存好的交叉点，每个「街区格」(400px) 取分数最高的前 N 个（budget = N，另有总数上限）
    zoom 1 街区：视口内每户只留重要度最高的前 k 条（交叉点 > 亲家/房东/债/恩主 > 施舍/兵营/官府 > 同乡/对头），
               全部用存好的强关系 + 户属性向量化算，不碰背景类（同水/面包/同行/信仰同堂）
    zoom 2 单街：视口里的户，背景类也算（逐户现算自我网，按重要度够 k 条就停），总条数受 budget 限制
    点开一户：ego.Ego.ego(户, 年) 完整自我网
python3 view.py → 三种视野计时 + 全量 vs 分级 对照 + 前 8 名在分级后是否还在，写 out/view.json
"""
import os, sys, json, time, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ego import Ego, TIER

CELL = 400   # 街区格（干山页像素；一栋房子约 15px 宽）


class View:
    def __init__(self, scope, mode='v1'):
        self.E = E = Ego(scope, mode)
        C = E.cross
        rows = [(i, a, b) for i, c in enumerate(C) for a, b in c[5]]
        self.ci = np.array([r[0] for r in rows]); self.cy0 = np.array([r[1] for r in rows]); self.cy1 = np.array([r[2] for r in rows])
        fa = np.array([c[0] for c in C]); fb = np.array([c[1] for c in C]); sc = np.array([c[3] for c in C])
        self.cfa, self.cfb, self.csc = fa[self.ci], fb[self.ci], sc[self.ci]
        mx = np.where(self.cfb >= 0, (E.fx[self.cfa] + E.fx[np.maximum(self.cfb, 0)]) / 2, E.fx[self.cfa])
        my = np.where(self.cfb >= 0, (E.fy[self.cfa] + E.fy[np.maximum(self.cfb, 0)]) / 2, E.fy[self.cfa])
        self.cmx, self.cmy = mx, my
        self.ccell = (np.floor(mx / CELL).astype(np.int64) * 100003 + np.floor(my / CELL).astype(np.int64))
        A = E.assign
        self.ak = np.array([TIER[a[0]] for a in A]); self.aa = np.array([a[1] for a in A]); self.ab = np.array([a[2] for a in A])
        self.ay0 = np.array([a[3] for a in A]); self.ay1 = np.array([a[4] for a in A]); self.akind = [a[0] for a in A]
        K = E.M['kin']
        self.ka, self.kb, self.ky0, self.ky1 = (K[:, 0], K[:, 1], K[:, 2], K[:, 3]) if len(K) else (np.zeros(0, int),) * 4
        self.count = collections.Counter()

    # ------------------------------------------------------------------
    def query(self, bbox, zoom, year, budget):
        x0, y0, x1, y1 = bbox; E = self.E
        if zoom == 0:
            N, cap = budget if isinstance(budget, tuple) else (budget, 10 ** 9)
            m = (self.cy0 <= year) & (year <= self.cy1) & (self.cmx >= x0) & (self.cmx <= x1) & (self.cmy >= y0) & (self.cmy <= y1)
            idx = np.nonzero(m)[0]
            o = idx[np.lexsort((-self.csc[idx], self.ccell[idx]))]
            cell = self.ccell[o]
            start = np.r_[0, np.nonzero(np.diff(cell))[0] + 1]
            rank = np.arange(len(o)) - np.repeat(start, np.diff(np.r_[start, len(o)]))
            keep = o[rank < N]
            keep = keep[np.argsort(-self.csc[keep], kind='stable')][:cap]
            self.count['evaluated'] += len(idx)
            return [('cross', int(self.ci[i]), int(self.cfa[i]), int(self.cfb[i]), float(self.csc[i])) for i in keep]
        c = E.year_ctx(year)
        S = c['S']
        vis = S[(E.fx[S] >= x0) & (E.fx[S] <= x1) & (E.fy[S] >= y0) & (E.fy[S] <= y1)]
        k, cap = budget if isinstance(budget, tuple) else (budget, 10 ** 9)
        if zoom == 1:
            return self._lod1(vis, year, c, k, cap)
        # zoom 2：单街——逐户现算自我网（够 k 条就停，背景类最后算），总条数到 cap 就停
        out = []
        order = self._priority(vis, year)
        for F in order:
            r = E.ego(int(F), year, budget=k)
            out += [(F,) + t for t in r]
            if len(out) >= cap: break
        self.count['households_ego'] += len(order)
        return out[:cap]

    def _priority(self, vis, year):
        """先画有交叉点的户（按最高分），再画其余的。"""
        best = np.zeros(self.E.NF)
        m = (self.cy0 <= year) & (year <= self.cy1)
        np.maximum.at(best, self.cfa[m], self.csc[m]); fbm = self.cfb[m]; ok = fbm >= 0
        np.maximum.at(best, fbm[ok], self.csc[m][ok])
        return vis[np.argsort(-best[vis], kind='stable')]

    def _lod1(self, vis, year, c, k, cap):
        """视口内每户前 k 条（不含背景类），全部向量化：交叉点、制度分配、亲家、施舍/兵营、同乡链。"""
        E = self.E; NF = E.NF
        inv = np.zeros(NF, bool); inv[vis] = True
        F_, O_, T_, S_ = [], [], [], []
        # 交叉点
        m = (self.cy0 <= year) & (year <= self.cy1) & (inv[self.cfa] | (self.cfb >= 0) & inv[np.maximum(self.cfb, 0)])
        i = np.nonzero(m)[0]
        for a, b in ((self.cfa[i], self.cfb[i]), (self.cfb[i], self.cfa[i])):
            ok = (a >= 0) & inv[np.maximum(a, 0)]
            F_.append(a[ok]); O_.append(b[ok]); T_.append(np.full(ok.sum(), 9.0) + self.csc[i][ok] / 100); S_.append(i[ok])
        # 制度分配（房东 / 恩主 / 债）
        m = (self.ay0 <= year) & (year <= self.ay1) & (inv[self.aa] | inv[self.ab])
        i = np.nonzero(m)[0]
        for a, b in ((self.aa[i], self.ab[i]), (self.ab[i], self.aa[i])):
            ok = inv[a]; F_.append(a[ok]); O_.append(b[ok]); T_.append(self.ak[i][ok].astype(float)); S_.append(-1 - i[ok])
        # 亲家
        if len(self.ka):
            m = (self.ky0 <= year) & (year < self.ky1) & c['pres'][self.ka] & c['pres'][self.kb] & (inv[self.ka] | inv[self.kb])
            i = np.nonzero(m)[0]
            for a, b in ((self.ka[i], self.kb[i]), (self.kb[i], self.ka[i])):
                ok = inv[a]; F_.append(a[ok]); O_.append(b[ok]); T_.append(np.full(ok.sum(), float(TIER['kin']))); S_.append(np.full(ok.sum(), -10 ** 9))
        # 施舍（缺男丁户 → 机构）、兵营（当兵户）：只看户属性
        nd = vis[c['needy'][vis]]
        F_.append(nd); O_.append(np.full(len(nd), -2)); T_.append(np.full(len(nd), float(TIER['alms']))); S_.append(np.full(len(nd), -10 ** 9))
        so = vis[E.M['fsold'][vis] <= year]
        F_.append(so); O_.append(np.full(len(so), -3)); T_.append(np.full(len(so), float(TIER['garrison']))); S_.append(np.full(len(so), -10 ** 9))
        # 同乡链：第一个今年还在住的候选（CSR，向量化）
        lo, hi = E.ch_ptr[vis], E.ch_ptr[vis + 1]
        ln = hi - lo
        if ln.sum():
            rows = np.repeat(vis, ln); pos = np.repeat(lo - np.cumsum(np.r_[0, ln[:-1]]), ln) + np.arange(ln.sum())
            t = E.ch_t[pos]; ok = c['pres'][t]
            rows, t = rows[ok], t[ok]
            first = np.r_[True, rows[1:] != rows[:-1]] if len(rows) else np.zeros(0, bool)
            F_.append(rows[first]); O_.append(t[first]); T_.append(np.full(first.sum(), float(TIER['hometown']))); S_.append(np.full(first.sum(), -10 ** 9))
        F_ = np.concatenate(F_); O_ = np.concatenate(O_); T_ = np.concatenate(T_); S_ = np.concatenate(S_)
        self.count['evaluated'] += len(F_)
        o = np.lexsort((-T_, F_)); F_, O_, T_, S_ = F_[o], O_[o], T_[o], S_[o]
        start = np.r_[0, np.nonzero(np.diff(F_))[0] + 1] if len(F_) else np.zeros(0, int)
        rank = np.arange(len(F_)) - np.repeat(start, np.diff(np.r_[start, len(F_)]))
        keep = rank < k
        F_, O_, T_, S_ = F_[keep], O_[keep], T_[keep], S_[keep]
        o = np.argsort(-T_, kind='stable')[:cap]       # 总预算：先留最重要的
        return list(zip(F_[o].tolist(), O_[o].tolist(), T_[o].tolist(), S_[o].tolist()))


def timeit(fn, n=30):
    fn()
    ts = []
    for _ in range(n):
        a = time.perf_counter(); r = fn(); ts.append(time.perf_counter() - a)
    ts = np.array(ts) * 1000
    return r, dict(mean_ms=round(ts.mean(), 2), p95_ms=round(np.percentile(ts, 95), 2), max_ms=round(ts.max(), 2))


def street_bbox(E, name, Y, pad=20):
    M = E.M; sid = M['st_names'].index(name); c = E.year_ctx(Y); S = c['S']
    on = S[c['st'][S] == sid]
    return (E.fx[on].min() - pad, E.fy[on].min() - pad, E.fx[on].max() + pad, E.fy[on].max() + pad), len(on)


def main():
    Y = 55; res = {}
    Vc = View('city'); Vx = View('xero')
    full = lambda E: (float(E.fx.min()) - 1, float(E.fy.min()) - 1, float(E.fx.max()) + 1, float(E.fy.max()) + 1)
    # 全城视野
    r, t = timeit(lambda: Vc.query(full(Vc.E), 0, Y, (3, 400)))
    res['city_full_zoom0'] = dict(t, returned=len(r), note='全城（合成人家）：每 400px 街区格前 3 个交叉点，总数 ≤400')
    r, t = timeit(lambda: Vx.query(full(Vx.E), 0, Y, (3, 400)))
    res['xero_full_zoom0'] = dict(t, returned=len(r), note='干山整片：每街区格前 3 个交叉点')
    # 干山街区视野（zoom 1）
    r, t = timeit(lambda: Vx.query(full(Vx.E), 1, Y, (4, 800)))
    res['xero_full_zoom1'] = dict(t, returned=len(r), note='干山整片按街区视野：每户前 4 条（不含背景类），总数 ≤800')
    bb = (600, 0, 1000, 400)
    r, t = timeit(lambda: Vx.query(bb, 1, Y, (4, 800)))
    res['xero_district_zoom1'] = dict(t, returned=len(r), bbox=bb, note='干山一块 400×400px 视口')
    # 单街视野（zoom 2，背景类也算）
    bbs, nh = street_bbox(Vx.E, '水池街', Y)
    r, t = timeit(lambda: Vx.query(bbs, 2, Y, (4, 120)), n=15)
    c_ = Vx.E.year_ctx(Y); S_ = c_['S']
    nin = int(((Vx.E.fx[S_] >= bbs[0]) & (Vx.E.fx[S_] <= bbs[2]) & (Vx.E.fy[S_] >= bbs[1]) & (Vx.E.fy[S_] <= bbs[3])).sum())
    res['xero_street_zoom2'] = dict(t, returned=len(r), bbox=[round(v) for v in bbs], households_on_street=nh, households_in_bbox=nin,
                                    note='水池街外接框：逐户现算自我网，每户前 4 条，总数 ≤120')
    bb2 = (bbs[0], bbs[1], bbs[0] + 160, bbs[1] + 160)
    r, t = timeit(lambda: Vx.query(bb2, 2, Y, (4, 60)), n=15)
    res['xero_street_segment_zoom2'] = dict(t, returned=len(r), bbox=[round(v) for v in bb2], note='水池街一段 160×160px')
    # 点开一户
    F = int(Vx._priority(Vx.E.year_ctx(Y)['S'], Y)[0])
    r, t = timeit(lambda: Vx.E.ego(F, Y))
    res['xero_click_one_house'] = dict(t, returned=len(r), house=Vx.E.keys[F])
    # ------- 全量 vs 分级+视野
    eg = json.load(open(os.path.join(HERE, 'out', 'ego_xero.json')))['bench']; egc = json.load(open(os.path.join(HERE, 'out', 'ego_city.json')))['bench']
    v0x = json.load(open(os.path.join(HERE, '..', 'rules_v0', 'out', 'xero.json'))); v0c = json.load(open(os.path.join(HERE, '..', 'rules_v0', 'out', 'city.json')))
    res['full_vs_tiered'] = dict(
        xero=dict(v0_edges_per_year=round(v0x['edges_total'] / 21), v0_seconds_per_year=round(v0x['seconds']['rules'] / 21, 2),
                  full_ego_all_households=dict(relations=round(eg['households_in_year'] * eg['relations_per_household']['mean']),
                                               ms=round(eg['households_in_year'] * eg['full_ego_ms']['mean'])),
                  zoom1_whole_xero=dict(relations_evaluated=None, returned=res['xero_full_zoom1']['returned'], ms=res['xero_full_zoom1']['mean_ms'])),
        city=dict(v0_edges_per_year=round(v0c['edges_total'] / 21), full_ego_all_households=dict(relations=round(egc['households_in_year'] * egc['relations_per_household']['mean']),
                  ms=round(egc['households_in_year'] * egc['full_ego_ms']['mean'])), zoom0=dict(returned=res['city_full_zoom0']['returned'], ms=res['city_full_zoom0']['mean_ms'])))
    Vx.count.clear(); Vx.query(full(Vx.E), 1, Y, (4, 800)); res['full_vs_tiered']['xero']['zoom1_whole_xero']['relations_evaluated'] = Vx.count['evaluated']
    # ------- 前 8 名在分级后还在不在
    res['top8_retention'] = {}
    for mode in ('v1', 'compat'):
        V = Vx if mode == 'v1' else View('xero', 'compat')
        picks = json.load(open(os.path.join(HERE, 'out', f'xero_{mode}.json')))['picks']
        rr = []
        for p in picks:
            Fa = V.E.key2f[p['a']]; Fb = V.E.key2f.get(p['b'], -1)
            ys = p['years']; kept = collections.Counter()
            for Yp in ys:
                for kk in (1, 3, 4, 5):
                    sel = V._lod1(np.array(sorted({Fa} | ({Fb} if Fb >= 0 else set()))), Yp, V.E.year_ctx(Yp), kk, 10 ** 9)
                    if any(t >= 9 and ((f == Fa and o == Fb) or (f == Fb and o == Fa)) for f, o, t, s in sel): kept[f'lod1_k{kk}'] += 1
                for N in (1, 3, 5):
                    sel = V.query((-1e9, -1e9, 1e9, 1e9), 0, Yp, (N, 10 ** 9))
                    if any({fa, fb} == {Fa, Fb} or (Fb < 0 and fa == Fa) for _, ci, fa, fb, sc in sel): kept[f'lod0_N{N}'] += 1
            rr.append(dict(a=p['a'], b=p['b'], score=p['score'], years=len(ys), kept_years={k: f'{v}/{len(ys)}' for k, v in sorted(kept.items())}))
        res['top8_retention'][mode] = rr
    json.dump(res, open(os.path.join(HERE, 'out', 'view.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
