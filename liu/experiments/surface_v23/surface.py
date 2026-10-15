# -*- coding: utf-8 -*-
"""surface_v23：在 surface_v22 的映射上补三件事。——Hark（刘线）

1 行当统一：每栋房每个年份的生计直接取经济层（economy_v21 骤降路径逐年流 AF40–70）→ docs/living/xerolophos/trades.json；
  页面行当一律读它（手工铺/作坊才用原散列行当做细分），冲突统计在 trades.py。
2 年份 61–70：账本里落在页面范围、页面 houses.json 没有的新建房，用账本多边形经 v22 同一仿射（页面→账本最小二乘，求逆）
  画成简单多边形 → houses.json 新键 "ledger_new"；页面房屋按账本拆毁年写回 houses.json 第 4 列（原 9999）。
3 房屋维护存量：每栋房一个房况存量 C（0–V_h），每年按房龄与上年房况折旧、房主修房支出按栋摊回，四档由存量定，
  替代 v22 只看当年流的判断；surface_AF{40..70}.json 每年一份。

只读：本目录 .path/flows_AF{40..70}.json.gz（path_run.py 产出，economy_v21 骤降路径 AF65 到港 ×0.3，AF40–64 与基准逐字节相同）、
economy_v21/results.json、yamen_v13/registry_AF*.json.gz；按路径载入 ../surface_v22/surface.py 复用 compute_year（不改 v22）。
运行：python3 path_run.py（约 145 s）→ python3 surface.py（约 60 s）→ python3 dump_fams.py → python3 trades.py。
"""
import os, sys, json, gzip, importlib.util, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
PAGE = os.path.join(ROOT, "docs", "living", "xerolophos")
PATH = os.path.join(HERE, ".path")

sp = importlib.util.spec_from_file_location("surface_v22_ro", os.path.join(EXP, "surface_v22", "surface.py"))
S22 = importlib.util.module_from_spec(sp); sp.loader.exec_module(S22)

YEARS = list(range(40, 71))
V_H = S22.V_H                     # 房值 30
NEED = S22.UPKEEP                 # 维护需求 0.6/栋·年（2%×V_h）
# ---------- 房况存量参数（假设，见 REPORT）
WEAR_BASE = 0.6                   # 中年（30 年）房、房况完好时的年折旧 = 维护需求：每年修满需求的房保持不变
def wear(age, c):
    a = np.clip(age, 0, 60) / 60.0
    return WEAR_BASE * (0.6 + 0.8 * a) * (1.0 + 0.5 * (1.0 - c / V_H))      # 新房 0.36、30 年 0.6、60 年 0.84；房况越差折旧越快（最多 ×1.5）
def c_init(age):                  # AF40 已在立的房（无 40 年前的流）：按房龄给初值，0.85–1.0×V_h（寻常线 0.75 之上留余量）
    return V_H * np.maximum(0.85, 1.0 - 0.003 * np.maximum(age, 0))
CUT = (0.90, 0.75, 0.55)          # C/V_h ≥0.90 新修（完好）· ≥0.75 寻常 · ≥0.55 失修 · 其余 破败
def state(c):
    r = c / V_H
    return np.where(r >= CUT[0], 0, np.where(r >= CUT[1], 1, np.where(r >= CUT[2], 2, 3)))

WHY_V23 = {
    "m0new": "房子建成不到 3 年（账本建成年 {built}），还是新墙新瓦。房况存量 {cond}%。",
    "m0": "房况存量 {cond}%（九成以上）：房龄 {age} 年，今年折旧 {wear}，{owner}修房摊到这栋 {rs}。{trend}",
    "m1": "房况存量 {cond}%（七成半到九成，寻常）：房龄 {age} 年，今年折旧 {wear}，{owner}修房摊到这栋 {rs}。{trend}",
    "m2": "房况存量 {cond}%（五成半到七成半，失修）：房龄 {age} 年，今年折旧 {wear}，{owner}修房摊到这栋 {rs}。{trend}",
    "m3": "房况存量 {cond}%（不到五成半，破败）：房龄 {age} 年，今年折旧 {wear}，{owner}修房摊到这栋 {rs}。{trend}",
}


def ships_for(res21, Y):
    sh = res21["shock_path"]["v21_shock"]
    return sh[str(Y)]["ships"] if str(Y) in sh else res21["years"][str(Y)]["sector"]["ships"]


def reg_year(Y):
    return 40 if Y < 45 else 50 if Y < 55 else 60 if Y < 66 else 70


def v22_maint(Y, d, F, TI, Hh, N, NT, built):
    """v22 原规则（只看当年流），用来在同一路径上对比跳变。"""
    q = F["q"] / 1000.0
    m = F["t"] == TI["修房(付营造)"]
    rep = np.bincount(F["a"][m], q[m], NT)[:N]
    inc = np.asarray(Hh["income_m"]) / 1000
    mb = np.isin(F["t"], [TI[t] for t in S22.BUSINESS_OUT if t in TI])
    net = inc - np.bincount(F["a"][mb], q[mb], NT)[:N]
    ll = S22.remap_ll(Hh, np.asarray(Hh["landlord"])); own = np.asarray(Hh["houses_owned"])
    owner = np.where(ll >= 0, ll, np.arange(N))
    ratio = rep[owner] / (NEED * np.maximum(own[owner], 1))
    house = [int(h[1:]) for h in Hh["house"]]
    newh = np.array([(Y - built.get(h, -999)) < 3 for h in house])
    mt = np.where(newh | (ratio >= 0.95), 0, np.where(ratio > 1e-9, 1, np.where(net[owner] < S22.POOR, 3, 2)))
    return dict(zip(house, mt.tolist()))


def main():
    PH = json.load(open(os.path.join(PAGE, "houses.json")))
    addr = json.load(open(os.path.join(PAGE, "facts_upstream", "addr.json")))
    city = json.load(open(os.path.join(PAGE, "city.json")))
    HB = city.get("harbor_box") or [-9999, -9999, -9990, -9990]
    H = S22.ledger_world()
    page_h = {}
    for hid, dist_, built, dest, p in PH["houses"]:
        n = len(p) // 2
        page_h[hid] = dict(built=built, destroyed=dest, c=(sum(p[0::2]) / n, sum(p[1::2]) / n))
    A, inv, aff = S22.fit_page_to_ledger(H, {h: v["c"] for h, v in page_h.items()})
    lb = {int(h[1:]): int(b) for h, b in zip(H.hid, H.built) if h.startswith("h")}
    ld = {int(h[1:]): int(x) for h, x in zip(H.hid, H.dest) if h.startswith("h")}
    # ---------- 2 页面房屋拆毁年 ← 账本；新建房多边形
    dest_fix = {}
    for row in PH["houses"]:
        hid = row[0]
        if ld.get(hid, 9999) <= 70 and (row[3] == 9999 or (row[3] == ld[hid] and row[3] > 60)):
            dest_fix[hid] = ld[hid]; row[3] = ld[hid]; page_h[hid]["destroyed"] = ld[hid]
    new = []
    for hv in H.world["houses"]:
        if not hv["id"].startswith("h"):
            continue
        hid = int(hv["id"][1:])
        if hid in page_h:
            continue
        b = hv["built"]; d = hv["destroyed"] if hv["destroyed"] is not None else 9999
        if b is None or b > 70 or d <= 60:
            continue
        pp = S22.to_page(inv, np.array(hv["p"], float))
        cx, cy = pp.mean(0)
        if not (0 <= cx <= 1820 and 0 <= cy <= 2048) or (HB[0] < cx < HB[2] and HB[1] < cy < HB[3]):
            continue
        new.append([hid, int(b), int(d) if d <= 70 else 9999, [round(float(v), 1) for v in pp.reshape(-1)]])
    new.sort()
    new_before61 = [x for x in new if x[1] <= 60]
    for hid, b, d, p in new:
        n = len(p) // 2
        page_h[hid] = dict(built=b, destroyed=d, c=(sum(p[0::2]) / n, sum(p[1::2]) / n), new=True)
    PH["ledger_new"] = new
    PH["_v23"] = "surface_v23：houses 第 4 列拆毁年按账本补（原 9999 的 %d 栋）；ledger_new = [账本房屋id, 建成年, 拆毁年, 页面多边形]，账本多边形经 surface_v22 仿射（页面→账本最小二乘求逆）画到页面，只画轮廓色块。——Hark（刘线）" % len(dest_fix)
    with open(os.path.join(PAGE, "houses.json"), "w") as f:
        json.dump(PH, f, ensure_ascii=False, separators=(",", ":"))
    page = dict(houses=page_h, addr=addr["h"])
    # ---------- 设施节点（同 v22）
    NAME = {"harbor_prosphorion": "普洛斯佛里昂港", "harbor_julian": "尤利安港", "harbor_neorion": "涅奥里昂港", "harbor_theodosius": "狄奥多西港",
            "agora_tetrastoon": "四柱廊市集", "forum_founder": "建城者广场", "forum_theodosius": "狄奥多西广场", "market_embers": "余烬市集",
            "warehouse_horn": "金角货栈", "church_peace": "和平教堂", "church_apostles": "使徒教堂", "church_megale": "大教堂",
            "church_mocius": "莫基乌斯教堂", "church_anastasia": "阿纳斯塔西娅教堂", "arian_meeting": "阿里乌聚会所", "church_arian_brick": "阿里乌砖堂"}
    nodes = []
    for s in H.world["structures"]:
        if s["type"] not in ("harbor", "forum", "market", "warehouse", "church"):
            continue
        co = np.array(s["geom"]["coords"], float).reshape(-1, 2)
        c = S22.to_page(inv, co.mean(0, keepdims=True))[0]
        kind = "market" if s["type"] in ("forum", "market") else s["type"]
        nodes.append(dict(id=s["id"], kind=kind, name=NAME.get(s["id"], s.get("name", s["id"])), xy=[round(float(c[0])), round(float(c[1]))],
                          built=int(s.get("built") or -999), inpage=bool(-150 <= c[0] <= 1970 and -150 <= c[1] <= 2200)))
    world = dict(built=lb, nodes=nodes, dest=ld)
    regs = {Y: json.load(gzip.open(os.path.join(EXP, "yamen_v13", f"registry_AF{Y}.json.gz"), "rt")) for Y in (40, 50, 60, 70)}
    res21 = json.load(open(os.path.join(EXP, "economy_v21", "results.json")))

    # ---------- 3 房况存量（全部账本房屋，逐年）+ 1 逐年生计
    C = {}                         # 房屋id → 房况
    stock = {}                     # Y → {hid: (state, cond, wear, repshare, age, prev)}
    v22m = {}
    livY = {}                      # Y → {hid: 生计码}
    LN = None
    prev_state = {}
    for Y in YEARS:
        d, T, TI, F, Hh, N, NT = S22.load_flows(os.path.join(PATH, f"flows_AF{Y}.json.gz"))
        LN = Hh["livelihood_names"]
        q = F["q"] / 1000.0
        m = F["t"] == TI["修房(付营造)"]
        rep = np.bincount(F["a"][m], q[m], NT)[:N]
        ll = S22.remap_ll(Hh, np.asarray(Hh["landlord"])); own = np.asarray(Hh["houses_owned"])
        owner = np.where(ll >= 0, ll, np.arange(N))
        house = [int(h[1:]) for h in Hh["house"]]
        rshare = rep[owner] / np.maximum(own[owner], 1)          # 房主修房按其名下栋数平摊
        rs = dict(zip(house, rshare.tolist()))
        livY[Y] = dict(zip(house, np.asarray(Hh["livelihood"]).tolist()))
        v22m[Y] = v22_maint(Y, d, F, TI, Hh, N, NT, lb)
        alive = [h for h, b in lb.items() if b <= Y < ld[h]]
        out = {}
        for h in alive:
            age = Y - lb[h]
            if h not in C:
                C[h] = V_H if lb[h] >= Y or lb[h] >= 40 else float(c_init(np.array(age)))
            c0 = C[h]
            w = float(wear(np.array(age), np.array(c0))) if lb[h] < Y else 0.0
            r = rs.get(h, 0.0)
            c1 = min(V_H, max(0.0, c0 - w + r))
            C[h] = c1
            st = int(state(np.array(c1)))
            out[h] = (st, c1, w, r, age, prev_state.get(h, -1))
            prev_state[h] = st
        for h in list(C):
            if ld[h] <= Y:
                C.pop(h); prev_state.pop(h, None)
        stock[Y] = out
        print(Y, len(alive), collections.Counter(v[0] for v in out.values()), flush=True)

    # ---------- 每年页面文件（复用 v22 compute_year，再用存量覆盖维护）
    MAINT = S22.MAINT
    summ = {}; files = {}; streets_all = {}
    rows_by_year = {}
    outs = {}
    for Y in YEARS:
        r = S22.compute_year(Y, os.path.join(PATH, f"flows_AF{Y}.json.gz"), page, world, regs[reg_year(Y)], ships_for(res21, Y))
        outs[Y] = r
    # 街道门槛：沿用 v22 固定门槛（AF70 基准各街分位），各年同一把尺
    res22 = json.load(open(os.path.join(EXP, "surface_v22", "results.json")))
    tq = np.array(res22["street_thresholds"]["trade_per_house"]); cq = np.array(res22["street_thresholds"]["craft_per_street"])
    base_store = {n["id"]: n.get("store_fee", 0) for n in S22_base_nodes(res22) if n["kind"] == "harbor"}
    page_ids = set(page_h)
    for Y in YEARS:
        r = outs[Y]
        for s in r["streets"]:
            s["crowd"] = int(np.searchsorted(tq, s["trade_ph"], side="right"))
            s["smoke"] = 0 if s["craft"] <= 0 else int(np.searchsorted(cq, s["craft"], side="right"))
        for n in r["nodes"]:
            if n["kind"] == "harbor":
                b = base_store.get(n["id"]) or 0
                n["fill"] = round(n["store_fee"] / b, 2) if b else None
                n["store"] = "满" if (n["fill"] or 0) >= 0.85 else "半空" if (n["fill"] or 0) >= 0.45 else "空"
        stY = stock[Y]
        for hs, row in r["rows"].items():
            h = int(hs)
            st, c1, w, rsh, age, pv = stY.get(h, (row[0], V_H, 0.0, 0.0, 0, -1))
            row[0] = st
            row += [int(round(100 * c1 / V_H)), round(w, 2), round(rsh, 2), int(age), int(pv)]
        cnt_page = collections.Counter(stY[int(h)][0] for h in r["rows"] if int(h) in stY)
        cnt_city = collections.Counter(v[0] for v in stY.values())
        sm = r["summary"]
        sm["maint_page"] = {MAINT[k]: int(cnt_page.get(k, 0)) for k in range(4)}
        sm["maint_city_houses"] = {MAINT[k]: int(cnt_city.get(k, 0)) for k in range(4)}
        sm.pop("maint_city", None)
        sm["path"] = "骤降路径" if Y >= 65 else "基准（与骤降路径相同）"
        sm["new_houses_drawn"] = int(sum(1 for h in r["rows"] if page_h[int(h)].get("new")))
        summ[f"AF{Y}"] = sm
        why = dict(S22.WHY); why.update(WHY_V23)
        doc = dict(
            _doc=f"surface_v23 · AF{Y}（{'到港骤降路径' if Y >= 65 else '骤降前，与基准相同'}）：经济层 economy_v21 → 表面层；维护 = 房况存量四档。字段见 fields；规则见 experiments/surface_v23/REPORT.md。——Hark（刘线）",
            year=Y, path="骤降路径" if Y >= 65 else "基准",
            fields=["维护(存量档)", "门面", "生计", "出租栋数", "租住房东房屋id", "标记(1贫困 2灶冷 4借债 8领施舍)", "关门原因(1低营收关门转业 2原定铺不在营 3零营收)",
                    "收入", "净收入", "支出", "现钱", "房主修房", "维护需求", "房主现钱", "房主净收入", "卖货", "手工品", "施舍", "亏空施舍",
                    "借入", "借自", "最大收入类", "最大收入额", "最大支出类", "最大支出额", "账本建成年",
                    "房况存量%", "今年折旧", "修房摊到本栋", "房龄", "上年维护档(-1 无)"],
            maint=MAINT, facade=S22.FACADE, level=S22.LEVEL, street_thresholds=res22["street_thresholds"], liv=LN, types=r["types"], why=why, poverty=S22.POOR,
            stock=dict(V_h=V_H, cut=CUT, wear="0.6×(0.6+0.8×min(房龄,60)/60)×(1+0.5×(1−C/V_h))"),
            summary=sm, houses=r["rows"],
            streets=[{k: s[k] for k in ("si", "x", "y", "h", "open", "ws", "closed", "stall", "trade", "crowd", "craft", "smoke", "beg", "beg_spot", "church_d")} for s in r["streets"]],
            nodes=r["nodes"], gone={str(h): ld.get(h) for h in r["unmatched"]},
        )
        p = os.path.join(PAGE, f"surface_AF{Y}.json")
        with open(p, "w") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        files[os.path.basename(p)] = os.path.getsize(p)

    # ---------- 1 逐年生计 → trades.json（页面读）
    allh = sorted(page_ids)
    th = {}
    for h in allh:
        s = "".join(chr(97 + livY[Y][h]) if h in livY[Y] else "." for Y in YEARS)
        if s.strip("."):
            th[str(h)] = s
    TERM = {"雇工": "雇工", "码头脚夫": "码头脚夫", "面包": "面包师", "手工铺": "手艺人", "作坊": "作坊主", "港货商": "港货商", "运水人": "运水人",
            "营造": "营造匠", "体面户": "体面人家", "兵户": "兵户", "装卸行": "装卸行", "港仓": "货栈", "船修": "船匠", "牙人": "牙人", "兑钱商": "银钱商",
            "菜农": "菜农", "渔户": "渔户"}
    trades = dict(_doc="surface_v23 · 每栋房每年的行当 = 经济层生计（economy_v21 骤降路径 AF40–70 逐年流；40 年前按 40 年回推）。h[id] 第 k 个字符 = 建城 40+k 年生计码（a=0，'.'=当年账本无户）；"
                       "页面用语 term；手工铺/作坊且原散列行当是手艺（craft_fine）时以原行当为细分。——Hark（刘线）",
                  y0=40, y1=70, liv=LN, term=[TERM[n] for n in LN], craft_liv=[LN.index("手工铺"), LN.index("作坊")], craft_fine=["陶匠", "织工", "鞋匠", "铜匠"], h=th)
    with open(os.path.join(PAGE, "trades.json"), "w") as f:
        json.dump(trades, f, ensure_ascii=False, separators=(",", ":"))
    files["trades.json"] = os.path.getsize(os.path.join(PAGE, "trades.json"))

    # ---------- 跳变对比（页面房屋，同一骤降路径）
    def page_states(Y, src):
        r = outs[Y]["rows"]
        return {int(h): (src[Y].get(int(h)) if src is v22m else stock[Y][int(h)][0]) for h in r if int(h) in (src[Y] if src is v22m else stock[Y])}
    jumps = {}
    for Y in range(41, 71):
        a22, b22 = page_states(Y - 1, v22m), page_states(Y, v22m)
        a23, b23 = page_states(Y - 1, stock), page_states(Y, stock)
        com = [h for h in b22 if h in a22 and h in a23 and h in b23]
        def tr(a, b):
            c = collections.Counter((MAINT[a[h]], MAINT[b[h]]) for h in com if a[h] != b[h])
            return sum(c.values()), {f"{k[0]}→{k[1]}": v for k, v in c.most_common()}
        n22, t22 = tr(a22, b22); n23, t23 = tr(a23, b23)
        jumps[f"AF{Y-1}→{Y}"] = dict(common=len(com), v22_rule=n22, v23_stock=n23, v22_trans=t22, v23_trans=t23,
                                      v22_derelict_neglect=t22.get("破败→失修", 0) + t22.get("失修→破败", 0),
                                      v23_derelict_neglect=t23.get("破败→失修", 0) + t23.get("失修→破败", 0))
    # 每栋房 AF40–70 档位改变次数（翻转 = 跳回上一档）
    flips = collections.Counter(); flips22 = collections.Counter()
    for src, ctr in ((stock, flips), (v22m, flips22)):
        for h in page_ids:
            seq = [(src[Y][h][0] if src is stock else src[Y][h]) for Y in YEARS if h in src[Y]]
            back = sum(1 for i in range(2, len(seq)) if seq[i] == seq[i - 2] and seq[i] != seq[i - 1])
            ctr[min(back, 5)] += 1
    v22dist = {f"AF{Y}": {MAINT[k]: int(collections.Counter(v22m[Y][int(h)] for h in outs[Y]["rows"] if int(h) in v22m[Y]).get(k, 0)) for k in range(4)} for Y in (40, 50, 60, 64, 65, 66, 70)}
    # 新建房补画
    newinfo = dict(total=len(new), built_61_70=sum(1 for x in new if x[1] > 60), built_le60_missing=len(new_before61),
                   demolished_by70=sum(1 for x in new if x[2] <= 70),
                   drawn_by_year={f"AF{Y}": sum(1 for x in new if x[1] <= Y < x[2]) for Y in (61, 65, 70)},
                   page_dest_fixed=len(dest_fix), page_dest_fixed_by_year=dict(collections.Counter(dest_fix.values())))
    res = dict(_doc="surface_v23 结果——Hark（刘线）", affine_page_to_ledger=aff, files=files, new_houses=newinfo,
               stock_params=dict(V_h=V_H, need=NEED, cut=CUT, wear="0.6×(0.6+0.8×min(age,60)/60)×(1+0.5×(1−C/V_h))", init="AF40 已在立：V_h×max(0.85, 1−0.003×房龄)；新建房 V_h"),
               jumps=jumps, flipbacks_per_house_40_70=dict(v23_stock=dict(sorted(flips.items())), v22_rule=dict(sorted(flips22.items()))),
               maint_page_v23={k: v["maint_page"] for k, v in summ.items()}, maint_city_houses_v23={k: v["maint_city_houses"] for k, v in summ.items()},
               maint_page_v22_rule_same_path=v22dist, summary=summ)
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else float(o))
    print(json.dumps(newinfo, ensure_ascii=False)); print(json.dumps(jumps["AF64→65"], ensure_ascii=False)); print(json.dumps(summ["AF70"]["maint_page"], ensure_ascii=False))
    print(sum(files.values()) / 1e6, "MB")


def S22_base_nodes(res22):
    """仓储满空基准：v22 AF70 基准路径各港仓储费（同一把尺）。"""
    return res22["nodes_by_year"]["AF70"]


if __name__ == "__main__":
    main()
