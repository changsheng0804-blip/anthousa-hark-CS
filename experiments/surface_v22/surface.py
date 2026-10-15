# -*- coding: utf-8 -*-
"""surface_v22：经济层（economy_v21 逐户流）→ 城市表面层（街上看得见的东西）。——Hark（刘线）

只读：../economy_v21/flows_AF{40,50,60,70}.json.gz、results.json；骤降年读 .shock/flows_AF{64,65,66}.json.gz（shock_run.py 产出，不入库）；
按路径载入 ../economy_v21/economy.py 只为取账本世界（设施多边形、房屋账本坐标、上游→账本仿射），不改任何旧目录。
页面事实：docs/living/xerolophos/houses.json（页面房屋 id = 账本房屋 `h<id>`）、facts_upstream/addr.json（街名索引、门牌）、
experiments/yamen_v13/registry_AF*.json.gz（教区）。
输出：docs/living/xerolophos/surface_AF{40,50,60,65,70}.json（页面用字段）、本目录 results.json（分布、匹配率、骤降对照）。
运行：python3 shock_run.py（约 50 s，骤降路径）；python3 surface.py（约 15 s）。
"""
import os, sys, json, gzip, importlib.util, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
PAGE = os.path.join(ROOT, "docs", "living", "xerolophos")
E21 = os.path.join(EXP, "economy_v21")

POOR = 3.0          # economy_v21 A["poverty"]
V_H = 30.0          # P4["V_h"]
UPKEEP = 0.02 * V_H  # 维护需求 2%×V_h / 栋·年（v17 修房上限）
SHOP_LIV = ["面包", "手工铺", "港货商", "兑钱商", "牙人"]
FIRM_LIV = ["营造", "装卸行", "港仓", "船修", "运水人", "渔户", "菜农"]
CRAFT_LIV = ["手工铺", "作坊"]
SALES_T = ["买卖:面包", "买卖:水", "买卖:手工", "买卖:港货", "买卖:菜蔬", "买卖:鱼", "出口:手工(船商付)", "出口:鱼(船商付)", "买卖:手工(港口采购)"]
CRAFT_T = ["买卖:手工", "出口:手工(船商付)", "买卖:手工(港口采购)"]
BUSINESS_OUT = ["工钱", "工钱:港口", "进货/原料(付城外)", "港货进价(付船商)", "原料(转口货)", "税钱上缴(坊长→区长)", "税钱上缴(区长→城市长官)",
                "行会钱上缴(行会头→城市长官)", "工钱:零工(码头)", "超额利润税", "工钱:短工(转业)"]          # = economy_v18 BUSINESS_OUT
NOT_INC = ["口粮调拨", "口粮下仓", "口粮配给", "借贷", "还款", "迁入带钱", "迁出带钱", "嫁资", "存放教会", "取回寄存"]   # 粮与转移：不算收支要点
LOAN_KEYS = [("官贷", "坊长代发官贷"), ("亲属", "亲属"), ("v2 债", "放债人"), ("盈余", "同区盈余户"), ("行会", "同行会"), ("坊长", "坊长")]


def loan_src(rule_text):
    """flows.r = 本年文件 rules 的序号（各年序号不同，按文字认来源）。"""
    for k, v in LOAN_KEYS:
        if k in rule_text:
            return v
    return "别人"

MAINT = ["新修", "寻常", "失修", "破败"]
FACADE = ["住家", "开张的铺子", "作坊开工", "关门的铺面", "行号"]
LEVEL = ["冷清", "寻常", "热闹", "拥挤"]

# 页面「为什么看起来这样」模板：由数据字段填空（JS 只做替换），每条注明经济量
WHY = {
    "m0new": "房子建成不到 3 年（账本建成年 {built}），还是新墙新瓦。",
    "m0": "{owner}这年付营造户修房 {rep}，够上维护需求 {need}（2%×房值×{nh} 栋）。",
    "m1": "{owner}这年修房只花了 {rep}，不到维护需求 {need}，只补了漏处。",
    "m2": "{owner}这年没有余钱修房（现钱 {ocash}，不到 6 个月基本开支），净收入 {onet} 尚在贫困线 3.0 以上。",
    "m3": "{owner}这年净收入 {onet} 低于贫困线 3.0，一文没花在修房上。",
    "f1": "铺子开着：这年卖货进账 {sales}。",
    "f2": "作坊开工：这年手工品卖出 {craft}。",
    "f3c": "铺面关着：原是手工铺，营收连续两年低于 5.5 后关门转业，现做{liv}。",
    "f3": "铺面关着：v19 原定是手工铺，这年不在营，做{liv}。",
    "f3z": "铺面关着：{liv}这年没有卖出货。",
    "p_smoke": "灶冷：亏空借不到钱，靠主教库补 {dalms}。",
    "p_loan": "这年向{lsrc}借了 {loan}。",
    "p_alms": "这年领主教施舍 {alms}。",
}


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sys.path.insert(0, os.path.dirname(path))
    sp.loader.exec_module(m)
    return m


def ledger_world():
    """账本房屋坐标、设施多边形与上游→账本仿射（经 economy_v21 → yamen_v13 → city_system_v7 载入，只读）。"""
    M = _load("economy_v21_ro_surface", os.path.join(E21, "economy.py"))
    H = M.HW()
    return H


def fit_page_to_ledger(H, page_houses):
    """页面坐标 = 上游坐标（facts_upstream/SOURCE.md：id/位置同）。用逐栋 id 对齐做最小二乘仿射 页面→账本，并给反变换。"""
    idx = {int(h[1:]): i for i, h in enumerate(H.hid) if h.startswith("h")}
    src, dst = [], []
    for hid, (cx, cy) in page_houses.items():
        if hid in idx:
            src.append([cx, cy, 1.0]); dst.append(H.xy[idx[hid]])
    src = np.array(src); dst = np.array(dst)
    A, *_ = np.linalg.lstsq(src, dst, rcond=None)
    res = np.linalg.norm(src @ A - dst, axis=1)
    A3 = np.c_[A, [0, 0, 1]]
    inv = np.linalg.inv(A3)
    return A, inv, dict(matched=len(src), rms_ledger=float(np.sqrt((res ** 2).mean())), p95_ledger=float(np.percentile(res, 95)))


def to_page(inv, xy):
    v = np.c_[np.asarray(xy, float).reshape(-1, 2), np.ones(len(np.asarray(xy).reshape(-1, 2)))] @ inv
    return v[:, :2]


def load_flows(path):
    d = json.load(gzip.open(path, "rt"))
    T = d["types"]; TI = {t: i for i, t in enumerate(T)}
    F = {k: np.asarray(v) for k, v in d["flows"].items()}
    Hh = d["households"]
    N = len(Hh["ent"]); NT = len(d["entities"])
    ent = np.asarray(Hh["ent"])
    # 实体序号 → 户行：流里的 a/b 是实体序号；户行与实体序号一般相同，骤降年有缺号时按 ent 重排
    remap = np.full(NT + 1, N, np.int64); remap[ent] = np.arange(N)
    for k in ("a", "b"):
        F[k] = remap[np.clip(F[k], 0, NT)]
    return d, T, TI, F, Hh, N, N + 1


def remap_ll(Hh, ll):
    ent = np.asarray(Hh["ent"]); pos = {int(e): i for i, e in enumerate(ent)}
    return np.array([pos.get(int(x), -1) if x >= 0 else -1 for x in ll])


def compute_year(Y, path, page, world, regs, ships):
    d, T, TI, F, Hh, N, NT = load_flows(path)
    q = F["q"] / 1000.0

    def S(types, side, mask=None):
        m = np.isin(F["t"], [TI[t] for t in types if t in TI])
        if mask is not None:
            m &= mask
        return np.bincount(F[side][m], q[m], NT)[:N]

    LN = Hh["livelihood_names"]; LI = {n: i for i, n in enumerate(LN)}
    liv = np.asarray(Hh["livelihood"]); liv19 = np.asarray(Hh["liv_v19"]); conv = np.asarray(Hh["craft_conv"])
    work = np.asarray(Hh["work"]); own = np.asarray(Hh["houses_owned"]); ll = np.asarray(Hh["landlord"])
    ll = remap_ll(Hh, ll)        # 房东 = 实体序号（假设与流 a/b 同口径）→ 户行
    inc = np.asarray(Hh["income_m"]) / 1000; exp = np.asarray(Hh["expense_m"]) / 1000
    cash = np.asarray(Hh["cash_m"]) / 1000; debt = np.asarray(Hh["debt_m"]) / 1000
    house = [int(h[1:]) for h in Hh["house"]]
    hpos = {h: i for i, h in enumerate(house)}
    net = inc - S(BUSINESS_OUT, "a")
    rep = S(["修房(付营造)"], "a")
    sales = S(SALES_T, "b"); craft = S(CRAFT_T, "b")
    alms = S(["施舍"], "b"); dalms = S(["施舍(亏空)"], "b")
    rent_in = S(["租金"], "b")
    mloan = F["t"] == TI["借贷"]
    loan = np.bincount(F["b"][mloan], q[mloan], NT)[:N]
    lsrc = np.full(N, -1)
    for b_, r_ in zip(F["b"][mloan], F["r"][mloan]):
        if b_ < N and lsrc[b_] < 0:
            lsrc[b_] = r_
    # 收支要点：最大一项收入 / 支出（不计粮、借还、嫁资、寄存）
    keep = ~np.isin(F["t"], [TI[t] for t in NOT_INC if t in TI])
    topi = np.full(N, -1); topi_v = np.zeros(N); tope = np.full(N, -1); tope_v = np.zeros(N)
    for side, top, topv in (("b", topi, topi_v), ("a", tope, tope_v)):
        m = keep & (F[side] < N)
        key = F[side][m].astype(np.int64) * 128 + F["t"][m]
        u, inv_ = np.unique(key, return_inverse=True)
        s = np.bincount(inv_, q[m])
        hh_ = u // 128; tt = u % 128
        order = np.lexsort((-s, hh_))
        seen = set()
        for k in order:
            h = int(hh_[k])
            if h in seen:
                continue
            seen.add(h); top[h] = int(tt[k]); topv[h] = s[k]

    # ---------- 房屋：维护（房主 = 自己有房则自己，租住则房东）
    owner = np.where(ll >= 0, ll, np.arange(N))
    nh_o = np.maximum(own[owner], 1)
    need_o = UPKEEP * nh_o
    ratio = rep[owner] / need_o
    built = world["built"]
    newh = np.array([(Y - built.get(h, -999)) < 3 for h in house])
    maint = np.where(newh | (ratio >= 0.95), 0, np.where(ratio > 1e-9, 1, np.where(net[owner] < POOR, 3, 2)))
    # ---------- 门面
    is_shop = np.isin(liv, [LI[n] for n in SHOP_LIV]); is_ws = liv == LI["作坊"]; is_firm = np.isin(liv, [LI[n] for n in FIRM_LIV if n in LI])
    was_shop = (liv19 == LI["手工铺"]) & ~np.isin(liv, [LI[n] for n in SHOP_LIV + ["作坊"]])
    facade = np.zeros(N, int)
    facade[is_shop & (sales > 1e-9)] = 1
    facade[is_shop & (sales <= 1e-9)] = 3
    facade[is_ws] = np.where(craft[is_ws] > 1e-9, 2, 3)
    facade[is_firm] = 4
    facade[was_shop] = 3
    fcause = np.where(was_shop & (conv == 1), 1, np.where(was_shop, 2, np.where(facade == 3, 3, 0)))   # 1 低营收关门转业（craft_conv）2 原定铺、不在营 3 在册但零营收
    poor = net < POOR
    nosmoke = dalms > 1e-9
    flags = poor * 1 + nosmoke * 2 + (loan > 1e-9) * 4 + (alms > 1e-9) * 8

    # ---------- 页面房屋
    present = [h for h, v in page["houses"].items() if v["built"] <= Y < v["destroyed"]]
    matched = [h for h in present if h in hpos]
    rows = {}
    for h in matched:
        i = hpos[h]; o = owner[i]
        tenant_of = house[o] if ll[i] >= 0 else 0
        rows[str(h)] = [int(maint[i]), int(facade[i]), int(liv[i]), int(max(own[i] - 1, 0)), int(tenant_of), int(flags[i]), int(fcause[i]),
                        round(float(inc[i]), 1), round(float(net[i]), 1), round(float(exp[i]), 1), round(float(cash[i]), 1),
                        round(float(rep[o]), 2), round(float(need_o[i]), 1), round(float(cash[o]), 1), round(float(net[o]), 1),
                        round(float(sales[i]), 1), round(float(craft[i]), 1), round(float(alms[i]), 1), round(float(dalms[i]), 1),
                        round(float(loan[i]), 1), loan_src(d["rules"][int(lsrc[i])]) if lsrc[i] >= 0 else "", int(topi[i]), round(float(topi_v[i]), 1),
                        int(tope[i]), round(float(tope_v[i]), 1), int(built.get(h, -999))]
    # ---------- 街道（页面街名索引，门牌取 addr.json 当年）
    st = collections.defaultdict(lambda: dict(h=0, open=0, ws=0, closed=0, trade=0.0, craft=0.0, beg=0, dbeg=0, xs=0.0, ys=0.0, ids=[]))
    for h in matched:
        a = page["addr"].get(str(h))
        if not a:
            continue
        r = next((x for x in a[1] if x[2] <= Y < x[3]), None)
        if not r:
            continue
        i = hpos[h]; s = st[r[0]]
        s["h"] += 1; s["open"] += facade[i] == 1; s["ws"] += facade[i] == 2; s["closed"] += facade[i] == 3
        s["trade"] += sales[i]; s["craft"] += craft[i] if liv[i] in (LI["手工铺"], LI["作坊"]) else 0.0
        s["beg"] += alms[i] > 1e-9; s["dbeg"] += dalms[i] > 1e-9
        cx, cy = page["houses"][h]["c"]; s["xs"] += cx; s["ys"] += cy; s["ids"].append(h)
    churches = [c for c in world["nodes"] if c["kind"] == "church" and c["built"] <= Y and c.get("inpage")]
    streets = []
    for si, s in st.items():
        if s["h"] < 3:
            continue
        cx, cy = s["xs"] / s["h"], s["ys"] / s["h"]
        dch = min([min(np.hypot(page["houses"][h]["c"][0] - c["xy"][0], page["houses"][h]["c"][1] - c["xy"][1]) for h in s["ids"]) for c in churches] or [9e9])
        streets.append(dict(si=si, x=round(cx), y=round(cy), h=s["h"], open=int(s["open"]), ws=int(s["ws"]), closed=int(s["closed"]),
                            stall=round((s["open"] + s["ws"]) / s["h"], 3), trade=round(s["trade"], 1), trade_ph=round(s["trade"] / s["h"], 2),
                            craft=round(s["craft"], 1), beg=int(s["beg"] + s["dbeg"]), church_d=round(float(dch))))
    for s in streets:
        s["beg_spot"] = int(s["beg"] >= 2 and s["church_d"] <= 300)
    # ---------- 市场 / 码头 / 教堂（全城节点；页面内的会画出来）
    mk = np.asarray(Hh["market"]); hp = np.asarray(Hh["home_port"])
    nodes = []
    ships_tot = ships
    m_load = F["t"] == TI["港费:装卸"]; load_in = np.bincount(F["b"][m_load], q[m_load], NT)[:N]
    m_sto = F["t"] == TI["港费:仓储"]; sto_in = np.bincount(F["b"][m_sto], q[m_sto], NT)[:N]
    m_pw = F["t"] == TI["工钱:港口"]; port_wage_rcv = np.bincount(F["b"][m_pw], q[m_pw], NT)[:N] > 0
    m_cz = F["t"] == TI["工钱:零工(码头)"]; casual_rcv = np.bincount(F["b"][m_cz], q[m_cz], NT)[:N] > 0
    load_tot = load_in.sum() or 1.0
    reg = regs
    parish = {}
    for v in reg["rows"].values():
        if str(v[0]).startswith("h"):
            parish[int(v[0][1:])] = v[4]
    for nd in world["nodes"]:
        if nd["built"] > Y:
            continue
        o = dict(id=nd["id"], kind=nd["kind"], name=nd["name"], x=nd["xy"][0], y=nd["xy"][1], inpage=nd.get("inpage", False))
        if nd["kind"] in ("market", "forum", "warehouse", "harbor"):
            m = mk == nd["id"]
            sellers = m & (is_shop | is_ws | (liv == LI.get("菜农", -1)) | (liv == LI.get("渔户", -1)))
            o.update(sellers_open=int((sellers & (sales > 1e-9)).sum()), sellers_closed=int((m & (facade == 3)).sum()),
                     trade=round(float(sales[m].sum()), 1), buyers=int(m.sum()))
        if nd["kind"] == "harbor":
            m = hp == nd["id"]
            share = float(load_in[m].sum() / load_tot)
            o.update(ships=round(ships_tot * share), porters=int((m & (liv == LI["码头脚夫"])).sum() + (m & port_wage_rcv & (liv != LI["码头脚夫"])).sum()),
                     casual=int((m & casual_rcv).sum()), load_fee=round(float(load_in[m].sum()), 1), store_fee=round(float(sto_in[m].sum()), 1))
        if nd["kind"] == "church":
            ids = [house[i] for i in np.nonzero((alms > 1e-9) | (dalms > 1e-9))[0]]
            o.update(alms_queue=int(sum(1 for h in ids if parish.get(h) == nd["id"])))
        nodes.append(o)
    # 仓库满空：本港仓储费 ÷ 同港基准（到港 600 时 AF70 基线）
    # ---------- 城市级分布（全城户 + 页面）
    def dist(arr, names, mask=None):
        a = arr if mask is None else arr[mask]
        c = collections.Counter(a.tolist())
        return {names[k]: int(c.get(k, 0)) for k in range(len(names))}
    page_idx = np.array([hpos[h] for h in matched], int)
    summary = dict(
        year=Y, households=N, page_houses_present=len(present), page_matched=len(matched),
        match_rate=round(len(matched) / max(len(present), 1), 4),
        maint_city=dist(maint, MAINT), maint_page=dist(maint, MAINT, page_idx),
        facade_city=dist(facade, FACADE), facade_page=dist(facade, FACADE, page_idx),
        closed_shopfronts_city=int((facade == 3).sum()), closed_shopfronts_page=int((facade[page_idx] == 3).sum()),
        closed_low_revenue_city=int(((facade == 3) & (fcause == 1)).sum()),
        open_shops_city=int((facade == 1).sum()), workshops_city=int((facade == 2).sum()),
        poor_city=int(poor.sum()), poor_page=int(poor[page_idx].sum()), nosmoke_city=int(nosmoke.sum()), nosmoke_page=int(nosmoke[page_idx].sum()),
        loans_city=int((loan > 1e-9).sum()), lender_loans_city=int(sum(1 for x in lsrc if x >= 0 and loan_src(d["rules"][int(x)]) == "放债人")),
        loan_src_city=dict(collections.Counter(loan_src(d["rules"][int(x)]) for x in lsrc if x >= 0)),
        alms_city=int((alms > 1e-9).sum()), renting_out_city=int((own > 1).sum()), tenants_city=int((ll >= 0).sum()),
        ships=ships_tot,
    )
    return dict(rows=rows, streets=streets, nodes=nodes, summary=summary, unmatched=[h for h in present if h not in hpos],
                maint_arr=maint, facade_arr=facade, hpos=hpos, liv_names=LN, types=T)


def main():
    PH = json.load(open(os.path.join(PAGE, "houses.json")))
    addr = json.load(open(os.path.join(PAGE, "facts_upstream", "addr.json")))
    page_h = {}
    for hid, dist_, built, dest, p in PH["houses"]:
        n = len(p) // 2
        page_h[hid] = dict(built=built, destroyed=dest, c=(sum(p[0::2]) / n, sum(p[1::2]) / n))
    page = dict(houses=page_h, addr=addr["h"])
    H = ledger_world()
    A, inv, aff = fit_page_to_ledger(H, {h: v["c"] for h, v in page_h.items()})
    built = {int(h[1:]): int(b) for h, b in zip(H.hid, H.built) if h.startswith("h")}
    nodes = []
    NAME = {"harbor_prosphorion": "普洛斯佛里昂港", "harbor_julian": "尤利安港", "harbor_neorion": "涅奥里昂港", "harbor_theodosius": "狄奥多西港",
            "agora_tetrastoon": "四柱廊市集", "forum_founder": "建城者广场", "forum_theodosius": "狄奥多西广场", "market_embers": "余烬市集",
            "warehouse_horn": "金角货栈", "church_peace": "和平教堂", "church_apostles": "使徒教堂", "church_megale": "大教堂",
            "church_mocius": "莫基乌斯教堂", "church_anastasia": "阿纳斯塔西娅教堂", "arian_meeting": "阿里乌聚会所", "church_arian_brick": "阿里乌砖堂"}
    for s in H.world["structures"]:
        if s["type"] not in ("harbor", "forum", "market", "warehouse", "church"):
            continue
        co = np.array(s["geom"]["coords"], float).reshape(-1, 2)
        c = to_page(inv, co.mean(0, keepdims=True))[0]
        kind = "market" if s["type"] in ("forum", "market") else s["type"]
        nodes.append(dict(id=s["id"], kind=kind, name=NAME.get(s["id"], s.get("name", s["id"])), xy=[round(float(c[0])), round(float(c[1]))],
                          built=int(s.get("built") or -999), inpage=bool(-150 <= c[0] <= 1970 and -150 <= c[1] <= 2200)))
    dest = {int(h[1:]): int(x) for h, x in zip(H.hid, H.dest) if h.startswith("h")}
    world = dict(built=built, nodes=nodes, dest=dest)
    # 账本里落在页面范围内、页面 houses.json 没有的房（页面只到 AF60）
    pxy = to_page(inv, H.xy)
    extra = {}
    for Y in (60, 65, 70):
        extra[Y] = int(sum(1 for i, h in enumerate(H.hid) if h.startswith("h") and int(h[1:]) not in page_h and H.built[i] <= Y < H.dest[i]
                           and 0 <= pxy[i, 0] <= 1820 and 0 <= pxy[i, 1] <= 2048))
    regs = {Y: json.load(gzip.open(os.path.join(EXP, "yamen_v13", f"registry_AF{Y}.json.gz"), "rt")) for Y in (40, 50, 60, 70)}
    res21 = json.load(open(os.path.join(E21, "results.json")))
    shock = res21["shock_path"]["v21_shock"]
    runs = [(Y, os.path.join(E21, f"flows_AF{Y}.json.gz"), regs[Y], res21["years"][str(Y)]["sector"]["ships"], "基准") for Y in (40, 50, 60, 70)]
    for Y, rY in ((64, 60), (65, 60), (66, 70)):
        p = os.path.join(HERE, ".shock", f"flows_AF{Y}.json.gz")
        if os.path.exists(p):
            runs.append((Y, p, regs[rY], shock[str(Y)]["ships"], "骤降路径"))
    out = {}; summ = {}
    # 仓储基准：AF70 基线同港仓储费
    for Y, p, reg, ships, label in runs:
        r = compute_year(Y, p, page, world, reg, ships)
        r["summary"]["path"] = label
        out[Y] = r; summ[f"AF{Y}"] = r["summary"]
        print(Y, label, json.dumps({k: r["summary"][k] for k in ("match_rate", "maint_page", "facade_page", "closed_shopfronts_city", "poor_page", "ships")}, ensure_ascii=False))
    # 街道等级：门槛固定取 AF70 基准各街分位（40/75/92%），各年同一把尺，骤降年才看得出变化
    tq = np.percentile([s["trade_ph"] for s in out[70]["streets"]], [40, 75, 92])
    cq = np.percentile([s["craft"] for s in out[70]["streets"] if s["craft"] > 0], [40, 75, 92])
    for r in out.values():
        for s in r["streets"]:
            s["crowd"] = int(np.searchsorted(tq, s["trade_ph"], side="right"))
            s["smoke"] = 0 if s["craft"] <= 0 else int(np.searchsorted(cq, s["craft"], side="right"))
    thresholds = dict(trade_per_house=[round(float(x), 2) for x in tq], craft_per_street=[round(float(x), 1) for x in cq])
    base_store = {n["id"]: n.get("store_fee", 0) for n in out[70]["nodes"] if n["kind"] == "harbor"}
    for Y, r in out.items():
        for n in r["nodes"]:
            if n["kind"] == "harbor":
                b = base_store.get(n["id"]) or 0
                n["fill"] = round(n["store_fee"] / b, 2) if b else None
                n["store"] = "满" if (n["fill"] or 0) >= 0.85 else "半空" if (n["fill"] or 0) >= 0.45 else "空"
    # ---------- 写页面文件
    LN = out[70]["liv_names"]; T = out[70]["types"]
    files = {}
    for Y, r in out.items():
        if Y == 64 or Y == 66:
            continue
        doc = dict(
            _doc=f"surface_v22 · AF{Y}（{r['summary']['path']}）：经济层 economy_v21 → 表面层。房屋 rows[id] 字段见 fields；规则见 experiments/surface_v22/REPORT.md。——Hark（刘线）",
            year=Y, path=r["summary"]["path"],
            fields=["维护", "门面", "生计", "出租栋数", "租住房东房屋id", "标记(1贫困 2灶冷 4借债 8领施舍)", "关门原因(1低营收关门转业 2原定铺不在营 3零营收)",
                    "收入", "净收入", "支出", "现钱", "房主修房", "维护需求", "房主现钱", "房主净收入", "卖货", "手工品", "施舍", "亏空施舍",
                    "借入", "借自", "最大收入类", "最大收入额", "最大支出类", "最大支出额", "账本建成年"],
            maint=MAINT, facade=FACADE, level=LEVEL, street_thresholds=thresholds, liv=LN, types=T, why=WHY, poverty=POOR,
            summary={k: v for k, v in r["summary"].items()},
            houses=r["rows"],
            streets=[{k: s[k] for k in ("si", "x", "y", "h", "open", "ws", "closed", "stall", "trade", "crowd", "craft", "smoke", "beg", "beg_spot", "church_d")} for s in r["streets"]],
            nodes=r["nodes"],
            gone={str(h): world["dest"].get(h) for h in r["unmatched"]},
        )
        p = os.path.join(PAGE, f"surface_AF{Y}.json")
        with open(p, "w") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        files[os.path.basename(p)] = os.path.getsize(p)
    # ---------- 骤降对照（AF64→65→66，同一骤降路径；页面房屋 + 全城）
    shock_cmp = {}
    if 64 in out and 65 in out:
        a, b = out[64], out[65]
        common = [h for h in a["rows"] if h in b["rows"]]
        trans = collections.Counter((MAINT[a["rows"][h][0]], MAINT[b["rows"][h][0]]) for h in common if a["rows"][h][0] != b["rows"][h][0])
        ftrans = collections.Counter((FACADE[a["rows"][h][1]], FACADE[b["rows"][h][1]]) for h in common if a["rows"][h][1] != b["rows"][h][1])
        shock_cmp = dict(
            page_common=len(common),
            maint_transitions_page={f"{k[0]}→{k[1]}": v for k, v in trans.most_common()},
            facade_transitions_page={f"{k[0]}→{k[1]}": v for k, v in ftrans.most_common()},
            harbors={Y: [{k: n.get(k) for k in ("id", "ships", "porters", "casual", "fill", "store")} for n in out[Y]["nodes"] if n["kind"] == "harbor"] for Y in (64, 65, 66) if Y in out},
            churches={Y: {n["id"]: n["alms_queue"] for n in out[Y]["nodes"] if n["kind"] == "church"} for Y in (64, 65, 66) if Y in out},
            streets_crowd_page={Y: collections.Counter(s["crowd"] for s in out[Y]["streets"]) for Y in (64, 65, 66) if Y in out},
            streets_trade_page={Y: round(sum(s["trade"] for s in out[Y]["streets"]), 1) for Y in (64, 65, 66) if Y in out},
            streets_beg_page={Y: sum(s["beg"] for s in out[Y]["streets"]) for Y in (64, 65, 66) if Y in out},
        )
    unmatched = {f"AF{Y}": dict(n=len(r["unmatched"]), ledger_dest=dict(collections.Counter(world["dest"].get(h) for h in r["unmatched"])), ids=r["unmatched"]) for Y, r in out.items()}
    res = dict(_doc="surface_v22 结果——Hark（刘线）", affine_page_to_ledger=aff, street_thresholds=thresholds, ledger_only_in_page_bbox=extra, nodes=nodes, summary=summ, files=files, shock=shock_cmp, unmatched=unmatched,
               streets_dist={f"AF{Y}": dict(crowd=collections.Counter(s["crowd"] for s in r["streets"]), smoke=collections.Counter(s["smoke"] for s in r["streets"]),
                                             beg_spots=sum(s["beg_spot"] for s in r["streets"]), n=len(r["streets"])) for Y, r in out.items()},
               nodes_by_year={f"AF{Y}": r["nodes"] for Y, r in out.items()})
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else float(o))
    print(json.dumps(files), json.dumps(aff))


if __name__ == "__main__":
    main()
