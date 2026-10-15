#!/usr/bin/env python3
"""位置歧义下的字段稳定度（AF50）。——Hark（刘线）

CS 瓦片房屋相对账本位置有约 5 单位扰动，而相邻房屋间距约 1.5 单位，同年份对门限内常有多个候选。
对每栋已匹配且 AF50 在世的房屋，取门限内同年份对、AF50 在世的全部账本候选，看各字段是否全部一致：
一致 → 该字段不受「到底是哪一栋」影响；不一致 → 字段值取决于匹配的个体选择。
"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
import city_system as csys  # noqa: E402
from join import GATE, apply_aff, load_cs, pair_of  # noqa: E402
from load import fetch_meta  # noqa: E402

Y = 50


def main():
    meta = fetch_meta()
    world = json.load(open(os.path.join(csys.ROOT, "world.json")))
    H = world["houses"]
    L = np.array([np.mean(h["p"], 0) for h in H])
    lby = collections.defaultdict(list)
    for i, h in enumerate(H):
        lby[pair_of(h)].append(i)
    st_ = json.load(open(os.path.join(HERE, "join_stats.json")))
    QM = {q: np.array(v["affine"]) for q, v in st_["per_quarter"].items()}
    QM[None] = np.array(st_["global_affine_full"])
    cs, tile_refs, _ = load_cs(meta)
    tiles = json.load(open(os.path.join(HERE, "join.json")))["tiles"]
    mid = {}
    for (tx, ty), refs in tile_refs.items():
        for i, hid in zip(refs, tiles[f"{tx}_{ty}"]):
            if hid is not None:
                mid[i] = hid
    S = csys.prepare(world)
    st = csys.build(world, Y, S)
    recs, _ = csys.materialize(st)
    names = ["d", "fang", "parish", "water", "watch", "guild"]
    col = [0, 1, 3, 2, 5, 8]
    agree = collections.Counter()
    n = 0
    ncand = []
    for i, hid in mid.items():
        if hid not in recs:
            continue
        x = apply_aff(QM.get(cs[i]["q"] or None, QM[None]), cs[i]["c"][None])[0]
        li = [j for j in lby[cs[i]["pair"]] if np.linalg.norm(L[j] - x) <= GATE and H[j]["id"] in recs]
        n += 1
        ncand.append(len(li))
        for nm, c in zip(names, col):
            if len({recs[H[j]["id"]][c] for j in li}) == 1:
                agree[nm] += 1
    out = {"Y": Y, "houses": n, "cand_in_gate_median": float(np.median(ncand)),
           "cand_in_gate_p90": float(np.percentile(ncand, 90)),
           "single_candidate": int(sum(1 for c in ncand if c == 1)),
           "field_all_candidates_agree": {k: round(agree[k] / n, 4) for k in names}}
    print(out)
    json.dump(out, open(os.path.join(HERE, "stability.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
