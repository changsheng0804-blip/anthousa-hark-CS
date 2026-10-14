# -*- coding: utf-8 -*-
"""economy_v15：港口转口 / 手工业 / 农渔 三个产业部门替代 v14 的宫廷采购兜底；主教库与城市长官库加支出规则。
地下数据管线，不做页面。——Hark（刘线）

按路径只读载入（不改）：
  ../economy_v14/economy.py（HW、Year、State、生计 v14、口粮/房税/税链/奉献/租金/借贷 规则、事件定义、gini、rows_hash）
  ../yamen_v13/yamen.py 与 .cache_incr.pkl（经 v14 载入）；v7 街网（经 yamen.cs7）算到港口的步行距离
  world.json（港口、港仓 horrea、农田、城墙、街、蓄水池、教堂）

运行：python3 economy.py run            # 基准 AF40–70 + 输出
      python3 economy.py sens           # 到港量 3 档敏感性（×0.5 / ×1.0 / ×1.5），只写 results.json["sensitivity"]
      python3 economy.py events         # v14 的 4 个事件 + 合成「到港量骤降一年」：增量 == 重建
"""
import os, sys, json, gzip, time, pickle, hashlib, importlib.util, collections, csv, heapq, math
import numpy as np
from scipy.spatial import ConvexHull

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, ".."))


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sys.path.insert(0, os.path.dirname(path))
    sp.loader.exec_module(m)
    return m


E14 = _load("economy_v14_for_v15", os.path.join(EXP, "economy_v14", "economy.py"))
HW, Year, State, food_cap, stable_u, gini, rows_hash = E14.HW, E14.Year, E14.State, E14.food_cap, E14.stable_u, E14.gini, E14.rows_hash
P4, LL, DEBT, V4 = E14.P4, E14.LL, E14.DEBT, E14.V4
Y0, Y1, SNAP, EVENT_YEARS = E14.Y0, E14.Y1, E14.SNAP, E14.EVENT_YEARS
SHIP_EVENT_YEAR = 65

# ------------------------------------------------------------------ 参数（v14 沿用 + 本轮新假设）
A = {k: v for k, v in E14.A.items() if k not in ("court", "muni_reserve", "muni_draw", "export", "cost_share")}
A.update(
    # ---- (a) 港口转口
    ships_base=600,          # 年到港商船（不含皇家粮运 annona 船队；假设）
    ships_mult=1.0,          # 敏感性档位
    cargo=600.0,             # 每船货值（份；≈70–100 吨杂货，按粮折价的 2–3 倍，假设）
    kommerkion=0.10,         # 关税率（kommerkion 10% 为 8 世纪后制度；4–5 世纪对应 octava 12.5%，见 REPORT）
    customs_city_share=1 / 3,   # 关税留城比例（仿 CTh 4.13.7 / 15.1.18 城市得本地 vectigal 三分之一，存疑）
    f_handle=0.040,          # 装卸 / 搬运费 = 货值 4%（装卸行）
    f_store=0.020,           # 仓储费 2%（港仓户；warehouse_horn 拿 40%，其余按港口货量）
    w_horrea=0.40,
    r_ship=8.0,              # 每船修补 / 补给 8 份（船修户）
    f_broker=0.015,          # 牙佣 1.5%（牙人户）
    f_change=0.010,          # 兑钱 1%（兑钱商户）
    local_share=0.25,        # 到港货留城比例（城内消费 + 作坊原料），其余转口
    m_reexp=0.05,            # 转口差价：港货商在转口部分上的毛利 5%（船商付）
    harbor_cost=0.50,        # 港货商卖给本城的货，进价 = 售价 50%（付船商）
    port_wage_share=0.50,    # 港口雇主当年港费营收 50% 雇工（装卸是按船日雇，故用当年而非上年）
    R_walk=150.0,            # 港口雇工：到港口步行距离上限（账本单位，≈1.8 km）
    # ---- (b) 手工业
    craft_cost=0.30,         # 原料 / 燃料 = 营收 30%
    craft_local_raw=0.40,    # 其中 40% 买自本城港货商（转口货），60% 付城外
    export_work=10.0, export_shop=1.5,   # 作坊 / 手工铺 每户每年出口（份，到港量基准时）
    export_elast=0.5,        # 出口 ∝ (到港量 / 基准)^0.5：出口要靠船运走（假设）
    # ---- (c) 农业 / 渔业
    q_veg=0.25, q_fish=0.20,             # 户需求：菜蔬、鱼（价 1 计的量）；谷物仍是口粮
    R_field=30.0, R_coast=6.0,           # 菜农：离农田 ≤30 或在城墙外；渔户：离海岸代理 ≤6
    p_farm=0.70, p_fish=0.35,            # 候选户中转业概率（确定性散列）
    farm_cost=0.10, fish_cost=0.15,      # 种子农具 / 网具船具 付城外
    export_fish=1.0,                     # 渔户咸鱼出口（份/户，基准到港量）
    # ---- 其他卖方成本（v14）
    bread_cost=0.20,
    # ---- 户可支配盈余追加消费
    c_surplus=0.30, buffer=6.0, surplus_mix={"craft": 0.55, "harbor": 0.35, "fish": 0.10},
    # ---- 库银支出规则
    retain_bishop=0.50, alms_share=1 / 3, alms_cap=2.0, clergy_share=1 / 3, builders_per_church=25,
    retain_eparch=0.50, eparch_floor=5000.0, pw_share=0.40, builders_per_struct=20,
    stip_fang=1.0, stip_district=3.0,
    port_split={5: .35, 10: .20, 11: .15, 12: .12, 13: .10, 14: .08},   # v14 港货商 → 港口各行（散列，假设）
)

LIV = ["雇工", "码头脚夫", "面包", "手工铺", "作坊", "港货商", "运水人", "营造", "体面户", "兵户",
       "装卸行", "港仓", "船修", "牙人", "兑钱商", "菜农", "渔户"]
PORT_M = (5, 10, 11, 12, 13, 14)
CRAFT = (3, 4)
AGRI = (15, 16)
DIST_EMP = (2, 3, 4, 7)
WORKERS = (0, 1)
SELL_GOOD = {2: "bread", 3: "craft", 4: "craft", 5: "harbor", 6: "water", 15: "veg", 16: "fish"}
SECTORS = {"转口": PORT_M, "手工": CRAFT, "农渔": AGRI}

TYPES = ["公役工钱", "口粮调拨", "口粮下仓", "口粮配给",
         "房税", "人头税", "行会钱", "税钱上缴(坊长→区长)", "税钱上缴(区长→城市长官)", "行会钱上缴(行会头→城市长官)", "上交皇库",
         "奉献", "奉献截留(长老)", "奉献上缴(→主教)", "施舍", "神职俸给", "教堂营造",
         "租金", "买卖:面包", "买卖:水", "买卖:手工", "买卖:港货", "买卖:菜蔬", "买卖:鱼",
         "进货/原料(付城外)", "港货进价(付船商)", "原料(转口货)", "出口:手工(船商付)", "出口:鱼(船商付)",
         "港费:装卸", "港费:仓储", "港费:船修", "港费:牙佣", "港费:兑钱", "转口差价(船商付)",
         "关税", "关税分成(→城市长官)", "关税上解(→皇库)",
         "工钱", "工钱:港口", "俸给", "官俸(坊长/区长)", "兵饷", "城防街渠维护",
         "借贷", "还款", "拆迁补偿", "搬迁费", "建设:新房", "建设:公共工程", "修水摊派", "迁入带钱", "迁出带钱"]
TI = {t: i for i, t in enumerate(TYPES)}
GRAIN_T = [TI["口粮调拨"], TI["口粮下仓"], TI["口粮配给"]]
FIN_T = [TI["借贷"], TI["还款"], TI["迁入带钱"], TI["迁出带钱"]]
PORT_FEE_T = ["港费:装卸", "港费:仓储", "港费:船修", "港费:牙佣", "港费:兑钱", "转口差价(船商付)"]
BUSINESS_OUT = ["工钱", "工钱:港口", "进货/原料(付城外)", "港货进价(付船商)", "原料(转口货)", "税钱上缴(坊长→区长)", "税钱上缴(区长→城市长官)", "行会钱上缴(行会头→城市长官)"]
REV_T = ["买卖:面包", "买卖:手工", "买卖:港货", "买卖:水", "买卖:菜蔬", "买卖:鱼", "原料(转口货)", "出口:手工(船商付)", "出口:鱼(船商付)",
         "建设:新房", "建设:公共工程", "教堂营造", "城防街渠维护"] + PORT_FEE_T
RULES = []
RI = {}


def rule(s):
    if s not in RI:
        RI[s] = len(RULES); RULES.append(s)
    return RI[s]


EXT = ["皇库", "皇家粮运", "城外贸易", "城外商人", "迁入", "迁出", "船商"]


class Rows:
    def __init__(self):
        self.c = collections.defaultdict(list)

    def add(self, t, a, b, v, r, o, k):
        shp = np.shape(a) if np.ndim(a) else np.shape(b) if np.ndim(b) else np.shape(v) if np.ndim(v) else (1,)
        n = shp[0]
        f = lambda x, dt: np.broadcast_to(np.asarray(x, dt), (n,)).copy()
        self.c["t"].append(f(TI[t], np.int16)); self.c["a"].append(f(a, np.int64)); self.c["b"].append(f(b, np.int64))
        self.c["v"].append(f(v, float)); self.c["r"].append(f(rule(r), np.int16)); self.c["o"].append(f(o, np.int64)); self.c["k"].append(f(k, np.int8))

    def cat(self):
        dts = dict(t=np.int16, a=np.int64, b=np.int64, v=float, r=np.int16, o=np.int64, k=np.int8)
        if not self.c["t"]:
            return {x: np.zeros(0, dt) for x, dt in dts.items()}
        R = {x: np.concatenate(self.c[x]) for x in dts}
        m = R["v"] > 1e-12
        return {x: y[m] for x, y in R.items()}


def catd(*Rs):
    return {x: np.concatenate([R[x] for R in Rs]) for x in Rs[0]}


# ================================================================ 硬件扩展：港口步行距离、海岸、农田
class HW15:
    def __init__(self, H):
        self.H = H
        self.cs7 = H.ym.cs7
        C = H.C
        self.C = C
        self.street_index = {s["id"]: i for i, s in enumerate(C.streets)}
        st = H.st
        self.harbors = sorted(k for k, s in st.items() if s["type"] == "harbor")
        self.ports = self.harbors + sorted(k for k, s in st.items() if s["type"] == "warehouse")    # warehouse_horn = horrea
        poly = {s["id"]: np.asarray(s["geom"]["coords"], float).reshape(-1, 2) for s in H.world["structures"]}
        self.poly = poly
        def area(p):
            x, y = p[:, 0], p[:, 1]
            return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        self.harbor_area = {k: area(poly[k]) for k in self.harbors}
        # 海岸代理：历年全部房屋形心凸包边界，去掉陆墙一侧（边中点在 Founder 城墙线以西或距墙 <20）；加上港口多边形
        ever = np.nonzero(np.asarray(C.S.built) < 10 ** 8)[0]
        P = H.xy
        hull = ConvexHull(P)
        wall = poly["wall_founder"]
        def wall_x(y):
            return np.interp(y, wall[:, 1][np.argsort(wall[:, 1])], wall[:, 0][np.argsort(wall[:, 1])])
        edges = []
        for s in hull.simplices:
            a, b = P[s[0]], P[s[1]]
            m = (a + b) / 2
            if m[0] > wall_x(m[1]) + 20:
                edges.append((a, b))
        self.coast_edges = edges
        def dseg(Q, a, b):
            ab = b - a; t = np.clip(((Q - a) @ ab) / (ab @ ab), 0, 1)
            return np.hypot(*(Q - a - t[:, None] * ab).T)
        dc = np.full(len(P), 1e9)
        for a, b in edges:
            dc = np.minimum(dc, dseg(P, a, b))
        for k in self.harbors:
            q = poly[k]
            for i in range(len(q)):
                dc = np.minimum(dc, dseg(P, q[i], q[(i + 1) % len(q)]))
        self.d_coast = dc
        # 农田（field_north / field_south，AF32 起）多边形外接框距离；城墙外 = Founder 城墙线以西
        df = np.full(len(P), 1e9)
        for k in ("field_north", "field_south"):
            q = poly[k]; lo, hi = q.min(0), q.max(0)
            dx = np.maximum(0, np.maximum(lo[0] - P[:, 0], P[:, 0] - hi[0])); dy = np.maximum(0, np.maximum(lo[1] - P[:, 1], P[:, 1] - hi[1]))
            df = np.minimum(df, np.hypot(dx, dy))
        self.d_field = df
        self.outside_wall = P[:, 0] < wall_x(P[:, 1])
        self.field_xy = np.array([poly[k].mean(0) for k in ("field_north", "field_south")] + [st["gate_founder"]["xy"]])
        self._walk = {}
        self.t_walk = 0.0

    def streets_for(self, yr):
        s = self.cs7.street_ids_for(self.C, yr.Y)
        drop = {self.street_index[x] for x in yr.drop if x in self.street_index}
        return frozenset(s - drop)

    def walk(self, yr):
        """全部房屋到各港口设施的街网步行距离（门口→街网 Dijkstra→港口门口）；按街集缓存。"""
        key = self.streets_for(yr)
        if key in self._walk:
            return self._walk[key]
        t0 = time.time()
        cs7, C, H = self.cs7, self.C, self.H
        st = cs7.build(C, yr.Y, streets=set(key))
        segs = np.array(sorted(st.segon))
        NH = H.NH
        out = np.full((NH, len(self.ports)), np.inf)
        doors = [None] * NH
        for h in range(NH):
            dr = cs7._house_door(st, h)
            if dr is not None:
                s, r, t, Pd, acc, left = dr
                a, b, _, _ = cs7._bracket(st, s, t)
                doors[h] = (a, b, Pd, acc)
        for j, k in enumerate(self.ports):
            P0 = self.H.st[k]["xy"]
            D = cs7._seg_dist_mat_sub(C, np.array([P0]), segs)[0]
            s = int(segs[np.lexsort((segs, D))[0]])
            t, Pd, acc = cs7.proj(C, s, P0)
            a, b, _, _ = cs7._bracket(st, s, t)
            dist = {}
            heap = [(acc + cs7.kdist(x, Pd), x) for x in {a, b}]
            heapq.heapify(heap)
            while heap:
                d, x = heapq.heappop(heap)
                if x in dist:
                    continue
                dist[x] = d
                for y, e in st.adj.get(x, {}).items():
                    if y not in dist:
                        heapq.heappush(heap, (d + min(e.values()), y))
            for h in range(NH):
                dr = doors[h]
                if dr is None:
                    continue
                a, b, Pd, acc = dr
                best = np.inf
                for x in (a, b):
                    if x in dist:
                        best = min(best, dist[x] + cs7.kdist(x, Pd) + acc)
                out[h, j] = best
        self._walk[key] = out
        self.t_walk += time.time() - t0
        return out


# ================================================================ 生计 v15 = v14 生计 + 港口分行 + 菜农 / 渔户
def livelihoods15(H, W):
    L = E14.livelihoods(H)
    liv = L["liv"].copy()
    first = L["first"]
    u = stable_u(H.idnum, 15)
    # 港货商 → 港口各行
    m = liv == 5
    codes = list(A["port_split"].keys()); w = np.cumsum(list(A["port_split"].values())); w /= w[-1]
    liv[m] = np.array(codes)[np.searchsorted(w, u[m], side="right").clip(0, len(codes) - 1)]
    # 菜农：雇工 / 脚夫，离农田 ≤ R_field 或城墙外；首次在册年须农田已建（AF32）
    u2 = stable_u(H.idnum, 16)
    cand = np.isin(liv, WORKERS) & ((W.d_field <= A["R_field"]) | W.outside_wall) & (first >= 32)
    farm = cand & (u2 < A["p_farm"])
    liv[farm] = 15
    # 渔户：雇工 / 脚夫，离海岸代理 ≤ R_coast
    cand = np.isin(liv, WORKERS) & (W.d_coast <= A["R_coast"])
    liv[cand & (u2 < A["p_fish"])] = 16
    liv[first < 0] = -1
    L = dict(L); L["liv"] = liv
    return L


# ================================================================ 经济
class Econ:
    def __init__(self, H, W, ships_mult=1.0):
        self.H, self.W = H, W
        self.L = livelihoods15(H, W)
        self.liv = self.L["liv"]
        self.ships_mult = ships_mult
        self.inst_keys, self.inst_ix = [], {}
        for e in EXT:
            self.I(("外", e))
        self.hseed = (stable_u(H.idnum, 3) * 1e6).astype(np.int64)

    def I(self, key):
        if key not in self.inst_ix:
            self.inst_ix[key] = self.H.NH + len(self.inst_keys)
            self.inst_keys.append(key)
        return self.inst_ix[key]

    def ships(self, yr):
        return A["ships_base"] * self.ships_mult * yr.mod.get("ships_mult", 1.0)

    # ---------------------------------------------------------- 年视图派生量（v14 + 港口步行、菜/鱼价）
    def derive(self, yr, S):
        H = self.H; Y = yr.Y; al = yr.alive
        # v14 的派生量（市场节点、价格、门牌序、距离）—— 借 v14 Econ.derive 的实现（只读调用）
        d = E14.Econ.derive(self, yr, S)
        d["liv"] = self.liv[al]
        Wk = self.W.walk(yr)
        d["walk"] = Wk[al]                                     # n × 港口设施数
        nh = len(self.W.harbors)
        d["home_port"] = np.argmin(d["walk"][:, :nh], 1)       # 最近（步行）商港
        d["home_store"] = np.argmin(d["walk"], 1)              # 最近（步行）港口设施（含 horrea）
        MX = d["MX"]
        FX = self.W.field_xy
        HX = np.array([H.st[k]["xy"] for k in self.W.harbors])
        d["p_veg"] = 1 + A["k_price"] * np.min(np.hypot(MX[:, None, 0] - FX[None, :, 0], MX[:, None, 1] - FX[None, :, 1]), 1)
        d["p_fish"] = 1 + A["k_price"] * np.min(np.hypot(MX[:, None, 0] - HX[None, :, 0], MX[:, None, 1] - HX[None, :, 1]), 1)
        return d

    landlords = E14.Econ.landlords

    # ---------------------------------------------------------- 主计算
    def step(self, yr, S, inc=None):
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
        alset = set(al.tolist())
        R = Rows()
        gone = np.setdiff1d(S.alive_prev, al) if len(S.alive_prev) else np.zeros(0, np.int64)
        new = al[(H.built[al] == Y) & (Y > Y0)]
        ships = self.ships(yr)
        sfac = (ships / A["ships_base"]) ** A["export_elast"]
        # ------------------- K0 粮（v14 原样）
        t0 = time.perf_counter()
        R.add("口粮调拨", X["皇家粮运"], AN, yr.food, "账本 food_cap（chronicle）", -1, 0)
        gl = sorted(set(dv["grain"]))
        gi = {k: I(("仓", k)) for k in gl}
        cnt = collections.Counter(dv["grain"])
        for k in gl:
            R.add("口粮下仓", AN, gi[k], cnt[k] * yr.ration, "v7 口粮全城均分 + 配给点=最近粮仓（走街）", -1, 0)
        R.add("口粮配给", np.array([gi[k] for k in dv["grain"]]), al, yr.ration, "v7 口粮全城均分 + 配给点=最近粮仓（走街）", al, 0)
        tim["grain"] = time.perf_counter() - t0
        # ------------------- K1 每户固定项（按户可增量）
        t0 = time.perf_counter()
        ma = np.ones(n, bool) if inc is None else inc["dirty_a"]
        ix = np.nonzero(ma)[0]
        g_ = al[ix]
        own_of = np.where(dv["owner"][ix] | (ll[g_] < 0), g_, ll[g_])
        fh = np.array([hold.get(("fang_head", f), -1) for f in dv["fang"][ix]])
        dh = np.array([hold.get(("district_head", x), -1) for x in dv["d"][ix]])
        coll = np.where(fh >= 0, fh, np.where(dh >= 0, dh, EP))
        R.add("房税", own_of, coll, P4["tau"], "v4 tau=0.5/栋 房主交", g_, 1)
        R.add("人头税", g_, coll, A["head_tax"], "新假设 人头税 0.2/户", g_, 1)
        gm = dv["guild"][ix] != ""
        gh = np.array([hold.get(("guild_head", f"{a}×{b}"), -1) for a, b in zip(dv["d"][ix][gm], dv["guild"][ix][gm])])
        R.add("行会钱", g_[gm], np.where(gh >= 0, gh, EP) if len(gh) else np.zeros(0, np.int64), P4["delta"], "v4 delta=0.3/行会户", g_[gm], 1)
        ar = dv["arian"][ix] != ""
        pa = (~ar) & (dv["parish"][ix] != "")
        R.add("奉献", g_[ar], np.array([I(("官", "arian_elder|" + x)) for x in dv["arian"][ix][ar]], np.int64), P4["omega"], "v4 omega=0.3/教区户", g_[ar], 1)
        R.add("奉献", g_[pa], np.array([I(("官", "parish_elder|" + x)) for x in dv["parish"][ix][pa]], np.int64), P4["omega"], "v4 omega=0.3/教区户", g_[pa], 1)
        ten = (~dv["owner"][ix]) & (ll[g_] >= 0)
        R.add("租金", g_[ten], ll[g_[ten]], P4["rho"], "v4 rho=1.0/租户；v2 房东规则", g_[ten], 1)
        sold = liv[ix] == 9
        R.add("兵饷", NY, g_[sold], A["soldier_pay"], "兵饷 v4 sigma=1.0 + 皇库（假设）", g_[sold], 1)
        for c_, v_, tn in ((4, A["export_work"], "出口:手工(船商付)"), (3, A["export_shop"], "出口:手工(船商付)"), (16, A["export_fish"], "出口:鱼(船商付)")):
            wk = liv[ix] == c_
            R.add(tn, X["船商"], g_[wk], v_ * sfac, f"出口 ∝ (到港量/基准)^{A['export_elast']}（假设）", g_[wk], 1)
        nw = (H.built[g_] == Y) & (Y > Y0)
        R.add("迁入带钱", X["迁入"], g_[nw], A["c_in"], "迁入/迁出（外部源汇，假设）", g_[nw], 1)
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
            R.add("建设:新房", ll[g_[i]], b, A["house_cost"], "新房造价 10（假设）付最近同区营造户", g_[i], 1)
        tim["fixed"] = time.perf_counter() - t0
        # ------------------- 还款、俸给、兵饷、补偿、账本工程（全量，小）
        t0 = time.perf_counter()
        rp = [(L[1], L[0], min(L[3], L[2])) for L in S.loans if L[2] > 1e-9 and L[1] in alset and L[0] in alset]
        if rp:
            R.add("还款", np.array([x[0] for x in rp]), np.array([x[1] for x in rp]), np.array([x[2] for x in rp]), "v2 债（cap4，4 年，无息）", -1, 9)
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
            R.add("俸给", src_, np.array([x[0] for x in lst]), np.array([x[1] for x in lst]), "俸给（v14 假设）", -1, 9)
        ns = int((liv == 9).sum())
        R.add("兵饷", X["皇库"], NY, A["soldier_imperial"] * ns, "兵饷 v4 sigma=1.0 + 皇库（假设）", -1, 9)
        R.add("兵饷", EP, NY, P4["sigma"] * ns, "兵饷 v4 sigma=1.0 + 皇库（假设）", -1, 9)
        for g in gone:
            if H.dest[g] != Y:
                continue
            if H.built[g] <= Y0:
                R.add("拆迁补偿", EP, g, P4["comp"] * P4["V_h"], "v4 comp=0.5×V_h 给房主", -1, 9)
            else:
                lg = S.landlord[g]
                R.add("拆迁补偿", EP, lg if (lg >= 0 and lg in alset) else g, P4["comp"] * P4["V_h"], "v4 comp=0.5×V_h 给房主", -1, 9)
                R.add("搬迁费", EP, g, P4["reloc"], "v4 reloc=1.0/租户", -1, 9)
        for w in H.works:
            if w["year"] != Y or w["id"] in yr.drop or not len(bl):
                continue
            wx = H.st[w["id"]]["xy"]
            dd = np.hypot(*(H.xy[al[bl]] - wx).T)
            pick = al[bl[np.lexsort((H.idnum[al[bl]], dd))[:A["builders_per_work"]]]]
            pay = w["payer"]; cost = w["cost"]
            src = {"emperor": [(X["皇库"], 1.0)], "merchants": [(X["城外商人"], 1.0)], "church_private": [(BN, 1.0)],
                   "bishop_arian": [(BA, 1.0)], "prefect": [(EP, 1.0)], "prefect+levy": [(EP, 1.0)],
                   "district_xero+bishop_nicene": [(EP, 0.5), (BN, 0.5)]}.get(pay, [(EP, 1.0)])
            for s_, sh in src:
                R.add("建设:公共工程", s_, pick, cost * sh / len(pick), "v4 账本工程造价×出资方 → 最近 20 户营造户", -1, 9)
            if pay == "prefect+levy":
                R.add("修水摊派", al[dv["water"] == w["id"]], EP, P4["levy"], "v4 levy=1.0/户（新池供水组）", -1, 9)
        tim["misc"] = time.perf_counter() - t0
        # ------------------- KP 港口（全量，O(港口行户)）：到港量 → 货值 → 关税、港费 → 港口行户；港口雇工按步行距离与行会
        t0 = time.perf_counter()
        hb = self.W.harbors; nh = len(hb)
        aw = np.array([self.W.harbor_area[k] for k in hb]); sh = aw / aw.sum()
        S_h = ships * sh; T_h = S_h * A["cargo"]
        port_rev = collections.defaultdict(float)
        for j, k in enumerate(hb):
            cu = I(("官", "customs|" + k))
            kt = A["kommerkion"] * T_h[j]
            R.add("关税", X["船商"], cu, kt, "kommerkion 10% 货值（8 世纪后制度，4–5 世纪对应 octava 12.5%；存疑）", -1, 8)
            R.add("关税分成(→城市长官)", cu, EP, A["customs_city_share"] * kt, "关税 1/3 留城（仿 CTh 4.13.7 城市得本地 vectigal 三分之一；存疑）", -1, 8)
            R.add("关税上解(→皇库)", cu, X["皇库"], (1 - A["customs_city_share"]) * kt, "关税其余上解皇库（sacrae largitiones；假设）", -1, 8)
        pools = []   # (类型, 行, 设施下标, 金额)
        for j in range(nh):
            pools += [("港费:装卸", 10, j, A["f_handle"] * T_h[j]), ("港费:船修", 12, j, A["r_ship"] * S_h[j]),
                      ("港费:牙佣", 13, j, A["f_broker"] * T_h[j]), ("港费:兑钱", 14, j, A["f_change"] * T_h[j]),
                      ("转口差价(船商付)", 5, j, A["m_reexp"] * (1 - A["local_share"]) * T_h[j])]
        Ttot = T_h.sum()
        for j in range(len(self.W.ports)):
            k = self.W.ports[j]
            amt = A["f_store"] * Ttot * (A["w_horrea"] if H.st[k]["type"] == "warehouse" else (1 - A["w_horrea"]) * sh[j])
            pools.append(("港费:仓储", 11, j, amt))
        rule_p = "到港量×货值×费率 → 本港（步行最近）该行户均分；本港无此行 → 全城该行均分（假设）"
        for tn, code, j, amt in pools:
            home = dv["home_store"] if code == 11 else dv["home_port"]
            m = np.nonzero((liv == code) & (home == j))[0]
            if not len(m):
                m = np.nonzero(liv == code)[0]
            if not len(m) or amt <= 0:
                continue
            R.add(tn, X["船商"], al[m], amt / len(m), rule_p, -1, 8)
            for i in m:
                port_rev[int(i)] += amt / len(m)
        # 港口雇工：每户工位 = 当年港费营收 × 50% ÷ 工钱；工人按（码头脚夫=港役行会 优先，步行距离，港口，门牌序）贪心
        emp = np.array(sorted(port_rev, key=lambda i: (dv["home_port"][i], dv["door_rank"][i])), np.int64)
        fr = A["port_wage_share"] * np.array([port_rev[int(i)] for i in emp]) / A["wage"]
        slots = np.floor(fr + 1e-9).astype(np.int64)
        extra = int(np.floor(fr.sum() + 1e-9)) - int(slots.sum())
        if extra > 0:
            slots[np.argsort(-(fr - slots), kind="stable")[:extra]] += 1
        q_by_port = collections.defaultdict(collections.deque)
        for i, s_ in zip(emp, slots):
            for _ in range(int(s_)):
                q_by_port[int(dv["home_port"][i])].append(int(i))
        wk_all = np.nonzero(np.isin(liv, WORKERS))[0]
        Wd = dv["walk"][wk_all][:, :nh]
        pi, pj = np.nonzero(Wd <= A["R_walk"])
        pw = wk_all[pi]
        order = np.lexsort((dv["door_rank"][pw], pj, Wd[pi, pj], (liv[pw] != 1).astype(int)))
        taken = np.zeros(n, bool)
        pa_, pb_ = [], []
        for o in order:
            i = int(pw[o]); j = int(pj[o])
            if taken[i] or not q_by_port[j]:
                continue
            e = q_by_port[j].popleft(); taken[i] = True
            pa_.append(al[e]); pb_.append(al[i])
        port_slots = int(slots.sum())
        if pa_:
            R.add("工钱:港口", np.array(pa_), np.array(pb_), A["wage"], "港口雇工：步行 ≤R_walk，码头脚夫（港役行会，假设）优先，再按步行距离、门牌序", np.array(pb_), 8)
        tim["port"] = time.perf_counter() - t0
        # ------------------- K2 区内工钱（v14 匹配，去掉港口雇主与已被港口雇走的人；按区签名可增量）
        t0 = time.perf_counter()
        rev = S.rev_prev
        dnames = sorted(set(dv["d"]))
        dsig = {}
        jobs_d = {}
        dist_slots = 0
        for dname in dnames:
            ii = np.nonzero(dv["d"] == dname)[0]
            empd = ii[np.isin(liv[ii], DIST_EMP)]
            empd = empd[np.argsort(dv["door_rank"][empd], kind="stable")]
            frd = A["wage_share"] * rev[al[empd]] / A["wage"]
            sl_ = np.floor(frd + 1e-9).astype(np.int64)
            ex = int(np.floor(frd.sum() + 1e-9)) - int(sl_.sum())
            if ex > 0:
                sl_[np.argsort(-(frd - sl_), kind="stable")[:ex]] += 1
            sl = np.repeat(empd, sl_)
            wk_ = ii[np.isin(liv[ii], WORKERS) & ~taken[ii]]
            wk_ = wk_[np.argsort(dv["door_rank"][wk_], kind="stable")]
            h_ = hashlib.sha1()
            for arr in (al[sl], al[wk_], liv[wk_], liv[sl]):
                h_.update(np.ascontiguousarray(arr).tobytes())
            h_.update("|".join(dv["street"][wk_].tolist() + ["#"] + dv["street"][sl].tolist()).encode())
            dsig[dname] = h_.hexdigest()
            dist_slots += len(sl)
            jobs_d[dname] = (sl, wk_)
        if inc is None:
            dset = dnames
        else:
            old = inc["cache"]["dsig"]
            dset = sorted(set(x for x in dnames if old.get(x) != dsig[x]) | (set(inc["dirty_d"]) & set(dnames)))
        for dname in dset:
            sl, wk_ = jobs_d[dname]
            free_s = np.ones(len(sl), bool); free_w = np.ones(len(wk_), bool)
            st_w = dv["street"][wk_]; st_s = dv["street"][sl]
            pref_w = np.zeros(len(wk_), int); pref_s = np.zeros(len(sl), int)
            for phase in range(4):
                if not free_s.any() or not free_w.any():
                    break
                kw = [(st_w[i] if phase < 2 else "", pref_w[i] if phase in (0, 2) else 0) for i in range(len(wk_))]
                ks = [(st_s[i] if phase < 2 else "", pref_s[i] if phase in (0, 2) else 0) for i in range(len(sl))]
                qs = collections.defaultdict(collections.deque)
                for i in np.nonzero(free_s)[0]:
                    qs[ks[i]].append(i)
                a2, b2 = [], []
                for i in np.nonzero(free_w)[0]:
                    q = qs.get(kw[i])
                    if q:
                        j = q.popleft(); free_s[j] = False; free_w[i] = False
                        a2.append(al[sl[j]]); b2.append(al[wk_[i]])
                if a2:
                    R.add("工钱", np.array(a2), np.array(b2), A["wage"], "工钱：同街优先，再同区（v14）", np.array(b2), 2)
        tim["wages"] = time.perf_counter() - t0
        # ------------------- 合并增量缓存（K1 / K2 干净行沿用）
        t0 = time.perf_counter()
        Rnew = R.cat()
        if inc is not None:
            C = inc["cache"]["rows"]
            pos = np.searchsorted(al, np.clip(C["o"], 0, None)); okp = (C["o"] >= 0) & (pos < n)
            hit = np.zeros(len(C["t"]), bool); hit[okp] = al[np.clip(pos[okp], 0, n - 1)] == C["o"][okp]
            ia = np.where(hit, np.clip(pos, 0, n - 1), 0)
            dmask = np.array([x in set(dset) for x in dv["d"]], bool)
            dd_ = dmask[ia] if len(ia) else np.zeros(0, bool)
            keep1 = (C["k"] == 1) & hit & ~ma[ia]
            keep2 = (C["k"] == 2) & hit & ~dd_
            Rpre = {x: np.concatenate([C[x][keep1 | keep2], Rnew[x]]) for x in Rnew}
        else:
            Rpre = Rnew
        tim["merge"] = time.perf_counter() - t0
        # ------------------- K3 买卖（按买方签名可增量）
        t0 = time.perf_counter()
        cash_mid = self._net_house(Rpre, al, S)
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
                for m_ in np.nonzero(~has)[0]:
                    dd = np.hypot(*(dv["MX"][hx] - dv["MX"][m_]).T); eff[m_] = hx[int(np.argmin(dd))]
            sellers[gd] = (tab, eff, has.any())
        city_sell = {}
        for gd, code in (("veg", 15), ("fish", 16)):
            s_i = np.nonzero(liv == code)[0]
            city_sell[gd] = al[s_i[np.argsort(dv["door_rank"][s_i], kind="stable")]]
        wl6 = np.nonzero(liv == 6)[0]
        wsell = collections.defaultdict(list); wsell_d = collections.defaultdict(list)
        for i in wl6[np.argsort(dv["door_rank"][wl6], kind="stable")]:
            wsell[dv["water"][i]].append(int(al[i])); wsell_d[dv["d"][i]].append(int(al[i]))
        q = dict(bread=np.full(n, A["q_bread"]), craft=np.full(n, A["q_craft"]), harbor=np.full(n, A["q_harbor"]),
                 veg=np.full(n, A["q_veg"]), fish=np.full(n, A["q_fish"]))
        q["craft"][liv == 8] *= A["fine_mult"]; q["harbor"][liv == 8] *= A["fine_mult"]
        node = dv["node"]
        price = {}
        for gd in ("bread", "craft", "harbor"):
            tab, eff, ok = sellers[gd]
            price[gd] = dv["p_" + gd][eff[node]]
        price["veg"] = dv["p_veg"][node]; price["fish"] = dv["p_fish"][node]
        avail = {gd: (sellers[gd][2] if gd in sellers else len(city_sell[gd]) > 0) for gd in price}
        need = sum(q[gd] * price[gd] for gd in price if avail[gd]) + A["q_water"] * dv["p_water"]
        scale = np.clip(cash_mid / need, A["floor"], 1.0)
        extra = (0.0 if getattr(self, "boot", False) else A["c_surplus"]) * np.maximum(0.0, cash_mid - need - A["buffer"])
        dv["scale"] = scale; dv["price"] = price
        hs = self.hseed[al]
        def mix(a, b):
            return (a * np.int64(1000003) + b) % np.int64(2 ** 61 - 1)
        sig = np.zeros(n, np.int64)
        sel = {}
        for gd in ("bread", "craft", "harbor"):
            tab, eff, ok = sellers[gd]
            cntn = np.array([len(t) for t in tab]); eN = eff[node]
            flat = np.array([x for t in tab for x in t] or [0], np.int64); offn = np.concatenate([[0], np.cumsum(cntn)[:-1]])
            sel[gd] = np.where(cntn[eN] > 0, flat[np.minimum(offn[eN] + hs % np.maximum(cntn[eN], 1), len(flat) - 1)], -1)
        for gd in ("veg", "fish"):
            cs_ = city_sell[gd]
            sel[gd] = cs_[hs % len(cs_)] if len(cs_) else np.full(n, -1, np.int64)
        sel["water"] = np.array([(lambda t_: t_[hs[i] % len(t_)] if t_ else -1)(wsell.get(dv["water"][i]) or wsell_d.get(dv["d"][i])) for i in range(n)], np.int64)
        amt = {}
        for gd in ("bread", "craft", "harbor", "veg", "fish"):
            amt[gd] = scale * q[gd] * price[gd] + extra * A["surplus_mix"].get(gd, 0.0)
        amt["water"] = scale * A["q_water"] * dv["p_water"]
        for gd in amt:
            sig = mix(sig, sel[gd] + 7); sig = mix(sig, np.round(amt[gd] * 1e9).astype(np.int64))
        sig_g = np.full(H.NH, -1, np.int64); sig_g[al] = sig
        mc = np.ones(n, bool) if inc is None else inc["cache"]["sig_g"][al] != sig
        R = Rows()
        mi = np.nonzero(mc)[0]
        for gd, tname in (("bread", "买卖:面包"), ("craft", "买卖:手工"), ("harbor", "买卖:港货"), ("veg", "买卖:菜蔬"), ("fish", "买卖:鱼"), ("water", "买卖:水")):
            b_ = mi[sel[gd][mi] >= 0]
            if len(b_):
                R.add(tname, al[b_], sel[gd][b_], amt[gd][b_], "户需求表×市场价；盈余 30% 追加手工/港货/鱼（新假设）", al[b_], 3)
        Rc = R.cat()
        if inc is not None:
            C = inc["cache"]["rows"]
            pos = np.searchsorted(al, np.clip(C["o"], 0, None)); okp = (C["o"] >= 0) & (pos < n)
            hit = np.zeros(len(C["t"]), bool); hit[okp] = al[np.clip(pos[okp], 0, n - 1)] == C["o"][okp]
            ia = np.where(hit, np.clip(pos, 0, n - 1), 0)
            keep3 = (C["k"] == 3) & hit & ~mc[ia]
            Rn = {x: np.concatenate([Rpre[x], C[x][keep3], Rc[x]]) for x in Rc}
        else:
            Rn = catd(Rpre, Rc)
        tim["purchase"] = time.perf_counter() - t0
        tim["dirty_buyers"] = int(mc.sum())
        # ------------------- K4 聚合（全量）：卖方成本、原料、税链、奉献
        t0 = time.perf_counter()
        R2 = Rows()
        NT = H.NH + len(self.inst_keys) + 256
        def tot(names, R_=None):
            R_ = Rn if R_ is None else R_
            m = np.isin(R_["t"], [TI[t] for t in names])
            return np.bincount(R_["b"][m], R_["v"][m], NT)
        s_bread = tot(["买卖:面包"]); s_craft = tot(["买卖:手工", "出口:手工(船商付)"])
        s_veg = tot(["买卖:菜蔬"]); s_fish = tot(["买卖:鱼", "出口:鱼(船商付)"])
        g2 = al[liv == 2]; R2.add("进货/原料(付城外)", g2, X["城外贸易"], A["bread_cost"] * s_bread[g2], "面包 20% 进货付城外（v14）", -1, 4)
        g15 = al[liv == 15]; R2.add("进货/原料(付城外)", g15, X["城外贸易"], A["farm_cost"] * s_veg[g15], "菜农 10% 种子农具付城外（假设）", -1, 4)
        g16 = al[liv == 16]; R2.add("进货/原料(付城外)", g16, X["城外贸易"], A["fish_cost"] * s_fish[g16], "渔户 15% 网具船具付城外（假设）", -1, 4)
        # 手工原料：30% 营收；其中 40% 买本港货商（步行最近港口的港货商，散列定一家），60% 付城外
        merch = np.nonzero(liv == 5)[0]
        cr = np.nonzero(np.isin(liv, CRAFT))[0]
        raw = A["craft_cost"] * s_craft[al[cr]]
        R2.add("进货/原料(付城外)", al[cr], X["城外贸易"], (1 - A["craft_local_raw"]) * raw, "手工原料 30%×60% 付城外（假设）", -1, 4)
        if len(merch):
            mb = collections.defaultdict(list)
            for i in merch[np.argsort(dv["door_rank"][merch], kind="stable")]:
                mb[int(dv["home_port"][i])].append(int(al[i]))
            allm = al[merch[np.argsort(dv["door_rank"][merch], kind="stable")]]
            tgt = np.array([(lambda t_: t_[hs[i] % len(t_)])(mb.get(int(dv["home_port"][i])) or list(allm)) for i in cr], np.int64)
            R2.add("原料(转口货)", al[cr], tgt, A["craft_local_raw"] * raw, "手工原料 30%×40% 买本港港货商（转口货，假设）", -1, 4)
        else:
            R2.add("进货/原料(付城外)", al[cr], X["城外贸易"], A["craft_local_raw"] * raw, "手工原料（无港货商）付城外", -1, 4)
        R2c0 = R2.cat()
        s_h = tot(["买卖:港货"]) + tot(["原料(转口货)"], R2c0)
        g5 = al[liv == 5]
        R2.add("港货进价(付船商)", g5, X["船商"], A["harbor_cost"] * s_h[g5], "港货商留城货进价 = 售价 50%（付船商，假设）", -1, 4)
        # 税链（v4）
        tx = tot(["房税", "人头税"])
        fang_of = {g: jur for (off, jur), g in hold.items() if off == "fang_head" and g >= 0}
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
                R2.add("税钱上缴(坊长→区长)", g, dhh, up, "v4 alpha=0.10 坊长截留", -1, 4); dtx[dhh] += up
            else:
                R2.add("税钱上缴(区长→城市长官)", g, EP, up, "v4 alpha=0.10 坊长截留", -1, 4)
        for (off, jur), g in sorted(hold.items()):
            if off == "district_head" and g >= 0:
                t_ = dtx[g] + (tx[g] if g not in fang_of else 0.0)
                if t_ > 0:
                    R2.add("税钱上缴(区长→城市长官)", g, EP, (1 - P4["beta"]) * t_, "v4 beta=0.10 区长截留", -1, 4)
        gt = tot(["行会钱"])
        for g in np.nonzero(gt[:H.NH] > 0)[0]:
            R2.add("行会钱上缴(行会头→城市长官)", g, EP, (1 - P4["gamma"]) * gt[g], "v4 gamma=0.10 行会头截留", -1, 4)
        R2c = R2.cat()
        ep_tax = (np.bincount(R2c["b"], R2c["v"], NT)[EP] + sum(Rn["v"][(Rn["t"] == TI[t]) & (Rn["b"] == EP)].sum() for t in ("房税", "人头税", "行会钱")))
        R2.add("上交皇库", EP, X["皇库"], P4["remit"] * ep_tax, "v4 remit=0.5 上交皇库（不含关税分成）", -1, 4)
        of = tot(["奉献"])
        for key, e in sorted(self.inst_ix.items(), key=lambda x: x[1]):
            if key[0] == "官" and "|" in key[1] and not key[1].startswith("customs") and of[e] > 0:
                off, ch = key[1].split("|")
                hg = hold.get((off, ch), -1)
                bishop = BA if off == "arian_elder" else BN
                skim = P4["eps"] * of[e] if hg >= 0 else 0.0
                if skim:
                    R2.add("奉献截留(长老)", e, hg, skim, "v4 eps=0.05 长老截留", -1, 4)
                R2.add("奉献上缴(→主教)", e, bishop, of[e] - skim, "v4 omega 上缴主教", -1, 4)
        tim["agg"] = time.perf_counter() - t0
        # ------------------- K5 库银支出规则（全量）
        t0 = time.perf_counter()
        R2c = R2.cat()
        Rk = catd(Rn, R2c)
        cnow = self._cash_after(Rk, S, NT)
        R5 = Rows()
        bld = np.nonzero(liv == 7)[0]
        def pay_builders(src, xy, k_, amount, tn, rl):
            if amount <= 1e-12 or not len(bld):
                return
            dd = np.hypot(*(H.xy[al[bld]] - xy).T)
            pick = al[bld[np.lexsort((H.idnum[al[bld]], dd))[:k_]]]
            R5.add(tn, src, pick, amount / len(pick), rl, -1, 5)
        poor_prev = S.inc_prev[al] < A["poverty"]
        spend_log = {}
        for bishop, bk, mask, faith in ((BN, "bishop_nicene", dv["arian"] == "", "n"), (BA, "bishop_arian", dv["arian"] != "", "a")):
            av = max(0.0, cnow[bishop])
            sp = (1 - A["retain_bishop"]) * av
            el = al[poor_prev & mask & (H.built[al] < Y)]
            alms = min(A["alms_share"] * sp, A["alms_cap"] * len(el))
            if len(el) and alms > 0:
                R5.add("施舍", bishop, el, alms / len(el), "主教库：可用×(1−留存 50%)的 1/3 施舍上年收入<线的本派户，每户 ≤2.0（仿 Gelasius 494 四分法，主教份另由俸给付）", -1, 5)
            cl = [g for (off, ch), g in sorted(hold.items()) if g >= 0 and g in alset and off == ("arian_elder" if faith == "a" else "parish_elder")]
            clergy = A["clergy_share"] * sp if cl else 0.0
            if cl and clergy > 0:
                R5.add("神职俸给", bishop, np.array(cl), clergy / len(cl), "主教库：1/3 神职俸给（长老任职户均分；仿 Gelasius 四分法）", -1, 5)
            church = sp - alms - clergy
            chs = [k for k in H.standing(Y, ("church",), yr.drop) if (("arian" in k) == (faith == "a"))]
            for k in chs:
                pay_builders(bishop, H.st[k]["xy"], A["builders_per_church"], church / len(chs), "教堂营造", "主教库：其余 → 本派各教堂维修/新建，离教堂最近 25 户营造户承建（新规则）")
            spend_log[bk] = dict(available=round(av, 2), spend=round(sp, 2), alms=round(alms, 2), clergy=round(clergy, 2), church=round(church, 2), poor=len(el))
        # 城市长官：可用超出底线部分 × (1−留存)；先发坊长/区长官俸，再 40% 公役，余下城墙/街/水池维护
        av = cnow[EP]
        sp = (1 - A["retain_eparch"]) * max(0.0, av - A["eparch_floor"])
        offs = [(g, A["stip_fang"] if off == "fang_head" else A["stip_district"]) for (off, jur), g in sorted(hold.items())
                if off in ("fang_head", "district_head") and g >= 0 and g in alset]
        need_st = sum(v for _, v in offs)
        sc = min(1.0, sp / need_st) if need_st > 0 else 0.0
        if offs and sc > 0:
            R5.add("官俸(坊长/区长)", EP, np.array([g for g, _ in offs]), np.array([v for _, v in offs]) * sc, "城市长官库：坊长 1.0、区长 3.0（新规则）", -1, 5)
        rest = sp - need_st * sc
        pw_budget = A["pw_share"] * rest
        emp_w = set(Rn["b"][np.isin(Rn["t"], [TI["工钱"], TI["工钱:港口"]])].tolist())
        un = np.array([i for i in np.nonzero(np.isin(liv, WORKERS))[0] if int(al[i]) not in emp_w], np.int64)
        jobs = int(pw_budget // A["wage"])
        n_pw = 0
        if jobs > 0 and len(un):
            k_all = min(jobs, len(un))
            dl = sorted(set(dv["d"][un]))
            cntd = np.array([(dv["d"][un] == x).sum() for x in dl], float)
            qd = k_all * cntd / cntd.sum(); fl = np.floor(qd + 1e-9).astype(int)
            for j in np.argsort(-(qd - fl), kind="stable")[:k_all - fl.sum()]:
                fl[j] += 1
            pick = []
            for x, k_ in zip(dl, fl):
                u_ = un[dv["d"][un] == x]
                pick.extend(u_[np.argsort(dv["door_rank"][u_], kind="stable")][:k_].tolist())
            pick = np.array(sorted(pick), np.int64)
            n_pw = len(pick)
            R5.add("公役工钱", EP, al[pick], A["wage"], "城市长官库：40% 雇无主雇工（按区无主人数分额、区内门牌序，新规则）", -1, 5)
        maint = rest - n_pw * A["wage"]
        ms = [k for k in H.standing(Y, ("wall", "road", "cistern", "aqueduct", "aqueduct_bridge", "gate"), yr.drop)]
        for k in ms:
            pay_builders(EP, H.st[k]["xy"], A["builders_per_struct"], maint / len(ms), "城防街渠维护", "城市长官库：其余 → 城墙/街/水池/水渠/城门 均分，离设施形心最近 20 户营造户（新规则）")
        spend_log["eparch"] = dict(available=round(av, 2), spend=round(sp, 2), officials=round(need_st * sc, 2), public_works=round(n_pw * A["wage"], 2), maintenance=round(maint, 2), unemployed_before=len(un))
        tim["treasury"] = time.perf_counter() - t0
        # ------------------- 年末：迁出、借贷（v2）
        t0 = time.perf_counter()
        Rall = catd(Rk, R5.cat())
        cash = self._cash_after(Rall, S, NT)
        R3 = Rows()
        gp = np.array([g for g in gone if cash[g] > 0], np.int64)
        if len(gp):
            R3.add("迁出带钱", gp, X["迁出"], cash[gp], "迁入/迁出（外部源汇，假设）", -1, 6)
        act = np.zeros(H.NH, np.int64)
        for L in S.loans:
            if L[2] > 1e-9 and L[1] in alset:
                act[L[0]] += 1
        lend_ok = dv["owner"] & np.isin(liv, (2, 8))
        lenders_by_d = {x: (lambda Ld: Ld[np.argsort(H.idnum[Ld], kind="stable")])(al[lend_ok & (dv["d"] == x)]) for x in sorted(set(dv["d"]))}
        bor = np.nonzero(cash[al] < -1e-9)[0]
        bor = bor[np.argsort(H.idnum[al[bor]], kind="stable")]
        lc = cash.copy(); unfunded = 0; newloans = []; la, lb, lv = [], [], []
        for i in bor:
            g = int(al[i]); amt_ = -lc[g]
            Ld = lenders_by_d.get(dv["d"][i])
            if Ld is None or not len(Ld):
                unfunded += 1; continue
            ok = (act[Ld] < DEBT["cap"]) & (lc[Ld] >= amt_ + 2.0) & (Ld != g)
            if not ok.any():
                unfunded += 1; continue
            c = Ld[ok]
            dd = np.hypot(*(H.xy[c] - H.xy[g]).T)
            o = int(c[np.lexsort((H.idnum[c], dd))[0]])
            la.append(o); lb.append(g); lv.append(amt_)
            lc[o] -= amt_; lc[g] += amt_; act[o] += 1
            newloans.append([o, g, amt_, amt_ / DEBT["years"], Y])
        if la:
            R3.add("借贷", np.array(la), np.array(lb), np.array(lv), "v2 债（cap4，4 年，无息）", -1, 6)
        Rall = catd(Rall, R3.cat())
        tim["close"] = time.perf_counter() - t0
        return dict(rows=Rall, sig_g=sig_g, dsig=dsig, dv=dv, ll=ll, newloans=newloans, unfunded=unfunded, gone=gone, new=new,
                    tim=tim, NT=NT, ships=ships, T=float(Ttot), spend=spend_log, n_pw=n_pw, taken=int(taken.sum()),
                    slots=dict(port=port_slots, district=dist_slots))

    def _net_house(self, R, al, S):
        NT = self.H.NH + len(self.inst_keys) + 256
        m = ~np.isin(R["t"], GRAIN_T)
        net = np.bincount(R["b"][m], R["v"][m], NT) - np.bincount(R["a"][m], R["v"][m], NT)
        return S.cash[al] + net[al]

    def _cash_after(self, R, S, NT):
        NT = max(NT, self.H.NH + len(self.inst_keys) + 1)
        m = ~np.isin(R["t"], GRAIN_T)
        net = np.bincount(R["b"][m], R["v"][m], NT) - np.bincount(R["a"][m], R["v"][m], NT)
        c = np.zeros(NT); c[:self.H.NH] = S.cash
        for k, v in S.inst.items():
            c[self.inst_ix[k]] = v
        return c + net

    def advance(self, yr, S, out):
        H = self.H; R = out["rows"]; al = yr.alive
        NT = max(out["NT"], H.NH + len(self.inst_keys) + 1)
        c = self._cash_after(R, S, NT)
        S2 = S.copy()
        S2.cash = c[:H.NH].copy()
        for k, e in self.inst_ix.items():
            S2.inst[k] = float(c[e])
        S2.cash[out["gone"]] = 0.0
        m = ~np.isin(R["t"], GRAIN_T)
        fin = np.isin(R["t"], FIN_T)
        inc = np.bincount(R["b"][m & ~fin], R["v"][m & ~fin], NT)[:H.NH]
        exp = np.bincount(R["a"][m & ~fin], R["v"][m & ~fin], NT)[:H.NH]
        alset = set(al.tolist())
        for L in S2.loans:
            if L[2] > 1e-9 and L[1] in alset and L[0] in alset:
                L[2] -= min(L[3], L[2])
            elif L[2] > 1e-9:
                L[2] = 0.0
        S2.loans = [L for L in S2.loans if L[2] > 1e-9] + out["newloans"]
        mm = np.isin(R["t"], [TI[t] for t in REV_T])
        S2.rev_prev = np.bincount(R["b"][mm], R["v"][mm], NT)[:H.NH]
        S2.inc_prev = inc
        S2.landlord = out["ll"]
        S2.alive_prev = al.copy()
        return S2, inc, exp

    def init_state(self):
        H = self.H
        S = State(H, self.L)
        al = np.array(sorted(H.g[h] for h in H.years[Y0]), np.int64)
        liv = self.liv[al]
        S.cash[al] = np.where(liv == 8, A["cash0"][8], np.where(np.isin(liv, list(SELL_GOOD) + list(PORT_M)), A["cash0"]["seller"], A["cash0"]["other"]))
        for k, v in A["treasury0"].items():
            S.inst[("官", k)] = v; self.I(("官", k))
        yr = Year(H, Y0)
        S0 = S.copy(); S0.cash[:] = 1e6
        self.boot = True                # 引导年：满额需求、不追加盈余消费（只用于定 AF40 工位数）
        o = self.step(yr, S0)
        self.boot = False
        R = o["rows"]
        mm = np.isin(R["t"], [TI[t] for t in REV_T if t not in PORT_FEE_T])
        S.rev_prev = np.bincount(R["b"][mm], R["v"][mm], max(o["NT"], H.NH + len(self.inst_keys) + 1))[:H.NH]
        S.inc_prev = np.full(H.NH, 99.0)
        return S


# ================================================================ 统计
def sector_stats(E, yr, R, NT, out):
    H = E.H; al = yr.alive; liv = E.liv
    def by(tn, side="b", mask_codes=None):
        m = R["t"] == TI[tn]
        x = np.bincount(R[side][m], R["v"][m], NT)[:H.NH]
        if mask_codes is not None:
            x = x * np.isin(liv, mask_codes)
        return float(x.sum())
    # 产值（毛） = 部门户全部营业收入；增加值 = 毛 − 外购投入（城外、船商、本城他部门原料）
    port_fees = sum(by(t) for t in PORT_FEE_T)
    tr_sales = by("买卖:港货", mask_codes=PORT_M) + by("原料(转口货)", mask_codes=PORT_M)
    tr_gross = port_fees + tr_sales
    tr_in = by("港货进价(付船商)", "a", PORT_M)
    cr_gross = by("买卖:手工", mask_codes=CRAFT) + by("出口:手工(船商付)", mask_codes=CRAFT)
    cr_in = by("原料(转口货)", "a", CRAFT) + by("进货/原料(付城外)", "a", CRAFT)
    ag_gross = by("买卖:菜蔬", mask_codes=AGRI) + by("买卖:鱼", mask_codes=AGRI) + by("出口:鱼(船商付)", mask_codes=AGRI)
    ag_in = by("进货/原料(付城外)", "a", AGRI)
    ext_rx = dict(转口=port_fees, 手工=by("出口:手工(船商付)", mask_codes=CRAFT), 农渔=by("出口:鱼(船商付)", mask_codes=AGRI))
    ext_px = dict(转口=tr_in, 手工=by("进货/原料(付城外)", "a", CRAFT), 农渔=ag_in)
    # 就业：部门户（自营 / 雇主） + 被部门雇主雇的雇工户
    wm = np.isin(R["t"], [TI["工钱"], TI["工钱:港口"]])
    wa, wb = R["a"][wm], R["b"][wm]
    nH = len(al)
    emp = {}
    for s, codes in SECTORS.items():
        own = int(np.isin(liv[al], codes).sum())
        hired = int(np.isin(liv[wa], codes).sum())
        emp[s] = dict(households=own, hired_workers=hired, total=own + hired, share_of_households=round((own + hired) / nH, 4))
    other_hired = int((~np.isin(liv[wa], sum(SECTORS.values(), ()))).sum())
    pw = int((R["t"] == TI["公役工钱"]).sum())
    workers = int(np.isin(liv[al], WORKERS).sum())
    unemployed = workers - int(len(np.unique(wb))) - pw
    gross = dict(转口=tr_gross, 手工=cr_gross, 农渔=ag_gross)
    va = dict(转口=tr_gross - tr_in, 手工=cr_gross - cr_in, 农渔=ag_gross - ag_in)
    r = lambda d: {k: round(v, 2) for k, v in d.items()}
    tva = sum(va.values())
    tt = lambda tn: float(R["v"][R["t"] == TI[tn]].sum())
    return dict(ships=round(out["ships"], 1), throughput=round(out["T"], 1), customs=round(tt("关税"), 2),
                customs_city=round(tt("关税分成(→城市长官)"), 2), customs_imperial=round(tt("关税上解(→皇库)"), 2), gross=r(gross), value_added=r(va),
                va_share={k: round(v / tva, 4) for k, v in va.items()},
                port_fees={t: round(by(t), 2) for t in PORT_FEE_T}, external_receipts=r(ext_rx), external_payments=r(ext_px),
                employment=emp, other_hired=other_hired, public_works=pw, workers=workers, unemployed_workers=unemployed,
                private_slot_coverage=round(int(wm.sum()) / max(workers, 1), 4),
                slots_offered=out["slots"], slots_per_worker=round((out["slots"]["port"] + out["slots"]["district"]) / max(workers, 1), 3), port_hired=int((R["t"] == TI["工钱:港口"]).sum()))


def ent_name(E, H, yr, e, gone_door):
    if e < H.NH or E.inst_keys[e - H.NH][0] != "官" or not E.inst_keys[e - H.NH][1].startswith("customs|"):
        return E14.ent_name(E, H, yr, e, gone_door)
    k = E.inst_keys[e - H.NH][1].split("|")[1]
    al = yr.alive
    d = np.hypot(*(H.xy[al] - H.st[k]["xy"]).T)
    g = int(al[np.lexsort((H.idnum[al], d))[0]])
    return f"官:关卡|{k}@近{H.door(H.hid[g], yr.Y)}"


def emit_year(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
    used = np.unique(np.concatenate([R["a"], R["b"], al]))
    remap = -np.ones(int(used.max()) + 1, np.int64); remap[used] = np.arange(len(used))
    names = [ent_name(E, H, yr, int(e), gone_door) for e in used]
    kind = ["户" if e < H.NH else E.inst_keys[e - H.NH][0] for e in used]
    q = np.round(R["v"] * 1000).astype(np.int64)
    o = np.lexsort((R["b"], R["a"], R["t"]))
    doc = dict(
        year=yr.Y, _doc="economy_v15 逐年流（列式）。q 为千分之一份；粮类型的份 = 一人一年口粮，其余为折粮的钱。sector: 转口/手工/农渔/其他。——Hark（刘线）",
        entities=names, entity_kind=kind, types=TYPES, rules=RULES,
        flows=dict(t=R["t"][o].tolist(), a=remap[R["a"][o]].tolist(), b=remap[R["b"][o]].tolist(), q=q[o].tolist(), r=R["r"][o].tolist()),
        households=dict(ent=remap[al].tolist(), house=[H.hid[g] for g in al], livelihood=E.liv[al].tolist(), livelihood_names=LIV,
                        sector=[next((s for s, c in SECTORS.items() if x in c), "其他") for x in E.liv[al]],
                        lh_src=E.L["src"][al].tolist(), lh_src_names=E14.FN_SRC,
                        income_m=np.round(income * 1000).astype(int).tolist(), expense_m=np.round(expense * 1000).astype(int).tolist(),
                        cash_m=np.round(cash * 1000).astype(int).tolist(), networth_m=np.round(nw * 1000).astype(int).tolist(),
                        houses_owned=owned.astype(int).tolist(), debt_m=np.round(pay[al] * 1000).astype(int).tolist(),
                        landlord=[int(remap[x]) if x >= 0 else -1 for x in out["ll"][al]],
                        market=[out["dv"]["mk"][i] for i in out["dv"]["node"]],
                        home_port=[E.W.harbors[i] for i in out["dv"]["home_port"]],
                        walk_port=np.round(np.min(out["dv"]["walk"][:, :len(E.W.harbors)], 1), 1).tolist(),
                        dist_market=np.round(out["dv"]["dist_market"], 1).tolist(), dist_grain=np.round(out["dv"]["dist_grain"], 1).tolist()))
    with gzip.open(os.path.join(HERE, f"flows_AF{yr.Y}.json.gz"), "wt", compresslevel=9) as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


# ================================================================ 主流程
def simulate(ships_mult=1.0, write=True, H=None, W=None):
    t00 = time.time()
    H = H or HW()
    W = W or HW15(H)
    E = Econ(H, W, ships_mult)
    t_prep = time.time() - t00
    S = E.init_state()
    per, recon, timing, gone_door, ev_states = {}, [], [], {}, {}
    treas = {k: [] for k in ("eparch", "bishop_nicene", "bishop_arian")}
    sample_g, sample_txt = None, {}
    for Y in range(Y0, Y1 + 1):
        t0 = time.perf_counter()
        yr = Year(H, Y)
        if Y + 0 == SHIP_EVENT_YEAR or Y in EVENT_YEARS:
            ev_states[Y] = S.copy()
        out = E.step(yr, S)
        t_step = time.perf_counter() - t0
        R = out["rows"]; NT = max(out["NT"], H.NH + len(E.inst_keys) + 1)
        M_before = float(S.cash.sum() + sum(S.inst[k] for k in E.inst_keys if k[0] != "外"))
        S2, inc, exp = E.advance(yr, S, out)
        M_after = float(S2.cash.sum() + sum(S2.inst[k] for k in E.inst_keys if k[0] != "外"))
        ext = [E.inst_ix[("外", e)] for e in EXT]
        money = ~np.isin(R["t"], GRAIN_T)
        ext_in = float(R["v"][money & np.isin(R["a"], ext)].sum())
        ext_out = float(R["v"][money & np.isin(R["b"], ext)].sum())
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
        al = yr.alive
        grain_hh = float(R["v"][R["t"] == TI["口粮配给"]].sum())
        house_tax = float(R["v"][R["t"] == TI["房税"]].sum())
        ledger_houses = int(((H.built <= Y) & (H.dest > Y)).sum())
        recon.append(dict(year=Y, ledger_houses=ledger_houses, model_households=len(al), houses_ok=ledger_houses == len(al),
                          food_cap=food_cap(Y), grain_to_households=round(grain_hh, 3), grain_ok=abs(grain_hh - food_cap(Y)) < 1e-6,
                          house_tax_model=round(house_tax, 3), house_tax_rule=round(P4["tau"] * ledger_houses, 3),
                          house_tax_ok=abs(house_tax - P4["tau"] * ledger_houses) < 1e-6,
                          money_stock=round(M_after, 3), dM=round(dM, 3), ext_in=round(ext_in, 3), ext_out=round(ext_out, 3),
                          bad_debt_with_departing=round(neg_gone, 3), conservation_err=abs(cons_err),
                          max_type_err=max(v["err"] for v in per_type.values()),
                          eparch=round(S2.inst[("官", "eparch")], 2), bishop_nicene=round(S2.inst[("官", "bishop_nicene")], 2),
                          bishop_arian=round(S2.inst[("官", "bishop_arian")], 2), households_cash=round(float(S2.cash.sum()), 2)))
        for k in treas:
            treas[k].append(round(S2.inst[("官", k)], 1))
        cash = S2.cash[al]
        owned = np.where(out["dv"]["owner"], 1, 0).astype(float)
        llc = np.bincount(np.clip(out["ll"][al], 0, None), weights=(out["ll"][al] >= 0).astype(float), minlength=H.NH)
        owned += llc[al]
        recv = np.zeros(H.NH); pay = np.zeros(H.NH)
        for L in S2.loans:
            recv[L[0]] += L[2]; pay[L[1]] += L[2]
        nw = cash + P4["V_h"] * owned + recv[al] - pay[al]
        income = inc[al]; expense = exp[al]
        bm = np.isin(R["t"], [TI[t] for t in BUSINESS_OUT])
        net_income = income - np.bincount(R["a"][bm], R["v"][bm], NT)[:H.NH][al]
        pl = A["poverty"]; med = float(np.median(income))
        sec = sector_stats(E, yr, R, NT, out)
        stats = dict(households=len(al), poor_share=round(float((income < pl).mean()), 4), poor=int((income < pl).sum()),
                     at_or_below_line_share=round(float((income <= pl + 1e-9).mean()), 4),
                     rel_poor_share=round(float((income < 0.6 * med).mean()), 4),
                     gini_income=round(gini(income), 4), gini_networth=round(gini(nw), 4),
                     gini_net_income=round(gini(np.maximum(net_income, 0.0)), 4), net_income_negative=int((net_income < -1e-9).sum()), poor_share_net=round(float((net_income < pl).mean()), 4),
                     median_net_income=round(float(np.median(net_income)), 3),
                     poor_by_livelihood={LIV[i]: int(((income < pl) & (E.liv[al] == i)).sum()) for i in range(len(LIV)) if ((income < pl) & (E.liv[al] == i)).any()},
                     median_income=round(med, 3), mean_income=round(float(income.mean()), 3),
                     unfunded_deficits=out["unfunded"], loans_active=len(S2.loans),
                     treasury=dict(eparch=round(S2.inst[("官", "eparch")], 2), bishop_nicene=round(S2.inst[("官", "bishop_nicene")], 2),
                                   bishop_arian=round(S2.inst[("官", "bishop_arian")], 2)),
                     spend=out["spend"], sector=sec, rows=int(len(R["t"])),
                     by_type_total={TYPES[t]: round(float(R["v"][R["t"] == t].sum()), 2) for t in range(len(TYPES)) if (R["t"] == t).any()})
        per[Y] = dict(stats=stats, per_type=per_type)
        timing.append(dict(year=Y, step_s=round(t_step, 3)))
        for g in out["gone"]:
            gone_door[g] = S.door_prev.get(g, H.hid[g])
        if write:
            if sample_g is None and Y == 41:
                cand = [g for g in out["new"] if E.liv[g] == 0 and H.dest[g] > 70]
                sample_g = int(sorted(cand, key=lambda g: H.idnum[g])[0]) if cand else int(al[0])
            if sample_g is not None and sample_g in set(al.tolist()) and Y in (41, 48, 60, 70):
                sample_txt[Y] = sample_year(E, H, yr, R, sample_g, gone_door, S, S2, inc, exp)
            if Y in SNAP:
                emit_year(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay)
        S2.door_prev = {g: H.door(H.hid[g], Y) for g in al} if write else {}
        S = S2
    return dict(E=E, H=H, W=W, per=per, recon=recon, timing=timing, treas=treas, ev_states=ev_states,
                sample=(sample_g, sample_txt), t_total=time.time() - t00, t_prep=t_prep)


def sample_year(E, H, yr, R, g, gone_door, S, S2, inc, exp):
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


def curve(xs):
    ys = list(range(Y0, Y1 + 1))
    d = np.diff(xs)
    peak = int(np.argmax(xs))
    return dict(AF40=xs[0], AF45=xs[5], AF50=xs[10], AF55=xs[15], AF60=xs[20], AF65=xs[25], AF70=xs[30],
                max=max(xs), max_year=ys[peak], min=min(xs), years_up=int((d > 0).sum()), years_down=int((d < 0).sum()),
                monotone_up=bool((d >= 0).all()), last10_slope_per_year=round(float(np.polyfit(range(10), xs[-10:], 1)[0]), 1))


def run():
    o = simulate(1.0, True)
    E, H, per, recon = o["E"], o["H"], o["per"], o["recon"]
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    L = E.L; reg = L["first"] >= 0
    liv14 = E14.livelihoods(H)["liv"]
    res = dict(
        _doc="economy_v15 结果（economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
        livelihood=dict(counts={LIV[i]: int(((L["liv"] == i) & reg).sum()) for i in range(len(LIV))},
                        changed_from_v14={f"{E14.LIV[a]}→{LIV[b]}": int(c) for (a, b), c in collections.Counter(zip(liv14[reg & (liv14 != L['liv'])].tolist(), L['liv'][reg & (liv14 != L['liv'])].tolist())).items()},
                        houses_ever=int(reg.sum())),
        hardware=dict(harbors=E.W.harbors, ports=E.W.ports, harbor_area={k: round(v, 1) for k, v in E.W.harbor_area.items()},
                      coast_edges=len(E.W.coast_edges), walk_tables=len(E.W._walk), walk_s=round(E.W.t_walk, 2)),
        years={str(Y): per[Y]["stats"] for Y in per},
        treasury_curves={k: dict(series=v, summary=curve(v)) for k, v in o["treas"].items()},
        conservation=dict(max_per_type_err=max(r["max_type_err"] for r in recon), max_money_err=max(r["conservation_err"] for r in recon),
                          grain_all_years_ok=all(r["grain_ok"] for r in recon), house_tax_all_years_ok=all(r["house_tax_ok"] for r in recon),
                          houses_all_years_ok=all(r["houses_ok"] for r in recon)),
        per_type_AF70=per[70]["per_type"],
        timing=dict(total_s=round(o["t_total"], 2), prep_s=round(o["t_prep"], 2),
                    step_median_s=float(np.median([t["step_s"] for t in o["timing"]])), step_max_s=max(t["step_s"] for t in o["timing"])),
        files={f"flows_AF{Y}.json.gz": os.path.getsize(os.path.join(HERE, f"flows_AF{Y}.json.gz")) for Y in SNAP},
        sample=dict(house=H.hid[o["sample"][0]], text=o["sample"][1]),
    )
    p = os.path.join(HERE, "results.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    for k in ("events", "sensitivity"):
        if k in old:
            res[k] = old[k]
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(HERE, "sample_household.txt"), "w") as f:
        f.write("\n\n".join(o["sample"][1][y] for y in sorted(o["sample"][1])))
    pickle.dump(dict(states=o["ev_states"], inst_keys=E.inst_keys), open(os.path.join(HERE, ".cache_states.pkl"), "wb"))
    s70 = per[70]["stats"]
    print(json.dumps(dict(total_s=round(o["t_total"], 1), cons=res["conservation"], liv=res["livelihood"]["counts"],
                          AF70={k: s70[k] for k in ("poor_share", "gini_income", "gini_networth", "treasury")}, sector=s70["sector"],
                          curves={k: v["summary"] for k, v in res["treasury_curves"].items()}), ensure_ascii=False, default=float))


def sens():
    H = HW(); W = HW15(H)
    out = {}
    for mlt in (0.5, 1.0, 1.5):
        o = simulate(mlt, False, H, W)
        s = o["per"][70]["stats"]
        out[f"x{mlt}"] = dict(ships_AF70=s["sector"]["ships"], poor_share_AF70=s["poor_share"], gini_income_AF70=s["gini_income"],
                              gini_networth_AF70=s["gini_networth"], coverage_AF70=s["sector"]["private_slot_coverage"],
                              unemployed_AF70=s["sector"]["unemployed_workers"], public_works_AF70=s["sector"]["public_works"],
                              va=s["sector"]["value_added"], va_share=s["sector"]["va_share"], gross=s["sector"]["gross"],
                              employment={k: v["share_of_households"] for k, v in s["sector"]["employment"].items()},
                              treasury_AF70=s["treasury"], poor_share_by_year={str(Y): o["per"][Y]["stats"]["poor_share"] for Y in SNAP},
                              max_money_err=max(r["conservation_err"] for r in o["recon"]),
                              checks_ok=all(r["grain_ok"] and r["house_tax_ok"] and r["houses_ok"] for r in o["recon"]))
        print(mlt, json.dumps(out[f"x{mlt}"], ensure_ascii=False)[:500])
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); res["sensitivity"] = out
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


# ================================================================ 事件
def dirty_sets15(E, yr_cf, yr_ev, o_cf, ll_ev):
    ma, dd, nch, ngone = E14.dirty_sets(E.H, yr_cf, yr_ev, o_cf, ll_ev)
    if yr_cf.mod.get("ships_mult", 1.0) != yr_ev.mod.get("ships_mult", 1.0):
        exp_ = np.isin(E.liv[yr_ev.alive], (3, 4, 16))       # 出口户的固定项随到港量变
        nch += int((exp_ & ~ma).sum()); ma = ma | exp_
    return ma, dd, nch, ngone


def events():
    t00 = time.time()
    H = HW(); W = HW15(H)
    E = Econ(H, W)
    C_ = pickle.load(open(os.path.join(HERE, ".cache_states.pkl"), "rb"))
    E.inst_keys = list(C_["inst_keys"]); E.inst_ix = {k: H.NH + i for i, k in enumerate(E.inst_keys)}
    out = {}
    evs = [("fire48", 48), ("granary55", 55), ("forum57", 57), ("street62", 62), ("ships_drop65", SHIP_EVENT_YEAR)]
    for name, Y in evs:
        S = C_["states"][Y]
        if name == "ships_drop65":
            mod_ev, mod_cf = dict(ships_mult=0.3), {}
            desc = f"合成事件 AF{Y}：到港商船骤降到 30%（一年，如海战/瘟疫/封港）；反事实 = 基准到港量"
            yr_ev = Year(H, Y, mod_ev); yr_cf = Year(H, Y, mod_cf)
        else:
            mod, desc = E14.event_mods(H, E, Y, name)
            yr_ev = Year(H, Y); yr_cf = Year(H, Y, mod)
        E.W.walk(yr_ev); E.W.walk(yr_cf)                    # 步行表预热（按街集缓存，不计入事件耗时）
        t0 = time.perf_counter(); o_cf = E.step(yr_cf, S); t_cf = time.perf_counter() - t0
        t0 = time.perf_counter(); o_ev = E.step(yr_ev, S); t_full = time.perf_counter() - t0
        t0 = time.perf_counter()
        dv = E.derive(yr_ev, S); ll = E.landlords(yr_ev, S, dv)
        ma, dd, nch, ngone = dirty_sets15(E, yr_cf, yr_ev, o_cf, ll)
        t_dirty = time.perf_counter() - t0
        t1 = time.perf_counter()
        o_inc = E.step(yr_ev, S, inc=dict(cache=o_cf, dirty_a=ma, dirty_d=dd, dv=dv, ll=ll))
        t_inc = time.perf_counter() - t1 + t_dirty
        h_full, h_inc = rows_hash(o_ev["rows"]), rows_hash(o_inc["rows"])
        NT = max(o_ev["NT"], H.NH + len(E.inst_keys) + 1)
        money = [TI[t] for t in TYPES if TI[t] not in GRAIN_T and TI[t] not in FIN_T]
        def per_house(o):
            R = o["rows"]; m = np.isin(R["t"], money)
            return np.bincount(R["b"][m], R["v"][m], NT)[:H.NH], np.bincount(R["a"][m], R["v"][m], NT)[:H.NH]
        inc_ev, exp_ev = per_house(o_ev); inc_cf, exp_cf = per_house(o_cf)
        both = np.intersect1d(yr_ev.alive, yr_cf.alive)
        d_inc = inc_ev[both] - inc_cf[both]
        def sig_rows(o):
            R = o["rows"]; m = ~np.isin(R["t"], GRAIN_T)
            d = collections.defaultdict(list)
            for t, a, b, v in zip(R["t"][m], R["a"][m], R["b"][m], np.round(R["v"][m], 9)):
                if a < H.NH: d[int(a)].append((int(t), int(b), -v))
                if b < H.NH: d[int(b)].append((int(t), int(a), v))
            return {k: sorted(v) for k, v in d.items()}
        s_ev, s_cf = sig_rows(o_ev), sig_rows(o_cf)
        changed = [g for g in both.tolist() if s_ev.get(g) != s_cf.get(g)]
        def emp_set(o):
            R = o["rows"]; return set(R["b"][np.isin(R["t"], [TI["工钱"], TI["工钱:港口"], TI["公役工钱"]])].tolist())
        lost_job = len(emp_set(o_cf) - emp_set(o_ev)); got_job = len(emp_set(o_ev) - emp_set(o_cf))
        pl = A["poverty"]
        poor_ev = int((inc_ev[yr_ev.alive] < pl).sum()); poor_cf = int((inc_cf[yr_cf.alive] < pl).sum())
        nz = np.abs(d_inc) > 1e-9
        R_ev, R_cf = o_ev["rows"], o_cf["rows"]
        out[name] = dict(
            year=Y, desc=desc,
            hardware=dict(households_ev=len(yr_ev.alive), households_cf=len(yr_cf.alive), changed_inputs=nch,
                          dirty_households_K1=int(ma.sum()), dirty_districts=sorted(dd), dirty_buyers_K3=o_inc["tim"]["dirty_buyers"]),
            affected_households_money=len(changed),
            income_change=dict(n=int(nz.sum()), total=round(float(d_inc.sum()), 2), down=int((d_inc < -1e-9).sum()), up=int((d_inc > 1e-9).sum()),
                               min=round(float(d_inc.min()), 3), max=round(float(d_inc.max()), 3)),
            jobs=dict(lost=lost_job, gained=got_job), poor_ev=poor_ev, poor_cf=poor_cf,
            totals_ev_minus_cf={t: round(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - R_cf["v"][R_cf["t"] == TI[t]].sum()), 2)
                                for t in TYPES if abs(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - R_cf["v"][R_cf["t"] == TI[t]].sum())) > 1e-6},
            incremental_equals_rebuild=h_full == h_inc, rows=int(len(R_ev["t"])), rows_hash=h_full[:16],
            timing_ms=dict(full_rebuild=round(t_full * 1000, 1), incremental=round(t_inc * 1000, 1), counterfactual=round(t_cf * 1000, 1),
                           dirty_detect=round(t_dirty * 1000, 1)))
        print(name, json.dumps({k: out[name][k] for k in ("affected_households_money", "incremental_equals_rebuild", "jobs", "poor_ev", "poor_cf", "timing_ms")}, ensure_ascii=False))
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); res["events"] = out; res["events_total_s"] = round(time.time() - t00, 1)
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    {"run": run, "sens": sens, "events": events}[sys.argv[1]]()
