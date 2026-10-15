#!/usr/bin/env python3
"""gov_frame_v8 —— 政府架构规则 → 按规则填人（刘线）。

  offices.json     规则表（不含人）
  procedures.json  五条流程（职位序列 + 每步职权）
  cast.py          AF41–70 每年按资格与产生方式从 v7 户籍选人填职；增量 == 从头；检查；关系图

运行：python3 cast.py            （全部，约 1 分钟内）
依赖：numpy、scipy；按路径载入 ../city_system_v7_streets/city_system.py（未改动）。
——Hark（刘线）
"""
import gzip
import importlib.util
import json
import os
import sys
import time
import zlib
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
_sp = importlib.util.spec_from_file_location("cs7", os.path.join(HERE, "..", "city_system_v7_streets", "city_system.py"))
cs7 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(cs7)

Y0, Y1 = 40, 70
GRAPH_YEARS = (40, 50, 60, 70)
MODES = ("appoint", "elect", "hereditary", "seniority")
POWERS = ("批建", "征税", "配粮", "治安", "裁断", "任免", "上报")
RF = ("d", "fang", "water", "parish", "arian", "watch", "grain", "guild", "street")   # 户籍记录字段（取自 v7 materialize）
I = {f: i for i, f in enumerate(RF)}
CITY = "全城"


def jkey(scope, r):
    """辖区键：由 v7 户籍记录推出。None = 该户不属于此类辖区。"""
    if scope == "city":
        return CITY
    if scope == "arian_city":
        return CITY if r[I["arian"]] else None
    if scope == "district":
        return r[I["d"]]
    if scope == "guild":
        g = r[I["guild"]]
        return f"{r[I['d']]}×{g}" if g else None
    if scope == "parish":
        return None if r[I["arian"]] else r[I["parish"]]
    if scope == "arian_parish":
        return r[I["arian"]]
    return r[I[scope]]       # fang / watch / grain / water


RES_SCOPES = ("district", "guild", "fang", "parish", "arian_parish", "watch", "grain", "water")


def faith(r):
    return "arian" if r[I["arian"]] else "nicene"


# ================================================================ 规则载入与静态校验
def load_rules():
    O = json.load(open(os.path.join(HERE, "offices.json")))
    P = json.load(open(os.path.join(HERE, "procedures.json")))
    return O, P


def check_rules(O, P):
    """静态校验：职权词表、上级存在且层级更高、流程每步有职位持有该职权、实例可由户的辖区解析。不可达 → 报错。"""
    errs = []
    offs = {o["id"]: o for o in O["offices"]}
    for o in O["offices"]:
        for p in o["powers"]:
            if p not in POWERS:
                errs.append(f"{o['id']}: 未知职权 {p}")
        s = o["superior"]
        if s is not None:
            if s not in offs:
                errs.append(f"{o['id']}: 上级 {s} 不存在")
            elif offs[s]["level"] >= o["level"]:
                errs.append(f"{o['id']}: 上级 {s} 层级不高于本职")
        if o["selection"] not in MODES:
            errs.append(f"{o['id']}: 未知产生方式 {o['selection']}")
    for pr in P["procedures"]:
        for i, stp in enumerate(pr["steps"]):
            o = offs.get(stp["office"])
            if o is None:
                errs.append(f"{pr['id']} 第{i + 1}步：职位 {stp['office']} 不存在")
            elif stp["power"] not in o["powers"]:
                errs.append(f"{pr['id']} 第{i + 1}步：{o['name']} 不持有职权「{stp['power']}」→ 不可达")
            elif o["scope"] in ("arian_city", "arian_parish", "guild"):
                errs.append(f"{pr['id']} 第{i + 1}步：{o['name']} 的辖区不是每户都有 → 部分户不可达")
    return errs


# ================================================================ 户籍（v7 增量逐年）与关系图原料
def census():
    world = json.load(open(os.path.join(ROOT, "world.json")))
    C = cs7.prepare(world)
    S = C.S
    st = cs7.build(C, Y0)
    years, graw = {}, {}
    for Y in range(Y0, Y1 + 1):
        if Y > Y0:
            st.Y = Y
            for ev in cs7.events_for_year(C, Y):
                cs7.apply(st, ev)
        recs, _ = cs7.materialize(st)
        years[Y] = {h: tuple(v[k] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9)) for h, v in recs.items()}
        if Y in GRAPH_YEARS:
            graw[Y] = graph_raw(C, st)
    hidx = {S.hid[i]: i for i in range(len(S.hid))}
    built = {h: int(S.built[i]) for h, i in hidx.items()}
    idnum = {h: int(S.idnum[i]) for h, i in hidx.items()}
    persons = load_persons(world)
    return years, built, idnum, graw, persons


def graph_raw(C, st):
    """硬件节点：站着的设施门（井/水池、教堂、粮仓、城门/城墙段）与街网交点；每户门口最近交点。"""
    S = C.S
    TYPE = {"cistern": "井/水池", "church": "教堂", "granary": "粮仓", "gate": "城门", "wall": "城墙段"}
    fac = {}
    for k in sorted(st.sset):
        s = S.structs[k]
        for lb, kds, pts in C.fac.get(k, []):
            p = pts.mean(0)
            fac[lb] = (TYPE.get(s["type"], s["type"]), s["id"], round(float(p[0]), 1), round(float(p[1]), 1))
    jset = set()
    for s, d in st.inter.items():
        if s in st.segon:
            for j, kk in d.items():
                if j in st.segon:
                    jset.add(kk)
    hj = {}
    for h in st.rec:
        dr = st.hdoor.get(h)
        if dr is None:
            continue
        s, P = dr[0], dr[3]
        cands = [kk for j, kk in st.inter.get(s, {}).items() if j in st.segon]
        if cands:
            kk = min(cands, key=lambda q: ((q[0] / 100 - P[0]) ** 2 + (q[1] / 100 - P[1]) ** 2, q))
            hj[S.hid[h]] = f"j:{kk[0] / 100:.2f},{kk[1] / 100:.2f}"
    return {"fac": fac, "junctions": sorted(f"j:{k[0] / 100:.2f},{k[1] / 100:.2f}" for k in jset), "house_junction": hj}


def load_persons(world):
    """人物身份：账本 persons/ 或 world.json persons 中 address 恰为房屋 id 的在世人物。当前仓库无此数据 → 空。"""
    out = {}
    src = list(world.get("persons", []))
    pd = os.path.join(ROOT, "persons")
    if os.path.isdir(pd):
        for fn in sorted(os.listdir(pd)):
            if fn.endswith(".json"):
                src += json.load(open(os.path.join(pd, fn))).get("persons", [])
    for p in src:
        a = p.get("address")
        if a and a.startswith("h") and p.get("status", "alive") == "alive":
            out.setdefault(a, p["id"])
    return out


# ================================================================ 户主、居住年数
GEN = 25


def gen_of(h, Y, built):
    off = zlib.crc32(h.encode()) % GEN
    return (Y - built[h] + off) // GEN


def residency_table(years, built):
    """since[Y][h][scope] = 该户本类辖区标签最近一次改变的年份（AF40 假设自建成起未变）。"""
    since, prev = {}, {}
    for Y in range(Y0, Y1 + 1):
        cur = {}
        for h, r in years[Y].items():
            p = prev.get(h)
            d = {}
            for sc in RES_SCOPES:
                k = jkey(sc, r)
                if p is not None and p[0].get(sc) == k:
                    d[sc] = p[1][sc]
                else:
                    d[sc] = built[h] if (Y == Y0 or built[h] == Y) else Y
            cur[h] = ({sc: jkey(sc, r) for sc in RES_SCOPES}, d)
        since[Y] = {h: v[1] for h, v in cur.items()}
        prev = cur
    return since


# ================================================================ 填职引擎
class World:
    def __init__(self, years, built, idnum, since, persons):
        self.years, self.built, self.idnum, self.since, self.persons = years, built, idnum, since, persons


class Caster:
    """incremental=False：每年对全部职位做在任校验（从头重填的规范版本）；True：只校验受影响职位。两者出缺后的递补完全相同。"""

    def __init__(self, W, O, mode=None, incremental=False):
        self.W, self.incr = W, incremental
        self.offs = sorted(O["offices"], key=lambda o: o["order"])
        self.ob = {o["id"]: o for o in self.offs}
        self.mode = {o["id"]: (mode or o["selection"]) for o in self.offs}
        self.term = {o["id"]: (None if self.mode[o["id"]] == "hereditary" else o["term_years"]) for o in self.offs}
        self.holder = {}          # inst → [h, person, start, term_end]
        self.held = {}            # h → inst
        self.members = defaultdict(set)   # (scope, key) → {h}
        self.spells = []          # (office, start, end) 已结束的任期
        self.log = {}
        self.checked = []

    # ---- 资格
    def res(self, h, scope, Y):
        if scope in ("city", "arian_city"):
            return Y - self.W.built[h]
        return Y - self.W.since[Y][h][scope]

    def elig(self, o, h, Y, why=None):
        r = self.W.years[Y][h]
        e = o["eligibility"]
        f = e.get("faith")
        if f and f.get("status", "").startswith("enforced") and faith(r) != f["value"]:
            if why is not None:
                why["信仰不符"] += 1
            return False
        m = e.get("min_res_years")
        if m and self.res(h, m["scope"], Y) < m["value"]:
            if why is not None:
                why["居住年数不足"] += 1
            return False
        return True

    def person(self, h, Y):
        p = self.W.persons.get(h)
        return p if p else f"hh_{h}_g{gen_of(h, Y, self.W.built)}"

    # ---- 一年
    def step(self, Y, changed=None):
        recs = self.W.years[Y]
        if not self.incr or changed is None:
            self.members = defaultdict(set)
            for h, r in recs.items():
                for o in self.offs:
                    k = jkey(o["scope"], r)
                    if k is not None:
                        self.members[(o["scope"], k)].add(h)
        else:
            prevr = self.W.years[Y - 1]
            for h in changed:
                for sc in {o["scope"] for o in self.offs}:
                    a = jkey(sc, prevr[h]) if h in prevr else None
                    b = jkey(sc, recs[h]) if h in recs else None
                    if a != b:
                        if a is not None:
                            self.members[(sc, a)].discard(h)
                            if not self.members[(sc, a)]:
                                del self.members[(sc, a)]
                        if b is not None:
                            self.members[(sc, b)].add(h)
        exists = lambda inst: (self.ob[inst[0]]["scope"], inst[1]) in self.members
        # ---- 在任校验
        if not self.incr or changed is None:
            todo = list(self.holder)
        else:
            todo = {self.held[h] for h in changed if h in self.held}
            todo |= {i for i, v in self.holder.items() if v[3] is not None and v[3] <= Y}
        self.checked.append(len(todo))
        barred = set()
        for inst in sorted(todo):
            if inst not in self.holder:
                continue
            h, per, start, tend = self.holder[inst]
            o = self.ob[inst[0]]
            reason = None
            if not exists(inst):
                reason = "辖区消失"
            elif h not in recs:
                reason = "户毁"
            elif jkey(o["scope"], recs[h]) != inst[1]:
                reason = "迁出辖区"
            elif not self.elig(o, h, Y):
                reason = "不再合格"
            elif tend is not None and tend <= Y:
                reason = "任满"
                barred.add((inst, h))
            elif self.person(h, Y) != per:
                if self.mode[inst[0]] == "hereditary":
                    self.holder[inst][1] = self.person(h, Y)
                else:
                    reason = "户主更替"
            if reason:
                self.spells.append((inst[0], start, Y, reason))
                del self.holder[inst]
                del self.held[h]
        # ---- 出缺递补（规范顺序：order，辖区键）
        vac = sorted(((o["order"], o["id"], k) for o in self.offs for (sc, k) in self.members
                      if sc == o["scope"] and (o["id"], k) not in self.holder))
        empty = []
        for _, oid, k in vac:
            o = self.ob[oid]
            why = Counter()
            cands = []
            for h in self.members[(o["scope"], k)]:
                if h in self.held:
                    why["已任他职"] += 1
                elif ((oid, k), h) in barred:
                    why["任满不得连任"] += 1
                elif self.elig(o, h, Y, why):
                    cands.append(h)
            if not cands:
                empty.append({"office": oid, "key": k, "members": len(self.members[(o["scope"], k)]), "why": dict(why)})
                continue
            h = self.select(o, k, cands, Y)
            t = self.term[oid]
            self.holder[(oid, k)] = [h, self.person(h, Y), Y, None if t is None else Y + t]
            self.held[h] = (oid, k)
        self.log[Y] = {"empty": empty, "n_inst": sum(1 for o in self.offs for (sc, k) in self.members if sc == o["scope"])}

    def select(self, o, k, cands, Y):
        W, m = self.W, self.mode[o["id"]]
        sc = o["scope"]
        sen = lambda h: (W.built[h], W.idnum[h])
        if m in ("seniority", "hereditary"):
            return min(cands, key=sen)
        rk = lambda h: (-self.res(h, sc, Y), *sen(h))
        st = lambda h: W.years[Y][h][I["street"]] or "无街"
        if m == "appoint":
            sup = self.superior_holder(o, k, Y)
            ss = st(sup) if sup else None
            return min(cands, key=lambda h: (0 if ss and st(h) == ss else 1, *rk(h)))
        if m == "elect":
            votes = Counter(st(h) for h in self.members[(sc, k)])
            cs = set(cands)
            for s, _ in sorted(votes.items(), key=lambda x: (-x[1], x[0])):
                pool = [h for h in cs if st(h) == s]
                if pool:
                    return min(pool, key=rk)
            return min(cands, key=rk)
        raise ValueError(m)

    def superior_inst(self, o, k, Y):
        s = o["superior"]
        if s is None:
            return None
        so = self.ob[s]
        if so["scope"] in ("city", "arian_city"):
            return (s, CITY)
        if so["scope"] == "district":
            ds = Counter(self.W.years[Y][h][I["d"]] for h in self.members[(o["scope"], k)])
            return (s, min(ds.items(), key=lambda x: (-x[1], x[0]))[0])
        return None

    def superior_holder(self, o, k, Y):
        si = self.superior_inst(o, k, Y)
        v = self.holder.get(si) if si else None
        return v[0] if v else None

    def snapshot(self):
        return {f"{a}|{b}": tuple(v) for (a, b), v in sorted(self.holder.items())}


def changed_houses(W, Y):
    a, b = W.years[Y - 1], W.years[Y]
    ch = {h for h in set(a) | set(b) if a.get(h) != b.get(h)}
    ch |= {h for h in b if h in a and gen_of(h, Y, W.built) != gen_of(h, Y - 1, W.built)}
    return ch


# ================================================================ 运行一种配置
def run(W, O, P, mode=None, verify=True, keep=GRAPH_YEARS):
    full = Caster(W, O, mode, incremental=False)
    inc = Caster(W, O, mode, incremental=True) if verify else None
    eq, mism, kept, viol, dual = 0, [], {}, [], 0
    ostreet, ohouse = Counter(), Counter()
    office_years = vac_years = 0
    t_full = t_inc = 0.0
    cover = {}
    for Y in range(Y0, Y1 + 1):
        t0 = time.perf_counter()
        full.step(Y)
        t_full += time.perf_counter() - t0
        if inc:
            t0 = time.perf_counter()
            inc.step(Y, None if Y == Y0 else changed_houses(W, Y))
            t_inc += time.perf_counter() - t0
            if inc.snapshot() == full.snapshot() and inc.log[Y]["empty"] == full.log[Y]["empty"]:
                eq += 1
            else:
                mism.append(Y)
        # 检查：兼职、资格
        hs = [v[0] for v in full.holder.values()]
        dual += len(hs) - len(set(hs))
        for (oid, k), v in full.holder.items():
            o = full.ob[oid]
            r = W.years[Y].get(v[0])
            if r is None or jkey(o["scope"], r) != k or not full.elig(o, v[0], Y):
                viol.append((Y, oid, k, v[0]))
            ostreet[r[I["street"]] or "无街"] += 1
            ohouse[v[0]] += 1
        office_years += full.log[Y]["n_inst"]
        vac_years += len(full.log[Y]["empty"])
        cover[Y] = coverage(full, P, Y)
        if Y in keep:
            kept[Y] = {inst: list(v) for inst, v in full.holder.items()}
    # 任期
    ended = [e - s for _, s, e, _ in full.spells]
    cens = [Y1 + 1 - v[2] for v in full.holder.values()]
    tot = sum(ostreet.values())
    hh = sorted(ohouse.values(), reverse=True)
    res = {
        "vacancy_rate": round(vac_years / office_years, 4),
        "office_years": office_years, "vacant_office_years": vac_years,
        "mean_tenure_ended": round(sum(ended) / len(ended), 2) if ended else None,
        "n_spells_ended": len(ended),
        "mean_tenure_incl_censored_AF70": round((sum(ended) + sum(cens)) / (len(ended) + len(cens)), 2),
        "street_top5_share": round(sum(v for _, v in ostreet.most_common(5)) / tot, 4),
        "street_hhi": round(sum((v / tot) ** 2 for v in ostreet.values()), 4),
        "distinct_streets": len(ostreet),
        "distinct_houses_ever_held": len(ohouse),
        "house_top10_share": round(sum(hh[:10]) / tot, 4),
        "departures_by_reason": dict(Counter(x[3] for x in full.spells)),
        "dual_office_violations": dual, "eligibility_violations": len(viol),
        "procedure_full_coverage_mean": {p: round(sum(cover[Y][p] for Y in cover) / len(cover), 4) for p in cover[Y0]},
        "procedure_full_coverage_min": {p: round(min(cover[Y][p] for Y in cover), 4) for p in cover[Y0]},
    }
    if inc:
        res["incremental"] = {"years_equal": eq, "years": Y1 - Y0 + 1, "mismatch_years": mism,
                              "checked_per_year_incr_median": sorted(inc.checked[1:])[len(inc.checked[1:]) // 2],
                              "checked_per_year_full_median": sorted(full.checked[1:])[len(full.checked[1:]) // 2],
                              "ms_full": round(t_full * 1000, 1), "ms_incr": round(t_inc * 1000, 1)}
    return res, full, kept


def resolve(c, oid, r, Y):
    o = c.ob[oid]
    k = jkey(o["scope"], r)
    return None if k is None else (oid, k)


def coverage(c, P, Y):
    out = {}
    recs = c.W.years[Y]
    for pr in P["procedures"]:
        ok = 0
        for h, r in recs.items():
            if all((resolve(c, s["office"], r, Y) in c.holder) for s in pr["steps"]):
                ok += 1
        out[pr["id"]] = ok / len(recs)
    return out


# ================================================================ 关系图
def build_graph(W, O, P, Y, holder, raw):
    offs = {o["id"]: o for o in O["offices"]}
    recs = W.years[Y]
    held = {v[0]: inst for inst, v in holder.items()}
    nodes, nid = [], {}

    def node(i, t, a):
        nid[i] = len(nodes)
        nodes.append([i, t, a])
    for h in sorted(recs, key=lambda x: W.idnum[x]):
        r = recs[h]
        a = {"person": f"hh_{h}_g{gen_of(h, Y, W.built)}" if h not in W.persons else W.persons[h],
             "d": r[I["d"]], "street": r[I["street"]], "faith": faith(r)}
        if h in held:
            oid, k = held[h]
            a["office"] = offs[oid]["name"]
            a["jurisdiction"] = k
        node(h, "职位户" if h in held else "户", a)
    for lb, (t, sid, x, y) in sorted(raw["fac"].items()):
        node(lb, t, {"struct": sid, "xy": [x, y]})
    for j in raw["junctions"]:
        node(j, "路口", {})
    E = set()

    def edge(a, b, t, sub, src):
        if a in nid and b in nid and a != b:
            E.add((nid[a], nid[b], t, sub, src))
    # 隶属：户 → 本户各辖区职位持有户（规则）；职位 → 上级职位（规则）
    for h, r in recs.items():
        for oid, o in offs.items():
            k = jkey(o["scope"], r)
            v = holder.get((oid, k))
            if v:
                edge(h, v[0], "隶属", o["name"], "规则")
    for (oid, k), v in holder.items():
        o = offs[oid]
        s = o["superior"]
        if s:
            so = offs[s]
            if so["scope"] in ("city", "arian_city"):
                sk = CITY
            else:
                ds = Counter(recs[h][I["d"]] for h in recs if jkey(o["scope"], recs[h]) == k) if so["scope"] == "district" else None
                sk = min(ds.items(), key=lambda x: (-x[1], x[0]))[0] if ds else None
            sv = holder.get((s, sk))
            if sv:
                edge(v[0], sv[0], "隶属", f"{o['name']}→{so['name']}", "规则")
    # 辖区覆盖：设施类职位 → 本辖区设施（硬件推出）；坊长 → 本坊户门口路口（硬件推出）
    for (oid, k), v in holder.items():
        sc = offs[oid]["scope"]
        if sc in ("parish", "arian_parish", "watch", "grain", "water"):
            edge(v[0], k, "辖区覆盖", offs[oid]["name"], "硬件推出")
        if sc == "fang":
            for h, r in recs.items():
                if r[I["fang"]] == k and h in raw["house_junction"]:
                    edge(v[0], raw["house_junction"][h], "辖区覆盖", "坊长", "硬件推出")
    # 流程上下游：每户的流程实例，相邻两步持有户相连（规则），去重
    for pr in P["procedures"]:
        for h, r in recs.items():
            seq = []
            for s in pr["steps"]:
                o = offs[s["office"]]
                v = holder.get((s["office"], jkey(o["scope"], r)))
                seq.append(v[0] if v else None)
            for a, b in zip(seq, seq[1:]):
                if a and b:
                    edge(a, b, "流程上下游", pr["name"], "规则")
    # 共享设施：户 → 所用设施（走街最近，硬件推出；阿里乌教堂依信仰代理 → 假设）；户 → 门口路口
    for h, r in recs.items():
        edge(h, r[I["water"]], "共享设施", "用水", "硬件推出")
        edge(h, r[I["grain"]], "共享设施", "领粮", "硬件推出")
        edge(h, r[I["watch"]], "共享设施", "守哨", "硬件推出")
        if r[I["arian"]]:
            edge(h, r[I["arian"]], "共享设施", "礼拜", "假设")
        else:
            edge(h, r[I["parish"]], "共享设施", "礼拜", "硬件推出")
        if h in raw["house_junction"]:
            edge(h, raw["house_junction"][h], "共享设施", "门口路口", "硬件推出")
    E = sorted(E)
    g = {"year": Y, "_doc": "nodes[i]=[id,类型,属性]；edges=[源下标,目标下标,类型,细类,来源]；来源∈{硬件推出,规则,假设}。同一设施的两户经设施节点即「共享」。——Hark（刘线）",
         "nodes": nodes, "edges": [list(e) for e in E]}
    nh = sum(1 for n in nodes if n[1] in ("户", "职位户"))
    deg = Counter()
    for a, b, *_ in E:
        deg[a] += 1
        deg[b] += 1
    hdeg = sum(deg[i] for i, n in enumerate(nodes) if n[1] in ("户", "职位户"))
    st = {"nodes": len(nodes), "households": nh, "facilities": len(raw["fac"]), "junctions": len(raw["junctions"]),
          "edges": len(E), "edges_per_household_mean": round(hdeg / nh, 2),
          "edges_by_type": dict(Counter(e[2] for e in E)), "edges_by_source": dict(Counter(e[4] for e in E))}
    return g, st


# ================================================================ 主程序
def main():
    t0 = time.time()
    O, P = load_rules()
    errs = check_rules(O, P)
    # 自检：抽掉一个职权，静态校验必须报不可达
    O2 = json.loads(json.dumps(O))
    for o in O2["offices"]:
        if o["id"] == "district_head":
            o["powers"].remove("批建")
    selftest = check_rules(O2, P)
    if errs:
        print("规则校验失败：", errs)
        sys.exit(1)
    years, built, idnum, graw, persons = census()
    since = residency_table(years, built)
    W = World(years, built, idnum, since, persons)
    t_census = time.time() - t0
    out = {"rules_check": {"errors": errs, "selftest_remove_district_批建_errors": selftest},
           "persons_from_ledger": len(persons), "households_by_year": {Y: len(years[Y]) for Y in (40, 50, 60, 70)}}
    res, full, kept = run(W, O, P, None, verify=True)
    out["default"] = res
    out["default"]["empty_by_year"] = {Y: full.log[Y]["empty"] for Y in range(Y0, Y1 + 1)}
    out["default"]["empty_count_by_year"] = {Y: len(full.log[Y]["empty"]) for Y in range(Y0, Y1 + 1)}
    out["default"]["instances_by_year"] = {Y: full.log[Y]["n_inst"] for Y in range(Y0, Y1 + 1)}
    out["default"]["instances_by_office_AF70"] = dict(Counter(i[0] for i in full.holder) + Counter(e["office"] for e in full.log[Y1]["empty"]))
    es = Counter()
    for Y in range(Y0, Y1 + 1):
        for e in full.log[Y]["empty"]:
            es[f"{e['office']}|{max(e['why'], key=e['why'].get) if e['why'] else '无户'}|{'单户辖区' if e['members'] == 1 else '多户辖区'}"] += 1
    out["default"]["empty_summary_office_mainreason_size"] = dict(es.most_common())
    out["modes"] = {}
    for m in MODES:
        r, _, _ = run(W, O, P, m, verify=True, keep=())
        out["modes"][m] = r
    out["graphs"] = {}
    for Y in GRAPH_YEARS:
        g, st = build_graph(W, O, P, Y, kept[Y], graw[Y])
        fn = os.path.join(HERE, f"graph_AF{Y}.json.gz")
        raw = json.dumps(g, ensure_ascii=False, separators=(",", ":")).encode()
        with gzip.GzipFile(fn, "wb", mtime=0) as f:
            f.write(raw)
        st["json_bytes"] = len(raw)
        st["gzip_bytes"] = os.path.getsize(fn)
        out["graphs"][f"AF{Y}"] = st
    # AF70 职位名册样例（默认配置）
    out["roster_AF70_city_level"] = {f"{a}|{b}": v for (a, b), v in sorted(kept[70].items()) if b == CITY}
    out["seconds"] = {"census": round(t_census, 1), "total": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=str)
    brief = {k: out[k] for k in ("rules_check", "persons_from_ledger", "households_by_year", "seconds")}
    brief["default"] = {k: v for k, v in out["default"].items() if not k.startswith("empty_by")}
    brief["modes"] = out["modes"]
    brief["graphs"] = out["graphs"]
    print(json.dumps(brief, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
