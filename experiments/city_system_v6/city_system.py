#!/usr/bin/env python3
"""city_system v6 —— 以账本房屋为户籍单位的城市制度层（刘线）。

硬件（world.json 的 houses / structures）→ 制度（区、坊、供水组、教区、哨/征工点、配给点、口粮、
节点担任者）。只读 world.json，不读逐人数据。

  build(world, Y, S=None)  从头生成第 Y 年（AF）的制度状态
  apply(state, event)      增量：event = ("build", [hidx..]) | ("destroy", [hidx..])
                                    | ("struct_add", sidx) | ("struct_remove", sidx)
  materialize(state)       → (records, nodes)，供比对/导出
  python3 city_system.py   跑 AF41–70 增量验证 + 对账 + 性能，写 results.json

——Hark（刘线）
"""
import bisect
import gzip
import json
import os
import sys
import time
import tracemalloc

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

POP_PER_HOUSE = 9            # engine/rules：人口 = 房屋 × 9
FANG_SIZE = 150              # 假设：每 ~150 栋一坊
WALL_SEG = 50.0              # 假设：城墙每 50 单位一段 = 一个哨/征工点
ARIAN = {"arian_meeting", "church_arian_brick"}
FIELDS = ("d", "fang", "water", "parish", "arian", "watch", "grain", "ration")
NODE_TITLE = {"区": "区长", "坊": "坊长", "水": "水役头", "教": "长老", "阿": "长老(阿里乌)", "哨": "哨长"}


def food_cap(Y):
    """engine/rules 粮食上限：AF<46 153,202；46–54 173,202；≥55 193,202。"""
    return 153202 if Y < 46 else (173202 if Y < 55 else 193202)


def standing(o, Y):
    return o["built"] <= Y and (o["destroyed"] is None or o["destroyed"] > Y)


def hilbert(x, y, order=16):
    n = 1 << order
    x = x.astype(np.int64).copy()
    y = y.astype(np.int64).copy()
    d = np.zeros_like(x)
    s = n >> 1
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64)
        ry = ((y & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ ry)
        flip = (ry == 0) & (rx == 1)
        x = np.where(flip, n - 1 - x, x)
        y = np.where(flip, n - 1 - y, y)
        sw = ry == 0
        x, y = np.where(sw, y, x), np.where(sw, x, y)
        s >>= 1
    return d


# ---------------------------------------------------------------- 静态准备（与年份无关）
class Static:
    pass


def prepare(world):
    S = Static()
    H = world["houses"]
    S.hid = [h["id"] for h in H]
    S.idnum = np.array([int(h["id"][1:]) for h in H], dtype=np.int64)
    S.d = [h["d"] for h in H]
    S.built = np.array([h["built"] for h in H], dtype=np.int64)
    S.destroyed = np.array([10 ** 9 if h["destroyed"] is None else h["destroyed"] for h in H], dtype=np.int64)
    S.xy = np.array([np.asarray(h["p"], float).mean(0) for h in H])        # 质心 = 顶点均值
    lo, hi = S.xy.min(0), S.xy.max(0)
    g = ((S.xy - lo) / (hi - lo + 1e-9) * 65535).astype(np.int64)
    S.hkey = hilbert(g[:, 0], g[:, 1])
    S.seniority = S.built * 10 ** 7 + S.idnum   # 年资：最早建成，同年按 id
    # 坊界：区内全部账本房屋按 (Hilbert, id) 排序，每 FANG_SIZE 栋一界；坊界固定不随增减移动（假设）
    S.fang_bounds = {}
    S.fang = [None] * len(H)
    by_d = {}
    for i, d in enumerate(S.d):
        by_d.setdefault(d, []).append(i)
    for d, idx in by_d.items():
        idx.sort(key=lambda i: (S.hkey[i], S.idnum[i]))
        S.fang_bounds[d] = [(int(S.hkey[i]), int(S.idnum[i])) for i in idx[::FANG_SIZE]]
        for r, i in enumerate(idx):
            S.fang[i] = f"{d}#f{r // FANG_SIZE:02d}"
    # 结构 → 设施点
    S.structs = world["structures"]
    S.sidx = {s["id"]: k for k, s in enumerate(S.structs)}
    S.kind_pts = {}          # sidx -> [(kind, label, xy), ...]
    for k, s in enumerate(S.structs):
        g = s["geom"]
        c = np.asarray(g["coords"], float)
        cen = c.reshape(2) if g["type"] == "point" else c.mean(0)
        t, sid = s["type"], s["id"]
        pts = []
        if t == "cistern":
            pts.append(("water", sid, cen))
        elif t == "church":
            pts.append(("church_all", sid, cen))
            if sid not in ARIAN:
                pts.append(("parish", sid, cen))
        elif t == "granary":
            pts.append(("grain", sid, cen))
        elif t == "gate":
            pts.append(("watch", sid, cen))
        elif t == "wall":
            for a, b, segno in _wall_segments(c):
                for q in _sample(a, b):
                    pts.append(("watch", f"{sid}#s{segno:02d}", q))
        S.kind_pts[k] = pts
    S.kinds = ("water", "parish", "church_all", "watch", "grain")
    return S


def _wall_segments(c):
    """把折线按累计长度切成 WALL_SEG 段。"""
    out, acc = [], 0.0
    for a, b in zip(c[:-1], c[1:]):
        L = float(np.hypot(*(b - a)))
        t = 0.0
        while t < L - 1e-9:
            t2 = min(L, t + WALL_SEG - (acc % WALL_SEG))
            seg = int(acc // WALL_SEG)
            out.append((a + (b - a) * t / L, a + (b - a) * t2 / L, seg))
            acc += t2 - t
            t = t2
    return out


def _sample(a, b, step=1.0):
    L = float(np.hypot(*(b - a)))
    m = max(1, int(np.ceil(L / step)))
    return [a + (b - a) * (j + 0.5) / m for j in range(m)]


def fang_of(S, d, hkey, idnum):
    """账本外新房屋用：按坊界二分。"""
    b = S.fang_bounds[d]
    return f"{d}#f{max(0, bisect.bisect_right(b, (hkey, idnum)) - 1):02d}"


# ---------------------------------------------------------------- 状态
class State:
    pass


def _make_trees(S, sset):
    trees = {}
    for kind in S.kinds:
        pts, lab = [], []
        for k in sorted(sset):
            for kd, label, q in S.kind_pts[k]:
                if kd == kind:
                    pts.append(q)
                    lab.append(label)
        trees[kind] = (cKDTree(np.array(pts)), lab) if pts else (None, [])
    return trees


def _query(st, kind, xy):
    tree, lab = st.trees[kind]
    if tree is None:
        return [None] * len(xy)
    _, j = tree.query(xy)
    return [lab[t] for t in np.atleast_1d(j)]


def _assign(st, hs):
    """hs：房屋下标列表 → {h: [water, parish, arian, watch, grain]}"""
    if not len(hs):
        return {}
    xy = st.S.xy[hs]
    w = _query(st, "water", xy)
    p = _query(st, "parish", xy)
    a = _query(st, "church_all", xy)
    g = _query(st, "watch", xy)
    r = _query(st, "grain", xy)
    return {h: [w[i], p[i], a[i] if a[i] in ARIAN else None, g[i], r[i]] for i, h in enumerate(hs)}


def _node_keys(st, h):
    S, v = st.S, st.rec[h]
    ks = [("区", S.d[h]), ("坊", S.fang[h])]
    for tag, x in (("水", v[0]), ("教", v[1]), ("阿", v[2]), ("哨", v[3])):
        if x is not None:
            ks.append((tag, x))
    return ks


def _join(st, h):
    sen = st.S.seniority
    for k in _node_keys(st, h):
        m = st.members.get(k)
        if m is None:
            st.members[k] = {h}
            st.holder[k] = h
        else:
            m.add(h)
            if sen[h] < sen[st.holder[k]]:
                st.holder[k] = h


def _leave(st, h):
    sen = st.S.seniority
    for k in _node_keys(st, h):
        m = st.members[k]
        m.discard(h)
        if not m:
            del st.members[k], st.holder[k]
        elif st.holder[k] == h:
            st.holder[k] = min(m, key=sen.__getitem__)


def build(world, Y, S=None):
    S = S or prepare(world)
    st = State()
    st.S, st.Y = S, Y
    st.sset = {k for k, s in enumerate(S.structs) if standing(s, Y)}
    st.trees = _make_trees(S, st.sset)
    alive = np.nonzero((S.built <= Y) & (S.destroyed > Y))[0]
    st.rec = _assign(st, alive.tolist())
    st.members, st.holder = {}, {}
    # 按年资顺序加入：第一个加入者即担任者
    for h in alive[np.argsort(S.seniority[alive], kind="stable")].tolist():
        for k in _node_keys(st, h):
            m = st.members.get(k)
            if m is None:
                st.members[k] = {h}
                st.holder[k] = h
            else:
                m.add(h)
    return st


def apply(st, ev):
    kind, arg = ev
    if kind == "build":
        hs = [h for h in arg if h not in st.rec]
        st.rec.update(_assign(st, hs))
        for h in hs:
            _join(st, h)
    elif kind == "destroy":
        for h in arg:
            if h in st.rec:
                _leave(st, h)
                del st.rec[h]
    elif kind in ("struct_add", "struct_remove"):
        if kind == "struct_add":
            st.sset.add(arg)
        else:
            st.sset.discard(arg)
        if not st.S.kind_pts[arg]:          # 道路、街区多边形等：不改任何制度字段
            return 0
        st.trees = _make_trees(st.S, st.sset)
        hs = list(st.rec)
        new = _assign(st, hs)
        changed = [h for h in hs if new[h] != st.rec[h]]
        for h in changed:
            _leave(st, h)
        for h in changed:
            st.rec[h] = new[h]
            _join(st, h)
        return len(changed)
    return 0


def materialize(st):
    S = st.S
    n = len(st.rec)
    cap = food_cap(st.Y)
    ration = cap / n if n else 0.0
    recs = {}
    for h, v in st.rec.items():
        recs[S.hid[h]] = (S.d[h], S.fang[h], v[0], v[1], v[2], v[3], v[4], ration)
    nodes = {f"{k[0]}:{k[1]}": (NODE_TITLE[k[0]], S.hid[st.holder[k]], len(m)) for k, m in st.members.items()}
    return recs, nodes


def events_for_year(S, Y):
    evs = []
    for k, s in enumerate(S.structs):
        if s["destroyed"] == Y:
            evs.append(("struct_remove", k))
        if s["built"] == Y:
            evs.append(("struct_add", k))
    for h in np.nonzero(S.built == Y)[0].tolist():
        evs.append(("build", [h]))
    dl = np.nonzero(S.destroyed == Y)[0].tolist()
    if dl:
        evs.append(("destroy", dl))
    return evs


def diff(a, b):
    ra, na = a
    rb, nb = b
    bad = {f: 0 for f in FIELDS}
    keys = set(ra) | set(rb)
    miss = sum(1 for k in keys if k not in ra or k not in rb)
    for k in keys:
        if k in ra and k in rb:
            for i, f in enumerate(FIELDS):
                if ra[k][i] != rb[k][i]:
                    bad[f] += 1
    nb_bad = sum(1 for k in set(na) | set(nb) if na.get(k) != nb.get(k))
    return miss, bad, nb_bad


def main():
    t0 = time.perf_counter()
    world = json.load(open(os.path.join(ROOT, "world.json")))
    t_load = time.perf_counter() - t0
    out = {"load_s": round(t_load, 3)}

    # 性能：全城 build
    t0 = time.perf_counter(); S = prepare(world); t_prep = time.perf_counter() - t0
    bt = []
    for Y in (41, 55, 70, 70, 70):
        t0 = time.perf_counter(); st = build(world, Y, S); bt.append(time.perf_counter() - t0)
    tracemalloc.start()
    st70 = build(world, 70, S)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    recs70, nodes70 = materialize(st70)
    js = json.dumps([[k, *v] for k, v in recs70.items()], ensure_ascii=False).encode()
    gz = gzip.compress(js, 9)
    jn = gzip.compress(json.dumps(nodes70, ensure_ascii=False).encode(), 9)
    out["perf"] = {
        "prepare_s": round(t_prep, 3),
        "build_s_Y41_55_70": [round(x, 3) for x in bt],
        "build_plus_prepare_s": round(t_prep + min(bt[2:]), 3),
        "build_mem_peak_MB": round(peak / 2 ** 20, 1),
        "state_mem_MB": round(cur / 2 ** 20, 1),
        "records_json_bytes": len(js), "records_gz_bytes": len(gz),
        "bytes_per_household_gz": round(len(gz) / len(recs70), 1),
        "nodes_gz_bytes": len(jn), "n_nodes_70": len(nodes70),
    }

    # 增量 AF41–70
    st = build(world, 40, S)
    yearly, times = [], {"build": [], "destroy": [], "struct_add": [], "struct_remove": []}
    destroy_per_house = []
    all_ok = True
    for Y in range(41, 71):
        st.Y = Y
        evs = events_for_year(S, Y)
        ch = 0
        for ev in evs:
            t0 = time.perf_counter()
            r = apply(st, ev)
            dt = time.perf_counter() - t0
            times[ev[0]].append(dt)
            if ev[0] == "destroy":
                destroy_per_house.append(dt / len(ev[1]))
            if ev[0].startswith("struct"):
                ch += r or 0
        inc = materialize(st)
        ref = materialize(build(world, Y, S))
        miss, bad, nbad = diff(inc, ref)
        ok = miss == 0 and not any(bad.values()) and nbad == 0
        all_ok &= ok
        recs, nodes = inc
        n = len(recs)
        ledger_n = int(sum(1 for h in world["houses"] if standing(h, Y)))
        rsum = sum(v[7] for v in recs.values())
        yearly.append({
            "Y": Y, "events": len(evs),
            "built": int((S.built == Y).sum()), "destroyed": int((S.destroyed == Y).sum()),
            "structs": [S.structs[e[1]]["id"] + ("+" if e[0] == "struct_add" else "-") for e in evs if e[0].startswith("struct")],
            "struct_reassigned_houses": ch,
            "houses": n, "ledger_houses": ledger_n, "pop": n * POP_PER_HOUSE, "bread_books": len(recs),
            "food_cap": food_cap(Y), "ration": round(food_cap(Y) / n, 4), "ration_sum": round(rsum, 6),
            "ration_sum_err": abs(rsum - food_cap(Y)),
            "nodes": len(nodes), "incr_eq_full": ok, "missing": miss, "field_mismatch": bad, "node_mismatch": nbad,
        })
        print(Y, n, ledger_n, len(evs), "OK" if ok else f"FAIL {miss} {bad} {nbad}", flush=True)

    def stat(v):
        if not v:
            return None
        a = np.array(v) * 1000
        return {"n": len(a), "median_ms": round(float(np.median(a)), 4), "p99_ms": round(float(np.percentile(a, 99)), 4),
                "max_ms": round(float(a.max()), 4)}
    out["incremental"] = {k: stat(v) for k, v in times.items()}
    out["incremental"]["destroy_per_house"] = stat(destroy_per_house)
    out["incremental"]["all_years_equal"] = bool(all_ok)
    out["yearly"] = yearly

    # 坊规模（Y=70 站着房屋）
    fs = [c for (t, _, c) in nodes70.values() if t == "坊长"]
    out["fang_70"] = {"n": len(fs), "min": min(fs), "median": float(np.median(fs)), "max": max(fs)}
    out["node_counts_70"] = {}
    for t, _, c in nodes70.values():
        out["node_counts_70"][t] = out["node_counts_70"].get(t, 0) + 1
    out["sample_nodes_70"] = {k: v for k, v in nodes70.items() if not k.startswith("坊:")}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=int)
    print(json.dumps({k: out[k] for k in ("perf", "incremental", "fang_70", "node_counts_70")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
