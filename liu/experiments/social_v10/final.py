"""最佳组：AF40–70 每年全部指标 + 写 ties/lost_neighbors；复跑（light）比逐年哈希；汇总 results.json。
  python3 final.py full    → .cache/best_full.json（并写 ties_AF*.json.gz、lost_neighbors.json.gz）
  python3 final.py rerun   → .cache/best_rerun.json（只出逐年哈希）
  python3 final.py assemble → results.json ——Hark（刘线）"""
import json, sys, collections
import numpy as np
import run, model, data, metrics


def lineage_stats(cfg):
    W = model.World(); S = model.Sim(W, cfg)
    tiers = collections.Counter()
    for u in np.flatnonzero(S.parent >= 0).tolist():
        p = int(S.parent[u]); b = int(W.built[u]); m = W.mem[min(max(b, data.Y0), data.Y1)]; M = m['M']
        if M['坊'][u] >= 0 and M['坊'][u] == M['坊'][p]: tiers['同坊'] += 1
        elif M['街'][u] >= 0 and M['街'][u] == M['街'][p]: tiers['同街（含邻坊）'] += 1
        elif W.Hs['d'][u] == W.Hs['d'][p]: tiers['同区'] += 1
        else: tiers['其他（邻坊跨区等）'] += 1
    d = np.hypot(*(W.xy[S.parent[S.parent >= 0]] - W.xy[S.parent >= 0]).T)
    Mr = S.mar; cross = 0; cross_eligible = 0; md = []
    for t, u, v in Mr.tolist():
        m = W.mem[min(max(t, data.Y0), data.Y1)]
        md.append(float(np.hypot(*(W.xy[u] - W.xy[v]))))
        if t >= 52:
            cross_eligible += 1; cross += int(m['faith'][u] != m['faith'][v])
    alive = np.array([W.dest[u] > data.Y0 and W.built[u] <= data.Y1 for u in range(W.N)])
    return dict(houses_alive_40_70=int(alive.sum()), with_parent=int((S.parent >= 0).sum()), parent_rule_tier_check=dict(tiers),
                parent_child_distance_median=round(float(np.median(d)), 1), kin_pairs_by_dist={model.KIN_LABEL[int(k)]: int(c) for k, c in zip(*np.unique(S.kin[:, 2], return_counts=True))},
                marriages_total=int(len(Mr)), marriages_AF52plus=cross_eligible, cross_faith_marriages_AF52plus=cross,
                marriage_distance_median=round(float(np.median(md)), 1), markets=[dict(id=m[0], type=m[1], source=m[2], built=m[5]) for m in W.markets])


if __name__ == '__main__':
    cfg = json.load(open('config_best.json'))
    if sys.argv[1] == 'full':
        lf = open('.cache/best_full.log', 'w')
        res = run.simulate(cfg, tuple(range(40, 71)), ties=True, log=lambda *a: print(*a, file=lf, flush=True))
        json.dump(res, open('.cache/best_full.json', 'w'), ensure_ascii=False, default=float)
    elif sys.argv[1] == 'rerun':
        lf = open('.cache/best_rerun.log', 'w')
        res = run.simulate(cfg, (), light=True, log=lambda *a: print(*a, file=lf, flush=True))
        json.dump(res, open('.cache/best_rerun.json', 'w'), ensure_ascii=False, default=float)
    else:
        A = json.load(open('.cache/best_full.json')); B = json.load(open('.cache/best_rerun.json'))
        sw = json.load(open('sweep_summary.json'))
        det = {y: dict(run1=A['years'][y]['digest'], run2=B['years'][y]['digest'], identical=A['years'][y]['digest'] == B['years'][y]['digest']) for y in A['years']}
        yrs = {}
        for y, r in A['years'].items():
            yrs[y] = {k: v for k, v in r.items()}
        out = dict(_doc='v10 结果：targets=靶区与出处；sweep=扫描汇总；best_config；years=AF40–70 逐年指标（metrics/hits/存活率/拆户失去邻居/每步耗时/哈希）；determinism=同种子两次运行逐年哈希；lineage=亲属与婚姻统计。——Hark（刘线）',
                   targets={k: list(v) for k, v in metrics.TARGETS.items()}, sweep=sw, best_config=cfg, lineage=lineage_stats(cfg),
                   determinism=dict(all_identical=all(v['identical'] for v in det.values()), years=det), years=yrs,
                   seconds=dict(full_run=A['seconds'], rerun_light=B['seconds']))
        json.dump(out, open('results.json', 'w'), ensure_ascii=False, indent=1, default=float)
        print('det', out['determinism']['all_identical'], json.dumps(out['lineage'], ensure_ascii=False)[:1500])
