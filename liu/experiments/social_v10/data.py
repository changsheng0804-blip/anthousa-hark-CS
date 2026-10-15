"""v10 输入：逐年户籍（v7 增量）+ 逐年职位名册（v8 Caster 默认配置）+ 门口路口 + 市场节点。
只按路径载入 ../gov_frame_v8/cast.py（它再载入 ../city_system_v7_streets/city_system.py），不改它们。
结果缓存到 .cache/census.pkl（不入库，可由本文件重建）。——Hark（刘线）"""
import importlib.util, json, os, pickle, sys, time, zlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CACHE = os.path.join(HERE, '.cache', 'census.pkl')
Y0, Y1 = 40, 70


def load_cast():
    sp = importlib.util.spec_from_file_location('cast8', os.path.join(HERE, '..', 'gov_frame_v8', 'cast.py'))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def build_cache():
    t0 = time.time()
    cast = load_cast(); cs7 = cast.cs7
    world = json.load(open(os.path.join(ROOT, 'world.json')))
    C = cs7.prepare(world); S = C.S
    st = cs7.build(C, Y0)
    years, junc = {}, {}
    for Y in range(Y0, Y1 + 1):
        if Y > Y0:
            st.Y = Y
            for ev in cs7.events_for_year(C, Y):
                cs7.apply(st, ev)
        recs, _ = cs7.materialize(st)
        years[Y] = {h: tuple(v[k] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9)) for h, v in recs.items()}
        junc[Y] = cast.graph_raw(C, st)['house_junction']
        print('census', Y, len(years[Y]), round(time.time() - t0, 1), flush=True)
    hidx = {S.hid[i]: i for i in range(len(S.hid))}
    built = {h: int(S.built[i]) for h in hidx for i in [hidx[h]]}
    idnum = {h: int(S.idnum[i]) for h in hidx for i in [hidx[h]]}
    since = cast.residency_table(years, built)
    W = cast.World(years, built, idnum, since, {})
    O, P = cast.load_rules()
    _, full, kept = cast.run(W, O, P, None, verify=False, keep=tuple(range(Y0, Y1 + 1)))
    holders = {Y: {inst: v[0] for inst, v in kept[Y].items()} for Y in kept}
    out = dict(years=years, junc=junc, holders=holders, built=built, offices=O['offices'])
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    pickle.dump(out, open(CACHE, 'wb'))
    print('cache done', round(time.time() - t0, 1))
    return out


def load():
    if not os.path.exists(CACHE):
        return build_cache()
    return pickle.load(open(CACHE, 'rb'))


def houses():
    """账本房屋：id、区、形心、建成/拆毁年；面积（身份代理）。"""
    w = json.load(open(os.path.join(ROOT, 'world.json')))
    H = w['houses']
    ids = [h['id'] for h in H]
    xy = np.array([np.mean(h['p'], 0) for h in H])
    def area(p):
        p = np.array(p); x, y = p[:, 0], p[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    A = np.array([area(h['p']) for h in H])
    built = np.array([h['built'] for h in H]); dest = np.array([h['destroyed'] if h['destroyed'] is not None else 10 ** 6 for h in H])
    d = [h['d'] for h in H]
    return dict(ids=ids, xy=xy, area=A, built=built, dest=dest, d=d, world=w)


def market_nodes(Hs):
    """市场类节点（来源标注）：
    - world.json structures：market / forum（广场即市）/ harbor（港口）/ warehouse（港仓）→ 多边形形心，按 built/destroyed 取当年；
    - facts_upstream/landmarks.json generated_xerolophos 中 spec=bread_steps（面包台阶）→ 落在上游房屋 id 上，取同 id 账本房屋形心。
    返回 [(id, 类型, 来源, x, y, built, destroyed)]。"""
    w = Hs['world']; out = []
    for s in w['structures']:
        if s['type'] in ('market', 'forum', 'harbor', 'warehouse'):
            p = np.array(s['geom']['coords'], float)
            out.append((s['id'], s['type'], 'world.json structures', float(p[:, 0].mean()), float(p[:, 1].mean()), s['built'], s['destroyed'] if s['destroyed'] is not None else 10 ** 6))
    L = json.load(open(os.path.join(ROOT, 'docs', 'living', 'xerolophos', 'facts_upstream', 'landmarks.json')))
    pos = {h: k for k, h in enumerate(Hs['ids'])}
    for g in L['generated_xerolophos']:
        if g['spec'] == 'bread_steps':
            k = pos.get(f"h{g['house']}")
            if k is None: continue
            out.append((f"bread_steps@h{g['house']}", 'bread_steps', 'facts_upstream/landmarks.json generated_xerolophos（上游房屋 id→账本形心）',
                        float(Hs['xy'][k, 0]), float(Hs['xy'][k, 1]), g['built'], g['destroyed'] if g['destroyed'] < 9999 else 10 ** 6))
    return out


if __name__ == '__main__':
    build_cache()
