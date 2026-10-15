"""汇总 12 组 → sweep_summary.json；选最佳组写 config_best.json。
排序：AF50/60/70 三年全落靶优先，其次三年命中和、再次靶距和。另报：Dunbar 最内层改用未取整靶 1.6–3.0（仅说明）时的全落靶组。——Hark（刘线）"""
import json, glob, collections
import core12
core = core12.core11
KEY = ['median_cum_layer', 'clustering', 'avg_path', 'modularity', 'assort_faith', 'closure_share', 'office_strength_ratio', 'office_betw_ratio',
       'latent_max_over_median', 'market_share', 'cap_share', 'mean_degree']
rows = []; miss_all = collections.Counter()
for fn in sorted(glob.glob('sweep/g*.json'), key=lambda f: int(f.split('/g')[1].split('.')[0])):
    r = json.load(open(fn)); sim = r['sim']; Y = r['2.0']['years']
    per = {}; allhit = True; allhit_alt = True; nh = 0; ds = 0
    for y in ('50', '60', '70'):
        h = {a: b for a, b in Y[y]['hits'].items() if b is not None}
        miss = [a for a, b in h.items() if not b]
        alt_miss = [a for a in miss if a != 'dunbar_cum_3'] + ([] if Y[y]['hit_dunbar3_unrounded'] else ['dunbar_cum_3(1.6–3.0)'])
        per[y] = dict(n_hit=len(h) - len(miss), n_eval=len(h), miss=miss, miss_alt=alt_miss, dist=round(core.dist(Y[y]['metrics']), 4))
        allhit &= not miss; allhit_alt &= not alt_miss; nh += per[y]['n_hit']; ds += per[y]['dist']; miss_all.update(miss)
    rows.append(dict(id=f"g{sim['j']}", **sim, all_hit_50_60_70=allhit, all_hit_alt_dunbar3=allhit_alt, hits_sum=nh, dist_sum=round(ds, 4), per=per,
                     m70={a: Y['70']['metrics'].get(a) for a in KEY}, survival_70=Y['70'].get('survival'),
                     clustering_by_year={y: Y[y]['metrics'].get('clustering') for y in ('50', '60', '70')},
                     group_size_70=r['group_stats']['70']))
rows.sort(key=lambda d: (not d['all_hit_50_60_70'], not d['all_hit_alt_dunbar3'], -d['hits_sum'], d['dist_sum']))
best = rows[0]
out = dict(grid_size=len(rows), n_all_hit=sum(d['all_hit_50_60_70'] for d in rows), all_hit=[d['id'] for d in rows if d['all_hit_50_60_70']],
           n_all_hit_alt_dunbar3=sum(d['all_hit_alt_dunbar3'] for d in rows), all_hit_alt_dunbar3=[d['id'] for d in rows if d['all_hit_alt_dunbar3']],
           best=best['id'], miss_counts_over_50_60_70=dict(miss_all.most_common()), table=rows)
json.dump(out, open('sweep_summary.json', 'w'), ensure_ascii=False, indent=1, default=float)
cfg = json.load(open(f"sweep/{best['id']}.json"))['config']
cfg['_doc'] += f"  最佳组 {best['id']}：g {best['group_size']}、x {best['cross_x']}、p_in {best['p_in']}。"
json.dump(cfg, open('config_best.json', 'w'), ensure_ascii=False, indent=1)
for d in rows:
    print(d['id'], d['group_size'], d['cross_x'], d['p_in'], d['all_hit_50_60_70'], d['all_hit_alt_dunbar3'], d['hits_sum'], [d['per'][y]['miss'] for y in ('50', '60', '70')],
          {a: (round(v, 3) if isinstance(v, float) else v) for a, v in d['m70'].items()}, round(d['survival_70'], 3))
print('n_all_hit', out['n_all_hit'], out['all_hit'], 'alt', out['n_all_hit_alt_dunbar3'], 'best', best['id'], out['miss_counts_over_50_60_70'])
