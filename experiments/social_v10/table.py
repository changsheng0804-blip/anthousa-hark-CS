"""从 results.json 打印 REPORT 用的表。——Hark（刘线）"""
import json
R = json.load(open('results.json')); Y = R['years']
def f(v, d=3):
    if v is None: return '—'
    if isinstance(v, float): return f'{v:.{d}f}'
    return str(v)
rows = [('户数 / 输出边数', lambda m, r: f"{m['n']:,} / {m['edges']:,}"),
        ('Dunbar 累计中位 5/15/50/150', lambda m, r: '/'.join(f'{x:g}' for x in m['median_cum_layer'])),
        ('度中位（潜在网中位/最大）', lambda m, r: f"{m['median_degree']:g}（{m['latent_median_degree']:g}/{m['latent_max_degree']}）"),
        ('触 150 上限户占比', lambda m, r: f(m['cap_share'])),
        ('平均聚类', lambda m, r: f(m['clustering'])),
        ('平均路径 / 估计直径', lambda m, r: f"{f(m['avg_path'], 2)} / {f(m['diameter_est'], 0)}"),
        ('潜在网度偏度 / 最大÷中位', lambda m, r: f"{f(m['latent_degree_skew'], 2)} / {f(m['latent_max_over_median'], 2)}"),
        ('Louvain 模块度（社区数）', lambda m, r: f"{f(m['modularity'])}（{m['n_communities']}）"),
        ('信仰同配', lambda m, r: f(m['assort_faith'])),
        ('行会同配', lambda m, r: f(m['assort_guild'])),
        ('职位/普通 强度和比（全图度比）', lambda m, r: f"{f(m['office_strength_ratio'], 2)}（{f(m['office_degree_ratio_full'], 2)}）"),
        ('职位/普通 中介比', lambda m, r: f(m['office_betw_ratio'], 2)),
        ('三元闭合来源占比', lambda m, r: f(m['closure_share'])),
        ('关系年存活率（双方仍在）', lambda m, r: f(r.get('survival'))),
        ('落靶', lambda m, r: f"{sum(1 for v in r['hits'].values() if v)}/{sum(1 for v in r['hits'].values() if v is not None)}")]
print('| 指标 | ' + ' | '.join(f'AF{y}' for y in (40, 50, 60, 70)) + ' |')
print('|---|' + '---|' * 4)
for name, fn in rows:
    print(f'| {name} | ' + ' | '.join(fn(Y[str(y)]['metrics'], Y[str(y)]) for y in (40, 50, 60, 70)) + ' |')
print()
# 逐年摘要
import numpy as np
ks = ['clustering', 'avg_path', 'modularity', 'assort_faith', 'closure_share', 'dunbar_cum_150']
for k in ks:
    v = [Y[str(y)]['metrics'].get(k) for y in range(40, 71)]
    v2 = [x for x in v if x is not None]
    print(k, 'min', round(min(v2), 3), 'max', round(max(v2), 3))
sv = [Y[str(y)]['survival'] for y in range(41, 71)]
print('survival min/median/max', round(min(sv), 3), round(float(np.median(sv)), 3), round(max(sv), 3))
for t in ('强', '中', '弱', '认识'):
    print(t, round(float(np.median([Y[str(y)]['survival_by_tier'][t] for y in range(41, 71)])), 3))
miss = {}
for y in range(40, 71):
    for k, v in Y[str(y)]['hits'].items():
        if v is False: miss[k] = miss.get(k, 0) + 1
print('yearly miss counts (31 年)', miss)
L = [(y, Y[str(y)]['lost']) for y in range(41, 71) if Y[str(y)]['lost']['demolished']]
print('lost', sum(l['demolished'] for _, l in L), sum(l['ties_lost'] for _, l in L), [(y, l['demolished'], l['ties_lost'], l['households_losing']) for y, l in L])
print('new hh', sum(Y[str(y)]['new_households'] for y in range(41, 71)))
print('step sec median/max', float(np.median([Y[str(y)]['step_sec'] for y in range(41, 71)])), max(Y[str(y)]['step_sec'] for y in range(41, 71)))
print('src70', Y['70']['metrics']['source_label_share'])
print('det', R['determinism']['all_identical'])
print(json.dumps(R['lineage'], ensure_ascii=False))
