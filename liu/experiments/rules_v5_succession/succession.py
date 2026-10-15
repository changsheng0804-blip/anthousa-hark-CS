"""规则预演 v5 · 选任与继承对照（干山，AF40–70）。只 import v1/v3（不运行写 out/ 的脚本），读 ../rules_v5_<scope>.pkl 与 ../rules_v2_must_<scope>.pkl。
四种职位：区长 district、坊长 fang、长老 elder（坊 × 教派）、行会头 guild（区 × 行当）。组划分与 v3 相同。
机制：
  G1   直接用 v3 Registry offices（v3 自己的出缺规则，作基准）
  其余机制共用出缺：在任者死亡 / 离家、户结束（绝户 · 迁走 · 被拆，48 年被拆记「大火」）、失格、年老 ≥65（假设）、告发 2%/年（假设）
  上级任命  区长：城里派，取尼西亚派里年资最老；坊长/长老/行会头：本区区长挑 同籍贯 → 同教派 → 年资
  房主推举  本组房主（不含候选人自己）各投亲疏分最高者：亲家 3 + 同籍贯 2 + 同教派 1 + 同行当 1；平票取人多、年资
  世袭      职位跟户走：户主换人不出缺；户主成了寡妇/孤儿 → 女婿户（本组）代理 → 同乡；本户儿/孙满龄可索回
  按财产    分 = 房主 3 + 同屋户数 + 口数/5 + 在 must 里作施方（恩主/房东/债主）的条数
  按年资    搬入最早，再户主最年长
  教派限制  民政职（区长/坊长/行会头）只许尼西亚派（假设；参考《狄奥多西法典》16.5 对异端任职的限制），挑法同 v3
  恩主举荐  本组外也算：恩主按在世门客数排序，第一个在本组有合格门客的恩主举荐其门客（年资最老）；没有 → 门客最多者自荐 → 年资
  抽签      合格者中均匀抽，20 个种子
合格（假设 E1）：户在场、户主是成年男（≥A）；长老另须非拜旧神；G1 以外不要求房主（所以能看到租户在任）。
usage: python3 succession.py [--A 14] [--p 0.02] [--seed 0]
"""
import os, sys, time, json, collections, pickle
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'rules_v3_registry')); sys.path.insert(0, os.path.join(HERE, '..', 'rules_v1'))
import prep5  # noqa: E402
import registry as RG  # noqa: E402  (v3，只读)

OFF = ['district', 'fang', 'elder', 'guild']
OFFZH = dict(district='区长', fang='坊长', elder='长老', guild='行会头')
MECH = ['上级任命', '房主推举', '世袭', '按财产', '按年资', '教派限制', '恩主举荐']
LOCAL = '本城生'
Y0, Y1 = 40, 70


class World:
    def __init__(self, scope='xero', A=14):
        t = time.time()
        self.G = RG.Registry(scope); self.years, _ = self.G.build(Y0, Y1)
        X = prep5.load(scope); self.X = X; self.A = A
        self.head = X[A]['head']; self.hk = X[A]['hk']; self.P = X['P']; self.pb = np.array(self.P['b']); self.pd = np.array(self.P['d'])
        self.endev = {(e[0], e[1]): e[2] for e in X[A]['events'] if e[2] in ('绝户', '迁走', '被拆')}
        self.names = self.G.names; self.keys = self.G.M['keys']
        M = self.G.M; self.fB = M['fB']; self.fo = M['fo']; self.ff = M['ff']; self.ft = M['ft']
        self.local_o = M['origins'].index(LOCAL) if LOCAL in M['origins'] else -9
        self.NT = len(self.G.trades)
        must = pickle.load(open(os.path.join(prep5.D0.CACHE, f'rules_v2_must_{scope}.pkl'), 'rb'))['must']
        self.must = must
        kin = M['kin']; self.kin = kin
        # 女婿户：女儿户 F → 她嫁入的户 G（v1 亲家表，女儿活着期间）
        self.inlaw = collections.defaultdict(list)
        for F, Gg, y, dy in kin: self.inlaw[int(F)].append((int(Gg), int(y), int(dy)))
        self.ctx = {Y: self._ctx(Y) for Y in range(Y0, Y1 + 1)}
        self.t_load = time.time() - t

    def _ctx(self, Y):
        R = self.years[Y]; S = R['S']; yi = Y - Y0; n = len(S)
        hk = self.hk[S, yi]; elig = (hk == 0) | (hk == 3)
        hp = self.head[S, yi]
        gk = dict(district=R['dist'].astype(np.int64), fang=R['fang'].astype(np.int64),
                  elder=R['fang'].astype(np.int64) * 3 + R['faith'], guild=R['dist'].astype(np.int64) * self.NT + R['trade'])
        groups = {}
        for o in OFF:
            e = elig & (R['faith'] != RG.PAGAN) if o == 'elder' else elig
            idx = np.nonzero(e)[0]; d = collections.defaultdict(list)
            for i in idx: d[int(gk[o][i])].append(int(i))
            allg = collections.defaultdict(list)
            for i in range(n): allg[int(gk[o][i])].append(i)
            groups[o] = (d, allg)
        # 施方条数（财产）、恩主 → 门客
        act = [m for m in self.must if m[3] <= Y <= m[4]]
        giver = collections.Counter(m[2] for m in act)
        clients = collections.defaultdict(list)
        for m in act:
            if m[0] == 'patron': clients[m[2]].append(m[1])
        kinp = set()
        for F, Gg, y, dy in self.kin:
            if y <= Y < dy: kinp.add((int(F), int(Gg))); kinp.add((int(Gg), int(F)))
        wealth = 3 * R['own'] + R['hh_in_house'] + R['size'] / 5 + np.array([giver.get(int(f), 0) for f in S])
        return dict(R=R, S=S, elig=elig, hp=hp, gk=gk, groups=groups, wealth=wealth, clients=clients,
                    ncli={k: len(v) for k, v in clients.items()}, kinp=kinp)

    # ---------------------------------------------------------------- 挑人（返回户号 F，-1 = 无人可选）
    def seniority(self, C, cand):
        S = C['S']
        return min(cand, key=lambda i: (self.fB[S[i]], self.pb[C['hp'][i]], self.G.keyrank[S[i]]))

    def pick(self, mech, o, k, Y, state, rng=None, prev=None):
        C = self.ctx[Y]; S = C['S']; R = C['R']
        cand = C['groups'][o][0].get(k, [])
        if mech == '教派限制' and o != 'elder': cand = [i for i in cand if R['faith'][i] == RG.NICENE]
        if not cand: return -1
        if mech == '抽签': return int(S[cand[rng.integers(len(cand))]])
        if mech in ('按年资',): return int(S[self.seniority(C, cand)])
        if mech == '按财产': return int(S[max(cand, key=lambda i: (C['wealth'][i], -self.fB[S[i]], -self.G.keyrank[S[i]]))])
        if mech == '教派限制':
            return int(S[min(cand, key=lambda i: (-R['hh_in_house'][i], self.fB[S[i]], self.G.keyrank[S[i]]))])
        if mech == '上级任命':
            if o == 'district':
                nic = [i for i in cand if R['faith'][i] == RG.NICENE]
                return int(S[self.seniority(C, nic or cand)])
            d = self.G.fang_dist[k] if o == 'fang' else self.G.fang_dist[k // 3] if o == 'elder' else k // self.NT
            ap = state.get(('district', int(d)), -1) if state is not None else -1
            ali = C['R']['loc'][ap] if ap >= 0 else -1
            if ali < 0: return int(S[self.seniority(C, cand)])
            ao, af = self.fo[ap], self.ff[ap]
            return int(S[min(cand, key=lambda i: (self.fo[S[i]] != ao, R['faith'][i] != af, self.fB[S[i]], self.pb[C['hp'][i]]))])
        if mech == '房主推举':
            allg = C['groups'][o][1].get(k, [])
            voters = np.array([i for i in allg if R['own'][i]], int)
            ca = np.array(cand, int)
            if len(voters) == 0: return int(S[self.seniority(C, cand)])
            fo, ff, ft = self.fo, self.ff, self.ft
            Sv, Sc = S[voters], S[ca]
            aff = 2 * (fo[Sv][:, None] == fo[Sc][None]) + (ff[Sv][:, None] == ff[Sc][None]) + (ft[Sv][:, None] == ft[Sc][None])
            aff = aff.astype(float)
            if C['kinp']:
                for a_, v in enumerate(Sv):
                    for b_, c in enumerate(Sc):
                        if (int(v), int(c)) in C['kinp']: aff[a_, b_] += 3
            aff[Sv[:, None] == Sc[None]] = -9                      # 不投自己
            tieb = R['hh_in_house'][ca] * 1e-3 - (self.fB[Sc] - self.fB[Sc].min()) * 1e-6
            vote = np.argmax(aff + tieb[None], 1)
            cnt = np.bincount(vote, minlength=len(ca)).astype(float)
            return int(Sc[np.argmax(cnt + tieb)])
        if mech == '恩主举荐':
            ncli = C['ncli']; candF = {int(S[i]): i for i in cand}
            for pat in sorted(ncli, key=lambda p: (-ncli[p], p)):
                cl = [candF[c] for c in C['clients'][pat] if c in candF]
                if cl: return int(S[self.seniority(C, cl)])
                if ncli[pat] < 2: break
            return int(S[max(cand, key=lambda i: (ncli.get(int(S[i]), 0), -self.fB[S[i]]))])
        if mech == '世袭':                                           # 出缺时的接任：前任户的女婿户 → 同乡
            if prev is not None and prev >= 0:
                candF = {int(S[i]): i for i in cand}
                sil = [candF[g] for g, y, dy in self.inlaw.get(prev, []) if y <= Y < dy and g in candF]
                if sil: return int(S[self.seniority(C, sil)])
                same = [i for i in cand if self.fo[S[i]] == self.fo[prev]]
                if same: return int(S[self.seniority(C, same)])
            return int(S[self.seniority(C, cand)])
        raise ValueError(mech)

    # ---------------------------------------------------------------- 出缺判定
    def vacancy(self, F, p, o, Y, rng, pden, hered):
        C = self.ctx[Y]; li = C['R']['loc'][F]
        if li < 0:
            ev = self.endev.get((F, Y))
            if ev is None:   # 结束在更早年份（不该发生）或户在场但 v3 不收
                ev = '绝户'
            return '48年大火' if (ev == '被拆' and Y == 48) else ev
        if not hered:
            if C['hp'][li] != p: return '死亡' if self.pd[p] <= Y else '离家'
            if not C['elig'][li]: return '失格'
            if Y - self.pb[p] >= 65: return '年老'
        if rng.random() < pden: return '告发'
        return None

    def run(self, mech, seed=0, pden=0.02, log=False):
        rng = np.random.default_rng(seed); prng = np.random.default_rng(seed + 1000)
        hold = {}; claim = {}; changes = collections.Counter(); reasons = collections.Counter(); comp = collections.Counter()
        events = []; dyn = {}
        for Y in range(Y0, Y1 + 1):
            C = self.ctx[Y]; R = C['R']; S = C['S']
            for o in OFF:
                ng = len(R['offices'][o])
                for k in range(ng):
                    key = (o, k); cur = hold.get(key)
                    if mech == '世袭':
                        F = cur[0] if cur else -1
                        why = None
                        if F >= 0:
                            why = self.vacancy(F, -1, o, Y, prng, pden, True)
                            # 索回：原世袭户回到有成年男户主
                            cl = claim.get(key)
                            if why is None and cl is not None and cl != F:
                                lc = R['loc'][cl]
                                if lc >= 0 and C['elig'][lc] and (o != 'elder' or R['faith'][lc] != RG.PAGAN) and int(C['gk'][o][lc]) == k:
                                    events.append(dict(Y=Y, o=o, k=k, kind='索回', old=F, new=cl)); hold[key] = (cl, -1); changes[o] += 1
                                    claim.pop(key); F = cl
                            if why is None:
                                li = R['loc'][F]
                                if not C['elig'][li]:   # 户主成了寡妇/孤儿 → 女婿/同乡代理，留索回权
                                    newF = self.pick('世袭', o, k, Y, None, prev=F)
                                    newF = -1 if newF == F else newF
                                    if newF >= 0:
                                        events.append(dict(Y=Y, o=o, k=k, kind='代理', old=F, new=newF)); claim[key] = F
                                        hold[key] = (newF, -1); changes[o] += 1; reasons['户主成寡妇/孤儿'] += 1
                        if F < 0 or why is not None:
                            if why: reasons[why] += 1
                            newF = self.pick('世袭', o, k, Y, None, prev=F) if F >= 0 or True else -1
                            if why == '告发' and newF == F: newF = -1
                            if cur and newF != F: changes[o] += 1
                            if newF >= 0: events.append(dict(Y=Y, o=o, k=k, kind='出缺', why=why, old=F, new=newF))
                            if claim.get(key) == F: claim.pop(key, None)
                            hold[key] = (newF, -1) if newF >= 0 else None
                    else:
                        why = None
                        if cur:
                            why = self.vacancy(cur[0], cur[1], o, Y, prng, pden, False)
                        if cur is None or why is not None:
                            if why: reasons[why] += 1
                            newF = self.pick(mech, o, k, Y, {kk: v[0] for kk, v in hold.items() if v}, rng=rng)
                            if why == '告发' and cur and newF == cur[0]:   # 被告发者本人不再选
                                C2 = C; cand = [i for i in C2['groups'][o][0].get(k, []) if S[i] != cur[0]]
                                newF = int(S[self.seniority(C2, cand)]) if cand else -1
                            if cur and (newF < 0 or newF != cur[0]): changes[o] += 1
                            if newF >= 0:
                                events.append(dict(Y=Y, o=o, k=k, kind='出缺', why=why, old=cur[0] if cur else -1, new=newF))
                            hold[key] = (newF, int(C['hp'][R['loc'][newF]])) if newF >= 0 else None
                    h = hold.get(key)
                    if h:
                        li = R['loc'][h[0]]; comp[(o, 'n')] += 1
                        comp[(o, '旧神')] += R['faith'][li] == RG.PAGAN; comp[(o, '阿里乌')] += R['faith'][li] == RG.ARIAN
                        comp[(o, '租户')] += not R['own'][li]; comp[(o, '外来')] += self.fo[h[0]] != self.local_o
                    else: comp[(o, '空缺')] += 1
                    if Y == Y1: dyn[key] = h[0] if h else -1
        return dict(changes=changes, reasons=reasons, comp=comp, events=events)

    def g1(self):
        changes = collections.Counter(); comp = collections.Counter(); vac = []
        prev = None
        for Y in range(Y0, Y1 + 1):
            R = self.years[Y]
            for o in OFF:
                cur = R['offices'][o]
                for k, F in enumerate(cur):
                    F = int(F)
                    if prev is not None:
                        pF = int(prev[o][k])
                        if F != pF:
                            if pF >= 0: changes[o] += 1
                            if F >= 0: vac.append((Y, o, k, pF, F))
                    elif F >= 0: pass
                    if F >= 0:
                        li = R['loc'][F]; comp[(o, 'n')] += 1
                        comp[(o, '旧神')] += R['faith'][li] == RG.PAGAN; comp[(o, '阿里乌')] += R['faith'][li] == RG.ARIAN
                        comp[(o, '租户')] += not R['own'][li]; comp[(o, '外来')] += self.fo[F] != self.local_o
                    else: comp[(o, '空缺')] += 1
            prev = R['offices']
        return dict(changes=changes, comp=comp, vac=vac)

    def same_vacancy(self, vac, nseed=20):
        """G1 每次换人（同一出缺）时，各机制会不会选出别人。上级任命用 G1 当年的区长作任命者。"""
        diff = collections.Counter(); tot = collections.Counter()
        for Y, o, k, pF, F in vac:
            st = {('district', d): int(v) for d, v in enumerate(self.years[Y]['offices']['district'])}
            tot[o] += 1
            for m in MECH:
                if self.pick(m, o, k, Y, st, prev=pF) != F: diff[(m, o)] += 1
            for s in range(nseed):
                if self.pick('抽签', o, k, Y, st, rng=np.random.default_rng(s * 7919 + Y * 31 + k)) != F: diff[('抽签', o)] += 1 / nseed
        return diff, tot


def shares(comp, o):
    n = comp[(o, 'n')]
    if not n: return {}
    return {k: round(comp[(o, k)] / n, 3) for k in ('旧神', '阿里乌', '租户', '外来')} | {'在任户年': n, '空缺组年': comp[(o, '空缺')]}


def conflicts(W, runs, pden, seed):
    """冲突 = 世袭跑里的出缺/代理/索回事件，各机制在同一时点的人选不一致；分 = 不同人选数（含 G1 当年在任）。"""
    out = []
    for e in runs['世袭']['events']:
        Y, o, k = e['Y'], e['o'], e['k']
        st = {('district', d): int(v) for d, v in enumerate(W.years[Y]['offices']['district'])}
        picks = {m: W.pick(m, o, k, Y, st, prev=e['old']) for m in MECH if m != '世袭'}
        picks['世袭'] = e['new']; picks['G1'] = int(W.years[Y]['offices'][o][k])
        distinct = len({v for v in picks.values() if v >= 0})
        if e['kind'] in ('索回', '代理') or (picks['世袭'] != picks['G1'] and picks['世袭'] != picks['房主推举']):
            out.append(dict(Y=Y, o=o, k=k, kind=e['kind'], why=e.get('why'), old=e['old'], new=e['new'], distinct=distinct, picks=picks))
    rank = dict(district=0, fang=1, guild=2, elder=3)
    kindr = {'索回': 0, '代理': 1, '出缺': 2}
    out.sort(key=lambda c: (-c['distinct'], kindr[c['kind']], rank[c['o']], c['Y'], c['k']))
    return out


def main(A=14, pden=0.02, seed=0, write=True):
    t0 = time.time()
    W = World('xero', A); t_load = W.t_load
    t = time.time()
    g1 = W.g1()
    runs = {m: W.run(m, seed, pden) for m in MECH}
    lot = [W.run('抽签', s, pden) for s in range(20)]
    t_run = time.time() - t
    t = time.time(); diff, tot = W.same_vacancy(g1['vac']); t_sv = time.time() - t
    t = time.time(); C = conflicts(W, runs, pden, seed); t_c = time.time() - t
    res = dict(A=A, pden=pden, seed=seed, seconds=dict(load_registry_and_ctx=round(t_load, 2), mechanisms=round(t_run, 2), same_vacancy=round(t_sv, 2),
                                                          conflicts=round(t_c, 2), total=round(time.time() - t0, 2)))
    tab = {}
    tab['G1'] = dict(changes={OFFZH[o]: g1['changes'][o] for o in OFF}, comp={OFFZH[o]: shares(g1['comp'], o) for o in OFF})
    for m in MECH:
        r = runs[m]
        tab[m] = dict(changes={OFFZH[o]: r['changes'][o] for o in OFF}, comp={OFFZH[o]: shares(r['comp'], o) for o in OFF},
                      reasons=dict(r['reasons']), diff_vs_G1={OFFZH[o]: diff[(m, o)] for o in OFF})
    lc = collections.Counter(); lcomp = collections.Counter(); lr = collections.Counter()
    for r in lot: lc.update(r['changes']); lcomp.update(r['comp']); lr.update(r['reasons'])
    tab['抽签(20种子均值)'] = dict(changes={OFFZH[o]: round(lc[o] / 20, 1) for o in OFF}, comp={OFFZH[o]: shares(lcomp, o) for o in OFF},
                               reasons={k: round(v / 20, 1) for k, v in lr.items()}, diff_vs_G1={OFFZH[o]: round(diff[('抽签', o)], 1) for o in OFF})
    res['g1_vacancies'] = {OFFZH[o]: tot[o] for o in OFF}
    res['table'] = tab
    res['n_conflicts'] = len(C)
    def nm(F): return f"{W.names[F]}家 {W.keys[F]}" if F >= 0 else '（空）'
    res['conflicts_top'] = [dict(c, old_name=nm(c['old']), new_name=nm(c['new']), picks_named={m: nm(v) for m, v in c['picks'].items()}) for c in C[:30]]
    if write:
        json.dump(res, open(os.path.join(HERE, 'out', f'succession_A{A}_p{int(pden*100)}_s{seed}.json'), 'w'), ensure_ascii=False, indent=1, default=int)
    return W, res, C


if __name__ == '__main__':
    a = sys.argv
    A = int(a[a.index('--A') + 1]) if '--A' in a else 14
    p = float(a[a.index('--p') + 1]) if '--p' in a else 0.02
    s = int(a[a.index('--seed') + 1]) if '--seed' in a else 0
    W, res, C = main(A, p, s)
    print(json.dumps({k: res[k] for k in ('seconds', 'g1_vacancies', 'n_conflicts')}, ensure_ascii=False))
    for m, v in res['table'].items(): print(m, json.dumps(v['changes'], ensure_ascii=False), json.dumps(v.get('diff_vs_G1', {}), ensure_ascii=False))
