"""v10 指标与靶区（igraph 计算；v9 那套 + Dunbar 各层 + 存活率 + 闭合占比）。出处与改动理由见 REPORT.md。——Hark（刘线）"""
import collections
import numpy as np
import igraph as ig

TARGETS = {
    # 名称: (下限, 上限, 出处/理由)
    'dunbar_cum_5': (3.5, 6.5, 'Dunbar 1993; Zhou+2005：支持圈≈5（任务给定"5 附近"，±30%）'),
    'dunbar_cum_15': (10.5, 19.5, 'Zhou+2005 同情圈≈15（±30%）'),
    'dunbar_cum_50': (35.0, 65.0, 'Zhou+2005 ≈50（±30%）'),
    'dunbar_cum_150': (105.0, 150.0, 'Dunbar 1993 / Hill&Dunbar 2003 ≈150（下 30%，上限即 150 截断）'),
    'clustering': (0.1, 0.5, 'Watts&Strogatz 1998; Newman 2003（社会网 0.1–0.5），同 v9'),
    'avg_path': (2.5, 6.0, '改：v9 的 4–8 来自全国尺度；1.7 万户×度≈130 的城内网，随机网基线 lnN/lnk≈2.0，要求高于基线以体现空间局部性（模型假设）'),
    'latent_degree_skew': (0.0, None, '改：150 截断后输出图的度被压平（≤150、≤50 层亦被截），改在截断前的潜在关系网上检验右偏（Amaral+2000）'),
    'latent_max_over_median': (3.0, None, '同上：潜在关系网最大度 ≥3×中位'),
    'modularity': (0.3, None, 'Newman 2006; Clauset+2004，同 v9'),
    'assort_faith': (0.5, 0.85, '改为区间：下限=宗教同质性显著（McPherson+2001），上限 0.85 = 不得接近完全隔离；依据见 REPORT 二栏'),
    'assort_guild': (0.0, None, 'McPherson+2001 职业同质性，同 v9'),
    'office_strength_ratio': (1.5, None, '改：150 截断后度比被压到 ≤1.2，改比输出关系强度和（职位户/普通户；Padgett&Ansell 1993）'),
    'office_betw_ratio': (2.0, None, 'Freeman 1977，同 v9'),
    'closure_share': (0.0, 0.4, '任务给定：三元闭合来源占比 <40%'),
}


def compute(N, stand, uk, tier, srcs_typ_counts, faith, guild, is_office, latent_uk, strength, seed=0, n_src=60, betw_src=48, heavy=True):
    S = np.flatnonzero(stand); pos = np.full(N, -1); pos[S] = np.arange(len(S))
    u = pos[uk // N]; v = pos[uk % N]
    n = len(S)
    m = {'n': int(n), 'edges': int(len(uk))}
    deg = np.bincount(u, minlength=n) + np.bincount(v, minlength=n)
    m['median_degree'] = float(np.median(deg)); m['mean_degree'] = float(deg.mean())
    m['cap_share'] = float((deg >= 150).mean()); m['isolates'] = int((deg == 0).sum())
    cnt = np.zeros((n, 4))
    for k in range(4):
        s = tier == k
        cnt[:, k] = np.bincount(u[s], minlength=n) + np.bincount(v[s], minlength=n)
    cum = np.median(np.cumsum(cnt, 1), 0)
    m['median_cum_layer'] = [float(x) for x in cum]
    m['median_layer_counts'] = [float(x) for x in np.median(cnt, 0)]
    for k, L in enumerate((5, 15, 50, 150)): m[f'dunbar_cum_{L}'] = float(cum[k])
    inner = cnt[:, :3].sum(1)
    sd = inner.std()
    m['inner_median_degree'] = float(np.median(inner))
    m['inner_degree_skew'] = float(((inner - inner.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    m['inner_max_over_median'] = float(inner.max() / max(1, np.median(inner)))
    off = is_office[S]
    m['office_inner_degree_ratio'] = float(inner[off].mean() / max(1e-9, inner[~off].mean())) if off.any() else None
    stg = np.bincount(u, strength, minlength=n) + np.bincount(v, strength, minlength=n)
    m['office_strength_ratio'] = float(stg[off].mean() / max(1e-9, stg[~off].mean())) if off.any() else None
    lu = pos[latent_uk // N]; lv = pos[latent_uk % N]
    ld = np.bincount(lu, minlength=n) + np.bincount(lv, minlength=n); lsd = ld.std()
    m['latent_median_degree'] = float(np.median(ld)); m['latent_max_degree'] = int(ld.max())
    m['latent_degree_skew'] = float(((ld - ld.mean()) ** 3).mean() / lsd ** 3) if lsd > 0 else 0.0
    m['latent_max_over_median'] = float(ld.max() / max(1, np.median(ld)))
    m['office_degree_ratio_full'] = float(deg[off].mean() / max(1e-9, deg[~off].mean())) if off.any() else None
    tot = sum(srcs_typ_counts.values())
    m['closure_share'] = srcs_typ_counts.get('三元闭合', 0) / max(1, tot)
    m['source_label_share'] = {k: round(c / tot, 4) for k, c in sorted(srcs_typ_counts.items(), key=lambda x: -x[1])}
    G = ig.Graph(n=n, edges=np.stack([u, v], 1).tolist())
    F = faith[S]
    if len(set(F.tolist())) > 1:
        m['assort_faith'] = float(G.assortativity_nominal(types=F.tolist(), directed=False))
    else:
        m['assort_faith'] = None
    gm = np.flatnonzero(guild[S] >= 0)
    if len(gm) > 1:
        H = G.induced_subgraph(gm.tolist())
        gv = guild[S][gm]; _, gcode = np.unique(gv, return_inverse=True)
        m['assort_guild'] = float(H.assortativity_nominal(types=gcode.tolist(), directed=False)) if H.ecount() else None
    if not heavy:
        return m
    m['clustering'] = float(G.transitivity_avglocal_undirected(mode='zero'))
    comps = G.connected_components(); gc = max(comps, key=len)
    m['giant_share'] = len(gc) / n
    rng = np.random.default_rng(seed)
    src = rng.choice(gc, min(n_src, len(gc)), replace=False).tolist()
    D = np.array(G.distances(source=src), float)
    D = D[np.isfinite(D) & (D > 0)]
    m['avg_path'] = float(D.mean()); m['diameter_est'] = float(D.max())
    cl = G.community_multilevel()
    m['modularity'] = float(cl.modularity); m['n_communities'] = len(cl)
    bs = rng.choice(n, min(betw_src, n), replace=False).tolist()
    b = np.array(G.betweenness(sources=bs, directed=False))
    m['office_betw_ratio'] = float(b[off].mean() / max(1e-12, b[~off].mean())) if off.any() else None
    top = np.argsort(-b)[: max(1, n // 100)]
    m['office_share_top1pct_betw'] = float(off[top].mean()); m['office_base_rate'] = float(off.mean())
    return m


def hits(m):
    out = {}
    for k, (lo, hi, _) in TARGETS.items():
        v = m.get(k)
        if v is None: out[k] = None; continue
        out[k] = (lo is None or v >= lo) and (hi is None or v <= hi)
    return out


def dist(m):
    d = 0.0
    for k, (lo, hi, _) in TARGETS.items():
        v = m.get(k)
        if v is None: continue
        span = abs(hi - lo) if (lo is not None and hi is not None) else max(1.0, abs(lo or 1))
        if lo is not None and v < lo: d += (lo - v) / span
        if hi is not None and v > hi: d += (v - hi) / span
    return d
