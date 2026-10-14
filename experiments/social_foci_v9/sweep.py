"""小网格扫描 c×a×q（27 组），可断点续跑。用法: python sweep.py YEAR [起 止]  ——Hark（刘线）"""
import json, sys, os, itertools, time, copy
import foci, metrics
year = int(sys.argv[1]); lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0; hi = int(sys.argv[3]) if len(sys.argv) > 3 else 999
CS = [0.5, 1.0, 2.0]; AS = [0.7, 0.85, 1.0]; QS = [0.0, 0.05, 0.15]
GRID = list(itertools.product(CS, AS, QS))
base = json.load(open('config.json'))
C = foci.build_city(year, base); C['_cfg'] = base; foci.prep(C)
os.makedirs('sweep', exist_ok=True)
for k, (c, a, q) in enumerate(GRID):
    if not (lo <= k < hi): continue
    fn = f'sweep/AF{year}_{k:02d}.json'
    if os.path.exists(fn): continue
    cfg = copy.deepcopy(base); cfg.update(c=c, a=a, q_closure=q)
    t = time.time(); T = foci.generate(C, cfg); tg = time.time() - t
    m = metrics.compute(C, T); m['gen_sec'] = tg; m['metric_sec'] = time.time() - t - tg
    h = metrics.hits(m); n, d = metrics.score(m)
    json.dump(dict(k=k, c=c, a=a, q=q, metrics=m, hits=h, n_hit=n, dist=d), open(fn, 'w'), ensure_ascii=False)
    print(k, c, a, q, 'hit', n, 'deg', m['median_degree'], 'cl', round(m['clustering'], 3), 'L', round(m['avg_path'], 2), 'Q', round(m['modularity'], 3), 'af', m['assort_faith'], 'ag', m['assort_guild'], 'odr', round(m['office_degree_ratio'], 2), 'obr', round(m['office_betw_ratio'], 2), 'cap', m['cap_share'], f'{tg:.1f}+{m["metric_sec"]:.1f}s', flush=True)
