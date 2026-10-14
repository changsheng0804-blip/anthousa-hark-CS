"""汇总 18 组扫描 → sweep_summary.json；选最佳组写 config_best.json。
排序：AF50/60/70 三年全落靶优先，其次三年命中数之和、再次靶距之和。——Hark（刘线）"""
import json, glob, collections
import numpy as np
import core

KEY = ['median_cum_layer', 'clustering', 'avg_path', 'modularity', 'assort_faith', 'assort_guild', 'closure_share',
       'latent_degree_skew', 'latent_max_over_median', 'office_strength_ratio', 'office_betw_ratio', 'cap_share',
       'office_median_degree', 'nonoffice_median_degree', 'mean_degree']
rows = []; miss_all = collections.Counter(); miss70 = collections.Counter()
for fn in sorted(glob.glob('sweep/s*.json')):
    r = json.load(open(fn)); sim = r['sim']
    for k in ('1.0', '1.5', '2.0'):
        Y = r[k]['years']; per = {}; allhit = True; nh = 0; ds = 0
        for y in ('50', '60', '70'):
            h = Y[y]['hits']; ev = {a: b for a, b in h.items() if b is not None}
            miss = [a for a, b in ev.items() if not b]
            per[y] = dict(n_hit=len(ev) - len(miss), n_eval=len(ev), miss=miss, dist=round(core.dist(Y[y]['metrics']), 4))
            allhit &= not miss; nh += per[y]['n_hit']; ds += per[y]['dist']
            miss_all.update(miss)
            if y == '70': miss70.update(miss)
        m70 = {a: Y['70']['metrics'].get(a) for a in KEY}
        rows.append(dict(id=f"s{sim['j']}k{k}", **sim, office_cap_mult=float(k), all_hit_50_60_70=allhit, hits_sum=nh, dist_sum=round(ds, 4),
                         per=per, m70=m70, survival_70=Y['70'].get('survival'),
                         clustering_by_year={y: Y[y]['metrics'].get('clustering') for y in ('50', '60', '70')}))
rows.sort(key=lambda d: (not d['all_hit_50_60_70'], -d['hits_sum'], d['dist_sum']))
best = rows[0]
out = dict(grid_size=len(rows), n_all_hit=sum(d['all_hit_50_60_70'] for d in rows), all_hit=[d['id'] for d in rows if d['all_hit_50_60_70']],
           best=best['id'], miss_counts_over_50_60_70=dict(miss_all.most_common()), miss_counts_70=dict(miss70.most_common()), table=rows)
json.dump(out, open('sweep_summary.json', 'w'), ensure_ascii=False, indent=1, default=float)
cfg = json.load(open(f"sweep/s{best['j']}.json"))['config']; cfg['office_cap_mult'] = best['office_cap_mult']
cfg['_doc'] = cfg['_doc'] + f"  最佳组 {best['id']}：市场 {best['market_strength']}、c {best['c']}、辖民容量 {best['office_hub_capacity']}、k {best['office_cap_mult']}。"
json.dump(cfg, open('config_best.json', 'w'), ensure_ascii=False, indent=1)
for d in rows:
    print(d['id'], d['market_strength'], d['c'], d['office_hub_capacity'], d['office_cap_mult'], d['all_hit_50_60_70'], d['hits_sum'], d['dist_sum'],
          [d['per'][y]['miss'] for y in ('50', '60', '70')], {a: (round(v, 3) if isinstance(v, float) else v) for a, v in d['m70'].items()})
print('n_all_hit', out['n_all_hit'], 'best', best['id'], out['miss_counts_over_50_60_70'])
