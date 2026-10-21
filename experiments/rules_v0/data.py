"""规则预演 v0 · 数据层：把页面家谱推演 + 谭线空间事实 + 世界账本整理成规则能读的「户」与「场所」。
只读：docs/living/xerolophos/（index.html 推演经 export_households.js 导出）、facts_upstream/、world.json。
两种范围：
  xero  干山页全部房子（账本人家，页面同一推演；街名/门牌/街区功能来自 facts_upstream/addr.json）
  city  world.json 全城房子 + 页面同一 household() 推演出的「合成人家」（export_city.js），只做规模测试
"""
import json, math, os, subprocess, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
XD = os.path.join(ROOT, 'docs/living/xerolophos')
FU = os.path.join(XD, 'facts_upstream')
CACHE = os.path.abspath(os.path.join(ROOT, '..'))  # 工作副本外，不进仓库

# 账本大事（world.json eras 41–70 的 accepted 建筑 + 其 history）。w = 对街坊的冲击强度（规则预演里自定的权重）
LEDGER_EVENTS = {
    48: ('南港大火，烧掉 287 座房子', 2.0),
    49: ('阿纳斯塔西娅：尼西亚派在私宅小堂聚会', 0.5),
    51: ('新皇帝把阿里乌派请出城里所有教堂', 2.0),
    52: ('阿里乌派节日出奠基者城门，在城外院子祈祷', 1.0),
    54: ('运水人凑铜板修运水人蓄水池（拆 17 座房）', 2.0),
    55: ('亚历山大粮仓（埃及粮船）', 0.5),
    57: ('狄奥多西广场（拆 29 座房）', 1.0),
    62: ('运水人台阶路 + 第二座运水人蓄水池（上坡人家再凑铜板）', 1.5),
    63: ('城外新区 Exokionion', 0.5),
    64: ('城门外的阿里乌派砖砌教堂', 1.0),
    65: ('寡妇孤儿之家（山上七户里有一户没有成年男人、家里有小孩）', 1.5),
}


def _cen(p):
    xs, ys = p[0::2], p[1::2]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _affine():
    return json.load(open(os.path.join(os.path.dirname(__file__), 'affine.json')))


def _T(M, x, y):
    return (x * M[0][0] + y * M[1][0] + M[2][0], x * M[0][1] + y * M[1][1] + M[2][1])


def _world_points():
    """全城建筑中心，换到干山页像素坐标。"""
    W = json.load(open(os.path.join(ROOT, 'world.json')))
    M = _affine()
    out = {}
    for s in W['structures']:
        g = s['geom']; c = g.get('coords')
        if not c: continue
        if g['type'] == 'polygon' and isinstance(c[0][0], list): c = c[0]
        pts = [c] if not isinstance(c[0], (list, tuple)) else c
        x = sum(p[0] for p in pts) / len(pts); y = sum(p[1] for p in pts) / len(pts)
        out[s['id']] = dict(id=s['id'], type=s['type'], xy=_T(M, x, y), built=s['built'],
                            destroyed=s['destroyed'] if s['destroyed'] is not None else 9999,
                            line=[_T(M, *p) for p in pts] if g['type'] == 'line' else None)
    return out


def load_xero():
    hh_path = os.path.join(CACHE, 'hh_all.json')
    if not os.path.exists(hh_path):
        subprocess.run(f'node tools/export_households.js docs/living/xerolophos > {hh_path}', shell=True, cwd=ROOT, check=True)
    H = json.load(open(hh_path))
    A = json.load(open(os.path.join(FU, 'addr.json')))
    U = {h[0]: h for h in json.load(open(os.path.join(FU, 'houses.json')))['houses']}
    streets = A['streets']  # [name0, since, [[name, from, to], ...]]
    houses = []
    for h in H:
        u = U.get(h['id'])
        ux, uy = _cen(u[4]) if u else (h['cx'], h['cy'])
        a = A['h'].get(str(h['id']), ['homes', []])
        segs = []
        for si, num, f, t in a[1]:
            for nm, nf, nt in streets[si][2]:
                lo, hi = max(f, nf), min(t, nt)
                if lo < hi: segs.append((nm, num, lo, hi, streets[si][0]))
        houses.append(dict(id=h['id'], x=ux, y=uy, lx=h['cx'], ly=h['cy'], built=h['built'], destroyed=h['destroyed'],
                           fams=h['fams'], ev=h['ev'], fn=a[0], segs=segs))
    J = json.load(open(os.path.join(FU, 'junctions.json')))
    WP = _world_points()
    water = [dict(id=f'井{i}', kind='well', xy=(x, y), built=yr) for i, (x, y, yr, k) in enumerate(J) if k == 'well']
    for sid, nm in [('cistern_modestus', '莫德斯图斯蓄水池'), ('cistern_carriers', '运水人蓄水池'), ('cistern_slope', '第二座运水人蓄水池')]:
        s = WP[sid]; water.append(dict(id=nm, kind='cistern', xy=s['xy'], built=s['built'], sid=sid))
    ovens = [dict(id=f'炉{i}', xy=(x, y), built=yr) for i, (x, y, yr, k) in enumerate(J) if k == 'oven']
    named = {tuple(j[:2]): j[4] for j in json.load(open(os.path.join(FU, 'junctions_named.json')))['junctions']}
    for o in ovens + [w for w in water if w['kind'] == 'well']:
        o['streets'] = named.get((int(o['xy'][0]), int(o['xy'][1])), [])
    return dict(scope='xero', houses=houses, water=water, ovens=ovens, places=WP)


def load_city():
    p = os.path.join(CACHE, 'city_hh.json')
    if not os.path.exists(p):
        subprocess.run(f'node experiments/rules_v0/export_city.js > {p}', shell=True, cwd=ROOT, check=True)
    H = json.load(open(p))
    WP = _world_points()
    roads = [s for s in WP.values() if s['type'] == 'road' and s['line']]
    # 合成「街」：最近的账本道路（60px 内）+ 沿路 120px 一段算一条「街」；60px 外按 120px 网格算「巷」。全是假设。
    def seg_d(px, py, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy or 1
        t = max(0, min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / L))
        qx, qy = a[0] + t * dx, a[1] + t * dy
        return math.hypot(px - qx, py - qy), t, math.hypot(dx, dy)
    FN = {'market': 'market', 'forum': 'market', 'harbor': 'shops', 'warehouse': 'shops', 'granary': 'shops', 'barracks': 'garrison',
          'cistern': 'water', 'palace': 'fine', 'church': 'fine', 'monument': 'fine', 'baths': 'shops', 'farmland': 'garden'}
    nonroad = [s for s in WP.values() if s['type'] in FN]
    houses = []
    for h in H:
        x, y = h['cx'], h['cy']; best = None
        for r in roads:
            if r['built'] > h['built'] + 60: continue
            acc = 0
            for a, b in zip(r['line'], r['line'][1:]):
                d, t, L = seg_d(x, y, a, b)
                if best is None or d < best[0]: best = (d, r['id'], int((acc + t * L) // 120), r['built'])
                acc += L
        if best and best[0] < 60:
            st = f"{best[1]}#{best[2]}"; since = best[3]
        else:
            st = f"巷{int(x // 120)},{int(y // 120)}"; since = -999
        ns = min(nonroad, key=lambda s: math.hypot(s['xy'][0] - x, s['xy'][1] - y))
        fn = FN[ns['type']] if math.hypot(ns['xy'][0] - x, ns['xy'][1] - y) < 150 else 'homes'
        houses.append(dict(id=h['id'], x=x, y=y, lx=x, ly=y, built=h['built'], destroyed=h['destroyed'], fams=h['fams'], ev=h['ev'],
                           fn=fn, segs=[(st, 0, max(since, -999), 9999, st)]))
    water = [dict(id=s['id'], kind='cistern', xy=s['xy'], built=s['built']) for s in WP.values() if s['type'] == 'cistern']
    # 全城没有井和炉的底账：按 240px 网格放「假设井」「假设炉」各一（合成，只为让规则可运行）
    cells = {(int(h['x'] // 240), int(h['y'] // 240)) for h in houses}
    water += [dict(id=f'假设井{c}', kind='well', xy=(c[0] * 240 + 120, c[1] * 240 + 120), built=-999) for c in cells]
    ovens = [dict(id=f'假设炉{c}', xy=(c[0] * 240 + 120, c[1] * 240 + 120), built=-999, streets=[]) for c in cells]
    return dict(scope='city', houses=houses, water=water, ovens=ovens, places=WP)


def street_at(h, Y):
    for nm, num, f, t, orig in h['segs']:
        if f <= Y < t: return nm, num
    return None, None


def home(p, Y):  # 与页面 aliveAt 同一规则
    return p['b'] <= Y < p['d'] and (not p['married'] or p['married'] <= Y) and not (p['left'] and p['left'] <= Y)


def fam_at(h, Y):
    f = None; idx = -1
    for i, x in enumerate(h['fams']):
        if x['B'] <= Y: f = x; idx = i
    return f, idx
