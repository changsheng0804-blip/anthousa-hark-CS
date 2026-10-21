"""小测（下一步方案的可行性）：以「账本房屋」为单位挂户——每户落到最近的账本房屋（world.json d_xerolophos，仿射到页面坐标），
一栋账本房屋 = 一个房东（屋里住得最久的那家）+ 一本配给簿；房东和配给就变成「户 → 所在账本房屋」的纯函数，不再需要全城顺序贪心，也不用存。
只测：每栋账本房屋里几户、和 v1 房东分配有多少相同、单户现算耗时。不改任何规则文件。
usage: python3 ledger_house.py
"""
import os, sys, json, time, collections
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econpol as EP  # noqa: E402
import data as D0  # noqa: E402
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def main():
    P = json.load(open(os.path.join(EP.V0, 'rules.json')))
    E = EP.EconPol('xero', P, 'v1'); M = E.M
    WH = [h for h in json.load(open(os.path.join(ROOT, 'world.json')))['houses'] if h['d'] == 'd_xerolophos']
    A = D0._affine()
    wxy = np.array([D0._T(A, *np.mean(np.array(h['p']), 0)) for h in WH])
    wb = np.array([h['built'] for h in WH]); wd = np.array([h['destroyed'] if h['destroyed'] is not None else 9999 for h in WH])
    t0 = time.perf_counter()
    tree = cKDTree(wxy)
    out = {}
    for Y in (51, 55, 60, 65):
        yi = Y - E.YR0; S = np.nonzero(M['present'][:, yi])[0]
        alive = np.nonzero((wb <= Y) & (wd > Y))[0]
        t = cKDTree(wxy[alive]); _, j = t.query(np.c_[E.flx[S], E.fly[S]]); lh = alive[j]
        cnt = np.bincount(lh, minlength=len(WH))[alive]
        # 房东 = 这栋账本房屋里搬入最早的人家（同年按户键）
        B = M['fB'][S]; kr = E.keyrank[S]
        o = np.lexsort((kr, B, lh)); first = np.r_[True, lh[o][1:] != lh[o][:-1]]
        head = np.full(len(WH), -1); head[lh[o][first]] = S[o][first]
        ll_new = head[lh]; ll_new = np.where(ll_new == S, -1, ll_new)
        R = E.year_ep(Y); L = R['landlord']; ll_v1 = np.where(L >= 0, S[np.maximum(L, 0)], -1)
        ten_v1 = ll_v1 >= 0
        out[Y] = dict(ledger_houses=int(len(alive)), households=int(len(S)), empty_ledger_houses=int((cnt == 0).sum()),
                      households_per_ledger_house=dict(mean=round(float(cnt.mean()), 2), p50=float(np.median(cnt)), p95=float(np.percentile(cnt, 95)), max=int(cnt.max())),
                      landlords_new=int(len(set(ll_new[ll_new >= 0].tolist()))), landlords_v1=int(len(set(ll_v1[ten_v1].tolist()))),
                      v1_tenants=int(ten_v1.sum()), v1_tenants_same_landlord=int((ten_v1 & (ll_new == ll_v1)).sum()),
                      ration_books_new=int(len(alive)), owner_households_rule_A=int(E.owner[S].sum()))
    # 单户现算：一次最近邻 + 读屋主
    Y = 60; yi = Y - E.YR0; S = np.nonzero(M['present'][:, yi])[0]
    alive = np.nonzero((wb <= Y) & (wd > Y))[0]; t = cKDTree(wxy[alive])
    ts = []
    for F in S[:400].tolist():
        a = time.perf_counter(); t.query([E.flx[F], E.fly[F]]); ts.append(time.perf_counter() - a)
    out['ego_ms_mean'] = round(float(np.mean(ts)) * 1000, 4)
    out['seconds'] = round(time.perf_counter() - t0, 3)
    json.dump(out, open(os.path.join(HERE, 'out', 'ledger_house.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
