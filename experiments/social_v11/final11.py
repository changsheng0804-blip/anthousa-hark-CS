"""最佳组 AF40–70 每年全部指标 + 只写 ties_AF70.json.gz；汇总 results.json。
  python3 final11.py full      → .cache/best_full.json（并写 ties_AF70.json.gz）
  python3 final11.py assemble  → results.json ——Hark（刘线）"""
import json, os, sys
import core, run11

if __name__ == '__main__':
    os.makedirs('.cache', exist_ok=True)
    cfg = json.load(open('config_best.json')); k = cfg['office_cap_mult']
    if sys.argv[1] == 'full':
        lf = open('.cache/best_full.log', 'w')
        res = run11.simulate(cfg, (k,), tuple(range(40, 71)), ties=k, log=lambda *a: print(*a, file=lf, flush=True))
        json.dump(res, open('.cache/best_full.json', 'w'), ensure_ascii=False, default=float)
        print('done', file=lf, flush=True)
    else:
        A = json.load(open('.cache/best_full.json')); sw = json.load(open('sweep_summary.json'))
        yrs = A[str(k)]['years']
        out = dict(_doc='v11 结果：conversion=人→户换算；targets=靶区与出处（v10★版本，只改 Dunbar 层靶）；sweep=18 组扫描汇总（AF50/60/70 heavy）；'
                        'best_config；years=最佳组 AF40–70 逐年全部指标/命中/存活率/哈希。ties 只存 AF70（ties_AF70.json.gz）。——Hark（刘线）',
                   conversion=dict(person_layers=[5, 15, 50, 150], persons_per_household=round(core.PERSONS_PER_HH, 3),
                                   exact=[round(x / core.PERSONS_PER_HH, 2) for x in (5, 15, 50, 150)], household_layers=core.LAYERS,
                                   source='Hill & Dunbar 2003（150 人≈68 户）', office_cap='68×k，k 为假设参数'),
                   targets={a: list(b) for a, b in core.TARGETS.items()}, sweep=sw, best_config=cfg, years=yrs,
                   seconds=A['_seconds'])
        json.dump(out, open('results.json', 'w'), ensure_ascii=False, indent=1, default=float)
        print('ok', len(yrs))
