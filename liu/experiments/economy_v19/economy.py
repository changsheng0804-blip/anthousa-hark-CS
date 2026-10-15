# -*- coding: utf-8 -*-
"""economy_v19：缓冲的退出与上限——触发后逐年递减延续（接住 AF66 余震）、按就业缺口定扩招规模、
关税蠲免改为部分（≤50%）且有年限（连续 ≤3 年，之后间隔 2 年）、储备不足时公役 / 救济按比例缩减、
储备库满额时的常年小额公役（只雇「无工」户，针对 AF70 净收入贫困的主因）。
地下数据管线，不做页面。——Hark（刘线）

按路径只读载入（不改）：
  ../economy_v18/economy.py（Econ18、State18、simulate、events、sens_one；经它再载入 v17…v7、v12）
  v18 的 HERE / Econ18 / emit_year18 三个模块全局在运行时指向本目录与本类，v18 文件一个字节都不动。
运行：python3 economy.py run            # 基准 AF40–70 + 输出（≈50 s）
      python3 economy.py sens 0.5 & python3 economy.py sens 1.5; python3 economy.py sens merge
      python3 economy.py events         # 5 个事件：增量 == 重建（需先 run）
      python3 economy.py path v19_shock # 骤降路径：AF65 到港 ×0.3 一年（v18 / v17 路径取自 ../economy_v18/results.json）
      python3 economy.py path_merge
      python3 economy.py diag           # AF70 净收入贫困户诊断（v18 与 v19 的 flows_AF70）
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


E18 = _load("economy_v18_for_v19", os.path.join(EXP, "economy_v18", "economy.py"))
for _k, _v in list(vars(E18).items()):
    if not _k.startswith("__") and _k not in ("HERE", "EXP", "_load", "run", "sens", "sens_one", "events", "path", "path_merge", "arian", "emit_year18", "v17_ref"):
        globals()[_k] = _v
E15, E17 = E18.E15, E18.E17
Econ18 = E18.Econ18      # 原类（下面模块全局会被改指 Econ19，显式调用一律用这个引用）

NEW_T19 = ["公役工钱(储备库常年)"]
for t in NEW_T19:
    if t not in E15.TI:
        E15.TI[t] = len(E15.TYPES); E15.TYPES.append(t)
TYPES, TI = E15.TYPES, E15.TI

A = E18.A
A.update(
    # ---- 1 触发后延续、逐年递减（触发年 = 1.0）
    taper=[1.0, 0.75, 0.4],   # 触发年、次年、第三年的缓冲强度；之后退出（到港仍低就重新触发，从 1.0 开始）
    u_floor=0.08,             # 扩招只补到「剩余无工 + 零工候选 ≤ 8% × 工人」为止（按就业缺口定规模，不再一律吸到 45%）
    # ---- 2 关税蠲免：部分、有年限
    res_remit=0.5,            # 触发年蠲免关税上解 50%（v18 为 100%）
    remit_years=3,            # 连续蠲免最多 3 年
    remit_gap=2,              # 之后须间隔 2 年（这两年即使触发也不蠲免）
    # ---- 3 常年小额公役（平年；储备库满额附近才动用）
    std_on=True,
    std_cap=0.04,             # ≤ 4% × 工人
    std_floor=0.9,            # 只动用库存超过 90% × 上限（18,000）的部分：冲击缓冲优先
)
if os.environ.get("V19_OVR"):
    A.update(json.loads(os.environ["V19_OVR"]))
BUF0 = dict(since=None, remit_run=0, gap_left=0)


class State19(E18.State18):
    def copy(self):
        s = E18.State18.copy(self)
        s.__class__ = State19
        s.buf = dict(getattr(self, "buf", BUF0))
        return s


class Econ19(Econ18):
    def step(self, yr, S, inc=None):
        if not A["buffer_on"]:
            return Econ18.step(self, yr, S, inc)
        buf = dict(getattr(S, "buf", BUF0))
        ships = self.ships(yr)
        trig = bool(ships < A["res_trig"] * A["ships_base"]) and not getattr(self, "boot", False)
        nb = dict(buf)
        remit = 0.0
        if trig:
            since = 0
            if buf["gap_left"] > 0:
                nb["gap_left"] = buf["gap_left"] - 1
            else:
                remit = A["res_remit"]; nb["remit_run"] = buf["remit_run"] + 1
                if nb["remit_run"] >= A["remit_years"]:
                    nb["remit_run"] = 0; nb["gap_left"] = A["remit_gap"]
        else:
            since = (buf["since"] + 1) if buf["since"] is not None else None
            nb["remit_run"] = 0; nb["gap_left"] = max(0, buf["gap_left"] - 1)
        level = A["taper"][since] if since is not None and since < len(A["taper"]) else 0.0
        nb["since"] = since if (since is not None and since + 1 < len(A["taper"])) else (since if trig else None)
        self._cur = dict(trig=trig, level=level, since=since, remit=remit)
        old = A["res_remit"]; A["res_remit"] = remit
        try:
            out = Econ18.step(self, yr, S, inc)
        finally:
            A["res_remit"] = old
        out["buf_next"] = nb
        out["spend"]["reserve"].update(level=level, since=since, remit=remit, remit_run=nb["remit_run"], gap_left=nb["gap_left"])
        return out

    def advance(self, yr, S, out):
        S2, inc, exp = Econ18.advance(self, yr, S, out)
        S2.__class__ = State19
        S2.buf = dict(out.get("buf_next", BUF0))
        return S2, inc, exp

    def init_state(self):
        S = Econ18.init_state(self)
        S.__class__ = State19; S.buf = dict(BUF0)
        return S

    # ------------------------------------------------------------------ v19 冲击块：强度 level、按缺口定规模、按比例缩减
    def shock_block(self, trig, yr, S, dv, liv, al, n, un, pw_set, unf_d, wage, N_w, cnow, RES, EP, R5, pos_of, n_pw):
        H = self.H; cur = self._cur; lvl = cur["level"]; trig = cur["trig"]
        assigned = pw_set.copy()
        out = dict(assigned=assigned, casual_set=np.zeros(n, bool), n_pw_extra=0, n_fish=0, n_craft=0, n_std=0, budget=0.0,
                   spent_pw=0.0, spent_fish=0.0, spent_relief=0.0, spent_taxrelief=0.0, spent_std=0.0, n_relief=0, n_taxrelief=0,
                   gap=0, scale=1.0, res_cash=round(float(cnow[RES]), 2))
        if lvl <= 0:
            out["budget_left"] = 0.0
            return out
        budget = A["res_spend"] * max(0.0, float(cnow[RES]))
        out["budget"] = budget
        nh = len(self.W.harbors)
        wmin = np.min(dv["walk"][:, :nh], 1)
        rem = un[~assigned[un]]
        gap = max(0, len(rem) - int(A["u_floor"] * N_w)); out["gap"] = gap
        want = int(round(lvl * gap))                    # 本年要吸收的人数（缺口 × 强度）
        # ① 手工 / 营造短工（仅触发年；v18 规则，各档都是 0）
        cap_c = int(A["tr_craft_cap"] * N_w) if trig else 0
        u_ = rem[np.argsort(dv["door_rank"][rem], kind="stable")]
        if len(unf_d) and len(u_) and cap_c > 0 and want > 0:
            SX = H.xy[al[unf_d]]; free = np.ones(len(unf_d), bool); a2, b2 = [], []
            for i in u_:
                if len(a2) >= min(cap_c, want) or not free.any():
                    break
                d2 = np.hypot(*(SX - H.xy[al[i]]).T); d2[~free] = np.inf
                j = int(np.argmin(d2)); free[j] = False
                a2.append(al[unf_d[j]]); b2.append(al[i]); assigned[i] = True
            if a2:
                R5.add("工钱:短工(转业)", np.array(a2), np.array(b2), wage, f"冲击转业①：剩余无工者补区内剩余工位，≤{A['tr_craft_cap']:.0%}×工人（v18 规则）", -1, 5)
                out["n_craft"] = len(a2); want -= len(a2)
        # 计划：近岸渔（仅触发年）+ 公役扩招 + 救济估计，预算不足时三者同比例缩减
        pay_f = A["fish_pay"] * wage
        cand_f = rem[~assigned[rem] & (wmin[rem] <= A["R_walk"])]; cand_f = cand_f[np.argsort(dv["door_rank"][cand_f], kind="stable")]
        kf = int(min(len(cand_f), A["fish_cap"] * int((liv == 16).sum()), max(0, want))) if trig else 0
        kp = int(min(max(0, want - kf), max(0, int(A["pw_cap"] * N_w) - n_pw)))
        left_est = len(rem) - out["n_craft"] - kf - kp
        relief_est = lvl * A["relief_nowork"] * max(0, left_est)
        cost = kf * pay_f + kp * wage + relief_est
        f_ = min(1.0, budget / cost) if cost > 0 else 1.0
        out["scale"] = round(f_, 4)
        kf = int(kf * f_); kp = int(kp * f_)
        if kf > 0:
            pk = cand_f[:kf]; assigned[pk] = True
            R5.add("收购渔获(储备库→近岸渔工)", RES, al[pk], pay_f,
                   f"冲击转业②：近岸渔业（港边无工者，每户渔户带 ≤{A['fish_cap']:.0f} 人），储备库按 {A['fish_pay']:.0%}×工钱 收购渔获（v18 规则；v19 计入缺口、预算不足同比例缩）", -1, 5)
            out["n_fish"] = kf; out["spent_fish"] = kf * pay_f; budget -= kf * pay_f
        u_ = un[~assigned[un]]; u_ = u_[np.argsort(dv["door_rank"][u_], kind="stable")]
        kp = min(kp, len(u_), int(budget // wage))
        if kp > 0:
            pk = u_[:kp]; assigned[pk] = True
            R5.add("公役工钱(储备库扩招)", RES, al[pk], wage,
                   f"冲击：储备库公役扩招，人数 = 强度 {lvl:.2f} × 就业缺口（剩余无工 − {A['u_floor']:.0%}×工人），常年 + 扩招 ≤{A['pw_cap']:.0%}×工人；触发后逐年递减 {A['taper']}；预算不足与救济同比例缩（v19 假设）", -1, 5)
            out["n_pw_extra"] = kp; out["spent_pw"] = kp * wage; budget -= kp * wage
        out["budget_left"] = budget
        return out

    def relief_block(self, shock, trig, dv, liv, al, un, R5, RES, P4):
        cur = self._cur; lvl = cur["level"]
        nowork = un[~shock["assigned"][un] & ~shock["casual_set"][un]]
        if lvl <= 0:
            # 平年：常年小额公役——只雇「无工」户（既无工位、也没轮到公役和码头零工），储备库只动用超过 std_floor × 上限的部分
            if not A["std_on"] or not len(nowork):
                return
            N_w = int(np.isin(liv, WORKERS).sum())
            wage = self._wage_now
            bud = max(0.0, shock["res_cash"] - A["std_floor"] * A["res_cap"])
            k_ = int(min(len(nowork), A["std_cap"] * N_w, bud // wage))
            if k_ > 0:
                pk = nowork[np.argsort(dv["door_rank"][nowork], kind="stable")][:k_]
                shock["assigned"][pk] = True
                R5.add("公役工钱(储备库常年)", RES, al[pk], wage,
                       f"平年常年小额公役：储备库库存超过 {A['std_floor']:.0%}×上限 的部分，雇「无工」户（不含码头零工），≤{A['std_cap']:.0%}×工人，门牌序，工钱 = 当年出清工钱（v19 假设，仿城市以本地收入修城墙街渠）", -1, 5)
                shock["n_std"] = k_; shock["spent_std"] = k_ * wage; shock["n_pw_extra"] += k_
            return
        budget = shock["budget_left"]
        cas = un[shock["casual_set"][un]]
        rn, rc = lvl * A["relief_nowork"], lvl * A["relief_casual"]
        need = len(nowork) * rn + len(cas) * rc
        f_ = min(1.0, budget / need) if need > 0 else 0.0
        if f_ > 0:
            if len(nowork):
                R5.add("救济(平价粮)", RES, al[nowork], rn * f_, f"冲击：储备库平价 / 救济粮折钱，无工户 {A['relief_nowork']:.1f} × 强度 {lvl:.2f}（预算不足按比例缩；v19）", -1, 5)
            if len(cas):
                R5.add("救济(平价粮)", RES, al[cas], rc * f_, f"冲击：储备库平价 / 救济粮折钱，只有码头零工的户 {A['relief_casual']:.1f} × 强度 {lvl:.2f}（v19）", -1, 5)
            sp = need * f_; budget -= sp
            shock["spent_relief"] = sp; shock["n_relief"] = int(len(nowork) + len(cas)); shock["relief_scale"] = round(f_, 4)
        if A["tax_relief"] and budget > 0:
            ow = un[dv["owner"][un]]
            k_ = int(min(len(ow), budget // P4["tau"]))
            if k_ > 0:
                ow = ow[np.argsort(dv["door_rank"][ow], kind="stable")][:k_]
                R5.add("房税减免(储备库代缴)", RES, al[ow], P4["tau"], "冲击：无正式工位的自住房主户，当年房税由储备库代缴（v18 规则）", -1, 5)
                shock["spent_taxrelief"] = k_ * P4["tau"]; shock["n_taxrelief"] = k_; budget -= k_ * P4["tau"]
        shock["budget_left"] = budget


# relief_block 需要当年工钱：shock_block 收到 wage，记下来
_sb = Econ19.shock_block
def _shock_block(self, trig, yr, S, dv, liv, al, n, un, pw_set, unf_d, wage, *a):
    self._wage_now = wage
    return _sb(self, trig, yr, S, dv, liv, al, n, un, pw_set, unf_d, wage, *a)
Econ19.shock_block = _shock_block


def emit_year19(E, H, yr, R, al, income, expense, cash, nw, owned, out, gone_door, pay):
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
        year=yr.Y, _doc="economy_v19 逐年流（列式）。q 为千分之一份；粮类型的份 = 一人一年口粮，其余为折粮的钱。work: 工人户的就业状态（雇工/公役/转业/零工/无工；公役含常年、扩招、储备库常年小额）；wage_m = 当年出清工钱×1000。——Hark（刘线）",
        wage_m=int(round(out["wage"] * 1000)), reserve=out["spend"]["reserve"],
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


# v18 的模块全局改指本目录 / 本类（v18 文件不动）
E18.HERE = HERE
E18.Econ18 = Econ19
E18.emit_year18 = emit_year19
simulate = E18.simulate


def v18_ref():
    r = json.load(open(os.path.join(EXP, "economy_v18", "results.json")))
    s = r["years"]["70"]; lab = s["sector"]["labor"]; x5 = r["sensitivity"]["x0.5"]
    ev = r.get("events", {}).get("ships_drop65", {})
    return dict(poor_share=s["poor_share"], poor=s["poor"], poor_share_net=s["poor_share_net"], poor_net=s["poor_net"], gini_net_income=s["gini_net_income"],
                gini_income=s["gini_income"], unfunded=s["unfunded_deficits"], wage=lab["wage"], unemployed_or_casual=lab["rate_unemployed_or_casual"],
                public_works=lab["public_works"], treasury=s["treasury"], reserve=s.get("reserve"), poor_net_by_livelihood=s["poor_net_by_livelihood"],
                unemployment_series=r["unemployment_series"],
                ships_drop65_unemployed_or_casual=ev.get("labor", {}).get("unemployed_or_casual_rate"), ships_drop65_poor=(ev.get("poor_cf"), ev.get("poor_ev")),
                sens_x05=dict(unfunded=x5["unfunded_AF70"], unemp=x5["labor_AF70"]["rate_unemployed_or_casual"], poor=x5["poor_share_AF70"],
                              poor_net=x5["poor_share_net_AF70"], gini_net=x5["gini_net_income_AF70"], reserve_series=x5.get("reserve_series")),
                shock_path=r.get("shock_path"))


def run():
    o = simulate(1.0, True)
    E, H, per, recon = o["E"], o["H"], o["per"], o["recon"]
    with open(os.path.join(HERE, "ledger_reconcile.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon[0].keys())); w.writeheader(); w.writerows(recon)
    res = dict(
        _doc="economy_v19 结果（economy.py run 写出）——Hark（刘线）",
        params=dict(v4=P4, v0_landlord=LL, v0_debt=DEBT, new=A),
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
        v18_AF70=v18_ref(),
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
    print(json.dumps(dict(total_s=round(o["t_total"], 1), cons=res["conservation"],
                          AF70={k: s70[k] for k in ("poor_share", "poor_share_net", "poor_net", "gini_income", "gini_net_income", "unfunded_deficits", "reserve", "poor_net_by_livelihood")},
                          labor=s70["sector"]["labor"], reserve70=s70["spend"]["reserve"], unemp=res["unemployment_series"],
                          reserve_series=o["treas"]["储备库"]), ensure_ascii=False, default=float))


def sens():
    E18.sens()


def events():
    E18.events()


def path():
    nm = sys.argv[2]
    sc = {"v19_shock": {65: 0.3}}
    H = HW(); W = HW15(H)
    o = simulate(1.0, False, H=H, W=W, shock=sc[nm], cls=Econ19)
    row = {}
    for Y in range(63, 71):
        s = o["per"][Y]["stats"]; row[str(Y)] = E18._yr_row(s); row[str(Y)]["reserve_spend"] = {k: s["spend"]["reserve"].get(k) for k in ("level", "remit", "gap", "scale", "n_pw_extra", "n_fish", "n_std", "spent_pw", "spent_relief", "spent_std", "budget")}
    print(nm, json.dumps({Y: (v["unemp_casual"], v["poor"], v["poor_net"], v["unfunded"], v["reserve"]) for Y, v in row.items()}))
    json.dump(row, open(os.path.join(HERE, f".path_{nm}.json"), "w"), ensure_ascii=False, default=float)


def path_merge():
    p = os.path.join(HERE, "results.json")
    res = json.load(open(p)); out = {}
    f = os.path.join(HERE, ".path_v19_shock.json"); out["v19_shock"] = json.load(open(f)); os.remove(f)
    out["v19_base"] = {str(Y): E18._yr_row(res["years"][str(Y)]) for Y in range(63, 71)}
    v18 = json.load(open(os.path.join(EXP, "economy_v18", "results.json")))["shock_path"]
    for k in ("v18_shock", "v18_base", "v17_shock", "v17_base"):
        out[k] = v18[k]
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
    for c in sorted(set(liv[poor].tolist())):
        m = poor & (liv == c)
        ids = ent[m]; sel = np.isin(b, ids) & mI; so = np.isin(a, ids) & mB
        cin = collections.Counter(); cout = collections.Counter()
        for tt, vv in zip(t[sel], v[sel]): cin[T[tt]] += vv
        for tt, vv in zip(t[so], v[so]): cout[T[tt]] += vv
        n_ = int(m.sum())
        out["by_livelihood"][L[c]] = dict(n=n_, of=int((liv == c).sum()), median_net=round(float(np.median(net[m])), 2),
                                          income_per_hh={k: round(x / n_, 2) for k, x in cin.most_common(6)},
                                          business_out_per_hh={k: round(x / n_, 2) for k, x in cout.most_common(4)},
                                          work=dict(collections.Counter(work[m].tolist())) if c == 0 else None)
    out["workers_by_status"] = {w: dict(n=int(((liv == 0) & (work == w)).sum()), poor_net=int((poor & (liv == 0) & (work == w)).sum())) for w in sorted(set(work[liv == 0].tolist()))}
    return out


def diag():
    r = dict(v18=_diag_flows(os.path.join(EXP, "economy_v18", "flows_AF70.json.gz")), v19=_diag_flows(os.path.join(HERE, "flows_AF70.json.gz")))
    p = os.path.join(HERE, "results.json"); res = json.load(open(p)); res["diag"] = r
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "sens": sens, "events": events, "path": path, "path_merge": path_merge, "diag": diag}[sys.argv[1]]()
