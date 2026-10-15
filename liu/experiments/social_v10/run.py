"""v10 运行器。
  python3 run.py sim <配置.json> <输出.json> [heavy 年份逗号] [--ties] [--light]
AF40 初始化，AF41–70 逐年增量；每年记录 v9 指标子集 + Dunbar + 存活率 + 闭合占比 + 拆户"失去邻居"；heavy 年份算全部指标。
--ties：写 ties_AF{40,50,60,70}.json.gz 与 lost_neighbors.json.gz。--light：只出逐年摘要哈希（确定性复跑用）。——Hark（刘线）"""
import collections, gzip, hashlib, json, sys, time
import numpy as np
import model, metrics, data

LN = ['强', '中', '弱', '认识']


def digest(uk, tier, s):
    h = hashlib.sha256()
    h.update(uk.tobytes()); h.update(tier.astype(np.int8).tobytes()); h.update(np.round(s, 4).tobytes())
    return h.hexdigest()[:16]


def simulate(cfg, heavy_years=(50, 60, 70), ties=False, light=False, log=print):
    t0 = time.time()
    W = model.World(); S = model.Sim(W, cfg)
    log('init', round(time.time() - t0, 1), 'kin', len(S.kin), 'mar', len(S.mar))
    N = W.N
    guild = None
    out = dict(years={}, lineage=dict(households_with_parent=int((S.parent >= 0).sum()), kin_pairs=int(len(S.kin)),
                                       kin_by_dist={int(k): int(v) for k, v in zip(*np.unique(S.kin[:, 2], return_counts=True))},
                                       marriages=int(len(S.mar))))
    R, m = None, None; prevE = None; lost_rows = []
    for Y in range(data.Y0, data.Y1 + 1):
        ts = time.time()
        pm = m
        R, m = S.step(Y, R, pm)
        uk, s, tier, inv, keep = S.output(R, Y)
        rec = dict(step_sec=round(time.time() - ts, 2), digest=digest(uk, tier, s), records=int(len(R['u'])))
        st = m['stand']
        if prevE is not None:
            pu, pt = prevE
            both = st[pu // N] & st[pu % N]
            still = np.isin(pu, uk)
            rec['survival'] = float(still[both].mean())
            rec['survival_by_tier'] = {LN[k]: float(still[both & (pt == k)].mean()) for k in range(4) if (both & (pt == k)).any()}
            rec['survival_incl_demolished'] = float(still.mean())
            gone = pm['stand'] & ~st
            touch = gone[pu // N] | gone[pu % N]
            other = np.where(gone[pu // N], pu % N, pu // N)[touch]
            rec['lost'] = dict(demolished=int(gone.sum()), ties_lost=int(touch.sum()), households_losing=int(len(np.unique(other[st[other]]))),
                               by_tier={LN[k]: int((touch & (pt == k)).sum()) for k in range(4)})
            if ties:
                dem = np.where(gone[pu // N], pu // N, pu % N)[touch]
                for a, b, k in zip(dem.tolist(), other.tolist(), pt[touch].tolist()):
                    lost_rows.append([Y, W.ids[a], W.ids[b], LN[k]])
            newh = st & ~pm['stand']
            rec['new_households'] = int(newh.sum())
        prevE = (uk, tier)
        if not light:
            styp = collections.Counter()
            tt = R['typ'][keep[inv]]
            for t, c in zip(*np.unique(tt, return_counts=True)):
                name = model.TYPES[t]; name = '职位辖民' if name.startswith('职位辖民') else name
                styp[name] += int(c)
            faith = m['faith']; g = m['M']['行会']
            is_off = np.zeros(N, bool)
            for h in W.D['holders'][Y].values(): is_off[W.pos[h]] = True
            mt = metrics.compute(N, st, uk, tier, styp, faith, g, is_off, S.latent[0], s, seed=cfg['seed'], heavy=Y in heavy_years)
            # 仅亲属/仅婚姻/仅市场的边占比（新焦点贡献）
            rec['metrics'] = mt; rec['hits'] = metrics.hits(mt)
        rec['sec'] = round(time.time() - ts, 2)
        out['years'][Y] = rec
        if ties and Y in (40, 50, 60, 70):
            lab = model.sources_of(W, R, uk, inv, keep, None)
            edges = [[W.ids[a // N], W.ids[a % N], LN[k], round(float(w), 3), lab[j]] for j, (a, k, w) in enumerate(zip(uk.tolist(), tier.tolist(), s.tolist()))]
            doc = dict(year=Y, _doc='户-户社会关系（v10：亲属/婚姻/市场 + 场所焦点 + 职位 + 三元闭合，AF40 起逐年连续）。edges=[户A,户B,层级(强/中/弱/认识),强度,来源列表]；来源「类型:焦点」（亲属:父子/兄弟/祖孙/叔侄；婚姻:AF成婚年；市场:节点 id；三元闭合:经由户）。参数见 config。——Hark（刘线）',
                       config=cfg, n_households=int(st.sum()), edges=edges)
            with gzip.GzipFile(f'ties_AF{Y}.json.gz', 'wb', mtime=0) as f:
                f.write(json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode())
        mm = rec.get('metrics', {})
        log(Y, 'n', int(st.sum()), 'E', len(uk), 'cum', mm.get('median_cum_layer'), 'surv', round(rec.get('survival', 1), 3), 'cl', mm.get('clustering'),
            'L', mm.get('avg_path'), 'Q', mm.get('modularity'), 'af', mm.get('assort_faith'), 'clos', round(mm.get('closure_share', 0), 3), 'sec', rec['sec'])
    if ties:
        with gzip.GzipFile('lost_neighbors.json.gz', 'wb', mtime=0) as f:
            f.write(json.dumps(dict(_doc='拆户导致的关系移除：[年, 被拆户, 失去邻居的户, 上一年层级]。——Hark（刘线）', rows=lost_rows), ensure_ascii=False, separators=(',', ':')).encode())
    out['seconds'] = round(time.time() - t0, 1)
    return out


if __name__ == '__main__':
    cfgf, outf = sys.argv[2], sys.argv[3]
    heavy = tuple(int(x) for x in sys.argv[4].split(',')) if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else (50, 60, 70)
    cfg = json.load(open(cfgf))
    lf = open(outf + '.log', 'w')
    def log(*a):
        print(*a, file=lf, flush=True)
    res = simulate(cfg, heavy, ties='--ties' in sys.argv, light='--light' in sys.argv, log=log)
    res['config'] = cfg
    json.dump(res, open(outf, 'w'), ensure_ascii=False, indent=1, default=float)
    log('done')
