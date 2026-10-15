# -*- coding: utf-8 -*-
"""economy_v20：剩余贫困的两块——手工铺按市场节点的实际需求定可维持铺数（过剩铺转业），体面户按身份给收入来源。
地下数据管线，不做页面。——Hark（刘线）

按路径只读载入（不改）：
  ../economy_v19/economy.py（Econ19、emit_year19…；经它再载入 v18…v7、v12）
  ../economy_v19/flows_AF70.json.gz（只读：v19 基准 AF70 各市场节点手工实际需求，定铺数上限）
  v19 在载入时把 v18 的 HERE / Econ18 / emit_year18 改指 v19；本文件载入 v19 后再改指本目录与本类，v19 / v18 文件不动。
运行：python3 economy.py run            # 基准 AF40–70 + 输出
      python3 economy.py sens 0.5 & python3 economy.py sens 1.5; python3 economy.py sens merge
      python3 economy.py events         # 5 个事件：增量 == 重建（需先 run）
      python3 economy.py path v20_shock && python3 economy.py path_merge
      python3 economy.py diag           # AF70 净收入贫困户构成（v19 与 v20）+ 体面户身份 + 转业户去向
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


E19 = _load("economy_v19_for_v20", os.path.join(EXP, "economy_v19", "economy.py"))
E18, E15, E17 = E19.E18, E19.E15, E19.E17
for _k, _v in list(vars(E19).items()):
    if not _k.startswith("__") and _k not in ("HERE", "EXP", "_load", "run", "sens", "events", "path", "path_merge", "diag", "_diag_flows",
                                               "emit_year19", "v18_ref", "E18", "E15", "E17", "simulate"):
        globals()[_k] = _v
Econ19 = E19.Econ19

NEW_T20 = ["田租(城外田产)", "年金(皇库)"]
for t in NEW_T20:
    if t not in E15.TI:
        E15.TI[t] = len(E15.TYPES); E15.TYPES.append(t)
TYPES, TI = E15.TYPES, E15.TI
if "城外田庄" not in E15.EXT:
    E15.EXT.append("城外田庄")          # 新外部源（EXT 是各版共用的同一个列表对象：守恒按外部流入记）
EXT = E15.EXT

A = E19.A
A.update(
    # ---- 1 手工铺：按市场节点实际需求定可维持铺数
    craft_cap_on=True,
    craft_rmin=7.0,          # 可维持铺：节点内每铺平均年营收（本城卖货 + 出口额度）≥ 7.0（扣原料 30% 后 ≈4.9；同节点内各铺分到的买主多少不一，留出余量；标定 G1–G3 取 7.0，假设）
    export_shop0=1.5,        # v15 每铺出口额度（到港基准）；v20 起手工铺出口总额 = 铺数（转业前）× 1.5 不变，由留下的铺子分
    R_conv_harbor20=60.0,    # 转业去向：离商港直线 ≤60 → 码头脚夫（港口），否则 → 雇工（转作他人作坊 / 铺子雇工 = 合并）
    # ---- 2 体面户：按身份给收入
    fine_on=True,
    fine_estate=4.5,         # 自住有房、无出租、无官职的体面户 → 城外田产租（城外田庄净流入，每户每年；假设）
    fine_pension=3.5,        # 租住的体面户中 p_pension 份 → 年金 / 俸禄遗属（皇库付；假设）
    p_pension=0.3,
)
if os.environ.get("V20_OVR"):
    A.update(json.loads(os.environ["V20_OVR"]))
FINE_ROLES = ["", "房东", "任官", "城外田产", "年金", "无来源"]


# ================================================================ 1 手工铺上限（静态，同 v16 面包户再平衡的做法）
def craft_cap(H, W, liv):
    """各市场节点（AF70 在立市场，户按直线最近归节点）：v19 基准 AF70 实测本城手工买卖（日常 + 添置）D_m，
    留下的铺数 k_m = 满足「D_m/(k_m + 作坊数_m) + 出口额度/铺 ≥ craft_rmin」的最大 k（出口总额固定，留下的铺分）。
    过剩铺按确定性散列在本节点抽出（概率 1 − k_m/n_m，作用于历年全部在册手工铺）。"""
    d = json.load(gzip.open(os.path.join(EXP, "economy_v19", "flows_AF70.json.gz"), "rt"))
    T = d["types"]; F = d["flows"]; t = np.array(F["t"]); b = np.array(F["b"]); v = np.array(F["q"]) / 1000
    hh = d["households"]; ent = np.array(hh["ent"]); lv = np.array(hh["livelihood"]); mkt = np.array(hh["market"])
    sold = np.bincount(b[t == T.index("买卖:手工")], v[t == T.index("买卖:手工")], len(d["entities"]))
    mk = H.standing(Y1, ("market", "forum", "harbor", "warehouse"))
    mi = {k: i for i, k in enumerate(mk)}; nm = len(mk)
    sel = np.isin(lv, (3, 4))
    D = np.zeros(nm); n3 = np.zeros(nm); n4 = np.zeros(nm)
    for e, l, m in zip(ent[sel], lv[sel], mkt[sel]):
        j = mi[m]; D[j] += sold[e]; (n3 if l == 3 else n4)[j] += 1
    E_tot = A["export_shop0"] * n3.sum()
    k = n3.copy()
    for _ in range(30):
        ex = E_tot / max(k.sum(), 1)
        k_new = np.zeros(nm)
        for j in range(nm):
            if n3[j] == 0:
                continue
            kk = np.arange(int(n3[j]), 0, -1)
            ok = D[j] / (kk + n4[j]) + ex >= A["craft_rmin"]
            k_new[j] = kk[ok][0] if ok.any() else 1     # 每个有铺的节点至少留 1 铺
        if np.array_equal(k_new, k):
            break
        k = k_new
    r_keep = np.where(n3 > 0, k / np.maximum(n3, 1), 1.0)
    MX = np.array([H.st[x]["xy"] for x in mk])
    node = np.argmin(np.hypot(H.xy[:, None, 0] - MX[None, :, 0], H.xy[:, None, 1] - MX[None, :, 1]), 1)
    reg = np.zeros(H.NH, bool)
    for Y in range(Y0, Y1 + 1):
        reg[[H.g[h] for h in H.years[Y]]] = True
    u = stable_u(H.idnum, 201)
    conv = reg & (liv == 3) & (u >= r_keep[node])
    HX = np.array([H.st[x]["xy"] for x in W.harbors])
    dh = np.min(np.hypot(H.xy[:, None, 0] - HX[None, :, 0], H.xy[:, None, 1] - HX[None, :, 1]), 1)
    to_p = conv & (dh <= A["R_conv_harbor20"]); to_w = conv & ~to_p
    liv2 = liv.copy(); liv2[to_p] = 1; liv2[to_w] = 0
    n3_ever, n3_after = int((reg & (liv == 3)).sum()), int((reg & (liv2 == 3)).sum())
    info = dict(markets=mk, demand_local_AF70_v19={mk[j]: round(float(D[j]), 1) for j in range(nm) if n3[j] + n4[j] > 0},
                shops_AF70_v19={mk[j]: int(n3[j]) for j in range(nm) if n3[j] > 0}, workshops_AF70_v19={mk[j]: int(n4[j]) for j in range(nm) if n4[j] > 0},
                keep_AF70={mk[j]: int(k[j]) for j in range(nm) if n3[j] > 0},
                revenue_per_shop_before={mk[j]: round(float(D[j] / (n3[j] + n4[j]) + A["export_shop0"]), 2) for j in range(nm) if n3[j] > 0},
                revenue_per_shop_after={mk[j]: round(float(D[j] / (k[j] + n4[j]) + E_tot / max(k.sum(), 1)), 2) for j in range(nm) if n3[j] > 0},
                export_total_AF70=round(float(E_tot), 1), export_per_shop_after_AF70=round(float(E_tot / max(k.sum(), 1)), 3),
                shops_ever=n3_ever, shops_ever_after=n3_after, converted_ever=int(conv.sum()), to_porter_ever=int(to_p.sum()), to_labourer_ever=int(to_w.sum()))
    export_shop = A["export_shop0"] * n3_ever / max(n3_after, 1)     # 出口总额不变（按历年在册铺数之比），留下的铺分
    info["export_shop_param"] = round(export_shop, 4)
    return liv2, conv, to_p, to_w, export_shop, info


# ================================================================ 注入行：K1 之前的第一个 Rows 带上当年体面户收入
class Rows20(E18.Rows):
    pending = None

    def __init__(self):
        super().__init__()
        f = Rows20.pending
        if f is not None:
            Rows20.pending = None
            f(self)


E18.Rows = Rows20


class Econ20(Econ19):
    def __init__(self, H, W, ships_mult=1.0, kin=None):
        super().__init__(H, W, ships_mult, kin)
        self.liv19 = self.liv.copy()
        if A["craft_cap_on"]:
            liv2, conv, to_p, to_w, ex, info = craft_cap(H, W, self.liv)
            self.liv = liv2; self.L = dict(self.L); self.L["liv"] = liv2
            self.conv = dict(any=conv, porter=to_p, labourer=to_w); self.craft_info = info
            A["export_shop"] = ex
        else:
            A["export_shop"] = A["export_shop0"]
            self.conv = dict(any=np.zeros(H.NH, bool), porter=np.zeros(H.NH, bool), labourer=np.zeros(H.NH, bool)); self.craft_info = None
        self.I(("外", "城外田庄"))
        self.fine_role = {}

    def derive(self, yr, S):
        dv = Econ19.derive(self, yr, S); self._dv = dv
        return dv

    def landlords(self, yr, S, dv):
        ll = Econ19.landlords(self, yr, S, dv); self._ll = ll
        return ll

    def _fine_rows(self, yr, R):
        H = self.H; al = yr.alive; dv = self._dv; ll = self._ll
        liv = self.liv[al]
        role = np.zeros(len(al), np.int8)
        if A["fine_on"]:
            fi = np.nonzero(liv == 8)[0]
            llv = ll[al]
            n_rent = np.bincount(llv[llv >= 0], minlength=H.NH)[al] if (llv >= 0).any() else np.zeros(len(al))
            holders = {H.g.get(v[0], -1) for v in yr.holders.values()}
            u = stable_u(H.idnum, 202)
            for i in fi:
                g = int(al[i])
                if n_rent[i] > 0:
                    role[i] = 1
                elif g in holders:
                    role[i] = 2
                elif dv["owner"][i]:
                    role[i] = 3
                elif u[g] < A["p_pension"]:
                    role[i] = 4
                else:
                    role[i] = 5
            X_e, X_i = self.I(("外", "城外田庄")), self.I(("外", "皇库"))
            m3 = np.nonzero(role == 3)[0]; m4 = np.nonzero(role == 4)[0]
            if len(m3):
                R.add("田租(城外田产)", X_e, al[m3], A["fine_estate"],
                      f"体面户·自住有房、无出租、无官职 → 城外田产租（城外田庄净流入 {A['fine_estate']}/户·年；v20 假设，仿城市议员阶层以城外田产为生）", -1, 9)
            if len(m4):
                R.add("年金(皇库)", X_i, al[m4], A["fine_pension"],
                      f"体面户·租住者中 {A['p_pension']:.0%}（散列）→ 年金 / 俸禄遗属，皇库付 {A['fine_pension']}/户·年（v20 假设）", -1, 9)
        self._role = role

    def step(self, yr, S, inc=None):
        if inc is not None:
            if "dv" in inc: self._dv = inc["dv"]
            if "ll" in inc: self._ll = inc["ll"]
        Rows20.pending = lambda R: self._fine_rows(yr, R)
        try:
            out = Econ19.step(self, yr, S, inc)
        finally:
            Rows20.pending = None
        out["fine_role"] = self._role.copy()
        return out


def emit_year20(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
    used = np.unique(np.concatenate([R["a"], R["b"], al]))
    remap = -np.ones(int(used.max()) + 1, np.int64); remap[used] = np.arange(len(used))
    names = [E15.ent_name(E, H, yr, int(e), gone_door) for e in used]
    kind = ["户" if e < H.NH else E.inst_keys[e - H.NH][0] for e in used]
    q = np.round(R["v"] * 1000).astype(np.int64)
    o = np.lexsort((R["b"], R["a"], R["t"]))
    wm = np.isin(R["t"], [TI["工钱"], TI["工钱:港口"]]); pwm = np.isin(R["t"], [TI["公役工钱"], TI["公役工钱(储备库扩招)"], TI["公役工钱(储备库常年)"]]); cm = R["t"] == TI["工钱:零工(码头)"]
    sm = R["t"] == TI["工钱:短工(转业)"]; fm = R["t"] == TI["收购渔获(储备库→近岸渔工)"]
    emp = set(R["b"][wm].tolist()); pws = set(R["b"][pwm].tolist()); cas = set(R["b"][cm].tolist()); shs = set(R["b"][sm].tolist()); fis = set(R["b"][fm].tolist())
    st = [("雇工" if g in emp else "公役" if g in pws else "转业:短工" if g in shs else "转业:渔" if g in fis else "零工" if g in cas else "无工") if E.liv[g] in WORKERS else "" for g in al]
    doc = dict(
        year=yr.Y, _doc="economy_v20 逐年流（列式）。q 为千分之一份；粮类型的份 = 一人一年口粮，其余为折粮的钱。work: 工人户的就业状态；"
                        "craft_conv: 1 = v19 的手工铺因市场节点铺数上限转业（v20）；fine_role: 体面户身份（v20 按户籍可见属性定，见 fine_role_names）。——Hark（刘线）",
        wage_m=int(round(out["wage"] * 1000)), reserve=out["spend"]["reserve"],
        entities=names, entity_kind=kind, types=TYPES, rules=E15.RULES,
        flows=dict(t=R["t"][o].tolist(), a=remap[R["a"][o]].tolist(), b=remap[R["b"][o]].tolist(), q=q[o].tolist(), r=R["r"][o].tolist()),
        households=dict(ent=remap[al].tolist(), house=[H.hid[g] for g in al], livelihood=E.liv[al].tolist(), livelihood_names=LIV,
                        sector=[next((s for s, c in SECTORS.items() if x in c), "其他") for x in E.liv[al]], work=st,
                        craft_conv=E.conv["any"][al].astype(int).tolist(),
                        fine_role=out["fine_role"].tolist(), fine_role_names=FINE_ROLES,
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


# v18 的模块全局改指本目录 / 本类（v18、v19 文件不动）
E18.HERE = HERE
E18.Econ18 = Econ20
E18.emit_year18 = emit_year20
simulate = E18.simulate


def v19_ref():
    r = json.load(open(os.path.join(EXP, "economy_v19", "results.json")))
    s = r["years"]["70"]; lab = s["sector"]["labor"]; x5 = r["sensitivity"]["x0.5"]; x15 = r["sensitivity"]["x1.5"]
    return dict(poor_share=s["poor_share"], poor=s["poor"], poor_share_net=s["poor_share_net"], poor_net=s["poor_net"], gini_net_income=s["gini_net_income"],
                gini_income=s["gini_income"], unfunded=s["unfunded_deficits"], wage=lab["wage"], unemployed_or_casual=lab["rate_unemployed_or_casual"],
                no_work=lab["no_work"], casual=lab["casual"], workers=lab["workers"], public_works=lab["public_works"], treasury=s["treasury"], reserve=s.get("reserve"),
                poor_net_by_livelihood=s["poor_net_by_livelihood"], livelihood_counts=s["livelihood_counts"],
                unemployment_series=r["unemployment_series"],
                sens_x05=dict(unfunded=x5["unfunded_AF70"], unemp=x5["labor_AF70"]["rate_unemployed_or_casual"], poor=x5["poor_share_AF70"],
                              poor_net=x5["poor_share_net_AF70"], gini_net=x5["gini_net_income_AF70"]),
                sens_x15=dict(unfunded=x15["unfunded_AF70"], unemp=x15["labor_AF70"]["rate_unemployed_or_casual"], poor=x15["poor_share_AF70"],
                              poor_net=x15["poor_share_net_AF70"], gini_net=x15["gini_net_income_AF70"]),
                shock_path=r.get("shock_path", {}).get("v19_shock"))


def run():
    o = simulate(1.0, True)
    E, H, per, recon = o["E"], o["H"], o["per"], o["recon"]
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    reg = E.L["first"] >= 0
    res = dict(
        _doc="economy_v20 结果（economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
        craft_cap=E.craft_info,
        livelihood=dict(counts_ever={LIV[i]: int(((E.liv == i) & reg).sum()) for i in range(len(LIV))},
                        counts_ever_v19={LIV[i]: int(((E.liv19 == i) & reg).sum()) for i in range(len(LIV))}),
        years={str(Y): per[Y]["stats"] for Y in per},
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
        v19_AF70=v19_ref(),
        calibration=json.load(open(os.path.join(HERE, "calibration.json"))) if os.path.exists(os.path.join(HERE, "calibration.json")) else None,
    )
    p = os.path.join(HERE, "results.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    for k in ("events", "sensitivity", "events_total_s", "shock_path", "diag"):
        if k in old:
            res[k] = old[k]
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(HERE, "sample_household.txt"), "w") as f:
        f.write("\n\n".join(o["sample"][1][y] for y in sorted(o["sample"][1])))
    pickle.dump(dict(states=o["ev_states"], inst_keys=E.inst_keys), open(os.path.join(HERE, ".cache_states.pkl"), "wb"))
    s70 = per[70]["stats"]
    print(json.dumps(dict(total_s=round(o["t_total"], 1), cons=res["conservation"], craft={k: v for k, v in (E.craft_info or {}).items() if not isinstance(v, (dict, list))},
                          AF70={k: s70[k] for k in ("poor_share", "poor_share_net", "poor_net", "gini_income", "gini_net_income", "unfunded_deficits", "reserve", "poor_net_by_livelihood")},
                          labor=s70["sector"]["labor"], unemp=res["unemployment_series"],
                          reserve_series=o["treas"]["储备库"]), ensure_ascii=False, default=float))


def sens():
    E18.sens()


def events():
    E18.events()


def path():
    nm = sys.argv[2]
    sc = {"v20_shock": {65: 0.3}}
    H = HW(); W = HW15(H)
    o = simulate(1.0, False, H=H, W=W, shock=sc[nm], cls=Econ20)
    row = {}
    for Y in range(63, 71):
        s = o["per"][Y]["stats"]; row[str(Y)] = E18._yr_row(s); row[str(Y)]["reserve_spend"] = {k: s["spend"]["reserve"].get(k) for k in ("level", "remit", "gap", "scale", "n_pw_extra", "n_fish", "n_std", "spent_pw", "spent_relief", "spent_std", "budget")}
    row["checks"] = dict(max_money_err=max(r["conservation_err"] for r in o["recon"]), checks_ok=all(r["grain_ok"] and r["house_tax_ok"] and r["houses_ok"] for r in o["recon"]))
    print(nm, json.dumps({Y: (v["unemp_casual"], v["poor"], v["poor_net"], v["unfunded"], v["reserve"]) for Y, v in row.items() if Y != "checks"}), row["checks"])
    json.dump(row, open(os.path.join(HERE, f".path_{nm}.json"), "w"), ensure_ascii=False, default=float)


def path_merge():
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); out = {}
    f = os.path.join(HERE, ".path_v20_shock.json"); out["v20_shock"] = json.load(open(f)); os.remove(f)
    out["v20_base"] = {str(Y): E18._yr_row(res["years"][str(Y)]) for Y in range(63, 71)}
    v19 = json.load(open(os.path.join(EXP, "economy_v19", "results.json")))["shock_path"]
    for k in ("v19_shock", "v19_base", "v18_shock", "v18_base"):
        out[k] = v19[k]
    res["shock_path"] = out
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)


def _diag_flows(path_):
    d = json.load(gzip.open(path_, "rt"))
    T = d["types"]; F = d["flows"]; t = np.array(F["t"]); a = np.array(F["a"]); b = np.array(F["b"]); v = np.array(F["q"]) / 1000
    NE = len(d["entities"]); TI_ = {x: i for i, x in enumerate(T)}
    mI = ~np.isin(t, [TI_[x] for x in T if TI[x] in GRAIN_T or TI[x] in FIN_T])
    mB = np.isin(t, [TI_[x] for x in E18.BUSINESS_OUT if x in TI_])
    inc = np.bincount(b[mI], v[mI], NE); bo = np.bincount(a[mB], v[mB], NE)
    hh = d["households"]; ent = np.array(hh["ent"]); liv = np.array(hh["livelihood"]); L = hh["livelihood_names"]; work = np.array(hh["work"])
    net = inc[ent] - bo[ent]; poor = net < A["poverty"]
    out = dict(households=len(ent), poor_net=int(poor.sum()), poor_net_share=round(float(poor.mean()), 4), by_livelihood={})
    for c in sorted(set(liv.tolist())):
        m = poor & (liv == c)
        n_ = int(m.sum())
        if not n_:
            out["by_livelihood"][L[c]] = dict(n=0, of=int((liv == c).sum()))
            continue
        ids = ent[m]; sel = np.isin(b, ids) & mI; so = np.isin(a, ids) & mB
        cin = collections.Counter(); cout = collections.Counter()
        for tt, vv in zip(t[sel], v[sel]): cin[T[tt]] += vv
        for tt, vv in zip(t[so], v[so]): cout[T[tt]] += vv
        out["by_livelihood"][L[c]] = dict(n=n_, of=int((liv == c).sum()), median_net=round(float(np.median(net[m])), 2),
                                          income_per_hh={k: round(x / n_, 2) for k, x in cin.most_common(6)},
                                          business_out_per_hh={k: round(x / n_, 2) for k, x in cout.most_common(4)},
                                          work=dict(collections.Counter(work[m].tolist())) if c in (0, 1) else None)
    out["workers_by_status"] = {w: dict(n=int(((liv == 0) & (work == w)).sum()), poor_net=int((poor & (liv == 0) & (work == w)).sum())) for w in sorted(set(work[liv == 0].tolist()))}
    # 手工铺本城卖货 / 户
    sold = np.bincount(b[t == TI_["买卖:手工"]], v[t == TI_["买卖:手工"]], NE)
    m3 = liv == 3
    out["shop_local_sales"] = dict(mean=round(float(sold[ent[m3]].mean()), 2), median=round(float(np.median(sold[ent[m3]])), 2), n=int(m3.sum()))
    # 体面户：户籍可见属性
    m8 = liv == 8
    own = np.array(hh["houses_owned"]); lls = np.array(hh["landlord"]); src = np.array(hh["lh_src"])
    rent_in = np.bincount(b[t == TI_["租金"]], v[t == TI_["租金"]], NE)
    hold_ = np.bincount(b[np.isin(t, [TI_[x] for x in ("俸给", "官俸(坊长/区长)") if x in TI_])], v[np.isin(t, [TI_[x] for x in ("俸给", "官俸(坊长/区长)") if x in TI_])], NE)
    fine = dict(n=int(m8.sum()), owner_occupier=int((m8 & (own >= 1) & (lls < 0)).sum()) if False else None,
                houses_owned=dict(collections.Counter(own[m8].tolist())), tenants=int((m8 & (lls >= 0)).sum()),
                with_rent_income=int((m8 & (rent_in[ent] > 0)).sum()), with_stipend=int((m8 & (hold_[ent] > 0)).sum()),
                lh_src={hh["lh_src_names"][k]: int(c) for k, c in collections.Counter(src[m8].tolist()).items()},
                poor_net=int((m8 & poor).sum()))
    if "fine_role" in hh:
        fr = np.array(hh["fine_role"]); nm_ = hh["fine_role_names"]
        fine["by_role"] = {nm_[r]: dict(n=int((m8 & (fr == r)).sum()), poor_net=int((m8 & (fr == r) & poor).sum()),
                                        median_net=round(float(np.median(net[m8 & (fr == r)])), 2) if (m8 & (fr == r)).any() else None) for r in range(1, len(nm_))}
    out["fine"] = fine
    if "craft_conv" in hh:
        cv = np.array(hh["craft_conv"]) == 1
        out["converted_AF70"] = dict(n=int(cv.sum()), by_livelihood={L[c]: int((cv & (liv == c)).sum()) for c in set(liv[cv].tolist())},
                                     work=dict(collections.Counter(work[cv].tolist())), poor_net=int((cv & poor).sum()))
    return out


def diag():
    r = dict(v19=_diag_flows(os.path.join(EXP, "economy_v19", "flows_AF70.json.gz")), v20=_diag_flows(os.path.join(HERE, "flows_AF70.json.gz")))
    p = os.path.join(HERE, "results.json"); res = json.load(open(p)); res["diag"] = r
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "sens": sens, "events": events, "path": path, "path_merge": path_merge, "diag": diag}[sys.argv[1]]()
