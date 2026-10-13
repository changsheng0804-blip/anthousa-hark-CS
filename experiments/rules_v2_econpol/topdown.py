"""规则预演 v2 · 反过来推演：自上而下从账本总量分配到 机构 → 中间节点 → 户，再与自下而上（v1/骨架）对账。

账本输入（只读，不改）：
  docs/data.json eras[].stats（每十年末：人口、粮食上限、水的上限、房屋）——与 world.json / chronicle 同源
  world.json houses（每栋房子的街区 d、建/拆年）→ 各街区房屋数、各年拆房数
  chronicle/41_50.md、51_60.md、61_70.md 里写明的数（年份 + 数）：粮食/水上限升级的年份，干山 60 年的户数、人数、挤屋户、缺男丁户、运水人家
推不出的量一律标「假设」（见 ASSUME）。
usage: python3 topdown.py        （跑干山 + 全城合成，写 out/topdown.json）
"""
import os, sys, json, collections, math, time
import numpy as np
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import econpol as EP  # noqa: E402
from reproduce import Repro  # noqa: E402
import data as D0  # noqa: E402  (rules_v0 数据层，只读)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# ---------------- 账本（城市总量）
ERAS = {e['to']: e['stats'] for e in json.load(open(os.path.join(ROOT, 'docs', 'data.json')))['eras']}
LEDGER = {Y: dict(pop=ERAS[Y]['population'], food=ERAS[Y]['food'], water=ERAS[Y]['water'], houses=ERAS[Y]['houses']) for Y in (40, 50, 60, 70)}
# 上限升级的年份（chronicle 原文）：粮 46 年 173,202（41_50.md:11）、55 年 193,202（51_60.md）；水 41 年 173,000（41_50.md:5）、54 年 188,000（51_60.md）、62 年 203,000（61_70.md:7）
def food_cap(Y): return 193202 if Y >= 55 else 173202 if Y >= 46 else 153202
def water_cap(Y): return 203000 if Y >= 62 else 188000 if Y >= 54 else 173000 if Y >= 41 else 158000
CISTERN_GAIN = 15000          # 每座新蓄水池让水的上限 +15,000（41/54/62 三次，账本差分）
# 干山 60 年（chronicle/61_70.md:3,5,7,9）
XERO_AF60 = dict(households=4383, people=23912, crowded_10plus=469, needy_under14=615, carrier_households=742, sons_turning_18_in_61_70=3373)
# 拆房（chronicle + world.json）：54 运水人蓄水池 17；57 狄奥多西广场 29（d_forum）；61–62 台阶路 40 + 第二座蓄水池 15；65 寡妇孤儿之家 13
ASSUME = {
    'T1 人口按房屋分': '城→街区按账本房屋数等分人口（账本没有分街区人口）',
    'T2 配给按房屋': '君士坦丁的房屋面包：每栋账本房屋一本配给簿，口粮 = 粮食上限 ÷ 账本房屋数（账本没有配给量，粮食只有上限）',
    'T2b 簿给谁': '一条街上的配给簿给这条街住得最久的人家（与规则 A「有房 = 41 年前的首户」同精神，但数目由账本房屋数定）',
    'T3 蓄水池容量': '每座蓄水池容量 = 它让水的上限增加的 15,000 人（账本差分）；井的容量账本没有',
    'T4 施舍': '账本没有施舍量；只按教派与年份（49/51/64/65）分有无',
    'T5 征工': '57 年征工总数账本没有：用自下而上的总数，只比较按街分配的方式（每街 2 户 vs 按街户数比例）',
    'T6 修水凑铜板': '凑铜板的金额账本没有；只比较出钱户数',
    'T7 兵营': '账本没有兵员数；不做自上而下',
    'T8 年内插值': '账本只有每十年末的总量，十年内按线性插值（只用于人口）',
}


def lerp_pop(Y):
    a = (Y // 10) * 10; b = a + 10
    if Y % 10 == 0: return LEDGER[Y]['pop']
    return LEDGER[a]['pop'] + (LEDGER[b]['pop'] - LEDGER[a]['pop']) * (Y - a) / 10


def world_houses():
    W = json.load(open(os.path.join(ROOT, 'world.json')))
    return W['houses']


def standing(h, Y): return h['built'] <= Y and (h['destroyed'] is None or h['destroyed'] > Y)


def city_level(WH):
    """城 → 街区：账本房屋数、人口按房屋等分（T1） vs 全城合成人家（自下而上，同一 household() 推演跑在全城房子上）。"""
    P = json.load(open(os.path.join(EP.V0, 'rules.json')))
    E = EP.EconPol('city', P, 'v1'); M = E.M
    dmap = {h['id']: h['d'] for h in WH}
    fd = np.array([dmap.get(M['hid'][i], '?') for i in M['fh']])
    out = {}
    for Y in (50, 55, 60, 65, 70):
        yi = Y - E.YR0; pr = M['present'][:, yi]
        hd = collections.Counter(h['d'] for h in WH if standing(h, Y)); Htot = sum(hd.values())
        pop_td = lerp_pop(Y)
        bu = collections.Counter(); bh = collections.Counter()
        for d, s in zip(fd[pr].tolist(), M['size'][pr, yi].tolist()): bu[d] += s; bh[d] += 1
        rows = {}
        for d in sorted(hd):
            td = pop_td * hd[d] / Htot
            rows[d] = dict(houses_ledger=hd[d], pop_td=round(td), pop_bu=int(bu[d]), households_bu=int(bh[d]), diff=int(bu[d] - round(td)), ratio=round(bu[d] / td, 3) if td else None)
        own_bu = int((E.owner & pr).sum())
        out[Y] = dict(pop_ledger=round(pop_td), pop_bu=int(M['size'][pr, yi].sum()), houses_ledger=Htot,
                      houses_bu=int(((M['hbuilt'] <= Y) & (M['hdest'] > Y)).sum()), households_bu=int(pr.sum()),
                      ration_books_td=Htot, owner_households_bu=own_bu, food_cap=food_cap(Y), water_cap=water_cap(Y),
                      food_per_head_ledger=round(food_cap(Y) / pop_td, 3), by_district=rows)
    dest_bu = collections.Counter(M['hdest'][(M['hdest'] >= 40) & (M['hdest'] <= 70)].tolist())
    return out, {int(k): int(v) for k, v in sorted(dest_bu.items())}


def xero_level(WH):
    P = json.load(open(os.path.join(EP.V0, 'rules.json')))
    E = Repro('xero', P, 2, 300); M = E.M; out = {}
    # ---------- 干山 60 年：账本（chronicle）写明的数 vs 页面推演
    W = D0.load_xero()
    Y = 60; ppl_kids14 = collections.Counter(); sons = 0
    fam_index = {}
    for h in W['houses']:
        for j, f in enumerate(h['fams']):
            nxt = h['fams'][j + 1]['B'] if j + 1 < len(h['fams']) else 10 ** 6
            if not (f['B'] <= Y < nxt and h['built'] <= Y < h['destroyed']): continue
            home = [p for p in f['people'] if D0.home(p, Y)]
            if not home: continue
            men = sum(1 for p in home if p['s'] == 'm' and Y - p['b'] >= 16)
            k14 = sum(1 for p in home if Y - p['b'] < 14)
            ppl_kids14['needy14'] += (men == 0 and k14 > 0)
            sons += sum(1 for p in home if p['s'] == 'm' and 8 <= Y - p['b'] <= 17)
    yi = Y - E.YR0; pr = M['present'][:, yi]
    carriers = int((pr & (M['ft'] == E.carrier_t)).sum())
    out['af60_check'] = dict(
        households=[XERO_AF60['households'], int(pr.sum())], people=[XERO_AF60['people'], int(M['size'][pr, yi].sum())],
        crowded_10plus=[XERO_AF60['crowded_10plus'], int((pr & (M['size'][:, yi] >= 10)).sum())],
        needy_under14=[XERO_AF60['needy_under14'], int(ppl_kids14['needy14'])],
        needy_under12_rule=[None, int((pr & (M['men'][:, yi] == 0) & (M['kids'][:, yi] > 0)).sum())],
        carrier_households=[XERO_AF60['carrier_households'], carriers],
        sons_turning_18_in_61_70=[XERO_AF60['sons_turning_18_in_61_70'], sons],
        houses=[sum(1 for h in WH if h['d'] == 'd_xerolophos' and standing(h, 60)), int(((M['hbuilt'] <= 60) & (M['hdest'] > 60)).sum())])
    # ---------- 拆房：账本（world.json d_xerolophos）vs 页面
    led = collections.Counter(h['destroyed'] for h in WH if h['d'] == 'd_xerolophos' and h['destroyed'] is not None and 40 <= h['destroyed'] <= 70)
    pg = collections.Counter(M['hdest'][(M['hdest'] >= 40) & (M['hdest'] <= 70)].tolist())
    out['demolitions'] = dict(ledger={int(k): v for k, v in sorted(led.items())}, page={int(k): int(v) for k, v in sorted(pg.items())})
    # ---------- 世界房屋 → 页面坐标 → 页面街（每年）
    Mx = D0._affine()
    xw = [h for h in WH if h['d'] == 'd_xerolophos']
    wxy = np.array([D0._T(Mx, *(np.mean(np.array(h['p']), 0))) for h in xw])
    hx, hy = M['hlx'], M['hly']          # 仿射的目标是页面坐标（与蓄水池同一坐标系）
    dmap_, _ = cKDTree(wxy).query(np.c_[hx, hy])
    out['map_check'] = dict(page_house_to_nearest_ledger_house_px=dict(p50=round(float(np.median(dmap_)), 1), p90=round(float(np.percentile(dmap_, 90)), 1)),
                            ledger_x_range=[round(float(np.percentile(wxy[:, 0], 1))), round(float(np.percentile(wxy[:, 0], 99)))],
                            page_x_range=[round(float(np.percentile(hx, 1))), round(float(np.percentile(hx, 99)))])
    res_years = {}
    for Y in (50, 55, 60, 65, 70):
        yi = Y - E.YR0; pr = M['present'][:, yi]; S = np.nonzero(pr)[0]
        Hx = sum(1 for h in xw if standing(h, Y)); Hc = sum(1 for h in WH if standing(h, Y))
        pop = lerp_pop(Y)
        # 人口（T1）
        pop_td = pop * Hx / Hc; pop_bu = int(M['size'][pr, yi].sum())
        # 配给（T2）：口粮/账本房屋 × 干山账本房屋；自下而上：有房户（规则 A）的人
        per_house = food_cap(Y) / Hc
        own = E.owner[S]; size = M['size'][S, yi]
        ration_td = per_house * Hx; fed_bu = int(size[own].sum())
        # 每条街：配给簿 td = 落在这条街的账本房屋数；bu = 这条街的有房户数
        st_y = M['hstreet'][M['fh'][S], yi]
        # 账本房屋落不到页面街上（仿射后页面房子到最近账本房屋的距离中位数 >500px，见 map_check），
        # 所以 td 的簿数按街户数比例分（最大余数法），总数 = 干山账本房屋数
        hs_ = collections.Counter(st_y.tolist()); Ntot = sum(hs_.values())
        quota = {s_: Hx * c / Ntot for s_, c in hs_.items()}
        td_books = collections.Counter({s_: int(math.floor(q)) for s_, q in quota.items()})
        for s_ in sorted(quota, key=lambda s_: -(quota[s_] - math.floor(quota[s_])))[:Hx - sum(td_books.values())]: td_books[s_] += 1
        bu_books = collections.Counter(st_y[own].tolist())
        # T2b：每条街把 td 簿数给住得最久的人家 → 与 bu（有房户）逐户比
        B = M['fB'][S]; kr = E.keyrank[S]
        td_has = np.zeros(len(S), bool)
        for s_ in set(st_y.tolist()):
            idx = np.nonzero(st_y == s_)[0]
            k = td_books.get(s_, 0)
            if k: td_has[idx[np.lexsort((kr[idx], B[idx]))][:k]] = True
        both = int((td_has & own).sum()); only_td = int((td_has & ~own).sum()); only_bu = int((~td_has & own).sum())
        streets = []
        for s_ in set(td_books) | set(bu_books):
            nm = M['st_names'][s_] if s_ >= 0 else '（无街名）'
            streets.append(dict(street=nm, households=int((st_y == s_).sum()), books_td=td_books.get(s_, 0), books_bu=bu_books.get(s_, 0), diff=bu_books.get(s_, 0) - td_books.get(s_, 0)))
        streets.sort(key=lambda r: -abs(r['diff']))
        # 蓄水池（T3）
        R = E.year_ep(Y); wsrc = E.water_src(R['Yd'])
        cis = {}
        for w_i, w in enumerate(E.water):
            if w['kind'] != 'cistern' or w['built'] > Y: continue
            users = wsrc == w_i
            cis[w['id']] = dict(built=w['built'], households_bu=int(users.sum()), people_bu=int(R['size'][users].sum()), capacity_td=CISTERN_GAIN)
        wells_people = int(R['size'][(wsrc >= 0) & E.wwell[np.maximum(wsrc, 0)]].sum()); nowater = int(R['size'][wsrc < 0].sum())
        # 施舍（T4）
        needy = R['Yd']['needy']; faith = R['Yd']['faith']
        alms = dict()
        for fn, f in (('阿里乌派', 0), ('尼西亚派', 1), ('还拜旧神', 2)):
            m = needy & (faith == f)
            alms[fn] = dict(needy=int(m.sum()), with_alms=int((m & (R['alms_src'] != '')).sum()))
        # 房东（td：一栋账本房屋一个房东）
        L = R['landlord']; ten = ~own
        landlords_bu = len(set(L[L >= 0].tolist())); ten_no_ll = int((ten & (L < 0)).sum())
        res_years[Y] = dict(houses_ledger_xero=Hx, houses_ledger_city=Hc, households_bu=int(len(S)),
                            pop_td=round(pop_td), pop_bu=pop_bu, pop_ratio=round(pop_bu / pop_td, 2),
                            ration_per_ledger_house=round(per_house, 2), rations_td=round(ration_td), fed_people_bu=fed_bu, people_without_house_bread_bu=int(pop_bu - fed_bu),
                            ration_books_td=Hx, owner_households_bu=int(own.sum()),
                            per_household_bread=dict(both=both, td_only=only_td, bu_only=only_bu, neither=int(len(S) - both - only_td - only_bu)),
                            streets_worst=streets[:8], streets_count=len(streets), streets_exact=sum(1 for r in streets if r['diff'] == 0),
                            cisterns=cis, people_on_wells_bu=wells_people, people_without_water_source_bu=nowater,
                            alms=alms, landlords_td=Hx, landlords_bu=landlords_bu, tenants_bu=int(ten.sum()), tenants_without_landlord_bu=ten_no_ll,
                            tenants_per_landlord_td=round(int(ten.sum()) / Hx, 2), tenants_per_landlord_bu=round((int(ten.sum()) - ten_no_ll) / max(landlords_bu, 1), 2))
    out['years'] = res_years
    # ---------- 征工（T5）：57 年，每街 2 户 vs 按街户数比例
    Y = 57; R = E.year_ep(Y); Yd = R['Yd']; st = Yd['st']
    cor = R['ev']['corvee']; total = int(cor.sum())
    elig = ~Yd['own'] & (R['men'] >= 1) & (st >= 0)
    hs = collections.Counter(st[st >= 0].tolist()); Ntot = sum(hs.values())
    rows = []
    for s_, nh in hs.items():
        td = total * nh / Ntot; bu = int((cor & (st == s_)).sum())
        rows.append(dict(street=E.M['st_names'][s_], households=nh, eligible=int((elig & (st == s_)).sum()), corvee_bu=bu, corvee_td=round(td, 2), diff=round(bu - td, 2)))
    rows.sort(key=lambda r: r['diff'])
    big = [r for r in rows if r['households'] >= 40]
    out['corvee_57'] = dict(total=total, streets=len(rows), streets_with_eligible=sum(1 for r in rows if r['eligible'] > 0),
                            most_under_drafted=rows[:5], most_over_drafted=rows[-5:], big_streets_bu_share=round(sum(r['corvee_bu'] for r in big) / max(total, 1), 3),
                            big_streets_household_share=round(sum(r['households'] for r in big) / Ntot, 3))
    # ---------- 修水凑铜板（T6）
    lev = {}
    for Y in (54, 62):
        R = E.year_ep(Y); lev[Y] = dict(contributors_bu=int(R['ev']['levy'].sum()),
                                        carriers_present_bu=int((R['Yd']['trade'] == E.carrier_t).sum()))
    out['levy'] = lev
    return out


def main():
    t0 = time.time()
    WH = world_houses()
    city, dest_city = city_level(WH)
    xero = xero_level(WH)
    led_dest = collections.Counter(h['destroyed'] for h in WH if h['destroyed'] is not None and 40 <= h['destroyed'] <= 70)
    res = dict(assumptions=ASSUME, ledger=LEDGER, city=city, city_demolitions=dict(ledger={int(k): v for k, v in sorted(led_dest.items())}, synthetic=dest_city),
               xero=xero, seconds=round(time.time() - t0, 2))
    json.dump(res, open(os.path.join(HERE, 'out', 'topdown.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(af60=xero['af60_check'], demol=xero['demolitions'], city_dem=res['city_demolitions'],
                          city60={k: v for k, v in city[60].items() if k != 'by_district'}, city70={k: v for k, v in city[70].items() if k != 'by_district'},
                          city60_districts=city[60]['by_district'], x60={k: v for k, v in xero['years'][60].items() if k not in ('streets_worst',)},
                          corvee=xero['corvee_57'], levy=xero['levy'], sec=res['seconds']), ensure_ascii=False, indent=0))


if __name__ == '__main__':
    main()
