"""v11：Dunbar 层靶改为按"户"计。
模拟动力学完全沿用 v10（按路径载入 ../social_v10/model.py、metrics.py、data.py，不改它们）；
只改输出端：按户单位的分层 3/7/23/68，普通户上限 68 户，职位户上限 68×k（k 为假设参数）。

换算（写明为模型假设）：Dunbar 层 5/15/50/150 是"人"；Hill & Dunbar 2003 圣诞卡样本中 150 人约对应 68 户
→ 每户约 150/68 ≈ 2.2 个成人关系人。按户层 = 人层 / 2.2：5→2.3≈3、15→6.8≈7、50→22.7≈23、150→68。
职位户上限 ×k（k∈{1,1.5,2}）：假设职务带来额外认识面（辖民、上下级），不是文献给定值。
——Hark（刘线）"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V10 = os.path.abspath(os.path.join(HERE, '..', 'social_v10'))
if V10 not in sys.path:
    sys.path.insert(0, V10)
import data as data10      # noqa: E402  ../social_v10/data.py（再载入 v8 cast / v7 city_system）
import model as model10    # noqa: E402  ../social_v10/model.py
import metrics as metrics10  # noqa: E402  ../social_v10/metrics.py

LAYERS = [3, 7, 23, 68]
PERSONS_PER_HH = 150 / 68

# 靶区：沿用 v10 的★版本，只把 Dunbar 四层换成按户层（±30%；68 层上限即截断上限 68）
TARGETS = {}
for k, v in metrics10.TARGETS.items():
    if k.startswith('dunbar_cum_'):
        continue
    TARGETS[k] = v
_D = {
    'dunbar_cum_3': (2.1, 3.9, 'Dunbar 5 人层 ÷2.2 人/户（Hill&Dunbar 2003 150 人≈68 户）≈2.3→取 3，±30%'),
    'dunbar_cum_7': (4.9, 9.1, '15 人层 ÷2.2 ≈6.8→7，±30%'),
    'dunbar_cum_23': (16.1, 29.9, '50 人层 ÷2.2 ≈22.7→23，±30%'),
    'dunbar_cum_68': (47.6, 68.0, '150 人层 ÷2.2 ≈68，下 30%，上限即 68 截断（职位户 ×k 上浮不影响全体中位）'),
}
TARGETS = {**_D, **TARGETS}


def tiers_k(W, uk, s, is_off, k):
    """按户分层：每条边在两端各自的强度排名；普通户上限 68，职位户上限 round(68·k)。
    边保留 ⇔ 两端排名都在各自上限内；层 = 两端较差排名落在 [0,3)/[3,7)/[7,23)/[23,上限) → 强/中/弱/认识。"""
    N = W.N
    tb = ((uk * 2654435761) % 100000) / 1e9            # 与 v10 相同的确定性并列打破
    a, b, ss, rank = model10.topk_neighbors(W, uk, s + tb, 10 ** 9)
    ka = np.minimum(a, b) * N + np.maximum(a, b)
    r_end = np.full((len(uk), 2), 10 ** 9)
    pos = np.searchsorted(uk, ka)
    first = a < b
    r_end[pos[first], 0] = rank[first]; r_end[pos[~first], 1] = rank[~first]
    cap = np.where(is_off, int(round(LAYERS[3] * k)), LAYERS[3])
    u = uk // N; v = uk % N
    keep = (r_end[:, 0] < cap[u]) & (r_end[:, 1] < cap[v])
    worst = r_end.max(1)
    tier = np.digitize(worst, LAYERS[:3])               # 0..3
    return tier, keep


def compute(N, stand, uk, tier, styp, faith, guild, is_off, latent_uk, strength, seed, heavy):
    m = metrics10.compute(N, stand, uk, tier, styp, faith, guild, is_off, latent_uk, strength, seed=seed, heavy=heavy)
    for L10, L in zip((5, 15, 50, 150), LAYERS):
        m[f'dunbar_cum_{L}'] = m.pop(f'dunbar_cum_{L10}')
    # 触顶：普通户度 ≥68 的占比（v10 的 cap_share 按 150 算，此处重算）
    S = np.flatnonzero(stand); pos = np.full(N, -1); pos[S] = np.arange(len(S))
    deg = np.bincount(pos[uk // N], minlength=len(S)) + np.bincount(pos[uk % N], minlength=len(S))
    off = is_off[S]
    m['cap_share'] = float((deg[~off] >= LAYERS[3]).mean())
    m['office_median_degree'] = float(np.median(deg[off])) if off.any() else None
    m['nonoffice_median_degree'] = float(np.median(deg[~off]))
    m['n_office'] = int(off.sum())
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
