"""v12：市场关系改为"摊位/常客群"结构。
按路径载入 ../social_v11/（core.py、run11.py）与 ../social_v10/（model.py、data.py、metrics.py），不改它们；
只在运行时替换 v10 的两处：每年的市场成员列（市场节点 → 市场下的常客群）与 gen_year（市场分支）。

分群（确定性、跨年稳定）：
  1 市场节点首次出现那一年，按成员到市场的方位分 n_sec 个扇区（n_sec=min(8, round(n/g))），
    扇区内按到市场距离分位切成 round(n_扇区/g) 个环 → 方位扇区 × 距离环 = 住处近邻的格子；格子边界此后固定。
  2 格子内同质性拆分：少数信仰户数 ≥ max(3, g/3) → 单独成群；某行会户数 ≥ max(3, g/2) → 该行会单独成群。
    拆分一旦成立不再撤销（滞回，避免群 id 年年抖动）。
  3 认识层市场关系只在同群内按 p_in 生成（不再用距离衰减，近邻已在分群里）；可选跨群：同市场异群，
    每户期望跨群条数 = x/(1−x) × 群内期望条数（x = 市场关系中跨群的目标占比，假设）。
群成员离开该群（搬走、市场改变、群拆分）→ 原 v10 规则：休眠、按 p_lost 解体。——Hark（刘线）"""
import os, sys, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V11 = os.path.abspath(os.path.join(HERE, '..', 'social_v11'))
V10 = os.path.abspath(os.path.join(HERE, '..', 'social_v10'))
for p in (V10, V11):
    if p not in sys.path: sys.path.insert(0, p)
import run11                       # noqa: E402  ../social_v11/run11.py（再载入 v11 core 与 v10 model/data/metrics）
import core as core11              # noqa: E402  ../social_v11/core.py
model = run11.model; data = run11.data

XT = '市场跨群'
if XT not in model.TYPES:
    model.TYPES.append(XT); model.T[XT] = len(model.TYPES) - 1
    model.GROUP.append(XT)
T = model.T
_ORIG_WORLD = model.World
_ORIG_STILL = model.still_in_focus
CFG = {}   # 当前运行配置（World 构造时需要 g）


def _node(ang, dist, g, force=False):
    """方位扇区 × 距离环：n_sec=min(8, round(n/g))，扇区内按距离分位切 round(n_扇区/g) 环。force 时至少切 2 块。"""
    n = len(ang); n_sec = int(max(1, min(8, round(n / g))))
    if force and n_sec == 1 and n >= 2: n_sec = 2
    a0 = float(np.min(ang)) if n else 0.0; a1 = float(np.max(ang)) + 1e-9 if n else 1.0
    if not force: a0, a1 = 0.0, 1.0 + 1e-9
    sec = np.minimum(((ang - a0) / (a1 - a0) * n_sec).astype(int), n_sec - 1)
    bnds = []
    for s in range(n_sec):
        d = np.sort(dist[sec == s]); nr = int(max(1, round(len(d) / g)))
        bnds.append(np.quantile(d, np.arange(1, nr) / nr) if nr > 1 and len(d) else np.zeros(0))
    return dict(a0=a0, a1=a1, n_sec=n_sec, bnds=bnds, ch={})


def _assign(nd, ang, dist):
    """返回每户的叶格子路径字符串（如 '3-1' 或 '3-1.0-2'）。"""
    sec = np.clip(((ang - nd['a0']) / (nd['a1'] - nd['a0']) * nd['n_sec']).astype(int), 0, nd['n_sec'] - 1)
    ring = np.array([np.searchsorted(nd['bnds'][s], d, side='right') for s, d in zip(sec.tolist(), dist.tolist())], int)
    lab = np.array([f'{a}-{b}' for a, b in zip(sec.tolist(), ring.tolist())], dtype=object)
    for c in list(nd['ch']):
        ic = lab == c
        if ic.any():
            lab[ic] = np.array([c + '.' + x for x in _assign(nd['ch'][c], ang[ic], dist[ic])], dtype=object)
    return lab


def _partition(W, g):
    """把每年 M['市场'] / M['市场2']（市场节点码）改成常客群码；原节点码另存 M['市场跨群'] / M['市场跨群2']。"""
    cells = {}       # 市场名 -> (cx, cy, n_sec, [每扇区环边界数组])
    splits_f = set(); splits_g = set()
    mk_xy = {m[0]: (m[3], m[4]) for m in W.markets}
    stats = {}
    for Y in range(data.Y0, data.Y1 + 1):
        mm = W.mem[Y]; M = mm['M']; S = mm['S']
        faith = mm['faith']; guild = M['行会']
        mk1 = M['市场'].copy(); mk2 = M['市场2'].copy()
        names = W.names['市场']
        new1 = np.full(W.N, -1, np.int32); new2 = np.full(W.N, -1, np.int32)
        X1 = np.full(W.N, -1, np.int32); X2 = np.full(W.N, -1, np.int32)
        sizes = []
        allmk = sorted(set(mk1[S][mk1[S] >= 0].tolist()) | set(mk2[S][mk2[S] >= 0].tolist()))
        for code in allmk:
            name = names[code]
            in1 = S[mk1[S] == code]; in2 = S[mk2[S] == code]
            mem = np.concatenate([in1, in2])
            cx, cy = mk_xy[name]
            dx = W.xy[mem, 0] - cx; dy = W.xy[mem, 1] - cy
            ang = (np.arctan2(dy, dx) + np.pi) / (2 * np.pi)          # [0,1]
            dist = np.hypot(dx, dy)
            if name not in cells:
                cells[name] = _node(ang, dist, g)
            cell = _assign(cells[name], ang, dist)
            # 格子长到 >2g（新建房屋、新市场初年成员少）→ 永久细分该格子（滞回，只分不合）
            for _ in range(4):
                big = [(c, n) for c, n in zip(*np.unique(cell, return_counts=True)) if n > 2 * g]
                if not big: break
                for c, n in big:
                    ic = cell == c; nd = cells[name]; path = c.split('.')
                    for p_ in path[:-1]: nd = nd['ch'][p_]
                    nd['ch'][path[-1]] = _node(ang[ic], dist[ic], g, force=True)
                cell = _assign(cells[name], ang, dist)
            fa = faith[mem]; gu = guild[mem]
            # 同质性拆分（滞回）
            for c in np.unique(cell).tolist():
                ic = cell == c
                for f in (0, 1):
                    k = (name, c, f)
                    if k not in splits_f and (fa[ic] == f).sum() >= max(3, g / 3) and (fa[ic] != f).sum() >= max(3, g / 3):
                        splits_f.add(k)
                for gg, cnt in zip(*np.unique(gu[ic & (gu >= 0)], return_counts=True)):
                    k = (name, c, int(gg))
                    if k not in splits_g and cnt >= max(3, g / 2) and ic.sum() - cnt >= max(3, g / 3):
                        splits_g.add(k)
            keys = []
            for c, f, gg in zip(cell.tolist(), fa.tolist(), gu.tolist()):
                fk = f'信{f}' if ((name, c, 0) in splits_f or (name, c, 1) in splits_f) else '信*'
                gk = f'会{W.names["行会"][gg]}' if gg >= 0 and (name, c, gg) in splits_g else '会*'
                keys.append(f'{name}|格{c}|{fk}|{gk}')
            gcodes = np.array([W.code('市场', k) for k in keys], np.int32)
            xc = W.code(XT, name)
            new1[in1] = gcodes[:len(in1)]; new2[in2] = gcodes[len(in1):]
            X1[in1] = xc; X2[in2] = xc
            sizes += list(collections.Counter(gcodes.tolist()).values())
        M['市场'] = new1; M['市场2'] = new2; M[XT] = X1; M[XT + '2'] = X2
        stats[Y] = dict(n_groups=len(sizes), size_median=float(np.median(sizes)), size_mean=float(np.mean(sizes)),
                        size_p10=float(np.percentile(sizes, 10)), size_p90=float(np.percentile(sizes, 90)), size_max=int(max(sizes)))
    W.group_stats = stats
    global LAST_STATS
    LAST_STATS = stats


class World12(_ORIG_WORLD):
    def __init__(self):
        super().__init__()
        _partition(self, CFG['group_size'])


def still_in_focus(W, m, R):
    ok = _ORIG_STILL(W, m, R)
    s = R['typ'] == T[XT]
    if s.any():
        M = m['M']; u, v, f = R['u'][s], R['v'][s], R['fid'][s]
        ok[s] = ((M[XT][u] == f) | (M[XT + '2'][u] == f)) & ((M[XT][v] == f) | (M[XT + '2'][v] == f))
    return ok


def _members2(m, col1, col2):
    S = m['S']; M = m['M']; c1 = M[col1][S]; c2 = M[col2][S]
    f = np.concatenate([c1[c1 >= 0], c2[c2 >= 0]]); u = np.concatenate([S[c1 >= 0], S[c2 >= 0]])
    o = np.lexsort((u, f)); f, u = f[o], u[o]
    if not len(f): return {}
    cut = np.flatnonzero(np.diff(f)) + 1
    return {int(ff[0]): uu for ff, uu in zip(np.split(f, cut), np.split(u, cut))}


def gen_year(W, cfg, Y, prev_m, m, R, init=False):
    """v10 gen_year 原样，只改市场分支：群内 p_in（无距离衰减）+ 可选跨群 x。"""
    seed = cfg['seed']; TW = cfg['tie_weight']; out = []
    rng_of, make, accept, pw, pb = model.rng_of, model.make, model.accept, model.pairs_within, model.pairs_between
    for typ in model.GROUP:
        if typ == XT: continue
        rng = rng_of(seed, typ, Y)
        if typ == '市场':
            G = _members2(m, '市场', '市场2'); Gp = _members2(prev_m, '市场', '市场2') if prev_m is not None else {}
        else:
            G = model.group_members(m, typ); Gp = model.group_members(prev_m, typ) if prev_m is not None else {}
        delta = cfg['turnover'][typ]
        for fid in sorted(G):
            Mem = G[fid]
            p = cfg['p_in'] if typ == '市场' else model.focus_p(cfg, typ, len(Mem))
            if init:
                I, J = pw(Mem, p, rng)
            else:
                old = Gp.get(fid, np.zeros(0, int)); newc = np.setdiff1d(Mem, old); stay = np.intersect1d(Mem, old)
                I1, J1 = pw(stay, p * delta, rng); I2, J2 = pb(newc, stay, p, rng); I3, J3 = pw(newc, p, rng)
                I, J = np.concatenate([I1, I2, I3]), np.concatenate([J1, J2, J3])
            if len(I) == 0: continue
            if typ == '市场':
                a = accept(W, cfg, m, I, J, dist=False)
            else:
                a = accept(W, cfg, m, I, J, cfg['dist_d0'])
            k = rng.random(len(I)) < a
            I, J = I[k], J[k]
            born = (Y - rng.geometric(delta, len(I)) + 1) if init else Y
            out.append(make(T[typ], I, J, fid, born, TW[typ]))
    # 跨群（同市场异群）
    x = cfg['cross_x']
    if x > 0:
        rng = rng_of(seed, XT, Y); delta = cfg['turnover'][XT]
        G = _members2(m, XT, XT + '2'); Gp = _members2(prev_m, XT, XT + '2') if prev_m is not None else {}
        grp = m['M']['市场']; grp2 = m['M']['市场2']
        for fid in sorted(G):
            Mem = G[fid]; s = len(Mem)
            gs = np.array(list(collections.Counter(np.concatenate([grp[Mem][m['M'][XT][Mem] == fid], grp2[Mem][m['M'][XT + '2'][Mem] == fid]]).tolist()).values()))
            gm = float((gs ** 2).sum() / gs.sum())                      # 户所在群的平均大小
            if s - gm < 1: continue
            p = min(1.0, x / (1 - x) * cfg['p_in'] * (gm - 1) / (s - gm))
            if init:
                I, J = pw(Mem, p, rng)
            else:
                old = Gp.get(fid, np.zeros(0, int)); newc = np.setdiff1d(Mem, old); stay = np.intersect1d(Mem, old)
                I1, J1 = pw(stay, p * delta, rng); I2, J2 = pb(newc, stay, p, rng); I3, J3 = pw(newc, p, rng)
                I, J = np.concatenate([I1, I2, I3]), np.concatenate([J1, J2, J3])
            if len(I) == 0: continue
            same = ((grp[I] == grp[J]) & (grp[I] >= 0)) | ((grp2[I] >= 0) & ((grp2[I] == grp[J]) | (grp2[I] == grp2[J]))) | ((grp2[J] >= 0) & (grp[I] == grp2[J]))
            I, J = I[~same], J[~same]
            k = rng.random(len(I)) < accept(W, cfg, m, I, J, dist=False)
            I, J = I[k], J[k]
            born = (Y - rng.geometric(delta, len(I)) + 1) if init else Y
            out.append(make(T[XT], I, J, fid, born, TW[XT]))
    # 以下与 v10 相同：近邻、职位辖民、职位上下级
    rng = rng_of(seed, '近邻', Y); k = cfg['knn_k']; S = m['S']
    pk = min(1.0, cfg['c'] * cfg['base']['近邻'] * (k + 1) ** (-cfg['a']))
    I = np.repeat(S, k); J = m['knn'][:, :k].ravel()
    if init:
        pr = np.full(len(I), pk)
    else:
        newu = ~prev_m['stand'][I] if prev_m is not None else np.ones(len(I), bool)
        pr = np.where(newu, pk, pk * cfg['turnover']['近邻'])
    keep = rng.random(len(I)) < pr * accept(W, cfg, m, I, J, dist=False)
    born = (Y - rng.geometric(cfg['turnover']['近邻'], keep.sum()) + 1) if init else Y
    out.append(make(T['近邻'], I[keep], J[keep], 0, born, TW['近邻']))
    for tname, arr in sorted(m['hub_mem'].items()):
        rng = rng_of(seed, tname, Y); hh = m['hub_holder'][tname]
        S = m['S']; col = arr[S]
        for fid in sorted(hh):
            o = hh[fid]; subs = S[(col == fid) & (S != o)]
            if len(subs) == 0: continue
            ph = min(1.0, cfg['office_hub_capacity'] / len(subs))
            if init or prev_m is None or prev_m['hub_holder'][tname].get(fid) != o:
                pr = np.full(len(subs), ph)
            else:
                was = prev_m['hub_mem'][tname][subs] == fid
                pr = np.where(was, ph * cfg['turnover']['职位辖民'], ph)
            keep = rng.random(len(subs)) < pr * accept(W, cfg, m, np.full(len(subs), o), subs) ** 0.5
            out.append(make(T[tname], np.full(keep.sum(), o), subs[keep], fid, Y if not init else Y - rng.geometric(cfg['turnover']['职位辖民'], keep.sum()) + 1, TW['职位辖民']))
    if m['sup']:
        A = np.array(m['sup'])
        out.append(make(T['职位上下级'], A[:, 0], A[:, 1], A[:, 2], Y, TW['职位上下级']))
    return model.cat(*out)


def install(cfg):
    CFG.clear(); CFG.update(group_size=cfg['group_size'])
    model.World = World12; model.gen_year = gen_year; model.still_in_focus = still_in_focus
    run11.DOC = ('户-户社会关系 v12（v11 + 市场关系改为常客群：市场节点下按方位扇区×距离环+信仰/行会拆分成群，认识层市场关系只在群内生成）。'
                 'households=户 id 列表；layers=层名；sources=来源标签（类型:焦点；市场:<市场>|扇i环j|信仰|行会 为常客群）；edges 为列式：第 i 条边 = households[a[i]]–households[b[i]]，'
                 '层 layers[layer[i]]，强度 w[i]，来源 src[i]（sources 序号；多来源时为序号列表）。——Hark（刘线）')


ALT_DUNBAR3 = (1.6, 3.0)   # 未取整 2.27±30%，仅作说明


def market_share(mt):
    sh = mt.get('source_label_share', {})
    return round(sh.get('市场', 0) + sh.get(XT, 0), 4)
