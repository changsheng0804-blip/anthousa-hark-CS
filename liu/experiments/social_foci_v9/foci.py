"""v9：从 v8 的场所(foci) 反推户-户社会关系（Feld 1981 焦点理论 + 同质性 + 三元闭合 + 空间衰减 + Dunbar 分层）。
只读 ../gov_frame_v8/graph_AF*.json.gz。——Hark（刘线）"""
import gzip, json, math, zlib, os, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V8 = os.path.join(HERE, '..', 'gov_frame_v8')

def load_v8(year):
    g = json.load(gzip.open(os.path.join(V8, f'graph_AF{year}.json.gz')))
    return g['nodes'], g['edges']

def jxy(jid):
    x, y = jid[2:].split(',')
    return float(x), float(y)

def build_city(year, cfg):
    """返回 households 列表（户+职位户）及其焦点成员表。"""
    nodes, edges = load_v8(year)
    H = [i for i, n in enumerate(nodes) if n[1] in ('户', '职位户')]
    hid = {i: k for k, i in enumerate(H)}
    N = len(H)
    door = [None] * N; ward = [None] * N; guild = [None] * N
    church = [None] * N; well = [None] * N
    office_of = collections.defaultdict(set)   # 官员户下标 -> 直属辖民户
    sup = []                                   # 职位上下级（户-户）
    hub_types = set(cfg['office_hub_types'])
    for s, t, typ, sub, src in edges:
        if s not in hid: continue
        u = hid[s]
        if typ == '共享设施':
            if sub == '门口路口': door[u] = nodes[t][0]
            elif sub == '礼拜': church[u] = nodes[t][0]
            elif sub == '用水': well[u] = nodes[t][0]
        elif typ == '隶属':
            if t in hid:
                if '→' in sub:
                    sup.append((u, hid[t]))
                else:
                    if sub == '坊长': ward[u] = nodes[t][0]
                    if sub == '行会头': guild[u] = nodes[t][0]
                    if sub in hub_types and hid[t] != u: office_of[hid[t]].add(u)
    attrs = [nodes[i][2] for i in H]
    ids = [nodes[i][0] for i in H]
    # 坐标：门口路口；无门者用同街均值，再退到同区均值
    xy = np.full((N, 2), np.nan)
    for u in range(N):
        if door[u]: xy[u] = jxy(door[u])
    for key in ('street', 'd'):
        acc = collections.defaultdict(list)
        for u in range(N):
            if not np.isnan(xy[u, 0]): acc[attrs[u].get(key)].append(xy[u])
        mean = {k: np.mean(v, axis=0) for k, v in acc.items()}
        for u in range(N):
            if np.isnan(xy[u, 0]) and attrs[u].get(key) in mean: xy[u] = mean[attrs[u].get(key)]
    xy[np.isnan(xy)] = np.nanmean(xy)
    cell = cfg['street_seg_cell']
    seg = [f"{attrs[u].get('street')}@{int(xy[u,0]//cell)},{int(xy[u,1]//cell)}" for u in range(N)]
    foci = collections.defaultdict(list)  # (类型, id) -> 成员
    for u in range(N):
        if door[u]: foci[('门口路口', door[u])].append(u)
        foci[('街段', seg[u])].append(u)
        if ward[u]: foci[('坊', ward[u])].append(u)
        if guild[u]: foci[('行会', guild[u])].append(u)
        if church[u]: foci[('教堂会众', church[u])].append(u)
        if well[u]: foci[('井/水池', well[u])].append(u)
    # 官员本人也是其坊/行会焦点成员（若未被包含则加入）
    is_office = np.array([n[1] == '职位户' for n in (nodes[i] for i in H)])
    faith = [a.get('faith') for a in attrs]
    return dict(N=N, ids=ids, attrs=attrs, xy=xy, faith=faith, guild=guild, ward=ward,
                foci=dict(foci), office_of={k: sorted(v) for k, v in office_of.items()},
                sup=sup, is_office=is_office, seg=seg, door=door, church=church, well=well)

def frng(seed, *keys):
    h = zlib.crc32(('|'.join(map(str, (seed,) + keys))).encode())
    return np.random.default_rng(h)

def accept_prob(C, cfg, i, j):
    d = math.hypot(*(C['xy'][i] - C['xy'][j]))
    a = (1.0 + d / cfg['dist_d0']) ** (-cfg['dist_gamma'])
    if C['faith'][i] != C['faith'][j]: a *= (1 - cfg['homophily_faith'])
    gi, gj = C['guild'][i], C['guild'][j]
    if gi and gj and gi != gj: a *= (1 - cfg['homophily_guild'])
    return a

def accept_vec(C, cfg, I, J):
    d = np.hypot(*(C['xy'][I] - C['xy'][J]).T)
    a = (1.0 + d / cfg['dist_d0']) ** (-cfg['dist_gamma'])
    F = C['faith_arr']; G = C['guild_arr']
    a = a * np.where(F[I] != F[J], 1 - cfg['homophily_faith'], 1.0)
    a = a * np.where((G[I] >= 0) & (G[J] >= 0) & (G[I] != G[J]), 1 - cfg['homophily_guild'], 1.0)
    return a

def prep(C):
    fv = {f: k for k, f in enumerate(sorted(set(map(str, C['faith']))))}
    C['faith_arr'] = np.array([fv[str(f)] for f in C['faith']])
    gv = {g: k for k, g in enumerate(sorted(set(g for g in C['guild'] if g)))}
    C['guild_arr'] = np.array([gv[g] if g else -1 for g in C['guild']])
    # 近邻 k 户（以每户为中心的自我焦点）：网格分桶求 kNN
    from collections import defaultdict
    xy = C['xy']; k = C['_cfg']['knn_k']
    jitter = frng(C['_cfg']['seed'], 'jit').normal(0, 0.5, xy.shape)  # 同门口户之间打散，确定性
    P = xy + jitter
    cell = 15.0; B = defaultdict(list)
    for u, (x, y) in enumerate(P): B[(int(x // cell), int(y // cell))].append(u)
    knn = []
    for u, (x, y) in enumerate(P):
        cx, cy = int(x // cell), int(y // cell); r = 1
        while True:
            cand = [v for dx in range(-r, r + 1) for dy in range(-r, r + 1) for v in B.get((cx + dx, cy + dy), []) if v != u]
            if len(cand) >= k or r > 8: break
            r += 1
        cand = np.array(cand)
        dd = np.hypot(*(P[cand] - P[u]).T)
        knn.append(cand[np.argsort(dd, kind='stable')[:k]].tolist())
    C['knn'] = knn
    C['P'] = P
    return C

def gen_focus_pairs(C, cfg, ftype, fid, members, rng):
    """焦点内按 p = c·base·s^-a 生成候选对，再按接受率筛。返回 (i,j) 数组。"""
    s = len(members)
    if s < 2: return np.zeros((0, 2), int)
    p = min(1.0, cfg['c'] * cfg['base'][ftype] * s ** (-cfg['a']))
    M = np.array(members)
    if s <= 80:
        iu, ju = np.triu_indices(s, 1)
        keep = rng.random(len(iu)) < p
        I, J = M[iu[keep]], M[ju[keep]]
    else:
        m = rng.poisson(p * s * (s - 1) / 2)
        a = rng.integers(0, s, m); b = rng.integers(0, s, m)
        ok = a != b
        I, J = M[a[ok]], M[b[ok]]
    if len(I) == 0: return np.zeros((0, 2), int)
    acc = accept_vec(C, cfg, I, J)
    keep = rng.random(len(I)) < acc
    return np.stack([I[keep], J[keep]], 1)

def generate(C, cfg):
    """全城生成。返回 ties: dict[(u,v)] -> {'w':强度, 'src':set(焦点类型/id)}"""
    seed = cfg['seed']
    ties = {}
    def add(u, v, w, src):
        if u == v: return
        if u > v: u, v = v, u
        t = ties.get((u, v))
        if t is None: ties[(u, v)] = t = {'w': 0.0, 'src': []}
        t['w'] += w; t['src'].append(src)
    TW = cfg['tie_weight']
    # 1 场所焦点
    for (ft, fid) in sorted(C['foci']):
        mem = C['foci'][(ft, fid)]
        pr = gen_focus_pairs(C, cfg, ft, fid, mem, frng(seed, ft, fid))
        for u, v in pr.tolist(): add(u, v, TW[ft], f'{ft}:{fid}')
    # 2 近邻 k 户（自我焦点，大小 k+1）
    pk = min(1.0, cfg['c'] * cfg['base']['近邻'] * (cfg['knn_k'] + 1) ** (-cfg['a']))
    for u in range(C['N']):
        r = frng(seed, '近邻', C['ids'][u])
        for v in C['knn'][u]:
            if r.random() < pk * accept_prob_local(C, cfg, u, v): add(u, v, TW['近邻'], f'近邻:{C["ids"][u]}')
    # 3 职位：上下级必连；官员-辖民 hub 概率 = 容量/辖民数 × 接受率
    for u, v in C['sup']: add(u, v, TW['职位上下级'], '职位上下级')
    for o in sorted(C['office_of']):
        subs = C['office_of'][o]
        ph = min(1.0, cfg['office_hub_capacity'] / max(1, len(subs)))
        r = frng(seed, '职位辖民', C['ids'][o])
        S = np.array(subs); O = np.full(len(S), o)
        acc = ph * accept_vec(C, cfg, O, S) ** 0.5
        keep = r.random(len(S)) < acc
        for v in S[keep].tolist(): add(o, v, TW['职位辖民'], f'职位辖民:{C["ids"][o]}')
    # 4 一轮三元闭合（基于闭合前的强/中关系）
    closure(C, cfg, ties, add, range(C['N']))
    # 5 Dunbar 分层与上限
    return dunbar(C, cfg, ties)

def accept_prob_local(C, cfg, u, v):
    # 近邻：空间衰减已由 kNN 体现，只用同质性
    a = 1.0
    if C['faith'][u] != C['faith'][v]: a *= (1 - cfg['homophily_faith'])
    gi, gj = C['guild'][u], C['guild'][v]
    if gi and gj and gi != gj: a *= (1 - cfg['homophily_guild'])
    return a

def adjacency(ties):
    adj = collections.defaultdict(dict)
    for (u, v), t in ties.items():
        adj[u][v] = t['w']; adj[v][u] = t['w']
    return adj

def closure(C, cfg, ties, add, nodes_iter):
    q = cfg['q_closure']
    if q <= 0: return
    adj = adjacency(ties); K = cfg['closure_top_k']; seed = cfg['seed']
    new = []
    for u in nodes_iter:
        nb = sorted(adj.get(u, {}).items(), key=lambda x: (-x[1], x[0]))[:K]
        if len(nb) < 2: continue
        r = frng(seed, '闭合', C['ids'][u])
        vs = [v for v, _ in nb]
        for x in range(len(vs)):
            for y in range(x + 1, len(vs)):
                v, w = vs[x], vs[y]
                if w in adj[v]: continue
                if r.random() < q:
                    new.append((v, w, cfg['closure_weight_factor'] * min(nb[x][1], nb[y][1]), C['ids'][u]))
    for v, w, wt, via in new: add(v, w, wt, f'三元闭合:{via}')

def tiebreak(seed, a, b):
    return (zlib.crc32(f'{seed}|{a}|{b}'.encode()) % 100000) / 1e9

def dunbar(C, cfg, ties):
    L = cfg['dunbar_layers']; seed = cfg['seed']
    adj = collections.defaultdict(list)
    for (u, v), t in ties.items():
        s = t['w'] + tiebreak(seed, u, v)
        adj[u].append((s, v)); adj[v].append((s, u))
    rank = {}
    for u, lst in adj.items():
        lst.sort(key=lambda x: (-x[0], x[1]))
        for r, (_, v) in enumerate(lst): rank[(u, v)] = r
    def layer(r):
        for k, cap in enumerate(L):
            if r < cap: return k
        return None
    out = {}
    for (u, v), t in ties.items():
        lu, lv = layer(rank[(u, v)]), layer(rank[(v, u)])
        if lu is None or lv is None: continue
        out[(u, v)] = dict(w=round(t['w'], 3), tier=max(lu, lv), src=t['src'])
    return out

# ---------- 局部增量：新建一户只在其焦点内生成 ----------
def add_household(C, cfg, ties_raw, new_id, like_u):
    """新户 new_id 落在已有户 like_u 的门口，继承其街/坊/教堂/井/行会/信仰焦点。
    只在这些焦点 + 近邻 k 户 + 直属官员 内生成新户的边，再做以新户为中心的局部闭合与 Dunbar 重排。
    ties_raw: generate_raw 的未分层结果（就地修改）。返回 (新边列表, 受重排影响的户集合)。"""
    seed = cfg['seed']; TW = cfg['tie_weight']
    n = C['N']
    C['N'] = n + 1; C['ids'].append(new_id)
    C['xy'] = np.vstack([C['xy'], C['xy'][like_u]]); C['P'] = np.vstack([C['P'], C['P'][like_u] + frng(seed, 'jit', new_id).normal(0, 0.5, 2)])
    for key in ('faith', 'guild', 'ward', 'door', 'church', 'well', 'seg', 'attrs'):
        C[key].append(C[key][like_u])
    C['faith_arr'] = np.append(C['faith_arr'], C['faith_arr'][like_u]); C['guild_arr'] = np.append(C['guild_arr'], C['guild_arr'][like_u])
    C['is_office'] = np.append(C['is_office'], False)
    new = []
    def add(u, v, w, src):
        if u > v: u, v = v, u
        t = ties_raw.get((u, v))
        if t is None: ties_raw[(u, v)] = t = {'w': 0.0, 'src': []}; new.append((u, v))
        t['w'] += w; t['src'].append(src)
    keys = [('门口路口', C['door'][n]), ('街段', C['seg'][n]), ('坊', C['ward'][n]), ('行会', C['guild'][n]), ('教堂会众', C['church'][n]), ('井/水池', C['well'][n])]
    for ft, fid in keys:
        if not fid: continue
        mem = C['foci'].setdefault((ft, fid), [])
        s = len(mem) + 1
        p = min(1.0, cfg['c'] * cfg['base'][ft] * s ** (-cfg['a']))
        r = frng(seed, ft, fid, new_id)
        M = np.array(mem)
        if len(M):
            acc = p * accept_vec(C, cfg, np.full(len(M), n), M)
            for v in M[r.random(len(M)) < acc].tolist(): add(n, v, TW[ft], f'{ft}:{fid}')
        mem.append(n)
    # 近邻 k 户
    d = np.hypot(*(C['P'][:n] - C['P'][n]).T)
    nb = np.argsort(d, kind='stable')[:cfg['knn_k']]
    pk = min(1.0, cfg['c'] * cfg['base']['近邻'] * (cfg['knn_k'] + 1) ** (-cfg['a']))
    r = frng(seed, '近邻', new_id)
    for v in nb.tolist():
        if r.random() < pk * accept_prob_local(C, cfg, n, v): add(n, v, TW['近邻'], f'近邻:{new_id}')
    # 直属官员（与 like_u 同一批官员）
    r = frng(seed, '职位辖民', new_id)
    for o, subs in C['office_of'].items():
        if like_u in subs:
            ph = min(1.0, cfg['office_hub_capacity'] / (len(subs) + 1))
            if r.random() < ph * accept_vec(C, cfg, np.array([o]), np.array([n]))[0] ** 0.5: add(o, n, TW['职位辖民'], f'职位辖民:{C["ids"][o]}')
    # 局部闭合：只闭合以新户为一端的三角（新户—邻居的强邻居）
    q = cfg['q_closure']
    if q > 0 and new:
        adj = adjacency(ties_raw); K = cfg['closure_top_k']
        mine = sorted(adj[n].items(), key=lambda x: (-x[1], x[0]))[:K]
        r = frng(seed, '闭合', new_id)
        cand = []
        for v, wv in mine:
            for w, ww in sorted(adj[v].items(), key=lambda x: (-x[1], x[0]))[:K]:
                if w != n and w not in adj[n]: cand.append((w, cfg['closure_weight_factor'] * min(wv, ww), C['ids'][v]))
        for w, wt, via in cand:
            if (min(n, w), max(n, w)) not in ties_raw and r.random() < q: add(n, w, wt, f'三元闭合:{via}')
    touched = {n} | {x for e in new for x in e}
    return new, touched

def generate_raw(C, cfg):
    """同 generate 但返回分层前的原始关系（供增量用）。"""
    holder = {}
    orig = dunbar
    g = globals()
    g['dunbar'] = lambda C_, cfg_, ties: holder.setdefault('raw', ties)
    try:
        generate(C, cfg)
    finally:
        g['dunbar'] = orig
    return holder['raw']
