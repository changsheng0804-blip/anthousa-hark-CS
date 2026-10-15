"""规则预演 v3 · 户籍 + 治理树上的交叉点：
  ① v1 交叉点复现率：v1 引擎原样跑（只读复用 rules_v1/engine.py + run.py 的打分），但「谁有房、谁是房东」换成户籍册
     （房主 = 登记账本房屋里搬来最早的一户，房东 = 本屋房主），「缺男丁」换成 14 岁口径。复现 = 同一对人家、同一组模式、同样年份。
  ② 新增政治交叉点 = 治理树上的利益冲突位置（一户同时站在两条线上），全部是户籍字段的查询：
     坊长/区长兼房东、兼债主、兼恩主 · 异派坊长点名征工 · 坊长征自家租户 · 坊长治下被拆（异派加重）· 区长同乡坊长
     · 房主有饼、缺男丁租户无饼（门内分配）· 教区长老与坊长异派同坊 · 一户多帽
  ③ 骨架分布（前 5 占比）、前 8 名。
usage: python3 politics.py xero|city|sample
"""
import os, sys, json, time, collections, math, types, resource
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import registry as RG  # noqa: E402
import edicts as ED  # noqa: E402
from engine import Engine  # noqa: E402
import importlib.util as _iu  # noqa: E402
_sp = _iu.spec_from_file_location('run_v1', os.path.join(RG.V1, 'run.py')); RUN = _iu.module_from_spec(_sp); _sp.loader.exec_module(RUN)
CACHE = RG.prep.CACHE
TMP = '/tmp/rules_v3_tmp'; os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(TMP, 'out'), exist_ok=True)


class RegEngine(Engine):
    """v1 引擎，只换三处输入：有房（户籍房主，逐年）、房东（本屋房主）、缺男丁（14 岁）。规则、参数、打分不动。"""
    G = None; YRS = None; OVR = 'both'      # 对照：none（应与 v1 逐条相同，检验接线）/ kids（只换 14 岁）/ owner（只换房主房东）/ both
    def __init__(self, scope, P, mode):
        super().__init__(scope, P, mode)
        G, yrs = self.G, self.YRS
        self.M = dict(self.M)
        if self.OVR in ('kids', 'both'): self.M['kids'] = G.kids14
        self.ownY = {}; self.llY = {}
        for Y, R in yrs.items():
            o = np.zeros(G.NF, bool); o[R['S'][R['own']]] = True; self.ownY[Y] = o
            l = np.full(G.NF, -1, np.int64); l[R['S'][~R['own']]] = R['owner'][~R['own']]; self.llY[Y] = l
        self.keep = {}

    def year(self, Y, need_pairtypes=True):
        if self.OVR in ('owner', 'both'): self.owner = self.ownY[Y]
        self._ll_prev = None
        Yd = super().year(Y, need_pairtypes)
        S = Yd['S']
        self.keep[Y] = dict(patron=np.where(Yd['patron'] >= 0, S[np.maximum(Yd['patron'], 0)], -1), S=S,
                            debts=[(int(S[a]), int(S[b])) for a, b in Yd['debts']])
        return Yd

    def _landlord(self, Yd):
        if self.OVR not in ('owner', 'both'): return super()._landlord(Yd)
        ll = self.llY[Yd['Y']][Yd['S']]
        return np.where(ll >= 0, Yd['loc'][np.maximum(ll, 0)], -1)

    def _debt_of(self, hy):
        if self.OVR not in ('owner', 'both'): return super()._debt_of(hy)
        save = self.owner; self.owner = self.ownY[hy]
        try: return super()._debt_of(hy)
        finally: self.owner = save


W = {'坊长兼房东': 1.0, '坊长兼债主': 2.5, '坊长兼恩主': 2.0, '区长兼房东': 1.5, '区长兼债主': 3.0, '区长兼恩主': 2.5,
     '异派坊长点名征工': 2.5, '坊长征自家租户': 2.5, '坊长治下被拆': 2.0, '异派坊长治下被拆': 3.0, '区长同乡坊长': 1.5,
     '房主有饼·缺男丁租户无饼': 2.0, '教区长老与坊长异派同坊': 1.0, '一户多帽': 1.5}
EVENT_YEARS = {51, 54, 57, 62, 64, 65}


def political(G, yrs, keep):
    hits = collections.defaultdict(lambda: collections.defaultdict(set))   # (O, H) → 模式 → 年
    role = {}
    def add(name, O, H, Y, r):
        hits[(int(O), H if isinstance(H, str) else int(H))][name].add(Y); role.setdefault((int(O), H if isinstance(H, str) else int(H)), r)
    pick57, _ = ED.corvee(G, yrs[57])
    for Y in range(50, 71):
        R = yrs[Y]; S = R['S']; n = len(S); loc = R['loc']
        fz = R['offices']['fang']; dz = R['offices']['district']; ez = R['offices']['elder']; gz = R['offices']['guild']
        myf = fz[R['fang']]; myd = dz[R['dist']]
        ten = ~R['own']; ow = R['owner']
        for O_arr, lab, r in ((myf, '坊长', '坊长-户'), (myd, '区长', '区长-户')):
            m = ten & (ow == O_arr) & (O_arr >= 0)
            for O, H in zip(O_arr[m].tolist(), S[m].tolist()): add(lab + '兼房东', O, H, Y, r)
            assert np.array_equal(keep[Y]['S'], S); pm = keep[Y]['patron']
            m = (pm >= 0) & (pm == O_arr)
            for O, H in zip(O_arr[m].tolist(), S[m].tolist()): add(lab + '兼恩主', O, H, Y, r)
            for lo, bo in keep[Y]['debts']:
                i = loc[bo]
                if i >= 0 and O_arr[i] == lo: add(lab + '兼债主', lo, bo, Y, r)
        if Y == 57:
            idx = np.nonzero(pick57)[0]
            for i in idx.tolist():
                O = myf[i]
                if O < 0: continue
                if G.M['ff'][O] != R['faith'][i]: add('异派坊长点名征工', O, S[i], Y, '坊长-户')
                if ow[i] == O and not R['own'][i]: add('坊长征自家租户', O, S[i], Y, '坊长-户')
        if Y in (54, 57, 62, 65):
            ev = ED.evictions(G, yrs, Y); Rp = yrs[Y - 1]
            for H in ev['households']:
                i = Rp['loc'][H]; O = Rp['offices']['fang'][Rp['fang'][i]]
                if O < 0 or O == H: continue
                add('异派坊长治下被拆' if G.M['ff'][O] != Rp['faith'][i] else '坊长治下被拆', O, H, Y, '坊长-户')
        # 区长同乡坊长
        local = G.origins.index('本城生') if '本城生' in G.origins else -99
        for f in range(G.NFang):
            O = fz[f]; D = dz[G.fang_dist[f]]
            if O >= 0 and D >= 0 and G.M['fo'][O] == G.M['fo'][D] and G.M['fo'][O] != local: add('区长同乡坊长', D, O, Y, '区长-坊长')
            for fa in (0, 1):
                E = ez[f * 3 + fa]
                if E >= 0 and O >= 0 and E != O and G.M['ff'][E] != G.M['ff'][O]: add('教区长老与坊长异派同坊', O, E, Y, '坊长-长老')
        # 门内分配
        full = R['fed'] >= R['size'] - 1e-9
        m = ten & R['needy'] & ~full
        oi = loc[ow[m]]
        for O, H, ok in zip(ow[m].tolist(), S[m].tolist(), full[np.maximum(oi, 0)].tolist()):
            if ok: add('房主有饼·缺男丁租户无饼', O, H, Y, '房主-租户')
        # 一户多帽
        cnt = collections.Counter([x for x in np.r_[dz, fz, ez, gz].tolist() if x >= 0])
        for O, c in cnt.items():
            if c >= 2: add('一户多帽', O, '@多帽', Y, '单户')
    return hits, role


def score_rows(G, hits, role, v1pairs):
    rows = []
    keys = G.M['keys']
    for (O, H), pats in hits.items():
        ys = sorted({y for v in pats.values() for y in v})
        dur = 0; run = 0; prev = None
        for y in ys:
            run = run + 1 if prev is not None and y == prev + 1 else 1; dur = max(dur, run); prev = y
        sc = sum(W[p] for p in pats) + 1.5 * (len(pats) - 1) + 0.25 * min(dur, 8) + (1.0 if set(ys) & EVENT_YEARS else 0)
        kv = None
        if not isinstance(H, str):
            kv = v1pairs.get(tuple(sorted((keys[O], keys[H]))))
            if kv: sc += 1.0 + 0.5 * len(kv)        # 同一对人家在 v1 引擎（户籍版）里也有交叉点：经济社会线叠在政治线上
        fdiff = (not isinstance(H, str)) and G.M['ff'][O] != G.M['ff'][H]
        sig = '+'.join(sorted(pats)) + '|' + role[(O, H)] + '|' + ('异派' if fdiff else '同派' if not isinstance(H, str) else '-')
        rows.append(dict(O=O, H=H, a=keys[O], b=H if isinstance(H, str) else keys[H], patterns=sorted(pats), pattern_years={p: [min(v), max(v)] for p, v in pats.items()},
                         years=[ys[0], ys[-1]], n_years=len(ys), dur=dur, score=round(sc, 2), skeleton=sig, v1_patterns=sorted(kv) if kv else []))
    rows.sort(key=lambda r: (-r['score'], r['a'], str(r['b'])))
    return rows


def describe(G, yrs, r):
    def who(F, Y):
        R = yrs[Y]; i = R['loc'][F]
        st = G.M['hstreet'][G.fh[F], Y - G.YR0]
        stn = G.M['st_names'][st] if st >= 0 else '（无街名）'
        offs = [k for k, a in (('区长', R['offices']['district']), ('坊长', R['offices']['fang']), ('教区长老', R['offices']['elder']), ('行会头', R['offices']['guild'])) if F in set(a.tolist())]
        return dict(key=G.M['keys'][F], name=G.names[F] + ' 家', faith=RG.FAITHS[G.M['ff'][F]], origin=G.origins[G.M['fo'][F]], trade=G.trades[G.M['ft'][F]],
                    street=stn, district=RG.DNAME[G.dnames[G.fdist[F]]], fang=int(G.ffang[F]), role=('房主' if i >= 0 and R['own'][i] else '租户') if i >= 0 else '不在',
                    offices=offs, size=int(R['size'][i]) if i >= 0 else 0)
    best = -1; Y = r['years'][0]
    for y in range(r['years'][0], r['years'][1] + 1):     # 展示「同时成立的模式最多」的那一年
        if yrs[y]['loc'][r['O']] < 0 or (not isinstance(r['H'], str) and yrs[y]['loc'][r['H']] < 0): continue
        c = sum(1 for p, (a, b) in r['pattern_years'].items() if a <= y <= b)
        if c > best: best, Y = c, y
    d = dict(r, year_shown=Y, O_info=who(r['O'], Y))
    if not isinstance(r['H'], str): d['H_info'] = who(r['H'], Y)
    return d


def controls(scope, G, yrs):
    """拆开看复现率掉在哪：none / kids / owner 三种只换一部分输入的对照。"""
    v1 = json.load(open(os.path.join(CACHE, f'rules_v1_cross_{scope}_v1.json')))
    def k3(r): return (r['a'], r['b'], tuple(sorted(r['patterns'])), tuple(r['years']))
    def kp(r): return tuple(sorted((r['a'], r['b'])))
    V = {k3(r) for r in v1}; VP = {kp(r) for r in v1}; out = {}
    for ovr in ('none', 'kids', 'owner'):
        RegEngine.OVR = ovr
        rows, o1, E = RUN.main(scope, 'v1', os.path.join(RG.V0, 'rules.json'), quiet=True)
        new = [r.d() for r in rows]; S3 = {k3(r) for r in new}; SP = {kp(r) for r in new}
        out[ovr] = dict(crossings=len(new), exact=sum(k in S3 for k in V), same_pair=sum(k in SP for k in VP),
                        scores_equal=(ovr == 'none' and [r['score'] for r in new[:100]] == [r['score'] for r in v1[:100]]))
    RegEngine.OVR = 'both'
    return out


def main(scope):
    t0 = time.time()
    G = RG.Registry(scope); yrs, tb = G.build(40, 70)
    RegEngine.G = G; RegEngine.YRS = yrs
    P = json.load(open(os.path.join(RG.V0, 'rules.json')))
    RUN.Engine = RegEngine; RUN.HERE = TMP; RUN.prep = types.SimpleNamespace(CACHE=TMP)
    ctl = controls(scope, G, yrs)
    t1 = time.time()
    rows, o1, E = RUN.main(scope, 'v1', os.path.join(RG.V0, 'rules.json'), quiet=True)
    t_engine = time.time() - t1
    v1 = json.load(open(os.path.join(CACHE, f'rules_v1_cross_{scope}_v1.json')))
    v1out = json.load(open(os.path.join(RG.V1, 'out', f'{scope}_v1.json')))
    def k3(r): return (r['a'], r['b'], tuple(sorted(r['patterns'])), tuple(r['years']))
    def kp(r): return tuple(sorted((r['a'], r['b'])))
    new = [r.d() for r in rows]
    S3 = {k3(r) for r in new}; SP = {kp(r) for r in new}; SPP = {(kp(r), tuple(sorted(r['patterns']))) for r in new}
    rep = dict(v1=len(v1), registry=len(new),
               exact=sum(k3(r) in S3 for r in v1), same_pair=sum(kp(r) in SP for r in v1), same_pair_patterns=sum((kp(r), tuple(sorted(r['patterns']))) in SPP for r in v1),
               top100_exact=sum(k3(r) in S3 for r in v1[:100]), top100_pair=sum(kp(r) in SP for r in v1[:100]),
               top8_pair=sum(kp(r) in SP for r in v1out['picks']), top8_exact=sum(k3(r) in S3 for r in v1out['picks']),
               by_pattern_v1=dict(collections.Counter(p for r in v1 for p in r['patterns'])), by_pattern_registry=dict(collections.Counter(p for r in new for p in r['patterns'])),
               engine_seconds=round(t_engine, 2), controls=ctl)
    # 漏掉 / 新增的按模式
    miss = collections.Counter(p for r in v1 if k3(r) not in S3 for p in r['patterns'])
    V3 = {k3(r) for r in v1}
    gain = collections.Counter(p for r in new if k3(r) not in V3 for p in r['patterns'])
    rep['lost_by_pattern'] = dict(miss); rep['new_by_pattern'] = dict(gain)
    rep['registry_top8'] = [dict(a=p['a'], b=p['b'], patterns=p['patterns'], years=[p['years'][0], p['years'][-1]], score=p['score']) for p in o1['picks']]
    v1pairs = collections.defaultdict(set)
    for r in new:
        if not str(r['b']).startswith('@'): v1pairs[kp(r)] |= set(r['patterns'])
    # ---------- 政治交叉点
    t2 = time.perf_counter()
    hits, role = political(G, yrs, E.keep)
    prow = score_rows(G, hits, role, v1pairs)
    t_pol = time.perf_counter() - t2
    sk = collections.Counter(r['skeleton'] for r in prow)
    tot = len(prow)
    used = set(); usk = collections.Counter(); picks = []
    for r in prow:
        ks = {r['O']} | ({r['H']} if not isinstance(r['H'], str) else set())
        if ks & used or usk[r['skeleton']] >= 2: continue
        picks.append(describe(G, yrs, r)); used |= ks; usk[r['skeleton']] += 1
        if len(picks) == 8: break
    pol = dict(crossings=tot, by_pattern=dict(collections.Counter(p for r in prow for p in r['patterns'])),
               multi_pattern=sum(1 for r in prow if len(r['patterns']) >= 2), with_v1_cross_on_same_pair=sum(1 for r in prow if r['v1_patterns']),
               skeletons=len(sk), top5=[[k, v, round(v / tot, 3)] for k, v in sk.most_common(5)], top5_share=round(sum(v for _, v in sk.most_common(5)) / max(tot, 1), 3),
               score_hist=dict(sorted(collections.Counter(int(r['score']) for r in prow).items())), seconds=round(t_pol, 3), picks=picks, top30=prow[:30])
    out = dict(scope=scope, v1_reproduction=rep, political=pol, seconds_total=round(time.time() - t0, 2),
               peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1))
    json.dump(out, open(os.path.join(HERE, 'out', f'politics_{scope}.json'), 'w'), ensure_ascii=False, indent=1, default=int)
    print(json.dumps({k: v for k, v in rep.items() if k not in ('by_pattern_v1', 'by_pattern_registry')}, ensure_ascii=False, default=int))
    print(json.dumps({k: v for k, v in pol.items() if k not in ('picks', 'top30')}, ensure_ascii=False, default=int))
    for p in picks: print(p['score'], p['patterns'], p['a'], p['b'], p['years'], p['O_info']['name'], p['O_info']['offices'], p.get('H_info', {}).get('name'))


if __name__ == '__main__':
    main(sys.argv[1])
