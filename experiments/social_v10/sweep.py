"""小扫描（24 组）：跨信仰婚姻概率 × 信仰同质性折扣 × 市场强度。每组 AF40 起逐年连续跑到 AF70，heavy 指标在 AF50/60/70。
用法：python3 sweep.py <worker> <workers>  （各 worker 取 k % workers == worker 的组）。——Hark（刘线）"""
import json, sys, copy, itertools, os
import run
base = json.load(open('config.json'))
GRID = list(itertools.product([0.02, 0.1], [0.2, 0.4, 0.6], [800.0, 1500.0, 2500.0, 4000.0]))
if __name__ == '__main__':
    w, nw = int(sys.argv[1]), int(sys.argv[2])
    for k, (pc, hf, ms) in enumerate(GRID):
        if k % nw != w: continue
        fn = f'sweep/g{k:02d}.json'
        if os.path.exists(fn): continue
        if ms in (800.0, 4000.0) and k != 0: continue   # 中途收窄：800 使认识层<105（g00 已见）；2500 已使潜在度尾<3×（g02），4000 推断更甚，只跑 1500/2500
        cfg = copy.deepcopy(base); cfg.update(p_cross_faith=pc, homophily_faith=hf, market_strength=ms)
        lf = open(fn + '.log', 'w')
        res = run.simulate(cfg, (50, 60, 70), log=lambda *a: print(*a, file=lf, flush=True))
        res['config'] = cfg; res['grid'] = dict(k=k, p_cross_faith=pc, homophily_faith=hf, market_strength=ms)
        json.dump(res, open(fn, 'w'), ensure_ascii=False, indent=1, default=float)
