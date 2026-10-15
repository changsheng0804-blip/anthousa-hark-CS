#!/usr/bin/env python3
"""为每个 CS vec 瓦片烤户籍旁车 reg/{Y}/{tx}_{ty}.json（Y = 40/50/60）。——Hark（刘线）

依赖 join.py 产出的 join.json（瓦片房屋顺序 → 账本 id）。制度在账本坐标里由 ../city_system.py 计算，
再按 id 连接到瓦片——CS 瓦片坐标对个体房屋有约 5 单位的位置扰动，不能直接用于空间制度。

旁车格式：{"Y":50,"f":[字段名],"h":[每栋一项，顺序同 vec 瓦片的 h]}
  未匹配 → null；匹配但该年不在世 → [账本id]；
  否则 [账本id, 区, 坊, 教区, 供水组, 哨, 行会, 职务]，缺省字段为 null，职务为 0 或 [职名, 节点]。
"""
import gzip
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
import city_system as cs  # noqa: E402

FIELDS = ["id", "d", "fang", "parish", "water", "watch", "guild", "office"]


def main():
    world = json.load(open(os.path.join(cs.ROOT, "world.json")))
    tiles = json.load(open(os.path.join(HERE, "join.json")))["tiles"]
    t0 = time.time()
    S = cs.prepare(world)
    t_prep = time.time() - t0
    hpos = {h: i for i, h in enumerate(S.hid)}
    out = {"prepare_s": round(t_prep, 3), "years": {}}
    for Y in (40, 50, 60):
        t1 = time.time()
        st = cs.build(world, Y, S)
        recs, _ = cs.materialize(st)
        t_build = time.time() - t1
        t2 = time.time()
        office = {S.hid[h]: [cs.NODE_TITLE[k[0]], f"{k[0]}:{k[1]}"] for h, k in st.office.items()}
        d = os.path.join(HERE, "reg", str(Y))
        os.makedirs(d, exist_ok=True)
        nb = ng = n_rec = n_off = n_dead = n_null = 0
        for key, ids in tiles.items():
            rows = []
            for hid in ids:
                if hid is None:
                    rows.append(None)
                    n_null += 1
                    continue
                r = recs.get(hid)
                if r is None:
                    rows.append([hid])
                    n_dead += 1
                    continue
                # r = (d, fang, water, parish, arian, watch, grain, ration, guild)
                parish = r[3] if r[4] is None else [r[3], r[4]]
                o = office.get(hid, 0)
                n_off += o != 0
                rows.append([hid, r[0], r[1], parish, r[2], r[5], r[8], o])
                n_rec += 1
            b = json.dumps({"Y": Y, "f": FIELDS, "h": rows}, ensure_ascii=False, separators=(",", ":")).encode()
            open(os.path.join(d, f"{key}.json"), "wb").write(b)
            nb += len(b)
            ng += len(gzip.compress(b, 9))
        t_bake = time.time() - t2
        out["years"][Y] = {"tiles": len(tiles), "bytes": nb, "gzip_bytes": ng,
                           "houses_with_record": n_rec, "matched_not_standing": n_dead, "unmatched_null": n_null,
                           "office_holders_in_tiles": n_off, "office_holders_city": len(st.office),
                           "standing_ledger": len(recs),
                           "build_s": round(t_build, 3), "bake_s": round(t_bake, 3)}
        print(Y, out["years"][Y])

    out["total_s"] = round(time.time() - t0, 3)
    json.dump(out, open(os.path.join(HERE, "bake_stats.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
