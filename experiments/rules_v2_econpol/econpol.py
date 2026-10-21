"""规则预演 v2 · 只做经济 + 政治关系的预演（层级 / 星形骨架），不算任何户与户之间的弱关系网。

结构（每年）：
  第 0 层 机构：官府、尼西亚派教会、阿里乌派教会、寡妇孤儿之家（65 起）、城门兵营、各行会（每个行当一个）
  第 1 层 中间节点：配给点（炉，挂官府）、蓄水池（修水，挂官府）、大房东、恩主、债主、师傅（作坊主）——后四类本身也是户
  第 2 层 普通户：每户只有指向上层的「父指针」，没有户与户之间的网
每户每年的槽位（常数个）：
  房东 0–1、恩主 0–1、债主 0–2（实测 ≤1）、师傅 0–1、配给点 0–1（只有有房户，面包跟房子走）、教区 0–1（还拜旧神的没有）、
  行会 1、兵营 0–1、官府事件 0–3（拆房 / 凑铜板 / 征工）
规则与参数与 v0 调参版、v1 完全相同（rules_v0/rules.json）；房东/恩主/债三条顺序贪心直接调用 rules_v1/engine.py 的实现（只读复用）。
usage: python3 econpol.py sample|xero|city [--ego]
"""
import os, sys, json, time, resource, collections, math, pickle, gzip
T0 = time.time()
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(HERE, '..', 'rules_v1'); V0 = os.path.join(HERE, '..', 'rules_v0')
sys.path.insert(0, V1); sys.path.insert(1, V0)
from engine import Engine, ARIAN, NICENE, PAGAN, INF  # noqa: E402
import prep  # noqa: E402
T_IMPORT = time.time() - T0

# 每户槽位（类型 → 父节点类别）
SLOTS = ['landlord', 'patron', 'debt', 'master', 'ration', 'parish', 'guild', 'garrison', 'evicted', 'levy', 'corvee']
MUST_STORE = {'landlord', 'patron', 'debt'}        # 全城顺序贪心 + 容量：单户算不出来，必须批量算后存
LOCAL = {'master': '300px 内最近的同行师傅（无容量）：单户 KD 现查',
         'ration': '最近的炉（只看坐标 + 炉建成年）：纯函数',
         'parish': '信仰 + 年份：纯函数（是否领施舍再看缺男丁）',
         'guild': '行当：纯函数',
         'garrison': '街区功能 / 离兵营距离 / 儿子当兵年：纯函数',
         'evicted': '房子拆毁年：纯函数', 'levy': '行当 + 离蓄水池距离 + 年：纯函数',
         'corvee': '同街租户按成年男人数排前 2：只看本街'}


class EconPol(Engine):
    """只算经济政治骨架。继承 v1 引擎只为复用它的数据装载与三条顺序贪心（_landlord/_patron/_debt_of）和 _nodes。"""
    def _chain_csr(self):          # 同乡链不是经济政治关系：骨架里不算
        self.ch_s = self.ch_t = np.zeros(0, np.int64)

    def year_ep(self, Y):
        M = self.M; P = self.P; yi = Y - self.YR0
        tm = collections.OrderedDict(); t = time.perf_counter()
        def tick(name):
            nonlocal t
            u = time.perf_counter(); tm[name] = tm.get(name, 0) + u - t; t = u
        S = np.nonzero(M['present'][:, yi])[0]; n = len(S)
        loc = np.full(len(M['fB']), -1, np.int64); loc[S] = np.arange(n)
        x, y, lx, ly = self.fx[S], self.fy[S], self.flx[S], self.fly[S]
        st = M['hstreet'][M['fh'][S], yi]; trade = M['ft'][S]; faith = M['ff'][S]; B = M['fB'][S]
        own = self.owner[S]; size = M['size'][S, yi]; men = M['men'][S, yi]; kids = M['kids'][S, yi]
        dth = M['deaths'][S, yi] > 0; needy = (men == 0) & (kids > 0); fnn = self.ffn[S]
        tk = np.empty(n, np.int64); tk[np.lexsort((np.arange(n), np.floor(y / 120), np.floor(x / 120)))] = np.arange(n)
        Yd = dict(Y=Y, S=S, tk=tk, loc=loc, n=n, x=x, y=y, st=st, trade=trade, faith=faith, own=own, needy=needy, dth=dth, B=B)
        tick('户状态切片')
        # ---- 第 0 层：教区（信仰 → 本派教会；施舍 = 缺男丁 ∧ 本派此年有施舍的地方）
        C = P['church']
        parish = np.full(n, -1, np.int8)                 # 0 尼西亚派教会, 1 阿里乌派教会
        parish[faith == NICENE] = 0; parish[faith == ARIAN] = 1
        if Y >= C['xenon_from']: has_alms = np.ones(n, bool)
        else:
            has_alms = np.zeros(n, bool)
            if Y >= C['nicene_church_from']: has_alms |= faith == NICENE
            if Y < C['arian_out_from'] or Y >= C['arian_church_from']: has_alms |= faith == ARIAN
        alms = needy & has_alms
        alms_src = np.full(n, '', object)
        if Y >= C['xenon_from']: alms_src[needy] = '@寡妇孤儿之家'
        else:
            alms_src[needy & (faith == NICENE) & (Y >= C['nicene_church_from'])] = '@阿纳斯塔西娅的执事'
            if Y < C['arian_out_from']: alms_src[needy & (faith == ARIAN)] = '@城里的阿里乌派教堂'
            elif Y >= C['arian_church_from']: alms_src[needy & (faith == ARIAN)] = '@城门外砖堂'
        tick('教区与施舍')
        # ---- 配给点：有房户 → 最近的已建成的炉（面包跟房子走；租户没有）
        ration = np.full(n, -1, np.int64)
        om = np.nonzero(self.ob <= Y)[0]; ow = np.nonzero(own)[0]
        if len(om) and len(ow):
            kk = min(3, len(om))
            _, oi = cKDTree(np.c_[self.ox[om], self.oy[om]]).query(np.c_[x[ow], y[ow]], k=kk)
            oi = om[np.asarray(oi).reshape(len(ow), -1)]
            dd = np.hypot(self.ox[oi] - x[ow][:, None], self.oy[oi] - y[ow][:, None])
            j = np.lexsort((oi, dd), axis=1)[:, 0]
            ration[ow] = oi[np.arange(len(ow)), j]
        tick('配给点（炉）')
        # ---- 房东 / 恩主 / 债：v1 的顺序贪心（只读复用）
        landlord = self._landlord(Yd); tick('房东（顺序贪心）')
        patron = self._patron(Yd, size, dth, fnn, B, Y); tick('恩主（顺序贪心）')
        debts = []
        for hy in self.hard_years:
            if Y - P['debt']['years'] < hy <= Y:
                for lg, bg in self._debt_of(hy):
                    if loc[lg] >= 0 and loc[bg] >= 0: debts.append((int(loc[lg]), int(loc[bg])))
        debts = list(dict.fromkeys(debts)); tick('债')
        # ---- 师傅：没有成年男人、有 12–15 岁男孩的人家 → 300px 内最近的同行师傅（否则最近的师傅）
        Ap = P['apprentice']; app = np.full(n, -1)
        q = np.nonzero((men == 0) & M['boy'][S, yi])[0]
        if len(q):
            mm = np.nonzero(men > 0)[0]
            if len(mm):
                tm1 = cKDTree(np.c_[x[mm] + trade[mm] * 1e5, y[mm]])
                _, i1 = tm1.query(np.c_[x[q] + trade[q] * 1e5, y[q]], k=min(4, len(mm)), distance_upper_bound=Ap['radius'] * 1.0001)
                ta = cKDTree(np.c_[x[mm], y[mm]])
                _, i2 = ta.query(np.c_[x[q], y[q]], k=min(4, len(mm)), distance_upper_bound=Ap['radius'] * 1.0001)
                i1 = np.asarray(i1).reshape(len(q), -1); i2 = np.asarray(i2).reshape(len(q), -1)
                for r_, s_ in enumerate(q):
                    best = self._nearest(i1[r_], mm, x[s_], y[s_], x, y, Ap['radius'], same=trade[s_], trade=trade, tk=tk)
                    if best < 0: best = self._nearest(i2[r_], mm, x[s_], y[s_], x, y, Ap['radius'], tk=tk)
                    app[s_] = best
        tick('师傅（学徒）')
        # ---- 官府事件 + 兵营（v1 _nodes，只读复用）
        node = self._nodes(Yd, alms_src, men, dth, needy, lx, ly)
        ev = {k: np.zeros(n, bool) for k in ('evicted', 'levy', 'corvee', 'garrison')}
        for i, nd in enumerate(node):
            if nd:
                for k, _ in nd:
                    if k in ev: ev[k][i] = True
        tick('官府事件与兵营')
        return dict(Yd=Yd, parish=parish, alms=alms, alms_src=alms_src, ration=ration, landlord=landlord, patron=patron,
                    debts=debts, app=app, ev=ev, node=node, tm=tm, men=men, size=size)


def count_year(E, R):
    """一年的节点数 / 边数（层级结构）。"""
    Yd = R['Yd']; n = Yd['n']; Y = Yd['Y']
    e = collections.Counter()
    e['landlord'] = int((R['landlord'] >= 0).sum()); e['patron'] = int((R['patron'] >= 0).sum()); e['debt'] = len(R['debts'])
    e['master'] = int((R['app'] >= 0).sum()); e['ration'] = int((R['ration'] >= 0).sum()); e['parish'] = int((R['parish'] >= 0).sum())
    e['guild'] = n
    for k in ('garrison', 'evicted', 'levy', 'corvee'): e[k] = int(R['ev'][k].sum())
    ovens_live = int((E.ob <= Y).sum()); cis = int(sum(1 for w in E.water if w['kind'] == 'cistern' and w['built'] <= Y))
    # 第 1 层 → 第 0 层：配给点、蓄水池挂官府
    e['L1→官府'] = ovens_live + cis
    inst = 1 + 2 + (1 if Y >= E.P['church']['xenon_from'] else 0) + 1 + len(set(Yd['trade'].tolist()))
    mid = dict(landlords=len(set(R['landlord'][R['landlord'] >= 0].tolist())), patrons=len(set(R['patron'][R['patron'] >= 0].tolist())),
               lenders=len({a for a, b in R['debts']}), masters=len(set(R['app'][R['app'] >= 0].tolist())), ovens=ovens_live, cisterns=cis)
    mid_households = len(set(R['landlord'][R['landlord'] >= 0].tolist()) | set(R['patron'][R['patron'] >= 0].tolist()) | {a for a, b in R['debts']} | set(R['app'][R['app'] >= 0].tolist()))
    slots = np.zeros(n, np.int16)
    for arr in (R['landlord'], R['patron'], R['app'], R['ration']): slots += arr >= 0
    slots += R['parish'] >= 0; slots += 1
    for k in ('garrison', 'evicted', 'levy', 'corvee'): slots += R['ev'][k]
    for a, b in R['debts']: slots[b] += 1
    dmax = collections.Counter(b for a, b in R['debts'])
    return dict(households=n, institutions=inst, mid_nodes=mid, mid_households=mid_households, edges=dict(e),
                hh_edges=int(sum(v for k, v in e.items() if k != 'L1→官府')), edges_total=int(sum(e.values())),
                per_household_max=int(slots.max()) if n else 0, per_household_mean=round(float(slots.mean()), 3) if n else 0,
                debts_per_borrower_max=max(dmax.values()) if dmax else 0,
                tenants_per_landlord_max=int(np.bincount(R['landlord'][R['landlord'] >= 0]).max()) if (R['landlord'] >= 0).any() else 0)


def intervals(ys):
    ys = sorted(set(ys)); out = []
    for y_ in ys:
        if out and y_ == out[-1][1] + 1: out[-1][1] = y_
        else: out.append([y_, y_])
    return out


def main(scope, ego=False):
    t0 = time.time()
    P = json.load(open(os.path.join(V0, 'rules.json')))
    E = EconPol(scope, P, 'v1')
    t_load = time.time() - t0
    y0, y1 = P['years']
    tm = collections.Counter(); per_year = {}; asg = collections.defaultdict(set)
    t_rules = 0.0
    for Y in range(y0, y1 + 1):
        a = time.perf_counter()
        R = E.year_ep(Y)
        t_rules += time.perf_counter() - a
        for k, v in R['tm'].items(): tm[k] += v
        per_year[Y] = count_year(E, R)
        S = R['Yd']['S']
        # 全部槽位逐年记下 → 压成区间（只为统计「如果全存要多少」；真正必须存的只有房东/恩主/债）
        for kind, arr in (('landlord', R['landlord']), ('patron', R['patron']), ('master', R['app']), ('ration', R['ration'])):
            i_ = np.nonzero(arr >= 0)[0]
            par = S[arr[i_]] if kind != 'ration' else arr[i_]
            for c, p in zip(S[i_].tolist(), par.tolist()): asg[(kind, c, p)].add(Y)
        for c, p in zip(S.tolist(), R['parish'].tolist()):
            if p >= 0: asg[('parish', c, p)].add(Y)
        for a_, b_ in R['debts']: asg[('debt', int(S[b_]), int(S[a_]))].add(Y)
        for k in ('garrison', 'evicted', 'levy', 'corvee'):
            for c in S[R['ev'][k]].tolist(): asg[(k, c, 0)].add(Y)
    t_total = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    iv = collections.Counter(); rows = []
    for (k, c, p), ys in asg.items():
        for a_, b_ in intervals(ys): iv[k] += 1; rows.append((k, c, p, a_, b_))
    must = [r for r in rows if r[0] in MUST_STORE]
    # 存储体积：必须存的区间 7 B/条（户 3B + 父 3B + 起止年 1B，与 v1 §6 同口径）
    raw = bytearray()
    KI = {k: i for i, k in enumerate(SLOTS)}
    for k, c, p, a_, b_ in sorted(must, key=lambda r: (r[1], r[0])):
        raw += int(c).to_bytes(3, 'little') + int(p).to_bytes(3, 'little') + bytes([((a_ - 40) & 0x1f) | ((KI[k] & 0x3) << 5)])
        raw += bytes([b_ - 40])
    NF = len(E.keys); fam_live = int(E.M['present'][:, y0 - E.YR0:y1 - E.YR0 + 1].any(1).sum())
    hy = sum(v['households'] for v in per_year.values())
    edges_total = sum(v['edges_total'] for v in per_year.values()); hh_edges = sum(v['hh_edges'] for v in per_year.values())
    by_type = collections.Counter()
    for v in per_year.values(): by_type.update(v['edges'])
    out = dict(scope=scope, years=[y0, y1], household_years=hy, families_in_window=fam_live,
               edges_per_year=edges_total / len(per_year), edges_total=edges_total, household_edges_total=hh_edges,
               edges_per_household_year=round(hh_edges / hy, 3), edges_by_type=dict(by_type),
               nodes_AF60=dict(institutions=per_year[60]['institutions'], mid=per_year[60]['mid_nodes'], mid_households=per_year[60]['mid_households'], households=per_year[60]['households']),
               per_household_slots_max=max(v['per_household_max'] for v in per_year.values()),
               debts_per_borrower_max=max(v['debts_per_borrower_max'] for v in per_year.values()),
               tenants_per_landlord_max=max(v['tenants_per_landlord_max'] for v in per_year.values()),
               intervals_all=dict(iv), intervals_all_total=sum(iv.values()), intervals_must_store=len(must),
               must_store_bytes=dict(raw=len(raw), gzip=len(gzip.compress(bytes(raw), 9)), per_family_raw=round(len(raw) / fam_live, 2), per_family_gzip=round(len(gzip.compress(bytes(raw), 9)) / fam_live, 2)),
               seconds=dict(total_in_process=round(t_total, 3), python_import=round(T_IMPORT, 3), load_cache=round(t_load, 3), rules=round(t_rules, 3),
                            by_rule={k: round(v, 3) for k, v in sorted(tm.items(), key=lambda kv: -kv[1])}),
               peak_rss_mb=round(rss, 1), per_year={str(k): v for k, v in per_year.items()})
    if ego:
        out['ego'] = ego_bench(E, P, rows)
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, 'out', f'skeleton_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    pickle.dump(dict(must=must), open(os.path.join(prep.CACHE, f'rules_v2_must_{scope}.pkl'), 'wb'))
    print(json.dumps({k: out[k] for k in ('scope', 'household_years', 'edges_total', 'edges_per_household_year', 'edges_by_type', 'nodes_AF60',
                                          'per_household_slots_max', 'intervals_all_total', 'intervals_must_store', 'must_store_bytes', 'seconds', 'peak_rss_mb')}, ensure_ascii=False))
    return out, E, rows


class EgoEP:
    """单户经济政治处境按需现算：只读存好的房东/恩主/债区间，其余槽位从户属性 + 坐标现算。
    年上下文（切换年份时做一次）：在住户、有房户、建好的炉、师傅候选的 KD 树、各街租户表。"""
    def __init__(self, E, must):
        self.E = E; self.M = E.M; self.store = collections.defaultdict(list)
        for k, c, p, a, b in must: self.store[c].append((k, p, a, b))
        self.Y = None

    def year_ctx(self, Y):
        E, M = self.E, self.M; yi = Y - E.YR0
        S = np.nonzero(M['present'][:, yi])[0]
        men = M['men'][S, yi]; mm = S[men > 0]
        self.mm = mm
        self.tm_trade = cKDTree(np.c_[E.fx[mm] + M['ft'][mm] * 1e5, E.fy[mm]]) if len(mm) else None
        self.tm_any = cKDTree(np.c_[E.fx[mm], E.fy[mm]]) if len(mm) else None
        om = np.nonzero(E.ob <= Y)[0]; self.om = om
        self.otree = cKDTree(np.c_[E.ox[om], E.oy[om]]) if len(om) else None
        st = M['hstreet'][M['fh'][S], yi]; own = E.owner[S]
        self.street_ten = collections.defaultdict(list)
        if Y == E.P['office']['corvee_year']:
            for F, s_, o_, m_ in zip(S.tolist(), st.tolist(), own.tolist(), men.tolist()):
                if not o_ and m_ >= 1 and s_ >= 0: self.street_ten[s_].append(F)
        self.Y = Y

    def ego(self, F, Y):
        if self.Y != Y: self.year_ctx(Y)
        E, M = self.E, self.M; yi = Y - E.YR0; P = E.P; out = []
        for k, p, a, b in self.store.get(F, ()):
            if a <= Y <= b: out.append((k, p))
        own = E.owner[F]; men = M['men'][F, yi]; kids = M['kids'][F, yi]; fa = M['ff'][F]
        if own and self.otree is not None:
            _, j = self.otree.query([E.fx[F], E.fy[F]], k=min(3, len(self.om))); oi = self.om[np.atleast_1d(j)]
            dd = np.hypot(E.ox[oi] - E.fx[F], E.oy[oi] - E.fy[F]); out.append(('ration', int(oi[np.lexsort((oi, dd))[0]])))
        if fa in (NICENE, ARIAN): out.append(('parish', 0 if fa == NICENE else 1))
        out.append(('guild', int(M['ft'][F])))
        if men == 0 and M['boy'][F, yi] and self.tm_any is not None:
            R = P['apprentice']['radius']; best = -1; bd = INF
            for tree, same in ((self.tm_trade, True), (self.tm_any, False)):
                qx = E.fx[F] + (M['ft'][F] * 1e5 if same else 0)
                for j in tree.query_ball_point([qx, E.fy[F]], R * 1.0001):
                    o = self.mm[j]; d = math.hypot(E.fx[o] - E.fx[F], E.fy[o] - E.fy[F])
                    if d <= R and d < bd: bd, best = d, int(o)
                if best >= 0: break
            if best >= 0: out.append(('master', best))
        if E.fdest[F] == Y + 1: out.append(('evicted', 0))
        b = E.D['barracks']; fg = E.fn_names.index('garrison') if 'garrison' in E.fn_names else -99
        if M['fsold'][F] <= Y or E.ffn[F] == fg or (b is not None and math.hypot(b[0] - E.flx[F], b[1] - E.fly[F]) <= P['garrison']['radius']):
            out.append(('garrison', 0))
        if Y == P['office']['corvee_year']:
            st = M['hstreet'][M['fh'][F], yi]
            l = sorted(self.street_ten.get(st, ()), key=lambda i: (-M['men'][i, yi], E.keyrank[i]))[:P['office']['corvee_per_street']]
            if F in l: out.append(('corvee', 0))
        return out


def ego_bench(E, P, rows):
    must = [r for r in rows if r[0] in MUST_STORE]
    G = EgoEP(E, must); res = {}
    rng = np.random.default_rng(7)
    for Y in (51, 55, 57, 60, 65, 70):
        a = time.perf_counter(); G.year_ctx(Y); tc = time.perf_counter() - a
        S = np.nonzero(E.M['present'][:, Y - E.YR0])[0]
        pick = rng.choice(S, size=min(400, len(S)), replace=False)
        ts = []; ns = []
        for F in pick.tolist():
            a = time.perf_counter(); r = G.ego(F, Y); ts.append(time.perf_counter() - a); ns.append(len(r))
        ts = np.array(ts) * 1000
        res[str(Y)] = dict(year_ctx_ms=round(tc * 1000, 2), mean_ms=round(float(ts.mean()), 4), p95_ms=round(float(np.percentile(ts, 95)), 4),
                           max_ms=round(float(ts.max()), 4), slots_mean=round(float(np.mean(ns)), 2), slots_max=int(max(ns)))
    # 核对：单户现算 vs 批量算（全部槽位）是否逐条相同
    allrows = collections.defaultdict(set)
    for k, c, p, a, b in rows:
        for Y in range(a, b + 1): allrows[(c, Y)].add((k, p if k in ('landlord', 'patron', 'debt', 'master', 'ration', 'parish') else 0))
    bad = 0; tot = 0
    for Y in (51, 57, 60, 65):
        S = np.nonzero(E.M['present'][:, Y - E.YR0])[0]
        for F in rng.choice(S, size=min(300, len(S)), replace=False).tolist():
            got = set(G.ego(F, Y)); exp = {(k, p) for k, p in allrows.get((F, Y), set()) if k not in ('levy',)}
            got = {g for g in got if g[0] not in ('levy',)}
            # guild 批量没逐条记（每户 1 条），单独补
            exp.add(('guild', int(E.M['ft'][F])))
            tot += 1; bad += got != exp
            if got != exp and len(res.setdefault('diff_examples', [])) < 5: res['diff_examples'].append([F, Y, sorted(map(str, got - exp)), sorted(map(str, exp - got))])
    res['verify'] = dict(checked=tot, mismatches=bad, note='levy（凑铜板）按距离蓄水池现算，未纳入逐条核对；其余槽位逐条比')
    return res


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(a[0], ego='--ego' in sys.argv)
