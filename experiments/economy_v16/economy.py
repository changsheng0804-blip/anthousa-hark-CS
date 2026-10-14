# -*- coding: utf-8 -*-
"""economy_v16：劳动市场（工位 = 实际劳动需求，工钱简单出清）、面包户再平衡、户层收支规则（盈余去向 + 亏空借贷顺序）。
地下数据管线，不做页面。——Hark（刘线）

按路径只读载入（不改）：
  ../economy_v15/economy.py（HW15、生计 v15、Rows、TYPES、出图/统计函数；经它再载入 v14、v13 缓存、v7 街网）
  ../social_v12/ties_AF70.json.gz（户-户关系里的「亲属:*」「婚姻:*」边，用作借贷/嫁资的亲属）
运行：python3 economy.py run       # 基准 AF40–70 + 输出（flows、ledger_reconcile.csv、results.json、sample_household.txt）
      python3 economy.py sens      # 到港量 ×0.5/×1/×1.5
      python3 economy.py events    # v15 的 5 个事件：增量 == 重建（需先 run）
"""
import os, sys, json, gzip, time, pickle, hashlib, importlib.util, collections, csv, heapq, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sys.path.insert(0, os.path.dirname(path))
    sp.loader.exec_module(m)
    return m


E15 = _load("economy_v15_for_v16", os.path.join(EXP, "economy_v15", "economy.py"))
E14 = E15.E14
HW, HW15, Year, State = E15.HW, E15.HW15, E15.Year, E15.State
food_cap, stable_u, gini, rows_hash = E15.food_cap, E15.stable_u, E15.gini, E15.rows_hash
P4, LL, DEBT = E15.P4, E15.LL, E15.DEBT
Y0, Y1, SNAP, EVENT_YEARS, SHIP_EVENT_YEAR = E15.Y0, E15.Y1, E15.SNAP, E15.EVENT_YEARS, E15.SHIP_EVENT_YEAR
Rows, catd, rule = E15.Rows, E15.catd, E15.rule
LIV, PORT_M, CRAFT, AGRI, WORKERS, SELL_GOOD, SECTORS, EXT = E15.LIV, E15.PORT_M, E15.CRAFT, E15.AGRI, E15.WORKERS, E15.SELL_GOOD, E15.SECTORS, E15.EXT
DIST_EMP = (2, 3, 4, 7)

# ------------------------------------------------------------------ 新流类型（追加到 v15 的类型表；运行时扩表，不改 v15 文件）
NEW_T = ["工钱:零工(码头)", "修房(付营造)", "嫁资", "存放教会", "施舍(亏空)"]
for t in NEW_T:
    if t not in E15.TI:
        E15.TI[t] = len(E15.TYPES); E15.TYPES.append(t)
TYPES, TI = E15.TYPES, E15.TI
GRAIN_T = E15.GRAIN_T
FIN_T = list(E15.FIN_T) + [TI["嫁资"], TI["存放教会"]]           # 转移 / 寄存：不计入收入与支出
REV_T = list(E15.REV_T) + ["修房(付营造)"]
BUSINESS_OUT = list(E15.BUSINESS_OUT) + ["工钱:零工(码头)"]
PORT_FEE_T = E15.PORT_FEE_T

# ------------------------------------------------------------------ 参数：v15 全部沿用，下列为本轮新增 / 改动（全部是假设，见 REPORT 三栏）
A = E15.A
A.update(
    # ---- 1 劳动市场
    w_min=3.0,          # 工钱下限 = 贫困线（基本篮子 1.8 + 租 1.0 + 人头税 0.2）：Allen 2007 价格敕令「刚够最低生存篮子」（bare-bones 福利比 1.16）
    w_max=4.5,          # 工钱上限 = 1.5 × 线：Morrisson–Cheynet 非熟练工 9–12 N/年 ≈ 2.4–3.2 个生存最低额（转引），家庭福利比 0.76–1（Milanovic 2006）
    labor_elast=0.5,    # 劳动需求对工钱弹性 η：D(w) = D(w_min) × (w / w_min)^(−η)
    own_labor=1.0,      # 雇主户自身劳力（户主自己干，抵 1 个工位）
    y_port=49.5,        # 每工年产出（份增加值 / 雇工·年）：港口行（当年港费营收）。初值 11/6/8/6 → 工钱顶在 4.5、失业 0；
    y_bread=27.0, y_craft=36.0, y_build=27.0,   # 面包、手工铺/作坊、营造（上年营收 × (1 − 外购成本率)）。标定 6 组取 ×4.5（见 REPORT §标定）
    cost_rate={2: 0.20, 3: 0.30, 4: 0.30, 7: 0.0},
    R_cross=120.0,      # 跨区找活：剩余工人取直线最近的剩余工位，上限 120（≈1.4 km）
    c_casual=0.10,      # 码头零工池 = 装卸行当年装卸费 10%，分给本港步行 ≤R_walk 的无工者
    casual_cap=0.5,     # 零工每人每年最多 0.5 × 工钱（约半年活）
    # ---- 2 面包户再平衡
    cap_bread=12.0,     # 每面包户年产能（份，含 1–2 个帮工）
    slack_bread=1.2,    # 面包产能富余 20%
    cap_craft=12.0, slack_craft=1.2,
    R_conv_harbor=60.0, # 多出的面包户离商港直线 ≤60 → 码头脚夫（转口搬运），否则手工缺口 → 手工铺，再否则 → 雇工
    # ---- 3 户层收支
    c_surplus=0.0,      # v15 的「盈余 30% 追加消费」规则停用，由下列规则替代
    months_buffer=6.0,  # 现钱超过 6 个月开支的部分算盈余
    s_spend=0.5,        # 盈余每年动用 50%
    mix_spend={"repair": 0.35, "goods": 0.35, "church": 0.15, "lend": 0.15},   # 修房（营造户）/ 添置（手工 .6 港货 .3 鱼 .1）/ 存放教会 / 留作放贷本钱
    goods_mix={"craft": 0.6, "harbor": 0.3, "fish": 0.1},
    p_marry=0.06,       # 每户每年嫁女概率（确定性散列；≈ 户均 15–20 年一次）
    dowry_frac=0.3,     # 嫁资 = 当年盈余 × 30%，付给亲属（v12 婚姻/亲属边）户，否则同街户
    lend_reserve=2.0,   # 放贷后自留至少 2.0（v2）
    alms_def_cap=3.0,   # 亏空施舍：每户最多 3.0
    alms_def_share=0.5, # 主教库年末余额最多拿 50% 做亏空施舍
)
for k in ("w_min", "w_max"):
    pass
A["wage"] = A["w_min"]   # v14/v15 规则里用到的「工钱」默认值（引导年）；实际每年由出清定

KIN_SRC_PREFIX = ("亲属", "婚姻")


# ================================================================ 生计 v16 = v15 + 面包户再平衡
def livelihoods16(H, W):
    L = E15.livelihoods15(H, W)
    liv = L["liv"].copy()
    first = L["first"]
    reg = first >= 0
    mk = H.standing(Y1, ("market", "forum", "harbor", "warehouse"))
    MX = np.array([H.st[k]["xy"] for k in mk])
    D = np.hypot(H.xy[:, None, 0] - MX[None, :, 0], H.xy[:, None, 1] - MX[None, :, 1])
    node = np.argmin(D, 1); dnode = D[np.arange(H.NH), node]
    nm = len(mk)
    pop = np.zeros(nm); bmax = np.zeros(nm); cmax = np.zeros(nm)
    for Y in range(Y0, Y1 + 1):
        gs = np.array([H.g[h] for h in H.years[Y]], np.int64)
        pop = np.maximum(pop, np.bincount(node[gs], minlength=nm))
        bmax = np.maximum(bmax, np.bincount(node[gs], weights=(liv[gs] == 2).astype(float), minlength=nm))
        cmax = np.maximum(cmax, np.bincount(node[gs], weights=np.isin(liv[gs], CRAFT).astype(float), minlength=nm))
    need_b = np.ceil(pop * A["q_bread"] * A["slack_bread"] / A["cap_bread"])
    r_keep = np.where(bmax > 0, np.minimum(1.0, need_b / np.maximum(bmax, 1)), 1.0)
    need_c = np.ceil(pop * A["q_craft"] * A["slack_craft"] / A["cap_craft"])
    gap_c = np.maximum(0.0, need_c - cmax)
    u = stable_u(H.idnum, 161)
    conv = reg & (liv == 2) & (u >= r_keep[node])
    # 转去哪：手工缺口（按节点，概率 = 缺口 / 该节点多出的面包户峰值数）→ 手工铺；否则离商港 ≤R → 码头脚夫；否则雇工
    conv_max = np.zeros(nm)
    for Y in range(Y0, Y1 + 1):
        gs = np.array([H.g[h] for h in H.years[Y]], np.int64)
        conv_max = np.maximum(conv_max, np.bincount(node[gs], weights=conv[gs].astype(float), minlength=nm))
    p_c = np.where(conv_max > 0, np.minimum(1.0, gap_c / np.maximum(conv_max, 1)), 0.0)
    u2 = stable_u(H.idnum, 162)
    HX = np.array([H.st[k]["xy"] for k in W.harbors])
    dh = np.min(np.hypot(H.xy[:, None, 0] - HX[None, :, 0], H.xy[:, None, 1] - HX[None, :, 1]), 1)
    to_c = conv & (u2 < p_c[node])
    to_p = conv & ~to_c & (dh <= A["R_conv_harbor"])
    to_w = conv & ~to_c & ~to_p
    liv[to_c] = 3; liv[to_p] = 1; liv[to_w] = 0
    L = dict(L); L["liv"] = liv; L["liv15"] = L.get("liv15", None)
    L["rebalance"] = dict(markets=mk, need_bread_by_node={mk[i]: int(need_b[i]) for i in range(nm)},
                          bread_peak_by_node={mk[i]: int(bmax[i]) for i in range(nm)}, pop_peak_by_node={mk[i]: int(pop[i]) for i in range(nm)},
                          craft_gap_by_node={mk[i]: int(gap_c[i]) for i in range(nm) if gap_c[i] > 0},
                          converted=int(conv.sum()), to_craft=int(to_c.sum()), to_porter=int(to_p.sum()), to_labourer=int(to_w.sum()))
    return L


def load_kin(H):
    """v12 AF70 户-户关系中的亲属 / 婚姻边 → g → [亲属 g]（按边强度降序、门号升序）。AF70 前离城的户没有亲属记录（v12 只出 AF70）。"""
    p = os.path.join(EXP, "social_v12", "ties_AF70.json.gz")
    d = json.load(gzip.open(p, "rt"))
    S = d["sources"]; hh = d["households"]; E = d["edges"]
    kin_ix = {i for i, s in enumerate(S) if s.startswith(KIN_SRC_PREFIX)}
    adj = collections.defaultdict(list)
    n = 0
    for a, b, w, s in zip(E["a"], E["b"], E["w"], E["src"]):
        ss = s if isinstance(s, list) else [s]
        if not any(i in kin_ix for i in ss):
            continue
        ga, gb = H.g.get(hh[a]), H.g.get(hh[b])
        if ga is None or gb is None:
            continue
        adj[ga].append((-w, H.idnum[gb], gb)); adj[gb].append((-w, H.idnum[ga], ga)); n += 1
    return {g: [x[2] for x in sorted(v)] for g, v in adj.items()}, n


# ================================================================ 经济
class Econ16(E15.Econ):
    def __init__(self, H, W, ships_mult=1.0, kin=None):
        super().__init__(H, W, ships_mult)
        self.L15 = self.L
        self.L = livelihoods16(H, W)
        self.liv = self.L["liv"]
        self.kin, self.n_kin_edges = kin if kin is not None else load_kin(H)

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
        pos_of = np.full(H.NH, -1, np.int64); pos_of[al] = np.arange(n)
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
        # ------------------- K1 每户固定项（按户可增量；v15 原样）
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
        # ------------------- 还款、俸给、兵饷、补偿、账本工程（全量；v15 原样）
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
        # ------------------- KP 港口费用（v15 原样），港口劳动需求 = 当年港费 ÷ 每工产出 − 户主自身
        t0 = time.perf_counter()
        hb = self.W.harbors; nh = len(hb)
        aw = np.array([self.W.harbor_area[k] for k in hb]); sh = aw / aw.sum()
        S_h = ships * sh; T_h = S_h * A["cargo"]
        port_rev = collections.defaultdict(float)
        handle_by_port = np.zeros(nh); handlers_by_port = collections.defaultdict(list)
        for j, k in enumerate(hb):
            cu = I(("官", "customs|" + k))
            kt = A["kommerkion"] * T_h[j]
            R.add("关税", X["船商"], cu, kt, "kommerkion 10% 货值（8 世纪后制度，4–5 世纪对应 octava 12.5%；存疑）", -1, 8)
            R.add("关税分成(→城市长官)", cu, EP, A["customs_city_share"] * kt, "关税 1/3 留城（仿 CTh 4.13.7 城市得本地 vectigal 三分之一；存疑）", -1, 8)
            R.add("关税上解(→皇库)", cu, X["皇库"], (1 - A["customs_city_share"]) * kt, "关税其余上解皇库（sacrae largitiones；假设）", -1, 8)
        pools = []
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
                if tn == "港费:装卸":
                    handlers_by_port[int(dv["home_port"][i])].append((int(i), amt / len(m)))
        emp_p = np.array(sorted(port_rev, key=lambda i: (dv["home_port"][i], dv["door_rank"][i])), np.int64)
        D_p = np.maximum(0.0, np.array([port_rev[int(i)] for i in emp_p]) / A["y_port"] - A["own_labor"]) if len(emp_p) else np.zeros(0)
        # 区内雇主劳动需求 = 上年营收 × (1 − 外购成本率) ÷ 每工产出 − 户主自身
        rev = S.rev_prev
        emp_d = np.nonzero(np.isin(liv, DIST_EMP))[0]
        emp_d = emp_d[np.argsort(dv["door_rank"][emp_d], kind="stable")]
        yv = np.array([{2: A["y_bread"], 3: A["y_craft"], 4: A["y_craft"], 7: A["y_build"]}[c] for c in liv[emp_d]]) if len(emp_d) else np.zeros(0)
        cr_ = np.array([A["cost_rate"][c] for c in liv[emp_d]]) if len(emp_d) else np.zeros(0)
        D_d = np.maximum(0.0, rev[al[emp_d]] * (1 - cr_) / yv - A["own_labor"]) if len(emp_d) else np.zeros(0)
        # ------------------- 出清：全城一个工钱
        wk_all = np.nonzero(np.isin(liv, WORKERS))[0]
        N_w = len(wk_all)
        D0 = float(D_p.sum() + D_d.sum())
        if D0 <= N_w or D0 <= 0:
            wage = A["w_min"]
        else:
            wage = min(A["w_max"], A["w_min"] * (D0 / N_w) ** (1.0 / A["labor_elast"]))
        sc = (wage / A["w_min"]) ** (-A["labor_elast"])
        fr_all = np.concatenate([D_p, D_d]) * sc
        sl_all = np.floor(fr_all + 1e-9).astype(np.int64)
        extra_ = int(np.floor(fr_all.sum() + 1e-9)) - int(sl_all.sum())
        if extra_ > 0:
            sl_all[np.argsort(-(fr_all - sl_all), kind="stable")[:extra_]] += 1
        slots_p, slots_d = sl_all[:len(D_p)], sl_all[len(D_p):]
        lab = dict(wage=round(wage, 4), demand_at_floor=round(D0, 1), demand_port_at_floor=round(float(D_p.sum()), 1), workers=N_w,
                   demand_scale=round(sc, 4), slots_port=int(slots_p.sum()), slots_district=int(slots_d.sum()))
        # 港口雇工：步行 ≤R_walk，码头脚夫优先，再按步行距离、港口、门牌序（v15 规则）
        q_by_port = collections.defaultdict(collections.deque)
        for i, s_ in zip(emp_p, slots_p):
            for _ in range(int(s_)):
                q_by_port[int(dv["home_port"][i])].append(int(i))
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
        port_left = [(j, e) for j in sorted(q_by_port) for e in q_by_port[j]]
        if pa_:
            R.add("工钱:港口", np.array(pa_), np.array(pb_), wage, "劳动市场：港口工位=当年港费÷每工产出−户主；工钱全城出清；步行 ≤R_walk，码头脚夫优先", np.array(pb_), 8)
        tim["port"] = time.perf_counter() - t0
        # ------------------- K2 区内工钱（同街→同区，v14 四阶段）+ 跨区（剩余工人取最近剩余工位）。工钱全城出清，故 K2 全量。
        t0 = time.perf_counter()
        dnames = sorted(set(dv["d"]))
        left_s, left_w = [], []
        rule_d = "劳动市场：区内工位=上年营收×(1−成本率)÷每工产出−户主；同街优先再同区（v14）；工钱全城出清"
        for dname in dnames:
            ii = np.nonzero(dv["d"] == dname)[0]
            md = dv["d"][emp_d] == dname
            sl = np.repeat(emp_d[md], slots_d[md])
            wk_ = ii[np.isin(liv[ii], WORKERS) & ~taken[ii]]
            wk_ = wk_[np.argsort(dv["door_rank"][wk_], kind="stable")]
            free_s = np.ones(len(sl), bool); free_w = np.ones(len(wk_), bool)
            st_w = dv["street"][wk_]; st_s = dv["street"][sl]
            for phase in range(4):
                if not free_s.any() or not free_w.any():
                    break
                kw = [(st_w[i] if phase < 2 else "") for i in range(len(wk_))]
                ks = [(st_s[i] if phase < 2 else "") for i in range(len(sl))]
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
                    R.add("工钱", np.array(a2), np.array(b2), wage, rule_d, np.array(b2), 2)
                    taken[pos_of[np.array(b2)]] = True
            left_s.extend(sl[free_s].tolist()); left_w.extend(wk_[free_w].tolist())
        # 跨区：港口剩余工位（步行外）不参与；区内剩余工位 × 剩余工人，按门牌序，直线最近，≤R_cross
        n_cross = 0
        if left_s and left_w:
            ls = np.array(left_s, np.int64); lw = np.array(left_w, np.int64)
            lw = lw[np.argsort(dv["door_rank"][lw], kind="stable")]
            SX = H.xy[al[ls]]; free = np.ones(len(ls), bool)
            a2, b2 = [], []
            for i in lw:
                if not free.any():
                    break
                d2 = np.hypot(*(SX - H.xy[al[i]]).T); d2[~free] = np.inf
                j = int(np.argmin(d2))
                if d2[j] <= A["R_cross"]:
                    free[j] = False; a2.append(al[ls[j]]); b2.append(al[i])
            if a2:
                R.add("工钱", np.array(a2), np.array(b2), wage, "劳动市场：跨区找活，剩余工人（门牌序）取直线最近剩余工位 ≤R_cross（假设）", np.array(b2), 2)
                taken[pos_of[np.array(b2)]] = True
                n_cross = len(a2)
            lab["slots_unfilled_district"] = int(free.sum())
        else:
            lab["slots_unfilled_district"] = len(left_s)
        lab["slots_unfilled_port"] = len(port_left)
        lab["cross_district_hires"] = n_cross
        tim["wages"] = time.perf_counter() - t0
        # ------------------- 合并增量缓存（K1 干净行沿用；K2 全量）
        t0 = time.perf_counter()
        Rnew = R.cat()
        if inc is not None:
            C = inc["cache"]["rows"]
            pos = np.searchsorted(al, np.clip(C["o"], 0, None)); okp = (C["o"] >= 0) & (pos < n)
            hit = np.zeros(len(C["t"]), bool); hit[okp] = al[np.clip(pos[okp], 0, n - 1)] == C["o"][okp]
            ia = np.where(hit, np.clip(pos, 0, n - 1), 0)
            keep1 = (C["k"] == 1) & hit & ~ma[ia]
            Rpre = {x: np.concatenate([C[x][keep1], Rnew[x]]) for x in Rnew}
        else:
            Rpre = Rnew
        tim["merge"] = time.perf_counter() - t0
        # ------------------- K3 买卖（按买方签名可增量；v15 原样，盈余追加消费停用）
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
            amt[gd] = scale * q[gd] * price[gd]
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
                R.add(tname, al[b_], sel[gd][b_], amt[gd][b_], "户需求表×市场价（v14/v15）", al[b_], 3)
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
        # ------------------- K3b 户层盈余去向（全量）：现钱超过 N 个月开支的部分 × 动用率 → 修房 / 添置 / 存放教会 / 放贷本钱；嫁资
        t0 = time.perf_counter()
        cash_b = self._net_house(Rn, al, S)
        basic = need + np.where(dv["owner"], 0.0, P4["rho"]) + A["head_tax"]         # 年基本开支（篮子 + 租 + 人头税）
        surplus = np.maximum(0.0, cash_b - A["months_buffer"] / 12.0 * basic)
        spend = A["s_spend"] * surplus
        Rs = Rows()
        sp_i = np.nonzero(spend > 1e-9)[0]
        rl_s = f"户盈余：现钱超过 {A['months_buffer']:.0f} 个月基本开支的部分 × {A['s_spend']:.0%} 动用（新假设）"
        # 修房 → 本区最近 5 户营造户之一（散列）
        rep = A["mix_spend"]["repair"] * spend
        bld_by_d = collections.defaultdict(list)
        for i in bl:
            bld_by_d[dv["d"][i]].append(int(i))
        tgt = np.full(n, -1, np.int64)
        for i in sp_i:
            c = bld_by_d.get(dv["d"][i]) or bl.tolist()
            if not c:
                continue
            c = np.array(c)
            dd = np.hypot(*(H.xy[al[c]] - H.xy[al[i]]).T)
            k5 = c[np.lexsort((H.idnum[al[c]], dd))[:5]]
            tgt[i] = al[k5[hs[i] % len(k5)]]
        m_ = sp_i[tgt[sp_i] >= 0]
        Rs.add("修房(付营造)", al[m_], tgt[m_], rep[m_], rl_s + "；35% 修房，付本区最近 5 户营造户之一", al[m_], 7)
        # 添置 → 手工 / 港货 / 鱼 卖方（与日常买卖同一卖家）
        gds = A["mix_spend"]["goods"] * spend
        for gd, tn in (("craft", "买卖:手工"), ("harbor", "买卖:港货"), ("fish", "买卖:鱼")):
            m_ = sp_i[sel[gd][sp_i] >= 0]
            Rs.add(tn, al[m_], sel[gd][m_], A["goods_mix"][gd] * gds[m_], rl_s + "；35% 添置（手工 .6 港货 .3 鱼 .1）", al[m_], 7)
        # 存放教会 → 本派主教库
        chv = A["mix_spend"]["church"] * spend
        arm = dv["arian"][sp_i] != ""
        Rs.add("存放教会", al[sp_i], np.where(arm, BA, BN), chv[sp_i], rl_s + "；15% 存放本派主教库（视作寄存/奉献，不计返还，假设）", al[sp_i], 7)
        lend_cap = np.zeros(H.NH); lend_cap[al] = A["mix_spend"]["lend"] * spend      # 留作放贷本钱（不动用就仍是现钱）
        # 嫁资：p_marry 散列选中的盈余户，付当年盈余 × 30% 给亲属户（v12 亲属/婚姻边），无亲属在城则同街户
        um = stable_u(H.idnum[al], 1000 + Y)
        mar = np.nonzero((um < A["p_marry"]) & (surplus > 1e-9))[0]
        st_members = collections.defaultdict(list)
        for i in range(n):
            st_members[dv["street"][i]].append(int(al[i]))
        da, db, dvv = [], [], []
        n_dowry_kin = 0
        for i in mar:
            g = int(al[i])
            ks = [k for k in self.kin.get(g, ()) if k in alset]
            if ks:
                r_ = ks[hs[i] % len(ks)]; n_dowry_kin += 1
            else:
                c = [x for x in st_members[dv["street"][i]] if x != g]
                if not c:
                    continue
                r_ = c[hs[i] % len(c)]
            da.append(g); db.append(r_); dvv.append(A["dowry_frac"] * surplus[i])
        if da:
            Rs.add("嫁资", np.array(da), np.array(db), np.array(dvv), f"嫁资：每户每年 {A['p_marry']:.0%} 散列嫁女，付当年盈余 30% 给亲属户（v12 亲属/婚姻边），无则同街户（假设）", -1, 7)
        Rsc = Rs.cat()
        Rn = catd(Rn, Rsc)
        hh = dict(surplus_households=int((surplus > 1e-9).sum()), surplus_total=round(float(surplus.sum()), 2), spend_total=round(float(spend.sum()), 2),
                  repair=round(float(rep.sum()), 2), goods=round(float(gds.sum()), 2), church=round(float(chv.sum()), 2),
                  dowries=len(da), dowry_to_kin=n_dowry_kin, dowry_total=round(float(sum(dvv)), 2))
        tim["surplus"] = time.perf_counter() - t0
        # ------------------- K4 聚合（全量；v15 原样）
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
        merch = np.nonzero(liv == 5)[0]
        cr = np.nonzero(np.isin(liv, CRAFT))[0]
        raw = A["craft_cost"] * s_craft[al[cr]]
        R2.add("进货/原料(付城外)", al[cr], X["城外贸易"], (1 - A["craft_local_raw"]) * raw, "手工原料 30%×60% 付城外（假设）", -1, 4)
        if len(merch):
            mb = collections.defaultdict(list)
            for i in merch[np.argsort(dv["door_rank"][merch], kind="stable")]:
                mb[int(dv["home_port"][i])].append(int(al[i]))
            allm = al[merch[np.argsort(dv["door_rank"][merch], kind="stable")]]
            tgt2 = np.array([(lambda t_: t_[hs[i] % len(t_)])(mb.get(int(dv["home_port"][i])) or list(allm)) for i in cr], np.int64)
            R2.add("原料(转口货)", al[cr], tgt2, A["craft_local_raw"] * raw, "手工原料 30%×40% 买本港港货商（转口货，假设）", -1, 4)
        else:
            R2.add("进货/原料(付城外)", al[cr], X["城外贸易"], A["craft_local_raw"] * raw, "手工原料（无港货商）付城外", -1, 4)
        R2c0 = R2.cat()
        s_h = tot(["买卖:港货"]) + tot(["原料(转口货)"], R2c0)
        g5 = al[liv == 5]
        R2.add("港货进价(付船商)", g5, X["船商"], A["harbor_cost"] * s_h[g5], "港货商留城货进价 = 售价 50%（付船商，假设）", -1, 4)
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
        # ------------------- K5 库银支出规则（v15 原样；公役工钱用出清工钱）+ 码头零工
        t0 = time.perf_counter()
        R2c = R2.cat()
        Rk = catd(Rn, R2c)
        cnow = self._cash_after(Rk, S, NT)
        R5 = Rows()
        bld = bl
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
        av = cnow[EP]
        sp = (1 - A["retain_eparch"]) * max(0.0, av - A["eparch_floor"])
        offs = [(g, A["stip_fang"] if off == "fang_head" else A["stip_district"]) for (off, jur), g in sorted(hold.items())
                if off in ("fang_head", "district_head") and g >= 0 and g in alset]
        need_st = sum(v for _, v in offs)
        scs = min(1.0, sp / need_st) if need_st > 0 else 0.0
        if offs and scs > 0:
            R5.add("官俸(坊长/区长)", EP, np.array([g for g, _ in offs]), np.array([v for _, v in offs]) * scs, "城市长官库：坊长 1.0、区长 3.0（新规则）", -1, 5)
        rest = sp - need_st * scs
        pw_budget = A["pw_share"] * rest
        un = np.nonzero(np.isin(liv, WORKERS) & ~taken)[0]
        un_before_pw = len(un)
        jobs = int(pw_budget // wage)
        n_pw = 0
        pw_set = np.zeros(n, bool)
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
            n_pw = len(pick); pw_set[pick] = True
            R5.add("公役工钱", EP, al[pick], wage, "城市长官库：40% 雇无工者（按区无工人数分额、区内门牌序；工钱 = 当年出清工钱）", -1, 5)
        maint = rest - n_pw * wage
        ms = [k for k in H.standing(Y, ("wall", "road", "cistern", "aqueduct", "aqueduct_bridge", "gate"), yr.drop)]
        for k in ms:
            pay_builders(EP, H.st[k]["xy"], A["builders_per_struct"], maint / len(ms), "城防街渠维护", "城市长官库：其余 → 城墙/街/水池/水渠/城门 均分，离设施形心最近 20 户营造户（新规则）")
        spend_log["eparch"] = dict(available=round(av, 2), spend=round(sp, 2), officials=round(need_st * scs, 2), public_works=round(n_pw * wage, 2), maintenance=round(maint, 2), unemployed_before=un_before_pw)
        # 码头零工：各港装卸行拿当年装卸费 c_casual 雇本港步行 ≤R_walk 的无工者，每人 ≤ casual_cap × 工钱
        un2 = un[~pw_set[un]]
        n_casual = 0; casual_paid = 0.0
        for j in range(nh):
            hl = handlers_by_port.get(j, [])
            if not hl:
                continue
            pool = A["c_casual"] * sum(v for _, v in hl)
            cw = un2[(dv["home_port"][un2] == j) & (dv["walk"][un2, j] <= A["R_walk"])]
            if not len(cw) or pool <= 0:
                continue
            cw = cw[np.argsort(dv["door_rank"][cw], kind="stable")]
            each = min(A["casual_cap"] * wage, pool / len(cw))
            tot_ = each * len(cw)
            hv = np.array([v for _, v in hl]); hi = np.array([i for i, _ in hl], np.int64)
            for a_, share in zip(hi, hv / hv.sum()):
                R5.add("工钱:零工(码头)", al[a_], al[cw], each * share, "码头零工：本港装卸行拿装卸费 10% 按装卸费比例付本港步行 ≤R_walk 的无工者，每人 ≤0.5×工钱（假设）", -1, 5)
            n_casual += len(cw); casual_paid += tot_
        lab.update(unemployed_before_pw=un_before_pw, public_works=n_pw, casual=n_casual, casual_paid=round(casual_paid, 2),
                   no_work=un_before_pw - n_pw - n_casual)
        tim["treasury"] = time.perf_counter() - t0
        # ------------------- 年末：迁出、亏空借贷（亲属 → 同行会 → 坊长 → v2 放债人 → 盈余放贷人）→ 亏空施舍
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
        surp_by_d = {x: (lambda Ld: Ld[np.argsort(H.idnum[Ld], kind="stable")])(al[(lend_cap[al] > 1e-9) & (dv["d"] == x)]) for x in sorted(set(dv["d"]))}
        guild_members = collections.defaultdict(list)
        for i in np.nonzero(dv["guild"] != "")[0]:
            guild_members[(dv["d"][i], dv["guild"][i])].append(int(al[i]))
        bor = np.nonzero(cash[al] < -1e-9)[0]
        bor = bor[np.argsort(H.idnum[al[bor]], kind="stable")]
        lc = cash.copy(); newloans = []
        src_rows = collections.defaultdict(lambda: ([], [], []))
        n_src = collections.Counter()
        unfunded_g = []
        def can(o, g, amt_, surplus_only=False):
            if o == g or o < 0 or o not in alset or act[o] >= DEBT["cap"]:
                return False
            if lc[o] < amt_ + A["lend_reserve"]:
                return False
            return (not surplus_only) or lend_cap[o] >= amt_ - 1e-9
        for i in bor:
            g = int(al[i]); amt_ = -lc[g]
            o = -1; src_ = None
            for k in self.kin.get(g, ()):
                if can(k, g, amt_):
                    o, src_ = k, "亲属"; break
            if o < 0 and dv["guild"][i] != "":
                c = [x for x in guild_members[(dv["d"][i], dv["guild"][i])] if can(x, g, amt_)]
                if c:
                    c = np.array(c); dd = np.hypot(*(H.xy[c] - H.xy[g]).T); o, src_ = int(c[np.lexsort((H.idnum[c], dd))[0]]), "同行会"
            if o < 0:
                fh_ = hold.get(("fang_head", dv["fang"][i]), -1)
                if can(fh_, g, amt_):
                    o, src_ = fh_, "坊长"
            if o < 0:
                for pool_, nm_, so in ((lenders_by_d.get(dv["d"][i]), "v2放债人", False), (surp_by_d.get(dv["d"][i]), "盈余放贷人", True)):
                    if pool_ is None or not len(pool_):
                        continue
                    ok = np.array([can(int(x), g, amt_, so) for x in pool_])
                    if ok.any():
                        c = pool_[ok]; dd = np.hypot(*(H.xy[c] - H.xy[g]).T)
                        o, src_ = int(c[np.lexsort((H.idnum[c], dd))[0]]), nm_
                        break
            if o < 0:
                unfunded_g.append(g); continue
            ra, rb, rv = src_rows[src_]
            ra.append(o); rb.append(g); rv.append(amt_)
            lc[o] -= amt_; lc[g] += amt_; act[o] += 1
            if src_ == "盈余放贷人":
                lend_cap[o] -= amt_
            n_src[src_] += 1
            newloans.append([o, g, amt_, amt_ / DEBT["years"], Y])
        rl_src = {"亲属": "亏空借贷①亲属（v12 亲属/婚姻边，强度序）", "同行会": "亏空借贷②同区同行会户（v8 行会，最近）",
                  "坊长": "亏空借贷③本坊坊长（v8/v13 任职户）", "v2放债人": "亏空借贷④v2 债：同区有房面包师/体面户（cap4，4 年，无息）",
                  "盈余放贷人": "亏空借贷⑤同区盈余户（本年盈余 15% 作放贷本钱，新规则）"}
        for s_, (ra, rb, rv) in src_rows.items():
            R3.add("借贷", np.array(ra), np.array(rb), np.array(rv), rl_src[s_] + "；均 cap4、4 年、无息、放后自留 ≥2", -1, 6)
        # 亏空施舍：本派主教库年末余额 × 50% 为限，每户 ≤3.0，补无人借的亏空
        n_alms_def = 0; alms_def_tot = 0.0; still = 0
        if unfunded_g:
            ug = np.array(unfunded_g, np.int64)
            fa = dv["arian"][pos_of[ug]] != ""
            for bishop, msk in ((BN, ~fa), (BA, fa)):
                gg = ug[msk]
                if not len(gg):
                    continue
                need_ = np.minimum(-lc[gg], A["alms_def_cap"])
                bud = max(0.0, A["alms_def_share"] * lc[bishop])
                f_ = min(1.0, bud / need_.sum()) if need_.sum() > 0 else 0.0
                if f_ > 0:
                    R3.add("施舍(亏空)", bishop, gg, need_ * f_, "亏空施舍：借不到的亏空户，由本派主教库年末余额 50% 为限补，每户 ≤3.0（新规则）", -1, 6)
                    lc[gg] += need_ * f_; lc[bishop] -= float((need_ * f_).sum())
                    n_alms_def += int((need_ * f_ > 1e-9).sum()); alms_def_tot += float((need_ * f_).sum())
            still = int((lc[ug] < -1e-6).sum())
        Rall = catd(Rall, R3.cat())
        credit = dict(borrowers=len(bor), funded_by_source=dict(n_src), unfunded_no_lender=len(unfunded_g),
                      alms_deficit_households=n_alms_def, alms_deficit_total=round(alms_def_tot, 2), still_negative_after_alms=still)
        tim["close"] = time.perf_counter() - t0
        return dict(rows=Rall, sig_g=sig_g, dsig={}, dv=dv, ll=ll, newloans=newloans, unfunded=len(unfunded_g), gone=gone, new=new,
                    tim=tim, NT=NT, ships=ships, T=float(Ttot), spend=spend_log, n_pw=n_pw, taken=int(taken.sum()),
                    slots=dict(port=int(slots_p.sum()), district=int(slots_d.sum())), labor=lab, hh=hh, credit=credit, wage=wage)

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
        S0.rev_prev = np.zeros(H.NH)
        self.boot = True
        o = self.step(yr, S0)
        self.boot = False
        R = o["rows"]
        mm = np.isin(R["t"], [TI[t] for t in REV_T if t not in PORT_FEE_T])
        # 引导年 S0 现钱无限，盈余规则会放大营收，所以只取日常买卖、出口、原料、营造等（不含修房 / 添置的 k=7 行）
        mm &= R["k"] != 7
        S.rev_prev = np.bincount(R["b"][mm], R["v"][mm], max(o["NT"], H.NH + len(self.inst_keys) + 1))[:H.NH]
        S.inc_prev = np.full(H.NH, 99.0)
        return S


# ================================================================ 统计
def sector_stats16(E, yr, R, NT, out):
    s = E15.sector_stats(E, yr, R, NT, out)
    H = E.H; al = yr.alive; liv = E.liv
    lab = dict(out["labor"])
    N = lab["workers"]
    lab["rate_no_regular_job"] = round(lab["unemployed_before_pw"] / max(N, 1), 4)
    lab["rate_unemployed_or_casual"] = round((lab["casual"] + lab["no_work"]) / max(N, 1), 4)
    lab["rate_no_work"] = round(lab["no_work"] / max(N, 1), 4)
    lab["rate_casual"] = round(lab["casual"] / max(N, 1), 4)
    lab["filled_slots"] = int(np.isin(R["t"], [TI["工钱"], TI["工钱:港口"]]).sum())
    s["labor"] = lab
    s["unemployed_workers"] = lab["no_work"] + lab["casual"]
    return s


def emit_year16(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
    used = np.unique(np.concatenate([R["a"], R["b"], al]))
    remap = -np.ones(int(used.max()) + 1, np.int64); remap[used] = np.arange(len(used))
    names = [E15.ent_name(E, H, yr, int(e), gone_door) for e in used]
    kind = ["户" if e < H.NH else E.inst_keys[e - H.NH][0] for e in used]
    q = np.round(R["v"] * 1000).astype(np.int64)
    o = np.lexsort((R["b"], R["a"], R["t"]))
    wm = np.isin(R["t"], [TI["工钱"], TI["工钱:港口"]]); pwm = R["t"] == TI["公役工钱"]; cm = R["t"] == TI["工钱:零工(码头)"]
    emp = set(R["b"][wm].tolist()); pws = set(R["b"][pwm].tolist()); cas = set(R["b"][cm].tolist())
    st = [("雇工" if g in emp else "公役" if g in pws else "零工" if g in cas else "无工") if E.liv[g] in WORKERS else "" for g in al]
    doc = dict(
        year=yr.Y, _doc="economy_v16 逐年流（列式）。q 为千分之一份；粮类型的份 = 一人一年口粮，其余为折粮的钱。sector: 转口/手工/农渔/其他；work: 工人户的就业状态（雇工/公役/零工/无工）；wage_m = 当年出清工钱×1000。——Hark（刘线）",
        wage_m=int(round(out["wage"] * 1000)),
        entities=names, entity_kind=kind, types=TYPES, rules=E15.RULES,
        flows=dict(t=R["t"][o].tolist(), a=remap[R["a"][o]].tolist(), b=remap[R["b"][o]].tolist(), q=q[o].tolist(), r=R["r"][o].tolist()),
        households=dict(ent=remap[al].tolist(), house=[H.hid[g] for g in al], livelihood=E.liv[al].tolist(), livelihood_names=LIV,
                        sector=[next((s for s, c in SECTORS.items() if x in c), "其他") for x in E.liv[al]], work=st,
                        lh_src=E.L["src"][al].tolist(), lh_src_names=E14.FN_SRC,
                        income_m=np.round(income * 1000).astype(int).tolist(), expense_m=np.round(expense * 1000).astype(int).tolist(),
                        cash_m=np.round(cash * 1000).astype(int).tolist(), networth_m=np.round(nw * 1000).astype(int).tolist(),
                        houses_owned=owned.astype(int).tolist(), debt_m=np.round(pay[al] * 1000).astype(int).tolist(),
                        landlord=[int(remap[x]) if x >= 0 else -1 for x in out["ll"][al]],
                        market=[out["dv"]["mk"][i] for i in out["dv"]["node"]],
                        home_port=[E.W.harbors[i] for i in out["dv"]["home_port"]],
                        walk_port=np.round(np.min(out["dv"]["walk"][:, :len(E.W.harbors)], 1), 1).tolist()))
    with gzip.open(os.path.join(HERE, f"flows_AF{yr.Y}.json.gz"), "wt", compresslevel=9) as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def cash_dist(c):
    c = np.asarray(c, float)
    s = np.sort(c)
    top = s[-max(1, len(s) // 100):].sum() / max(s[s > 0].sum(), 1e-9)
    return dict(p10=round(float(np.percentile(c, 10)), 2), p50=round(float(np.percentile(c, 50)), 2), p90=round(float(np.percentile(c, 90)), 2),
                p99=round(float(np.percentile(c, 99)), 2), max=round(float(c.max()), 2), mean=round(float(c.mean()), 2),
                top1_share=round(float(top), 4), negative=int((c < -1e-6).sum()), total=round(float(c.sum()), 1))


# ================================================================ 主流程
def simulate(ships_mult=1.0, write=True, H=None, W=None, kin=None):
    t00 = time.time()
    H = H or HW()
    W = W or HW15(H)
    E = Econ16(H, W, ships_mult, kin)
    t_prep = time.time() - t00
    S = E.init_state()
    per, recon, timing, gone_door, ev_states = {}, [], [], {}, {}
    treas = {k: [] for k in ("eparch", "bishop_nicene", "bishop_arian")}
    cash_hist = {}
    sample_g, sample_txt = None, {}
    for Y in range(Y0, Y1 + 1):
        t0 = time.perf_counter()
        yr = Year(H, Y)
        if Y == SHIP_EVENT_YEAR or Y in EVENT_YEARS:
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
                          bishop_arian=round(S2.inst[("官", "bishop_arian")], 2), households_cash=round(float(S2.cash.sum()), 2),
                          wage=round(out["wage"], 4)))
        for k in treas:
            treas[k].append(round(S2.inst[("官", k)], 1))
        cash = S2.cash[al]
        cash_hist[Y] = (al.copy(), cash.copy())
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
        sec = sector_stats16(E, yr, R, NT, out)
        stats = dict(households=len(al), poor_share=round(float((income < pl).mean()), 4), poor=int((income < pl).sum()),
                     at_or_below_line_share=round(float((income <= pl + 1e-9).mean()), 4),
                     rel_poor_share=round(float((income < 0.6 * med).mean()), 4),
                     gini_income=round(gini(income), 4), gini_networth=round(gini(nw), 4),
                     gini_net_income=round(gini(np.maximum(net_income, 0.0)), 4), net_income_negative=int((net_income < -1e-9).sum()),
                     poor_share_net=round(float((net_income < pl).mean()), 4), poor_net=int((net_income < pl).sum()),
                     median_net_income=round(float(np.median(net_income)), 3),
                     poor_by_livelihood={LIV[i]: int(((income < pl) & (E.liv[al] == i)).sum()) for i in range(len(LIV)) if ((income < pl) & (E.liv[al] == i)).any()},
                     poor_net_by_livelihood={LIV[i]: int(((net_income < pl) & (E.liv[al] == i)).sum()) for i in range(len(LIV)) if ((net_income < pl) & (E.liv[al] == i)).any()},
                     median_income=round(med, 3), mean_income=round(float(income.mean()), 3),
                     unfunded_deficits=out["unfunded"], credit=out["credit"], loans_active=len(S2.loans),
                     cash=cash_dist(cash), gini_cash=round(gini(np.maximum(cash, 0)), 4), household_rules=out["hh"],
                     livelihood_counts={LIV[i]: int((E.liv[al] == i).sum()) for i in range(len(LIV))},
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
                sample_txt[Y] = E15.sample_year(E, H, yr, R, sample_g, gone_door, S, S2, inc, exp)
            if Y in SNAP:
                emit_year16(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay)
        S2.door_prev = {g: H.door(H.hid[g], Y) for g in al} if write else {}
        S = S2
    # 户现钱持续积累检查：AF61–70 每年都增长的户、AF70 现钱 > 50 的户
    common = set(cash_hist[61][0].tolist())
    for Y in range(62, 71):
        common &= set(cash_hist[Y][0].tolist())
    common = np.array(sorted(common), np.int64)
    ser = np.zeros((10, len(common)))
    for k_, Y in enumerate(range(61, 71)):
        pos = np.full(H.NH, -1, np.int64); pos[cash_hist[Y][0]] = np.arange(len(cash_hist[Y][0]))
        ser[k_] = cash_hist[Y][1][pos[common]]
    mono = int((np.diff(ser, axis=0) > 1e-6).all(0).sum()) if len(common) else 0
    accum = dict(households_alive_61_70=len(common), cash_rising_every_year_61_70=mono,
                 mean_cash_slope_last10=round(float(np.mean(np.polyfit(range(10), ser, 1)[0])) if len(common) else 0.0, 4),
                 p99_slope_last10=round(float(np.percentile(np.polyfit(range(10), ser, 1)[0], 99)) if len(common) else 0.0, 4))
    return dict(E=E, H=H, W=W, per=per, recon=recon, timing=timing, treas=treas, ev_states=ev_states, accum=accum,
                sample=(sample_g, sample_txt), t_total=time.time() - t00, t_prep=t_prep)


def v15_ref():
    p = os.path.join(EXP, "economy_v15", "results.json")
    r = json.load(open(p))
    s = r["years"]["70"]
    return dict(poor_share=s["poor_share"], poor_share_net=s.get("poor_share_net"), gini_income=s["gini_income"], gini_net_income=s.get("gini_net_income"),
                gini_networth=s["gini_networth"], unfunded=s["unfunded_deficits"], va=s["sector"]["value_added"], va_share=s["sector"]["va_share"],
                employment={k: v["share_of_households"] for k, v in s["sector"]["employment"].items()}, unemployed=s["sector"]["unemployed_workers"],
                workers=s["sector"]["workers"], slots_per_worker=s["sector"]["slots_per_worker"], livelihood=r["livelihood"]["counts"],
                ships_drop=r.get("events", {}).get("ships_drop65", {}).get("jobs"))


def run():
    o = simulate(1.0, True)
    E, H, per, recon = o["E"], o["H"], o["per"], o["recon"]
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    L = E.L; reg = L["first"] >= 0
    liv15 = E.L15["liv"]
    res = dict(
        _doc="economy_v16 结果（economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
        livelihood=dict(counts={LIV[i]: int(((L["liv"] == i) & reg).sum()) for i in range(len(LIV))},
                        counts_v15={LIV[i]: int(((liv15 == i) & reg).sum()) for i in range(len(LIV))},
                        changed_from_v15={f"{LIV[a]}→{LIV[b]}": int(c) for (a, b), c in collections.Counter(zip(liv15[reg & (liv15 != L['liv'])].tolist(), L['liv'][reg & (liv15 != L['liv'])].tolist())).items()},
                        rebalance=L["rebalance"], houses_ever=int(reg.sum())),
        kin=dict(edges=E.n_kin_edges, households_with_kin=len(E.kin)),
        years={str(Y): per[Y]["stats"] for Y in per},
        wage_series={str(Y): per[Y]["stats"]["sector"]["labor"]["wage"] for Y in per},
        unemployment_series={str(Y): per[Y]["stats"]["sector"]["labor"]["rate_unemployed_or_casual"] for Y in per},
        treasury_curves={k: dict(series=v, summary=E15.curve(v)) for k, v in o["treas"].items()},
        cash_accumulation=o["accum"],
        conservation=dict(max_per_type_err=max(r["max_type_err"] for r in recon), max_money_err=max(r["conservation_err"] for r in recon),
                          grain_all_years_ok=all(r["grain_ok"] for r in recon), house_tax_all_years_ok=all(r["house_tax_ok"] for r in recon),
                          houses_all_years_ok=all(r["houses_ok"] for r in recon)),
        per_type_AF70=per[70]["per_type"],
        timing=dict(total_s=round(o["t_total"], 2), prep_s=round(o["t_prep"], 2),
                    step_median_s=float(np.median([t["step_s"] for t in o["timing"]])), step_max_s=max(t["step_s"] for t in o["timing"])),
        files={f"flows_AF{Y}.json.gz": os.path.getsize(os.path.join(HERE, f"flows_AF{Y}.json.gz")) for Y in SNAP},
        sample=dict(house=H.hid[o["sample"][0]], text=o["sample"][1]),
        v15_AF70=v15_ref(),
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
    print(json.dumps(dict(total_s=round(o["t_total"], 1), cons=res["conservation"], liv=res["livelihood"]["changed_from_v15"],
                          AF70={k: s70[k] for k in ("poor_share", "poor_share_net", "gini_income", "gini_net_income", "gini_networth", "unfunded_deficits", "credit", "cash", "treasury")},
                          labor=s70["sector"]["labor"], va=s70["sector"]["va_share"], emp={k: v["share_of_households"] for k, v in s70["sector"]["employment"].items()},
                          wage=res["wage_series"], unemp=res["unemployment_series"], accum=o["accum"]), ensure_ascii=False, default=float))


def sens():
    H = HW(); W = HW15(H); kin = load_kin(H)
    out = {}
    for mlt in (0.5, 1.0, 1.5):
        o = simulate(mlt, False, H, W, kin)
        s = o["per"][70]["stats"]
        out[f"x{mlt}"] = dict(ships_AF70=s["sector"]["ships"], poor_share_AF70=s["poor_share"], poor_share_net_AF70=s["poor_share_net"],
                              gini_income_AF70=s["gini_income"], gini_net_income_AF70=s["gini_net_income"], gini_networth_AF70=s["gini_networth"],
                              labor_AF70=s["sector"]["labor"], va=s["sector"]["value_added"], va_share=s["sector"]["va_share"],
                              employment={k: v["share_of_households"] for k, v in s["sector"]["employment"].items()},
                              unfunded_AF70=s["unfunded_deficits"], treasury_AF70=s["treasury"],
                              max_money_err=max(r["conservation_err"] for r in o["recon"]),
                              checks_ok=all(r["grain_ok"] and r["house_tax_ok"] and r["houses_ok"] for r in o["recon"]))
        print(mlt, json.dumps(out[f"x{mlt}"], ensure_ascii=False)[:600])
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); res["sensitivity"] = out
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


def events():
    t00 = time.time()
    H = HW(); W = HW15(H)
    E = Econ16(H, W)
    C_ = pickle.load(open(os.path.join(HERE, ".cache_states.pkl"), "rb"))
    E.inst_keys = list(C_["inst_keys"]); E.inst_ix = {k: H.NH + i for i, k in enumerate(E.inst_keys)}
    out = {}
    evs = [("fire48", 48), ("granary55", 55), ("forum57", 57), ("street62", 62), ("ships_drop65", SHIP_EVENT_YEAR)]
    for name, Y in evs:
        S = C_["states"][Y]
        if name == "ships_drop65":
            mod_ev, mod_cf = dict(ships_mult=0.3), {}
            desc = f"合成事件 AF{Y}：到港商船骤降到 30%（一年）；反事实 = 基准到港量"
            yr_ev = Year(H, Y, mod_ev); yr_cf = Year(H, Y, mod_cf)
        else:
            mod, desc = E14.event_mods(H, E, Y, name)
            yr_ev = Year(H, Y); yr_cf = Year(H, Y, mod)
        E.W.walk(yr_ev); E.W.walk(yr_cf)
        t0 = time.perf_counter(); o_cf = E.step(yr_cf, S); t_cf = time.perf_counter() - t0
        t0 = time.perf_counter(); o_ev = E.step(yr_ev, S); t_full = time.perf_counter() - t0
        t0 = time.perf_counter()
        dv = E.derive(yr_ev, S); ll = E.landlords(yr_ev, S, dv)
        ma, dd, nch, ngone = E15.dirty_sets15(E, yr_cf, yr_ev, o_cf, ll)
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
        def emp_set(o, ts):
            R = o["rows"]; return set(R["b"][np.isin(R["t"], [TI[t] for t in ts])].tolist())
        reg = ["工钱", "工钱:港口"]
        lost_job = len(emp_set(o_cf, reg) - emp_set(o_ev, reg)); got_job = len(emp_set(o_ev, reg) - emp_set(o_cf, reg))
        pl = A["poverty"]
        poor_ev = int((inc_ev[yr_ev.alive] < pl).sum()); poor_cf = int((inc_cf[yr_cf.alive] < pl).sum())
        nz = np.abs(d_inc) > 1e-9
        R_ev, R_cf = o_ev["rows"], o_cf["rows"]
        le, lc_ = o_ev["labor"], o_cf["labor"]
        N = max(le["workers"], 1)
        labor = dict(ev=le, cf=lc_,
                     no_regular_job_rate=dict(ev=round(le["unemployed_before_pw"] / N, 4), cf=round(lc_["unemployed_before_pw"] / N, 4)),
                     unemployed_or_casual_rate=dict(ev=round((le["no_work"] + le["casual"]) / N, 4), cf=round((lc_["no_work"] + lc_["casual"]) / N, 4)),
                     no_work_rate=dict(ev=round(le["no_work"] / N, 4), cf=round(lc_["no_work"] / N, 4)))
        out[name] = dict(
            year=Y, desc=desc,
            hardware=dict(households_ev=len(yr_ev.alive), households_cf=len(yr_cf.alive), changed_inputs=nch,
                          dirty_households_K1=int(ma.sum()), dirty_districts=sorted(dd), dirty_buyers_K3=o_inc["tim"]["dirty_buyers"]),
            income_change=dict(n=int(nz.sum()), total=round(float(d_inc.sum()), 2), down=int((d_inc < -1e-9).sum()), up=int((d_inc > 1e-9).sum()),
                               min=round(float(d_inc.min()), 3), max=round(float(d_inc.max()), 3)),
            jobs=dict(lost_regular=lost_job, gained_regular=got_job), labor=labor, poor_ev=poor_ev, poor_cf=poor_cf,
            credit=dict(ev=o_ev["credit"], cf=o_cf["credit"]),
            totals_ev_minus_cf={t: round(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - R_cf["v"][R_cf["t"] == TI[t]].sum()), 2)
                                for t in TYPES if abs(float(R_ev["v"][R_ev["t"] == TI[t]].sum() - R_cf["v"][R_cf["t"] == TI[t]].sum())) > 1e-6},
            incremental_equals_rebuild=h_full == h_inc, rows=int(len(R_ev["t"])), rows_hash=h_full[:16],
            timing_ms=dict(full_rebuild=round(t_full * 1000, 1), incremental=round(t_inc * 1000, 1), counterfactual=round(t_cf * 1000, 1),
                           dirty_detect=round(t_dirty * 1000, 1)))
        print(name, json.dumps({k: out[name][k] for k in ("incremental_equals_rebuild", "jobs", "poor_ev", "poor_cf", "timing_ms")}, ensure_ascii=False),
              json.dumps(labor["unemployed_or_casual_rate"]), json.dumps(labor["no_regular_job_rate"]))
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); res["events"] = out; res["events_total_s"] = round(time.time() - t00, 1)
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    {"run": run, "sens": sens, "events": events}[sys.argv[1]]()
