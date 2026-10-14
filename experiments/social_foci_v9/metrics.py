"""网络指标与校准靶区（文献出处见 REPORT.md）。——Hark（刘线）"""
import numpy as np, networkx as nx, collections

TARGETS = {
    # 名称: (下限, 上限, 出处简写)
    'median_degree': (10, 70, 'Banerjee+2013 Science 村庄户级并联网均度≈15–20；Hill&Dunbar 2003 平均联系 68 户'),
    'cap_share': (0.0, 0.05, 'Dunbar 1993/Zhou+2005：150 为上限，触顶户应为少数'),
    'clustering': (0.1, 0.5, 'Newman 2003 SIAM Rev.；Watts&Strogatz 1998（社会网 0.1–0.5）'),
    'avg_path': (4.0, 8.0, 'Travers&Milgram 1969 ≈5.2；Backstrom+2012 4.74；任务给定 4–8'),
    'degree_skew': (0.0, None, '右偏：Amaral+2000 PNAS（社会网为截断/宽尺度分布）'),
    'max_over_median': (3.0, None, '右偏尾：最大度≥3×中位'),
    'modularity': (0.3, None, 'Newman 2006 PNAS；Clauset+2004（>0.3 有明显社区）'),
    'assort_faith': (0.0, None, 'McPherson+2001 Annu.Rev.Sociol. 宗教同质性'),
    'assort_guild': (0.0, None, 'McPherson+2001 职业同质性'),
    'office_degree_ratio': (1.5, None, 'Padgett&Ansell 1993 等：职位/精英户度高'),
    'office_betw_ratio': (2.0, None, 'Freeman 1977 中介中心性集中于职位户'),
}

def to_graph(N, ties):
    G = nx.Graph(); G.add_nodes_from(range(N))
    G.add_edges_from(ties.keys())
    return G

def compute(C, ties, seed=0, n_src=60, betw_k=48):
    N = C['N']; G = to_graph(N, ties)
    deg = np.array([d for _, d in G.degree()])
    m = {}
    m['n'] = N; m['edges'] = G.number_of_edges()
    m['median_degree'] = float(np.median(deg)); m['mean_degree'] = float(deg.mean())
    m['cap_share'] = float((deg >= 150).mean())
    m['isolates'] = int((deg == 0).sum())
    sd = deg.std()
    m['degree_skew'] = float(((deg - deg.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    m['max_over_median'] = float(deg.max() / max(1, np.median(deg)))
    m['clustering'] = float(nx.average_clustering(G))
    comp = max(nx.connected_components(G), key=len)
    m['giant_share'] = len(comp) / N
    H = G.subgraph(comp)
    import scipy.sparse as sp
    from scipy.sparse.csgraph import shortest_path
    idx = sorted(comp); pos = {u: k for k, u in enumerate(idx)}
    rows = [pos[u] for u, v in H.edges()] ; cols = [pos[v] for u, v in H.edges()]
    A = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(idx), len(idx))).tocsr()
    rng = np.random.default_rng(seed)
    src = rng.choice(len(idx), min(n_src, len(idx)), replace=False)
    D = shortest_path(A, directed=False, unweighted=True, indices=src)
    D = D[np.isfinite(D) & (D > 0)]
    m['avg_path'] = float(D.mean()); m['diameter_est'] = float(D.max())
    comms = nx.community.louvain_communities(G, seed=seed)
    m['modularity'] = float(nx.community.modularity(G, comms)); m['n_communities'] = len(comms)
    F = C['faith']
    if len(set(F)) > 1:
        nx.set_node_attributes(G, {u: F[u] for u in range(N)}, 'faith')
        m['assort_faith'] = float(nx.attribute_assortativity_coefficient(G, 'faith'))
    else:
        m['assort_faith'] = None
    gm = [u for u in range(N) if C['guild'][u]]
    S = G.subgraph(gm).copy()
    nx.set_node_attributes(S, {u: C['guild'][u] for u in gm}, 'g')
    m['assort_guild'] = float(nx.attribute_assortativity_coefficient(S, 'g')) if S.number_of_edges() else None
    off = C['is_office']
    m['office_degree_ratio'] = float(deg[off].mean() / max(1e-9, deg[~off].mean()))
    b = nx.betweenness_centrality(G, k=min(betw_k, N), seed=seed)
    bv = np.array([b[u] for u in range(N)])
    m['office_betw_ratio'] = float(bv[off].mean() / max(1e-12, bv[~off].mean()))
    top = np.argsort(-bv)[: max(1, N // 100)]
    m['office_share_top1pct_betw'] = float(off[top].mean()); m['office_base_rate'] = float(off.mean())
    # Dunbar 层：每户各层关系数中位
    lay = collections.defaultdict(lambda: [0, 0, 0, 0])
    for (u, v), t in ties.items():
        lay[u][t['tier']] += 1; lay[v][t['tier']] += 1
    arr = np.array([lay[u] for u in range(N)])
    m['median_layer_counts'] = [float(x) for x in np.median(arr, 0)]
    m['median_cum_layer'] = [float(x) for x in np.median(np.cumsum(arr, 1), 0)]
    src_ct = collections.Counter()
    for t in ties.values():
        for s in t['src']: src_ct[s.split(':')[0]] += 1
    m['tie_sources'] = dict(src_ct)
    return m

def hits(m):
    out = {}
    for k, (lo, hi, _) in TARGETS.items():
        v = m.get(k)
        if v is None: out[k] = None; continue
        out[k] = (lo is None or v >= lo) and (hi is None or v <= hi)
    return out

def score(m):
    """落靶数；并给连续距离（越小越好）用于并列排序。"""
    h = hits(m); n = sum(1 for x in h.values() if x)
    dist = 0.0
    for k, (lo, hi, _) in TARGETS.items():
        v = m.get(k)
        if v is None: continue
        span = abs(hi - lo) if (lo is not None and hi is not None) else max(1.0, abs(lo or 1))
        if lo is not None and v < lo: dist += (lo - v) / span
        if hi is not None and v > hi: dist += (v - hi) / span
    return n, dist
