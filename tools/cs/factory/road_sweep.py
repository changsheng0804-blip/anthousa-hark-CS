#!/usr/bin/env python3
"""/goal 4 G5 道路终扫（派生表 streets.json）。谭线 HANDOFF 第 4 节的 prune_islands，改成 CS 的「先接、接不上才收」：
 在 30..155 年每 5 年各查一次：在世的小巷/院巷（l、c）连成一片、不碰大街/街（m、s）、不出框边（出框的在邻块接上）= 孤岛。
 · 连通：两段中线相距 ≤ 4 px 算连（街面本来就压着，肉眼是通的）；
 · 孤岛离最近的在世街 ≤ 32 px 且连线 全程是陆地、不压当年在世的房、不穿史诗脚印 → 补一小段「接线」（l，宽 5，记号 s[9]='link'）；
 · 接不上的 → 收：孤岛的年份是开头一段就把开始年推到第一个通的年份，否则把结束年定在第一个孤岛年（记号 s[9]=['prune', 原始年]）。
 不改世界数据；史诗清场、房不压路由 check_epic_clear / check_roads 管。幂等：先撤自己上一次的记号（undo）再做。——Hark（CS线）"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import landmarks_city as L
import numpy as np
from PIL import Image
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree
from shapely.ops import nearest_points
import shapely
YEARS = list(range(30, 156, 5)); TOL = 2.0; MAXGAP = 32.0; SKIP = {'district', 'farmland', 'wall', 'gate', 'harbor'}
def undo(ST):
    out = []
    for s in ST:
        if len(s) > 9 and s[9] == 'link': continue
        if len(s) > 9 and isinstance(s[9], list) and s[9][0] == 'prune': s[6], s[7], s[8] = s[9][1], s[9][2], s[9][3]; del s[9:]
        out.append(s)
    ST[:] = out
def alive(s, Y): return s[6] <= Y and not (s[7] and s[7] <= Y)
def islands(ST, FW, FH):
    """→ {年: [[seg 下标…], …]}"""
    res = {}
    for Y in YEARS:
        idx = [i for i, s in enumerate(ST) if alive(s, Y)]
        Ls = [LineString([(ST[i][0], ST[i][1]), (ST[i][2], ST[i][3])]).buffer(TOL) for i in idx]
        T = STRtree(Ls); par = list(range(len(idx)))
        def f(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        for a, l in enumerate(Ls):
            for b in T.query(l):
                if b != a and l.intersects(Ls[b]): par[f(a)] = f(b)
        comp = {}
        for a in range(len(idx)): comp.setdefault(f(a), []).append(idx[a])
        for ids in comp.values():
            if any(ST[i][5] in ('m', 's') for i in ids): continue
            if any(min(ST[i][0], ST[i][2]) < 14 or max(ST[i][0], ST[i][2]) > FW - 14 or min(ST[i][1], ST[i][3]) < 14 or max(ST[i][1], ST[i][3]) > FH - 14 for i in ids): continue
            res.setdefault(Y, []).append(sorted(ids))
    return res
def main(quiet=False):
    EP = [(Polygon(e['geom']['coords']).buffer(0), e['built'], e['destroyed'] if e['destroyed'] is not None else 9999) for e in L.W['structures'] if e['geom']['type'] == 'polygon' and e['type'] not in SKIP]
    rep = {}
    for q in L.QS:
        p = os.path.join(L.LIV, q, 'streets.json'); ST = json.load(open(p)); undo(ST)
        HS = json.load(open(os.path.join(L.LIV, q, 'houses_street.json')))['houses']
        fr = json.load(open(os.path.join(L.LIV, q, 'frame.json'))); FW, FH = fr['frame'][2] * fr['scale'], fr['frame'][3] * fr['scale']
        gk = sorted(int(f[7:-4]) for f in os.listdir(os.path.join(L.LIV, q)) if f.startswith('ground_') and f[7:-4].lstrip('-').isdigit())
        G = np.asarray(Image.open(os.path.join(L.LIV, q, f'ground_{gk[-1]}.jpg')).convert('RGB')).astype(int)
        land = lambda x, y: 0 <= int(y) < G.shape[0] and 0 <= int(x) < G.shape[1] and (G[int(y), int(x), 1] - G[int(y), int(x), 0]) <= 15
        HP = [(Polygon([(h[4][i], h[4][i + 1]) for i in range(0, 8, 2)]).buffer(0), h[2], h[3]) for h in HS if h[3] > h[2]]
        HT = STRtree([x[0] for x in HP])
        nlink = nprune = 0
        for rnd in range(4):
            isl = islands(ST, FW, FH)
            if not isl: break
            # 每个孤岛（按 Y 的第一次出现）：试接线
            done = set(); added = 0
            for Y in sorted(isl):
                for ids in isl[Y]:
                    key = ids[0]
                    if key in done: continue
                    done.add(key)
                    U = shapely.union_all([LineString([(ST[i][0], ST[i][1]), (ST[i][2], ST[i][3])]) for i in ids])
                    rest = [(j, LineString([(s[0], s[1]), (s[2], s[3])])) for j, s in enumerate(ST) if j not in ids and alive(s, Y) and not (len(s) > 9 and s[9] == 'link' and False)]
                    if not rest: continue
                    j, tl = min(rest, key=lambda r: U.distance(r[1]))
                    d = U.distance(tl)
                    if d > MAXGAP: continue
                    a, b = nearest_points(U, tl); lk = LineString([a, b])
                    n = max(2, int(lk.length / 3)); wet = any(not land(*lk.interpolate(k / n, normalized=True).coords[0]) for k in range(n + 1))
                    if wet: continue
                    b0 = max(ST[j][6], min(ST[i][6] for i in ids)); e0 = 0
                    if ST[j][7]: e0 = ST[j][7]
                    band = lk.buffer(2.5, cap_style=2)
                    hit = any(HP[k][1] < (e0 or 9999) and HP[k][2] > b0 and HP[k][0].intersects(band) for k in HT.query(band))
                    if hit: continue
                    wl = LineString([L.to_world(q, a.x, a.y), L.to_world(q, b.x, b.y)])
                    if any(b0 < ee and (e0 or 9999) > eb and wl.intersects(P) and wl.intersection(P).length > 0.02 for P, eb, ee in EP): continue
                    ST.append([round(a.x, 1), round(a.y, 1), round(b.x, 1), round(b.y, 1), 5, 'l', b0, e0, b0, 'link']); added += 1
            nlink += added
            if not added: break
        # 接不上的收掉
        isl = islands(ST, FW, FH); bad = {}
        for Y, grp in isl.items():
            for ids in grp:
                for i in ids: bad.setdefault(i, set()).add(Y)
        for i, ys in bad.items():
            s = ST[i]; av = [Y for Y in YEARS if alive(s, Y)]; ob, oe = s[6], s[7]
            ok = [Y for Y in av if Y not in ys]; I = sorted(ys)
            if not ok: nb, ne = ob, (ob if ob else 1)                      # 活着的年份全是孤岛：整段不要
            elif av[:len(I)] == I: nb, ne = ok[0], oe                      # 开头一段是孤岛：连通以后才出现
            else: nb, ne = ob, min(ys)                                     # 后来才断：断的那年收掉
            if len(s) == 9: s.append(['prune', ob, oe, s[8]])
            s[6], s[7] = nb, ne
            if nb != ob: s[8] = nb
            nprune += 1
        json.dump(ST, open(p, 'w'), separators=(',', ':'))
        rep[q] = (nlink, nprune)
    if not quiet: print('终扫：' + ' '.join(f'{k} 接{v[0]}收{v[1]}' for k, v in rep.items()))
    return rep
if __name__ == '__main__': main()
