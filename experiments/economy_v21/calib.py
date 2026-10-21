# -*- coding: utf-8 -*-
"""标定：V21_OVR 覆盖参数，跑 基准 / AF65 骤降路径 / 到港 ×0.5，只记关键数（不写 flows）。python3 calib.py <组名> <base|path|x05> ——Hark（刘线）"""
import os, sys, json
import importlib.util
sp = importlib.util.spec_from_file_location("v21", os.path.join(os.path.dirname(os.path.abspath(__file__)), "economy.py"))
m = importlib.util.module_from_spec(sp); sys.modules["v21"] = m; sp.loader.exec_module(m)
g, kind = sys.argv[1], sys.argv[2]
mult, shock = (0.5, None) if kind == "x05" else (1.0, ({65: 0.3} if kind == "path" else None))
o = m.simulate(mult, False, shock=shock)
P = o["per"]; lab = lambda Y: P[Y]["stats"]["sector"]["labor"]
yrs = range(63, 71)
r = dict(group=g, kind=kind, ovr=json.loads(os.environ.get("V21_OVR", "{}")),
         unemp={Y: lab(Y)["rate_unemployed_or_casual"] for Y in yrs},
         poor_net={Y: P[Y]["stats"]["poor_net"] for Y in yrs}, poor={Y: P[Y]["stats"]["poor"] for Y in yrs},
         shops={Y: P[Y]["stats"]["livelihood_counts"].get("手工铺", 0) for Y in P},
         exits=sum(v["exits"] for v in o["E"].dyn_log.values()), entries=sum(v["entries"] for v in o["E"].dyn_log.values()),
         dyn={Y: o["E"].dyn_log.get(Y) for Y in yrs},
         AF70=dict(poor_share_net=P[70]["stats"]["poor_share_net"], poor_share=P[70]["stats"]["poor_share"], gini_net=P[70]["stats"]["gini_net_income"],
                   unemp=lab(70)["rate_unemployed_or_casual"], unfunded=P[70]["stats"]["unfunded_deficits"], poor_net_by_livelihood=P[70]["stats"]["poor_net_by_livelihood"]),
         reserve_AF70=o["treas"]["储备库"][-1],
         cons=max(x["conservation_err"] for x in o["recon"]), checks=all(x["grain_ok"] and x["house_tax_ok"] and x["houses_ok"] for x in o["recon"]))
json.dump(r, open(os.path.join("/tmp", f"calib21_{g}_{kind}.json"), "w"), ensure_ascii=False, default=float)
print(g, kind, json.dumps(r["AF70"], ensure_ascii=False), "shops70", r["shops"][70], "exits", r["exits"], "entries", r["entries"],
      "unemp63-70", [round(r["unemp"][Y], 3) for Y in yrs], "poornet", list(r["poor_net"].values()), r["cons"] < 1e-6 and r["checks"])
