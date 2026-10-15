# -*- coding: utf-8 -*-
"""economy_v21：手工需求内生（收入档边际消费 + 港口商人/船员采购 + 出口总额随到港量、由在营铺分）＋ 手工铺逐年进出（低于阈值连续 2 年关门转业、
高于阈值且有空铺面时回流开铺，每年进出有上限）。去掉 v20 的一次性铺数上限；基线 = v20 G4（只给体面户收入、不设上限）。
地下数据管线，不做页面。——Hark（刘线）

按路径只读载入（不改）：../economy_v20/economy.py（Econ20、emit_year20…；经它再载入 v19…v7、v12）。
v20 载入时把 v18 的 HERE / Econ18 / emit_year18 改指 v20；本文件载入后再把 v18 / v19 / v20 的 HERE 与 Econ18 / emit_year18 改指本目录与 Econ21。
运行：python3 economy.py run            # 基准 AF40–70 + 输出
      python3 economy.py sens 0.5 & python3 economy.py sens 1.5; python3 economy.py sens merge
      python3 economy.py events         # 5 个事件：增量 == 重建（需先 run）
      python3 economy.py path v21_shock && python3 economy.py path g4_shock && python3 economy.py path_merge
      python3 economy.py diag           # AF70 净收入贫困户构成（G4 与 v21）
"""
import os, sys, json, gzip, time, pickle, importlib.util, collections, csv
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


E20 = _load("economy_v20_for_v21", os.path.join(EXP, "economy_v20", "economy.py"))
E19, E18, E15, E17 = E20.E19, E20.E18, E20.E15, E20.E17
for _k, _v in list(vars(E20).items()):
    if not _k.startswith("__") and _k not in ("HERE", "EXP", "_load", "run", "sens", "events", "path", "path_merge", "diag", "_diag_flows",
                                               "emit_year20", "v19_ref", "E19", "E18", "E15", "E17", "simulate", "craft_cap"):
        globals()[_k] = _v
Econ20 = E20.Econ20

NEW_T21 = ["买卖:手工(港口采购)"]
for t in NEW_T21:
    if t not in E15.TI:
        E15.TI[t] = len(E15.TYPES); E15.TYPES.append(t)
TYPES, TI = E15.TYPES, E15.TI
for t in NEW_T21:
    if t not in E18.REV_T:
        E18.REV_T.append(t)          # 铺子营收（下一年区内雇工需求、进出判定都按它）

A = E20.A
A.update(
    craft_cap_on=False,      # 去掉 v20 一次性铺数上限（基线 = v20 G4）
    # ---- 1 手工需求内生
    dem_on=True,
    q_craft_base=0.30,       # 日常必需手工品（户需求表 q_craft，v15 0.5 → 0.3；其余改由收入档边际消费，假设）
    mpc_bands=[[4.5, 0.0], [8.0, 0.06], [15.0, 0.10], [1e9, 0.14]],   # 上年可支配收入（净收入）分档：4.5 以下 0；4.5–8 部分 6%；8–15 部分 10%；15 以上部分 14%（富户买更多手工品；假设）
    mpc_cash_cap=0.5,        # 边际手工消费 ≤ 年初现钱 × 50%（不靠借钱买）
    port_buy=1000.0,         # 港口商人 / 船员采购本城手工品，到港基准时全城每年总额（∝ 到港量，线性；假设）
    R_port_buy=120.0,        # 步行到最近商港 ≤120 的手工铺 / 作坊均分
    export_pool_on=True,     # 手工铺出口：总额 = 1.5 × 当年「v19 原定铺数」× (到港/基准)^0.5，由当年在营铺均分（不随关铺缩水）
    # ---- 2 铺子进出
    dyn_on=True,
    r_exit=5.5,              # 铺年营收（本城卖货 + 港口采购 + 出口）< 5.5（扣原料 30% 后 ≈3.85，贴贫困线加雇工钱余量）；标定 G6，见 REPORT
    exit_years=2,            # 连续 2 年低于阈值 → 关门转业
    exit_cap=0.05,           # 每年关铺 ≤ 5% × 在营铺（标定 G6）
    r_entry=8.0,             # 节点上年铺均营收 ≥ 8.0 且有空铺面（在营 < v19 原定铺面）→ 可开新铺，开后预计铺均 ≥ 8.0
    entry_cap=0.03,          # 每年开铺 ≤ 3% × 在营铺
    R_conv_harbor21=60.0,    # 转业去向：离商港直线 ≤60 → 码头脚夫，否则 → 雇工
)
if os.environ.get("V21_OVR"):
    A.update(json.loads(os.environ["V21_OVR"]))


# ================================================================ 状态：当年生计（liv）、连续低营收年数、上年可支配收入
class State21(E19.State19):
    def copy(self):
        s = E19.State19.copy(self)
        s.__class__ = State21
        s.liv = self.liv.copy() if getattr(self, "liv", None) is not None else None
        s.low = self.low.copy() if getattr(self, "low", None) is not None else None
        s.disp_prev = self.disp_prev.copy() if getattr(self, "disp_prev", None) is not None else None
        return s


def mpc_spend(d):
    out = np.zeros_like(d); lo = 0.0
    for hi, r in A["mpc_bands"]:
        out += r * np.clip(d - lo, 0.0, hi - lo); lo = hi
    return out


class Econ21(Econ20):
    def __init__(self, H, W, ships_mult=1.0, kin=None):
        super().__init__(H, W, ships_mult, kin)
        self.liv0 = self.liv.copy()                 # v19 原定生计（铺面）
        HX = np.array([H.st[x]["xy"] for x in W.harbors])
        self.dharb = np.min(np.hypot(H.xy[:, None, 0] - HX[None, :, 0], H.xy[:, None, 1] - HX[None, :, 1]), 1)
        self.dyn_log = {}

    def _use_state(self, S):
        lv = getattr(S, "liv", None)
        self.liv = lv if lv is not None else self.liv0
        self.L = dict(self.L); self.L["liv"] = self.liv
        cv = (self.liv0 == 3) & (self.liv != 3)
        self.conv = dict(any=cv, porter=cv & (self.liv == 1), labourer=cv & (self.liv == 0))

    def derive(self, yr, S):
        self._use_state(S)
        return Econ20.derive(self, yr, S)

    # K0 第一个 Rows：体面户收入（v20）+ 手工需求内生（v21，k=9 每年全量重算）
    def _fine_rows(self, yr, R):
        Econ20._fine_rows(self, yr, R)
        if A["dem_on"]:
            self._craft_rows(yr, R)

    def _craft_rows(self, yr, R):
        H = self.H; al = yr.alive; dv = self._dv; S = self._S; n = len(al)
        liv = self.liv[al]
        X_s = self.I(("外", "船商"))
        ships = self.ships(yr); sfac = (ships / A["ships_base"]) ** A["export_elast"]
        info = dict()
        # (a) 收入档边际消费：上年净收入 → 本节点手工卖家（与日常买卖同一家）
        dp = getattr(S, "disp_prev", None)
        if dp is not None:
            nm = len(dv["mk"]); node = dv["node"]
            s_i = np.nonzero(np.isin(liv, (3, 4)))[0]
            tab = [[] for _ in range(nm)]
            for i in s_i[np.argsort(dv["door_rank"][s_i], kind="stable")]:
                tab[node[i]].append(int(al[i]))
            has = np.array([len(t) > 0 for t in tab]); eff = np.arange(nm)
            if has.any():
                hx = np.nonzero(has)[0]
                for m_ in np.nonzero(~has)[0]:
                    eff[m_] = hx[int(np.argmin(np.hypot(*(dv["MX"][hx] - dv["MX"][m_]).T)))]
                cntn = np.array([len(t) for t in tab]); eN = eff[node]
                flat = np.array([x for t in tab for x in t], np.int64); offn = np.concatenate([[0], np.cumsum(cntn)[:-1]])
                hs = self.hseed[al]
                sel = flat[np.minimum(offn[eN] + hs % np.maximum(cntn[eN], 1), len(flat) - 1)]
                amt = np.minimum(mpc_spend(dp[al]), A["mpc_cash_cap"] * np.maximum(S.cash[al], 0.0))
                m = np.nonzero((amt > 1e-9) & (sel != al))[0]
                R.add("买卖:手工", al[m], sel[m], amt[m],
                      f"手工需求内生：上年净收入分档边际消费（{A['mpc_bands']}；≤年初现钱 {A['mpc_cash_cap']:.0%}）→ 本节点手工卖家（v21 假设，富户买更多）", -1, 9)
                info["mpc_total"] = round(float(amt[m].sum()), 1); info["mpc_buyers"] = int(len(m))
        # (b) 港口商人 / 船员采购：船商 → 步行到商港 ≤R 的手工铺 / 作坊均分，∝ 到港量
        nh = len(self.W.harbors)
        near = np.nonzero(np.isin(liv, (3, 4)) & (np.min(dv["walk"][:, :nh], 1) <= A["R_port_buy"]))[0]
        tot = A["port_buy"] * ships / A["ships_base"]
        if len(near) and tot > 0:
            R.add("买卖:手工(港口采购)", X_s, al[near], tot / len(near),
                  f"港口商人 / 船员采购本城手工品：到港基准时全城 {A['port_buy']:.0f}/年 ∝ 到港量，步行到商港 ≤{A['R_port_buy']:.0f} 的手工铺 / 作坊均分（v21 假设）", -1, 9)
        info["port_buy_total"] = round(float(tot), 1); info["port_buy_sellers"] = int(len(near))
        # (c) 手工铺出口总额：1.5 × 当年 v19 原定铺数 × sfac，在营铺均分
        if A["export_pool_on"]:
            sh = np.nonzero(liv == 3)[0]
            pool = A["export_shop0"] * int((self.liv0[al] == 3).sum()) * sfac
            if len(sh):
                R.add("出口:手工(船商付)", X_s, al[sh], pool / len(sh),
                      f"手工铺出口总额 = 1.5 × v19 原定铺数 × (到港/基准)^{A['export_elast']}，由当年在营手工铺均分（v21 假设：出口由船商定，不随铺数变）", -1, 9)
            info["export_pool"] = round(float(pool), 1); info["export_per_shop"] = round(float(pool / max(len(sh), 1)), 3)
        self._craft_info = info

    def step(self, yr, S, inc=None):
        self._use_state(S); self._S = S; self._craft_info = {}
        old = (A["q_craft"], A["export_shop"])
        if A["dem_on"]:
            A["q_craft"] = A["q_craft_base"]
        if A["dem_on"] and A["export_pool_on"]:
            A["export_shop"] = 0.0          # 手工铺出口改由 k=9 总额行发（作坊出口 export_work 原样）
        try:
            out = Econ20.step(self, yr, S, inc)
        finally:
            A["q_craft"], A["export_shop"] = old
        out["craft21"] = dict(self._craft_info)
        self._last_out = out
        return out

    # 年末：可支配收入、铺子进出（写进下一年状态）
    def advance(self, yr, S, out):
        H = self.H; al = yr.alive
        S2, inc, exp = Econ20.advance(self, yr, S, out)
        S2.__class__ = State21
        R = out["rows"]; NT = max(out["NT"], H.NH + len(self.inst_keys) + 1)
        bm = np.isin(R["t"], [TI[t] for t in E18.BUSINESS_OUT])
        S2.disp_prev = inc - np.bincount(R["a"][bm], R["v"][bm], NT)[:H.NH]
        liv = (S.liv if getattr(S, "liv", None) is not None else self.liv0).copy()
        low = S.low.copy() if getattr(S, "low", None) is not None else np.zeros(H.NH, np.int16)
        rev = S2.rev_prev
        lg = dict(shops=int((liv[al] == 3).sum()), exits=0, entries=0, to_porter=0, to_labourer=0, returned=0, from_labourer=0)
        if A["dyn_on"]:
            sh = al[liv[al] == 3]
            lowm = rev[sh] < A["r_exit"]
            low[sh] = np.where(lowm, low[sh] + 1, 0)
            # 关门：连续 exit_years 年低于阈值，营收最低的先关，≤ exit_cap
            cand = sh[low[sh] >= A["exit_years"]]
            k_exit = int(np.floor(A["exit_cap"] * len(sh)))
            cand = cand[np.lexsort((H.idnum[cand], rev[cand]))][:k_exit]
            to_p = cand[self.dharb[cand] <= A["R_conv_harbor21"]]; to_w = cand[self.dharb[cand] > A["R_conv_harbor21"]]
            liv[to_p] = 1; liv[to_w] = 0; low[cand] = 0
            lg.update(exits=int(len(cand)), to_porter=int(len(to_p)), to_labourer=int(len(to_w)))
            # 开铺：按市场节点；上年铺均营收 ≥ r_entry 且 在营 < v19 原定铺面；先回流（原铺户），再雇工；开后预计铺均 ≥ r_entry；全城 ≤ entry_cap
            dvv = out["dv"]; node = dvv["node"]; nm = len(dvv["mk"])
            pos = np.full(H.NH, -1, np.int64); pos[al] = np.arange(len(al))
            alive_after = al[liv[al] == 3]
            n_now = np.bincount(node[pos[alive_after]], minlength=nm)
            sh_old = sh[~np.isin(sh, cand)]
            r_node = np.bincount(node[pos[sh]], rev[sh], nm) / np.maximum(np.bincount(node[pos[sh]], minlength=nm), 1)
            prem = np.bincount(node[pos[al[self.liv0[al] == 3]]], minlength=nm)
            k_entry = int(np.floor(A["entry_cap"] * len(sh)))
            u = stable_u(H.idnum, 2100 + yr.Y)
            ent = []
            order = np.argsort(-r_node, kind="stable")
            for j in order:
                if len(ent) >= k_entry:
                    break
                if r_node[j] < A["r_entry"] or n_now[j] >= prem[j] or n_now[j] == 0:
                    continue
                tot_rev = r_node[j] * n_now[j]
                room = min(int(prem[j] - n_now[j]), int(np.floor(tot_rev / A["r_entry"])) - int(n_now[j]), k_entry - len(ent))
                if room <= 0:
                    continue
                inj = al[node == j]
                ret = inj[(self.liv0[inj] == 3) & np.isin(liv[inj], (0, 1))]
                lab = inj[(liv[inj] == 0) & (self.liv0[inj] != 3)]
                ret = ret[np.argsort(u[ret], kind="stable")]; lab = lab[np.argsort(u[lab], kind="stable")]
                pick = list(ret[:room]) + list(lab[:max(0, room - len(ret))])
                for g in pick:
                    ent.append((int(g), bool(self.liv0[g] == 3)))
            if ent:
                ge = np.array([g for g, _ in ent], np.int64)
                liv[ge] = 3; low[ge] = 0
            lg.update(entries=len(ent), returned=int(sum(1 for _, r in ent if r)), from_labourer=int(sum(1 for _, r in ent if not r)))
        lg["shops_next"] = int((liv[al] == 3).sum())
        S2.liv = liv; S2.low = low
        self.dyn_log[yr.Y] = lg
        out["dyn"] = lg
        return S2, inc, exp

    def init_state(self):
        S = Econ20.init_state(self)
        S.__class__ = State21
        S.liv = self.liv0.copy(); S.low = np.zeros(self.H.NH, np.int16)
        # 引导年可支配收入：引导步（现钱无限）的流，去掉盈余追加（k=7），收入 − 营业支出
        o = self._last_out; R = o["rows"]; NT = max(o["NT"], self.H.NH + len(self.inst_keys) + 1)
        m = (~np.isin(R["t"], GRAIN_T)) & (~np.isin(R["t"], FIN_T)) & (R["k"] != 7)
        bm = np.isin(R["t"], [TI[t] for t in E18.BUSINESS_OUT]) & (R["k"] != 7)
        S.disp_prev = np.bincount(R["b"][m], R["v"][m], NT)[:self.H.NH] - np.bincount(R["a"][bm], R["v"][bm], NT)[:self.H.NH]
        self._use_state(S)
        return S


def emit_year21(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
    E20.emit_year20(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay)
    p = os.path.join(E20.HERE, f"flows_AF{yr.Y}.json.gz")
    d = json.load(gzip.open(p, "rt"))
    d["_doc"] = d["_doc"].replace("economy_v20", "economy_v21") + " v21：craft_conv = 当年因营收低关门转业（原 v19 手工铺、当年不在营）；liv_v19 = v19 原定生计。"
    d["households"]["liv_v19"] = E.liv0[al].tolist()
    d["craft21"] = out.get("craft21")
    with gzip.open(p, "wt", compresslevel=9) as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))


# v18 / v19 / v20 的模块全局改指本目录 / 本类（父文件不动）
for _m in (E18, E19, E20):
    _m.HERE = HERE
E18.Econ18 = Econ21
E18.emit_year18 = emit_year21
simulate = E18.simulate


def g4_ref():
    c = json.load(open(os.path.join(EXP, "economy_v20", "calibration.json")))
    return next(g for g in c["groups"] if g["group"].startswith("G4"))


def shops_series(per):
    return {str(Y): per[Y]["stats"]["livelihood_counts"].get("手工铺", 0) for Y in per}


def run():
    o = simulate(1.0, True)
    E, H, per, recon = o["E"], o["H"], o["per"], o["recon"]
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    res = dict(
        _doc="economy_v21 结果（economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
        years={str(Y): per[Y]["stats"] for Y in per},
        shops_series=shops_series(per), dyn_log={str(k): v for k, v in E.dyn_log.items()},
        wage_series={str(Y): per[Y]["stats"]["sector"]["labor"]["wage"] for Y in per},
        unemployment_series={str(Y): per[Y]["stats"]["sector"]["labor"]["rate_unemployed_or_casual"] for Y in per},
        treasury_curves={k: dict(series=v, summary=E15.curve(v)) for k, v in o["treas"].items()},
        cash_accumulation=o["accum"],
        conservation=dict(max_per_type_err=max(r["max_type_err"] for r in recon), max_money_err=max(r["conservation_err"] for r in recon),
                          grain_all_years_ok=all(r["grain_ok"] for r in recon), house_tax_all_years_ok=all(r["house_tax_ok"] for r in recon),
                          houses_all_years_ok=all(r["houses_ok"] for r in recon)),
        per_type_AF70=per[70]["per_type"],
        timing=dict(total_s=round(o["t_total"], 2), step_median_s=float(np.median([t["step_s"] for t in o["timing"]]))),
        files={f"flows_AF{Y}.json.gz": os.path.getsize(os.path.join(HERE, f"flows_AF{Y}.json.gz")) for Y in SNAP},
        sample=dict(house=H.hid[o["sample"][0]], text=o["sample"][1]),
        g4_ref=g4_ref(),
        calibration=json.load(open(os.path.join(HERE, "calibration.json"))) if os.path.exists(os.path.join(HERE, "calibration.json")) else None,
    )
    p = os.path.join(HERE, "results.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    for k in ("events", "sensitivity", "events_total_s", "shock_path", "diag", "g4_run"):
        if k in old:
            res[k] = old[k]
    if os.path.exists(os.path.join(HERE, ".g4_run.json")):
        res["g4_run"] = json.load(open(os.path.join(HERE, ".g4_run.json")))
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(HERE, "sample_household.txt"), "w") as f:
        f.write("\n\n".join(o["sample"][1][y] for y in sorted(o["sample"][1])))
    pickle.dump(dict(states=o["ev_states"], inst_keys=E.inst_keys), open(os.path.join(HERE, ".cache_states.pkl"), "wb"))
    s70 = per[70]["stats"]
    print(json.dumps(dict(total_s=round(o["t_total"], 1), cons=res["conservation"],
                          AF70={k: s70[k] for k in ("poor_share", "poor_share_net", "poor_net", "gini_income", "gini_net_income", "unfunded_deficits", "reserve", "poor_net_by_livelihood")},
                          labor=s70["sector"]["labor"], unemp=res["unemployment_series"], shops=res["shops_series"]), ensure_ascii=False, default=float))


def sens():
    E18.sens()


def events():
    E18.events()


def path():
    nm = sys.argv[2]
    if nm == "g4_shock":
        A.update(dem_on=False, dyn_on=False, export_pool_on=False)
    H = HW(); W = HW15(H)
    o = simulate(1.0, False, H=H, W=W, shock={65: 0.3}, cls=Econ21)
    row = {}
    for Y in range(63, 71):
        s = o["per"][Y]["stats"]; row[str(Y)] = E18._yr_row(s)
        row[str(Y)]["reserve_spend"] = {k: s["spend"]["reserve"].get(k) for k in ("level", "remit", "gap", "scale", "n_pw_extra", "n_fish", "n_std", "budget")}
        row[str(Y)]["shops"] = s["livelihood_counts"].get("手工铺", 0)
        row[str(Y)]["poor_net_by_livelihood"] = s["poor_net_by_livelihood"]
        row[str(Y)]["dyn"] = o["E"].dyn_log.get(Y)
    row["shops_series"] = shops_series(o["per"])
    row["checks"] = dict(max_money_err=max(r["conservation_err"] for r in o["recon"]), checks_ok=all(r["grain_ok"] and r["house_tax_ok"] and r["houses_ok"] for r in o["recon"]))
    print(nm, json.dumps({Y: (v["unemp_casual"], v["poor"], v["poor_net"], v["shops"]) for Y, v in row.items() if Y not in ("checks", "shops_series")}), row["checks"])
    json.dump(row, open(os.path.join(HERE, f".path_{nm}.json"), "w"), ensure_ascii=False, default=float)


def path_merge():
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); out = {}
    for nm in ("v21_shock", "g4_shock"):
        f = os.path.join(HERE, f".path_{nm}.json")
        if os.path.exists(f):
            out[nm] = json.load(open(f)); os.remove(f)
    out["v21_base"] = {str(Y): dict(E18._yr_row(res["years"][str(Y)]), shops=res["years"][str(Y)]["livelihood_counts"].get("手工铺", 0)) for Y in range(63, 71)}
    v20 = json.load(open(os.path.join(EXP, "economy_v20", "results.json")))["shock_path"]
    for k in ("v20_shock", "v20_base"):
        out[k] = v20[k]
    res["shock_path"] = out
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


def g4_run():
    """基线 G4（v20：体面户收入、不设上限）用本文件跑一遍 AF70（v21 新机制全关），存 flows 到 /tmp 供 diag。"""
    A.update(dem_on=False, dyn_on=False, export_pool_on=False)
    global HERE
    tmp = "/tmp/v21_g4"; os.makedirs(tmp, exist_ok=True)
    for _m in (E18, E19, E20):
        _m.HERE = tmp
    o = simulate(1.0, True)
    s = o["per"][70]["stats"]
    r = dict(AF70={k: s[k] for k in ("poor_share", "poor_share_net", "poor_net", "gini_net_income", "unfunded_deficits", "poor_net_by_livelihood")},
             unemp=s["sector"]["labor"]["rate_unemployed_or_casual"], labor=s["sector"]["labor"], shops_series=shops_series(o["per"]),
             unemployment_series={str(Y): o["per"][Y]["stats"]["sector"]["labor"]["rate_unemployed_or_casual"] for Y in o["per"]},
             max_money_err=max(x["conservation_err"] for x in o["recon"]))
    json.dump(r, open(os.path.join(HERE, ".g4_run.json"), "w"), ensure_ascii=False, default=float)
    print(json.dumps(r, ensure_ascii=False)[:1500])


def diag():
    r = dict(g4=E20._diag_flows("/tmp/v21_g4/flows_AF70.json.gz"), v21=E20._diag_flows(os.path.join(HERE, "flows_AF70.json.gz")))
    p = os.path.join(HERE, "results.json"); res = json.load(open(p)); res["diag"] = r
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "sens": sens, "events": events, "path": path, "path_merge": path_merge, "diag": diag, "g4_run": g4_run}[sys.argv[1]]()
