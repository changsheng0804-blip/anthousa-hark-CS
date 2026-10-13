"""规则预演 v5 第二段 · 各选任机制重跑（干山）：请愿年份（许可链）、λ=0.5 偏袒、48 年大火带空缺延误的救济天数。
只 import v3/v4/v5 第一段（不运行写 out/ 的脚本）。把每个机制逐年的现任写进 years 副本，新建 v4 Fiscal 复用。
usage: python3 rerun.py [--lots 20] [--vac 10]
输出 out/rerun_xero.json
"""
import os, sys, time, json, math, inspect, textwrap, collections, copy
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'rules_v4_fiscal'))
import succession as SU  # noqa: E402
import permits as PM  # noqa: E402
import fiscal as FI  # noqa: E402
import run_v4 as R4  # noqa: E402  (只调函数，不跑 main)
import crisis as CR  # noqa: E402
RG = FI.RG
OUT = os.path.join(HERE, 'out')

# ---- 让 World.run 逐年记下现任（源码只在 Y1 记 dyn；这里改成每年记，其余一字不动）
_src = textwrap.dedent(inspect.getsource(SU.World.run))
_src = _src.replace("if Y == Y1: dyn[key] = h[0] if h else -1", "dyn[(Y,) + key] = h[0] if h else -1")
_src = _src.replace("return dict(changes=changes,", "return dict(dyn=dyn, changes=changes,")
assert 'dyn[(Y,) + key]' in _src and 'dyn=dyn' in _src
_ns = {}; exec(compile(_src, 'succession.run(patched)', 'exec'), vars(SU), _ns); SU.World.run_years = _ns['run']


def mech_years(W, mech, seed=0):
    r = W.run_years(mech, seed=seed)
    yrs = {}
    for Y, R in W.years.items():
        R2 = dict(R); off = {}
        for o in SU.OFF:
            n = len(R['offices'][o]); off[o] = np.array([r['dyn'].get((Y, o, k), -1) for k in range(n)], dtype=np.int64)
        R2['offices'] = off; yrs[Y] = R2
    return yrs


# ---- 48 年大火：v4 crisis.simulate + 空缺延误（假设 V1：空缺坊长 +N 天上报、+N 天发放（邻坊代管）；空缺区长上下行各 +N；空缺长老本组教会发放 +N）
def simulate_vac(X, F, Nvac=10, Y=48):
    base = CR.simulate(X, F, Y=Y)
    D = CR.DAYS; G = X.G
    Rp = X.years[Y - 1]; vict = X.evict[Y]; li = Rp['loc'][vict]
    n = len(li); S = Rp['S'][li]; size = Rp['size'][li]; own = Rp['own'][li]; fang = Rp['fang'][li]; dist = Rp['dist'][li]; faith = Rp['faith'][li]
    reserve = sum(float(F[y]['T']['民政/城市长官']['kept'][0]) for y in range(41, Y))
    breserve = np.array([sum(float(F[y]['T']['教会/主教']['kept'][b]) for y in range(41, Y)) for b in (0, 1)])
    out_houses = int(X.dest_d[Y].sum()) - len(np.unique(Rp['rh'][li][own]))
    need = float(size.sum()) * D['relief_per_person'] + out_houses * 9 * D['relief_per_person']
    fz = Rp['offices']['fang']; dz = Rp['offices']['district']; ez = Rp['offices']['elder']
    vf = lambda f: Nvac if fz[f] < 0 else 0
    vd = lambda d: Nvac if dz[d] < 0 else 0
    t_know = np.where(own, D['to_fang'], D['tenant_to_owner'] + D['to_fang']).astype(float)
    fangs = np.unique(fang)
    t_fang_up = {f: t_know[fang == f].max() + D['fang_up'] + vf(f) for f in fangs}
    dists = np.unique(dist)
    t_dist_up = {d: max(t_fang_up[f] for f in np.unique(fang[dist == d])) + D['district_up'] + vd(d) for d in dists}
    t_dec = max(t_dist_up.values()) + D['prefect_decide']
    frac = min(1.0, reserve / need) if need > 0 else 1.0
    t_civil = np.full(n, np.inf)
    for f in fangs:
        idx = np.nonzero(fang == f)[0]; d = int(dist[idx[0]])
        o = idx[np.lexsort((G.keyrank[S[idx]], -size[idx], ~Rp['needy'][li[idx]]))]
        t0 = t_dec + D['prefect_down'] + D['district_down'] + vd(d) + vf(f)
        k_now = int(math.floor(len(o) * frac + 1e-9))
        for r_, i in enumerate(o):
            b = t0 if r_ < k_now else t0 + D['next_collection']
            t_civil[i] = b + math.floor((r_ if r_ < k_now else r_ - k_now) / D['fang_cap'])
    t_church = np.full(n, np.inf)
    for b, fa in ((0, RG.ARIAN), (1, RG.NICENE)):
        m = np.nonzero(faith == fa)[0]
        if not len(m): continue
        t_b = D['to_elder'] + D['elder_up'] + D['bishop_decide']
        need_b = float(size[m].sum()) * D['relief_per_person']; frac_b = min(1.0, max(breserve[b], 0) / need_b) if need_b > 0 else 1.0
        ek = fang[m] * 3 + fa
        for k in np.unique(ek):
            idx = m[ek == k]; o = idx[np.lexsort((G.keyrank[S[idx]], -size[idx], ~Rp['needy'][li[idx]]))]
            ve = Nvac if ez[k] < 0 else 0
            k_now = int(math.floor(len(o) * frac_b + 1e-9))
            for r_, i in enumerate(o[:k_now]): t_church[i] = t_b + D['bishop_down'] + ve + math.floor(r_ / D['elder_cap'])
    t = np.minimum(t_civil, t_church)
    by = lambda msk: round(float(t[msk].mean()), 2) if msk.any() else None
    vac = dict(fang=int(sum(1 for f in fangs if fz[f] < 0)), district=int(sum(1 for d in dists if dz[d] < 0)),
               elder=int(sum(1 for k in np.unique(fang * 3 + faith) if ez[k] < 0 and (k % 3) != RG.PAGAN)))
    # 无空缺时应与 v4 原版一致（自检）
    return dict(days={'尼西亚派': by(faith == RG.NICENE), '阿里乌派': by(faith == RG.ARIAN), '还拜旧神': by(faith == RG.PAGAN), '全体': by(np.ones(n, bool))},
                v4_original_days={k: base['by_group'][k]['mean_day'] for k in ('尼西亚派', '阿里乌派', '还拜旧神')},
                vacant_on_path=vac, households=n, fangs=len(fangs))


def one(W, yrs, D_u, Nvac, lam=0.5):
    X = FI.Fiscal(W.G, yrs); F = X.run(41, 70)
    money = R4.petitions(X, F, use_reserve=True)
    pet = PM.petitions_with_permits(yrs, money, D_u)
    fav, res, _ = R4.favoritism(X, lam=lam)
    top3 = [dict(node=f"坊 {r['fang']} 坊长", head=r['head'], key=r['key'], name=r['name'], years=r['years'], excess=r['excess'], transfer=r['transfer']) for r in fav['top8'][:3]]
    exc = np.array([r['excess'] for r in res])
    cr = simulate_vac(X, F, Nvac)
    return dict(petition_year={k: pet[k]['year'] for k in pet}, petition_t={k: pet[k]['t'] for k in pet},
                permit_wait={k: pet[k]['permit_wait'] for k in pet}, total_wait={k: pet[k]['total_wait_from_raise'] for k in pet},
                money_year={k: money[k]['predicted_year'] for k in PM.CHAIN}, permit_log={k: pet[k]['log'] for k in pet},
                fav_top3=top3, fav_excess_pos_sum=round(float(exc[exc > 0].sum()), 2), fav_excess_sum=round(float(exc.sum()), 2),
                fav_transfer_total=fav['distribution']['transfer']['total'], fav_nodes=len(res), crisis=cr)


def main(nlots=20, Nvac=10):
    t0 = time.time()
    W = SU.World('xero')
    X0 = FI.Fiscal(W.G, W.years); F0 = X0.run(41, 70); m0 = R4.petitions(X0, F0, use_reserve=True)
    cal = PM.calibrate(W.years, m0); D_u = cal['D_u']
    res = {'G1': one(W, W.years, D_u, Nvac)}
    for mech in SU.MECH:
        res[mech] = one(W, mech_years(W, mech, 0), D_u, Nvac)
    lots = [one(W, mech_years(W, '抽签', s), D_u, Nvac) for s in range(nlots)]
    def mean(f): return round(float(np.mean([f(r) for r in lots])), 2)
    res['抽签均值'] = dict(
        petition_year={k: mean(lambda r: r['petition_year'][k]) for k in PM.CHAIN},
        petition_t={k: mean(lambda r: r['petition_t'][k]) for k in PM.CHAIN},
        permit_wait={k: mean(lambda r: r['permit_wait'][k]) for k in PM.CHAIN},
        total_wait={k: mean(lambda r: r['total_wait'][k]) for k in PM.CHAIN},
        fav_excess_pos_sum=mean(lambda r: r['fav_excess_pos_sum']), fav_transfer_total=mean(lambda r: r['fav_transfer_total']),
        fav_top3_seed0=lots[0]['fav_top3'],
        fav_top1_excess_mean=mean(lambda r: r['fav_top3'][0]['excess']),
        crisis=dict(days={g: mean(lambda r: r['crisis']['days'][g]) for g in ('尼西亚派', '阿里乌派', '还拜旧神', '全体')},
                    vacant_on_path={k: mean(lambda r: r['crisis']['vacant_on_path'][k]) for k in ('fang', 'district', 'elder')}),
        petition_year_range={k: [min(r['petition_year'][k] for r in lots), max(r['petition_year'][k] for r in lots)] for k in PM.CHAIN}, n=nlots)
    # 敏感度：D_u 区间两端、空缺延误 5/20 天（只看 G1 与各机制的年份 / 天数）
    sens = {}
    for D in cal['interval']:
        sens[f'D_u={D}'] = {'G1': {k: v['year'] for k, v in PM.petitions_with_permits(W.years, m0, D).items()}}
    out = dict(scope='xero', D_u=cal, permit_chain={k: dict(what=v['what'], party=str(v['party']), gates=[g[0] for g in v['gates']], ledger=v['ledger']) for k, v in PM.CHAIN.items()},
               Nvac_days=Nvac, lam=0.5, results=res, sensitivity=sens, seconds=round(time.time() - t0, 1))
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, 'rerun_xero.json'), 'w'), ensure_ascii=False, indent=1, default=lambda x: x.item() if hasattr(x, 'item') else str(x))
    print_table(out)
    return out


def print_table(out):
    res = out['results']
    print(f"D_u = {out['D_u']['D_u']} 年（区间 {out['D_u']['interval']}）  空缺延误 {out['Nvac_days']} 天  耗时 {out['seconds']} s")
    print('| 机制 | 请愿年份 水/挤/信仰/孤寡 | 许可等待合计（年）| 偏袒前 3（超出份）| 总超出（正）| 大火 尼西亚/阿里乌/旧神（天）|')
    for m, r in res.items():
        py = '/'.join(str(r['petition_year'][k]) for k in PM.CHAIN)
        pw = round(sum(r['permit_wait'].values()), 2)
        t3 = r.get('fav_top3') or r.get('fav_top3_seed0')
        t3s = '；'.join(f"{x['node']} {x['name']}{x['key']} {x['excess']:+.1f}" for x in t3)
        c = r['crisis']['days']
        print(f"| {m} | {py} | {pw} | {t3s} | {r['fav_excess_pos_sum']} | {c['尼西亚派']}/{c['阿里乌派']}/{c['还拜旧神']} |")


if __name__ == '__main__':
    a = sys.argv
    nl = int(a[a.index('--lots') + 1]) if '--lots' in a else 20
    nv = int(a[a.index('--vac') + 1]) if '--vac' in a else 10
    main(nl, nv)
