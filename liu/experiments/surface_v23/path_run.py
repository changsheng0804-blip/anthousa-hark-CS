# -*- coding: utf-8 -*-
"""surface_v23 辅助：按路径只读载入 economy_v21/economy.py，跑与 surface_v22 相同的到港骤降路径（AF65 到港 ×0.3），
但把 AF40–70 每一年的逐户流都写到本目录 .path/（不入库；economy_v21 目录不写任何文件）。房屋维护存量要逐年的修房流。——Hark（刘线）"""
import os, sys, importlib.util, time
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.dirname(HERE)
OUT = os.path.join(HERE, ".path"); os.makedirs(OUT, exist_ok=True)
sp = importlib.util.spec_from_file_location("economy_v21_ro", os.path.join(EXP, "economy_v21", "economy.py"))
M = importlib.util.module_from_spec(sp); sys.modules["economy_v21_ro"] = M; sys.path.insert(0, os.path.join(EXP, "economy_v21")); sp.loader.exec_module(M)
for m in (M.E18, M.E19, M.E20):
    m.HERE = OUT
M.E18.SNAP = tuple(range(40, 71))
t = time.time()
H = M.HW(); W = M.HW15(H)
o = M.simulate(1.0, True, H=H, W=W, shock={65: 0.3}, cls=M.Econ21)
print("done", round(time.time() - t, 1))
