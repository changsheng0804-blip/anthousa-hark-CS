"""规则预演 v4 · 敏感度：每个「假设」参数单独 ×0.5 / ×1.5，看结论变不变。
结论（基线）：
  C1 请愿年份：水 62、信仰 64、孤寡（修士补差）65 由钱 + 层级算对；挤 63 只有加「城市长官一年开一项请愿工程」的排队规则才对
  C2 瓶颈层：水 = 层层转呈；挤 = 城市长官排队；信仰 = 阿里乌派主教的钱；孤寡 = 干山区长的钱（区一级最薄）
  C3 偏袒：转移额主要由位置决定（|超出对照| 中位数 / 转移额中位数 < 0.1），第 1 名不变
  C4 大火：钱不是瓶颈（城库够），转呈是；还拜旧神的户最后拿到救济
usage: python3 sensitivity.py
"""
import os, sys, json, time, copy
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fiscal as FI, run_v4 as RV, crisis as CR  # noqa: E402
RG = FI.RG
OUT = os.path.join(HERE, 'out')


def conclusions(X, F, pp=None, D=None, fav=True):
    p = RV.petitions(X, F, pp=pp); q = RV.petitions(X, F, pp=pp, queue_one_per_year=True)
    c = dict(years_money={k: p[k]['predicted_year'] for k in RV.PETITIONS}, years_queue={k: q[k]['predicted_year'] for k in RV.PETITIONS},
             widow_monks=p['孤寡']['steps']['predicted_if_monks_fill'], bottleneck={k: p[k]['bottleneck'] for k in RV.PETITIONS})
    c['C1'] = (c['years_money']['水'] == 62 and c['years_money']['信仰'] == 64 and c['widow_monks'] == 65 and c['years_queue']['挤'] == 63)
    c['C2'] = (c['bottleneck']['水'].startswith('层层') and c['bottleneck']['信仰'].startswith('阿里乌派') and c['bottleneck']['孤寡'].startswith('干山区长')
               and (q['挤']['predicted_year'] > p['挤']['predicted_year'] or p['挤']['steps']['queue_wait_years'] > 0))
    if fav:
        f, res, _ = RV.favoritism(X, lam=X.P['lam'] or 0.5, K=6)
        ex = np.array([abs(r['excess']) for r in res]); tr = np.array([r['transfer'] for r in res])
        c['fav_ratio'] = round(float(np.median(ex) / max(np.median(tr), 1e-9)), 3); c['fav_top1'] = f['top8'][0]['name'] + ' ' + f['top8'][0]['key']
        c['fav_top8'] = [r['key'] for r in f['top8']]
        c['C3'] = c['fav_ratio'] < 0.1
    r = CR.simulate(X, F, D=D)
    c['crisis_last_day'] = r['relief_day']['first_any']['last']; c['crisis_covered'] = r['money']['covered_now']
    bg = r['by_group']; c['C4'] = (r['money']['covered_now'] >= 1.0 and bg['还拜旧神']['mean_day'] >= max(bg['阿里乌派']['mean_day'], bg['尼西亚派']['mean_day']))
    return c


def main():
    t0 = time.time()
    G = RG.Registry('xero'); years, _ = G.build(40, 70)
    base = FI.PARAM.copy(); base_bc = FI.BUILD_COST.copy()
    X = FI.Fiscal(G, years); F = X.run(41, 70)
    B = conclusions(X, F); top8_base = set(B['fav_top8'])
    rows = []
    def record(name, mult, c):
        rows.append(dict(param=name, mult=mult, C1=c['C1'], C2=c['C2'], C3=c.get('C3'), C4=c['C4'], years_money=c['years_money'], years_queue=c['years_queue'],
                         widow_monks=c['widow_monks'], bottleneck=c['bottleneck'], fav_ratio=c.get('fav_ratio'), fav_top1=c.get('fav_top1'),
                         fav_top8_overlap=len(top8_base & set(c.get('fav_top8', []))) if 'fav_top8' in c else None,
                         crisis_last_day=c['crisis_last_day'], crisis_covered=c['crisis_covered']))
    for k in base:
        if k in ('corvee_days',): continue
        for m in (0.5, 1.5):
            P = {k: base[k] * m} if k != 'lam' else {'lam': 0.5 * m}
            Xk = FI.Fiscal(G, years, P); Fk = Xk.run(41, 70)
            record(k, m, conclusions(Xk, Fk))
    for k in base_bc:
        for m in (0.5, 1.5):
            FI.BUILD_COST[k] = base_bc[k] * m
            Xk = FI.Fiscal(G, years); Fk = Xk.run(41, 70)
            record('造价系数.' + k, m, conclusions(Xk, Fk, fav=False))
            FI.BUILD_COST[k] = base_bc[k]
    for k in RV.PET_PARAM:
        if k == 'raised': continue
        for m in (0.5, 1.5):
            record('请愿.' + k, m, conclusions(X, F, pp={k: RV.PET_PARAM[k] * m}, fav=False))
    for k in CR.DAYS:
        for m in (0.5, 1.5):
            v = CR.DAYS[k] * m
            if isinstance(CR.DAYS[k], int): v = max(1, int(round(v)))
            record('大火.' + k, m, conclusions(X, F, D={k: v}, fav=False))
    # 极端情形：城库是空的（48 年前的结余全被上交或花掉）
    Xe = FI.Fiscal(G, years, {'remit': 1.0}); Fe = Xe.run(41, 70)
    rows.append(dict(param='极端：remit=1.0（城库不留钱）', mult=None, **{k: v for k, v in CR.simulate(Xe, Fe)['money'].items()}, relief=CR.simulate(Xe, Fe)['relief_day']))
    summ = dict(runs=len(rows) - 1, C1_holds=sum(1 for r in rows if r.get('C1')), C2_holds=sum(1 for r in rows if r.get('C2')),
                C3_holds=sum(1 for r in rows if r.get('C3')), C3_tested=sum(1 for r in rows if r.get('C3') is not None), C4_holds=sum(1 for r in rows if r.get('C4')),
                C1_breaks=[(r['param'], r['mult'], r['years_money'], r['years_queue'], r['widow_monks']) for r in rows if r.get('C1') is False],
                C2_breaks=[(r['param'], r['mult'], r['bottleneck']) for r in rows if r.get('C2') is False],
                C3_breaks=[(r['param'], r['mult'], r['fav_ratio']) for r in rows if r.get('C3') is False],
                C4_breaks=[(r['param'], r['mult'], r['crisis_covered'], r['crisis_last_day']) for r in rows if r.get('C4') is False],
                top1_changes=[(r['param'], r['mult'], r['fav_top1']) for r in rows if r.get('fav_top1') and r['fav_top1'] != B['fav_top1']])
    out = dict(base=B, summary=summ, rows=rows, seconds=round(time.time() - t0, 1))
    json.dump(out, open(os.path.join(OUT, 'sensitivity.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(dict(base=B, summary=summ), ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
