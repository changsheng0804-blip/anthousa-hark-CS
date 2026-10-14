#!/usr/bin/env python3
"""yamen_v13 —— 门牌 × 户籍 × 官府：门牌是户籍主键，辖区用门牌段表达，流程按门牌路由（刘线）。

运行（分段，每段 < 2 分钟；中间结果写 .cache_*.pkl）：
  python3 yamen.py incr      v7 逐年增量 + 门牌增量 + v8 填职 + 户籍增量（AF40–70）
  python3 yamen.py rebuild   v7 逐年从头建 + 门牌按街批量重放 + 户籍从头生成，与 incr 逐年比对
  python3 yamen.py emit      registry_AF*.json.gz、addr_history.json.gz、offices_seated.json、路由测时与核对、results.json
依赖：numpy、scipy；按路径载入 ../city_system_v7_streets/city_system.py 与 ../gov_frame_v8/cast.py（均未改动）。
——Hark（刘线）
"""
import copy
import gzip
import hashlib
import importlib.util
import json
import math
import os
import pickle
import random
import sys
import time
from bisect import bisect_left, insort
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
UP = os.path.join(ROOT, "docs", "living", "xerolophos", "facts_upstream")


def _load(name, rel):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", rel))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


cs7 = _load("cs7_y13", "city_system_v7_streets/city_system.py")
cast = _load("cast_y13", "gov_frame_v8/cast.py")
cs6 = cs7.cs6

Y0, Y1 = 40, 70
SNAP = (40, 50, 60, 70)
ODD_LEFT = False     # 假设：沿街方向看，账本坐标叉积 < 0 一侧为单号（与上游 facts_from_upstream 同式；见 REPORT）
RF = cast.RF


# ================================================================ 街：键、名、沿街位置
def street_tables(C):
    """K = 街键（账本道路 id，或 'u:上游街名'）；同名上游街的各段共用一条门牌序列，位置按上游整条折线累计。"""
    SN = json.load(open(os.path.join(UP, "streetnames.json")))
    sn = {s["n"]: s for s in SN}
    M = C.affine
    run_off = {}
    for s in SN:
        P = np.asarray(s["p"], float)
        W = np.c_[P, np.ones(len(P))] @ M
        ok = C.hull.find_simplex(W) >= 0
        cum = np.r_[0.0, np.cumsum(np.hypot(*(W[1:] - W[:-1]).T))]
        run, r, start = [], 0, None
        for j in range(len(W)):
            if ok[j]:
                if not run:
                    start = j
                run.append(j)
            if (not ok[j] or j == len(W) - 1) and len(run) >= 2:
                run_off[f"u:{s['n']}#{r}"] = float(cum[start])
                r += 1
            if not ok[j]:
                run = []
    K, off, segpos = [], [], {}
    for i, s in enumerate(C.streets):
        if s["src"] == "upstream":
            K.append("u:" + s["name"])
            off.append(run_off[s["id"]])
        else:
            K.append(s["id"])
            off.append(0.0)
        acc = off[-1]
        for g in C.street_segs[i]:
            L = math.dist(C.sA[g], C.sB[g])
            segpos[g] = (acc, L)
            acc += L
    return K, segpos, sn


def ledger_name(rid):
    """账本道路没有上游街名：由道路 id 生成稳定名（假设）。"""
    return "路·" + rid[2:] if rid.startswith("r_") else "路·" + rid


def name_at(T, k, Y):
    if k.startswith("u:"):
        s = T["sn"][k[2:]]
        for nm, a, b in s["r"]:
            if a <= Y < b:
                return nm
        return s["n"]
    return ledger_name(k)


def side_odd(left):
    return bool(left) == ODD_LEFT


# ================================================================ 门口表（每年）
def doors_of(st, T, C, Y):
    """eid → (街键, 单?, 沿街位置)。房屋 eid = 房屋 id；设施门 'f:标签'；兵营 's:结构 id'。"""
    S = C.S
    K, segpos = T["K"], T["segpos"]
    out = {}
    for h, dr in st.hdoor.items():
        g, _, t, P, acc, left = dr
        a, L = segpos[g]
        out[S.hid[h]] = (K[C.sst[g]], side_odd(left), round(a + float(t) * L, 4))
    for (k, lb), (g, key, acc) in st.doors.items():
        if k not in st.sset:
            continue
        pts = [p for l2, _, p in C.fac[k] if l2 == lb][0]
        Pm = pts.mean(0)
        t = min(1.0, max(0.0, cs7.tkey(C, g, key)))
        a, L = segpos[g]
        ax, ay = C.sA[g]
        bx, by = C.sB[g]
        left = (bx - ax) * (Pm[1] - ay) - (by - ay) * (Pm[0] - ax) >= 0
        out["f:" + lb] = (K[C.sst[g]], side_odd(left), round(a + t * L, 4))
    segs = np.array(sorted(st.segon))
    for k in T["extra_structs"]:
        if k not in st.sset:
            continue
        P0 = T["struct_xy"][k]
        D = cs7._seg_dist_mat_sub(C, np.array([P0]), segs)[0]
        g = int(segs[np.lexsort((segs, D))[0]])
        t, _, _ = cs7.proj(C, g, P0)
        ax, ay = C.sA[g]
        bx, by = C.sB[g]
        left = (bx - ax) * (P0[1] - ay) - (by - ay) * (P0[0] - ax) >= 0
        a, L = segpos[g]
        out["s:" + C.S.structs[k]["id"]] = (K[C.sst[g]], side_odd(left), round(a + float(t) * L, 4))
    return out


# ================================================================ 门牌规则
LET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def letters(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = LET[r] + s
    return s


def num_key(n):
    """门牌在本侧的排序：基号，小写附号（位于基号之前）< 无附号 < 大写附号（位于基号之后）。"""
    i = 0
    while i < len(n) and (n[i].isdigit()):
        i += 1
    b, suf = int(n[:i]), n[i:]
    if not suf:
        return (b, 1, 0, "")
    return (b, 0 if suf.islower() else 2, len(suf), suf.upper())


class Numbering:
    """一条街（两侧）的门牌状态。只看本街，不看别街——所以批量重建可按街独立重放。"""

    def __init__(self, k, upmax):
        self.k = k
        self.active = {True: [], False: []}     # 单/双 → 排序 [(pos, eid)]
        self.maxint = {True: -1, False: 0}
        self.upmax = upmax                       # 上游在本街本侧的最大门牌
        self.issued = {}                         # 号 → eid（含已注销）
        self.nextlet = Counter()                 # (基号, 大小写) → 下一个附号序
        self.num = {}                            # eid → 号（在册者；注销后留在 issued 里）

    def remove(self, eid, odd, pos):
        a = self.active[odd]
        i = bisect_left(a, (pos, eid))
        assert a[i] == (pos, eid), (self.k, eid)
        a.pop(i)

    def assign(self, eid, odd, pos, upnum):
        a = self.active[odd]
        if upnum is not None and upnum % 2 == (1 if odd else 0) and self.issued.get(str(upnum), eid) == eid:
            n, how = str(upnum), "上游门牌"
        else:
            i = bisect_left(a, (pos, eid))
            if i == len(a):
                b = max(self.maxint[odd], self.upmax.get(odd, -1 if odd else 0)) + 2
                n, how = str(b), "新号"
            elif i > 0:
                b = num_key(self.num[a[i - 1][1]])[0]
                c = self.nextlet[(b, "U")]
                self.nextlet[(b, "U")] += 1
                n, how = f"{b}{letters(c)}", "插号"
            else:
                b = num_key(self.num[a[0][1]])[0]
                c = self.nextlet[(b, "l")]
                self.nextlet[(b, "l")] += 1
                n, how = f"{b}{letters(c).lower()}", "插号(街头前)"
        nk = num_key(n)
        if nk[1] == 1:
            self.maxint[odd] = max(self.maxint[odd], nk[0])
        assert self.issued.get(n, eid) == eid, (self.k, n)
        self.issued[n] = eid
        self.num[eid] = n
        insort(a, (pos, eid))
        return n, how


class AddrBook:
    """全城门牌：逐年事件驱动（增量版）。"""

    def __init__(self, T):
        self.T = T
        self.streets = {}
        self.cur = {}          # eid → (街键, 单?, 位置, 号)
        self.events = []

    def street(self, k):
        s = self.streets.get(k)
        if s is None:
            s = self.streets[k] = Numbering(k, self.T["upmax"].get(k, {}))
        return s

    def step(self, Y, prev, door, changed, ctx):
        """changed：门口 (街键,侧) 变了、新出现或消失的 eid。先注销/迁出，再按 (有上游号先, 街, 侧, 位置, id) 编号，再记改名。"""
        T = self.T
        evs = []
        moved_out = {}
        for e in sorted(changed):
            c = self.cur.get(e)
            if c is None:
                continue
            d = door.get(e)
            if d is not None and d[:2] == c[:2]:
                continue
            self.streets[c[0]].remove(e, c[1], c[2])
            moved_out[e] = c
            del self.cur[e]
        arr = []
        for e in changed:
            d = door.get(e)
            if d is None or e in self.cur:
                continue
            arr.append((0 if T["upnum"](e, d[0], Y) is not None else 1, d[0], not d[1], d[2], e))
        arr.sort()
        for _, k, _, pos, e in arr:
            odd = door[e][1]
            n, how = self.street(k).assign(e, odd, pos, T["upnum"](e, k, Y))
            self.cur[e] = (k, odd, pos, n)
            old = moved_out.pop(e, None)
            new = (k, n)
            if old is None:
                evs.append((Y, e, "新编", None, new, how))
            else:
                evs.append((Y, e, "改址", (old[0], old[3]), new, reason(ctx, old[0], k)))
        for e, c in sorted(moved_out.items()):
            evs.append((Y, e, "注销", (c[0], c[3]), None, gone_reason(ctx, e)))
        # 改名：本年名字变了的街上、门牌未变的在册者
        moved = {ev[1] for ev in evs}
        for k in ctx["renamed"]:
            s = self.streets.get(k)
            if not s:
                continue
            for odd in (True, False):
                for pos, e in s.active[odd]:
                    if e not in moved:
                        evs.append((Y, e, "改名", (k, s.num[e]), (k, s.num[e]), f"{name_at(T, k, Y - 1)}→{name_at(T, k, Y)}"))
        self.events.extend(evs)
        return evs

    def snapshot(self):
        return {e: (c[0], c[3]) for e, c in self.cur.items()}


def gone_reason(ctx, e):
    if e in ctx["destroyed"]:
        return "拆毁"
    return "设施撤除" if e.startswith(("f:", "s:")) else "无街可归"


def reason(ctx, ko, kn):
    if ko not in ctx["standing"]:
        return "道路拆除"
    if kn in ctx["opened"] and kn != ko:
        return "新街开通"
    if kn == ko:
        return "换侧"
    return "门口改街"


def year_ctx(T, C, Y, prev_door, door, streets_on_prev, streets_on):
    Kp = {T["K"][i] for i in streets_on_prev}
    Kn = {T["K"][i] for i in streets_on}
    destroyed = {C.S.hid[h] for h in np.nonzero(C.S.destroyed == Y)[0].tolist()}
    renamed = sorted(k for k in Kn & Kp if name_at(T, k, Y) != name_at(T, k, Y - 1))
    return {"standing": Kn, "opened": Kn - Kp, "destroyed": destroyed, "renamed": renamed}


def changed_eids(prev, door):
    ch = [e for e, d in door.items() if (prev.get(e) or (None, None))[:2] != d[:2]]
    ch += [e for e in prev if e not in door]
    return ch


# ================================================================ 批量重建（按街独立重放）
def batch_numbering(T, C, doors, streets_on):
    """输入：每年从头建的门口表。按街键分组，每条街只看本街的进出，逐年重放。输出与 AddrBook 同形。"""
    years = sorted(doors)
    per_k = defaultdict(lambda: defaultdict(lambda: ([], [])))   # k → Y → (出, 进)
    for Y in years:
        prev = doors.get(Y - 1, {})
        cur = doors[Y]
        for e in set(prev) | set(cur):
            a, b = prev.get(e), cur.get(e)
            if (a or (None, None))[:2] == (b or (None, None))[:2]:
                continue
            if a is not None:
                per_k[a[0]][Y][0].append(e)
            if b is not None:
                per_k[b[0]][Y][1].append(e)
    cur_by_year = {Y: {} for Y in years}
    raw = []      # (Y, e, 'out'|'in', k, n, how)
    for k in sorted(per_k):
        s = Numbering(k, T["upmax"].get(k, {}))
        held = {}
        evY = per_k[k]
        for Y in years:
            if Y in evY:
                outs, ins = evY[Y]
                for e in sorted(outs):
                    a = doors[Y - 1][e]
                    s.remove(e, a[1], held[e][1])
                    raw.append((Y, e, "out", k, s.num[e]))
                    del held[e]
                arr = sorted((0 if T["upnum"](e, k, Y) is not None else 1, not doors[Y][e][1], doors[Y][e][2], e) for e in ins)
                for _, _, pos, e in arr:
                    odd = doors[Y][e][1]
                    n, how = s.assign(e, odd, pos, T["upnum"](e, k, Y))
                    held[e] = (odd, pos)
                    raw.append((Y, e, "in", k, n, how))
            for e in held:
                cur_by_year[Y][e] = (k, s.num[e])
    # 事件：同年同 eid 的出/进配对
    by = defaultdict(dict)
    for r in raw:
        by[(r[0], r[1])][r[2]] = r
    events = []
    for (Y, e), d in by.items():
        o, i = d.get("out"), d.get("in")
        ctx = T["ctx"][Y]
        if o and i:
            events.append((Y, e, "改址", (o[3], o[4]), (i[3], i[4]), reason(ctx, o[3], i[3])))
        elif i:
            events.append((Y, e, "新编", None, (i[3], i[4]), i[5]))
        else:
            events.append((Y, e, "注销", (o[3], o[4]), None, gone_reason(ctx, e)))
    for Y in years:
        if Y == years[0]:
            continue
        moved = {ev[1] for ev in events if ev[0] == Y}
        for k in T["ctx"][Y]["renamed"]:
            for e, (kk, n) in cur_by_year[Y].items():
                if kk == k and e not in moved and cur_by_year[Y - 1].get(e) == (k, n):
                    events.append((Y, e, "改名", (k, n), (k, n), f"{name_at(T, k, Y - 1)}→{name_at(T, k, Y)}"))
    return cur_by_year, events


def ev_key(ev):
    return (ev[0], ev[1], ev[2], str(ev[3]), str(ev[4]), ev[5])


# ================================================================ 上游门牌
def upstream_tables(C, T):
    A = json.load(open(os.path.join(UP, "addr.json")))
    us = A["streets"]
    pos = {int(x): C.S.hid[i] for i, x in enumerate(C.S.idnum.tolist())}
    runs = {}
    upmax = defaultdict(dict)
    for idn, (fn, rr) in A["h"].items():
        h = pos.get(int(idn))
        if h is None:
            continue
        for si, n, a, b in rr:
            k = "u:" + us[si][0]
            runs.setdefault(h, []).append((k, n, a, b))
            odd = n % 2 == 1
            upmax[k][odd] = max(upmax[k].get(odd, -1 if odd else 0), n)
    def upnum(e, k, Y):
        for kk, n, a, b in runs.get(e, ()):
            if kk == k and (a <= Y < b or (b == 999 and Y >= a)):
                return n
        return None
    return A, runs, dict(upmax), upnum


# ================================================================ 公共建筑与中心性代理
def seat_structs(C, Y):
    S = C.S
    st_ = [(k, s) for k, s in enumerate(S.structs) if cs6.standing(s, Y)]

    def area(s):
        P = np.asarray(s["geom"]["coords"], float)
        if P.ndim != 2 or len(P) < 3:
            return 0.0
        x, y = P[:, 0], P[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    oldest = lambda t: min(((s["built"], s["id"]) for k, s in st_ if s["type"] == t), default=(None, None))[1]
    ch = [(s, s["id"] in cs6.ARIAN) for k, s in st_ if s["type"] == "church"]
    big = lambda ar: max(((area(s), s["id"]) for s, a in ch if a == ar), default=(None, None))[1]
    return {"annona": ("f:" + oldest("granary"), "对应建筑：最早建成的在立粮仓（假设）"),
            "aquae": ("f:" + oldest("cistern"), "对应建筑：最早建成的在立蓄水池（假设）"),
            "nykteparch": ("s:" + oldest("barracks"), "对应建筑：兵营（账本唯一 barracks，假设夜巡长驻此）"),
            "bishop_nicene": ("f:" + big(False), "对应建筑：面积最大的在立尼西亚教堂（假设为主教座堂）"),
            "bishop_arian": (("f:" + big(True)) if big(True) else None, "对应建筑：面积最大的在立阿里乌教堂（假设）")}


def centrality_house(st, C):
    """账本没有城市长官官署：取当年全城街网路口里调和中心性最高者，门口离它最近的在册房屋代理（假设）。"""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    nodes = sorted(st.adj)
    ix = {n: i for i, n in enumerate(nodes)}
    r, c, w = [], [], []
    for u, nb in st.adj.items():
        for v, ow in nb.items():
            r.append(ix[u])
            c.append(ix[v])
            w.append(min(ow.values()))
    G = csr_matrix((w, (r, c)), shape=(len(nodes), len(nodes)))
    J = set()
    for s, d in st.inter.items():
        if s in st.segon:
            for j, kk in d.items():
                if j in st.segon:
                    J.add(kk)
    J = sorted(k for k in J if k in ix)
    ji = [ix[k] for k in J]
    D = dijkstra(G, directed=False, indices=ji)[:, ji]
    with np.errstate(divide="ignore"):
        H = np.where(D > 0, 1.0 / D, 0.0).sum(1)
    best = J[int(np.argmax(H))]
    bx, by = best[0] / 100, best[1] / 100
    hh = min(st.hdoor, key=lambda h: (math.hypot(st.hdoor[h][3][0] - bx, st.hdoor[h][3][1] - by), int(C.S.idnum[h])))
    return C.S.hid[hh], f"j:{bx:.2f},{by:.2f}", float(H.max()), len(J)


# ================================================================ 公共准备
def prep():
    world = json.load(open(os.path.join(ROOT, "world.json")))
    t = time.time()
    C = cs7.prepare(world)
    K, segpos, sn = street_tables(C)
    T = {"K": K, "segpos": segpos, "sn": sn}
    T["extra_structs"] = [k for k, s in enumerate(C.S.structs) if s["type"] == "barracks"]
    T["struct_xy"] = {k: np.asarray(C.S.structs[k]["geom"]["coords"], float).reshape(-1, 2).mean(0) for k in T["extra_structs"]}
    A, runs, upmax, upnum = upstream_tables(C, T)
    T["upmax"], T["upnum"], T["uprun"] = upmax, upnum, runs
    T["det"] = float(np.linalg.det(C.affine[:2]))
    return world, C, T, time.time() - t


def streets_on_at(C, Y):
    return cs7.street_ids_for(C, Y)


# ================================================================ 户籍
def reg_row(Y, h, r9, ration, held, built, addr):
    """户籍行（以门牌为键）：房屋、户主、坊、区、教区、信仰、供水组、配给点、口粮、哨、行会、职位、门口街段 id。"""
    I = cast.I
    arian = r9[I["arian"]]
    off = held.get(h)
    return [h, f"hh_{h}_g{cast.gen_of(h, Y, built)}", r9[I["fang"]], r9[I["d"]], arian or r9[I["parish"]],
            "arian" if arian else "nicene", r9[I["water"]], r9[I["grain"]], r9[I["watch"]],
            r9[I["guild"]], (f"{off[0]}|{off[1]}" if off else None), r9[I["street"]]]


REG_FIELDS = ["房屋id", "户主人物id", "坊", "区", "教区(尼西亚堂区或阿里乌会众)", "信仰代理", "供水组", "配给点(粮仓)",
              "哨", "行会", "所任职位(职位|辖区)", "门口街段id(v7)"]


def disp(T, a, Y):
    return None if a is None else f"{name_at(T, a[0], Y)} {a[1]}号"


def reg_hash(rows):
    return hashlib.sha1(json.dumps(sorted(rows.items()), ensure_ascii=False, default=str).encode()).hexdigest()


# ================================================================ 阶段一：增量
def stage_incr():
    t00 = time.time()
    world, C, T, t_prep = prep()
    S = C.S
    st = cs7.build(C, Y0)
    years, ration, doors, ton = {}, {}, {}, {}
    tim = {"v7_apply_ms": [], "door_extract_ms": [], "addr_detect_ms": [], "addr_update_ms": [], "materialize_ms": []}
    book = AddrBook(T)
    T["ctx"] = {}
    addr_by_year, evcount = {}, {}
    eparch_seat = {}
    seat_h = None
    prev_on = streets_on_at(C, Y0)
    for Y in range(Y0, Y1 + 1):
        t0 = time.perf_counter()
        if Y > Y0:
            st.Y = Y
            for ev in cs7.events_for_year(C, Y):
                cs7.apply(st, ev)
        tim["v7_apply_ms"].append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        recs, _ = cs7.materialize(st)
        tim["materialize_ms"].append((time.perf_counter() - t0) * 1000)
        years[Y] = {h: tuple(v[k] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9)) for h, v in recs.items()}
        ration[Y] = next(iter(recs.values()))[7] if recs else 0.0
        t0 = time.perf_counter()
        door = doors_of(st, T, C, Y)
        tim["door_extract_ms"].append((time.perf_counter() - t0) * 1000)
        doors[Y] = door
        on = set(st.streets_on)
        ton[Y] = on
        prev = doors.get(Y - 1, {})
        ctx = year_ctx(T, C, Y, prev, door, prev_on if Y > Y0 else on, on)
        T["ctx"][Y] = ctx
        t0 = time.perf_counter()
        ch = changed_eids(prev, door)
        t1 = time.perf_counter()
        evs = book.step(Y, prev, door, ch, ctx)
        t2 = time.perf_counter()
        if Y > Y0:
            tim["addr_detect_ms"].append((t1 - t0) * 1000)
            tim["addr_update_ms"].append((t2 - t1) * 1000)
        evcount[Y] = dict(Counter(e[2] for e in evs))
        addr_by_year[Y] = book.snapshot()
        prev_on = on
        if seat_h is None or seat_h not in years[Y]:
            seat_h, jn, hv, nj = centrality_house(st, C)
            eparch_seat[Y] = {"house": seat_h, "junction": jn, "harmonic": round(hv, 4), "junctions": nj}
    t_census = time.time() - t00
    # ---- v8 填职（规范版：每年全量校验）
    t0 = time.time()
    built = {S.hid[i]: int(S.built[i]) for i in range(len(S.hid))}
    idnum = {S.hid[i]: int(S.idnum[i]) for i in range(len(S.hid))}
    since = cast.residency_table(years, built)
    W = cast.World(years, built, idnum, since, {})
    O, P = cast.load_rules()
    cas = cast.Caster(W, O)
    holders, members = {}, {}
    for Y in range(Y0, Y1 + 1):
        cas.step(Y)
        holders[Y] = {inst: tuple(v) for inst, v in cas.holder.items()}
        if Y in SNAP:
            members[Y] = {k: set(v) for k, v in cas.members.items()}
    t_cast = time.time() - t0
    # ---- 户籍增量：只改变动户
    t0 = time.time()
    reg, reg_hashes, reg_snap, touched, hkey = {}, {}, {}, [], {}
    tim["reg_update_ms"] = []
    for Y in range(Y0, Y1 + 1):
        t1 = time.perf_counter()
        held = {v[0]: inst for inst, v in holders[Y].items()}
        A = addr_by_year[Y]
        if Y == Y0:
            ch = set(years[Y])
        else:
            pa, ph = addr_by_year[Y - 1], {v[0]: inst for inst, v in holders[Y - 1].items()}
            ch = {h for h in set(years[Y]) | set(years[Y - 1]) if years[Y].get(h) != years[Y - 1].get(h)}
            ch |= {h for h in years[Y] if cast.gen_of(h, Y, built) != cast.gen_of(h, Y - 1, built)}
            ch |= {h for h in set(held) | set(ph) if held.get(h) != ph.get(h)}
            ch |= {e for e in set(A) | set(pa) if A.get(e) != pa.get(e) and not e.startswith(("f:", "s:"))}
            ch |= {e for e, a in A.items() if not e.startswith(("f:", "s:")) and a[0] in T["ctx"][Y]["renamed"]}
        for h in ch:
            k_ = hkey.pop(h, None)
            if k_ is not None:
                del reg[k_]
        for h in ch:
            if h in years[Y] and h in A:
                k_ = disp(T, A[h], Y)
                reg[k_] = reg_row(Y, h, years[Y][h], ration[Y], held, built, A[h])
                hkey[h] = k_
        tim["reg_update_ms"].append((time.perf_counter() - t1) * 1000)
        touched.append(len(ch))
        reg_hashes[Y] = reg_hash(reg)
        if Y in SNAP:
            reg_snap[Y] = dict(reg)
    t_reg = time.time() - t0
    # 口粮字段会让每年全城都变：另报「不计口粮」的变动户数
    out = {"T_ctx": T["ctx"], "years": years, "ration": ration, "doors": doors, "addr_by_year": addr_by_year,
           "events": book.events, "evcount": evcount, "holders": holders, "members": members,
           "eparch_seat": eparch_seat, "reg_hashes": reg_hashes, "reg_snap": reg_snap, "touched": touched,
           "tim": tim, "t": {"prepare_s": t_prep, "census_addr_s": t_census, "cast_s": t_cast, "registry_s": t_reg},
           "streets_on": ton, "book": book, "since": since}
    # ---- 合成：AF70 后拆掉一条街 + 一条街改名（真实年里没有道路拆除）
    out["synthetic"] = synthetic(C, T, st, book, doors[Y1], ton[Y1])
    with open(os.path.join(HERE, ".cache_incr.pkl"), "wb") as f:
        pickle.dump({k: v for k, v in out.items() if k != "book"}, f)
    print(json.dumps({"t": out["t"], "evcount_total": dict(sum((Counter(v) for v in evcount.values()), Counter())),
                      "eparch_seat": eparch_seat, "synthetic": out["synthetic"]["summary"]}, ensure_ascii=False, default=str))


def synthetic(C, T, st, book, door70, on70):
    """AF70 状态上：拆掉门牌最多的一条账本道路，同时把一条上游街改名，增量 vs 按街重放。"""
    Y = Y1 + 1
    cnt = Counter(v[0] for v in door70.values())
    led = [k for k, _ in cnt.most_common() if not k.startswith("u:")]
    kill = led[0]
    iks = [i for i, k in enumerate(T["K"]) if k == kill]
    up = [k for k, _ in cnt.most_common() if k.startswith("u:")][0]
    sn_backup = copy.deepcopy(T["sn"][up[2:]]["r"])
    T["sn"][up[2:]]["r"] = [[r[0], r[1], min(r[2], Y)] for r in sn_backup] + [[name_at(T, up, Y1) + "（合成新名）", Y, 9999]]
    t0 = time.perf_counter()
    st.Y = Y
    for i in iks:
        cs7.apply(st, ("street_remove", i))
    t_v7 = time.perf_counter() - t0
    on = set(st.streets_on)
    door = doors_of(st, T, C, Y)
    ctx = year_ctx(T, C, Y, door70, door, on70, on)
    ctx["destroyed"] = set()
    T["ctx"][Y] = ctx
    b2 = copy.deepcopy(book)
    t0 = time.perf_counter()
    ch = changed_eids(door70, door)
    evs = b2.step(Y, door70, door, ch, ctx)
    t_inc = time.perf_counter() - t0
    fresh = cs7.build(C, Y, streets=on, sset=st.sset)
    dfresh = doors_of(fresh, T, C, Y)
    res = {"door_equal_incr_vs_fresh": dfresh == door, "removed_street": kill, "renamed_street": up,
           "v7_ms": round(t_v7 * 1000, 1), "addr_incr_ms": round(t_inc * 1000, 2), "changed": len(ch),
           "events": dict(Counter(e[2] + "|" + e[5] for e in evs))}
    T["sn"][up[2:]]["r"] = sn_backup
    return {"summary": res, "door71": dfresh, "snap71": b2.snapshot(), "events71": evs, "ctx71": ctx,
            "sn71": T["sn"][up[2:]]["r"], "up": up, "sn_r71": [[r[0], r[1], min(r[2], Y)] for r in sn_backup] + [[name_at(T, up, Y1) + "（合成新名）", Y, 9999]]}


# ================================================================ 阶段二：从头重建并比对
def stage_rebuild():
    D = pickle.load(open(os.path.join(HERE, ".cache_incr.pkl"), "rb"))
    world, C, T, _ = prep()
    T["ctx"] = D["T_ctx"]
    S = C.S
    t0 = time.time()
    fdoors, frecs, frat = {}, {}, {}
    tb = []
    door_eq = rec_eq = 0
    for Y in range(Y0, Y1 + 1):
        t1 = time.perf_counter()
        st = cs7.build(C, Y)
        recs, _ = cs7.materialize(st)
        fdoors[Y] = doors_of(st, T, C, Y)
        tb.append((time.perf_counter() - t1) * 1000)
        frecs[Y] = {h: tuple(v[k] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9)) for h, v in recs.items()}
        frat[Y] = next(iter(recs.values()))[7]
        door_eq += fdoors[Y] == D["doors"][Y]
        rec_eq += frecs[Y] == D["years"][Y]
    t_v7 = time.time() - t0
    t0 = time.perf_counter()
    cur, events = batch_numbering(T, C, fdoors, None)
    t_batch = time.perf_counter() - t0
    addr_eq = [Y for Y in range(Y0, Y1 + 1) if cur[Y] == D["addr_by_year"][Y]]
    ie = sorted(map(ev_key, D["events"]))
    be = sorted(map(ev_key, events))
    ev_eq_years = [Y for Y in range(Y0, Y1 + 1) if [e for e in ie if e[0] == Y] == [e for e in be if e[0] == Y]]
    # 户籍从头生成
    built = {S.hid[i]: int(S.built[i]) for i in range(len(S.hid))}
    t0 = time.perf_counter()
    reg_eq, treg = [], []
    for Y in range(Y0, Y1 + 1):
        t1 = time.perf_counter()
        held = {v[0]: inst for inst, v in D["holders"][Y].items()}
        A = cur[Y]
        rows = {disp(T, A[h], Y): reg_row(Y, h, r, frat[Y], held, built, A[h]) for h, r in frecs[Y].items() if h in A}
        treg.append((time.perf_counter() - t1) * 1000)
        if reg_hash(rows) == D["reg_hashes"][Y]:
            reg_eq.append(Y)
    # 合成年：拆路 + 改名
    sy = D["synthetic"]
    T["sn"][sy["up"][2:]]["r"] = sy["sn_r71"]
    T["ctx"][Y1 + 1] = sy["ctx71"]
    fd = dict(fdoors)
    fd[Y1 + 1] = sy["door71"]
    cur2, ev2 = batch_numbering(T, C, fd, None)
    syn_eq = cur2[Y1 + 1] == sy["snap71"] and sorted(map(ev_key, [e for e in ev2 if e[0] == Y1 + 1])) == sorted(map(ev_key, sy["events71"]))
    res = {"v7_fresh_build_ms_per_year": {"median": round(float(np.median(tb)), 1), "max": round(max(tb), 1)},
           "v7_fresh_total_s": round(t_v7, 1),
           "door_tables_equal_years": door_eq, "v7_records_equal_years": rec_eq,
           "addr_equal_years": len(addr_eq), "addr_mismatch_years": [Y for Y in range(Y0, Y1 + 1) if Y not in addr_eq],
           "events_equal_years": len(ev_eq_years), "events_total_incr": len(ie), "events_total_batch": len(be),
           "registry_equal_years": len(reg_eq), "registry_mismatch_years": [Y for Y in range(Y0, Y1 + 1) if Y not in reg_eq],
           "batch_numbering_all_years_ms": round(t_batch * 1000, 1),
           "registry_full_build_ms_per_year": {"median": round(float(np.median(treg)), 1), "max": round(max(treg), 1)},
           "synthetic_AF71_street_remove_and_rename_incr_eq_batch": syn_eq, "synthetic_summary": sy["summary"]}
    json.dump(res, open(os.path.join(HERE, ".part_rebuild.json"), "w"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(res, ensure_ascii=False, default=str))


# ================================================================ 阶段三：输出、辖区门牌段、路由
def ranges_for(T, Y, members_hh, A, side_lists):
    """成员户 → 每街每侧的门牌区间列表（区间 = 本侧在册户门牌按门牌序连续的一段）。"""
    by = defaultdict(set)
    nostreet = 0
    for h in members_hh:
        a = A.get(h)
        if a is None:
            nostreet += 1
            continue
        by[a[0]].add(a[1])
    out = []
    for k in sorted(by, key=lambda k: name_at(T, k, Y)):
        for odd in (True, False):
            seq = side_lists[(k, odd)]
            runs, cur = [], None
            for n in seq:
                if n in by[k]:
                    if cur is None:
                        cur = [n, n]
                    else:
                        cur[1] = n
                elif cur is not None:
                    runs.append(cur)
                    cur = None
            if cur is not None:
                runs.append(cur)
            if runs:
                out.append([name_at(T, k, Y), k, "单" if odd else "双", runs])
    return out, nostreet


def range_text(r):
    nm, _, sd, runs = r
    parts = [(f"{a}–{b}" if a != b else f"{a}") for a, b in runs]
    return f"{nm} {'、'.join(parts)} 号{sd}"


def decode_ranges(rs, side_lists):
    got = set()
    for nm, k, sd, runs in rs:
        seq = side_lists[(k, sd == "单")]
        ix = {n: i for i, n in enumerate(seq)}
        for a, b in runs:
            for n in seq[ix[a]:ix[b] + 1]:
                got.add((k, n))
    return got


def stage_emit():
    D = pickle.load(open(os.path.join(HERE, ".cache_incr.pkl"), "rb"))
    RB = json.load(open(os.path.join(HERE, ".part_rebuild.json")))
    world, C, T, _ = prep()
    T["ctx"] = D["T_ctx"]
    S = C.S
    O, P = cast.load_rules()
    offs = {o["id"]: o for o in O["offices"]}
    built = {S.hid[i]: int(S.built[i]) for i in range(len(S.hid))}
    res = {"params": {"ODD_LEFT": ODD_LEFT, "affine_det": T["det"], "letters": "大写附号=位于基号之后插入；小写附号=位于本侧首户之前插入",
                      "ledger_street_name": "路·<道路id去掉 r_>"}}
    # ---------------- 1. 门牌：上游一致率、事件统计
    A_up = json.load(open(os.path.join(UP, "addr.json")))
    us = A_up["streets"]
    upc = {}
    for Y in (40, 50, 60, 70):
        c = Counter()
        A = D["addr_by_year"][Y]
        for h, rr in T["uprun"].items():
            if h not in A:
                continue
            u = [r for r in rr if r[2] <= Y < r[3] or (r[3] == 999 and Y >= r[2])]
            if not u:
                c["上游当年无街"] += 1
                continue
            k, n = u[0][0], u[0][1]
            c["可比"] += 1
            if A[h][0] == k:
                c["街同"] += 1
                if A[h][1] == str(n):
                    c["门牌全同"] += 1
                if (num_key(A[h][1])[0] % 2) == (n % 2):
                    c["单双同"] += 1
        c = dict(c)
        c["街一致率"] = round(c.get("街同", 0) / c["可比"], 4)
        c["门牌一致率(占可比)"] = round(c.get("门牌全同", 0) / c["可比"], 4)
        c["单双一致率(占街同)"] = round(c.get("单双同", 0) / max(1, c.get("街同", 0)), 4)
        upc[f"AF{Y}"] = c
    how = Counter(e[5] for e in D["events"] if e[2] == "新编")
    res["addresses"] = {
        "entities_by_year": {f"AF{Y}": len(D["addr_by_year"][Y]) for Y in SNAP},
        "households_by_year": {f"AF{Y}": len(D["years"][Y]) for Y in SNAP},
        "households_without_address": {f"AF{Y}": sum(1 for h in D["years"][Y] if h not in D["addr_by_year"][Y]) for Y in SNAP},
        "streets_with_numbers": {f"AF{Y}": len({a[0] for a in D["addr_by_year"][Y].values()}) for Y in SNAP},
        "suffix_numbers": {f"AF{Y}": sum(1 for e, a in D["addr_by_year"][Y].items() if not a[1].isdigit() and not e.startswith(("f:", "s:"))) for Y in SNAP},
        "events_by_kind_AF41_70": dict(Counter(e[2] for e in D["events"] if e[0] > Y0)),
        "events_by_kind_reason_AF41_70": dict(Counter(f"{e[2]}|{e[5] if e[2] != '改名' else '改名'}" for e in D["events"] if e[0] > Y0)),
        "new_number_how_AF40_70": dict(how),
        "renames": {Y: D["T_ctx"][Y]["renamed"] for Y in range(Y0 + 1, Y1 + 1) if D["T_ctx"][Y]["renamed"]},
        "upstream_agreement": upc,
    }
    # 3,168：上游刷新前后 AF60 街名变化（复现）× 本模型
    try:
        import subprocess
        old = json.loads(subprocess.run(["git", "-C", ROOT, "show", "04c3bec^:docs/living/xerolophos/facts_upstream/addr.json"],
                                        capture_output=True, check=True).stdout)

        def nm60(A_, idn):
            rr = A_["h"].get(idn)
            if not rr:
                return None
            for si, n, a, b in rr[1]:
                if a <= 60 < b or (b == 999 and 60 >= a):
                    return A_["streets"][si][0]      # 街的现名（与 SYNC 记录的 3,168 同口径）
            return None
        ids = set(old["h"]) | set(A_up["h"])
        chg = {i for i in ids if nm60(old, i) != nm60(A_up, i) and i in A_up["h"]}
        idmap = {str(int(x)): S.hid[i] for i, x in enumerate(S.idnum.tolist())}
        chg_h = {idmap[i] for i in chg if i in idmap}
        ours = {e[1] for e in D["events"] if e[0] <= 60 and e[2] in ("改名", "改址")}
        A40, A60 = D["addr_by_year"][40], D["addr_by_year"][60]
        nm_diff = {h for h in A60 if h in A40 and not h.startswith(("f:", "s:")) and name_at(T, A40[h][0], 40) != name_at(T, A60[h][0], 60)}
        res["upstream_3168"] = {
            "reproduced_count": len(chg), "definition": "上游门牌表刷新（04c3bec 前后两版 addr.json）中，同一栋房 AF60 所在街（按街现名）不同的户数；是事实版本差（上游地块挪位/街线重画），不是城里某年发生的改名",
            "model_AF60_street_key_differs_from_AF40": len({h for h in A60 if h in A40 and not h.startswith(("f:", "s:")) and A40[h][0] != A60[h][0]}),
            "in_ledger_houses": len(chg_h),
            "model_houses_with_rename_or_readdress_AF41_60": len(ours),
            "model_AF60_streetname_differs_from_AF40": len(nm_diff),
            "overlap_with_3168": len(chg_h & nm_diff),
            "jaccard": round(len(chg_h & nm_diff) / max(1, len(chg_h | nm_diff)), 4)}
    except Exception as ex:  # noqa
        res["upstream_3168"] = {"error": repr(ex)}
    # ---------------- 2/3. 户籍、衙署、辖区门牌段
    hist = [[e[0], e[1], e[2], disp(T, e[3], e[0] - 1) if e[3] else None,
             disp(T, e[4], e[0]) if e[4] else None, e[5]] for e in D["events"]]
    # 当年坊长 / 区长户（按事件年该户户籍；注销者按上一年）
    I = cast.I
    for row, e in zip(hist, D["events"]):
        Y, h = e[0], e[1]
        r = D["years"][Y].get(h) or D["years"].get(Y - 1, {}).get(h)
        if r is None or h.startswith(("f:", "s:")):
            row += [None, None]
            continue
        hd = D["holders"][Y]
        fh = hd.get(("fang_head", r[I["fang"]]))
        dh = hd.get(("district_head", r[I["d"]]))
        row += [fh[0] if fh else None, dh[0] if dh else None]
    raw = json.dumps({"_doc": "地址变更史：[年, 实体id, 类型(新编/改址/改名/注销), 旧门牌, 新门牌, 原因或编号方式, 当时坊长户, 当时区长户]。实体 id：房屋 hNNN；设施门 f:标签；兵营 s:结构id。——Hark（刘线）",
                      "rows": hist}, ensure_ascii=False, separators=(",", ":")).encode()
    with gzip.GzipFile(os.path.join(HERE, "addr_history.json.gz"), "wb", mtime=0) as f:
        f.write(raw)
    res["addr_history"] = {"rows": len(hist), "gzip_bytes": os.path.getsize(os.path.join(HERE, "addr_history.json.gz")),
                           "readdress_with_heads": sum(1 for r in hist if r[2] in ("改址", "改名") and r[6])}
    regst, seated_all, routes_all = {}, {}, {}
    for Y in SNAP:
        A = D["addr_by_year"][Y]
        rows = D["reg_snap"][Y]
        raw = json.dumps({"year": Y, "fields": REG_FIELDS, "ration_per_household": D["ration"][Y],
                          "_doc": "键 = 当年门牌（街名 + 号）。口粮在 v7 里是全城均分值，放在表头，不进每户行。——Hark（刘线）", "rows": rows},
                         ensure_ascii=False, separators=(",", ":")).encode()
        fn = os.path.join(HERE, f"registry_AF{Y}.json.gz")
        with gzip.GzipFile(fn, "wb", mtime=0) as f:
            f.write(raw)
        regst[f"AF{Y}"] = {"rows": len(rows), "json_bytes": len(raw), "gzip_bytes": os.path.getsize(fn),
                           "gzip_bytes_per_household": round(os.path.getsize(fn) / len(rows), 1),
                           "json_bytes_per_household": round(len(raw) / len(rows), 1),
                           "unique_keys_ok": len(rows) == sum(1 for h in D["years"][Y] if h in A)}
        # 本侧门牌序（只含户）
        side = defaultdict(list)
        for h, a in A.items():
            if h.startswith(("f:", "s:")):
                continue
            side[(a[0], D["doors"][Y][h][1])].append(a[1])
        side_lists = defaultdict(list, {k: sorted(v, key=num_key) for k, v in side.items()})
        seats = seat_structs(C, Y)
        hold = D["holders"][Y]
        mem = D["members"][Y]
        ep = max((y for y in D["eparch_seat"] if y <= Y))
        ep_h = D["eparch_seat"][ep]["house"]
        seated, rt_ok, nrange, maxrun = [], 0, [], 0
        inst_info = {}
        for o in sorted(O["offices"], key=lambda o: o["order"]):
            for (sc, k), hs in sorted(mem.items(), key=lambda x: str(x[0])):
                if sc != o["scope"]:
                    continue
                v = hold.get((o["id"], k))
                hh = v[0] if v else None
                oid = o["id"]
                if oid == "eparch":
                    se, how_ = ep_h, f"中心性代理：AF{ep} 全城调和中心性最高路口 {D['eparch_seat'][ep]['junction']} 旁最近房屋（假设，账本无官署结构）"
                elif oid in seats:
                    se, how_ = seats[oid]
                elif sc in ("parish", "arian_parish", "water", "grain", "watch"):
                    se, how_ = "f:" + k, "辖区设施本身（教堂/蓄水池/粮仓/城门或城墙段，v7 设施门口）"
                else:
                    se, how_ = hh, "任职户门牌"
                sa = A.get(se) if se else None
                if sc in ("city",):
                    rs, ns, rtxt = [], 0, ["全城"]
                    ok = True
                else:
                    rs, ns = ranges_for(T, Y, hs, A, side_lists)
                    got = decode_ranges(rs, side_lists)
                    ok = got == {A[h] for h in hs if h in A}
                    rtxt = [range_text(r) for r in rs]
                    nrange.append(sum(len(r[3]) for r in rs))
                rt_ok += ok
                ent = {"office": oid, "name": o["name"], "jurisdiction": k, "holder_house": hh,
                       "holder_person": v[1] if v else None, "holder_address": disp(T, A.get(hh), Y) if hh else None,
                       "seat_entity": se, "seat_address": disp(T, sa, Y), "seat_basis": how_,
                       "members": len(hs), "members_without_address": ns, "ranges_decode_ok": ok,
                       "range_count": sum(len(r[3]) for r in rs) if rs else (1 if sc == "city" else 0),
                       "ranges": rtxt}
                seated.append(ent)
                inst_info[(oid, k)] = (hh, v[1] if v else None, disp(T, sa, Y))
        seated_all[f"AF{Y}"] = seated
        res.setdefault("offices_seated", {})[f"AF{Y}"] = {
            "instances": len(seated), "vacant": sum(1 for s in seated if s["holder_house"] is None),
            "seat_missing_address": sum(1 for s in seated if s["seat_address"] is None),
            "seat_missing_address_nonvacant": sum(1 for s in seated if s["seat_address"] is None and s["holder_house"] is not None),
            "seat_basis": dict(Counter(s["seat_basis"].split("：")[0] for s in seated)),
            "ranges_decode_ok": rt_ok, "range_segments_median": float(np.median(nrange)), "range_segments_max": int(max(nrange)),
            "range_segments_total": int(sum(nrange)),
            "fang_head_ranges_median": float(np.median([s["range_count"] for s in seated if s["office"] == "fang_head"]))}
        routes_all[Y] = (A, rows, inst_info)
    json.dump({"_doc": "每个职位实例的衙署门牌与辖区门牌段。区间 = 本侧在册户门牌按门牌序连续一段（含首尾）。——Hark（刘线）",
               "years": seated_all}, open(os.path.join(HERE, "offices_seated.json"), "w"), ensure_ascii=False, indent=0)
    res["registry"] = regst
    # ---------------- 4. 路由
    LINES = {"民政": ["fang_head", "district_head", "eparch"], "教会(尼西亚)": ["parish_elder", "bishop_nicene"],
             "教会(阿里乌)": ["arian_elder", "bishop_arian"], "粮": ["granary_head", "annona", "eparch"],
             "水": ["water_head", "aquae", "eparch"], "哨": ["watch_head", "nykteparch", "eparch"], "行会": ["guild_head", "eparch"]}
    I = cast.I
    KEYF = {"city": lambda r: cast.CITY}

    def build_index(Y):
        A, rows, info = routes_all[Y]
        idx = {}
        for ad, row in rows.items():
            h = row[0]
            r = D["years"][Y][h]
            ln = {}
            for nm, chain in LINES.items():
                seq = []
                for oid in chain:
                    k = cast.jkey(offs[oid]["scope"], r)
                    if k is None:
                        seq = None
                        break
                    hh, per, sa = info.get((oid, k), (None, None, None))
                    seq.append((oid, k, hh, sa))
                if seq:
                    ln[nm] = seq
            att = {}
            for oid, o in offs.items():          # v8 的归属口径：每类职位按 jkey 取本户辖区（主教（尼西亚）是全城职位，阿里乌户也在其下）
                k = cast.jkey(o["scope"], r)
                if k is not None:
                    att[oid] = (k,) + tuple(info.get((oid, k), (None, None, None)))
            idx[ad] = (row, ln, att)
        return idx
    PROC = {p["id"]: p for p in P["procedures"]}

    def route(idx, info, Y, ad):
        row, ln, att = idx[ad]
        r = D["years"][Y][row[0]]
        procs = {}
        for pid, pr in PROC.items():
            procs[pid] = [(s["office"], s["power"], info.get((s["office"], cast.jkey(offs[s["office"]]["scope"], r)), (None, None, None))[2])
                          for s in pr["steps"]]
        return {"row": row, "lines": ln, "procedures": procs, "attribution": att}
    rq = {}
    samples_txt = []
    for Y in SNAP:
        A, rows, info = routes_all[Y]
        t0 = time.perf_counter()
        idx = build_index(Y)
        t_idx = time.perf_counter() - t0
        keys = sorted(rows)
        rnd = random.Random(13 + Y)
        q = [rnd.choice(keys) for _ in range(20000)]
        t0 = time.perf_counter()
        for ad in q:
            route(idx, info, Y, ad)
        t_q = (time.perf_counter() - t0) / len(q)
        # 与 v8 关系图核对：1000 户
        g = json.load(gzip.open(os.path.join(HERE, "..", "gov_frame_v8", f"graph_AF{Y}.json.gz")))
        nid = [n[0] for n in g["nodes"]]
        sub = defaultdict(dict)
        for a, b, t, s_, src in g["edges"]:
            if t == "隶属" and "→" not in s_:
                sub[nid[a]][s_] = nid[b]
        name2id = {o["name"]: o["id"] for o in O["offices"]}
        samp = rnd.sample(keys, 1000)
        agree = mism = 0
        mm = []
        for ad in samp:
            row, ln, att = idx[ad]
            h = row[0]
            ours = {oid: a[1] for oid, a in att.items() if a[1] and a[1] != h}
            chain_ok = all(att[oid][1] == hh for seq in ln.values() for oid, k, hh, sa in seq)
            theirs = {name2id[n]: x for n, x in sub.get(h, {}).items()}
            if ours == theirs and chain_ok:
                agree += 1
            else:
                mism += 1
                if len(mm) < 5:
                    mm.append({"addr": ad, "ours": ours, "v8": theirs})
        rq[f"AF{Y}"] = {"index_build_ms": round(t_idx * 1000, 1), "query_us_mean": round(t_q * 1e6, 2),
                        "v8_check_households": 1000, "v8_agree": agree, "v8_mismatch": mism, "mismatch_examples": mm}
        if Y == Y1:
            r3 = random.Random(70)
            picks = []
            for want in ("fang", "arian", "suffix"):
                for ad in r3.sample(keys, len(keys)):
                    row = rows[ad]
                    if want == "fang" and row[10] and row[10].startswith("fang_head"):
                        picks.append(ad); break
                    if want == "arian" and row[5] == "arian" and ad not in picks:
                        picks.append(ad); break
                    if want == "suffix" and not ad.split(" ")[-1][:-1].isdigit() and ad not in picks and row[10] is None:
                        picks.append(ad); break
            for ad in picks:
                samples_txt.append(render(ad, route(idx, info, Y, ad), offs, Y))
    res["routing"] = rq
    res["rebuild"] = RB
    tim = D["tim"]
    st_ = lambda v: {"median_ms": round(float(np.median(v)), 3), "p90_ms": round(float(np.percentile(v, 90)), 3), "max_ms": round(max(v), 3), "sum_ms": round(sum(v), 1)}
    res["incremental"] = {"v7_apply": st_(tim["v7_apply_ms"][1:]), "door_extract": st_(tim["door_extract_ms"]),
                          "addr_detect_O(N)_diff": st_(tim["addr_detect_ms"]), "addr_update_local": st_(tim["addr_update_ms"]),
                          "registry_update": st_(tim["reg_update_ms"][1:]),
                          "registry_rows_touched_per_year_median": int(np.median(D["touched"][1:])),
                          "materialize": st_(tim["materialize_ms"]), "stage_seconds": {k: round(v, 1) for k, v in D["t"].items()},
                          "note": "口粮是全城均分值，放在户籍表头，不进每户行"}
    res["eparch_seat"] = D["eparch_seat"]
    res["samples_text"] = samples_txt
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(HERE, "samples_AF70.txt"), "w").write("\n\n".join(samples_txt) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("samples_text",)}, ensure_ascii=False, default=str)[:6000])
    print("\n\n".join(samples_txt))


def render(ad, q, offs, Y):
    row = q["row"]
    L = [f"【AF{Y} 门牌 {ad}】房屋 {row[0]}，户主 {row[1]}；区 {row[3]}，坊 {row[2]}；{'阿里乌会众' if row[5] == 'arian' else '尼西亚堂区'} {row[4]}；"
         f"供水组 {row[6]}；配给点 {row[7]}；哨 {row[8]}；行会 {row[9]}；本户职位 {row[10] or '无'}"]
    for nm, seq in q["lines"].items():
        L.append(f"  {nm}：" + " → ".join(f"{offs[o]['name']}[{k if k != cast.CITY else '全城'}] 衙署 {sa or '—'}（任职户 {hh or '空缺'}）" for o, k, hh, sa in seq))
    if row[5] == "arian":
        a = q["attribution"]["bishop_nicene"]
        L.append(f"  另：按 v8 口径主教（尼西亚）为全城职位，本户亦在其下：衙署 {a[3]}（任职户 {a[1]}）")
    for pid, steps in q["procedures"].items():
        L.append(f"  流程 {pid}：" + " → ".join(f"{offs[o]['name']}({pw}) @ {sa or '（空缺）'}" for o, pw, sa in steps))
    return "\n".join(L)


if __name__ == "__main__":
    {"incr": stage_incr, "rebuild": stage_rebuild, "emit": stage_emit}[sys.argv[1]]()
