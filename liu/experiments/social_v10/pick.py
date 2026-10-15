"""汇总扫描、选最佳组，写 config_best.json 与 sweep_summary.json。——Hark（刘线）"""
import json, glob, collections
import metrics

CHK = ('50', '60', '70')
rows = []
for fn in sorted(glob.glob('sweep/g*.json')):
    r = json.load(open(fn)); g = r['grid']
    per = {}
    for y in CHK:
        h = r['years'][y]['hits']
        per[y] = dict(n_hit=sum(1 for v in h.values() if v), n_eval=sum(1 for v in h.values() if v is not None),
                      miss=[k for k, v in h.items() if v is False], dist=round(metrics.dist(r['years'][y]['metrics']), 4))
    allhit = all(per[y]['n_hit'] == per[y]['n_eval'] for y in CHK)
    m70 = r['years']['70']['metrics']
    rows.append(dict(**g, all_hit_50_60_70=allhit, hit70=f"{per['70']['n_hit']}/{per['70']['n_eval']}", per=per,
                     dist_sum=round(sum(per[y]['dist'] for y in CHK), 4),
                     m70={k: m70.get(k) for k in ('median_cum_layer', 'clustering', 'avg_path', 'modularity', 'assort_faith', 'assort_guild', 'closure_share',
                                                 'latent_degree_skew', 'latent_max_over_median', 'office_strength_ratio', 'office_betw_ratio', 'cap_share')},
                     assort_faith_60=r['years']['60']['metrics'].get('assort_faith'), survival_70=r['years']['70'].get('survival')))
full = [r for r in rows if r['all_hit_50_60_70']]
pool = full or rows
best = min(pool, key=lambda r: (-sum(r['per'][y]['n_hit'] for y in CHK), r['dist_sum'], r['k']))
miss = collections.Counter(k for r in rows for y in CHK for k in r['per'][y]['miss'])
miss70 = collections.Counter(k for r in rows for k in r['per']['70']['miss'])
out = dict(grid_size=len(rows), n_all_hit=len(full), all_hit=[r['k'] for r in full], best=best,
           n_hit70_full=sum(1 for r in rows if r['per']['70']['n_hit'] == r['per']['70']['n_eval']),
           miss_counts_over_50_60_70=dict(miss.most_common()), miss_counts_70=dict(miss70.most_common()), table=rows)
json.dump(out, open('sweep_summary.json', 'w'), ensure_ascii=False, indent=1)
cfg = json.load(open(f"sweep/g{best['k']:02d}.json"))['config']
json.dump(cfg, open('config_best.json', 'w'), ensure_ascii=False, indent=1)
print(len(rows), 'all-hit', len(full), [r['k'] for r in full], 'best', best['k'], best['p_cross_faith'], best['homophily_faith'], best['market_strength'], 'miss', dict(miss.most_common()))
for r in rows:
    print(r['k'], r['p_cross_faith'], r['homophily_faith'], r['market_strength'], r['all_hit_50_60_70'], r['hit70'], {y: r['per'][y]['miss'] for y in CHK},
          [round(x, 3) if isinstance(x, float) else x for x in (r['m70']['clustering'], r['m70']['assort_faith'], r['m70']['closure_share'], r['m70']['avg_path'])], r['m70']['median_cum_layer'])
