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
import heapq
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
FIELDS = ("d", "fang", "water", "parish", "arian", "watch", "grain", "ration", "guild")
NODE_TITLE = {"区": "区长", "坊": "坊长", "水": "水役头", "教": "长老", "阿": "长老(阿里乌)", "哨": "哨长", "行": "行会头"}


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
    S.wall_poly = {}         # sidx -> 城墙折线（取候选时用作距离下界）
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
            S.wall_poly[k] = c
            for a, b, segno in _wall_segments(c):
                for q in _sample(a, b):
                    pts.append(("watch", f"{sid}#s{segno:02d}", q))
        S.kind_pts[k] = pts
    S.kinds = ("water", "parish", "church_all", "watch", "grain")
    S.lab_names = {kd: [] for kd in S.kinds}      # 每类设施的全局标签表（静态），房屋归属存整数下标
    S.lab_id = {kd: {} for kd in S.kinds}
    for k in range(len(S.structs)):
        for kd, label, _ in S.kind_pts[k]:
            if label not in S.lab_id[kd]:
                S.lab_id[kd][label] = len(S.lab_names[kd])
                S.lab_names[kd].append(label)
    S.is_arian = np.array([lb in ARIAN for lb in S.lab_names["church_all"]], bool)
    S.htree = cKDTree(S.xy)                      # 全部账本房屋（静态），供结构增量取候选
    S.guild = [None] * len(H)                    # 行会（第 9 栏街区功能），见 load_guilds
    load_guilds(S)
    return S


UPSTREAM = os.path.join(ROOT, "docs", "living", "xerolophos", "facts_upstream")
GUILD_FN = ("market", "shops", "workshop")       # 只把「行当」类街区功能算行会；民居/体面人家/菜园/新街坊/汲水/兵营不算


def load_guilds(S):
    """上游 houses.json 第 9 栏 = 房屋所在地块的街区功能；按 id 接到账本房屋，行当类给行会字段。"""
    S.guild_stats = {"upstream_houses": 0, "matched": 0, "date_mismatch": 0, "guild_houses": 0}
    try:
        fn = json.load(open(os.path.join(UPSTREAM, "blocks.json")))["fn"]
        U = json.load(open(os.path.join(UPSTREAM, "houses.json")))["houses"]
    except (OSError, KeyError, ValueError):
        return
    pos = {int(x): i for i, x in enumerate(S.idnum.tolist())}
    st = S.guild_stats
    st["upstream_houses"] = len(U)
    for row in U:
        i = pos.get(int(row[0]))
        if i is None:
            continue
        st["matched"] += 1
        if S.built[i] != row[2] or (S.destroyed[i] if S.destroyed[i] < 10 ** 9 else 9999) != row[3]:
            st["date_mismatch"] += 1
        if row[8] in GUILD_FN:
            S.guild[i] = fn[row[8]][0]
            st["guild_houses"] += 1


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


def _poly_dist(Q, c):
    """点集 Q 到折线 c 的最近距离（向量化）。"""
    best = np.full(len(Q), np.inf)
    for a, b in zip(c[:-1], c[1:]):
        ab = b - a
        L2 = float(ab @ ab)
        t = np.clip(((Q - a) @ ab) / L2, 0.0, 1.0) if L2 > 0 else np.zeros(len(Q))
        best = np.minimum(best, np.sqrt(((Q - a - t[:, None] * ab) ** 2).sum(1)))
    return best


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


KINDS = ("water", "parish", "church_all", "watch", "grain")
# 一户一职：固定优先序（区长 > 坊长 > 长老 > 阿里乌长老 > 水役头 > 哨长 > 行会头）
TAGS = ("区", "坊", "教", "阿", "水", "哨", "行")
LEVEL = {t: i for i, t in enumerate(TAGS)}
TIE_EPS = 1e-9


def _make_tree(S, sset, kind):
    pts, gid = [], []
    ids = S.lab_id[kind]
    for k in sorted(sset):
        for kd, label, q in S.kind_pts[k]:
            if kd == kind:
                pts.append(q)
                gid.append(ids[label])
    return (cKDTree(np.array(pts)), np.array(gid, dtype=np.int32)) if pts else (None, None)


def _assign_kind(st, kind, hs):
    """对房屋 hs 按当前该类设施树重查最近设施，写 dist / labi / tie（全向量化）。"""
    if not len(hs):
        return
    tree, gid = st.trees[kind]
    hs = np.asarray(hs, dtype=np.int64)
    if tree is None:
        st.dist[kind][hs] = np.inf
        st.labi[kind][hs] = -1
        st.tie[kind][hs] = False
        return
    if tree.n > 1:
        d, j = tree.query(st.S.xy[hs], k=2)
        st.tie[kind][hs] = (d[:, 1] - d[:, 0]) <= TIE_EPS * (1.0 + d[:, 0])
        d, j = d[:, 0], j[:, 0]
    else:
        d, j = tree.query(st.S.xy[hs])
        st.tie[kind][hs] = False
    st.dist[kind][hs] = d
    st.labi[kind][hs] = gid[j]


NODE_KIND = (("教", "parish"), ("阿", "church_all"), ("水", "water"), ("哨", "watch"))


def _node_keys(st, h):
    S = st.S
    ks = [("区", S.d[h]), ("坊", S.fang[h])]
    for tag, kd in NODE_KIND:
        i = st.labi[kd][h]
        if i >= 0 and (tag != "阿" or S.is_arian[i]):
            ks.append((tag, S.lab_names[kd][i]))
    g = S.guild[h]
    if g is not None:
        ks.append(("行", f"{S.d[h]}×{g}"))
    return ks


# ---- 一户一职的增量维护：脏节点按优先级层次由高到低结算，层 L 的改动只会弄脏 >L 的层
def _mark(st, k, h=None):
    if h is None:
        st.recomp.add(k)
    else:
        st.cand.setdefault(k, set()).add(h)
    if k not in st.queued:
        st.queued.add(k)
        heapq.heappush(st.heap, (LEVEL[k[0]], k))


def _free(st, h, L):
    """h 卸下层 L 的职务：若 h 仍在，则在其更低层节点里候选。"""
    if h in st.rec:
        for k2 in _node_keys(st, h):
            if LEVEL[k2[0]] > L:
                _mark(st, k2, h)


def _add_member(st, k, h):
    m = st.members.get(k)
    if m is None:
        st.members[k] = {h}
        st.holder[k] = None
    else:
        m.add(h)
    _mark(st, k, h)


def _remove_member(st, k, h):
    m = st.members[k]
    m.discard(h)
    if st.holder[k] == h:
        st.holder[k] = None
        del st.office[h]
        _free(st, h, LEVEL[k[0]])
        _mark(st, k)
    if not m:
        del st.members[k], st.holder[k]


def _settle(st):
    sen = st.S.seniority
    office, members, holder = st.office, st.members, st.holder
    while st.heap:
        L, k = heapq.heappop(st.heap)
        st.queued.discard(k)
        cand = st.cand.pop(k, ())
        rec = k in st.recomp
        st.recomp.discard(k)
        m = members.get(k)
        if m is None:
            continue

        def elig(x):
            o = office.get(x)
            return o is None or o == k or LEVEL[o[0]] > L
        cur = holder[k]
        src_ = m if rec else cand
        new = None
        if len(src_) > 64:              # 大批：按年资排序后取第一个合格者
            arr = np.fromiter(src_, dtype=np.int64, count=len(src_))
            for x in arr[np.argsort(sen[arr], kind="stable")].tolist():
                if (rec or x in m) and elig(x):
                    new = x
                    break
        else:
            pool = [x for x in src_ if (rec or x in m) and elig(x)]
            new = min(pool, key=sen.__getitem__) if pool else None
        if not rec and cur is not None and (new is None or sen[cur] < sen[new]):
            new = cur
        if new == cur:
            continue
        if cur is not None:
            del office[cur]
            _free(st, cur, L)
        if new is not None:
            o = office.get(new)
            if o is not None:
                holder[o] = None
                _mark(st, o)
            office[new] = k
        holder[k] = new


def _new_state(S, Y):
    st = State()
    st.S, st.Y = S, Y
    N = len(S.hid)
    st.alive = np.zeros(N, bool)
    st.dist = {k: np.full(N, np.inf) for k in KINDS}
    st.labi = {k: np.full(N, -1, dtype=np.int32) for k in KINDS}
    st.tie = {k: np.zeros(N, bool) for k in KINDS}
    st.rec, st.members, st.holder, st.office = {}, {}, {}, {}
    st.cand, st.recomp, st.queued, st.heap = {}, set(), set(), []
    return st


def build(world, Y, S=None, sset=None):
    S = S or prepare(world)
    st = _new_state(S, Y)
    st.sset = set(sset) if sset is not None else {k for k, s in enumerate(S.structs) if standing(s, Y)}
    st.trees = {kind: _make_tree(S, st.sset, kind) for kind in KINDS}
    alive = np.nonzero((S.built <= Y) & (S.destroyed > Y))[0]
    st.alive[alive] = True
    for kind in KINDS:
        _assign_kind(st, kind, alive)
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
    # 一户一职：逐层按年资（最早建成，同年按 id）取所辖中尚未任职者
    office, holder = st.office, st.holder
    for tag in TAGS:
        for h in order:
            if h in office:
                continue
            k = keys[h].get(tag)
            if k is not None and holder[k] is None:
                holder[k] = h
                office[h] = k
    return st


def apply(st, ev):
    kind, arg = ev
    S = st.S
    if kind == "build":
        hs = [h for h in arg if h not in st.rec]
        st.alive[hs] = True
        for kd in KINDS:
            _assign_kind(st, kd, hs)
        for h in hs:
            st.rec[h] = None
            for k in _node_keys(st, h):
                _add_member(st, k, h)
        _settle(st)
    elif kind == "destroy":
        for h in arg:
            if h in st.rec:
                ks = _node_keys(st, h)
                del st.rec[h]
                st.alive[h] = False
                for kd in KINDS:
                    st.tie[kd][h] = False
                for k in ks:
                    _remove_member(st, k, h)
        _settle(st)
    elif kind in ("struct_add", "struct_remove"):
        pts = S.kind_pts[arg]
        if kind == "struct_add":
            st.sset.add(arg)
        else:
            st.sset.discard(arg)
        if not pts:                         # 道路、街区多边形等：不改任何制度字段
            return 0
        moves = {}                      # (旧节点, 新节点) -> [房屋]；补给点（grain）不进节点
        tagof = {kd: tag for tag, kd in NODE_KIND}
        alive_idx = np.nonzero(st.alive)[0]
        n_changed = set()
        for kd in sorted({p[0] for p in pts}):
            P = np.array([q for kk, _, q in pts if kk == kd])
            ids = np.array(sorted({S.lab_id[kd][lb] for kk, lb, _ in pts if kk == kd}), dtype=np.int32)
            if kind == "struct_add":
                if st.trees[kd][0] is None or not len(alive_idx):
                    cand = alive_idx
                else:
                    # 只查可能改归属的房屋：离新设施比离当前归属设施更近（含并列）
                    c = P.mean(0)
                    R = float(np.sqrt(((P - c) ** 2).sum(1)).max())
                    rmax = float(st.dist[kd][alive_idx].max())
                    ball = np.asarray(S.htree.query_ball_point(c, R + rmax + 1e-6), dtype=np.int64)
                    ball = ball[st.alive[ball]]
                    Q = S.xy[ball]
                    if arg in S.wall_poly and kd == "watch" and len(P) > 16:
                        dn = _poly_dist(Q, S.wall_poly[arg])    # 折线距离 ≤ 到采样点距离：候选取超集，安全
                        if len(P) < sum(1 for p in pts if p[0] == kd):
                            dn = np.minimum(dn, cKDTree(P).query(Q)[0])
                    elif len(P) > 16:
                        dn = cKDTree(P).query(Q)[0]
                    else:
                        dn = np.sqrt(((Q[:, None, :] - P[None, :, :]) ** 2).sum(2)).min(1)
                    cand = ball[dn <= st.dist[kd][ball] * (1 + TIE_EPS) + TIE_EPS]
            else:
                # 拆除：只重查原归属该结构的房屋
                cand = alive_idx[np.isin(st.labi[kd][alive_idx], ids)]
            cand = np.union1d(cand, alive_idx[st.tie[kd][alive_idx]]).astype(np.int64)
            old = st.labi[kd][cand].copy()
            st.trees[kd] = _make_tree(S, st.sset, kd)
            _assign_kind(st, kd, cand)
            new = st.labi[kd][cand]
            ch = old != new
            hs, old, new = cand[ch], old[ch], new[ch]
            tag = tagof.get(kd)
            if tag is None or not len(hs):
                n_changed.update(hs.tolist())
                continue
            if tag == "阿":             # 只有最近教堂是阿里乌派时才是成员
                old = np.where((old >= 0) & S.is_arian[np.maximum(old, 0)], old, -1)
                new = np.where((new >= 0) & S.is_arian[np.maximum(new, 0)], new, -1)
                keep = old != new
                hs, old, new = hs[keep], old[keep], new[keep]
            n_changed.update(hs.tolist())
            names = S.lab_names[kd]
            pair = old.astype(np.int64) * 100003 + new
            for pv in np.unique(pair).tolist():
                sel = pair == pv
                o, nw = int(old[sel][0]), int(new[sel][0])
                moves[(None if o < 0 else (tag, names[o]), None if nw < 0 else (tag, names[nw]))] = hs[sel].tolist()
        n = len(n_changed)
        _bulk_move(st, moves)
        _settle(st)
        return n
    return 0


def _bulk_move(st, moves):
    """成批改节点成员：旧节点去掉、新节点加上（新成员全部作候选，结算时按一户一职取舍）。"""
    for (ko, kn), hs in moves.items():
        if ko is not None:
            m = st.members[ko]
            m.difference_update(hs)
            hd = st.holder[ko]
            if hd is not None and hd not in m:
                st.holder[ko] = None
                del st.office[hd]
                _free(st, hd, LEVEL[ko[0]])
                _mark(st, ko)
            if not m:
                del st.members[ko], st.holder[ko]
        if kn is not None:
            m = st.members.get(kn)
            if m is None:
                st.members[kn] = set(hs)
                st.holder[kn] = None
            else:
                m.update(hs)
            st.cand.setdefault(kn, set()).update(hs)
            if kn not in st.queued:
                st.queued.add(kn)
                heapq.heappush(st.heap, (LEVEL[kn[0]], kn))


def materialize(st):
    S = st.S
    n = len(st.rec)
    cap = food_cap(st.Y)
    ration = cap / n if n else 0.0
    recs = {}
    nm = S.lab_names

    def lab(kd, h):
        i = st.labi[kd][h]
        return None if i < 0 else nm[kd][i]
    for h in st.rec:
        a = lab("church_all", h)
        recs[S.hid[h]] = (S.d[h], S.fang[h], lab("water", h), lab("parish", h), a if a in ARIAN else None,
                          lab("watch", h), lab("grain", h), ration, S.guild[h])
    nodes = {f"{k[0]}:{k[1]}": (NODE_TITLE[k[0]], None if st.holder[k] is None else S.hid[st.holder[k]], len(m))
             for k, m in st.members.items()}
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
    yearly, times = [], {"build": [], "destroy": [], "struct_add": [], "struct_remove": [],
                         "struct_add_facility": [], "struct_remove_facility": []}
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
            if ev[0].startswith("struct") and S.kind_pts[ev[1]]:
                times[ev[0] + "_facility"].append(dt)
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
    # 拆除/新增结构往返（AF41–70 账本内无结构拆除事件，故合成）：在 AF45、AF70 对每个设施结构
    # 先拆（与「不含该结构」重建逐字段比对）再建回（与原年重建比对）
    rt = {"n": 0, "all_equal": True, "remove_ms": [], "add_ms": [], "worst": []}
    for Y in (45, 70):
        st2 = build(world, Y, S)
        for k in sorted(st2.sset):
            if not S.kind_pts[k]:
                continue
            t0 = time.perf_counter(); r1 = apply(st2, ("struct_remove", k)); d1 = time.perf_counter() - t0
            e1 = diff(materialize(st2), materialize(build(world, Y, S, st2.sset)))
            t0 = time.perf_counter(); r2 = apply(st2, ("struct_add", k)); d2 = time.perf_counter() - t0
            e2 = diff(materialize(st2), materialize(build(world, Y, S)))
            ok = all(e[0] == 0 and not any(e[1].values()) and e[2] == 0 for e in (e1, e2))
            rt["n"] += 1
            rt["all_equal"] &= ok
            rt["remove_ms"].append(d1)
            rt["add_ms"].append(d2)
            rt["worst"].append((round(max(d1, d2) * 1000, 2), Y, S.structs[k]["id"], r1, r2, ok))
            times["struct_remove"].append(d1); times["struct_remove_facility"].append(d1)
            times["struct_add_synthetic"] = times.get("struct_add_synthetic", []) + [d2]
    rt["worst"] = sorted(rt["worst"], reverse=True)[:8]
    rt["remove_ms"], rt["add_ms"] = stat(rt["remove_ms"]), stat(rt["add_ms"])
    out["struct_roundtrip"] = rt
    print("roundtrip", json.dumps(rt, ensure_ascii=False))

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
    # 一户一职核查（AF70）
    cnt = {}
    for t, hid, c in nodes70.values():
        if hid is not None:
            cnt[hid] = cnt.get(hid, 0) + 1
    out["one_office_70"] = {
        "households_with_multiple_offices": sum(1 for v in cnt.values() if v > 1),
        "office_holders": len(cnt), "nodes": len(nodes70),
        "vacant_nodes": sum(1 for _, hid, _ in nodes70.values() if hid is None),
        "h1315_offices": [k for k, v in nodes70.items() if v[1] == "h1315"],
    }
    out["guild"] = dict(S.guild_stats)
    out["guild"]["guild_houses_standing_70"] = sum(1 for v in recs70.values() if v[8] is not None)
    out["guild"]["standing_70"] = len(recs70)
    out["guild"]["nodes_70"] = {k: v for k, v in nodes70.items() if k.startswith("行:")}
    out["guild"]["upstream_matched_standing_by_year"] = {
        Y: int(sum(1 for r in json.load(open(os.path.join(UPSTREAM, "houses.json")))["houses"]
                   if r[2] <= Y < r[3])) for Y in (41, 50, 60, 70)} if S.guild_stats["upstream_houses"] else {}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=int)
    print(json.dumps({k: out[k] for k in ("perf", "incremental", "fang_70", "node_counts_70", "one_office_70", "guild")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
