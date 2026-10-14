# -*- coding: utf-8 -*-
"""economy_v14：门牌户籍 + 官府之上的经济活动体系（地下数据管线，不做页面）。——Hark（刘线）

按路径只读载入：
  ../yamen_v13/yamen.py 与它的 .cache_incr.pkl（v7 逐年户籍字段、门牌、v8 填职；缺缓存时先跑 `python3 yamen.py incr`）
  ../gov_frame_v8（经 yamen 载入 cast.py / offices.json）
  ../rules_v4_fiscal/out/fiscal_city.json（v4 参数、账本工程造价表、逐年层级账）
  ../rules_v0/rules.json（v2 所用的房东 / 债规则参数）
  docs/living/xerolophos/facts_upstream/houses.json（第 9 栏 = 地块所在街区功能）
不改任何已有目录。

运行：python3 economy.py run      # AF40–70 逐年全量计算 + 输出（≈1–2 分钟）
      python3 economy.py events   # 4 个账本事件：反事实 vs 事件、增量 == 重建、耗时
"""
import os, sys, json, gzip, time, pickle, hashlib, importlib.util, collections, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, ".."))
UP = os.path.join(ROOT, "docs", "living", "xerolophos", "facts_upstream")


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.path.insert(0, os.path.dirname(path))
    sp.loader.exec_module(m)
    return m


Y0, Y1 = 40, 70
SNAP = (40, 50, 60, 70)
EVENT_YEARS = (48, 55, 57, 62)

# ------------------------------------------------------------------ 参数
V4 = json.load(open(os.path.join(EXP, "rules_v4_fiscal", "out", "fiscal_city.json")))
P4 = V4["params"]                       # v4：tau rho delta omega alpha beta gamma eps kappa alms sigma remit V_h comp reloc levy
RULES0 = json.load(open(os.path.join(EXP, "rules_v0", "rules.json")))
LL = RULES0["landlord"]                 # v2/v0：cap 6
DEBT = RULES0["debt"]                   # v2/v0：cap 4，years 4，放债 = 有房的面包师/酒馆老板


def food_cap(Y):                        # 账本（chronicle），与 v4/v7 同式
    return 193202 if Y >= 55 else 173202 if Y >= 46 else 153202


A = dict(                               # 本轮新假设（全部可调）
    head_tax=0.2,        # 人头税：每户每年 0.2 份（v4 没有人头税，新假设）
    q_bread=0.6, q_water=0.4, q_craft=0.5, q_harbor=0.3,   # 户需求表：每户每年按价 1 计的量（口粮另配，不在此）
    fine_mult=3.0,       # 体面户手工 / 港货需求倍数
    floor=0.3,           # 预算不足时购买至少保留基本量的 30%
    k_price=0.002,       # 价格 = 1 + k × 市场到货源（粮仓 / 港口）的直线距离（账本单位）
    k_water=0.004,       # 水价 = 1 + k × 户到其 v7 供水设施的直线距离
    cost_share={2: 0.20, 3: 0.30, 4: 0.30, 5: 0.50},       # 卖方进货 / 燃料 / 原料付城外（面包 20%、手工 30%、港货 50%）
    export={4: 6.0, 5: 4.0},   # 城外付：作坊出口 6.0、港货商转口佣金 4.0（每户每年，新假设）
    court={4: 12.0, 7: 12.0, 5: 8.0, 3: 4.0, 2: 4.0},   # 首都消费城：皇库在城内的宫廷/官署/驻军采购，按雇主生计每户每年（新假设）
    muni_reserve=20000.0, muni_draw=0.5,   # 城市长官公役：库存超过 20,000 的部分每年拿一半雇无主雇工（新假设）
    wage=3.0, wage_share=0.5,   # 雇主上年营收的 50% 用于雇工，每个工位每年 3.0 份
    house_cost=10.0,     # 新房造价（房东付承建营造户）
    c_in=2.0,            # 迁入户带来的现钱
    cash0={8: 30.0, "seller": 5.0, "other": 3.0},          # AF40 初始现钱
    treasury0={"eparch": 20000.0, "bishop_nicene": 3000.0, "bishop_arian": 0.0},
    stipend_imperial={"eparch": 30.0, "annona": 10.0, "aquae": 10.0, "nykteparch": 10.0},   # 皇库 → 任职户
    stipend_eparch={"granary_head": 2.0, "water_head": 2.0, "watch_head": 2.0},             # 城市长官 → 任职户
    stipend_bishop=5.0,  # 主教库 → 主教户
    soldier_imperial=2.0, soldier_pay=3.0,                   # 兵饷：皇库 2.0 + 城市长官 σ(v4)=1.0 → 夜巡长 → 兵户 3.0
    alms_budget_share=0.6, alms_reserve_draw=0.5,
    poverty=3.0,         # 贫困线：基本篮子（价 1）1.8 + 租 1.0 + 人头税 0.2
    builders_per_work=20,
    R_harbor=25.0, R_market=20.0, R_gate=20.0, R_cistern=15.0, R_barracks=15.0,
)

LIV = ["雇工", "码头脚夫", "面包", "手工铺", "作坊", "港货商", "运水人", "营造", "体面户", "兵户"]
SELL_GOOD = {2: "bread", 3: "craft", 4: "craft", 5: "harbor", 6: "water"}
EMPLOYERS = (2, 3, 4, 5, 7)
WORKERS = (0, 1)
FN_SRC = ["上游第9栏", "同街分布(假设)", "同坊分布(假设)", "距离先验(假设)"]
FNS = ["homes", "shops", "market", "workshop", "water", "fine", "planned", "garrison"]

TYPES = ["公役工钱", "宫廷采购(皇库付)", "口粮调拨", "口粮下仓", "口粮配给",
         "房税", "人头税", "行会钱", "税钱上缴(坊长→区长)", "税钱上缴(区长→城市长官)", "行会钱上缴(行会头→城市长官)", "上交皇库",
         "奉献", "奉献截留(长老)", "奉献上缴(→主教)", "施舍",
         "租金", "买卖:面包", "买卖:水", "买卖:手工", "买卖:港货", "进货/原料(付城外)", "出口(城外付)",
         "工钱", "俸给", "兵饷", "借贷", "还款", "拆迁补偿", "搬迁费", "建设:新房", "建设:公共工程", "修水摊派",
         "迁入带钱", "迁出带钱"]
TI = {t: i for i, t in enumerate(TYPES)}
GRAIN_T = {TI["口粮调拨"], TI["口粮下仓"], TI["口粮配给"]}
RULES = ["账本 food_cap（chronicle）", "v7 口粮全城均分 + 配给点=最近粮仓（走街）",
         "v4 tau=0.5/栋 房主交", "新假设 人头税 0.2/户", "v4 delta=0.3/行会户", "v4 alpha=0.10 坊长截留", "v4 beta=0.10 区长截留",
         "v4 gamma=0.10 行会头截留", "v4 remit=0.5 上交皇库", "v4 omega=0.3/教区户", "v4 eps=0.05 长老截留", "v4 alms=1.0/贫户（预算不足按比例）",
         "v4 rho=1.0/租户；v2 房东=同街住得最久有房户 cap6（一屋一户，AF41 后建房=租户，假设）",
         "户需求表×市场价（新假设）", "卖方成本付城外（新假设）", "作坊出口（新假设）",
         "工钱：同行会/同街优先，再同区（新假设）", "俸给（新假设）", "兵饷 v4 sigma=1.0 + 皇库（假设）",
         "v2 债：灾/亏户向同区有房面包师/体面户借，cap4，4 年还清，无息（假设）",
         "v4 comp=0.5×V_h 给房主", "v4 reloc=1.0/租户", "新房造价 10（假设）付最近同区营造户",
         "v4 账本工程造价×出资方（WORK_PAYER）→ 最近 20 户营造户", "v4 levy=1.0/户（新池供水组）", "迁入/迁出（外部源汇，假设）", "首都消费城：皇库城内采购按雇主生计定额（新假设）", "城市长官公役：库存超 20,000 部分的一半雇无主雇工，按区无主人数分额、区内按门牌序（新假设）"]
RI = {r: i for i, r in enumerate(RULES)}

EXT = ["皇库", "皇家粮运", "城外贸易", "城外商人", "迁入", "迁出"]


def stable_u(ids, salt):
    """确定性伪随机 [0,1)：由房屋编号与盐算出。"""
    x = (np.asarray(ids, np.uint64) * np.uint64(2654435761) + np.uint64(salt * 97531)) % np.uint64(2 ** 32)
    x = (x ^ (x >> np.uint64(13))) * np.uint64(1274126177) % np.uint64(2 ** 32)
    return (x % np.uint64(1000003)).astype(np.float64) / 1000003.0


# ================================================================ 硬件
class HW:
    def __init__(self):
        t0 = time.time()
        self.ym = _load("yamen_e14", os.path.join(EXP, "yamen_v13", "yamen.py"))
        self.world, self.C, self.T, _ = self.ym.prep()
        D = pickle.load(open(os.path.join(EXP, "yamen_v13", ".cache_incr.pkl"), "rb"))
        self.years, self.ration, self.addr, self.holders = D["years"], D["ration"], D["addr_by_year"], D["holders"]
        self.eparch_house = D["eparch_seat"][Y0]["house"]
        S = self.C.S
        self.hid = list(S.hid); self.NH = len(self.hid)
        self.g = {h: i for i, h in enumerate(self.hid)}
        self.idnum = np.array([int(h[1:]) for h in self.hid], np.int64)
        self.xy = np.asarray(S.xy, float)
        self.built = np.asarray(S.built, np.int64)
        self.dest = np.asarray(S.destroyed, np.int64)
        self.st = {}
        for s in self.world["structures"]:
            c = np.asarray(s["geom"]["coords"], float).reshape(-1, 2)
            self.st[s["id"]] = dict(type=s["type"], built=s["built"], dest=s["destroyed"] if s["destroyed"] is not None else 10 ** 9,
                                    xy=c.mean(0), faction=s.get("faction"))
        self.works = V4["works"]
        self.t_load = time.time() - t0

    def standing(self, Y, types, drop=()):
        return [k for k, s in self.st.items() if s["type"] in types and s["built"] <= Y < s["dest"] and k not in drop]

    def door(self, h, Y):
        a = self.addr[Y].get(h)
        return None if a is None else self.ym.disp(self.T, a, Y)

    def facility_door(self, key, Y):
        a = self.addr[Y].get(key)
        return self.ym.disp(self.T, a, Y) if a is not None else "无门牌"


# ================================================================ 生计（每栋房屋一户，静态：首次在册那年的硬件定下）
def livelihoods(H):
    up = json.load(open(os.path.join(UP, "houses.json")))["houses"]
    known = {}
    for u in up:
        g = H.g.get(f"h{u[0]}")
        if g is not None and u[8] in FNS:
            known[g] = FNS.index(u[8])
    NH = H.NH
    fn = np.full(NH, -1); src = np.full(NH, -1)
    first = np.full(NH, -1)
    street0, fang0 = [None] * NH, [None] * NH
    for Y in range(Y0, Y1 + 1):
        for h, r in H.years[Y].items():
            g = H.g[h]
            if first[g] < 0:
                first[g] = Y; street0[g] = r[8]; fang0[g] = r[1]
    for g, f in known.items():
        fn[g] = f; src[g] = 0
    # 同街 / 同坊已知分布
    def dist_by(keys):
        c = collections.defaultdict(lambda: np.zeros(len(FNS)))
        for g, f in known.items():
            if first[g] >= 0 and keys[g] is not None:
                c[keys[g]][f] += 1
        return c
    bys, byf = dist_by(street0), dist_by(fang0)
    reg = [g for g in range(NH) if first[g] >= 0]
    u = stable_u(H.idnum, 1)
    for g in reg:
        if fn[g] >= 0:
            continue
        for tab, key, code in ((byf, fang0[g], 2), (bys, street0[g], 1)):
            v = tab.get(key)
            if v is not None and v.sum() >= 8:
                fn[g] = int(np.searchsorted(np.cumsum(v / v.sum()), u[g], side="right")); src[g] = code
                break
    # 距离先验（首次在册年份在立的设施）
    left = [g for g in reg if fn[g] < 0]
    Yf = first[left] if left else np.array([])
    for Y in sorted(set(Yf.tolist())):
        gs = np.array([g for g in left if first[g] == Y])
        P = H.xy[gs]
        def dmin(types):
            ks = H.standing(Y, types)
            if not ks:
                return np.full(len(gs), 1e9)
            Q = np.array([H.st[k]["xy"] for k in ks])
            return np.min(np.hypot(P[:, None, 0] - Q[None, :, 0], P[:, None, 1] - Q[None, :, 1]), axis=1)
        dm, dh, dg, dc, db = dmin(("market", "forum")), dmin(("harbor", "warehouse")), dmin(("gate",)), dmin(("cistern",)), dmin(("barracks",))
        W = np.tile(np.array([.70, .12, .0, .06, .03, .03, .04, .02]), (len(gs), 1))
        W[dm <= A["R_market"], 1] += .15; W[dm <= A["R_market"], 2] += .10
        W[dh <= A["R_harbor"], 1] += .08; W[dh <= A["R_harbor"], 3] += .04
        W[dg <= A["R_gate"], 1] += .06
        W[dc <= A["R_cistern"], 4] += .10
        W[db <= A["R_barracks"], 7] += .30
        W /= W.sum(1, keepdims=True)
        c = np.cumsum(W, 1)
        fn[gs] = (c < u[gs, None]).sum(1); src[gs] = 3
    fn = np.minimum(fn, len(FNS) - 1)
    # 功能 → 生计
    u2 = stable_u(H.idnum, 2)
    dh_all = np.full(NH, 1e9)
    for Y in sorted(set(first[reg].tolist())):
        gs = np.array([g for g in reg if first[g] == Y])
        ks = H.standing(Y, ("harbor", "warehouse"))
        Q = np.array([H.st[k]["xy"] for k in ks])
        dh_all[gs] = np.min(np.hypot(H.xy[gs, None, 0] - Q[None, :, 0], H.xy[gs, None, 1] - Q[None, :, 1]), axis=1)
    near_h = dh_all <= A["R_harbor"]
    liv = np.full(NH, -1)
    F = {f: i for i, f in enumerate(FNS)}
    m = fn == F["market"]; liv[m] = np.where(u2[m] < .4, 2, np.where(u2[m] < .7, 3, 5))
    m = fn == F["shops"]; liv[m] = np.where(near_h[m], 5, np.where(u2[m] < .45, 2, 3))
    liv[fn == F["workshop"]] = 4; liv[fn == F["water"]] = 6; liv[fn == F["fine"]] = 8
    liv[fn == F["garrison"]] = 9; liv[fn == F["planned"]] = 7
    m = fn == F["homes"]; liv[m] = np.where(near_h[m], 1, 0)
    liv[first < 0] = -1
    return dict(fn=fn, src=src, liv=liv, first=first)


# ================================================================ 一年
class Year:
    """一年的硬件视图（可带反事实修改）。"""
    def __init__(self, H, Y, mod=None):
        mod = mod or {}
        self.Y = Y
        recs = dict(H.years[Y])
        for h, r in mod.get("add", {}).items():
            recs[h] = r
        for h, r in mod.get("set", {}).items():
            if h in recs:
                recs[h] = r
        self.recs = recs
        self.alive = np.array(sorted(H.g[h] for h in recs), np.int64)
        self.drop = set(mod.get("drop_structs", ()))
        self.addr = dict(H.addr[Y]); self.addr.update(mod.get("addr", {}))
        self.food = mod.get("food_cap", food_cap(Y))
        self.ration = self.food / len(self.alive)
        self.holders = H.holders[Y]
        self.mod = mod


class State:
    def __init__(self, H, L):
        n = H.NH
        self.cash = np.zeros(n)
        self.inst = collections.defaultdict(float)
        self.landlord = np.full(n, -1)
        self.loans = []              # [lender g, borrower g, remaining, installment, year]
        self.rev_prev = np.zeros(n)
        self.inc_prev = np.zeros(n)
        self.alive_prev = np.zeros(0, np.int64)
        self.door_prev = {}

    def copy(self):
        s = State.__new__(State)
        s.cash = self.cash.copy(); s.inst = collections.defaultdict(float, self.inst); s.landlord = self.landlord.copy()
        s.loans = [list(x) for x in self.loans]; s.rev_prev = self.rev_prev.copy(); s.inc_prev = self.inc_prev.copy()
        s.alive_prev = self.alive_prev.copy(); s.door_prev = dict(self.door_prev)
        return s


class Rows:
    def __init__(self):
        self.t, self.a, self.b, self.v, self.r, self.o, self.k = [], [], [], [], [], [], []

    def add(self, t, a, b, v, r, o, k):
        v = np.broadcast_to(np.asarray(v, float), np.shape(a) if np.ndim(a) else np.shape(b) if np.ndim(b) else (1,))
        n = len(v)
        f = lambda x, dt: np.broadcast_to(np.asarray(x, dt), (n,)).copy()
        self.t.append(f(TI[t], np.int16)); self.a.append(f(a, np.int64)); self.b.append(f(b, np.int64))
        self.v.append(np.asarray(v, float).copy()); self.r.append(f(RI[r], np.int16)); self.o.append(f(o, np.int64)); self.k.append(f(k, np.int8))

    def cat(self):
        if not self.t:
            z = np.zeros(0)
            return dict(t=z.astype(np.int16), a=z.astype(np.int64), b=z.astype(np.int64), v=z, r=z.astype(np.int16), o=z.astype(np.int64), k=z.astype(np.int8))
        R = dict(t=np.concatenate(self.t), a=np.concatenate(self.a), b=np.concatenate(self.b), v=np.concatenate(self.v),
                 r=np.concatenate(self.r), o=np.concatenate(self.o), k=np.concatenate(self.k))
        m = R["v"] > 1e-12
        return {x: y[m] for x, y in R.items()}


class Econ:
    def __init__(self, H):
        self.H = H
        self.L = livelihoods(H)
        self.liv = self.L["liv"]
        self.inst_keys = []
        self.inst_ix = {}
        for e in EXT:
            self.I(("外", e))
        u3 = stable_u(H.idnum, 3)
        self.hseed = (u3 * 1e6).astype(np.int64)

    def I(self, key):
        if key not in self.inst_ix:
            self.inst_ix[key] = self.H.NH + len(self.inst_keys)
            self.inst_keys.append(key)
        return self.inst_ix[key]

    # ---------------------------------------------------------- 年视图派生量
    def derive(self, yr, S):
        H = self.H; Y = yr.Y
        al = yr.alive
        r = [yr.recs[H.hid[g]] for g in al]
        d = dict(
            d=np.array([x[0] for x in r], object), fang=np.array([x[1] for x in r], object),
            water=np.array([x[2] for x in r], object), parish=np.array([x[3] or "" for x in r], object),
            arian=np.array([x[4] or "" for x in r], object), grain=np.array([x[6] for x in r], object),
            guild=np.array([x[7] or "" for x in r], object), street=np.array([x[8] or "无街" for x in r], object))
        d["liv"] = self.liv[al]
        # 门牌序
        keys = []
        for g in al:
            a = yr.addr.get(H.hid[g])
            keys.append((a[0], H.ym.num_key(a[1])) if a else ("~", (10 ** 9, 0, 0, "")))
        order = sorted(range(len(al)), key=lambda i: (keys[i], int(al[i])))
        rank = np.empty(len(al), np.int64); rank[np.array(order, np.int64)] = np.arange(len(al))
        d["door_rank"] = rank
        # 市场节点
        mk = H.standing(Y, ("market", "forum", "harbor", "warehouse"), yr.drop)
        MX = np.array([H.st[k]["xy"] for k in mk])
        P = H.xy[al]
        D = np.hypot(P[:, None, 0] - MX[None, :, 0], P[:, None, 1] - MX[None, :, 1])
        d["mk"] = mk; d["node"] = np.argmin(D, 1); d["dist_market"] = D[np.arange(len(al)), d["node"]]
        gr = H.standing(Y, ("granary",), yr.drop); GX = np.array([H.st[k]["xy"] for k in gr])
        hb = [k for k in mk if H.st[k]["type"] in ("harbor", "warehouse")]; HX = np.array([H.st[k]["xy"] for k in hb])
        dmg = np.min(np.hypot(MX[:, None, 0] - GX[None, :, 0], MX[:, None, 1] - GX[None, :, 1]), 1)
        dmh = np.min(np.hypot(MX[:, None, 0] - HX[None, :, 0], MX[:, None, 1] - HX[None, :, 1]), 1)
        d["p_bread"] = 1 + A["k_price"] * dmg; d["p_harbor"] = 1 + A["k_price"] * dmh; d["p_craft"] = np.ones(len(mk))
        d["MX"] = MX
        wx = np.array([H.st[w]["xy"] if w in H.st else P[i] for i, w in enumerate(d["water"])])
        d["dist_water"] = np.hypot(*(P - wx).T); d["p_water"] = 1 + A["k_water"] * d["dist_water"]
        gx = np.array([H.st[w]["xy"] for w in d["grain"]])
        d["dist_grain"] = np.hypot(*(P - gx).T)
        d["owner"] = H.built[al] <= Y0
        return d

    # ---------------------------------------------------------- 房东（v2 规则，持续：房东还在就沿用）
    def landlords(self, yr, S, dv):
        H = self.H; al = yr.alive; pos = {int(g): i for i, g in enumerate(al)}
        ll = S.landlord.copy()
        alive_set = set(pos)
        load = collections.Counter(int(x) for g, x in zip(range(H.NH), ll) if x >= 0 and g in alive_set and x in alive_set)
        own_idx = np.nonzero(dv["owner"])[0]
        by_st = collections.defaultdict(list)
        for i in own_idx[np.lexsort((H.idnum[al[own_idx]], H.built[al[own_idx]]))]:
            by_st[dv["street"][i]].append(int(al[i]))
        by_d = collections.defaultdict(list)
        for i in own_idx:
            by_d[dv["d"][i]].append(int(al[i]))
        need = [i for i in np.nonzero(~dv["owner"])[0] if ll[al[i]] < 0 or int(ll[al[i]]) not in alive_set]
        need.sort(key=lambda i: H.idnum[al[i]])
        for i in need:
            g = int(al[i]); best = -1
            for o in by_st.get(dv["street"][i], ()):
                if load[o] < LL["cap"]:
                    best = o; break
            if best < 0:
                c = [o for o in by_d.get(dv["d"][i], ()) if load[o] < LL["cap"]]
                if c:
                    cx = H.xy[c]; dd = np.hypot(*(cx - H.xy[g]).T)
                    best = c[int(np.lexsort((H.idnum[c], dd))[0])]
            ll[g] = best
            if best >= 0:
                load[best] += 1
        for g in range(H.NH):
            if g not in alive_set:
                ll[g] = -1
        return ll

    # ---------------------------------------------------------- 主计算
    def step(self, yr, S, inc=None):
        """一年全量（inc=None）或增量（inc = dict(cache=上次结果, dirty_a=户掩码, dirty_d=区集合, dirty_c=户掩码)）。"""
        H = self.H; Y = yr.Y; al = yr.alive; n = len(al)
        tim = {}
        t0 = time.perf_counter()
        dv = self.derive(yr, S) if inc is None or "dv" not in inc else inc["dv"]
        tim["derive"] = time.perf_counter() - t0
        ll = self.landlords(yr, S, dv) if inc is None or "ll" not in inc else inc["ll"]
        liv = dv["liv"]
        I = self.I
        EP, AN, NY = I(("官", "eparch")), I(("官", "annona")), I(("官", "nykteparch"))
        BN, BA = I(("官", "bishop_nicene")), I(("官", "bishop_arian"))
        X = {e: I(("外", e)) for e in EXT}
        hold = {k: H.g.get(v[0], -1) for k, v in yr.holders.items()}
        R = Rows()
        gone = np.setdiff1d(S.alive_prev, al) if len(S.alive_prev) else np.zeros(0, np.int64)
        new = al[(H.built[al] == Y) & (Y > Y0)]
        # ------------------- K0 粮（全城标量 → O(n)）
        t0 = time.perf_counter()
        R.add("口粮调拨", X["皇家粮运"], AN, yr.food, RULES[0], -1, 0)
        gl = sorted(set(dv["grain"]))
        gi = {k: I(("仓", k)) for k in gl}
        cnt = collections.Counter(dv["grain"])
        for k in gl:
            R.add("口粮下仓", AN, gi[k], cnt[k] * yr.ration, RULES[1], -1, 0)
        R.add("口粮配给", np.array([gi[k] for k in dv["grain"]]), al, yr.ration, RULES[1], al, 0)
        tim["grain"] = time.perf_counter() - t0
        # ------------------- K1 每户固定项（按户可增量）
        t0 = time.perf_counter()
        ma = np.ones(n, bool) if inc is None else inc["dirty_a"]
        ix = np.nonzero(ma)[0]
        g_ = al[ix]
        own_of = np.where(dv["owner"][ix] | (ll[g_] < 0), g_, ll[g_])     # 无房东的租户自交房税（假设）
        fh = np.array([hold.get(("fang_head", f), -1) for f in dv["fang"][ix]])
        dh = np.array([hold.get(("district_head", x), -1) for x in dv["d"][ix]])
        coll = np.where(fh >= 0, fh, np.where(dh >= 0, dh, EP))
        tax_payer_ok = own_of >= 0
        R.add("房税", own_of[tax_payer_ok], coll[tax_payer_ok], P4["tau"], RULES[2], g_[tax_payer_ok], 1)
        R.add("人头税", g_, coll, A["head_tax"], RULES[3], g_, 1)
        gm = dv["guild"][ix] != ""
        gh = np.array([hold.get(("guild_head", f"{a}×{b}"), -1) for a, b in zip(dv["d"][ix][gm], dv["guild"][ix][gm])])
        R.add("行会钱", g_[gm], np.where(gh >= 0, gh, EP), P4["delta"], RULES[4], g_[gm], 1)
        ar = dv["arian"][ix] != ""
        pa = (~ar) & (dv["parish"][ix] != "")
        R.add("奉献", g_[ar], np.array([I(("官", "arian_elder|" + x)) for x in dv["arian"][ix][ar]], np.int64), P4["omega"], RULES[9], g_[ar], 1)
        R.add("奉献", g_[pa], np.array([I(("官", "parish_elder|" + x)) for x in dv["parish"][ix][pa]], np.int64), P4["omega"], RULES[9], g_[pa], 1)
        ten = (~dv["owner"][ix]) & (ll[g_] >= 0)
        R.add("租金", g_[ten], ll[g_[ten]], P4["rho"], RULES[12], g_[ten], 1)
        sold = liv[ix] == 9
        R.add("兵饷", NY, g_[sold], A["soldier_pay"], RULES[18], g_[sold], 1)
        for c_, v_ in A["court"].items():
            wk = liv[ix] == c_
            R.add("宫廷采购(皇库付)", X["皇库"], g_[wk], v_, RULES[-2], g_[wk], 1)
        for c_, v_ in A["export"].items():
            wk = liv[ix] == c_
            R.add("出口(城外付)", X["城外贸易"], g_[wk], v_, RULES[15], g_[wk], 1)
        nw = (H.built[g_] == Y) & (Y > Y0)
        R.add("迁入带钱", X["迁入"], g_[nw], A["c_in"], RULES[25], g_[nw], 1)
        # 新房造价：房东 → 同区最近营造户
        bl = np.nonzero(liv == 7)[0]
        nt = nw & (~dv["owner"][ix]) & (ll[g_] >= 0)
        for i in np.nonzero(nt)[0]:
            c = bl[dv["d"][bl] == dv["d"][ix[i]]]
            if not len(c):
                c = bl
            if not len(c):
                continue
            dd = np.hypot(*(H.xy[al[c]] - H.xy[g_[i]]).T)
            b = al[c[np.lexsort((H.idnum[al[c]], dd))[0]]]
            R.add("建设:新房", ll[g_[i]], b, A["house_cost"], RULES[22], g_[i], 1)
        tim["fixed"] = time.perf_counter() - t0
        # ------------------- 还款、俸给（全量，小）
        t0 = time.perf_counter()
        alset = set(al.tolist())
        rp = [(L[1], L[0], min(L[3], L[2])) for L in S.loans if L[2] > 1e-9 and L[1] in alset and L[0] in alset]
        if rp:
            R.add("还款", np.array([x[0] for x in rp]), np.array([x[1] for x in rp]), np.array([x[2] for x in rp]), RULES[19], -1, 9)
        stp = collections.defaultdict(list)
        for (off, jur), g in sorted(hold.items()):
            if g < 0 or g not in alset:
                continue
            if off in A["stipend_imperial"]:
                stp[X["皇库"]].append((g, A["stipend_imperial"][off]))
            elif off in A["stipend_eparch"]:
                stp[EP].append((g, A["stipend_eparch"][off]))
            elif off == "bishop_nicene":
                stp[BN].append((g, A["stipend_bishop"]))
            elif off == "bishop_arian":
                stp[BA].append((g, A["stipend_bishop"]))
        for src_, lst in stp.items():
            R.add("俸给", src_, np.array([x[0] for x in lst]), np.array([x[1] for x in lst]), RULES[17], -1, 9)
        ns = int((liv == 9).sum())
        R.add("兵饷", X["皇库"], NY, A["soldier_imperial"] * ns, RULES[18], -1, 9)
        R.add("兵饷", EP, NY, P4["sigma"] * ns, RULES[18], -1, 9)
        # 拆迁补偿 / 搬迁费（本年拆毁 = 上年在册、本年不在）
        for g in gone:
            if H.dest[g] != Y:
                continue
            if H.built[g] <= Y0:
                R.add("拆迁补偿", EP, g, P4["comp"] * P4["V_h"], RULES[20], -1, 9)
            else:
                lg = S.landlord[g]
                R.add("拆迁补偿", EP, lg if (lg >= 0 and lg in alset) else g, P4["comp"] * P4["V_h"], RULES[20], -1, 9)
                R.add("搬迁费", EP, g, P4["reloc"], RULES[21], -1, 9)
        # 公共工程（账本建筑）
        for w in H.works:
            if w["year"] != Y or w["id"] in yr.drop:
                continue
            c = bl if len(bl) else np.zeros(0, np.int64)
            if not len(c):
                continue
            wx = H.st[w["id"]]["xy"]
            dd = np.hypot(*(H.xy[al[c]] - wx).T)
            pick = al[c[np.lexsort((H.idnum[al[c]], dd))[:A["builders_per_work"]]]]
            pay = w["payer"]; cost = w["cost"]
            src = {"emperor": [(X["皇库"], 1.0)], "merchants": [(X["城外商人"], 1.0)], "church_private": [(BN, 1.0)],
                   "bishop_arian": [(BA, 1.0)], "prefect": [(EP, 1.0)], "prefect+levy": [(EP, 1.0)],
                   "district_xero+bishop_nicene": [(EP, 0.5), (BN, 0.5)]}.get(pay, [(EP, 1.0)])
            for s_, sh in src:
                R.add("建设:公共工程", s_, pick, cost * sh / len(pick), RULES[23], -1, 9)
            if pay == "prefect+levy":
                lv = al[dv["water"] == w["id"]]
                R.add("修水摊派", lv, EP, P4["levy"], RULES[24], -1, 9)
        tim["misc"] = time.perf_counter() - t0
        # ------------------- K2 工钱（按区分组，可增量）
        t0 = time.perf_counter()
        dset = sorted(set(dv["d"])) if inc is None else sorted(inc["dirty_d"])
        rev = S.rev_prev
        for dname in dset:
            m = dv["d"] == dname
            ii = np.nonzero(m)[0]
            emp = ii[np.isin(liv[ii], EMPLOYERS)]
            emp = emp[np.argsort(dv["door_rank"][emp], kind="stable")]
            fr = A["wage_share"] * rev[al[emp]] / A["wage"]
            slots = np.floor(fr + 1e-9).astype(np.int64)
            extra = int(np.floor(fr.sum() + 1e-9)) - int(slots.sum())
            if extra > 0:
                slots[np.argsort(-(fr - slots), kind="stable")[:extra]] += 1
            sl = np.repeat(emp, slots)
            wk_ = ii[np.isin(liv[ii], WORKERS)]
            wk_ = wk_[np.argsort(dv["door_rank"][wk_], kind="stable")]
            free_s = np.ones(len(sl), bool); free_w = np.ones(len(wk_), bool)
            pref_w = np.where(liv[wk_] == 1, 1, 0)                    # 脚夫偏港货商；雇工偏其余雇主
            pref_s = np.where(liv[sl] == 5, 1, 0)
            st_w = dv["street"][wk_]; st_s = dv["street"][sl]
            for phase in range(4):
                if not free_s.any() or not free_w.any():
                    break
                kw = [(st_w[i] if phase < 2 else "", pref_w[i] if phase in (0, 2) else 0) for i in range(len(wk_))]
                ks = [(st_s[i] if phase < 2 else "", pref_s[i] if phase in (0, 2) else 0) for i in range(len(sl))]
                qs = collections.defaultdict(collections.deque)
                for i in np.nonzero(free_s)[0]:
                    qs[ks[i]].append(i)
                pa_, pb_ = [], []
                for i in np.nonzero(free_w)[0]:
                    q = qs.get(kw[i])
                    if q:
                        j = q.popleft(); free_s[j] = False; free_w[i] = False
                        pa_.append(al[sl[j]]); pb_.append(al[wk_[i]])
                if pa_:
                    R.add("工钱", np.array(pa_), np.array(pb_), A["wage"], RULES[16], np.array(pb_), 2)
        tim["wages"] = time.perf_counter() - t0
        # ------------------- 合并增量缓存（K1 / K2 干净行沿用）
        t0 = time.perf_counter()
        Rnew = R.cat()
        if inc is not None:
            C = inc["cache"]["rows"]
            pos = np.searchsorted(al, np.clip(C["o"], 0, None)); okp = (C["o"] >= 0) & (pos < n)
            hit = np.zeros(len(C["t"]), bool); hit[okp] = al[np.clip(pos[okp], 0, n - 1)] == C["o"][okp]
            ia = np.where(hit, np.clip(pos, 0, n - 1), 0)
            dmask = np.array([x in inc["dirty_d"] for x in dv["d"]], bool)
            dd_ = dmask[ia] if len(ia) else np.zeros(0, bool)
            keep1 = (C["k"] == 1) & hit & ~ma[ia]
            keep2 = (C["k"] == 2) & hit & ~dd_
            Rpre = {x: np.concatenate([C[x][keep1 | keep2], Rnew[x]]) for x in Rnew}
        else:
            Rpre = Rnew
        tim["merge"] = time.perf_counter() - t0
        # ------------------- 公役（全量）：城市长官雇无主雇工
        t0 = time.perf_counter()
        R = Rows()
        emp_w = set(Rpre["b"][Rpre["t"] == TI["工钱"]].tolist())
        budget = A["muni_draw"] * max(0.0, S.inst.get(("官", "eparch"), 0.0) - A["muni_reserve"])
        jobs = int(budget // A["wage"])
        un = np.array([i for i in np.nonzero(np.isin(liv, WORKERS))[0] if int(al[i]) not in emp_w], np.int64)
        if jobs > 0 and len(un):
            dl = sorted(set(dv["d"][un]))
            cntd = np.array([(dv["d"][un] == x).sum() for x in dl], float)
            qd = min(jobs, len(un)) * cntd / cntd.sum(); fl = np.floor(qd + 1e-9).astype(int)
            for j in np.argsort(-(qd - fl), kind="stable")[:min(jobs, len(un)) - fl.sum()]:
                fl[j] += 1
            pick = []
            for x, k_ in zip(dl, fl):
                u_ = un[dv["d"][un] == x]
                pick.extend(u_[np.argsort(dv["door_rank"][u_], kind="stable")][:k_].tolist())
            pick = np.array(sorted(pick), np.int64)
            R.add("公役工钱", EP, al[pick], A["wage"], RULES[-1], -1, 7)
        Rm = R.cat()
        Rpre = {x: np.concatenate([Rpre[x], Rm[x]]) for x in Rpre}
        tim["muni"] = time.perf_counter() - t0
        # ------------------- K3 买卖（按买方可增量；卖方表按市场）
        t0 = time.perf_counter()
        cash_mid = self._net_house(Rpre, al, S)          # 现钱 + 前面各项净额
        tim["net_mid"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        nm = len(dv["mk"])
        sellers = {}
        for gd in ("bread", "craft", "harbor"):
            codes = [c for c, v in SELL_GOOD.items() if v == gd]
            s_i = np.nonzero(np.isin(liv, codes))[0]
            tab = [[] for _ in range(nm)]
            for i in s_i[np.argsort(dv["door_rank"][s_i], kind="stable")]:
                tab[dv["node"][i]].append(int(al[i]))
            has = np.array([len(t) > 0 for t in tab])
            eff = np.arange(nm)
            if has.any():
                hx = np.nonzero(has)[0]
                MX = dv["MX"]
                for m_ in np.nonzero(~has)[0]:
                    dd = np.hypot(*(MX[hx] - MX[m_]).T); eff[m_] = hx[int(np.argmin(dd))]
            sellers[gd] = (tab, eff, has.any())
        wsell = collections.defaultdict(list)
        wl6 = np.nonzero(liv == 6)[0]
        for i in wl6[np.argsort(dv["door_rank"][wl6], kind="stable")]:
            wsell[dv["water"][i]].append(int(al[i]))
        wsell_d = collections.defaultdict(list)
        for i in wl6[np.argsort(dv["door_rank"][wl6], kind="stable")]:
            wsell_d[dv["d"][i]].append(int(al[i]))
        q = dict(bread=np.full(n, A["q_bread"]), craft=np.full(n, A["q_craft"]), harbor=np.full(n, A["q_harbor"]))
        q["craft"][liv == 8] *= A["fine_mult"]; q["harbor"][liv == 8] *= A["fine_mult"]
        node = dv["node"]
        price = {}
        for gd in ("bread", "craft", "harbor"):
            tab, eff, ok = sellers[gd]
            price[gd] = dv["p_" + gd][eff[node]]
        need = sum(q[gd] * price[gd] for gd in price) + A["q_water"] * dv["p_water"]
        scale = np.clip(cash_mid / need, A["floor"], 1.0)
        dv["scale"] = scale; dv["price"] = price
        hs = self.hseed[al]
        # 买方签名：实际卖方 + 金额（决定买卖行的全部输入）
        sig = np.zeros(n, np.int64)
        def mix(a, b):
            return (a * np.int64(1000003) + b) % np.int64(2 ** 61 - 1)
        for gd in ("bread", "craft", "harbor"):
            tab, eff, ok = sellers[gd]
            cntn = np.array([len(t) for t in tab]); eN = eff[node]
            flat = np.array([x for t in tab for x in t] or [0], np.int64); offn = np.concatenate([[0], np.cumsum(cntn)[:-1]])
            sel = np.where(cntn[eN] > 0, flat[np.minimum(offn[eN] + hs % np.maximum(cntn[eN], 1), len(flat) - 1)], -1)
            sig = mix(sig, sel + 7); sig = mix(sig, np.round(price[gd] * 1e9).astype(np.int64))
        wsel = np.array([(lambda t_: t_[hs[i] % len(t_)] if t_ else -1)(wsell.get(dv["water"][i]) or wsell_d.get(dv["d"][i])) for i in range(n)], np.int64)
        sig = mix(sig, wsel + 7); sig = mix(sig, np.round(dv["p_water"] * 1e9).astype(np.int64))
        sig = mix(sig, np.round(scale * 1e9).astype(np.int64)); sig = mix(sig, np.round(q["craft"] * 1e6).astype(np.int64))
        sig_g = np.full(H.NH, -1, np.int64); sig_g[al] = sig
        if inc is None:
            mc = np.ones(n, bool)
        else:
            mc = inc["cache"]["sig_g"][al] != sig
        R = Rows()
        mi = np.nonzero(mc)[0]
        for gd, tname in (("bread", "买卖:面包"), ("craft", "买卖:手工"), ("harbor", "买卖:港货")):
            tab, eff, ok = sellers[gd]
            if not ok or not len(mi):
                continue
            cntn = np.array([len(t) for t in tab]); offn = np.concatenate([[0], np.cumsum(cntn)[:-1]])
            flat = np.array([x for t in tab for x in t], np.int64)
            eN = eff[node[mi]]
            ok_ = cntn[eN] > 0
            b_ = mi[ok_]
            s_ = flat[offn[eN[ok_]] + hs[b_] % cntn[eN[ok_]]]
            R.add(tname, al[b_], s_, scale[b_] * q[gd][b_] * price[gd][b_], RULES[13], al[b_], 3)
        wm = mi[wsel[mi] >= 0]
        if len(wm):
            R.add("买卖:水", al[wm], wsel[wm], scale[wm] * A["q_water"] * dv["p_water"][wm], RULES[13], al[wm], 3)
        Rc = R.cat()
        if inc is not None:
            C = inc["cache"]["rows"]
            pos = np.searchsorted(al, np.clip(C["o"], 0, None)); okp = (C["o"] >= 0) & (pos < n)
            hit = np.zeros(len(C["t"]), bool); hit[okp] = al[np.clip(pos[okp], 0, n - 1)] == C["o"][okp]
            ia = np.where(hit, np.clip(pos, 0, n - 1), 0)
            keep3 = (C["k"] == 3) & hit & ~mc[ia]
            Rn = {x: np.concatenate([Rpre[x], C[x][keep3], Rc[x]]) for x in Rc}
        else:
            Rn = {x: np.concatenate([Rpre[x], Rc[x]]) for x in Rc}
        tim["purchase"] = time.perf_counter() - t0
        tim["dirty_buyers"] = int(mc.sum())
        # ------------------- K4 聚合项（全量，O(组数)）：卖方成本、税钱上缴、奉献、施舍、上交、迁出、借贷
        t0 = time.perf_counter()
        R2 = Rows()
        NT = H.NH + len(self.inst_keys) + 64
        sales = np.zeros(NT)
        for tname in ("买卖:面包", "买卖:手工", "买卖:港货", "买卖:水"):
            m = Rn["t"] == TI[tname]
            sales += np.bincount(Rn["b"][m], Rn["v"][m], NT)
        for c, sh in A["cost_share"].items():
            s_ = al[liv == c]
            R2.add("进货/原料(付城外)", s_, X["城外贸易"], sh * sales[s_], RULES[14], -1, 4)
        # 税钱上缴：坊长户 → 区长户 → 城市长官
        tx = np.zeros(NT)
        for tname in ("房税", "人头税"):
            m = Rn["t"] == TI[tname]
            tx += np.bincount(Rn["b"][m], Rn["v"][m], NT)
        fang_of = {}
        for (off, jur), g in hold.items():
            if off == "fang_head" and g >= 0:
                fang_of[g] = jur
        dist_of_fang = {}
        for f_, d_ in zip(dv["fang"], dv["d"]):
            dist_of_fang.setdefault(f_, collections.Counter())[d_] += 1
        dtx = np.zeros(NT)
        for g, f_ in sorted(fang_of.items()):
            if tx[g] <= 0:
                continue
            dmaj = dist_of_fang[f_].most_common(1)[0][0] if f_ in dist_of_fang else None
            dhh = hold.get(("district_head", dmaj), -1)
            up = (1 - P4["alpha"]) * tx[g]
            if dhh >= 0:
                R2.add("税钱上缴(坊长→区长)", g, dhh, up, RULES[5], -1, 4); dtx[dhh] += up
            else:
                R2.add("税钱上缴(区长→城市长官)", g, EP, up, RULES[5], -1, 4)
        for (off, jur), g in sorted(hold.items()):
            if off == "district_head" and g >= 0:
                tot = dtx[g] + (tx[g] if g not in fang_of else 0.0)
                if tot > 0:
                    R2.add("税钱上缴(区长→城市长官)", g, EP, (1 - P4["beta"]) * tot, RULES[6], -1, 4)
        m = Rn["t"] == TI["行会钱"]
        gt = np.bincount(Rn["b"][m], Rn["v"][m], NT)
        for g in np.nonzero(gt[:H.NH] > 0)[0]:
            R2.add("行会钱上缴(行会头→城市长官)", g, EP, (1 - P4["gamma"]) * gt[g], RULES[7], -1, 4)
        # 城市长官当年税收（含直收） × remit → 皇库
        R2c = R2.cat()
        ep_tax = (np.bincount(R2c["b"], R2c["v"], NT)[EP]
                  + sum(Rn["v"][(Rn["t"] == TI[t]) & (Rn["b"] == EP)].sum() for t in ("房税", "人头税", "行会钱")))
        R2.add("上交皇库", EP, X["皇库"], P4["remit"] * ep_tax, RULES[8], -1, 4)
        # 奉献：长老（教堂）→ 长老户 5% → 主教 95%
        m = Rn["t"] == TI["奉献"]
        of = np.bincount(Rn["b"][m], Rn["v"][m], NT)
        inc_b = collections.defaultdict(float)
        for key, e in sorted(self.inst_ix.items(), key=lambda x: x[1]):
            if key[0] == "官" and ("|" in key[1]) and of[e] > 0:
                off, ch = key[1].split("|")
                hg = hold.get((off, ch), -1)
                bishop = BA if off == "arian_elder" else BN
                skim = P4["eps"] * of[e] if hg >= 0 else 0.0
                if skim:
                    R2.add("奉献截留(长老)", e, hg, skim, RULES[10], -1, 4)
                R2.add("奉献上缴(→主教)", e, bishop, of[e] - skim, RULES[9], -1, 4)
                inc_b[bishop] += of[e] - skim
        # 施舍：上年收入低于贫困线的本派户
        poor_prev = S.inc_prev[al] < A["poverty"]
        for bishop, bk, mask in ((BN, "bishop_nicene", dv["arian"] == ""), (BA, "bishop_arian", dv["arian"] != "")):
            el = al[poor_prev & mask & (H.built[al] < Y)]
            needt = P4["alms"] * len(el)
            if needt <= 0:
                continue
            budget = A["alms_budget_share"] * inc_b[bishop] + A["alms_reserve_draw"] * max(0.0, S.inst.get(("官", bk), 0.0))
            sc = min(1.0, budget / needt)
            R2.add("施舍", bishop, el, P4["alms"] * sc, RULES[11], -1, 4)
        tim["agg"] = time.perf_counter() - t0
        # ------------------- 年末：现钱、迁出、借贷
        t0 = time.perf_counter()
        R2c = R2.cat()
        Rall = {x: np.concatenate([Rn[x], R2c[x]]) for x in Rn}
        cash = self._cash_after(Rall, S, NT)
        R3 = Rows()
        gp = np.array([g for g in gone if cash[g] > 0], np.int64)
        if len(gp):
            R3.add("迁出带钱", gp, X["迁出"], cash[gp], RULES[25], -1, 5)
        # 借贷（v2）：亏空户向同区有房面包师 / 体面户借
        act = np.zeros(H.NH, np.int64)
        for L in S.loans:
            if L[2] > 1e-9 and L[1] in alset:
                act[L[0]] += 1
        lend_ok = (dv["owner"]) & np.isin(liv, (2, 8))
        lenders_by_d = {}
        for x in sorted(set(dv["d"])):
            Ld = al[lend_ok & (dv["d"] == x)]
            lenders_by_d[x] = Ld[np.argsort(H.idnum[Ld], kind="stable")]
        bor = np.nonzero(cash[al] < -1e-9)[0]
        bor = bor[np.argsort(H.idnum[al[bor]], kind="stable")]
        lc = cash.copy()
        unfunded = 0
        newloans = []
        la, lb, lv = [], [], []
        for i in bor:
            g = int(al[i]); amt = -lc[g]
            Ld = lenders_by_d.get(dv["d"][i])
            if Ld is None or not len(Ld):
                unfunded += 1; continue
            ok = (act[Ld] < DEBT["cap"]) & (lc[Ld] >= amt + 2.0) & (Ld != g)
            if not ok.any():
                unfunded += 1; continue
            c = Ld[ok]
            dd = np.hypot(*(H.xy[c] - H.xy[g]).T)
            o = int(c[np.lexsort((H.idnum[c], dd))[0]])
            la.append(o); lb.append(g); lv.append(amt)
            lc[o] -= amt; lc[g] += amt; act[o] += 1
            newloans.append([o, g, amt, amt / DEBT["years"], Y])
        if la:
            R3.add("借贷", np.array(la), np.array(lb), np.array(lv), RULES[19], -1, 6)
        tim["close"] = time.perf_counter() - t0
        R3c = R3.cat()
        Rall = {x: np.concatenate([Rall[x], R3c[x]]) for x in Rall}
        return dict(rows=Rall, sig_g=sig_g, cash_mid=cash_mid, dv=dv, ll=ll, newloans=newloans, unfunded=unfunded, gone=gone, new=new, tim=tim, NT=NT)

    def _net_house(self, R, al, S):
        NT = self.H.NH + len(self.inst_keys) + 64
        m = ~np.isin(R["t"], list(GRAIN_T))
        net = np.bincount(R["b"][m], R["v"][m], NT) - np.bincount(R["a"][m], R["v"][m], NT)
        return S.cash[al] + net[al]

    def _cash_after(self, R, S, NT):
        m = ~np.isin(R["t"], list(GRAIN_T))
        net = np.bincount(R["b"][m], R["v"][m], NT) - np.bincount(R["a"][m], R["v"][m], NT)
        c = np.zeros(NT); c[:self.H.NH] = S.cash
        for k, v in S.inst.items():
            c[self.inst_ix[k]] = v
        return c + net

    # ---------------------------------------------------------- 状态推进
    def advance(self, yr, S, out):
        H = self.H; R = out["rows"]; NT = out["NT"]; al = yr.alive
        c = self._cash_after(R, S, NT)
        S2 = S.copy()
        S2.cash = c[:H.NH].copy()
        for k, e in self.inst_ix.items():
            S2.inst[k] = float(c[e])
        S2.cash[out["gone"]] = 0.0                     # 迁出户现钱已随户离城（或为负：欠账随户注销）
        m = ~np.isin(R["t"], list(GRAIN_T))
        fin = np.isin(R["t"], [TI["借贷"], TI["还款"], TI["迁入带钱"], TI["迁出带钱"]])
        inc = np.bincount(R["b"][m & ~fin], R["v"][m & ~fin], NT)[:H.NH]
        exp = np.bincount(R["a"][m & ~fin], R["v"][m & ~fin], NT)[:H.NH]
        alset = set(al.tolist())
        # 还款冲减
        for L in S2.loans:
            if L[2] > 1e-9 and L[1] in alset and L[0] in alset:
                L[2] -= min(L[3], L[2])
            elif L[2] > 1e-9:
                L.append("核销") if len(L) == 5 else None
                L[2] = 0.0
        S2.loans = [L for L in S2.loans if L[2] > 1e-9] + out["newloans"]
        rev = np.zeros(H.NH)
        for tname in ("买卖:面包", "买卖:手工", "买卖:港货", "买卖:水", "建设:新房", "建设:公共工程", "宫廷采购(皇库付)", "出口(城外付)"):
            mm = R["t"] == TI[tname]
            rev += np.bincount(R["b"][mm], R["v"][mm], NT)[:H.NH]
        S2.rev_prev = rev
        S2.inc_prev = inc
        S2.landlord = out["ll"]
        S2.alive_prev = al.copy()
        return S2, inc, exp

    def init_state(self, H):
        S = State(H, self.L)
        al = np.array(sorted(H.g[h] for h in H.years[Y0]), np.int64)
        liv = self.liv[al]
        S.cash[al] = np.where(liv == 8, A["cash0"][8], np.where(np.isin(liv, list(SELL_GOOD)), A["cash0"]["seller"], A["cash0"]["other"]))
        for k, v in A["treasury0"].items():
            S.inst[("官", k)] = v; self.I(("官", k))
        # AF40 引导：营收按满额需求估（只用于定 AF40 工位数，假设）
        yr = Year(H, Y0)
        S0 = S.copy()
        S0.cash[:] = 1e6
        o = self.step(yr, S0)
        R = o["rows"]
        rev = np.zeros(H.NH)
        for tname in ("买卖:面包", "买卖:手工", "买卖:港货", "买卖:水", "宫廷采购(皇库付)", "出口(城外付)"):
            mm = R["t"] == TI[tname]
            rev += np.bincount(R["b"][mm], R["v"][mm], o["NT"])[:H.NH]
        S.rev_prev = rev
        S.inc_prev = np.full(H.NH, 99.0)
        return S


# ================================================================ 统计
def gini(x):
    x = np.sort(np.asarray(x, float))
    if len(x) == 0:
        return 0.0
    if x.min() < 0:
        x = x - x.min()
    s = x.sum()
    if s <= 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * s))


def rows_hash(R):
    o = np.lexsort((np.round(R["v"], 9), R["b"], R["a"], R["t"]))
    h = hashlib.sha1()
    for x in ("t", "a", "b"):
        h.update(np.ascontiguousarray(R[x][o]).tobytes())
    h.update(np.round(R["v"][o], 9).tobytes())
    return h.hexdigest()


def ent_name(E, H, yr, e, gone_door):
    if e < H.NH:
        h = H.hid[e]
        d = H.door(h, yr.Y) if h in yr.recs else None
        if d is None:
            d = gone_door.get(e, h) + "（注销）"
        return d
    k = E.inst_keys[e - H.NH]
    if k[0] == "外":
        return "外:" + k[1]
    Y = yr.Y
    if k[0] == "仓":
        return f"仓:{k[1]}@{H.facility_door('f:' + k[1], Y)}"
    off = k[1]
    if off == "eparch":
        return f"官:城市长官@{H.door(H.eparch_house, Y) or '无门牌'}"
    if off == "annona":
        return f"官:粮政官@{H.facility_door('f:granary_founder', Y)}"
    if off == "nykteparch":
        return f"官:夜巡长@{H.facility_door('s:barracks_gate', Y)}"
    if off == "bishop_nicene":
        return f"官:主教(尼西亚)@{H.facility_door('f:church_megale', Y)}"
    if off == "bishop_arian":
        ch = "church_arian_brick" if Y >= 64 else "arian_meeting"
        return f"官:主教(阿里乌)@{H.facility_door('f:' + ch, Y)}"
    if "|" in off:
        o, ch = off.split("|")
        nm = "会众长老(阿里乌)" if o == "arian_elder" else "堂区长老"
        return f"官:{nm}|{ch}@{H.facility_door('f:' + ch, Y)}"
    return "官:" + off


# ================================================================ 主流程
def run():
    t00 = time.time()
    H = HW()
    E = Econ(H)
    t_liv = time.time() - t00 - H.t_load
    S = E.init_state(H)
    per = {}
    recon = []
    hh_snap = {}
    timing = []
    gone_door = {}
    M_prev = None
    sample_g = None
    sample_txt = {}
    ev_states = {}
    for Y in range(Y0, Y1 + 1):
        t0 = time.perf_counter()
        yr = Year(H, Y)
        out = E.step(yr, S)
        t_step = time.perf_counter() - t0
        R = out["rows"]; NT = out["NT"]
        # ---------- 守恒
        M_before = float(S.cash.sum() + sum(S.inst[k] for k in E.inst_keys if k[0] != "外"))
        S2, inc, exp = E.advance(yr, S, out)
        M_after = float(S2.cash.sum() + sum(S2.inst[k] for k in E.inst_keys if k[0] != "外"))
        written = float(S.cash[out["gone"]].sum()) if False else 0.0
        ext = [E.inst_ix[("外", e)] for e in EXT]
        money = ~np.isin(R["t"], list(GRAIN_T))
        ext_in = float(R["v"][money & np.isin(R["a"], ext)].sum())
        ext_out = float(R["v"][money & np.isin(R["b"], ext)].sum())
        # 迁出户负现钱（欠账）随户注销：记为调整项
        c_after = E._cash_after(R, S, NT)
        neg_gone = float(np.minimum(c_after[out["gone"]], 0).sum()) if len(out["gone"]) else 0.0
        dM = M_after - M_before
        cons_err = dM - (ext_in - ext_out) + neg_gone
        per_type = {}
        for t in range(len(TYPES)):
            m = R["t"] == t
            if m.any():
                paid = float(np.bincount(R["a"][m], R["v"][m], NT).sum()); got = float(np.bincount(R["b"][m], R["v"][m], NT).sum())
                per_type[TYPES[t]] = dict(rows=int(m.sum()), paid=round(paid, 3), received=round(got, 3), err=abs(paid - got))
        # 账本对账
        al = yr.alive
        grain_hh = float(R["v"][R["t"] == TI["口粮配给"]].sum())
        house_tax = float(R["v"][R["t"] == TI["房税"]].sum())
        v4l = V4["levels"].get(str(Y), {})
        v4_grain = v4l.get("粮/城市长官", {}).get("income")
        v4_tax_nodes = v4l.get("民政/房主（房屋）", {}).get("nodes")
        v4_tax = v4l.get("民政/房主（房屋）", {}).get("income")
        ledger_houses = int(sum(1 for i in range(H.NH) if H.built[i] <= Y and H.dest[i] > Y))
        no_owner = int(((~out["dv"]["owner"]) & (out["ll"][al] < 0)).sum())
        recon.append(dict(year=Y, ledger_houses=ledger_houses, model_households=len(al), houses_ok=ledger_houses == len(al),
                          food_cap=food_cap(Y), grain_to_households=round(grain_hh, 3), grain_ok=abs(grain_hh - food_cap(Y)) < 1e-6,
                          v4_grain_income=v4_grain, house_tax_model=round(house_tax, 3), house_tax_rule=round(P4["tau"] * ledger_houses, 3), house_tax_ok=abs(house_tax - P4["tau"] * ledger_houses) < 1e-6,
                          tenants_without_landlord=no_owner, v4_house_tax=v4_tax, v4_houses=v4_tax_nodes,
                          money_stock=round(M_after, 3), dM=round(dM, 3), ext_in=round(ext_in, 3), ext_out=round(ext_out, 3),
                          bad_debt_with_departing=round(neg_gone, 3), conservation_err=abs(cons_err),
                          max_type_err=max(v["err"] for v in per_type.values())))
        # 户统计
        cash = S2.cash[al]
        owned = np.where(out["dv"]["owner"], 1, 0).astype(float)
        llc = np.bincount(np.clip(out["ll"][al], 0, None), weights=(out["ll"][al] >= 0).astype(float), minlength=H.NH)
        owned += llc[al]
        recv = np.zeros(H.NH); pay = np.zeros(H.NH)
        for L in S2.loans:
            recv[L[0]] += L[2]; pay[L[1]] += L[2]
        nw = cash + P4["V_h"] * owned + recv[al] - pay[al]
        income = inc[al]; expense = exp[al]
        pl = A["poverty"]
        med = float(np.median(income))
        stats = dict(households=len(al), poverty_line=pl, poor=int((income < pl).sum()), poor_share=round(float((income < pl).mean()), 4),
                     at_or_below_line_share=round(float((income <= pl + 1e-9).mean()), 4),
                     rel_poverty_line=round(0.6 * med, 3), rel_poor_share=round(float((income < 0.6 * med).mean()), 4),
                     gini_income=round(gini(income), 4), gini_networth=round(gini(nw), 4), gini_cash=round(gini(cash), 4),
                     median_income=round(med, 3), mean_income=round(float(income.mean()), 3), median_networth=round(float(np.median(nw)), 3),
                     negative_cash=int((cash < -1e-9).sum()), unfunded_deficits=out["unfunded"],
                     loans_active=len(S2.loans), loans_new=len(out["newloans"]), loans_outstanding=round(float(sum(L[2] for L in S2.loans)), 2),
                     employed=int(((R["t"] == TI["工钱"])).sum()), workers=int(np.isin(E.liv[al], WORKERS).sum()),
                     eparch_treasury=round(S2.inst[("官", "eparch")], 2), bishop_nicene=round(S2.inst[("官", "bishop_nicene")], 2),
                     bishop_arian=round(S2.inst[("官", "bishop_arian")], 2), rows=int(len(R["t"])),
                     by_type_total={TYPES[t]: round(float(R["v"][R["t"] == t].sum()), 2) for t in range(len(TYPES)) if (R["t"] == t).any()})
        per[Y] = dict(stats=stats, per_type=per_type)
        timing.append(dict(year=Y, step_s=round(t_step, 3), **{k: round(v, 4) for k, v in out["tim"].items()}))
        for g in out["gone"]:
            gone_door[g] = S.door_prev.get(g, H.hid[g])
        # 示例户（AF70 仍在、AF41 起租、雇工）：逐年文本账
        if sample_g is None and Y == 41:
            cand = [g for g in out["new"] if E.liv[g] == 0 and H.dest[g] > 70]
            sample_g = int(sorted(cand, key=lambda g: H.idnum[g])[0]) if cand else int(al[0])
        if sample_g is not None and sample_g in set(al.tolist()) and Y in (41, 48, 60, 70):
            sample_txt[Y] = sample_year(E, H, yr, R, sample_g, gone_door, S, S2, inc, exp, out)
        if Y in SNAP:
            emit_year(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay)
        S2.door_prev = {g: H.door(H.hid[g], Y) for g in al}
        if Y + 1 in EVENT_YEARS:
            ev_states[Y + 1] = S2.copy()
        S = S2
    t_total = time.time() - t00
    # ---------- 输出
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys()))
        w.writeheader(); w.writerows(recon)
    L = E.L
    reg = L["first"] >= 0
    res = dict(
        _doc="economy_v14 结果（数字由 economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
        livelihood=dict(counts={LIV[i]: int(((L["liv"] == i) & reg).sum()) for i in range(len(LIV))},
                        source={FN_SRC[i]: int(((L["src"] == i) & reg).sum()) for i in range(4)},
                        fn={FNS[i]: int(((L["fn"] == i) & reg).sum()) for i in range(len(FNS))},
                        houses_ever=int(reg.sum())),
        years={str(Y): per[Y]["stats"] for Y in per},
        conservation=dict(max_per_type_err=max(r["max_type_err"] for r in recon), max_money_err=max(r["conservation_err"] for r in recon),
                          grain_all_years_ok=all(r["grain_ok"] for r in recon), house_tax_all_years_ok=all(r["house_tax_ok"] for r in recon), houses_all_years_ok=all(r["houses_ok"] for r in recon)),
        per_type_AF70=per[70]["per_type"],
        timing=dict(total_s=round(t_total, 2), load_s=round(H.t_load, 2), livelihood_s=round(t_liv, 2),
                    step_median_s=float(np.median([t["step_s"] for t in timing])), step_max_s=max(t["step_s"] for t in timing), per_year=timing),
        files={f"flows_AF{Y}.json.gz": os.path.getsize(os.path.join(HERE, f"flows_AF{Y}.json.gz")) for Y in SNAP},
        sample=dict(house=H.hid[sample_g], text=sample_txt),
    )
    old = {}
    p = os.path.join(HERE, "results.json")
    if os.path.exists(p):
        old = json.load(open(p))
    if "events" in old:
        res["events"] = old["events"]
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(HERE, "sample_household.txt"), "w") as f:
        f.write("\n\n".join(sample_txt[y] for y in sorted(sample_txt)))
    pickle.dump(dict(states=ev_states, inst_keys=E.inst_keys), open(os.path.join(HERE, ".cache_states.pkl"), "wb"))
    print(json.dumps(dict(total_s=round(t_total, 1), cons=res["conservation"], liv=res["livelihood"],
                          AF70={k: v for k, v in per[70]["stats"].items() if k != "by_type_total"}), ensure_ascii=False, default=float))


def sample_year(E, H, yr, R, g, gone_door, S, S2, inc, exp, out):
    Y = yr.Y
    lines = [f"AF{Y} {H.door(H.hid[g], Y)}（房屋 {H.hid[g]}，生计 {LIV[E.liv[g]]}，{'有房户' if H.built[g] <= Y0 else '租户'}）"]
    m = (R["a"] == g) | (R["b"] == g)
    for t, a, b, v in sorted(zip(R["t"][m], R["a"][m], R["b"][m], R["v"][m]), key=lambda x: (x[0], -x[3])):
        sign = "收" if b == g else "付"
        other = a if b == g else b
        unit = "份粮" if t in GRAIN_T else "份"
        lines.append(f"  {sign} {TYPES[t]:<10} {v:8.3f} {unit}  {'←' if sign == '收' else '→'} {ent_name(E, H, yr, int(other), gone_door)}")
    lines.append(f"  年收入 {inc[g]:.3f}，年支出 {exp[g]:.3f}，年初现钱 {S.cash[g]:.3f}，年末现钱 {S2.cash[g]:.3f}")
    return "\n".join(lines)


def emit_year(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
    used = np.unique(np.concatenate([R["a"], R["b"], al]))
    remap = -np.ones(int(used.max()) + 1, np.int64); remap[used] = np.arange(len(used))
    names = [ent_name(E, H, yr, int(e), gone_door) for e in used]
    kind = ["户" if e < H.NH else E.inst_keys[e - H.NH][0] for e in used]
    q = np.round(R["v"] * 1000).astype(np.int64)
    o = np.lexsort((R["b"], R["a"], R["t"]))
    doc = dict(
        year=yr.Y, _doc="economy_v14 逐年流（列式）。单位：q 为千分之一份；粮类型的份 = 一人一年口粮，其余为折粮的钱。——Hark（刘线）",
        entities=names, entity_kind=kind, types=TYPES, rules=RULES,
        flows=dict(t=R["t"][o].tolist(), a=remap[R["a"][o]].tolist(), b=remap[R["b"][o]].tolist(), q=q[o].tolist(), r=R["r"][o].tolist()),
        households=dict(ent=remap[al].tolist(), house=[H.hid[g] for g in al], livelihood=E.liv[al].tolist(), livelihood_names=LIV,
                        lh_src=E.L["src"][al].tolist(), lh_src_names=FN_SRC,
                        income_m=np.round(income * 1000).astype(int).tolist(), expense_m=np.round(expense * 1000).astype(int).tolist(),
                        cash_m=np.round(cash * 1000).astype(int).tolist(), networth_m=np.round(nw * 1000).astype(int).tolist(),
                        houses_owned=owned.astype(int).tolist(), debt_m=np.round(pay[al] * 1000).astype(int).tolist(),
                        landlord=[int(remap[x]) if x >= 0 else -1 for x in out["ll"][al]],
                        market=[out["dv"]["mk"][i] for i in out["dv"]["node"]],
                        dist_market=np.round(out["dv"]["dist_market"], 1).tolist(), dist_grain=np.round(out["dv"]["dist_grain"], 1).tolist()))
    with gzip.open(os.path.join(HERE, f"flows_AF{yr.Y}.json.gz"), "wt", compresslevel=9) as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


# ================================================================ 硬件事件：反事实 vs 事件、增量 == 重建
def event_mods(H, E, Y, name):
    """返回 (反事实 mod, 说明)。反事实只撤掉该事件本身，其余当年硬件不变。"""
    if name == "fire48":
        hs = [h for h in H.years[Y - 1] if H.dest[H.g[h]] == Y]
        return dict(add={h: H.years[Y - 1][h] for h in hs}, addr={h: H.addr[Y - 1][h] for h in hs}), \
            f"AF48 火灾：账本本年拆毁 {len(hs)} 栋（world.json destroyed=48）；反事实 = 这些房屋与户照 AF47 在册"
    if name == "granary55":
        st = {}
        alt = [k for k in H.standing(Y, ("granary",)) if k != "horrea_alexandrina"]
        GX = np.array([H.st[k]["xy"] for k in alt])
        for h, r in H.years[Y].items():
            if r[6] == "horrea_alexandrina":
                if h in H.years[Y - 1]:
                    g0 = H.years[Y - 1][h][6]
                else:
                    g0 = alt[int(np.argmin(np.hypot(*(GX - H.xy[H.g[h]]).T)))]
                st[h] = r[:6] + (g0,) + r[7:]
        return dict(set=st, drop_structs={"horrea_alexandrina"}, food_cap=food_cap(Y - 1)), \
            f"AF55 新粮仓 horrea_alexandrina：v7 配给点改到新仓 {len(st)} 户；账本 food_cap 173,202→193,202 同年（归因于新仓，假设）；反事实 = 无此仓、配给点回 AF54、food_cap 173,202"
    if name == "forum57":
        return dict(drop_structs={"forum_theodosius"}), "AF57 新市场 forum_theodosius（皇帝出资 9,600 份工程）；反事实 = 无此市场、无此工程"
    if name == "street62":
        st, ad = {}, {}
        for h, r in H.years[Y].items():
            if r[8] == "r_carriers" and h in H.years[Y - 1]:
                st[h] = H.years[Y - 1][h]
                if h in H.addr[Y - 1]:
                    ad[h] = H.addr[Y - 1][h]
        return dict(set=st, addr=ad, drop_structs={"r_carriers"}), \
            f"AF62 新街 r_carriers：v7 门口改到新街 {len(st)} 户（门牌改址）；反事实 = 这些户照 AF61 的街、坊、门牌，且无此路工程"
    raise KeyError(name)


def dirty_sets(H, yr_cf, yr_ev, o_cf, ll_ev):
    al = yr_ev.alive
    a_cf = set(yr_cf.alive.tolist())
    ch = set()
    for g in al:
        h = H.hid[g]
        if g not in a_cf or yr_cf.recs.get(h) != yr_ev.recs[h] or yr_cf.addr.get(h) != yr_ev.addr.get(h) \
                or o_cf["ll"][g] != ll_ev[g] or H.built[g] == yr_ev.Y:
            ch.add(int(g))
    gone = set(a_cf) - set(al.tolist())
    # 房东换人 / 房东离城的租户
    for g in al:
        if ll_ev[g] in gone or o_cf["ll"][g] in gone:
            ch.add(int(g))
    ma = np.array([int(g) in ch for g in al])
    dd = set()
    for g in ch | gone:
        h = H.hid[g]
        for yr in (yr_cf, yr_ev):
            if h in yr.recs:
                dd.add(yr.recs[h][0])
    return ma, dd, len(ch), len(gone)


def events():
    t00 = time.time()
    H = HW()
    E = Econ(H)
    C_ = pickle.load(open(os.path.join(HERE, ".cache_states.pkl"), "rb"))
    E.inst_keys = list(C_["inst_keys"]); E.inst_ix = {k: H.NH + i for i, k in enumerate(E.inst_keys)}
    out = {}
    for name, Y in (("fire48", 48), ("granary55", 55), ("forum57", 57), ("street62", 62)):
        S = C_["states"][Y]
        mod, desc = event_mods(H, E, Y, name)
        yr_ev = Year(H, Y); yr_cf = Year(H, Y, mod)
        t0 = time.perf_counter(); o_cf = E.step(yr_cf, S); t_cf = time.perf_counter() - t0
        t0 = time.perf_counter(); o_ev = E.step(yr_ev, S); t_full = time.perf_counter() - t0
        # 增量：从反事实结果出发，只重算脏户 / 脏区 / 签名变了的买方
        t0 = time.perf_counter()
        dv = E.derive(yr_ev, S)
        ll = E.landlords(yr_ev, S, dv)
        ma, dd, nch, ngone = dirty_sets(H, yr_cf, yr_ev, o_cf, ll)
        t_dirty = time.perf_counter() - t0
        t1 = time.perf_counter()
        o_inc = E.step(yr_ev, S, inc=dict(cache=o_cf, dirty_a=ma, dirty_d=dd, dv=dv, ll=ll))
        t_inc = time.perf_counter() - t1 + t_dirty + 0.0
        h_full, h_inc = rows_hash(o_ev["rows"]), rows_hash(o_inc["rows"])
        # 局部影响
        NT = o_ev["NT"]
        def per_house(o, kinds):
            R = o["rows"]; m = np.isin(R["t"], [TI[k] for k in kinds])
            return np.bincount(R["b"][m], R["v"][m], NT)[:H.NH], np.bincount(R["a"][m], R["v"][m], NT)[:H.NH]
        money = [t for t in TYPES if TI[t] not in GRAIN_T]
        fin = {"借贷", "还款", "迁入带钱", "迁出带钱"}
        inc_ev, exp_ev = per_house(o_ev, [t for t in money if t not in fin])
        inc_cf, exp_cf = per_house(o_cf, [t for t in money if t not in fin])
        gr_ev, _ = per_house(o_ev, ["口粮配给"]); gr_cf, _ = per_house(o_cf, ["口粮配给"])
        both = np.intersect1d(yr_ev.alive, yr_cf.alive)
        d_inc = inc_ev[both] - inc_cf[both]; d_exp = exp_ev[both] - exp_cf[both]
        def flowset(o, g):
            R = o["rows"]; m = ~np.isin(R["t"], list(GRAIN_T))
            return R
        # 任一笔钱流（金额或对方）变了的在册户
        def sig_rows(o):
            R = o["rows"]; m = ~np.isin(R["t"], list(GRAIN_T))
            d = collections.defaultdict(list)
            for t, a, b, v in zip(R["t"][m], R["a"][m], R["b"][m], np.round(R["v"][m], 9)):
                if a < H.NH: d[int(a)].append((int(t), int(b), -v))
                if b < H.NH: d[int(b)].append((int(t), int(a), v))
            return {k: sorted(v) for k, v in d.items()}
        s_ev, s_cf = sig_rows(o_ev), sig_rows(o_cf)
        changed = [g for g in both.tolist() if s_ev.get(g) != s_cf.get(g)]
        pos_ev = {int(g): i for i, g in enumerate(yr_ev.alive)}; pos_cf = {int(g): i for i, g in enumerate(yr_cf.alive)}
        bi = np.array([pos_ev[g] for g in both]); ci = np.array([pos_cf[g] for g in both])
        dist_g = o_ev["dv"]["dist_grain"][bi] - o_cf["dv"]["dist_grain"][ci]
        dist_m = o_ev["dv"]["dist_market"][bi] - o_cf["dv"]["dist_market"][ci]
        pb = o_ev["dv"]["price"]["bread"][bi] - o_cf["dv"]["price"]["bread"][ci]
        ph = o_ev["dv"]["price"]["harbor"][bi] - o_cf["dv"]["price"]["harbor"][ci]
        mkt_ev = np.array(o_ev["dv"]["mk"])[o_ev["dv"]["node"][bi]]; mkt_cf = np.array(o_cf["dv"]["mk"])[o_cf["dv"]["node"][ci]]
        def summ(x):
            nz = np.abs(x) > 1e-9
            return dict(n=int(nz.sum()), mean_changed=round(float(x[nz].mean()), 4) if nz.any() else 0.0,
                        min=round(float(x.min()), 4), max=round(float(x.max()), 4), total=round(float(x.sum()), 3))
        R_ev = o_ev["rows"]
        out[name] = dict(
            year=Y, desc=desc,
            hardware=dict(households_ev=len(yr_ev.alive), households_cf=len(yr_cf.alive), departing_vs_cf=ngone,
                          changed_inputs=nch, dirty_households_K1=int(ma.sum()), dirty_districts_K2=sorted(dd),
                          dirty_buyers_K3=o_inc["tim"]["dirty_buyers"]),
            affected_households_money=len(changed),
            ration_per_household=dict(ev=round(yr_ev.ration, 5), cf=round(yr_cf.ration, 5), note="口粮全城均分（v7）：所有在册户都变，属全城标量"),
            income_change=summ(d_inc), expense_change=summ(d_exp),
            dist_grain_change=summ(dist_g), dist_market_change=summ(dist_m), market_switched=int((mkt_ev != mkt_cf).sum()),
            bread_price_change=summ(pb), harbor_price_change=summ(ph),
            totals_ev_minus_cf={t: round(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - o_cf["rows"]["v"][o_cf["rows"]["t"] == TI[t]].sum()), 3)
                                for t in TYPES if abs(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - o_cf["rows"]["v"][o_cf["rows"]["t"] == TI[t]].sum())) > 1e-6},
            incremental_equals_rebuild=h_full == h_inc, rows=int(len(R_ev["t"])), rows_hash=h_full[:16],
            timing_ms=dict(full_rebuild=round(t_full * 1000, 1), incremental=round(t_inc * 1000, 1), counterfactual=round(t_cf * 1000, 1),
                           dirty_detect=round(t_dirty * 1000, 1), full_parts={k: round(v * 1000, 1) for k, v in o_ev["tim"].items() if k != "dirty_buyers"},
                           inc_parts={k: round(v * 1000, 1) for k, v in o_inc["tim"].items() if k != "dirty_buyers"}))
        print(name, json.dumps({k: out[name][k] for k in ("affected_households_money", "incremental_equals_rebuild", "timing_ms")}, ensure_ascii=False)[:600])
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p))
    res["events"] = out
    res["events_total_s"] = round(time.time() - t00, 1)
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    {"run": run, "events": events}[sys.argv[1]]()
