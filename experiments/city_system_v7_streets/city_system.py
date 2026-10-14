#!/usr/bin/env python3
"""city_system v7 —— 街道网络版制度层（刘线）。

v6 用直线最近设施定供水组/教区/配给点/哨，用「区内房屋 Hilbert 序每 150 栋」切坊（含未来房屋，时代错置）。
v7 把空间依据换成当年站着的街道网络：
  · 街道图：账本 world.json 道路（折线，按 built/destroyed 取当年）+ 上游 facts_upstream 街名折线
    （仿射到账本坐标，只取上游房屋凸包内的段，按街名年份取当年）；交点切分、端点吸附、设施门口切分。
  · 每户门口 = 最近站着街段上的垂足；步行距离 = 门口垂距 + 街网最短路 + 设施门口垂距。
  · 多源 Dijkstra（每类设施一次，键 = (距离, 设施标签号) 字典序）。
  · 坊 = 当年街网平面图的面（半边遍历），按临街长度过小合并、过大按街段切。

  build(ctx, Y, streets=None, sset=None)  从头生成第 Y 年
  apply(st, ev)  ev = ("build",[h..]) | ("destroy",[h..]) | ("struct_add",k) | ("struct_remove",k)
                      | ("street_add",si) | ("street_remove",si)
  materialize(st) → (records, nodes)

——Hark（刘线）
"""
import bisect
import gzip
import heapq
import json
import math
import os
import sys
import time
import tracemalloc

import numpy as np
from scipy.spatial import Delaunay

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("city_system_v6", os.path.join(HERE, "..", "city_system_v6", "city_system.py"))
cs6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs6)

UPSTREAM = os.path.join(ROOT, "docs", "living", "xerolophos", "facts_upstream")
INF = float("inf")
NEVER = 10 ** 9

# ---- 模型假设（数值）
SNAP_MAX = 6.0        # 街端点到别街距离 ≤ 此值（账本单位）则补一段连接；取值≈上游→账本仿射残差 p95（假设）
HULL_GROW = 1.02      # 上游覆盖范围 = 上游房屋质心凸包，自质心外扩 2%（假设）
TOPK = 48             # 每点静态保存的最近街段候选数（只是加速，不改结果；不足时回退全扫）
F_MIN = 20.0          # 坊：临街长度 < F_MIN 的面并入共边最长的邻面（假设）
F_MAX = 100.0         # 坊：临街长度 > F_MAX 的面沿边界按街段切成 ≤F_MAX 的段（假设）
Q = 100.0             # 节点坐标量化 0.01 单位
F_DEPTH = 20.0        # 坊：离街垂距每 20 单位一层（街网外的深处人家另成坊，假设）
F_SECTOR = 4          # 坊：门口落在街端点（垂足夹到端点）的人家按方位 4 扇区分（假设）

KINDS = ("water", "parish", "church_all", "watch", "grain")
DKINDS = ("water", "parish", "grain", "watch")
FIELDS = ("d", "fang", "water", "parish", "arian", "watch", "grain", "ration", "guild", "street",
          "dist_water", "dist_parish", "dist_grain", "dist_watch")


def key_of(x, y):
    return (int(round(x * Q)), int(round(y * Q)))


def kxy(k):
    return (k[0] / Q, k[1] / Q)


def kdist(k, P):
    return math.hypot(k[0] / Q - P[0], k[1] / Q - P[1])


# ================================================================ 静态准备
class Ctx:
    pass


def _affine_fit(src, dst):
    X = np.c_[src, np.ones(len(src))]
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)
    res = np.sqrt(((X @ M - dst) ** 2).sum(1))
    return M, res


def prepare(world):
    C = Ctx()
    C.world = world
    S = cs6.prepare(world)              # 复用 v6：房屋、年资、设施点/标签、行会、区
    C.S = S
    N = len(S.hid)
    pos = {int(x): i for i, x in enumerate(S.idnum.tolist())}
    # ---- 上游坐标 → 账本坐标：按房屋 id 对齐的仿射最小二乘
    U = json.load(open(os.path.join(UPSTREAM, "houses.json")))["houses"]
    us, ws, C.up_idx = [], [], []
    for r in U:
        i = pos.get(int(r[0]))
        if i is None:
            continue
        p = np.asarray(r[4], float).reshape(-1, 2).mean(0)
        us.append(p)
        ws.append(S.xy[i])
        C.up_idx.append(i)
    us, ws = np.array(us), np.array(ws)
    M, res = _affine_fit(us, ws)
    C.affine = M
    C.affine_stats = {"matched_houses": len(us), "rms": float(np.sqrt((res ** 2).mean())),
                      "median": float(np.median(res)), "p95": float(np.percentile(res, 95)),
                      "scale": float(np.sqrt(abs(np.linalg.det(M[:2]))))}
    cen = ws.mean(0)
    from scipy.spatial import ConvexHull
    hv = ws[ConvexHull(ws).vertices]
    C.hull = Delaunay(cen + (hv - cen) * HULL_GROW)
    C.up_set = np.zeros(N, bool)
    C.up_set[C.up_idx] = True

    def inhull(P):
        return C.hull.find_simplex(np.atleast_2d(P)) >= 0

    # ---- 街道表（静态：历来所有街）
    streets = []
    for k, s in enumerate(world["structures"]):
        if s["type"] == "road":
            streets.append({"id": s["id"], "name": s.get("label") or s["name"], "src": "ledger",
                            "built": s["built"], "destroyed": NEVER if s["destroyed"] is None else s["destroyed"],
                            "pts": np.asarray(s["geom"]["coords"], float)})
    SN = json.load(open(os.path.join(UPSTREAM, "streetnames.json")))
    C.up_clip = {"streets": len(SN), "kept_runs": 0, "segs_total": 0, "segs_kept": 0}
    for s in SN:
        P = np.asarray(s["p"], float)
        W = np.c_[P, np.ones(len(P))] @ M
        ok = inhull(W)
        C.up_clip["segs_total"] += len(W) - 1
        run, r = [], 0
        for j in range(len(W)):
            if ok[j]:
                run.append(W[j])
            if (not ok[j] or j == len(W) - 1) and len(run) >= 2:
                streets.append({"id": f"u:{s['n']}#{r}", "name": s["n"], "src": "upstream",
                                "built": s["y"], "destroyed": NEVER, "pts": np.array(run)})
                C.up_clip["segs_kept"] += len(run) - 1
                C.up_clip["kept_runs"] += 1
                r += 1
            if not ok[j]:
                run = []
    C.streets = streets
    SA, SB, sst = [], [], []
    C.street_segs = []
    for i, s in enumerate(streets):
        ids = []
        for a, b in zip(s["pts"][:-1], s["pts"][1:]):
            if math.hypot(*(b - a)) < 1e-6:
                continue
            ids.append(len(SA))
            SA.append(a)
            SB.append(b)
            sst.append(i)
        C.street_segs.append(ids)
    C.SA, C.SB = np.array(SA), np.array(SB)
    C.sst = np.array(sst)
    C.nseg = len(SA)
    C.sA = [tuple(map(float, a)) for a in C.SA]
    C.sB = [tuple(map(float, b)) for b in C.SB]
    # 端点（每条街首尾）
    C.ends = []
    for i, ids in enumerate(C.street_segs):
        if ids:
            C.ends.append((i, C.sA[ids[0]]))
            C.ends.append((i, C.sB[ids[-1]]))
    # ---- 设施候选门口点：沿用 v6 kind_pts；同一结构同一标签的点合并
    C.fac = {}                 # sidx -> [(label, [kinds], pts ndarray)]
    for k, pts in S.kind_pts.items():
        g = {}
        for kd, lb, q in pts:
            e = g.setdefault(lb, [[], []])
            if kd not in e[0]:
                e[0].append(kd)
            e[1].append(q)
        C.fac[k] = [(lb, kds, np.array(qs)) for lb, (kds, qs) in g.items()]
    # 去重同一标签下重复点（church_all 与 parish 共点）
    for k in C.fac:
        C.fac[k] = [(lb, kds, np.unique(q, axis=0)) for lb, kds, q in C.fac[k]]
    # ---- 静态 topK：房屋质心、街端点、设施点
    C.h_top, C.h_topd = _topk(C, S.xy)
    C.e_top, C.e_topd = _topk(C, np.array([p for _, p in C.ends]))
    fp = []
    C.fac_pt = {}
    for k in C.fac:
        for lb, kds, q in C.fac[k]:
            C.fac_pt[(k, lb)] = (len(fp), len(q))
            fp.extend(q)
    C.f_top, C.f_topd = _topk(C, np.array(fp))
    C.fpts = np.array(fp)
    # 街段 → 出现在其 topK 里的房屋（新开街时只查这些房屋）
    flat = C.h_top.ravel()
    order = np.argsort(flat, kind="stable")
    hs = (order // TOPK)
    cuts = np.searchsorted(flat[order], np.arange(C.nseg + 1))
    C.seg_inv_h = [hs[cuts[s]:cuts[s + 1]] for s in range(C.nseg)]
    C.h_rank = {}
    flat = C.e_top.ravel()
    order = np.argsort(flat, kind="stable")
    es = order // TOPK
    cuts = np.searchsorted(flat[order], np.arange(C.nseg + 1))
    C.seg_inv_e = [es[cuts[s]:cuts[s + 1]] for s in range(C.nseg)]
    # 房屋在每个街段上的左右侧（静态）
    C.street_of = {s["id"]: i for i, s in enumerate(streets)}
    return C


def _seg_dist_mat(C, P):
    A, B = C.SA[None], C.SB[None]
    ab = B - A
    L2 = (ab ** 2).sum(2)
    t = np.clip((((P[:, None, :] - A) * ab).sum(2)) / L2, 0, 1)
    return np.sqrt(((P[:, None, :] - A - t[..., None] * ab) ** 2).sum(2))


def _topk(C, P):
    out = np.empty((len(P), TOPK), np.int32)
    outd = np.empty((len(P), TOPK))
    for c in range(0, len(P), 512):
        D = _seg_dist_mat(C, P[c:c + 512])
        idx = np.argpartition(D, TOPK, axis=1)[:, :TOPK]
        dd = np.take_along_axis(D, idx, 1)
        o = np.lexsort((idx, dd), axis=1)
        out[c:c + 512] = np.take_along_axis(idx, o, 1)
        outd[c:c + 512] = np.take_along_axis(dd, o, 1)
    return out, outd


def proj(C, s, P):
    ax, ay = C.sA[s]
    bx, by = C.sB[s]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = ((P[0] - ax) * dx + (P[1] - ay) * dy) / L2
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    qx, qy = ax + t * dx, ay + t * dy
    return t, (qx, qy), math.hypot(P[0] - qx, P[1] - qy)


def tkey(C, s, k):
    """节点 k 在街段 s 上的参数（由量化坐标重算，保证增量与重建一致）。"""
    ax, ay = C.sA[s]
    bx, by = C.sB[s]
    dx, dy = bx - ax, by - ay
    return ((k[0] / Q - ax) * dx + (k[1] / Q - ay) * dy) / (dx * dx + dy * dy)


def nearest_seg(C, top, topd, i, segon, allP, exclude_street=None):
    """静态 topK 里第一个站着的街段；都不站着则对站着街段全扫。返回 (seg, rank)；rank=TOPK 表示回退。"""
    row = top[i]
    for r in range(TOPK):
        s = int(row[r])
        if s in segon and (exclude_street is None or C.sst[s] != exclude_street):
            return s, r
    cand = [s for s in segon if exclude_street is None or C.sst[s] != exclude_street]
    if not cand:
        return None, TOPK
    cand = np.array(sorted(cand))
    D = _seg_dist_mat_sub(C, allP[i:i + 1], cand)[0]
    o = np.lexsort((cand, D))
    return int(cand[o[0]]), TOPK


def _seg_dist_mat_sub(C, P, segs):
    A, B = C.SA[segs][None], C.SB[segs][None]
    ab = B - A
    L2 = (ab ** 2).sum(2)
    t = np.clip((((P[:, None, :] - A) * ab).sum(2)) / L2, 0, 1)
    return np.sqrt(((P[:, None, :] - A - t[..., None] * ab) ** 2).sum(2))


def inter(C, i, j):
    """街段 i、j 的交点 → (key, ti, tj) 或 None。i<j 规范顺序。"""
    if i > j:
        return inter(C, j, i)
    ax, ay = C.sA[i]
    bx, by = C.sB[i]
    cx, cy = C.sA[j]
    dx, dy = C.sB[j]
    rx, ry, sx, sy = bx - ax, by - ay, dx - cx, dy - cy
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    qx, qy = cx - ax, cy - ay
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    E = 1e-9
    if t < -E or t > 1 + E or u < -E or u > 1 + E:
        return None
    if t <= 1e-6:
        k = key_of(ax, ay)
    elif t >= 1 - 1e-6:
        k = key_of(bx, by)
    elif u <= 1e-6:
        k = key_of(cx, cy)
    elif u >= 1 - 1e-6:
        k = key_of(dx, dy)
    else:
        k = key_of(ax + t * rx, ay + t * ry)
    return k


# ================================================================ 状态
class State:
    pass


def _new_state(C, Y):
    st = State()
    st.C, st.S, st.Y = C, C.S, Y
    N = len(C.S.hid)
    st.segon = set()
    st.streets_on = set()
    st.splits = {}            # s -> {key: set(owner)}
    st.inter = {}             # s -> {j: key}
    st.snap = {}              # end idx -> (target seg, key)
    st.doors = {}             # (sidx,label) -> (seg, key, acc)
    st.oedges = {}            # owner -> {(u,v): w}
    st.adj = {}               # node -> {nbr: {owner: w}}
    st.node_segs = {}         # node -> set(seg)
    st.seg_keys = {}          # s -> sorted [(t, key)]
    st.seg_ts = {}
    st.hhe = {}
    st.seeds = {kd: {} for kd in KINDS}      # node -> {lab: d0}
    st.sp = {kd: ({}, {}, {}) for kd in KINDS}   # dist, lab, par
    st.sset = set()
    # 房屋
    st.alive = np.zeros(N, bool)
    st.hdoor = {}             # h -> (seg, rank, t, P, acc, side)
    st.seg_h = {}             # seg -> set(h)
    st.dist = {k: np.full(N, INF) for k in KINDS}
    st.labi = {k: np.full(N, -1, dtype=np.int32) for k in KINDS}
    st.fang = [None] * N
    st.he_fang = {}
    st.rec, st.members, st.holder, st.office = {}, {}, {}, {}
    st.cand, st.recomp, st.queued, st.heap = {}, set(), set(), []
    st.tie = {k: np.zeros(N, bool) for k in KINDS}   # v6 接口占位
    return st


# ---------------------------------------------------------------- 拓扑：分割点与边
def _add_split(st, s, k, owner):
    d = st.splits[s]
    o = d.get(k)
    if o is None:
        d[k] = {owner}
        st.node_segs.setdefault(k, set()).add(s)
    else:
        o.add(owner)


def _del_split(st, s, k, owner):
    d = st.splits.get(s)
    if d is None or k not in d:
        return
    d[k].discard(owner)
    if not d[k]:
        del d[k]
        ns = st.node_segs[k]
        ns.discard(s)
        if not ns:
            del st.node_segs[k]


def _seg_edges(st, s):
    C = st.C
    ks = sorted((tkey(C, s, k), k) for k in st.splits[s])
    st.seg_keys[s] = ks
    st.seg_ts[s] = [x[0] for x in ks]
    out = {}
    for (_, a), (_, b) in zip(ks[:-1], ks[1:]):
        if a != b:
            u, v = (a, b) if a < b else (b, a)
            out[(u, v)] = math.hypot((a[0] - b[0]) / Q, (a[1] - b[1]) / Q)
    return out


def _set_owner(st, owner, new, changed):
    old = st.oedges.get(owner, {})
    adj = st.adj
    for p, w in old.items():
        if new.get(p) != w:
            u, v = p
            for x, y in ((u, v), (v, u)):
                e = adj[x][y]
                del e[owner]
                if not e:
                    del adj[x][y]
                    if not adj[x]:
                        del adj[x]
            changed.add(p)
    for p, w in new.items():
        if old.get(p) != w:
            u, v = p
            for x, y in ((u, v), (v, u)):
                adj.setdefault(x, {}).setdefault(y, {})[owner] = w
            changed.add(p)
    if new:
        st.oedges[owner] = new
    else:
        st.oedges.pop(owner, None)


def _ew(st, u, v):
    e = st.adj.get(u, {}).get(v)
    return min(e.values()) if e else None


# ---------------------------------------------------------------- 最短路
def _sssp_full(st, kd):
    dist, lab, par = {}, {}, {}
    heap = []
    for x, sd in st.seeds[kd].items():
        lb = min(sd, key=lambda l: (sd[l], l))
        heap.append((sd[lb], lb, x, None))
    heapq.heapify(heap)
    adj = st.adj
    while heap:
        d, l, x, p = heapq.heappop(heap)
        if x in dist:
            continue
        dist[x], lab[x], par[x] = d, l, p
        for y, e in adj.get(x, {}).items():
            if y not in dist:
                heapq.heappush(heap, (d + min(e.values()), l, y, x))
    st.sp[kd] = (dist, lab, par)


def _better(d, l, dist, lab, y):
    od = dist.get(y)
    return od is None or d < od or (d == od and l < lab[y])


def _sssp_update(st, kd, pairs, seednodes):
    """动态最短路：删边/删源 → 重置受影响子树；加边/加源 → 只做递减松弛。返回键变化的节点集。"""
    dist, lab, par = st.sp[kd]
    adj = st.adj
    seeds = st.seeds[kd]
    roots = []
    for (u, v) in pairs:
        if par.get(v) == u:
            roots.append(v)
        if par.get(u) == v:
            roots.append(u)
    for x in seednodes:
        if x in dist and par.get(x) is None:
            roots.append(x)
    aff = set()
    stack = roots
    while stack:
        x = stack.pop()
        if x in aff or x not in dist:
            continue
        aff.add(x)
        for y in adj.get(x, ()):
            if par.get(y) == x:
                stack.append(y)
        for (u, v) in pairs:        # 已删边的孩子
            pass
    # 也要沿已删除的边找孩子：pairs 里的 root 已经覆盖
    old = {x: (dist[x], lab[x]) for x in aff}
    for x in aff:
        del dist[x], lab[x], par[x]
    heap = []

    def offer(x):
        sd = seeds.get(x)
        if sd:
            lb = min(sd, key=lambda l: (sd[l], l))
            heap.append((sd[lb], lb, x, None))
        for y, e in adj.get(x, {}).items():
            if y in dist:
                heap.append((dist[y] + min(e.values()), lab[y], x, y))
    for x in aff:
        offer(x)
    for (u, v) in pairs:
        w = _ew(st, u, v)
        if w is not None:
            if u in dist:
                heap.append((dist[u] + w, lab[u], v, u))
            if v in dist:
                heap.append((dist[v] + w, lab[v], u, v))
    for x in seednodes:
        sd = seeds.get(x)
        if sd:
            lb = min(sd, key=lambda l: (sd[l], l))
            heap.append((sd[lb], lb, x, None))
    # 消失的节点
    changed = set(aff)
    for x in list(dist):
        pass
    heapq.heapify(heap)
    while heap:
        d, l, x, p = heapq.heappop(heap)
        if x not in adj and x not in seeds:
            continue
        if not _better(d, l, dist, lab, x):
            continue
        if p is not None and p not in dist:
            continue
        if x not in old and x in dist:
            old[x] = (dist[x], lab[x])
        dist[x], lab[x], par[x] = d, l, p
        changed.add(x)
        for y, e in adj.get(x, {}).items():
            nd = d + min(e.values())
            if _better(nd, l, dist, lab, y):
                heapq.heappush(heap, (nd, l, y, x))
    # 不在图里的残留
    for x in [x for x in changed if x in dist and x not in adj and x not in seeds]:
        del dist[x], lab[x], par[x]
    out = {}
    for x in changed:
        o = old.get(x)
        n = (dist[x], lab[x]) if x in dist else None
        if o != n:
            out[x] = o
    return out


# ---------------------------------------------------------------- 门口（设施、房屋、吸附）
def _fac_door(st, k, lb):
    C = st.C
    i0, n = C.fac_pt[(k, lb)]
    best = None
    for i in range(i0, i0 + n):
        s, r = nearest_seg(C, C.f_top, C.f_topd, i, st.segon, C.fpts)
        if s is None:
            continue
        t, P, acc = proj(C, s, C.fpts[i])
        c = (acc, s, i)
        if best is None or c < best[0]:
            best = (c, s, key_of(*P), acc)
    return None if best is None else (best[1], best[2], best[3])


def _end_snap(st, e):
    C = st.C
    si, P = C.ends[e]
    s, r = nearest_seg(C, C.e_top, C.e_topd, e, st.segon, r_all(C), exclude_street=si)
    if s is None:
        return None
    t, Pp, d = proj(C, s, P)
    if d <= 1e-6 or d > SNAP_MAX:
        return None
    kp = key_of(*Pp)
    ke = key_of(*P)
    if kp == ke:
        return None
    return (s, kp, ke)


def r_all(C):
    if not hasattr(C, "_endP"):
        C._endP = np.array([p for _, p in C.ends])
    return C._endP


def _house_door(st, h):
    C = st.C
    s, r = nearest_seg(C, C.h_top, C.h_topd, h, st.segon, C.S.xy)
    if s is None:
        return None
    P0 = C.S.xy[h]
    t, P, acc = proj(C, s, P0)
    ax, ay = C.sA[s]
    bx, by = C.sB[s]
    side = (bx - ax) * (P0[1] - ay) - (by - ay) * (P0[0] - ax)
    return (s, r, t, P, acc, side >= 0)


def _bracket(st, s, t):
    """门口两侧的节点 a、b（门口恰在节点上则 a==b），以及门口所在的那条边 (ea, eb)。"""
    ks = st.seg_keys[s]
    ts = st.seg_ts[s]
    i = bisect.bisect_right(ts, t)
    j = bisect.bisect_left(ts, t)
    a = ks[i - 1][1] if i > 0 else ks[0][1]
    b = ks[j][1] if j < len(ks) else ks[-1][1]
    ia = min(max(i - 1, 0), len(ks) - 2)
    return a, b, ks[ia][1], ks[ia + 1][1]


def _house_eval(st, h, kinds=KINDS):
    """由门口与街网节点键得到 (各类 dist/lab, 半边)。"""
    dr = st.hdoor.get(h)
    out = {}
    if dr is None:
        for kd in KINDS:
            out[kd] = (INF, -1)
        return out, None
    s, r, t, P, acc, left = dr
    a, b, ea, eb = _bracket(st, s, t)
    for kd in kinds:
        dist, lab, _ = st.sp[kd]
        best = (INF, -1)
        for x in (a, b):
            if x in dist:
                c = ((dist[x] + kdist(x, P)) + acc, lab[x])
                if c < best:
                    best = c
        out[kd] = best
    # 规范方向：沿街段 A→B 为 ea→eb；房屋在左则半边 ea→eb，否则 eb→ea
    he = (ea, eb) if left else (eb, ea)
    return out, he


# ---------------------------------------------------------------- 坊：平面图的面（可局部更新）
def _rot(st, v):
    vx, vy = v
    o = sorted(st.adj[v], key=lambda u: (math.atan2(u[1] - vy, u[0] - vx), u))
    st.rot[v] = o
    st.rpos[v] = {u: i for i, u in enumerate(o)}


def _trace(st, u, v):
    cyc = []
    x, y = u, v
    while True:
        cyc.append((x, y))
        o = st.rot[y]
        x, y = y, o[st.rpos[y][x] - 1]
        if (x, y) == (u, v):
            return cyc


def _add_face(st, cyc):
    fid = min(cyc)
    L = 0.0
    for e in cyc:
        st.he_face[e] = fid
        L += _ew(st, *e)
    st.faces[fid] = (cyc, L)
    return fid


def _link(st, fid):
    """过小的面并入共边最长的邻面（同长取面 id 小者）；返回目标或 None。"""
    cyc, L = st.faces[fid]
    if L >= F_MIN:
        return None
    share = {}
    for a, b in cyc:
        g = st.he_face.get((b, a))
        if g is not None and g != fid:
            share[g] = share.get(g, 0.0) + _ew(st, a, b)
    if not share:
        return None
    return min(share, key=lambda x: (-share[x], x))


def _set_link(st, f, g):
    old = st.link.get(f)
    if old == g:
        return
    if old is not None:
        st.linked_by[old].discard(f)
    if g is None:
        st.link.pop(f, None)
    else:
        st.link[f] = g
        st.linked_by.setdefault(g, set()).add(f)


def _group_names(st, members, out):
    seq = []
    for fid in sorted(members):
        cyc = st.faces[fid][0]
        i0 = cyc.index(fid)
        seq.extend(cyc[i0:] + cyc[:i0])
    pieces = []
    for e in seq:
        L = _ew(st, *e)
        n = max(1, int(math.ceil(L / F_MAX)))
        for j in range(n):
            pieces.append((e, j, n, L / n))
    tot = sum(p[3] for p in pieces)
    nchunk = max(1, int(math.ceil(tot / F_MAX)))
    target = tot / nchunk
    chunks, cur, acc = [], [], 0.0
    for p in pieces:
        if cur and acc + p[3] / 2 > target and len(chunks) < nchunk - 1:
            chunks.append(cur)
            cur, acc = [], 0.0
        cur.append(p)
        acc += p[3]
    chunks.append(cur)
    names = {}
    for c in chunks:
        e0, j0 = min((p[0], p[1]) for p in c)
        name = f"坊@{e0[0][0] / Q:.2f},{e0[0][1] / Q:.2f}>{e0[1][0] / Q:.2f},{e0[1][1] / Q:.2f}.{j0}"
        for e, j, n, _ in c:
            names.setdefault(e, [None] * n)[j] = name
    for e, v in names.items():
        out[e] = tuple(v)


def _component(st, seeds):
    comp, stack = set(), list(seeds)
    while stack:
        f = stack.pop()
        if f in comp or f not in st.faces:
            continue
        comp.add(f)
        g = st.link.get(f)
        if g is not None:
            stack.append(g)
        stack.extend(st.linked_by.get(f, ()))
    return comp


def _regroup(st, seeds):
    """重算 seeds 所在合并组的坊名；返回名字变了的半边集。"""
    done, changed = set(), set()
    for f in sorted(seeds):
        if f in done or f not in st.faces:
            continue
        comp = _component(st, [f])
        done |= comp
        out = {}
        _group_names(st, comp, out)
        for e, v in out.items():
            if st.he_fang.get(e) != v:
                st.he_fang[e] = v
                changed.add(e)
    return changed


def _faces_full(st):
    st.rot, st.rpos, st.he_face, st.faces, st.link, st.linked_by, st.he_fang = {}, {}, {}, {}, {}, {}, {}
    for v in st.adj:
        _rot(st, v)
    for u in sorted(st.adj):
        for v in st.rot[u]:
            if (u, v) not in st.he_face:
                _add_face(st, _trace(st, u, v))
    for fid in st.faces:
        _set_link(st, fid, _link(st, fid))
    _regroup(st, set(st.faces))


def _faces_local(st, nodes):
    """nodes = 邻接关系变了的节点。只拆掉经过这些节点的面、重新描出新面，再重算受影响的合并组。"""
    dead = set()
    for v in nodes:
        for u in st.rot.get(v, ()):
            for e in ((v, u), (u, v)):
                f = st.he_face.get(e)
                if f is not None:
                    dead.add(f)
    regroup = set()
    old_he = set()
    for f in dead:
        regroup |= _component(st, [f])
    for f in dead:
        cyc, _ = st.faces.pop(f)
        for e in cyc:
            if st.he_face.get(e) == f:
                del st.he_face[e]
            old_he.add(e)
        _set_link(st, f, None)
        for g in list(st.linked_by.pop(f, ())):
            st.link.pop(g, None)
            regroup.add(g)
    regroup -= dead
    for v in nodes:
        if v in st.adj:
            _rot(st, v)
        else:
            st.rot.pop(v, None)
            st.rpos.pop(v, None)
    newf = set()
    starts = set()
    for v in nodes:
        for u in st.rot.get(v, ()):
            starts.add((v, u))
            starts.add((u, v))
    for e in old_he:
        if e[0] in st.adj and e[1] in st.adj.get(e[0], {}):
            starts.add(e)
    for e in sorted(starts):
        if e not in st.he_face:
            newf.add(_add_face(st, _trace(st, *e)))
    # 重新定合并指向：新面、新面的邻面
    relink = set(newf)
    for f in newf:
        for a, b in st.faces[f][0]:
            g = st.he_face.get((b, a))
            if g is not None:
                relink.add(g)
    relink |= {g for g in regroup if g in st.faces}
    seeds = set(relink)
    for f in relink:
        seeds |= _component(st, [f])        # 旧组
        _set_link(st, f, _link(st, f))
    seeds |= regroup
    changed = set()
    for e in old_he:
        if e not in st.he_face and e in st.he_fang:
            del st.he_fang[e]
            changed.add(e)
    changed |= _regroup(st, seeds)
    return changed


def fang_of_door(st, he, P):
    v = st.he_fang.get(he)
    if v is None:
        return None
    if len(v) == 1:
        return v[0]
    L = _ew(st, *he)
    j = int(kdist(he[0], P) / (L / len(v)))
    return v[min(max(j, 0), len(v) - 1)]


# ================================================================ 生成
def street_ids_for(C, Y):
    return {i for i, s in enumerate(C.streets) if s["built"] <= Y < s["destroyed"]}


def build(C, Y, streets=None, sset=None):
    S = C.S
    st = _new_state(C, Y)
    st.streets_on = set(streets) if streets is not None else street_ids_for(C, Y)
    st.sset = set(sset) if sset is not None else {k for k, s in enumerate(S.structs) if cs6.standing(s, Y)}
    for si in st.streets_on:
        for s in C.street_segs[si]:
            st.segon.add(s)
    segs = np.array(sorted(st.segon))
    for s in segs.tolist():
        st.splits[s] = {}
        st.inter[s] = {}
        _add_split(st, s, key_of(*C.sA[s]), "end")
        _add_split(st, s, key_of(*C.sB[s]), "end")
    # 全部交点：包围盒初筛（向量化）→ 精算
    if len(segs):
        A, B = C.SA[segs], C.SB[segs]
        lo, hi = np.minimum(A, B) - 1e-6, np.maximum(A, B) + 1e-6
        for ii in range(len(segs)):
            m = (lo[ii + 1:, 0] <= hi[ii, 0]) & (hi[ii + 1:, 0] >= lo[ii, 0]) & \
                (lo[ii + 1:, 1] <= hi[ii, 1]) & (hi[ii + 1:, 1] >= lo[ii, 1])
            i = int(segs[ii])
            for jj in np.nonzero(m)[0].tolist():
                j = int(segs[ii + 1 + jj])
                k = inter(C, i, j)
                if k is not None:
                    st.inter[i][j] = k
                    st.inter[j][i] = k
                    _add_split(st, i, k, ("x", j))
                    _add_split(st, j, k, ("x", i))
    # 端点吸附
    r_all(C)
    for e, (si, P) in enumerate(C.ends):
        if si in st.streets_on:
            sn = _end_snap(st, e)
            if sn:
                st.snap[e] = sn
                _add_split(st, sn[0], sn[1], ("snap", e))
    # 设施门口
    for k in sorted(st.sset):
        for lb, kds, _ in C.fac.get(k, []):
            dr = _fac_door(st, k, lb)
            if dr:
                st.doors[(k, lb)] = dr
                _add_split(st, dr[0], dr[1], ("door", k, lb))
                for kd in kds:
                    st.seeds[kd].setdefault(dr[1], {})[S.lab_id[kd][lb]] = dr[2]
    ch = set()
    for s in segs.tolist():
        _set_owner(st, ("seg", s), _seg_edges(st, s), ch)
    for e, (s, kp, ke) in st.snap.items():
        u, v = (kp, ke) if kp < ke else (ke, kp)
        _set_owner(st, ("snap", e), {(u, v): math.hypot((u[0] - v[0]) / Q, (u[1] - v[1]) / Q)}, ch)
    for kd in KINDS:
        _sssp_full(st, kd)
    _faces_full(st)
    # 房屋
    alive = np.nonzero((S.built <= Y) & (S.destroyed > Y))[0]
    st.alive[alive] = True
    for h in alive.tolist():
        _house_attach(st, h)
    order = alive[np.argsort(S.seniority[alive], kind="stable")].tolist()
    keys = {}
    for h in order:
        st.rec[h] = None
        ks = _node_keys(st, h)
        keys[h] = {k[0]: k for k in ks}
        for k in ks:
            m = st.members.get(k)
            if m is None:
                st.members[k] = {h}
                st.holder[k] = None
            else:
                m.add(h)
    office, holder = st.office, st.holder
    for tag in cs6.TAGS:
        for h in order:
            if h in office:
                continue
            k = keys[h].get(tag)
            if k is not None and holder[k] is None:
                holder[k] = h
                office[h] = k
    return st


def _house_attach(st, h):
    dr = _house_door(st, h)
    if dr is None:
        st.hdoor.pop(h, None)
    else:
        st.hdoor[h] = dr
        st.seg_h.setdefault(dr[0], set()).add(h)
    _house_set(st, h)


def _house_set(st, h):
    ev, he = _house_eval(st, h)
    for kd in KINDS:
        st.labi[kd][h] = ev[kd][1]
    st.hhe[h] = he
    dr = st.hdoor.get(h)
    if he is None:
        st.fang[h] = None
        return
    base = fang_of_door(st, he, dr[3])
    s, r, t, P, acc, left = dr
    band = int(acc // F_DEPTH)
    tag = base if band == 0 else f"{base}|深{band}"
    if (t <= 0.0 or t >= 1.0) and acc > 1e-9:
        H = st.C.S.xy[h]
        sec = int(((math.atan2(H[1] - P[1], H[0] - P[0]) + math.pi) / (2 * math.pi)) * F_SECTOR) % F_SECTOR
        tag = f"{tag}|角{sec}"
    st.fang[h] = tag


_node_keys_v6 = cs6._node_keys


def _node_keys(st, h):
    if not hasattr(st, "he_fang"):          # v6 的状态（对比用）走 v6 原函数
        return _node_keys_v6(st, h)
    S = st.S
    ks = [("区", S.d[h])]
    if st.fang[h] is not None:
        ks.append(("坊", st.fang[h]))
    for tag, kd in cs6.NODE_KIND:
        i = st.labi[kd][h]
        if i >= 0 and (tag != "阿" or S.is_arian[i]):
            ks.append((tag, S.lab_names[kd][i]))
    g = S.guild[h]
    if g is not None:
        ks.append(("行", f"{S.d[h]}×{g}"))
    return ks


cs6._node_keys = _node_keys          # v6 的一户一职维护函数改用 v7 的节点键


# ================================================================ 增量
def _topo_change(st, add_streets=(), del_streets=(), add_structs=(), del_structs=()):
    """街道/设施变动：只改动受影响街段的分割点与边、受影响的吸附与门口，然后对每类设施局部重跑最短路。"""
    C, S = st.C, st.S
    touched = set()
    new_segs, gone_segs = [], []
    for si in del_streets:
        st.streets_on.discard(si)
        for s in C.street_segs[si]:
            gone_segs.append(s)
    for s in gone_segs:
        st.segon.discard(s)
        for j, k in st.inter.pop(s, {}).items():
            st.inter[j].pop(s, None)
            _del_split(st, j, k, ("x", s))
            touched.add(j)
        for k, ow in list(st.splits[s].items()):
            for o in list(ow):
                _del_split(st, s, k, o)
        del st.splits[s]
        st.seg_keys.pop(s, None)
        st.seg_ts.pop(s, None)
    for si in add_streets:
        st.streets_on.add(si)
        new_segs.extend(C.street_segs[si])
    for s in new_segs:
        st.segon.add(s)
        st.splits[s] = {}
        st.inter[s] = {}
        _add_split(st, s, key_of(*C.sA[s]), "end")
        _add_split(st, s, key_of(*C.sB[s]), "end")
        touched.add(s)
    if new_segs:
        on = np.array(sorted(st.segon))
        A, B = C.SA[on], C.SB[on]
        lo, hi = np.minimum(A, B) - 1e-6, np.maximum(A, B) + 1e-6
        nset = set(new_segs)
        for s in new_segs:
            a, b = C.SA[s], C.SB[s]
            l2, h2 = np.minimum(a, b) - 1e-6, np.maximum(a, b) + 1e-6
            m = (lo[:, 0] <= h2[0]) & (hi[:, 0] >= l2[0]) & (lo[:, 1] <= h2[1]) & (hi[:, 1] >= l2[1])
            for j in on[m].tolist():
                if j == s or (j in nset and j < s) or j in st.inter[s]:
                    continue
                k = inter(C, s, j)
                if k is not None:
                    st.inter[s][j] = k
                    st.inter[j][s] = k
                    _add_split(st, s, k, ("x", j))
                    _add_split(st, j, k, ("x", s))
                    touched.add(j)
    chseg = set(new_segs) | set(gone_segs)
    # 吸附：街网一变，所有站着街的端点重算（端点只有数百个，确保与重建同一规则）
    ends = set(range(len(C.ends))) if chseg else set()
    snap_ch = set()
    for e in sorted(ends):
        old = st.snap.get(e)
        new = _end_snap(st, e) if C.ends[e][0] in st.streets_on else None
        if old != new:
            if old:
                _del_split(st, old[0], old[1], ("snap", e))
                touched.add(old[0])
            if new:
                _add_split(st, new[0], new[1], ("snap", e))
                touched.add(new[0])
                st.snap[e] = new
            else:
                st.snap.pop(e, None)
            snap_ch.add(e)
    # 设施门口：增删的结构 + 街网变了则全部站着设施重算（设施只有数十个）
    for k in del_structs:
        st.sset.discard(k)
    for k in add_structs:
        st.sset.add(k)
    fk = set(add_structs) | set(del_structs)
    if chseg:
        fk |= set(st.sset)
    seed_nodes = {kd: set() for kd in KINDS}
    for k in sorted(fk):
        for lb, kds, _ in C.fac.get(k, []):
            old = st.doors.get((k, lb))
            new = _fac_door(st, k, lb) if k in st.sset else None
            if old == new:
                continue
            if old:
                _del_split(st, old[0], old[1], ("door", k, lb))
                touched.add(old[0])
                for kd in kds:
                    sd = st.seeds[kd][old[1]]
                    del sd[S.lab_id[kd][lb]]
                    if not sd:
                        del st.seeds[kd][old[1]]
                    seed_nodes[kd].add(old[1])
                del st.doors[(k, lb)]
            if new:
                st.doors[(k, lb)] = new
                _add_split(st, new[0], new[1], ("door", k, lb))
                touched.add(new[0])
                for kd in kds:
                    st.seeds[kd].setdefault(new[1], {})[S.lab_id[kd][lb]] = new[2]
                    seed_nodes[kd].add(new[1])
    # 边
    pairs = set()
    touched -= set(gone_segs)
    for s in gone_segs:
        _set_owner(st, ("seg", s), {}, pairs)
    for s in sorted(touched):
        _set_owner(st, ("seg", s), _seg_edges(st, s), pairs)
    for e in snap_ch:
        sn = st.snap.get(e)
        if sn:
            s, kp, ke = sn
            u, v = (kp, ke) if kp < ke else (ke, kp)
            _set_owner(st, ("snap", e), {(u, v): math.hypot((u[0] - v[0]) / Q, (u[1] - v[1]) / Q)}, pairs)
        else:
            _set_owner(st, ("snap", e), {}, pairs)
    # 最短路局部更新
    chn = {}
    for kd in KINDS:
        if pairs or seed_nodes[kd]:
            for x, o in _sssp_update(st, kd, pairs, seed_nodes[kd]).items():
                chn.setdefault(x, {})[kd] = o
    # 坊（面）：只重描邻接变了的节点上的面
    chhe = set()
    if pairs:
        nodes = {x for p in pairs for x in p}
        chhe = _faces_local(st, nodes)
    # 待重评的房屋：门口街段的分割变了；街段上某节点的「设施标签」变了，或节点距离变了而该段节点标签不一。
    H = set()
    for s in touched | chseg:
        H |= st.seg_h.get(s, set())
    Hk = {}                           # 只需重算部分设施类的房屋
    for x, kds in chn.items():
        for s in st.node_segs.get(x, ()):
            if s in touched or not st.seg_h.get(s):
                continue
            for kd, o in kds.items():
                dist, lab, _ = st.sp[kd]
                nl = lab.get(x, -1)
                if o is None or o[1] != nl or any(lab.get(k, -1) != nl for _, k in st.seg_keys[s]):
                    for h in st.seg_h[s]:
                        Hk.setdefault(h, set()).add(kd)
    for (a, b) in chhe:
        for s in st.node_segs.get(a, ()):
            if b in st.splits.get(s, {}):
                H |= st.seg_h.get(s, set())
    redoor = set()
    for s in chseg:
        for h in C.seg_inv_h[s].tolist():
            if st.alive[h]:
                redoor.add(h)
    for s in gone_segs:
        redoor |= st.seg_h.pop(s, set())
    if chseg:
        redoor |= {h for h, d in st.hdoor.items() if d[1] == TOPK}
        if len(st.hdoor) < len(st.rec):
            redoor |= {h for h in st.rec if h not in st.hdoor}
    H |= redoor
    H = {h for h in H if st.alive[h]}
    for h in H:
        Hk.pop(h, None)
    moves = 0
    lid = {kd: st.labi[kd] for kd in KINDS}
    for h, kds in Hk.items():          # 只改标签：先比标签，没变就不碰节点
        ev = _house_eval(st, h, kds)[0]
        if all(lid[kd][h] == ev[kd][1] for kd in kds):
            continue
        oldk = set(_node_keys(st, h))
        for kd in kds:
            lid[kd][h] = ev[kd][1]
        newk = set(_node_keys(st, h))
        if oldk != newk:
            moves += 1
            for k in oldk - newk:
                cs6._remove_member(st, k, h)
            for k in newk - oldk:
                cs6._add_member(st, k, h)
    for h in sorted(H):
        oldk = set(_node_keys(st, h)) if h in st.rec else None
        if h in redoor:
            od = st.hdoor.get(h)
            if od is not None:
                st.seg_h.get(od[0], set()).discard(h)
            _house_attach(st, h)
        else:
            _house_set(st, h)
        if oldk is None:
            continue
        newk = set(_node_keys(st, h))
        if oldk != newk:
            moves += 1
            for k in oldk - newk:
                cs6._remove_member(st, k, h)
            for k in newk - oldk:
                cs6._add_member(st, k, h)
    cs6._settle(st)
    return moves


def apply(st, ev):
    kind, arg = ev
    if kind == "build":
        for h in arg:
            if h in st.rec:
                continue
            st.alive[h] = True
            _house_attach(st, h)
            st.rec[h] = None
            for k in _node_keys(st, h):
                cs6._add_member(st, k, h)
        cs6._settle(st)
        return 0
    if kind == "destroy":
        for h in arg:
            if h in st.rec:
                ks = _node_keys(st, h)
                del st.rec[h]
                st.alive[h] = False
                d = st.hdoor.pop(h, None)
                if d is not None:
                    st.seg_h[d[0]].discard(h)
                for k in ks:
                    cs6._remove_member(st, k, h)
        cs6._settle(st)
        return 0
    if kind == "struct_add":
        if not st.C.fac.get(arg):
            st.sset.add(arg)
            return 0
        return _topo_change(st, add_structs=[arg])
    if kind == "struct_remove":
        if not st.C.fac.get(arg):
            st.sset.discard(arg)
            return 0
        return _topo_change(st, del_structs=[arg])
    if kind == "street_add":
        return _topo_change(st, add_streets=[arg])
    if kind == "street_remove":
        return _topo_change(st, del_streets=[arg])
    raise ValueError(kind)


def materialize(st):
    S, C = st.S, st.C
    n = len(st.rec)
    cap = cs6.food_cap(st.Y)
    ration = cap / n if n else 0.0
    nm = S.lab_names
    recs = {}

    def lab(kd, h):
        i = st.labi[kd][h]
        return None if i < 0 else nm[kd][i]
    evs = {h: _house_eval(st, h)[0] for h in st.rec}     # 距离按需由门口+节点键算出（不常驻）
    for h in st.rec:
        a = lab("church_all", h)
        dr = st.hdoor.get(h)
        recs[S.hid[h]] = (S.d[h], st.fang[h], lab("water", h), lab("parish", h), a if a in cs6.ARIAN else None,
                          lab("watch", h), lab("grain", h), ration, S.guild[h],
                          None if dr is None else C.streets[C.sst[dr[0]]]["id"],
                          *(float(evs[h][kd][0]) for kd in DKINDS))
    nodes = {f"{k[0]}:{k[1]}": (cs6.NODE_TITLE[k[0]], None if st.holder[k] is None else S.hid[st.holder[k]], len(m))
             for k, m in st.members.items()}
    return recs, nodes


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


def events_for_year(C, Y):
    S = C.S
    evs = []
    for k, s in enumerate(S.structs):
        if s["type"] == "road":
            continue
        if s["destroyed"] == Y:
            evs.append(("struct_remove", k))
        if s["built"] == Y:
            evs.append(("struct_add", k))
    for i, s in enumerate(C.streets):
        if s["destroyed"] == Y:
            evs.append(("street_remove", i))
        if s["built"] == Y:
            evs.append(("street_add", i))
    for h in np.nonzero(S.built == Y)[0].tolist():
        evs.append(("build", [h]))
    dl = np.nonzero(S.destroyed == Y)[0].tolist()
    if dl:
        evs.append(("destroy", dl))
    return evs


# ================================================================ 验证与报告
def _stat(v):
    if not v:
        return None
    a = np.array(v) * 1000
    return {"n": len(a), "median_ms": round(float(np.median(a)), 3), "p90_ms": round(float(np.percentile(a, 90)), 3),
            "max_ms": round(float(a.max()), 3)}


def _ok(e):
    return e[0] == 0 and not any(e[1].values()) and e[2] == 0


def stage_incr(C, world):
    """AF41–70：AF40 重建后逐事件增量，每年与重建逐字段比对；记录耗时与改归属户数。"""
    S = C.S
    st = build(C, 40)
    times, per_ev, yearly, all_ok = {}, [], [], True
    for Y in range(41, 71):
        st.Y = Y
        evs = events_for_year(C, Y)
        for ev in evs:
            t0 = time.perf_counter()
            r = apply(st, ev)
            dt = time.perf_counter() - t0
            kd = ev[0]
            if kd == "struct_add" and not C.fac.get(ev[1]):
                kd = "struct_add_nonfacility"
            times.setdefault(kd, []).append(dt)
            if ev[0].startswith(("struct", "street")) and kd != "struct_add_nonfacility":
                name = S.structs[ev[1]]["id"] if ev[0].startswith("struct") else C.streets[ev[1]]["id"]
                per_ev.append({"Y": Y, "ev": ev[0], "id": name, "ms": round(dt * 1000, 2), "households_moved": r})
        t0 = time.perf_counter()
        ref_st = build(C, Y)
        tb = time.perf_counter() - t0
        inc, ref = materialize(st), materialize(ref_st)
        miss, bad, nbad = diff(inc, ref)
        ok = miss == 0 and not any(bad.values()) and nbad == 0
        all_ok &= ok
        recs, nodes = inc
        n = len(recs)
        ledger_n = int(sum(1 for h in world["houses"] if cs6.standing(h, Y)))
        rsum = sum(v[7] for v in recs.values())
        cnt = {}
        for t, hid, c in nodes.values():
            if hid is not None:
                cnt[hid] = cnt.get(hid, 0) + 1
        yearly.append({"Y": Y, "events": len(evs), "built": int((S.built == Y).sum()), "destroyed": int((S.destroyed == Y).sum()),
                       "streets_added": [C.streets[e[1]]["id"] for e in evs if e[0] == "street_add"],
                       "structs": [S.structs[e[1]]["id"] + ("+" if e[0] == "struct_add" else "-") for e in evs if e[0].startswith("struct")],
                       "houses": n, "ledger_houses": ledger_n, "bread_books": n, "pop": n * cs6.POP_PER_HOUSE,
                       "food_cap": cs6.food_cap(Y), "ration": round(cs6.food_cap(Y) / n, 4), "ration_sum_err": abs(rsum - cs6.food_cap(Y)),
                       "multi_office_households": sum(1 for v in cnt.values() if v > 1), "nodes": len(nodes),
                       "rebuild_s": round(tb, 3), "incr_eq_full": ok, "missing": miss,
                       "field_mismatch": {k: v for k, v in bad.items() if v}, "node_mismatch": nbad})
        print(Y, n, ledger_n, len(evs), "OK" if ok else f"FAIL {miss} {bad} {nbad}", flush=True)
    return {"all_years_equal": bool(all_ok), "times": {k: _stat(v) for k, v in times.items()},
            "topology_events": per_ev, "yearly": yearly}


def stage_rt(C, world, which):
    """往返：AF70 拆掉一条街/一个设施 → 与「不含它」重建比对；再建回 → 与原年重建比对（账本 AF41–70 无拆街事件，故合成）。"""
    Y = 70
    st = build(C, Y)
    full = materialize(build(C, Y))
    out = {"n": 0, "all_equal": True, "remove_ms": [], "add_ms": [], "items": []}
    if which == "street":
        items = sorted({i for i in st.streets_on if C.streets[i]["built"] >= 41} |
                       {i for i in st.streets_on if C.streets[i]["src"] == "ledger"})
    else:
        items = sorted(k for k in st.sset if C.fac.get(k))
    for it in items:
        if which == "street":
            t0 = time.perf_counter(); r1 = apply(st, ("street_remove", it)); d1 = time.perf_counter() - t0
            e1 = diff(materialize(st), materialize(build(C, Y, streets=st.streets_on)))
            t0 = time.perf_counter(); r2 = apply(st, ("street_add", it)); d2 = time.perf_counter() - t0
            name = C.streets[it]["id"]
        else:
            t0 = time.perf_counter(); r1 = apply(st, ("struct_remove", it)); d1 = time.perf_counter() - t0
            e1 = diff(materialize(st), materialize(build(C, Y, sset=st.sset)))
            t0 = time.perf_counter(); r2 = apply(st, ("struct_add", it)); d2 = time.perf_counter() - t0
            name = C.S.structs[it]["id"]
        e2 = diff(materialize(st), full)
        ok = _ok(e1) and _ok(e2)
        out["n"] += 1
        out["all_equal"] &= ok
        out["remove_ms"].append(d1)
        out["add_ms"].append(d2)
        out["items"].append({"id": name, "remove_ms": round(d1 * 1000, 2), "add_ms": round(d2 * 1000, 2),
                             "moved_remove": r1, "moved_add": r2, "equal": ok})
        print(which, name, round(d1 * 1000, 1), round(d2 * 1000, 1), r1, ok, flush=True)
    out["remove_ms"], out["add_ms"] = _stat(out["remove_ms"]), _stat(out["add_ms"])
    out["all_equal"] = bool(out["all_equal"])
    return out


def stage_compare(C, world):
    """街道版 vs v6 直线版；覆盖统计；性能与内存；坊规模。"""
    S = C.S
    out = {"affine_upstream_to_ledger": C.affine_stats, "upstream_clip": C.up_clip,
           "segments_total": C.nseg, "streets_total": len(C.streets)}
    comp = {}
    for Y in (41, 55, 70):
        st7 = build(C, Y)
        r7, n7 = materialize(st7)
        r6, n6 = cs6.materialize(cs6.build(world, Y, S))
        idx = {"water": 2, "parish": 3, "arian": 4, "watch": 5, "grain": 6}
        ch = {k: sum(1 for h in r7 if r7[h][i] != r6[h][i]) for k, i in idx.items()}
        anych = [h for h in r7 if any(r7[h][i] != r6[h][i] for i in (2, 3, 5, 6))]
        n = len(r7)
        # 差异最大的区域：按 v7 坊（≥30 户）计改归属比例；也按 v6 坊
        by = {}
        aset = set(anych)
        for h in r7:
            f = r7[h][1]
            a = by.setdefault(f, [0, 0])
            a[0] += 1
            a[1] += h in aset
        top = sorted(((v[1] / v[0], v[1], v[0], f) for f, v in by.items() if v[0] >= 30), reverse=True)[:3]
        by6 = {}
        for h in r6:
            f = r6[h][1]
            a = by6.setdefault(f, [0, 0])
            a[0] += 1
            a[1] += h in aset
        top6 = sorted(((v[1], v[0], f) for f, v in by6.items()), reverse=True)[:3]
        # 不计哨（城墙每 50 单位一段，街道版几乎全换）：只看供水/教区/配给
        exw = {h for h in r7 if any(r7[h][i] != r6[h][i] for i in (2, 3, 6))}
        byx = {}
        for h in r7:
            a = byx.setdefault(r7[h][1], [0, 0])
            a[0] += 1
            a[1] += h in exw
        topx = sorted(((v[1], v[1] / v[0], v[0], f) for f, v in byx.items() if v[0] >= 30), reverse=True)[:3]
        # 典型：最大直线距离与街道距离之比
        acc = np.array([st7.hdoor[h][4] for h in st7.rec])
        srcs = {}
        up_cov = {"in_upstream_coverage": 0}
        for h in st7.rec:
            src = C.streets[C.sst[st7.hdoor[h][0]]]["src"]
            srcs[src] = srcs.get(src, 0) + 1
            up_cov["in_upstream_coverage"] += bool(C.up_set[h])
        fc = {}
        for v in r7.values():
            fc[v[1]] = fc.get(v[1], 0) + 1
        fv = np.array(sorted(fc.values()))
        comp[Y] = {"households": n,
                   "changed_any_of_water_parish_watch_grain": len(anych), "changed_ratio": round(len(anych) / n, 4),
                   "changed_by_field": ch, "changed_ratio_by_field": {k: round(v / n, 4) for k, v in ch.items()},
                   "top3_v7_fang_by_ratio(>=30户)": [{"fang": f, "changed": c, "households": t, "ratio": round(r, 3)} for r, c, t, f in top],
                   "top3_v6_fang_by_count": [{"v6_fang": f, "changed": c, "households": t} for c, t, f in top6],
                   "changed_any_of_water_parish_grain": len(exw), "changed_ratio_excl_watch": round(len(exw) / n, 4),
                   "top3_v7_fang_excl_watch_by_count(>=30户)": [{"fang": f, "changed": c, "households": t, "ratio": round(r, 3)} for c, r, t, f in topx],
                   "door_street_source": srcs, "upstream_ledger_ids_standing": up_cov["in_upstream_coverage"],
                   "door_access": {"median": round(float(np.median(acc)), 2), "p90": round(float(np.percentile(acc, 90)), 2),
                                   "max": round(float(acc.max()), 2), "share_le_3": round(float((acc <= 3).mean()), 4)},
                   "graph": {"nodes": len(st7.adj), "edges": sum(len(v) for v in st7.adj.values()) // 2,
                             "streets_standing": len(st7.streets_on), "snap_links": len(st7.snap),
                             "faces": len(st7.faces)},
                   "fang": {"n": len(fv), "min": int(fv[0]), "median": float(np.median(fv)), "p90": float(np.percentile(fv, 90)),
                            "max": int(fv[-1]), "households_weighted_median": float(np.median(np.repeat(fv, fv))),
                            "n_le_5": int((fv <= 5).sum()), "households_in_fang_le_5": int(fv[fv <= 5].sum())},
                   "nodes_by_title": {}}
        for t, _, _ in n7.values():
            comp[Y]["nodes_by_title"][t] = comp[Y]["nodes_by_title"].get(t, 0) + 1
        cnt = {}
        for t, hid, c in n7.values():
            if hid is not None:
                cnt[hid] = cnt.get(hid, 0) + 1
        comp[Y]["one_office"] = {"multi_office_households": sum(1 for v in cnt.values() if v > 1), "holders": len(cnt),
                                 "vacant": sum(1 for _, hid, _ in n7.values() if hid is None)}
        # 账本道路单独（不补上游）时的门口垂距，对比「太粗」
        st_l = build(C, Y, streets={i for i in street_ids_for(C, Y) if C.streets[i]["src"] == "ledger"})
        al = np.array([st_l.hdoor[h][4] for h in st_l.rec])
        ups = [h for h in st7.rec if C.up_set[h]]
        comp[Y]["ledger_only_door_access"] = {"median": round(float(np.median(al)), 2), "p90": round(float(np.percentile(al, 90)), 2),
                                              "upstream_area_houses_median_ledger_only": round(float(np.median([st_l.hdoor[h][4] for h in ups])), 2) if ups else None,
                                              "upstream_area_houses_median_with_upstream": round(float(np.median([st7.hdoor[h][4] for h in ups])), 2) if ups else None}
        print("compare", Y, comp[Y]["changed_ratio"], flush=True)
    out["vs_v6"] = comp
    # 性能：全城生成、内存、每户字节
    bt = []
    for _ in range(3):
        t0 = time.perf_counter(); build(C, 70); bt.append(time.perf_counter() - t0)
    t0 = time.perf_counter(); prepare(world); tp = time.perf_counter() - t0
    tracemalloc.start()
    st = build(C, 70)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    recs, nodes = materialize(st)
    js = json.dumps([[k, *v] for k, v in recs.items()], ensure_ascii=False).encode()
    gz = gzip.compress(js, 9)
    out["perf"] = {"prepare_s": round(tp, 3), "build_Y70_s": [round(x, 3) for x in bt],
                   "build_mem_peak_MB": round(peak / 2 ** 20, 1), "state_mem_MB": round(cur / 2 ** 20, 1),
                   "state_bytes_per_household": round(cur / len(recs), 1),
                   "records_json_bytes": len(js), "records_gz_bytes": len(gz),
                   "bytes_per_household_gz": round(len(gz) / len(recs), 1), "n_nodes_70": len(nodes)}
    return out


def stage_junctions(C, world):
    """核对：上游 junctions.json 的路口（仿射到账本坐标）离 AF70 街网最近节点多远。"""
    J = json.load(open(os.path.join(UPSTREAM, "junctions.json")))
    P = np.c_[np.array([[j[0], j[1]] for j in J], float), np.ones(len(J))] @ C.affine
    st = build(C, 70)
    nodes = np.array([kxy(k) for k in st.adj])
    deg = np.array([len(st.adj[k]) for k in st.adj])
    from scipy.spatial import cKDTree
    d, i = cKDTree(nodes).query(P)
    j3 = nodes[deg >= 3]
    d3, _ = cKDTree(j3).query(P)
    return {"upstream_junctions": len(J), "nearest_node_median": round(float(np.median(d)), 3),
            "share_within_1": round(float((d <= 1).mean()), 4), "share_within_3": round(float((d <= 3).mean()), 4),
            "nearest_deg3_node_median": round(float(np.median(d3)), 3), "share_deg3_within_3": round(float((d3 <= 3).mean()), 4)}


def main():
    world = json.load(open(os.path.join(ROOT, "world.json")))
    C = prepare(world)
    stg = sys.argv[1] if len(sys.argv) > 1 else "all"
    part = os.path.join(HERE, f".part_{stg}.json")
    if stg == "incr":
        r = stage_incr(C, world)
    elif stg == "rt_street":
        r = stage_rt(C, world, "street")
    elif stg == "rt_fac":
        r = stage_rt(C, world, "fac")
    elif stg == "compare":
        r = stage_compare(C, world)
    elif stg == "junctions":
        r = stage_junctions(C, world)
    elif stg == "assemble":
        out = {"params": {"SNAP_MAX": SNAP_MAX, "HULL_GROW": HULL_GROW, "F_MIN": F_MIN, "F_MAX": F_MAX,
                          "F_DEPTH": F_DEPTH, "F_SECTOR": F_SECTOR, "node_quantum": 1 / Q, "TOPK": TOPK}}
        rp = os.path.join(HERE, "results.json")
        if os.path.exists(rp):
            old = json.load(open(rp))
            out = {**old, **out}
        for s in ("compare", "incr", "rt_street", "rt_fac", "junctions"):
            p = os.path.join(HERE, f".part_{s}.json")
            if os.path.exists(p):
                out[s] = json.load(open(p))
                os.remove(p)
        json.dump(out, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=int)
        return
    else:
        raise SystemExit("stage: incr | rt_street | rt_fac | compare | assemble")
    json.dump(r, open(part, "w"), ensure_ascii=False, indent=1, default=int)


if __name__ == "__main__":
    main()
