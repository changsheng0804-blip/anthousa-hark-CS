"""v11 小扫描（18 组 = 6 次模拟 × k 三档）：
  (市场强度, 认识层生成强度 c) ∈ {(1500,2.0) v10 最佳, (800,2.0), (1500,1.0)} × 官员-辖民容量 {40,80} × 职位户上限倍数 k {1,1.5,2}。
"认识层生成强度"取 v10 焦点生成系数 c（p=c·s^-a，场所焦点里的大量弱/认识关系由它产生）。
k 只作用于输出截断，一次模拟同时评三档。其余沿用 v10 最佳组。
用法：python3 sweep11.py <worker> <workers>   ——Hark（刘线）"""
import json, sys, copy, itertools, os
import run11
KS = (1.0, 1.5, 2.0)
SIMS = [(ms, c, cap) for (ms, c) in [(1500.0, 2.0), (800.0, 2.0), (1500.0, 1.0)] for cap in (40, 80)]
if __name__ == '__main__':
    base = json.load(open('config.json'))
    w, nw = int(sys.argv[1]), int(sys.argv[2])
    for j, (ms, c, cap) in enumerate(SIMS):
        if j % nw != w: continue
        fn = f'sweep/s{j}.json'
        if os.path.exists(fn): continue
        cfg = copy.deepcopy(base); cfg.update(market_strength=ms, c=c, office_hub_capacity=cap)
        lf = open(fn + '.log', 'w')
        res = run11.simulate(cfg, KS, (50, 60, 70), log=lambda *a: print(*a, file=lf, flush=True))
        res['config'] = cfg; res['sim'] = dict(j=j, market_strength=ms, c=c, office_hub_capacity=cap)
        json.dump(res, open(fn, 'w'), ensure_ascii=False, default=float)
