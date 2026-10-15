"""v11 运行器：一次 v10 模拟（AF40 初始化，AF41–70 增量），每年对每个职位上限倍数 k 各做一次按户分层截断并算指标。
k 只作用于输出截断，不改模拟状态（v10 的三元闭合等都在截断前的全部记录上运行），所以同一模拟可同时评 k=1/1.5/2。
  python3 run11.py <配置.json> <输出.json> <k 逗号> <heavy 年份逗号|all> [--ties]
——Hark（刘线）"""
import collections, gzip, hashlib, json, sys, time
import numpy as np
import core
model, data = core.model10, core.data10
LN = ['强', '中', '弱', '认识']


def digest(uk, tier, s):
    h = hashlib.sha256(); h.update(uk.tobytes()); h.update(tier.astype(np.int8).tobytes()); h.update(np.round(s, 4).tobytes())
    return h.hexdigest()[:16]


def columnar(edges):
    """行式 [a,b,层,强度,[来源…]] → 列式（gzip 后约小 20%）；单来源存整数，多来源存列表。"""
    return dict(a=[e[0] for e in edges], b=[e[1] for e in edges], layer=[e[2] for e in edges], w=[e[3] for e in edges],
                src=[e[4][0] if len(e[4]) == 1 else e[4] for e in edges])


def write_ties(W, R, Y, uk_all, inv, keep, tier, s, cfg, k, fn):
    """紧凑列式：households 户 id 列表 + sources 来源标签字典；edges 为等长列 a/b（户序号）、layer（0强..3认识）、w（强度）、src（来源序号或序号列表）。"""
    N = W.N
    lab = model.sources_of(W, R, None, inv, keep, None)
    ukk = uk_all[keep]
    hs = np.unique(np.concatenate([ukk // N, ukk % N]))
    hpos = {int(h): i for i, h in enumerate(hs.tolist())}
    L = {}; edges = []
    for j, (a, t, w) in enumerate(zip(ukk.tolist(), tier.tolist(), s.tolist())):
        src = [L.setdefault(x, len(L)) for x in lab[j]]
        edges.append([hpos[a // N], hpos[a % N], t, round(float(w), 2), src])
    doc = dict(year=Y, _doc=DOC, office_cap_mult=k, config=cfg, layers=LN, households=[W.ids[h] for h in hs.tolist()],
               sources=list(L), edges=columnar(edges))
    with gzip.GzipFile(fn, 'wb', mtime=0, compresslevel=9) as f:
        f.write(json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode())


DOC = ('户-户社会关系 v11（v10 模拟 + 按户 Dunbar 分层 3/7/23/68，普通户上限 68、职位户上限 68×k）。'
       'households=户 id 列表；layers=层名；sources=来源标签（类型:焦点）；edges 为列式：第 i 条边 = households[a[i]]–households[b[i]]，'
       '层 layers[layer[i]]，强度 w[i]，来源 src[i]（sources 序号；多来源时为序号列表）。——Hark（刘线）')


def diag_clustering(N, st, uk_all, uk, tier, R, inv, keep):
    """诊断（只在最佳组 AF70）：截断前潜在网、输出网逐层累计子图的平均局部聚类；输出边按来源类型的占比。"""
    import igraph as ig
    S = np.flatnonzero(st); pos = np.full(N, -1); pos[S] = np.arange(len(S))
    def cl(e):
        G = ig.Graph(n=len(S), edges=np.stack([pos[e // N], pos[e % N]], 1).tolist())
        return round(float(G.transitivity_avglocal_undirected(mode='zero')), 4), round(2 * len(e) / len(S), 1)
    out = {'latent(截断前)': cl(uk_all)}
    for j, nm in enumerate(['强', '强+中', '强+中+弱', '全部 4 层']):
        out[nm] = cl(uk[tier <= j])
    # 每条输出边的"主来源"类型（记录中权重最大者不易取，这里按是否含该类型计）
    typ_keep = R['typ'][keep[inv]]
    cnt = collections.Counter(model.TYPES[t].split(':')[0] for t in typ_keep.tolist())
    tot = sum(cnt.values())
    return dict(clustering_and_mean_degree=out, source_record_share={a: round(c / tot, 4) for a, c in cnt.most_common()})


def simulate(cfg, ks=(1.0,), heavy_years=(50, 60, 70), ties=None, log=print):
    t0 = time.time()
    W = model.World(); S = model.Sim(W, cfg)
    log('init', round(time.time() - t0, 1), 'kin', len(S.kin), 'mar', len(S.mar))
    N = W.N
    out = {str(k): dict(years={}) for k in ks}
    R, m = None, None; prev = {k: None for k in ks}
    for Y in range(data.Y0, data.Y1 + 1):
        ts = time.time(); pm = m
        R, m = S.step(Y, R, pm)
        uk_all, s_all, inv = model.union(W, cfg, R, Y)
        st = m['stand']
        is_off = np.zeros(N, bool)
        for h in W.D['holders'][Y].values(): is_off[W.pos[h]] = True
        tstep = round(time.time() - ts, 2)
        for k in ks:
            tk = time.time()
            tier_all, keep = core.tiers_k(W, uk_all, s_all, is_off, k)
            uk, s, tier = uk_all[keep], s_all[keep], tier_all[keep]
            rec = dict(digest=digest(uk, tier, s), records=int(len(R['u'])), step_sec=tstep)
            if prev[k] is not None:
                pu, pt = prev[k]
                both = st[pu // N] & st[pu % N]
                still = np.isin(pu, uk)
                rec['survival'] = float(still[both].mean())
                rec['survival_by_tier'] = {LN[j]: float(still[both & (pt == j)].mean()) for j in range(4) if (both & (pt == j)).any()}
            prev[k] = (uk, tier)
            styp = collections.Counter()
            tt = R['typ'][keep[inv]]
            for t, c in zip(*np.unique(tt, return_counts=True)):
                name = model.TYPES[t]; name = '职位辖民' if name.startswith('职位辖民') else name
                styp[name] += int(c)
            mt = core.compute(N, st, uk, tier, styp, m['faith'], m['M']['行会'], is_off, uk_all, s, cfg['seed'], Y in heavy_years)
            rec['metrics'] = mt; rec['hits'] = core.hits(mt); rec['sec'] = round(time.time() - tk + tstep, 2)
            out[str(k)]['years'][Y] = rec
            if ties and Y == 70 and k == ties:
                write_ties(W, R, Y, uk_all, inv, keep, tier, s, cfg, k, f'ties_AF{Y}.json.gz')
                rec['diag_clustering'] = diag_clustering(N, st, uk_all, uk, tier, R, inv, keep)
            log(Y, 'k', k, 'n', int(st.sum()), 'E', len(uk), 'cum', mt.get('median_cum_layer'), 'surv', round(rec.get('survival', 1), 3),
                'cl', mt.get('clustering'), 'L', mt.get('avg_path'), 'af', mt.get('assort_faith'), 'osr', round(mt['office_strength_ratio'], 3),
                'obr', mt.get('office_betw_ratio'), 'clos', round(mt.get('closure_share', 0), 3), 'sec', rec['sec'])
    out['_seconds'] = round(time.time() - t0, 1)
    return out


if __name__ == '__main__':
    cfg = json.load(open(sys.argv[1]))
    ks = tuple(float(x) for x in sys.argv[3].split(','))
    hy = tuple(range(40, 71)) if sys.argv[4] == 'all' else tuple(int(x) for x in sys.argv[4].split(','))
    lf = open(sys.argv[2] + '.log', 'w')
    res = simulate(cfg, ks, hy, ties=ks[0] if '--ties' in sys.argv else None, log=lambda *a: print(*a, file=lf, flush=True))
    res['config'] = cfg
    json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1, default=float)
    print('done', file=lf, flush=True)
