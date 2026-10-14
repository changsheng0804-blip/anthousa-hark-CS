#!/usr/bin/env python3
"""全城放「生成型」地标（谭线 v31 交接：肉鱼市 macellum、砖窑 kiln、城外墓地 cemetery）。
选址算法照搬谭线 tools/landmarks.py（干山线 handoff-cs 19b633d），改成全城版：
  · 只在本街区"拥有"的地皮上选（框叠着的地方归先长的街区，同 tile_bake ORDER/OWN）；
  · 城墙内外用 world.json 的 wall_founder（世界坐标），不用干山局部的 wall_x；
  · 同种地标之间的间距、和其它地标的 120 px 间距跨街区算；
  · 严格审计：地标（墙+屋顶+柱廊）存续期内不压当年存在的路，压了就换下一个候选。
结果写回各街区 houses_street.json（行格式同谭线：h[9]='lm:<id>'，h[13:]=[原类型, 原高, 原脚印]；
被并进来的邻居 h[13:]=['merged', 原拆毁年]，h[3] 改成地标开工年——即 cause='cleared for <地标>'）。
并写 docs/living/tiles/cleared_cs.json 供叠层「旧街坊」读取。底账 world.json 一字不动。
  python3 tools/cs/factory/landmarks_city.py          # 全城重放（先撤掉这三种的旧放置）
——Hark（CS线），算法来源：谭线（干山线）"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
import house_types as HT, landmark_shapes as LS
LIV = os.path.join(ROOT, 'docs', 'living'); OUT = os.path.join(LIV, 'tiles')
KINDS = ['macellum', 'kiln', 'cemetery']   # 本轮只收这三种（主人定的顺序第 1 项）
# 全城版补充：谭线的砖窑卡写着「城墙边」，在干山里自然成立（整块地挨着墙）；放到全城要明说——离创城者城墙 ≤ near_wall 世界单位
CITY_ADAPT = {'kiln': {'near_wall': 22}}
M = json.load(open(os.path.join(OUT, 'meta.json'))); TP = M['tile_px']; S = M['scale']; X0, Y0 = M['origin']; NX, NY = M['grid']
QS = M['owner_order']
FR = {q: json.load(open(os.path.join(LIV, q, 'frame.json')))['frame'] for q in QS}
OWN = np.full((NY * TP, NX * TP), -1, np.int8)
for i, q in enumerate(QS):
    f = FR[q]; ox, oy = round((f[0] - X0) * S), round((f[1] - Y0) * S); w, h = round(f[2] * S), round(f[3] * S)
    v = OWN[oy:oy + h, ox:ox + w]; v[v < 0] = i
W = json.load(open(os.path.join(ROOT, 'world.json')))
WF = next(s for s in W['structures'] if s['id'] == 'wall_founder')['geom']['coords']
def wall_world_x(y): (x1, y1), (x2, y2) = WF; return x1 + (x2 - x1) * (y - y1) / (y2 - y1)
def to_world(q, x, y): f = FR[q]; return f[0] + x / S, f[1] + y / S
def owned(q, x, y):
    f = FR[q]; px, py = int(round((f[0] - X0) * S + x)), int(round((f[1] - Y0) * S + y))
    return 0 <= py < OWN.shape[0] and 0 <= px < OWN.shape[1] and OWN[py, px] == QS.index(q)
# ── 谭线 audit_streets 的几何（本地复刻，去掉它导入时读 cwd 的副作用）
def sd(px, py, s):
    ax, ay, bx, by = s[:4]; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
def body(h):
    fp = HT.footprint(h); ht = h[7] + HT.roof_extra(h); return fp + [(x, y - ht) for x, y in fp]
def bodies(h):
    B = [body(h)]
    po = HT.portico(h)
    if po: B.append(list(po[0]) + [(x, y - po[1]) for x, y in po[0]])
    ax = HT.annex(h)
    if ax: B.append(list(ax[0]) + [(x, y - ax[1] - 0.6) for x, y in ax[0]])
    return B
def _cr(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
def seg_hits_poly(a, b, P, pad):
    n = len(P)
    for k in range(n):
        c, d = P[k], P[(k + 1) % n]
        if ((_cr(c, d, a) > 0) != (_cr(c, d, b) > 0)) and ((_cr(a, b, c) > 0) != (_cr(a, b, d) > 0)): return True
        if min(sd(a[0], a[1], (c[0], c[1], d[0], d[1])), sd(b[0], b[1], (c[0], c[1], d[0], d[1])), sd(c[0], c[1], (a[0], a[1], b[0], b[1])), sd(d[0], d[1], (a[0], a[1], b[0], b[1]))) < pad: return True
    # 线段完全在多边形里
    x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2; c = False
    for k in range(n):
        (x1, y1), (x2, y2) = P[k], P[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
def ok_strict(h, ST):
    b, e = h[2], h[3]; B = bodies(h); cx = sum(q[0] for q in B[0][:4]) / 4; cy = sum(q[1] for q in B[0][:4]) / 4
    for s in ST:
        if abs((s[0] + s[2]) / 2 - cx) > 160 or abs((s[1] + s[3]) / 2 - cy) > 160: continue
        if not ((s[8] if len(s) > 8 else s[6]) < e and not (len(s) > 7 and s[7] and s[7] <= b)): continue
        for Bd in B:
            fp, up = Bd[:4], Bd[4:]
            for P in [fp, up] + [[fp[k], fp[(k + 1) % 4], up[(k + 1) % 4], up[k]] for k in range(4)]:
                if seg_hits_poly((s[0], s[1]), (s[2], s[3]), P, s[4] / 2): return False
    return True
# ── 谭线 landmarks.py 的选址（逐行对照，见文件头）
def area(h): p = h[4]; return abs(sum(p[2 * i] * p[(2 * i + 3) % 8] - p[(2 * i + 2) % 8] * p[2 * i + 1] for i in range(4))) / 2
def ctr(h): p = h[4]; return ((p[0] + p[2] + p[4] + p[6]) / 4, (p[1] + p[3] + p[5] + p[7]) / 4)
def front_mid(h):
    p = h[4]; f = h[10] if len(h) > 10 else 2; a = (p[2 * f], p[2 * f + 1]); b = (p[(2 * f + 2) % 8], p[(2 * f + 3) % 8]); return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
def street_kind_at(ST, x, y, kinds, Y):
    best = 1e9
    for s in ST:
        if s[5] in kinds and s[6] <= Y and not (s[7] and s[7] <= Y): best = min(best, sd(x, y, s) - s[4] / 2)
    return best
def pts_of(h): p = h[4]; return [(p[i], p[i + 1]) for i in range(0, 8, 2)]
def merge_options(h, GRID, PROTECT):
    P = pts_of(h); f = h[10] if len(h) > 10 else 2; c = ctr(h); out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for n in GRID.get((int(c[0] // 40) + dx, int(c[1] // 40) + dy), []):
                if n is h or n[0] in PROTECT or len(n) < 13 or n[3] < 900 or (n[12] & 1) or str(n[9]).startswith('lm:') or len(n) > 13: continue
                Q = pts_of(n)
                for k in range(4):
                    if k == f: continue
                    a, b = P[k], P[(k + 1) % 4]
                    ia = [i for i in range(4) if math.hypot(Q[i][0] - a[0], Q[i][1] - a[1]) < 1.6]
                    ib = [i for i in range(4) if math.hypot(Q[i][0] - b[0], Q[i][1] - b[1]) < 1.6]
                    if not ia or not ib: continue
                    ia, ib = ia[0], ib[0]
                    if (ia - ib) % 4 not in (1, 3): continue
                    d = 1 if (ia - ib) % 4 == 3 else -1
                    fa = Q[(ia - d) % 4]; fb = Q[(ib + d) % 4]
                    R = list(P); R[k] = fa; R[(k + 1) % 4] = fb
                    out.append((n, [v for qq in R for v in qq]))
    return out
def reset(HS):
    for h in HS:
        if len(h) > 13 and h[13] == 'merged' and len(h) > 15 and h[15] in KINDS: h[3] = h[14]; del h[13:]
        elif isinstance(h[9], str) and h[9][3:] in KINDS:
            h[9], h[7] = h[13], h[14]
            if len(h) > 15: h[4] = h[15]
            del h[13:]
def main():
    D = {q: json.load(open(os.path.join(LIV, q, 'houses_street.json'))) for q in QS}
    for q in QS: reset(D[q]['houses'])
    placed_w = []   # 全城：(种类, 世界 x, 世界 y)
    for q in QS:   # 其它种类已有的地标（谭线 v30 的教堂、面包台阶……若以后进来）也算间距
        for h in D[q]['houses']:
            if isinstance(h[9], str) and h[9].startswith('lm:'): c = ctr(h); placed_w.append((h[9][3:],) + to_world(q, *c))
    cleared = []; log = []
    for q in QS:
        HS = D[q]['houses']; ST = json.load(open(os.path.join(LIV, q, 'streets.json')))
        PROTECT = set()
        sp_ = os.path.join(LIV, q, 'stories.json')
        if os.path.exists(sp_): PROTECT |= {int(k) for k in json.load(open(sp_)) if str(k).isdigit()}
        GRID = {}
        for h in HS: c = ctr(h); GRID.setdefault((int(c[0] // 40), int(c[1] // 40)), []).append(h)
        for sid in KINDS:
            sp = LS.SPECS[sid]; si = sp['siting']; lo, hi = si['lot']; e0 = sp['era'][0]; nmax = sp['instances']['count'][1]
            gap = si.get('gap', 300 if sp['size'] == 'small' else 420)
            C = []
            for h in HS:
                if len(h) < 13 or h[3] < 900 or h[2] < e0 or not ((lo if sp['size'] == 'small' else lo * 0.45) <= area(h) <= hi) or h[12] & 1 or h[0] in PROTECT: continue
                if str(h[9]).startswith('lm:') or len(h) > 13: continue
                cx, cy = ctr(h)
                if not owned(q, cx, cy): continue
                wx, wy = to_world(q, cx, cy)
                if si.get('outside_wall'):
                    if wx > wall_world_x(wy) - si.get('wall_margin', 0) / S or h[9] not in si['typ']: continue
                elif h[8] not in si['fn'] or h[9] not in si['typ'] or h[2] > si.get('built_by', 40) or wx < wall_world_x(wy): continue
                nw = CITY_ADAPT.get(sid, {}).get('near_wall')
                if nw and wx - wall_world_x(wy) > nw: continue
                if si.get('front_on'):
                    fx, fy = front_mid(h)
                    if street_kind_at(ST, fx, fy, si['front_on'], h[2] + 2) > si.get('front_dist', 6): continue
                pf = si.get('prefer_fn', []); rank = pf.index(h[8]) if h[8] in pf else len(pf)
                score = (rank, -area(h) * (0.6 + 0.4 * HT.hsh(h[0], 301)) if si.get('prefer') == 'large' else HT.hsh(h[0], 300))
                C.append((score, h))
            C.sort(key=lambda c: c[0]); got = 0
            for _, h in C:
                if got >= nmax: break
                c = ctr(h); wc = to_world(q, *c)
                if any(math.hypot((wc[0] - p[1]) * S, (wc[1] - p[2]) * S) < (gap if p[0] == sid else 120) for p in placed_w): continue
                old9, old7, old4 = h[9], h[7], h[4]
                opts = [(None, old4)]
                if sp['size'] != 'small' and area(h) < lo: opts = merge_options(h, GRID, PROTECT)
                elif sp['size'] != 'small': opts = merge_options(h, GRID, PROTECT) + opts if si.get('prefer_merge') else opts + merge_options(h, GRID, PROTECT)
                for nb, poly in opts:
                    h[4] = poly
                    if area(h) < lo or area(h) > hi * 1.6: continue
                    h += [old9, old7, old4]; h[9] = 'lm:' + sid; h[7] = LS.height(sp)
                    if ok_strict(h, ST):
                        mg = []
                        if nb is not None:
                            nb += ['merged', nb[3], sid]; nb[3] = max(nb[2], h[2]); mg.append(nb)
                            for _ in range(si.get('merge_max', 1) - 1):
                                if area(h) >= si.get('target', lo): break
                                for nb2, poly2 in sorted(merge_options(h, GRID, PROTECT), key=lambda o: -area(o[0])):
                                    keep = h[4]; h[4] = poly2
                                    if area(h) <= hi * 1.6 and ok_strict(h, ST):
                                        nb2 += ['merged', nb2[3], sid]; nb2[3] = max(nb2[2], h[2]); mg.append(nb2); break
                                    h[4] = keep
                                else: break
                        got += 1; placed_w.append((sid,) + wc)
                        for n in mg: cleared.append({'id': 'h%d' % n[0], 'for': sid, 'lm': 'h%d' % h[0], 'year': n[3], 'q': q})
                        log.append(f"{q} {sid} h{h[0]} 建于 {h[2]} 面积 {int(area(h))} {h[8]} 世界({wc[0]:.0f},{wc[1]:.0f}) 并入 {len(mg)}")
                        break
                    h[9], h[7] = old9, old7; del h[13:]
                else:
                    h[4] = old4; continue
                if h[4] != old4 and len(h) <= 13: h[4] = old4
    for q in QS: json.dump(D[q], open(os.path.join(LIV, q, 'houses_street.json'), 'w'), separators=(',', ':'))
    json.dump({'src': 'tools/cs/factory/landmarks_city.py（谭线 v31 地标卡）', 'cleared': cleared, 'placed': log}, open(os.path.join(OUT, 'cleared_cs.json'), 'w'), ensure_ascii=False, indent=0)
    print('\n'.join(log)); print('放置', len(log), '并入拆除', len(cleared))
if __name__ == '__main__': main()
