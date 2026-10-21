# -*- coding: utf-8 -*-
"""surface_v23 房况存量敏感性：折旧基数 0.6（主）/0.45/0.3 × 初值下限 0.85（主）/0.95，AF70 干山与全城四档、AF64→65 跳变。输出 sens.json。——Hark（刘线）"""
import os, json, collections, importlib.util
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location("s23", os.path.join(HERE, "surface.py")); S = importlib.util.module_from_spec(sp); sp.loader.exec_module(S)
S22 = S.S22
H = S22.ledger_world()
lb = {int(h[1:]): int(b) for h, b in zip(H.hid, H.built) if h.startswith("h")}
ld = {int(h[1:]): int(x) for h, x in zip(H.hid, H.dest) if h.startswith("h")}
PH = json.load(open(os.path.join(S.PAGE, "houses.json")))
page = set(r[0] for r in PH["houses"]) | set(r[0] for r in PH.get("ledger_new", []))
RS = {}
for Y in S.YEARS:
    d, T, TI, F, Hh, N, NT = S22.load_flows(os.path.join(S.PATH, f"flows_AF{Y}.json.gz"))
    q = F["q"] / 1000.0; m = F["t"] == TI["修房(付营造)"]
    rep = np.bincount(F["a"][m], q[m], NT)[:N]
    ll = S22.remap_ll(Hh, np.asarray(Hh["landlord"])); own = np.asarray(Hh["houses_owned"])
    owner = np.where(ll >= 0, ll, np.arange(N))
    RS[Y] = dict(zip([int(h[1:]) for h in Hh["house"]], (rep[owner] / np.maximum(own[owner], 1)).tolist()))
out = {}
for wb in (0.6, 0.45, 0.3):
    for fl in (0.85, 0.95):
        C = {}; st = {}
        for Y in S.YEARS:
            cur = {}
            for h, b in lb.items():
                if not (b <= Y < ld[h]):
                    continue
                age = Y - b
                if h not in C:
                    C[h] = S.V_H if b >= Y or b >= 40 else S.V_H * max(fl, 1 - 0.003 * max(age, 0))
                c0 = C[h]
                w = wb / S.WEAR_BASE * float(S.wear(np.array(age), np.array(c0))) if b < Y else 0.0
                C[h] = min(S.V_H, max(0.0, c0 - w + RS[Y].get(h, 0.0)))
                cur[h] = int(S.state(np.array(C[h])))
            st[Y] = cur
        a, b_ = st[64], st[65]
        com = [h for h in page if h in a and h in b_]
        dist = lambda Y, hs: {S22.MAINT[k]: v for k, v in sorted(collections.Counter(st[Y][h] for h in hs if h in st[Y]).items())}
        out[f"wear{wb}_init{fl}"] = dict(AF70_page=dist(70, page), AF70_city=dist(70, st[70].keys()), AF60_page=dist(60, page),
                                         jump64_65_page=sum(1 for h in com if a[h] != b_[h]))
        print(wb, fl, json.dumps(out[f"wear{wb}_init{fl}"], ensure_ascii=False), flush=True)
json.dump(out, open(os.path.join(HERE, "sens.json"), "w"), ensure_ascii=False, indent=1)
