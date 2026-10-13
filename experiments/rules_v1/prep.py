"""规则预演 v1 · 预计算（一次性）：把页面家谱推演 + 空间事实整理成紧凑的 numpy 数组，缓存到仓库外 ../rules_v1_<scope>.npz。
输入与 v0 完全相同（直接调用 rules_v0/data.py 的 load_xero / load_city，只读），保证两版吃的是同一份户。
预计算的是「每户不变的属性」和「每户每年的状态矩阵」，之后逐年规则只读这些数组：
  户（family = 房子里的一家，键 "房号:搬入年"）：房子下标、搬入年 B、下一家搬入年、籍贯/信仰/行当 id、是否有房（假设 A）
  每户每年（AF40–70）：在不在住、几口人、成年男人、12 岁以下孩子、当年死了几个、有没有 12–15 岁的男孩、当年住哪条街
  房子：坐标 (x,y)（谭线门牌坐标）、(lx,ly)（页面坐标）、建/拆年、街区功能
  亲家（v1 新增，只给分级/视野用，不进交叉点）：嫁出去的女儿 to=房号 → 两家
usage: python3 prep.py sample|xero|city
"""
import sys, os, json, time, pickle, resource
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V0 = os.path.join(HERE, '..', 'rules_v0')
sys.path.insert(0, V0)
import data as D0  # noqa: E402  (v0 数据层，只读)

YR0, YR1 = 40, 70          # 状态矩阵覆盖的年份（灾年要看 40–70 的死亡率）
NY = YR1 - YR0 + 1
CACHE = D0.CACHE
FAITHS = ['阿里乌派', '尼西亚派', '还拜旧神']


def cache_path(scope):
    return os.path.join(CACHE, f'rules_v1_{scope}.pkl')


def build(scope):
    t0 = time.time()
    if scope == 'city':
        W = D0.load_city(); full = None
    else:
        W = D0.load_xero(); full = None
        if scope == 'sample':
            ids = set(json.load(open(os.path.join(V0, 'sample.json')))['houses'])
            full = W['houses']
            W = dict(W, houses=[h for h in W['houses'] if h['id'] in ids])
    t_load = time.time() - t0
    out = dict(scope=scope, YR0=YR0, YR1=YR1)
    out['main'] = arrays(W['houses'])
    if full is not None:
        out['full'] = arrays(full)          # 样本按闭合世界跑，但灾年用整个干山的死亡率（与 v0 同）
    out['water'] = [dict(id=w['id'], kind=w['kind'], x=w['xy'][0], y=w['xy'][1], built=w['built']) for w in W['water']]
    out['ovens'] = [dict(id=o['id'], x=o['xy'][0], y=o['xy'][1], built=o['built']) for o in W['ovens']]
    b = W['places'].get('barracks_gate')
    out['barracks'] = b['xy'] if b else None
    pickle.dump(out, open(cache_path(scope), 'wb'), protocol=5)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(json.dumps(dict(scope=scope, load_v0_json_s=round(t_load, 2), prep_total_s=round(time.time() - t0, 2), prep_peak_rss_mb=round(rss),
                          families=len(out['main']['fB']), houses=len(out['main']['hid']), cache_bytes=os.path.getsize(cache_path(scope)))))


def arrays(houses):
    Hn = len(houses)
    hid = [h['id'] for h in houses]
    hx = np.array([h['x'] for h in houses], float); hy = np.array([h['y'] for h in houses], float)
    hlx = np.array([h['lx'] for h in houses], float); hly = np.array([h['ly'] for h in houses], float)
    hbuilt = np.array([h['built'] for h in houses], np.int32); hdest = np.array([h['destroyed'] for h in houses], np.int32)
    fn_names = sorted({h['fn'] for h in houses}); hfn = np.array([fn_names.index(h['fn']) for h in houses], np.int16)
    # 街：每房每年第一个匹配的段（与 v0 street_at 同）
    st_names = sorted({s[0] for h in houses for s in h['segs']})
    sti = {n: i for i, n in enumerate(st_names)}
    hstreet = np.full((Hn, NY), -1, np.int32)
    for i, h in enumerate(houses):
        for yi in range(NY):
            Y = YR0 + yi
            for nm, num, f, t, orig in h['segs']:
                if f <= Y < t: hstreet[i, yi] = sti[nm]; break
    # 户
    origins, trades = [], []
    def gid(lst, v):
        if v not in lst: lst.append(v)
        return lst.index(v)
    fh, fi, fB, fBn, fo, ff, ft, fsold = [], [], [], [], [], [], [], []
    pf, pb, pd, pm, pl, ps, pto = [], [], [], [], [], [], []
    for i, h in enumerate(houses):
        sy = sorted(y for y, t in h['ev'] if '当了兵' in t)
        for j, f in enumerate(h['fams']):
            F = len(fB)
            fh.append(i); fi.append(j); fB.append(f['B'])
            fBn.append(h['fams'][j + 1]['B'] if j + 1 < len(h['fams']) else 10 ** 6)
            fo.append(gid(origins, f['origin'])); ff.append(FAITHS.index(f['faith'])); ft.append(gid(trades, f['trade']))
            fsold.append(next((y for y in sy if y >= f['B']), 10 ** 6))   # soldier(Y) ⇔ 第一个 ≥B 的当兵年 ≤ Y
            for p in f['people']:
                pf.append(F); pb.append(p['b']); pd.append(p['d']); pm.append(p['married'] or 0); pl.append(p['left'] or 0)
                ps.append(p['s'] == 'm'); pto.append(p['to'] if isinstance(p.get('to'), int) else -1)
    fh = np.array(fh, np.int32); fi = np.array(fi, np.int16); fB = np.array(fB, np.int32); fBn = np.array(fBn, np.int32)
    pf = np.array(pf, np.int32); pb = np.array(pb, np.int32); pd = np.array(pd, np.int32)
    pm = np.array(pm, np.int32); pl = np.array(pl, np.int32); ps = np.array(ps, bool); pto = np.array(pto, np.int64)
    Fn = len(fB)

    def home(Y):  # 与页面 aliveAt / v0 home() 同一规则
        return (pb <= Y) & (Y < pd) & ((pm == 0) | (pm <= Y)) & ~((pl != 0) & (pl <= Y))
    present = np.zeros((Fn, NY), bool); size = np.zeros((Fn, NY), np.int16); men = np.zeros((Fn, NY), np.int16)
    kids = np.zeros((Fn, NY), np.int16); deaths = np.zeros((Fn, NY), np.int16); boy = np.zeros((Fn, NY), bool)
    for yi in range(NY):
        Y = YR0 + yi
        cur = (hbuilt[fh] <= Y) & (Y < hdest[fh]) & (fB <= Y) & (Y < fBn)
        hm = home(Y); age = Y - pb
        sz = np.bincount(pf[hm], minlength=Fn)
        present[:, yi] = cur & (sz > 0)
        size[:, yi] = sz
        men[:, yi] = np.bincount(pf[hm & ps & (age >= 16)], minlength=Fn)
        kids[:, yi] = np.bincount(pf[hm & (age < 12)], minlength=Fn)
        deaths[:, yi] = np.bincount(pf[(pd == Y) & home(Y - 1)], minlength=Fn)
        boy[:, yi] = np.bincount(pf[hm & ps & (age >= 12) & (age <= 15)], minlength=Fn) > 0
    present &= True
    keys = [f'{hid[fh[F]]}:{fB[F]}' for F in range(Fn)]
    # 亲家（v1 新增）：女儿 left 年嫁到 to 号房 → 娘家户 F 与那年住在 to 号房的户
    hidx = {h: i for i, h in enumerate(hid)}
    kin = []
    for k in np.nonzero(pto >= 0)[0]:
        j = hidx.get(int(pto[k]), hidx.get(str(pto[k])))
        if j is None: continue
        Y = int(pl[k])
        G = next((F for F in np.nonzero(fh == j)[0] if fB[F] <= Y < fBn[F]), None)
        if G is not None and G != pf[k]: kin.append((int(pf[k]), int(G), Y, int(pd[k])))  # 女儿活着期间算亲家
    return dict(hid=hid, hx=hx, hy=hy, hlx=hlx, hly=hly, hbuilt=hbuilt, hdest=hdest, hfn=hfn, fn_names=fn_names,
                hstreet=hstreet, st_names=st_names, fh=fh, fi=fi, fB=fB, fBn=fBn, fo=np.array(fo, np.int16), ff=np.array(ff, np.int8),
                ft=np.array(ft, np.int16), fsold=np.array(fsold, np.int32), origins=origins, trades=trades, keys=keys,
                present=present, size=size, men=men, kids=kids, deaths=deaths, boy=boy,
                kin=np.array(kin, np.int32).reshape(-1, 4))


def load(scope):
    return pickle.load(open(cache_path(scope), 'rb'))


if __name__ == '__main__':
    build(sys.argv[1])
