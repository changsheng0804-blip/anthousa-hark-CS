"""规则预演 v1 · 运行器
usage: python3 run.py SCOPE [--mode=compat|v1] [--params=../rules_v0/rules.json]
  compat：与 v0 调参版（rules_v0/rules.json）同规则、同打分，用来核对等价性（运水人边按需查进打分）。
  v1    ：去掉运水人边（只留户属性）、学徒拜异派师傅降权（见 score_v1）。
输出 out/SCOPE_MODE.json；全部交叉点（带起止年区间）写在仓库外 ../rules_v1_cross_SCOPE_MODE.json。
"""
import sys, os, json, time, resource, collections, math
T0 = time.time()
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(1, os.path.join(HERE, '..', 'rules_v0'))
from engine import Engine, ARIAN, PAIR_PATTERNS
import cross as C0                 # v0 打分函数，只读复用
import prep

T_IMPORT = time.time() - T0


def _implied():
    out = []
    for name in PAIR_PATTERNS:
        base, _ = _PAT[name]; rn = {C0.TYPE_RULE.get(t, t) for t in base}
        out.append(sum(v for t, v in Engine.TBITS.items() if C0.TYPE_RULE[t] in rn))
    return np.array(out, np.int64)


def bits2types(b):
    return {t for t, v in Engine.TBITS.items() if b & v}


class Row:
    """一个交叉点（强关系）。只存起止年区间，不存逐年列表；d() 还原成 v0 同格式的字典。"""
    __slots__ = ('patterns', 'a', 'b', 'dur', 'score', 'rules', 'near_event', 'pyrs', 'intervals', 'fa', 'fb')
    def __init__(self, *v):
        for k, x in zip(self.__slots__, v): setattr(self, k, x)
    def __getitem__(self, k): return getattr(self, k)
    @property
    def years(self): return [y for a, b in self.intervals for y in range(a, b + 1)]
    def d(self):
        return dict(patterns=list(self.patterns), a=self.a, b=self.b, years=self.years, dur=self.dur, score=self.score, rules=list(self.rules),
                    near_event=self.near_event, pattern_years={n: [p, q] for n, p, q in self.pyrs}, intervals=self.intervals)


def intervals(ys):
    ys = sorted(set(ys)); out = []
    for y in ys:
        if out and y == out[-1][1] + 1: out[-1][1] = y
        else: out.append([y, y])
    return out


_PAT = {n: (r, t) for n, f, r, t in C0.PAIR_PATTERNS + C0.HOUSE_PATTERNS}
_PROX = {}


def fast_score(prs, pair_types, snap, y0, y1):
    """与 v0 cross.score_pair 逐项相同的公式，只是把「账本大事贴近度」按 (年, 主题, 是否阿里乌派) 缓存（全部交叉点只有几十种组合）。"""
    rules = set(); tags = set(); ys = set()
    for name, years in prs:
        base, tg = _PAT[name]
        tags |= tg; rules |= {C0.TYPE_RULE.get(t, t) for t in base}; ys |= set(years)
    rules |= {C0.TYPE_RULE[t] for t in pair_types}
    wr = sum(0.5 if r in C0.BACKGROUND else 1.0 for r in rules)
    dur = C0.longest_run(ys)
    arian = any(s.get('arian') for s in snap.values())
    ft = frozenset(tags); prox = 0.0; ev = None
    for y in ys:
        kk = (y, ft, arian)
        if kk not in _PROX:
            bp = 0.0; be = None
            for ey, (txt, w) in C0.LEDGER_EVENTS.items():
                et = C0.EVENT_TAGS.get(ey, set())
                rel = 1.0 if (et & tags) and ('faith' not in et or arian) else 0.3
                v = w * rel * math.exp(-abs(y - ey))
                if v > bp: bp, be = v, ey
            _PROX[kk] = (bp, be)
        v, e = _PROX[kk]
        if v > prox: prox, ev = v, e
    pers = 0.0
    for s in snap.values():
        if s['died_in']: pers += 1.0
        if s['demolished']: pers += 1.5
        if s['was_needy']: pers += 0.5
    turn = 0.5 * (min(ys) > y0) + 0.5 * (max(ys) < y1)
    sc = wr + 1.5 * (len(prs) - 1) + 0.25 * min(dur, 8) + prox + pers + turn
    return round(sc, 2), sorted(rules), dur, ev


def score_v1(prs, ptypes, snap, y0, y1):
    """v1 打分：v0 的公式，但 (1) 运水人边不算（pair_types 里已去掉）；(2)「学徒拜异派师傅」降权：
    只有 51 年后阿里乌派对尼西亚派的那几年算一个模式（多模式加分 1.5 → 0.75），其余年份的异派只算半条「工钱与学徒」。"""
    sc, rl, dur, ev = fast_score(prs, ptypes, snap, y0, y1)
    names = [n for n, _ in prs]
    if '学徒拜异派师傅' in names:
        sc -= 0.75 if len(prs) > 1 else 0
        sc -= 0.5   # 工钱与学徒 算半条
    return round(sc, 2), rl, dur, ev


def save_strong(tag, rows, ASG, E):
    """强关系落盘（仓库外）：交叉点（两端户下标、分数、模式、起止年区间）+ 制度分配区间。弱关系一条不存。"""
    import pickle
    asg = collections.defaultdict(set)
    for kind, A, B, Y in ASG:
        for a, b in zip(A.tolist(), B.tolist()): asg[(kind, a, b)].add(Y)
    asg_rows = [(k, a, b, iv[0], iv[1]) for (k, a, b), ys in asg.items() for iv in intervals(ys)]
    cr = [(r.fa, r.fb, r.b if r.fb < 0 else None, r.score, r.patterns, r.intervals) for r in rows]
    pickle.dump(dict(cross=cr, assign=asg_rows), open(os.path.join(prep.CACHE, f'rules_v1_strong_{tag}.pkl'), 'wb'))


def main(scope, mode='compat', pfile=None, quiet=False):
    t0 = time.time()
    P = json.load(open(pfile or os.path.join(HERE, '..', 'rules_v0', 'rules.json')))
    E = Engine(scope, P, mode)
    t_load = time.time() - t0
    y0, y1 = P['years']
    NF = len(E.keys); KR = E.keyrank
    IMPLIED = _implied()
    H_pid, H_code, H_Y = [], [], []         # 成对交叉的命中：模式、无序对编码（甲键 < 乙键）、年
    occ_h = collections.defaultdict(set)    # 单户 × 机构
    ptu = {}                                # 无序对 → 弱关系类型位（只在命中年按需查）
    hh = {}; t_rules = t_types = 0.0; n_hits = 0; ASG = []
    for Y in range(y0, y1 + 1):
        a = time.time()
        Yd = E.year(Y)
        t_rules += time.time() - a
        hh[Y] = Yd['n']
        a = time.time()
        # 制度分配（租约 / 门客 / 债）：每户至多一两条，按年记下，最后压成起止年区间，供单户自我网和视野查询直接读
        S_ = Yd['S']
        for kind, arr in (('landlord', Yd['landlord']), ('patron', Yd['patron'])):
            i_ = np.nonzero(arr >= 0)[0]; ASG.append((kind, S_[arr[i_]], S_[i_], Y))
        if Yd['debts']:
            d_ = np.array(Yd['debts']); ASG.append(('debt', S_[d_[:, 0]], S_[d_[:, 1]], Y))
        if Yd['hits']:
            pid = np.concatenate([np.full(len(p), i) for i, p, q in Yd['hits']])
            p = np.concatenate([p for i, p, q in Yd['hits']]); q = np.concatenate([q for i, p, q in Yd['hits']])
            sw = KR[p] > KR[q]; a_ = np.where(sw, q, p); b_ = np.where(sw, p, q)
            code = a_.astype(np.int64) * NF + b_
            H_pid.append(pid); H_code.append(code); H_Y.append(np.full(len(code), Y)); n_hits += len(code)
            # 本年命中模式已蕴含的规则（如同水异粮蕴含「同一口水」「面包」），这些类型不用再按需查
            uc, inv = np.unique(code, return_inverse=True)
            imp = np.zeros(len(uc), np.int64); np.bitwise_or.at(imp, inv, IMPLIED[pid])
            loc = Yd['loc']
            bits = E.pair_types(Yd, loc[uc // NF], loc[uc % NF], carrier=(mode == 'compat'), need=~imp)
            for c, bt in zip(uc.tolist(), bits.tolist()): ptu[c] = ptu.get(c, 0) | bt
        for name, p, nd in Yd['hits_h']:
            occ_h[(name, (p, nd))].add(Y); n_hits += 1
        t_types += time.time() - a
    # ---- 合成强关系 + 打分（公式与 v0 finish/score_pair 同）
    a = time.time()
    M = E.M; keys = E.keys
    by_pair = collections.defaultdict(list)
    if H_pid:
        pid = np.concatenate(H_pid); code = np.concatenate(H_code); YY = np.concatenate(H_Y)
        o = np.lexsort((YY, pid, code)); pid, code, YY = pid[o], code[o], YY[o]
        E.hits = (pid, code, YY, NF)            # 留给 skeleton.py 做骨架分析（不落盘）
        brk = np.nonzero((np.diff(code) != 0) | (np.diff(pid) != 0))[0] + 1
        st = np.r_[0, brk]; en = np.r_[brk, len(code)]
        YL = YY.tolist()
        for s_, e_, c, pi in zip(st.tolist(), en.tolist(), code[st].tolist(), pid[st].tolist()):
            by_pair[(c // NF, c % NF)].append((PAIR_PATTERNS[pi], sorted(set(YL[s_:e_]))))
    for (name, k), ys in occ_h.items(): by_pair[k].append((name, sorted(ys)))
    yi0 = y0 - E.YR0; yi1 = y1 - E.YR0 + 1
    pres = M['present'][:, yi0:yi1]; dth = (M['deaths'][:, yi0:yi1] > 0) & pres
    nd_ = ((M['men'][:, yi0:yi1] == 0) & (M['kids'][:, yi0:yi1] > 0)) & pres
    demol = E.fdest <= y1 + 1; arian = M['ff'] == ARIAN
    hasflag = pres.any(1)
    # 每户在窗口里「有丧的年」「缺男丁的年」压成位掩码（Python int），每个交叉点只做一次与运算
    w = (1 << np.arange(y1 - y0 + 1)).astype(np.int64)
    dmask = (dth * w).sum(1).tolist(); nmask = (nd_ * w).sum(1).tolist()
    demol_l = demol.tolist(); arian_l = arian.tolist(); hasflag_l = hasflag.tolist()
    rows = []; INTERN = {}
    sf = score_v1 if mode == 'v1' else fast_score
    for k, prs in by_pair.items():
        ys = sorted({y for _, yy in prs for y in yy}); ym = 0
        for y_ in ys: ym |= 1 << (y_ - y0)
        snap = {}
        fams = [k[0]] if isinstance(k[1], str) else list(k)
        for F in fams:
            if not hasflag_l[F]: continue
            snap[keys[F]] = dict(died_in=bool(dmask[F] & ym), was_needy=bool(nmask[F] & ym), demolished=demol_l[F], arian=arian_l[F])
        pc = None if isinstance(k[1], str) else k[0] * NF + k[1]
        sc, rl, dur, ev = sf(prs, bits2types(ptu.get(pc, 0)), snap, y0, y1)
        a_ = keys[k[0]]; b_ = k[1] if isinstance(k[1], str) else keys[k[1]]
        pt_ = tuple(sorted(n for n, _ in prs)); rl_ = tuple(rl)
        rows.append(Row(INTERN.setdefault(pt_, pt_), a_, b_, dur, sc, INTERN.setdefault(rl_, rl_), ev,
                        tuple((n, yy_[0], yy_[-1]) for n, yy_ in prs), intervals(ys), int(k[0]), (-1 if isinstance(k[1], str) else int(k[1]))))
    E.ptu = ptu; E.occ_h = occ_h
    del by_pair
    rows.sort(key=lambda r: (-r['score'], r['a'], r['b']))
    t_score = time.time() - a
    # 骨架（v0 定义）与前 8
    def skel(r):
        tr = [M['ft'][r['fa']]] + ([M['ft'][r['fb']]] if r['fb'] >= 0 else ['@'])
        fa = sorted(('阿' if arian[f] else '非') if f >= 0 else '@' for f in (r['fa'], r['fb']))
        return '|'.join(r['patterns']) + ('|同行' if tr[0] == tr[1] else '|异行') + '|' + ''.join(fa)
    used = set(); usk = collections.Counter(); picks = []
    for r in rows:
        ks = {r['a'], r['b']} - ({r['b']} if r['b'].startswith('@') else set())
        if ks & used or usk[skel(r)] >= 2: continue
        picks.append(dict(r.d(), skeleton=skel(r))); used |= ks; usk[skel(r)] += 1
        if len(picks) == 8: break
    elapsed = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    sk_all = collections.Counter(skel(r) for r in rows)
    out = dict(scope=scope, mode=mode, hard_years=E.hard_years, households_per_year=hh, crossings=len(rows), pattern_hits=n_hits,
               crossings_by_pattern=dict(collections.Counter(n for r in rows for n in r['patterns'])),
               score_hist=dict(sorted(collections.Counter(int(r['score']) for r in rows).items())),
               skeletons=len(sk_all), biggest_skeletons=dict(sk_all.most_common(5)),
               picks=picks, top=[r.d() for r in rows[:60]],
               stats=dict(E.stats),
               seconds=dict(total=round(elapsed, 3), python_import=round(T_IMPORT, 3), load_cache=round(t_load, 3), rules_and_patterns=round(t_rules, 3),
                            pair_types_on_demand=round(t_types, 3), score=round(t_score, 3)),
               peak_rss_mb=round(rss, 1))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    tag = f'{scope}_{mode}'
    save_strong(tag, rows, ASG, E)
    json.dump(out, open(os.path.join(HERE, 'out', tag + '.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump([r.d() for r in rows], open(os.path.join(prep.CACHE, f'rules_v1_cross_{tag}.json'), 'w'), ensure_ascii=False)
    if not quiet:
        print(json.dumps({k: out[k] for k in ('scope', 'mode', 'hard_years', 'crossings', 'pattern_hits', 'crossings_by_pattern', 'skeletons', 'stats', 'seconds', 'peak_rss_mb')}, ensure_ascii=False))
    return rows, out, E


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    mode = next((x[7:] for x in sys.argv if x.startswith('--mode=')), 'compat')
    pf = next((x[9:] for x in sys.argv if x.startswith('--params=')), None)
    main(a[0], mode, pf)
