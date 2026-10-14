"""v12 扫描 12 组 = 常客群大小 g{8,15,25} × 跨群占比 x{0,0.05} × 群内成连概率 p_in{0.8,1.0}；其余沿用 v11 最佳组 s1k2.0（k=2）。
p_in 两档由 AF41 探针选定（g15/p0.6 与 g15/p0.9 的认识层累计仅 39–42 户 <47.6）。
用法：python3 sweep12.py <worker> <workers>   ——Hark（刘线）"""
import json, sys, copy, os
import run12
GRID = [(g, x, p) for g in (8, 15, 25) for x in (0.0, 0.05) for p in (0.8, 1.0)]
if __name__ == '__main__':
    base = json.load(open('config.json'))
    w, nw = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs('sweep', exist_ok=True)
    for j, (g, x, p) in enumerate(GRID):
        if j % nw != w: continue
        fn = f'sweep/g{j}.json'
        if os.path.exists(fn): continue
        cfg = copy.deepcopy(base); cfg.update(group_size=g, cross_x=x, p_in=p)
        lf = open(fn + '.log', 'w')
        res = run12.simulate(cfg, (50, 60, 70), log=lambda *a: print(*a, file=lf, flush=True))
        res['config'] = cfg; res['sim'] = dict(j=j, group_size=g, cross_x=x, p_in=p)
        json.dump(res, open(fn, 'w'), ensure_ascii=False, default=float)
