"""规则预演 v1 · 骨架去重。

骨架签名 = 模式组合 + 角色关系 + 结局类型
  角色关系：两户之间最强的那条制度关系（房东-租户 > 债主-欠债 > 恩主-门客 > 师傅-学徒 > 同乡先后 > 同行对头 > 只是邻居）
           + 有房/租的组合 + 同行/异行；单户 × 机构写「户×机构类」
  结局类型：交叉点最后一年之后发生了什么——拆房 / 一家死绝 / 换了人家 / 有人去世后不再成立 / 条件消散（孩子长大、不再缺男丁等）/ 延续到 70 年
python3 skeleton.py → 干山骨架分布（前 5 占比）+ 三条让骨架更分散的规则改法小测，写 out/skeleton_xero.json
"""
import os, sys, json, collections, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as RUN
from engine import PAIR_PATTERNS, Engine

ROLE_ORDER = [('landlord', '房东-租户'), ('debt', '债主-欠债'), ('patron', '恩主-门客'), ('apprentice', '师傅-学徒'),
              ('hometown', '同乡先后'), ('rival', '同行对头')]


def outcome(E, fams, yend, y1=70):
    if yend >= y1: return '延续到窗口末'
    M = E.M; yi = yend + 1 - E.YR0; yo = yend - E.YR0
    res = []
    for F in fams:
        if not M['present'][F, yi]:
            if E.fdest[F] == yend + 1: res.append(3)                        # 拆房
            elif M['fBn'][F] == yend + 1: res.append(1)                     # 换了人家（新户搬进这栋房）
            else: res.append(2)                                            # 一家死绝 / 走光
        elif M['deaths'][F, yo] > 0 or M['deaths'][F, yi] > 0: res.append(0.5)
    if not res: return '条件消散'
    m = max(res)
    return {3: '拆房', 2: '一家死绝', 1: '换了人家', 0.5: '有人去世后不再成立'}[m]


def role(E, fa, fb, bits):
    if fb < 0: return '户×机构'
    TB = Engine.TBITS
    r = next((name for t, name in ROLE_ORDER if bits & TB[t]), '只是邻居')
    ow = E.owner
    own = ''.join(sorted(('有' if ow[f] else '租') for f in (fa, fb)))
    tr = '同行' if E.M['ft'][fa] == E.M['ft'][fb] else '异行'
    return f'{r}·{own}·{tr}'


def skeletons(E, rows):
    out = []
    for r in rows:
        bits = 0
        if r.fb >= 0:
            a, b = (r.fa, r.fb) if E.keyrank[r.fa] < E.keyrank[r.fb] else (r.fb, r.fa)
            bits = E.ptu.get(a * len(E.keys) + b, 0)
        fams = [r.fa] + ([r.fb] if r.fb >= 0 else [])
        out.append(('+'.join(r.patterns), role(E, r.fa, r.fb, bits), outcome(E, fams, r.intervals[-1][1])))
    return out


def dist(sk, top=5):
    c = collections.Counter(sk); n = len(sk)
    return dict(crossings=n, distinct=len(c), top5_share=round(sum(v for _, v in c.most_common(top)) / max(n, 1), 3),
                top5=[(' | '.join(k), v, round(v / n, 3)) for k, v in c.most_common(top)])


def main(scope='xero', mode='v1'):
    rows, out, E = RUN.main(scope, mode, quiet=True)
    sk = skeletons(E, rows)
    res = dict(scope=scope, mode=mode, baseline=dist(sk))
    res['baseline']['top100_distinct'] = len(set(sk[:100]))
    res['baseline']['top100_top5_share'] = round(sum(v for _, v in collections.Counter(sk[:100]).most_common(5)) / 100, 3)
    res['baseline']['v0_definition'] = dict(distinct=out['skeletons'], biggest=out['biggest_skeletons'])
    res['by_part'] = dict(patterns=collections.Counter(s[0] for s in sk).most_common(5), roles=collections.Counter(s[1] for s in sk).most_common(6),
                          outcomes=collections.Counter(s[2] for s in sk).most_common())
    score = {(r.a, r.b): r.score for r in rows}

    # ---------------- 改法 1：转折触发——同水异粮 / 同井施舍分线只在「苦」刚开始的 3 年内算（丧事或缺男丁是新近才有的）
    pid, code, YY, NF = E.hits
    M = E.M
    cond = (M['deaths'] > 0) | ((M['men'] == 0) & (M['kids'] > 0))
    fresh = np.zeros_like(cond)
    start = cond & ~np.c_[np.zeros((cond.shape[0], 1), bool), cond[:, :-1]]
    for d in range(3): fresh[:, d:] |= start[:, :cond.shape[1] - d]
    fa = code // NF; fb = code % NF; yi = YY - E.YR0
    wb = PAIR_PATTERNS.index('同水异粮'); al = PAIR_PATTERNS.index('同井施舍分线')
    ten = np.where(E.owner[fa], fb, fa)
    keep = np.ones(len(pid), bool)
    keep[pid == wb] = fresh[ten[pid == wb], yi[pid == wb]]
    keep[pid == al] = fresh[fa[pid == al], yi[pid == al]] | fresh[fb[pid == al], yi[pid == al]]
    res['proposal1a_fresh_trouble_only'] = test_variant(E, rows, pid, code, YY, NF, keep.copy(), score,
        '只改同水异粮 / 同井施舍分线：丧事或缺男丁「新近 3 年内开始」的年份才成立')
    hs = PAIR_PATTERNS.index('同乡异信')
    m = pid == hs
    late = np.maximum(M['fB'][fa[m]], M['fB'][fb[m]])                 # 后来的那一家搬来的年份
    keep[m] = (YY[m] <= 53) | (YY[m] - late <= 3)                     # 51 年驱逐后的头三年，或后来那家刚到的三年
    res['proposal1_turning_points'] = test_variant(E, rows, pid, code, YY, NF, keep, score,
        '转折触发：同水异粮 / 同井施舍分线只在苦「新近 3 年内开始」时成立；同乡异信只在 51–53 年（刚被请出教堂）或后来那家刚到的 3 年内成立')

    # ---------------- 改法 2：一户只认一个——同一年一户租户的同水异粮只留分数最高的那一家有房邻居
    keep = np.ones(len(pid), bool)
    m = np.nonzero(pid == wb)[0]
    best = {}
    for i in m:
        k_ = (int(ten[i]), int(YY[i])); a_, b_ = E.keys[fa[i]], E.keys[fb[i]]
        s_ = score.get((a_, b_), 0)
        if k_ not in best or s_ > best[k_][0]: best[k_] = (s_, i)
    keep[m] = False
    keep[[v[1] for v in best.values()]] = True
    res['proposal2_one_neighbor_per_tenant'] = test_variant(E, rows, pid, code, YY, NF, keep, score,
        '同一年里一户没面包的人家只跟「一家」有面包的邻居构成同水异粮（取分数最高的那家）：去掉一户对四五家的重复')

    # ---------------- 改法 3：选故事时骨架配额——分数减去 1.0×log2(1+前面已有的同骨架数)
    import heapq
    old8 = [(p['a'], p['b']) for p in out['picks']]
    def rerank(lam, key):
        seen = collections.Counter()
        heap = [(-rows[i].score, i) for i in range(len(rows))]; heapq.heapify(heap); ranked = []
        while heap and len(ranked) < 100:
            s, i = heapq.heappop(heap)
            cur = -(rows[i].score - lam * math.log2(1 + seen[key(i)]))
            if cur > s + 1e-9 and heap and cur > heap[0][0] + 1e-9:
                heapq.heappush(heap, (cur, i)); continue
            ranked.append(i); seen[key(i)] += 1
        top100 = [sk[i] for i in ranked]
        roles8 = collections.Counter(sk[i][1] for i in ranked[:8])
        return dict(top100_distinct=len(set(top100)), top100_top5_share=round(sum(v for _, v in collections.Counter(top100).most_common(5)) / 100, 3),
                    top8_distinct_roles=len(roles8), top8_overlap_with_old_picks=len(set(old8) & {(rows[i].a, rows[i].b) for i in ranked[:8]}),
                    top8=[dict(a=rows[i].a, b=rows[i].b, score=rows[i].score, skeleton=' | '.join(sk[i])) for i in ranked[:8]])
    base8 = collections.Counter(sk[i][1] for i in range(8))
    res['proposal3_skeleton_quota_ranking'] = dict(
        rule='排序时同骨架递减：分数 − λ×log2(1+排在前面的同骨架数)，只改「挑哪几个写故事」，不改交叉点本身',
        before=dict(top100_distinct=res['baseline']['top100_distinct'], top100_top5_share=res['baseline']['top100_top5_share'], top8_distinct_roles=len(base8)),
        full_skeleton_lam1=rerank(1.0, lambda i: sk[i]), full_skeleton_lam2=rerank(2.0, lambda i: sk[i]),
        role_part_lam2=rerank(2.0, lambda i: sk[i][1]))
    json.dump(res, open(os.path.join(HERE, 'out', f'skeleton_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


def test_variant(E, rows, pid, code, YY, NF, keep, score, rule):
    """把某些模式-年去掉后重新合成交叉点，看骨架分布怎么变（分数沿用原交叉点的，不重算）。"""
    occ = collections.defaultdict(set)
    for p, c, y in zip(pid[keep].tolist(), code[keep].tolist(), YY[keep].tolist()):
        occ[(c // NF, c % NF)].add((PAIR_PATTERNS[p], y))
    for (name, k), ys in E.occ_h.items():
        for y in ys: occ[k].add((name, y))
    class R: pass
    new = []
    for k, s in occ.items():
        r = R(); r.fa = k[0]; r.fb = k[1] if not isinstance(k[1], str) else -1
        r.patterns = sorted({n for n, _ in s}); ys = sorted({y for _, y in s}); r.intervals = RUN.intervals(ys)
        new.append(r)
    sk = skeletons(E, new)
    d = dist(sk)
    d['rule'] = rule
    d['crossings_before'] = len(rows)
    # 高分段（原分 ≥12）还剩多少
    hi = {(r.a, r.b) for r in rows if r.score >= 12}
    newk = {(E.keys[r.fa], E.keys[r.fb] if r.fb >= 0 else None) for r in new}
    d['high_score_pairs_kept'] = f'{sum(1 for a, b in hi if (a, b) in newk or (b, a) in newk)}/{len([1 for a, b in hi if not b.startswith("@")])}'
    return d


if __name__ == '__main__':
    main(*(sys.argv[1:]))
