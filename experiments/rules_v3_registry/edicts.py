"""规则预演 v3 · 政令下行、诉求上行：用账本 AF51–70 的事件在户籍 + 治理树上跑一遍，并与 v2 / 账本对账。

政令（下行，城市长官或主教 → 区长 → 坊长 → 房主 → 户）：
  51 阿里乌派被请出城里教堂（教会树）· 54 运水人蓄水池（拆房 + 凑铜板）· 55 亚历山大粮仓（每本簿口粮变多）
  57 狄奥多西广场（征工 140 户，按树分配；广场拆房）· 62 台阶路 + 第二座蓄水池（拆房 + 上坡人家凑铜板）
  64 城门外砖堂（教会树）· 65 寡妇孤儿之家（拆房 + 施舍不分派）
诉求（上行，户 → 房主 → 坊长 → 区长 → 城市长官；信仰走教会树）：
  chronicle/61_70.md 写明被采纳的四份请愿（drafts/proposals_af61_70/ 的 1 水、2 挤、4 信仰、5 孤寡；3 防火巷没被采纳）
拆房按**账本**（world.json 每栋房屋的拆毁年）落到登记在那栋账本房屋上的人家（页面上 57/62/65 年没有拆房，v2 已知问题 #4）。
usage: python3 edicts.py [xero|city]
"""
import os, sys, json, time, collections, math
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import registry as RG  # noqa: E402

CORVEE_TOTAL = 140            # v2：57 年征工总数（自下而上，账本没有，假设 T5）
LEDGER_YEARS = {'水': (60, 62), '挤': (60, 63), '信仰': (60, 64), '孤寡': (60, 65)}   # chronicle/61_70.md：60 年提出，建成年


def evictions(G, years, Y):
    """账本 Y 年拆掉的房屋 → 前一年登记在那里的在住户被拆（迁籍到 Y 年的登记房屋）。"""
    if Y - 1 not in years or Y not in years: return dict(houses=0, households=[], people=0)
    Rp = years[Y - 1]; dest = G.WL['dest'][Rp['rh']]
    m = dest == Y
    hh = Rp['S'][m]
    R = years[Y]; loc = R['loc']
    still = loc[hh] >= 0
    new_rh = np.where(still, R['rh'][np.maximum(loc[hh], 0)], -1)
    page_gone = (~still).sum()
    return dict(houses=int(len(np.unique(Rp['rh'][m]))), households=hh.tolist(), people=int(Rp['size'][m].sum()),
                owners=int(Rp['own'][m].sum()), page_also_gone=int(page_gone), moved_to=new_rh.tolist(),
                districts=dict(collections.Counter(RG.DNAME[G.dnames[d]] for d in Rp['dist'][m].tolist())),
                fang=sorted(set(Rp['fang'][m].tolist())), faith=dict(collections.Counter(RG.FAITHS[f] for f in Rp['faith'][m].tolist())))


def corvee(G, R, total=CORVEE_TOTAL):
    """按树分配：城市长官 → 各区按户数（最大余数）→ 各坊按户数（最大余数）→ 坊长在本坊点名：
    先点有成年男人的租户、再点成年男人 ≥2 的房主，各按成年男人多→户键（假设 G3）；本坊够格的不够，余额顺给同区下一个坊。"""
    S, n = R['S'], len(R['S']); men = R['men']; own = R['own']; kr = G.keyrank[S]
    def lr(weights, tot):
        w = np.asarray(weights, float); q = tot * w / max(w.sum(), 1); fl = np.floor(q).astype(int)
        for i in np.argsort(-(q - fl), kind='stable')[:tot - fl.sum()]: fl[i] += 1
        return fl
    dl = sorted(set(R['dist'].tolist())); dq = lr([int((R['dist'] == d).sum()) for d in dl], total)
    pick = np.zeros(n, bool); fang_q = {}
    elig = ((~own) & (men >= 1)) | (own & (men >= 2))
    pri = np.where(~own, 0, 1)
    for d, qd in zip(dl, dq):
        fl = sorted(set(R['fang'][R['dist'] == d].tolist())); fq = lr([int((R['fang'] == f).sum()) for f in fl], int(qd))
        carry = 0
        for f, qf in zip(fl, fq):
            idx = np.nonzero((R['fang'] == f) & elig)[0]
            idx = idx[np.lexsort((kr[idx], -men[idx], pri[idx]))]
            k = min(len(idx), int(qf) + carry); carry = int(qf) + carry - k
            pick[idx[:k]] = True; fang_q[f] = (int(qf), k)
    return pick, fang_q


def levy(G, R, Y):
    """修水凑铜板（v0/v1 规则 office.levy，只读复用）：运水人家（62 年再加上坡人家），离新蓄水池 400 页面像素以内。"""
    name = G.P['office']['levy_years'].get(str(Y)); c = next((w for w in G.water if w['id'] == name), None)
    if c is None: return np.zeros(len(R['S']), bool)      # 全城合成水源没有这座池子的名字：不做
    lx, ly = G.flx[R['S']], G.fly[R['S']]
    d = np.hypot(c['x'] - lx, c['y'] - ly)
    return (d <= G.P['office']['levy_radius']) & ((R['trade'] == G.carrier_t) | ((Y == 62) & (ly < c['y'])))


def path_nodes(G, R, mask, top='prefect', adopt_district=None):
    """一批户（mask）沿民政树往上：经过的 房主、坊长、区长（去重）以及是否到城市长官。
    adopt_district：在某个区长那里被采纳（别的区的户要经城市长官转到那个区，最近公共上级）。"""
    S = R['S']; idx = np.nonzero(mask)[0]
    owners = set(R['owner'][idx][~R['own'][idx]].tolist())          # 租户要先经过房主
    fangs = set(R['fang'][idx].tolist()); dists = set(R['dist'][idx].tolist())
    hops_each = np.where(R['own'][idx], 0, 1) + 2                     # 户→(房主)→坊长→区长
    reach_top = top == 'prefect' or (adopt_district is not None and any(d != adopt_district for d in dists))
    if top == 'prefect': hops_each = hops_each + 1
    elif adopt_district is not None: hops_each = hops_each + np.where(R['dist'][idx] != adopt_district, 2, 0)   # 区长→城市长官→采纳区长
    nodes = len(owners) + len(fangs) + len(dists) + (1 if reach_top else 0) + (1 if (adopt_district is not None and reach_top) else 0)
    return dict(households=int(len(idx)), people=int(R['size'][idx].sum()), via_owner_houses=len(owners), fang_heads=len(fangs), district_heads=len(dists),
                reaches_prefect=bool(reach_top), relay_nodes=nodes, messages_no_aggregation=int(hops_each.sum()),
                messages_tree_aggregated=int(len(idx) + len(owners) + len(fangs) + len(dists) + (1 if reach_top else 0)),
                levels=int(hops_each.max()) if len(idx) else 0)


def water_source(G, R, Y):
    """喝哪口水（v0/v1 规则 1：井 140px，否则蓄水池 420px），用来看第二座蓄水池修好后谁换了水源。"""
    D = G.water; x = G.M['hx'][G.fh[R['S']]]; y = G.M['hy'][G.fh[R['S']]]; lx, ly = G.flx[R['S']], G.fly[R['S']]
    wx = np.array([w['x'] for w in D]); wy = np.array([w['y'] for w in D]); wb = np.array([w['built'] for w in D]); ww = np.array([w['kind'] == 'well' for w in D])
    n = len(x); src = np.full(n, -1)
    wm = np.nonzero(ww & (wb <= Y))[0]
    dd = np.hypot(wx[wm][None] - x[:, None], wy[wm][None] - y[:, None]); j = dd.argmin(1); ok = dd[np.arange(n), j] <= G.P['water']['well_reach']
    src[ok] = wm[j[ok]]
    cm = np.nonzero(~ww & (wb <= Y))[0]; rest = np.nonzero(src < 0)[0]
    dc = np.hypot(wx[cm][None] - lx[rest, None], wy[cm][None] - ly[rest, None]); j = dc.argmin(1); ok = dc[np.arange(len(rest)), j] <= G.P['water']['cistern_reach']
    src[rest[ok]] = cm[j[ok]]
    return src, [w['id'] for w in D]


def main(scope='xero'):
    t0 = time.time()
    G = RG.Registry(scope); years, tb = G.build(48, 70)
    out = dict(scope=scope, edicts={}, petitions={}, reconcile={})
    E = out['edicts']
    # ---------- 51 阿里乌派被请出教堂（教会树：主教 → 教区 → 教区长老 → 户）
    a, b = years[50], years[51]
    ar = b['faith'] == RG.ARIAN
    lost = int((a['alms'] & (a['faith'] == RG.ARIAN)).sum())
    E['51 阿里乌派被请出城里教堂'] = dict(tree='教会', path='皇帝诏 → 阿里乌派主教（失去城里教堂）→ 教区（城里的阿里乌派教堂 → 51 年无处、52 起城外木院）→ 教区长老 → 户',
        households=int(ar.sum()), people=int(b['size'][ar].sum()), parish_nodes_changed=1, elders=int((b['offices']['elder'][0::3] >= 0).sum()),
        needy14_lost_alms=lost, needy14_arian_51=int((b['needy'] & ar).sum()), levels=4, ledger='chronicle 51_60：51 年皇帝下诏只认尼西亚派，年底阿里乌派被请出城里所有的教堂')
    # ---------- 拆房（账本）
    for Y, site in ((54, '运水人蓄水池'), (57, '狄奥多西广场'), (62, '台阶路 + 第二座运水人蓄水池'), (65, '寡妇孤儿之家')):
        ev = evictions(G, years, Y); Rp = years[Y - 1]
        hh = np.array(ev['households'], np.int64); m = np.isin(Rp['S'], hh)
        p = path_nodes(G, Rp, m)
        led_total = int((G.WL['dest'] == Y).sum()); led_x = int(((G.WL['dest'] == Y) & (G.WL['d'] == 'd_xerolophos')).sum())
        E[f'{Y} 拆房：{site}'] = dict(tree='民政', ledger_houses_demolished_city=led_total, ledger_houses_demolished_xerolophos=led_x,
            ledger_houses_in_page_area=ev['houses'], households_evicted=len(hh), people=ev['people'], owners_evicted=ev['owners'],
            page_also_demolished=ev['page_also_gone'], districts=ev['districts'], faith=ev['faith'],
            re_registered_to=len(set(x for x in ev['moved_to'] if x >= 0)), relay=p, levels=p['levels'])
    # ---------- 凑铜板
    for Y in (54, 62):
        R = years[Y]; m = levy(G, R, Y); p = path_nodes(G, R, m)
        E[f'{Y} 修水凑铜板'] = dict(tree='民政', households=int(m.sum()), carriers=int((m & (R['trade'] == G.carrier_t)).sum()), relay=p,
                                v2_households={54: 70, 62: 380}[Y])
    # ---------- 55 粮仓：每本簿口粮 173,202/H → 193,202/H
    a, b = years[54], years[55]
    common = np.intersect1d(a['S'], b['S'])
    fa = a['fed'][a['loc'][common]]; fb = b['fed'][b['loc'][common]]
    E['55 亚历山大粮仓：口粮增加'] = dict(tree='民政（配给：城市长官 → 区 → 面包簿 → 屋里的户）', portions_per_book=[round(a['q'], 2), round(b['q'], 2)],
        books=[int(a['own'].sum()), int(b['own'].sum())], households_more_bread=int((fb > fa + 1e-9).sum()), people_newly_fed=round(float((fb - fa).clip(0).sum())),
        households_unfed_before=int((a['fed'] <= 0).sum()), households_unfed_after=int((b['fed'] <= 0).sum()), levels=4)
    # ---------- 57 征工
    R = years[57]; pick, fq = corvee(G, R)
    st = G.M['hstreet'][G.fh[R['S']], 57 - G.YR0]
    hs = collections.Counter(st[st >= 0].tolist()); Nt = sum(hs.values())
    big = [s for s, c in hs.items() if c >= 40]
    p = path_nodes(G, R, pick)
    E['57 狄奥多西广场：征工'] = dict(tree='民政（征工组 = 坊）', total=int(pick.sum()), total_v2=CORVEE_TOTAL, fang_short=sum(1 for q, k in fq.values() if k < q),
        tenants=int((pick & ~R['own']).sum()), owners=int((pick & R['own']).sum()),
        big_streets_share=round(sum(int((pick & (st == s)).sum()) for s in big) / max(int(pick.sum()), 1), 3), big_streets_household_share=round(sum(hs[s] for s in big) / Nt, 3),
        v2_big_streets_share=0.386, faith=dict(collections.Counter(RG.FAITHS[f] for f in R['faith'][pick].tolist())),
        faith_households=dict(collections.Counter(RG.FAITHS[f] for f in R['faith'].tolist())),
        per_fang_ratio=dict(min=round(min(k / max((R['fang'] == f).sum(), 1) for f, (q, k) in fq.items()), 4), max=round(max(k / max((R['fang'] == f).sum(), 1) for f, (q, k) in fq.items()), 4)),
        relay=p, levels=4)
    # ---------- 64 砖堂、65 孤寡院（施舍）
    a, b = years[63], years[64]
    E['64 城门外砖堂'] = dict(tree='教会', arian_households=int((b['faith'] == RG.ARIAN).sum()), parish='城外木院 → 城门外砖堂',
        needy14_regain_alms=int((b['alms'] & ~np.isin(b['S'], a['S'][a['alms']])).sum()), levels=3)
    a, b = years[64], years[65]
    newly = b['alms'] & ~np.isin(b['S'], a['S'][a['alms']])
    E['65 寡妇孤儿之家：施舍不分派'] = dict(tree='教会 → 机构（寡妇孤儿之家，挂区）', needy14=int(b['needy'].sum()), newly_alms=int(newly.sum()),
        newly_by_faith=dict(collections.Counter(RG.FAITHS[f] for f in b['faith'][newly].tolist())), levels=3)
    # ---------- 诉求上行（60 年提出）
    R = years[60]; P_ = out['petitions']
    xd = G.dnames.index('d_xerolophos')
    pres = dict(水=R['trade'] == G.carrier_t, 挤=R['size'] >= 10, 孤寡=R['needy'], 信仰=R['faith'] == RG.ARIAN)
    adopt = dict(水=('城市长官', 'prefect', None), 挤=('城市长官', 'prefect', None), 孤寡=('干山区区长（与尼西亚派修士合办）', 'district', xd), 信仰=('阿里乌派主教（教会树）', 'church', None))
    for k, m in pres.items():
        lvl, top, ad = adopt[k]
        if top == 'church':
            S = R['S'][m]; fangs = set(R['fang'][m].tolist()); el = R['offices']['elder'][np.array(sorted(fangs)) * 3 + RG.ARIAN]
            p = dict(households=int(m.sum()), people=int(R['size'][m].sum()), elders=int(len(set(el[el >= 0].tolist()))), parish=1, bishop=1,
                     messages_no_aggregation=int(m.sum()) * 3, messages_tree_aggregated=int(m.sum()) + len(set(el[el >= 0].tolist())) + 1, levels=3)
        else:
            p = path_nodes(G, R, m, top=top, adopt_district=ad)
        y0, y1 = LEDGER_YEARS[k]
        P_[k] = dict(adopted_at=lvl, relay=p, ledger_years=f'{y0} 提出 → {y1} 建成（{y1 - y0} 年）', petitioners_by_district=dict(collections.Counter(RG.DNAME[G.dnames[d]] for d in R['dist'][m].tolist())))
    # 结果落到户
    s61, ids = water_source(G, years[61], 61); s62, _ = water_source(G, years[62], 62)
    ci = ids.index('第二座运水人蓄水池') if '第二座运水人蓄水池' in ids else -2
    P_['水']['outcome'] = dict(households_switch_to_new_cistern_62=int((s62 == ci).sum()), people=int(years[62]['size'][s62 == ci].sum()),
                              demolished_for_it=E['62 拆房：台阶路 + 第二座运水人蓄水池']['households_evicted'])
    P_['挤']['outcome'] = dict(households_moved_out=0, note='页面家谱 61 年后不再有人搬来/搬走（MAXY=60），城墙外新区 63 年起的 531 栋账本房屋没有人家；户籍上无人迁出（缺口）')
    P_['孤寡']['outcome'] = dict(newly_alms_65=E['65 寡妇孤儿之家：施舍不分派']['newly_alms'], demolished_for_it=E['65 拆房：寡妇孤儿之家']['households_evicted'])
    P_['信仰']['outcome'] = dict(parish_changed_households=E['64 城门外砖堂']['arian_households'], needy_regain_alms=E['64 城门外砖堂']['needy14_regain_alms'])
    # ---------- 对账
    R = years[60]
    own = R['own']; ll = R['owner'][~own]
    out['reconcile'] = dict(
        households_people_60=[int(len(R['S'])), int(R['size'].sum()), 'chronicle 4,383 / 23,912'],
        needy14_60=[int(R['needy'].sum()), 'chronicle 615（v2 规则 12 岁口径 532）'],
        carriers_60=[int((R['trade'] == G.carrier_t).sum()), 'chronicle 742'], crowded10_60=[int((R['size'] >= 10).sum()), 'chronicle 469'],
        arian_60=[int((R['faith'] == RG.ARIAN).sum()), 'drafts README 2,435'],
        ledger_houses_page_area_60=int(own.sum()), people_per_ledger_house=round(int(R['size'].sum()) / int(own.sum()), 2),
        city_people_per_ledger_house_60=round(149193 / 16577, 2),
        books_60=dict(registry=int(own.sum()), v2_owner_households=2240, v2_ledger_xero=746),
        landlords_60=dict(registry_owners_with_tenants=int(len(set(ll.tolist()))), tenants=int((~own).sum()), v2_landlords=380, v2_tenants_per_landlord=5.18),
        bread_60=dict(portions=round(R['q'] * int(own.sum())), people=int(R['size'].sum()), fed=int(np.round(R['fed']).sum()),
                      unfed_people=int(R['size'].sum() - np.round(R['fed']).sum()), v2_fed=12912))
    out['seconds'] = round(time.time() - t0, 2)
    json.dump(out, open(os.path.join(HERE, 'out', f'edicts_{scope}.json'), 'w'), ensure_ascii=False, indent=1, default=int)
    print(json.dumps(out, ensure_ascii=False, indent=0, default=int)[:6000])


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'xero')
