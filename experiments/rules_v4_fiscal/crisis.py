"""规则预演 v4 · 危机动员小测：账本 48 年南港大火（world.json events：烧毁 287 座房屋，港口区）。
钱和人力沿树走，按天算：
  民政：户 →（租户经房主）→ 坊长 → 区长 → 城市长官（从城库积蓄拨救济）→ 区长 → 坊长 → 户（坊长一天发 c 户）
  教会：户 → 教区长老 → 教区 → 主教（从建堂/神职留存拨）→ 长老 → 本派户（长老一天发 c_e 户）；还拜旧神的户没有这条路
  人力：坊长从本坊没烧的人家里每 3 户叫 1 个男人清废墟，每栋烧掉的房子要 20 个人日
每层耽搁几天、每天发几户、每人救济多少都是假设（DAYS），敏感度见 sensitivity.py。
usage: python3 crisis.py
"""
import os, sys, json, time, math, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fiscal as FI  # noqa: E402
RG = FI.RG
OUT = os.path.join(HERE, 'out')
DAYS = dict(tenant_to_owner=1, to_fang=1, fang_up=2, district_up=3, prefect_decide=5, prefect_down=2, district_down=2, fang_cap=20,
            to_elder=1, elder_up=2, bishop_decide=2, bishop_down=2, elder_cap=10, relief_per_person=0.25, next_collection=90,
            clear_days_per_house=20, men_per_unaffected=1 / 3)


def simulate(X, F, Y=48, D=None, lam=0.0):
    D = dict(DAYS, **(D or {})); G = X.G
    Rp = X.years[Y - 1]; vict = X.evict[Y]; li = Rp['loc'][vict]
    n = len(li); S = Rp['S'][li]; size = Rp['size'][li]; own = Rp['own'][li]; fang = Rp['fang'][li]; dist = Rp['dist'][li]; faith = Rp['faith'][li]
    # 城库积蓄（41–47 城市长官留存累计）与主教留存累计
    reserve = sum(float(F[y]['T']['民政/城市长官']['kept'][0]) for y in range(41, Y))
    breserve = np.array([sum(float(F[y]['T']['教会/主教']['kept'][b]) for y in range(41, Y)) for b in (0, 1)])
    # 需要：页面内被烧户的人 + 页面外烧掉的账本房屋 × 9 人
    out_houses = int(X.dest_d[Y].sum()) - len(np.unique(Rp['rh'][li][own]))
    need_page = float(size.sum()) * D['relief_per_person']; need_out = out_houses * 9 * D['relief_per_person']; need = need_page + need_out
    # ---- 上报
    t_fang_know = np.where(own, D['to_fang'], D['tenant_to_owner'] + D['to_fang']).astype(float)
    fangs = np.unique(fang); t_fang_up = {f: t_fang_know[fang == f].max() + D['fang_up'] for f in fangs}
    dists = np.unique(dist); t_dist_up = {d: max(t_fang_up[f] for f in np.unique(fang[dist == d])) + D['district_up'] for d in dists}
    t_dec = max(t_dist_up.values()) + D['prefect_decide']
    frac_now = min(1.0, reserve / need) if need > 0 else 1.0
    t_fang_money = {f: t_dec + D['prefect_down'] + D['district_down'] for f in fangs}
    # ---- 坊长发放：中性 = 缺男丁先、人多先、户键；λ：亲疏先
    t_civil = np.full(n, np.inf); order_info = {}
    for f in fangs:
        idx = np.nonzero(fang == f)[0]
        head = Rp['offices']['fang'][f]
        needy = Rp['needy'][li[idx]]
        key = np.lexsort((G.keyrank[S[idx]], -size[idx], ~needy))
        o = idx[key]
        if lam and head >= 0:
            a = X.aff(Rp, head, li[o]); sc = np.arange(len(o)) / len(o) - lam * a / 4.0; o = o[np.argsort(sc, kind='stable')]
        # 钱只够 frac_now：前 frac_now 的户先领，其余等下一次收税
        k_now = int(math.floor(len(o) * frac_now + 1e-9))
        for r_, i in enumerate(o):
            base = t_fang_money[f] if r_ < k_now else t_fang_money[f] + D['next_collection']
            t_civil[i] = base + math.floor((r_ if r_ < k_now else r_ - k_now) / D['fang_cap'])
        order_info[int(f)] = dict(head=int(head), households=len(idx), first=int(S[o[0]]), last=int(S[o[-1]]))
    # ---- 教会
    t_church = np.full(n, np.inf)
    for b, fa in ((0, RG.ARIAN), (1, RG.NICENE)):
        m = np.nonzero(faith == fa)[0]
        if not len(m): continue
        t_b = D['to_elder'] + D['elder_up'] + D['bishop_decide']
        need_b = float(size[m].sum()) * D['relief_per_person']; frac_b = min(1.0, max(breserve[b], 0) / need_b) if need_b > 0 else 1.0
        ek = fang[m] * 3 + fa
        for k in np.unique(ek):
            idx = m[ek == k]; head = Rp['offices']['elder'][k]
            o = idx[np.lexsort((G.keyrank[S[idx]], -size[idx], ~Rp['needy'][li[idx]]))]
            if lam and head >= 0:
                a = X.aff(Rp, head, li[o]); sc = np.arange(len(o)) / len(o) - lam * a / 4.0; o = o[np.argsort(sc, kind='stable')]
            k_now = int(math.floor(len(o) * frac_b + 1e-9))
            for r_, i in enumerate(o[:k_now]): t_church[i] = t_b + D['bishop_down'] + math.floor(r_ / D['elder_cap'])
    t_first = np.minimum(t_civil, t_church)
    # ---- 人力：清废墟
    burned_by_fang = collections.Counter(fang[own].tolist())
    R = X.years[Y]; clear = {}
    for f, hcount in burned_by_fang.items():
        unaff = int(((R['fang'] == f) & ~np.isin(R['S'], S)).sum()); men = max(1, int(unaff * D['men_per_unaffected']))
        clear[int(f)] = dict(burned_houses=int(hcount), men_called=men, days=round(hcount * D['clear_days_per_house'] / men, 1), start=float(t_fang_know[fang == f].max()))
    def who(i):
        F_ = int(S[i]); return dict(key=G.M['keys'][F_], name=G.names[F_], faith=RG.FAITHS[int(faith[i])], role='房主' if own[i] else '租户', size=int(size[i]),
                                  district=RG.DNAME.get(G.dnames[int(dist[i])]), fang=int(fang[i]), needy=bool(Rp['needy'][li[i]]),
                                  civil_day=float(t_civil[i]), church_day=None if not np.isfinite(t_church[i]) else float(t_church[i]), first_day=float(t_first[i]))
    o = np.argsort(t_first, kind='stable')
    by = lambda m: dict(households=int(m.sum()), mean_day=round(float(t_first[m].mean()), 1) if m.any() else None, max_day=float(t_first[m].max()) if m.any() else None)
    return dict(victims=dict(households=n, people=int(size.sum()), owners=int(own.sum()), tenants=int((~own).sum()), ledger_houses_page=int(len(np.unique(Rp['rh'][li][own]))),
                             ledger_houses_city=int(X.dest_d[Y].sum()), ledger_houses_outside_page=out_houses, fangs=len(fangs), districts=[RG.DNAME.get(G.dnames[int(d)]) for d in dists]),
                money=dict(prefect_reserve_AF47=round(reserve, 1), need=round(need, 1), need_page=round(need_page, 1), need_outside=round(need_out, 1), covered_now=round(frac_now, 3),
                           bishop_reserve=[round(float(x), 1) for x in breserve]),
                levels=dict(fang_knows_day=[float(t_fang_know.min()), float(t_fang_know.max())], fang_reports_up_day=[min(t_fang_up.values()), max(t_fang_up.values())],
                            district_reports_day=[min(t_dist_up.values()), max(t_dist_up.values())], prefect_decides_day=t_dec, money_at_fang_day=t_dec + D['prefect_down'] + D['district_down'],
                            church_money_at_elder_day=D['to_elder'] + D['elder_up'] + D['bishop_decide'] + D['bishop_down']),
                relief_day=dict(civil=dict(first=float(t_civil.min()), median=float(np.median(t_civil)), last=float(t_civil.max())),
                                first_any=dict(first=float(t_first.min()), median=float(np.median(t_first)), last=float(t_first.max()))),
                by_group={'阿里乌派': by(faith == RG.ARIAN), '尼西亚派': by(faith == RG.NICENE), '还拜旧神': by(faith == RG.PAGAN),
                          '房主': by(own), '租户': by(~own), '缺男丁': by(Rp['needy'][li])},
                first5=[who(i) for i in o[:5]], last5=[who(i) for i in o[-5:]], clearing=clear, fang_order=order_info)


def main():
    t0 = time.time()
    G = RG.Registry('xero'); years, _ = G.build(40, 70)
    X = FI.Fiscal(G, years); F = X.run(41, 70)
    t = time.perf_counter(); r0 = simulate(X, F); t_sim = time.perf_counter() - t
    r1 = simulate(X, F, lam=0.5)
    # 偏袒让谁晚了：同一户 中性 vs λ 的差
    out = dict(days=DAYS, neutral=r0, favoritism_lambda05=dict(relief_day=r1['relief_day'], by_group=r1['by_group'], first5=r1['first5'], last5=r1['last5']),
               seconds=dict(simulate=round(t_sim, 4), total=round(time.time() - t0, 2)))
    json.dump(out, open(os.path.join(OUT, 'crisis_48_fire.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict(victims=r0['victims'], money=r0['money'], levels=r0['levels'], relief=r0['relief_day'], by_group=r0['by_group']), ensure_ascii=False, default=float))
    return X, F, out


if __name__ == '__main__':
    main()
