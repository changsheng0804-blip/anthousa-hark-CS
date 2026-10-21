"""规则预演 v3 · 户籍册的一次性预备（编册前的「底册」）：
  1. 年龄口径改 14：每户每年「14 岁以下孩子」矩阵（v1 缓存里是 12 岁）。与 v1 缓存同一户序，逐年核对人数矩阵完全相同。
  2. 户主名（户里第一个人的名字，只给故事列表用）。
  3. 页面房子 → 账本房屋：v2 只拿干山街区（d_xerolophos）的 746 栋去对，中位差 530px，结论是「一栋账本房屋≈6 户」。
     本轮发现：用同一个 v0 仿射（affine.json）去对**全城**账本房屋，页面房子到最近账本房屋中位只有 9px（≈半栋房子宽），
     页面上的「干山」其实横跨账本的广场区（d_forum）、港口区（d_harbor）和干山区（d_xerolophos）三个街区；
     页面 11/38/48/54 年的拆房与账本同年、同街区的拆房对得上（见 out/prep3_xero.json demolition_check）。
     所以底册 = 页面房子逐年登记到最近的、那年站着的账本房屋（ledger_reg，假设 R1/R2）。
  全城（合成）：合成人家本来就住在账本房屋上（一栋一户），登记房屋 = 自己的房子，不需要映射。
缓存写在仓库外 ../rules_v3_<scope>.pkl。
usage: python3 prep3.py sample|xero|city
"""
import sys, os, json, time, pickle, math, collections
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(HERE, '..', 'rules_v1'); V0 = os.path.join(HERE, '..', 'rules_v0')
sys.path.insert(0, V1); sys.path.insert(1, V0)
import prep  # noqa: E402  (v1 预计算，只读)
import data as D0  # noqa: E402  (v0 数据层，只读)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CACHE = prep.CACHE
YR0, YR1 = prep.YR0, prep.YR1; NY = YR1 - YR0 + 1


def cache_path(scope): return os.path.join(CACHE, f'rules_v3_{scope}.pkl')


def people_mats(houses, M):
    """与 v1 prep.arrays 同一户序；只算 14 岁口径的孩子数 + 户主名，并核对人数矩阵。"""
    pf, pb, pd, pm, pl = [], [], [], [], []; names = []; F = 0
    for h in houses:
        for f in h['fams']:
            names.append(f['people'][0]['n'] if f['people'] else '?')
            for p in f['people']:
                pf.append(F); pb.append(p['b']); pd.append(p['d']); pm.append(p['married'] or 0); pl.append(p['left'] or 0)
            F += 1
    assert F == len(M['fB']), (F, len(M['fB']))
    pf = np.array(pf); pb = np.array(pb); pd = np.array(pd); pm = np.array(pm); pl = np.array(pl)
    kids14 = np.zeros((F, NY), np.int16); chk = 0
    for yi in range(NY):
        Y = YR0 + yi
        hm = (pb <= Y) & (Y < pd) & ((pm == 0) | (pm <= Y)) & ~((pl != 0) & (pl <= Y))
        kids14[:, yi] = np.bincount(pf[hm & (Y - pb < 14)], minlength=F)
        chk += int((np.bincount(pf[hm], minlength=F) != M['size'][:, yi]).sum())
    return kids14, names, chk


def world_ledger():
    """账本全部房屋（world.json，全城 18,943 栋）：街区、建/拆年、中心点仿射到页面坐标（v0 affine.json，与蓄水池/大道同一坐标系）。"""
    WH = json.load(open(os.path.join(ROOT, 'world.json')))['houses']
    A = np.array(D0._affine())
    c = np.array([np.mean(np.array(h['p']), 0) for h in WH]); pc = c @ A[:2] + A[2]
    return dict(ids=[h['id'] for h in WH], d=np.array([h['d'] for h in WH], object), built=np.array([h['built'] for h in WH], np.int32),
                dest=np.array([h['destroyed'] if h['destroyed'] is not None else 9999 for h in WH], np.int32), px=pc[:, 0], py=pc[:, 1])


def ledger_reg(M, WL, K=8, R=40.0):
    """页面房子 → 账本房屋，逐年（底册）。候选 = 仿射后 40px 内最近的 8 栋账本房屋（任何街区），
    按「拆毁年对得上 + 建成年接近 + 距离」排序（假设 R1）；某年登记房屋 = 第一个那年站着的候选，
    一个都不站着就挂到那年站着的最近账本房屋（R2 暂挂/迁籍）。返回 reg[页面房子, 年] = 账本房屋下标。"""
    P = np.c_[M['hlx'], M['hly']]; Hn = len(P)
    t = cKDTree(np.c_[WL['px'], WL['py']])
    d, j = t.query(P, k=K)
    pde = np.minimum(M['hdest'], 71)[:, None]; lde = np.minimum(WL['dest'][j], 71)
    cost = d / 9.0 + np.abs(lde - pde) / 5.0 + np.abs(WL['built'][j] - M['hbuilt'][:, None]) / 20.0
    cost = np.where(d <= R, cost, 1e9 + d)
    o = np.argsort(cost, axis=1, kind='stable'); j = np.take_along_axis(j, o, 1)
    reg = np.full((Hn, NY), -1, np.int64); hosted = np.zeros((Hn, NY), bool)
    for yi in range(NY):
        Y = YR0 + yi
        ok = (WL['built'][j] <= Y) & (WL['dest'][j] > Y)
        first = np.argmax(ok, 1); has = ok[np.arange(Hn), first]
        reg[has, yi] = j[np.nonzero(has)[0], first[has]]
        rest = np.nonzero(~has)[0]
        if len(rest):
            st = np.nonzero((WL['built'] <= Y) & (WL['dest'] > Y))[0]
            if len(st):
                _, jj = cKDTree(np.c_[WL['px'][st], WL['py'][st]]).query(P[rest]); reg[rest, yi] = st[jj]; hosted[rest, yi] = True
    return reg, hosted, j[:, 0], d.min(1)


def build(scope):
    t0 = time.time()
    D = prep.load(scope); M = D['main']
    if scope == 'city': W = D0.load_city(); houses = W['houses']
    else:
        W = D0.load_xero(); houses = W['houses']
        if scope == 'sample':
            ids = set(json.load(open(os.path.join(V0, 'sample.json')))['houses']); houses = [h for h in houses if h['id'] in ids]
    kids14, names, chk = people_mats(houses, M)
    out = dict(scope=scope, kids14=kids14, names=names)
    info = dict(scope=scope, size_matrix_mismatch=chk)
    if scope == 'city':
        WL = world_ledger(); idx = {h: i for i, h in enumerate(WL['ids'])}
        r = np.array([idx[h] for h in M['hid']]); out['WL'] = WL
        out['reg'] = np.repeat(r[:, None], NY, 1); out['hosted'] = np.zeros((len(r), NY), bool)   # 登记房屋 = 自己的房子（合成人家住在账本房屋上）
    else:
        WL = world_ledger()
        reg, hosted, first, dmin = ledger_reg(M, WL)
        out.update(WL=WL, reg=reg, hosted=hosted)
        yi = 60 - YR0; st60 = (M['hbuilt'] <= 60) & (M['hdest'] > 60)
        u = np.unique(reg[st60, yi])
        chk = {}
        for yr in (11, 38, 48, 54):            # 页面拆房年 vs 登记账本房屋的拆毁年
            m = M['hdest'] == yr
            chk[str(yr)] = dict(page_demolished=int(m.sum()), ledger_same_year=int((WL['dest'][first[m]] == yr).sum()),
                                district=dict(collections.Counter(WL['d'][first[m]].tolist())))
        info.update(dist_to_ledger_px=dict(p50=round(float(np.median(dmin)), 1), p90=round(float(np.percentile(dmin, 90)), 1), p99=round(float(np.percentile(dmin, 99)), 1)),
                    hosted_house_years_AF50_70=int(hosted[:, 50 - YR0:].sum()), page_houses_AF60=int(st60.sum()), ledger_houses_AF60=len(u),
                    ledger_houses_AF60_by_district=dict(collections.Counter(WL['d'][u].tolist())), demolition_check=chk)
    pickle.dump(out, open(cache_path(scope), 'wb'), protocol=5)
    info.update(seconds=round(time.time() - t0, 2), bytes=os.path.getsize(cache_path(scope)))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    json.dump(info, open(os.path.join(HERE, 'out', f'prep3_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))


def load(scope): return pickle.load(open(cache_path(scope), 'rb'))


if __name__ == '__main__':
    build(sys.argv[1])
