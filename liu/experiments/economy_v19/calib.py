# -*- coding: utf-8 -*-
"""标定：V19_OVR 覆盖参数，跑 基准 / AF65 骤降路径 / 到港 ×0.5，只记关键数（不写 flows）。python3 calib.py <组名> <base|path|x05> ——Hark（刘线）"""
import os, sys, json
import importlib.util
sp = importlib.util.spec_from_file_location("v19", os.path.join(os.path.dirname(os.path.abspath(__file__)), "economy.py"))
m = importlib.util.module_from_spec(sp); sys.modules["v19"] = m; sp.loader.exec_module(m)
g, kind = sys.argv[1], sys.argv[2]
mult, shock = (0.5, None) if kind == "x05" else (1.0, ({65: 0.3} if kind == "path" else None))
o = m.simulate(mult, False, shock=shock)
P = o["per"]; lab = lambda Y: P[Y]["stats"]["sector"]["labor"]
r = dict(group=g, kind=kind, ovr=json.loads(os.environ.get("V19_OVR", "{}")),
         unemp={Y: lab(Y)["rate_unemployed_or_casual"] for Y in range(63, 71)},
         poor_net={Y: P[Y]["stats"]["poor_net"] for Y in range(63, 71)}, poor={Y: P[Y]["stats"]["poor"] for Y in range(63, 71)},
         AF70=dict(poor_share_net=P[70]["stats"]["poor_share_net"], poor_share=P[70]["stats"]["poor_share"], gini_net=P[70]["stats"]["gini_net_income"],
                   unfunded=P[70]["stats"]["unfunded_deficits"]),
         reserve_max=max(o["treas"]["储备库"]), reserve_AF70=o["treas"]["储备库"][-1],
         cons=max(x["conservation_err"] for x in o["recon"]), checks=all(x["grain_ok"] and x["house_tax_ok"] and x["houses_ok"] for x in o["recon"]))
json.dump(r, open(os.path.join("/tmp", f"calib_{g}_{kind}.json"), "w"), ensure_ascii=False)
print(json.dumps(r, ensure_ascii=False))
