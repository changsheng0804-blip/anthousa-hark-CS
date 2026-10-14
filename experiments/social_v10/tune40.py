"""AF40 初始化截面上的预调（不入扫描计数）：只看聚类/闭合占比/Dunbar。——Hark（刘线）"""
import json, sys, collections, copy, numpy as np, model, metrics
base = json.load(open('config.json')); W = model.World()
for spec in sys.argv[1:]:
    cfg = copy.deepcopy(base)
    for kv in spec.split(','):
        k, v = kv.split('='); cfg[k] = float(v)
    S = model.Sim(W, cfg); R, m = S.step(40, None, None)
    uk, s, tier, inv, keep = S.output(R, 40)
    st = collections.Counter(model.TYPES[t] for t in R['typ'][keep[inv]])
    mt = metrics.compute(W.N, m['stand'], uk, tier, st, m['faith'], m['M']['行会'], np.zeros(W.N, bool), S.latent[0], s, heavy=True)
    print(spec, mt['median_cum_layer'], 'cl', round(mt['clustering'], 3), 'L', round(mt['avg_path'], 2), 'Q', round(mt['modularity'], 3), 'clos', round(mt['closure_share'], 3), 'lat', mt['latent_median_degree'], round(mt['latent_degree_skew'],2), round(mt['latent_max_over_median'],1), flush=True)
