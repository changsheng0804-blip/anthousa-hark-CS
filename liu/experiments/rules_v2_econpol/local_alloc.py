"""小测（下一步方案的可行性）：把「房东」从全城顺序贪心改成「按街局部」——
  有街名、街上有有房户的租户：只在本街分（同一条街内仍按户键顺序、搬入最早 → 最近、每个房东至多 6 家）；
  没街名或本街没有有房户的租户：250px 内最近的有房户，不计容量（纯函数）。
这样一户的房东只取决于它这条街（平均几十户），单户/单街就能现算，不用全城批量算，也不用存。
测：与 v1 房东分配逐户相同的比例、受影响的交叉点（正统房东·阿里乌派租户 / 房东兼债主/恩主）、单街现算耗时。
usage: python3 local_alloc.py [xero|city]
"""
import os, sys, json, time, collections, math
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econpol as EP  # noqa: E402
from engine import NICENE, ARIAN  # noqa: E402


def street_landlords(st_ten, st_own, x, y, B, cap):
    """一条街：租户（已按户键排好）→ 房东。纯局部。"""
    load = collections.Counter(); out = {}
    pool = sorted(st_own, key=lambda o: (B[o], o))
    for t in st_ten:
        best = -1; bb = None; bd = 0.0
        for o in pool:
            if load[o] >= cap: continue
            if bb is not None and B[o] > bb: break
            d = math.hypot(x[o] - x[t], y[o] - y[t])
            if bb is None or d < bd or (d == bd and o < best): best, bb, bd = o, B[o], d
        if best >= 0: load[best] += 1; out[t] = best
    return out


def main(scope):
    P = json.load(open(os.path.join(EP.V0, 'rules.json')))
    E = EP.EconPol(scope, P, 'v1'); M = E.M; cap = P['landlord']['cap']; R_ = P['landlord']['radius']
    tot = collections.Counter(); street_ms = []
    for Y in range(50, 71):
        R = E.year_ep(Y); Yd = R['Yd']; S = Yd['S']; n = Yd['n']
        x, y, st, own, B = Yd['x'], Yd['y'], Yd['st'], Yd['own'], Yd['B']
        ten = np.nonzero(~own)[0]; ten = ten[np.argsort(E.keyrank[S[ten]], kind='stable')]
        by_o = collections.defaultdict(list); by_t = collections.defaultdict(list)
        for o in np.nonzero(own)[0].tolist():
            if st[o] >= 0: by_o[st[o]].append(o)
        new = np.full(n, -1)
        fb = []
        for t in ten.tolist():
            if st[t] >= 0 and by_o.get(st[t]): by_t[st[t]].append(t)
            else: fb.append(t)
        Bl = B.tolist(); xl = x.tolist(); yl = y.tolist()
        for s_, tl in by_t.items():
            a = time.perf_counter(); m = street_landlords(tl, by_o[s_], xl, yl, Bl, cap); street_ms.append((time.perf_counter() - a) * 1000)
            for t, o in m.items(): new[t] = o
        O = np.nonzero(own)[0]
        if fb and len(O):
            d, j = cKDTree(np.c_[x[O], y[O]]).query(np.c_[x[fb], y[fb]], distance_upper_bound=R_ * 1.0001)
            ok = j < len(O); new[np.array(fb)[ok]] = O[j[ok]]
        old = R['landlord']
        tv1 = old >= 0
        tot['v1_tenant_years'] += int(tv1.sum()); tot['same'] += int((tv1 & (new == old)).sum())
        tot['street_part_v1'] += int(sum(1 for t in np.nonzero(tv1)[0] if st[t] >= 0 and by_o.get(st[t])))
        tot['street_part_same'] += int(sum(1 for t in np.nonzero(tv1)[0] if st[t] >= 0 and by_o.get(st[t]) and new[t] == old[t]))
        tot['new_tenant_years'] += int((new >= 0).sum())
        f = Yd['faith']
        if Y >= 51:
            def pf(L):
                T = np.nonzero(L >= 0)[0]; return {(int(S[L[t]]), int(S[t])) for t in T if f[L[t]] == NICENE and f[t] == ARIAN}
            a, b = pf(old), pf(new); tot['pat_landlord_faith_v1'] += len(a); tot['pat_landlord_faith_same'] += len(a & b)
        tot['max_tenants_new'] = max(tot['max_tenants_new'], int(np.bincount(new[new >= 0]).max()) if (new >= 0).any() else 0)
    sm = np.array(street_ms)
    out = dict(scope=scope, **tot, same_share=round(tot['same'] / tot['v1_tenant_years'], 3),
               street_part_same_share=round(tot['street_part_same'] / max(tot['street_part_v1'], 1), 3),
               street_compute_ms=dict(mean=round(float(sm.mean()), 4), p95=round(float(np.percentile(sm, 95)), 4), max=round(float(sm.max()), 3)))
    json.dump(out, open(os.path.join(HERE, 'out', f'local_alloc_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'xero')
