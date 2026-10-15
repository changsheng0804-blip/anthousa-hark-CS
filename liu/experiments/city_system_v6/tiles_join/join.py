#!/usr/bin/env python3
"""CS 矢量瓦片房屋 → 账本房屋 id 对接（刘线）。

输入：CS 线 living/tiles/meta.json + vec/{tx}_{ty}.json（缓存于 /tmp/vec）、仓库根 world.json。
输出：join.json（CS 房屋键 → 账本 id，及每瓦片顺序映射）、join_stats.json（数字）。

方法：
  1. 读瓦片房屋，(built, destroyed, 轮廓前 4 数) 去重；片区按 meta.owner_order 首个包含质心的框归属。
  2. 片区 ↔ 账本区：比较年份对分布（余弦相似度），并在匹配后按实际落区统计。
  3. 变换：年份对在两侧都唯一的房屋作锚点；每片区 RANSAC 仿射（锚点 < MIN_ANCHOR 则用全城 RANSAC）；
     第一轮匹配后用全部匹配对按片区重新最小二乘拟合（迭代 2 次）。
  4. 匹配：每个年份对内，按变换后距离（账本单位）做匈牙利匹配，距离 > GATE 视为不匹配。

——Hark（刘线）
"""
import collections
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import HERE, ROOT, area, fetch_meta, fetch_vec, tiles  # noqa: E402

GATE = 12.0          # 账本单位；锚点残差最大约 9.6
MIN_ANCHOR = 15
REFIT_MIN = 30
RNG = np.random.default_rng(0)


def pair_of(h):
    return (h["built"], 9999 if h["destroyed"] is None else h["destroyed"])


def fit_affine(X, Y):
    Xa = np.c_[X, np.ones(len(X))]
    M, *_ = np.linalg.lstsq(Xa, Y, rcond=None)
    return M


def apply_aff(M, X):
    return np.c_[X, np.ones(len(X))] @ M


def fit_similarity(X, Y):
    """最小二乘相似变换（等比缩放+旋转+平移），返回 3×2 矩阵，与 apply_aff 兼容。"""
    mx, my = X.mean(0), Y.mean(0)
    A, B = X - mx, Y - my
    a = (A[:, 0] * B[:, 0] + A[:, 1] * B[:, 1]).sum() / (A ** 2).sum()
    b = (A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0]).sum() / (A ** 2).sum()
    R = np.array([[a, b], [-b, a]])
    return np.vstack([R, my - mx @ R])


def ransac_affine(X, Y, thr=10.0, it=2000):
    best, bestn = None, -1
    n = len(X)
    for _ in range(it):
        s = RNG.choice(n, 3, replace=False)
        try:
            M = fit_affine(X[s], Y[s])
        except np.linalg.LinAlgError:
            continue
        inl = np.linalg.norm(apply_aff(M, X) - Y, axis=1) < thr
        if inl.sum() > bestn:
            best, bestn = inl, inl.sum()
    return fit_affine(X[best], Y[best]), best


def load_cs(meta):
    T = tiles()
    Q = meta["quarters"]
    seen = {}
    houses = []          # dict(pair, c, poly, quarter)
    tile_refs = {}       # (tx,ty) -> [cs index per tile house]
    for key in sorted(T):
        refs = []
        for h in T[key]["h"]:
            k = (h[0], h[1], tuple(h[3][:4]))
            if k not in seen:
                P = np.array(h[3][:8], float).reshape(4, 2)
                c = P.mean(0)
                q = next((n for n in meta["owner_order"]
                          if Q[n][0] <= c[0] < Q[n][0] + Q[n][2] and Q[n][1] <= c[1] < Q[n][1] + Q[n][3]), None)
                seen[k] = len(houses)
                houses.append({"pair": (h[0], h[1]), "c": c, "poly": P, "q": q})
            refs.append(seen[k])
        tile_refs[key] = refs
    return houses, tile_refs, sum(len(t["h"]) for t in T.values())


def match(cs, L, lby, quarter_M):
    """每个年份对内匈牙利匹配。返回 cs_idx -> (ledger_idx, dist)。"""
    cby = collections.defaultdict(list)
    for i, h in enumerate(cs):
        cby[h["pair"]].append(i)
    X = np.array([apply_aff(quarter_M[h["q"]], h["c"][None])[0] for h in cs])
    out = {}
    for p, ci in cby.items():
        li = lby.get(p)
        if not li:
            continue
        D = np.linalg.norm(X[ci][:, None, :] - L[li][None, :, :], axis=2)
        C = np.where(D <= GATE, D, 1e6)
        r, c = linear_sum_assignment(C)
        for a, b in zip(r, c):
            if D[a, b] <= GATE:
                out[ci[a]] = (li[b], float(D[a, b]))
    return out, X


def main():
    t0 = time.time()
    meta = fetch_meta()
    fetch_vec(meta)
    S = meta["scale"]
    world = json.load(open(os.path.join(ROOT, "world.json")))
    H = world["houses"]
    L = np.array([np.mean(h["p"], 0) for h in H])
    Ld = [h["d"] for h in H]
    lby = collections.defaultdict(list)
    for i, h in enumerate(H):
        lby[pair_of(h)].append(i)
    cs, tile_refs, raw_n = load_cs(meta)
    quarters = list(meta["quarters"])
    stats = {"cs_raw_entries": raw_n, "cs_houses": len(cs), "ledger_houses": len(H)}

    # 年份对计数重合
    cpc = collections.Counter(h["pair"] for h in cs)
    lpc = {p: len(v) for p, v in lby.items()}
    stats["pair_overlap"] = sum(min(n, lpc.get(p, 0)) for p, n in cpc.items())
    stats["cs_pair_not_in_ledger"] = sum(n for p, n in cpc.items() if p not in lpc)

    # 1. 片区 ↔ 账本区（年份对分布余弦）
    dists = sorted(set(Ld))
    pairs = sorted(set(cpc) | set(lpc))
    pix = {p: i for i, p in enumerate(pairs)}

    def hist(ps):
        v = np.zeros(len(pairs))
        for p in ps:
            v[pix[p]] += 1
        return v / (np.linalg.norm(v) or 1)
    dh = {d: hist([pair_of(H[i]) for i in range(len(H)) if Ld[i] == d]) for d in dists}
    qcos = {}
    for q in quarters:
        qh = hist([h["pair"] for h in cs if h["q"] == q])
        qcos[q] = {d: round(float(qh @ dh[d]), 3) for d in dists}

    # 2. 变换：锚点
    anchors = [(i, lby[h["pair"]][0]) for i, h in enumerate(cs)
               if cpc[h["pair"]] == 1 and lpc.get(h["pair"]) == 1]
    AX = np.array([cs[i]["c"] for i, _ in anchors])
    AY = L[[j for _, j in anchors]]
    Mg, inl_g = ransac_affine(AX, AY)
    stats["anchors"] = len(anchors)
    stats["anchor_inliers_global"] = int(inl_g.sum())
    stats["global_affine"] = Mg.round(6).tolist()
    stats["global_scale_vs_meta"] = [round(float(1 / Mg[0, 0]), 3), round(float(1 / Mg[1, 1]), 3), S]
    aq = np.array([cs[i]["q"] for i, _ in anchors])
    QM = {None: Mg}
    stats["quarter_anchor_n"] = {}
    for q in quarters:
        s = aq == q
        stats["quarter_anchor_n"][q] = int(s.sum())
        QM[q] = ransac_affine(AX[s], AY[s])[0] if s.sum() >= MIN_ANCHOR else Mg

    # 3. 匹配 + 按片区重拟合：只用「门限内唯一同年份对候选」的匹配对（不用歧义匹配，避免自我强化），
    #    相似变换（全城锚点显示无剪切、x/y 比例差 < 2%），样本 < REFIT_MIN 的片区沿用全城变换。
    stats["quarter_refit_n"] = {}
    for it in range(3):
        m, X = match(cs, L, lby, QM)
        if it == 2:
            break
        for q in quarters:
            idx = [i for i in m if cs[i]["q"] == q
                   and sum(np.linalg.norm(L[lby[cs[i]["pair"]]] - X[i], axis=1) <= GATE) == 1]
            stats["quarter_refit_n"][q] = len(idx)
            if len(idx) >= REFIT_MIN:
                Mq, inl = ransac_affine(np.array([cs[i]["c"] for i in idx]), L[[m[i][0] for i in idx]])
                QM[q] = fit_similarity(np.array([cs[i]["c"] for i in idx])[inl], L[[m[i][0] for i in idx]][inl])
            else:
                QM[q] = Mg

    t_join = time.time() - t0
    matched = len(m)
    used = {j for j, _ in m.values()}
    stats["matched"] = matched
    stats["match_rate_cs"] = round(matched / len(cs), 4)
    stats["match_rate_ledger"] = round(matched / len(H), 4)
    stats["cs_unmatched"] = len(cs) - matched
    un = [i for i in range(len(cs)) if i not in m]
    stats["cs_unmatched_reason"] = {
        "年份对不在账本": sum(1 for i in un if cs[i]["pair"] not in lpc),
        "同年份对账本房屋已被占尽": sum(1 for i in un if cs[i]["pair"] in lpc
                                     and cpc[cs[i]["pair"]] > lpc[cs[i]["pair"]]),
    }
    stats["cs_unmatched_reason"]["门限外/其他"] = stats["cs_unmatched"] - sum(stats["cs_unmatched_reason"].values())
    absent = [j for j in range(len(H)) if j not in used]
    alive_any = lambda h: any(h["built"] <= Y and (h["destroyed"] is None or h["destroyed"] > Y) for Y in (40, 50, 60))
    stats["ledger_absent"] = len(absent)
    stats["ledger_absent_breakdown"] = {
        "AF40/50/60 均不在世": sum(1 for j in absent if not alive_any(H[j])),
        "在世但未匹配": sum(1 for j in absent if alive_any(H[j])),
    }
    stats["ledger_absent_by_d"] = dict(collections.Counter(Ld[j] for j in absent))

    # 歧义：门限内同年份对候选 >1
    amb = 0
    for i, (j, dd) in m.items():
        li = lby[cs[i]["pair"]]
        if sum(np.linalg.norm(L[li] - X[i], axis=1) <= GATE) > 1:
            amb += 1
    stats["matched_with_rival_in_gate"] = amb

    # 按片区残差与落区
    per_q = {}
    for q in quarters + [None]:
        idx = [i for i in m if cs[i]["q"] == q]
        n_q = sum(1 for h in cs if h["q"] == q)
        if not n_q:
            continue
        r = np.array([m[i][1] for i in idx]) if idx else np.zeros(1)
        per_q[str(q)] = {
            "cs": n_q, "matched": len(idx), "rate": round(len(idx) / n_q, 4),
            "resid_median": round(float(np.median(r)), 2), "resid_p90": round(float(np.percentile(r, 90)), 2),
            "resid_rms": round(float(np.sqrt((r ** 2).mean())), 2),
            "anchors": stats["quarter_anchor_n"].get(q, 0),
            "affine": QM[q].round(5).tolist(),
            "matched_d": dict(collections.Counter(Ld[m[i][0]] for i in idx).most_common()),
            "pair_cosine_d": qcos.get(q),
        }
    stats["per_quarter"] = per_q
    stats["global_affine_full"] = Mg.tolist()

    # 抽查 20 栋面积比
    pick = RNG.choice(sorted(m), 20, replace=False)
    samp = []
    for i in pick:
        j = m[int(i)][0]
        a_cs = area(cs[i]["poly"][:4]) / S ** 2
        a_l = area(np.array(H[j]["p"]))
        samp.append({"ledger_id": H[j]["id"], "pair": list(cs[i]["pair"]), "d": Ld[j], "quarter": cs[i]["q"],
                     "dist": round(m[int(i)][1], 2), "area_cs": round(a_cs, 2), "area_ledger": round(a_l, 2),
                     "ratio": round(a_cs / a_l, 2)})
    stats["area_sample"] = samp
    allr = np.array([area(cs[i]["poly"][:4]) / S ** 2 / area(np.array(H[j]["p"])) for i, (j, _) in m.items()])
    a_cs_all = np.array([area(cs[i]["poly"][:4]) / S ** 2 for i in m])
    a_l_all = np.array([area(np.array(H[j]["p"])) for j, _ in m.values()])
    stats["area_ratio_all"] = {"median": round(float(np.median(allr)), 3),
                               "p10": round(float(np.percentile(allr, 10)), 3),
                               "p90": round(float(np.percentile(allr, 90)), 3),
                               "pearson_cs_vs_ledger": round(float(np.corrcoef(a_cs_all, a_l_all)[0, 1]), 3)}
    stats["join_seconds"] = round(t_join, 2)

    # 输出：每瓦片按房屋顺序的账本 id（未匹配 null）
    tile_ids = {f"{tx}_{ty}": [H[m[i][0]]["id"] if i in m else None for i in refs]
                for (tx, ty), refs in tile_refs.items()}
    json.dump({"note": "CS vec 瓦片房屋顺序 → 账本 id（null=未匹配）。——Hark（刘线）", "tiles": tile_ids},
              open(os.path.join(HERE, "join.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(stats, open(os.path.join(HERE, "join_stats.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k not in ("per_quarter", "area_sample")}, ensure_ascii=False, indent=1))
    for q, v in per_q.items():
        print(q, {k: v[k] for k in ("cs", "matched", "rate", "resid_median", "resid_p90", "anchors", "matched_d")})


if __name__ == "__main__":
    main()
