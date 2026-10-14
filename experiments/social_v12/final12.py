"""最佳组 AF40–70 每年全部指标 + 只写 ties_AF70.json.gz；汇总 results.json。
  python3 final12.py full      → .cache/best_full.json（并写 ties_AF70.json.gz）
  python3 final12.py assemble  → results.json ——Hark（刘线）"""
import json, os, sys
import core12, run12

if __name__ == '__main__':
    os.makedirs('.cache', exist_ok=True)
    cfg = json.load(open('config_best.json')); k = str(cfg['office_cap_mult'])
    if sys.argv[1] == 'full':
        lf = open('.cache/best_full.log', 'w')
        res = run12.simulate(cfg, tuple(range(40, 71)), ties=True, log=lambda *a: print(*a, file=lf, flush=True))
        json.dump(res, open('.cache/best_full.json', 'w'), ensure_ascii=False, default=float)
        print('done', file=lf, flush=True)
    else:
        A = json.load(open('.cache/best_full.json')); sw = json.load(open('sweep_summary.json'))
        v11 = json.load(open('../social_v11/results.json'))
        out = dict(_doc='v12 结果：targets=靶区（同 v11，正式靶不改）；alt_dunbar3=未取整最内层靶 1.6–3.0（仅说明）；sweep=12 组扫描汇总（AF50/60/70 heavy）；'
                        'best_config；group_stats=最佳组逐年常客群规模；years=最佳组 AF40–70 逐年全部指标/命中/存活率/哈希；v11_best_AF70=对比用。ties 只存 AF70。——Hark（刘线）',
                   targets={a: list(b) for a, b in core12.core11.TARGETS.items()}, alt_dunbar3=list(core12.ALT_DUNBAR3), sweep=sw, best_config=cfg,
                   group_stats=A['group_stats'], years=A[k]['years'], seconds=A['_seconds'],
                   v11_best_AF70=dict(metrics=v11['years']['70']['metrics'], survival=v11['years']['70'].get('survival'), diag_clustering=v11['years']['70'].get('diag_clustering')))
        json.dump(out, open('results.json', 'w'), ensure_ascii=False, indent=1, default=float)
        print('ok', len(out['years']))
