"""v12 运行器：安装常客群补丁后调用 ../social_v11/run11.simulate（AF40 初始化，AF41–70 增量，每年按户分层 3/7/23/68、职位户 68×k）。
  python3 run12.py <配置.json> <输出.json> [--ties]   ——Hark（刘线）"""
import json, sys, time
import core12


def simulate(cfg, heavy_years=(50, 60, 70), ties=False, log=print):
    core12.install(cfg)
    k = cfg['office_cap_mult']
    res = core12.run11.simulate(cfg, (k,), heavy_years, ties=k if ties else None, log=log)
    res["group_stats"] = core12.LAST_STATS
    yrs = res[str(k)]['years']
    for Y, rec in yrs.items():
        mt = rec['metrics']
        mt['market_share'] = core12.market_share(mt)
        lo, hi = core12.ALT_DUNBAR3
        rec['hit_dunbar3_unrounded'] = lo <= mt['dunbar_cum_3'] <= hi
    return res


if __name__ == '__main__':
    cfg = json.load(open(sys.argv[1]))
    lf = open(sys.argv[2] + '.log', 'w')
    res = simulate(cfg, ties='--ties' in sys.argv, log=lambda *a: print(*a, file=lf, flush=True))
    res['config'] = cfg
    json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1, default=float)
    print('done', file=lf, flush=True)
