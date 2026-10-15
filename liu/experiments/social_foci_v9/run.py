"""用最佳参数输出 ties_AF{40,50,60,70}.json.gz，验证确定性与局部增量。——Hark（刘线）"""
import json, gzip, hashlib, time, copy, glob
import numpy as np
import foci, metrics
base = json.load(open('config.json'))
R = [json.load(open(f)) for f in sorted(glob.glob('sweep/AF70_*.json'))]
full = [r for r in R if r['n_hit'] == len(metrics.TARGETS)]
def margin(r):  # 次级排序：有界靶（度/聚类/路径）离边界的最小相对余量
    m = r['metrics']; out = []
    for k in ('median_degree', 'clustering', 'avg_path'):
        lo, hi, _ = metrics.TARGETS[k]; v = m[k]
        out.append(min(v - lo, hi - v) / (hi - lo))
    return min(out)
best = max(full, key=margin)
cfg = copy.deepcopy(base); cfg.update(c=best['c'], a=best['a'], q_closure=best['q'])
json.dump(cfg, open('config_best.json', 'w'), ensure_ascii=False, indent=1)
LN = cfg['layer_names']
def digest(T):
    h = hashlib.sha256()
    for (u, v) in sorted(T): t = T[(u, v)]; h.update(f'{u},{v},{t["tier"]},{t["w"]},{"|".join(t["src"])};'.encode())
    return h.hexdigest()[:16]
res = dict(sweep=dict(grid_size=len(R), n_full_hit=len(full), full_hit=[dict(k=r['k'], c=r['c'], a=r['a'], q=r['q'], margin=round(margin(r), 4)) for r in full],
           miss_counts={}, best=dict(k=best['k'], c=best['c'], a=best['a'], q=best['q'])), targets={k: list(v) for k, v in metrics.TARGETS.items()}, years={})
import collections
res['sweep']['miss_counts'] = dict(collections.Counter(k for r in R for k, v in r['hits'].items() if v is False))
res['sweep']['table'] = [dict(k=r['k'], c=r['c'], a=r['a'], q=r['q'], n_hit=r['n_hit'], **{x: r['metrics'][x] for x in ('median_degree', 'clustering', 'avg_path', 'modularity', 'degree_skew', 'max_over_median', 'assort_faith', 'assort_guild', 'office_degree_ratio', 'office_betw_ratio', 'cap_share')}) for r in R]
import sys
YS = [int(x) for x in sys.argv[1:]] or [40, 50, 60, 70]
try: res["years"] = json.load(open("results.json"))["years"]
except Exception: pass
for y in YS:
    C = foci.build_city(y, cfg); C['_cfg'] = cfg; foci.prep(C)
    t = time.time(); T = foci.generate(C, cfg); tg = time.time() - t
    T2 = foci.generate(C, cfg)
    d1, d2 = digest(T), digest(T2)
    m = metrics.compute(C, T); m['gen_sec'] = round(tg, 2)
    edges = [[C['ids'][u], C['ids'][v], LN[t['tier']], t['w'], t['src']] for (u, v), t in sorted(T.items())]
    out = dict(year=y, _doc='户-户社会关系（v9 焦点模型）。edges=[户A,户B,层级(强/中/弱/认识),强度,来源焦点列表]；来源焦点「类型:场所id」。参数见 config。——Hark（刘线）',
               config=cfg, n_households=C['N'], edges=edges)
    with gzip.open(f'ties_AF{y}.json.gz', 'wt', encoding='utf-8') as f: json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    # 局部增量：新户落在中位户门口
    raw = foci.generate_raw(C, cfg)
    before = {k: (round(v['w'], 6), len(v['src'])) for k, v in raw.items()}
    like = int(np.argsort([len(C['foci'].get(('门口路口', C['door'][u]), [])) if C['door'][u] else 0 for u in range(C['N'])])[C['N'] // 2])
    t = time.time(); new, touched = foci.add_household(C, cfg, raw, 'h_new_test', like); tl = time.time() - t
    changed_old = sum(1 for k, v in before.items() if (round(raw[k]['w'], 6), len(raw[k]['src'])) != v)
    nid = C['N'] - 1
    focus_members = set()
    for ft in ('门口路口', '街段', '坊', '行会', '教堂会众', '井/水池'):
        fid = {'门口路口': C['door'], '街段': C['seg'], '坊': C['ward'], '行会': C['guild'], '教堂会众': C['church'], '井/水池': C['well']}[ft][nid]
        if fid: focus_members |= set(C['foci'][(ft, fid)])
    others = [v for e in new for v in e if v != nid]
    outside = [v for v in others if v not in focus_members]
    srcs = collections.Counter(raw[e]['src'][0].split(':')[0] for e in new)
    tfull = tg
    res['years'][y] = dict(metrics=m, hits=metrics.hits(m), determinism=dict(run1=d1, run2=d2, identical=d1 == d2),
                           incremental=dict(sec=round(tl, 4), full_regen_sec=round(tfull, 2), new_edges=len(new), old_edges_changed=changed_old,
                                            partners_outside_own_foci=len(outside), new_edge_sources=dict(srcs), touched_households=len(touched)), file=f'ties_AF{y}.json.gz')
    print(y, m['n'], m['edges'], 'deg', m['median_degree'], 'cl', round(m['clustering'], 3), 'L', round(m['avg_path'], 2), 'Q', round(m['modularity'], 3), 'hits', sum(1 for v in metrics.hits(m).values() if v), [k for k, v in metrics.hits(m).items() if v is not True], d1 == d2, res['years'][y]['incremental'], flush=True)
    json.dump(res, open('results.json', 'w'), ensure_ascii=False, indent=1, default=float)
