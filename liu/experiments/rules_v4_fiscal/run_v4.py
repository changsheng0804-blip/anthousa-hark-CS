"""规则预演 v4 · 财政层主程序：财政流（逐级守恒）+ 与账本对账 + 四份请愿的资金路径 + 偏袒可测化 + 计算量。
usage: python3 run_v4.py xero|city [--bench]
输出 out/fiscal_<scope>.json
"""
import os, sys, json, time, resource, collections, gzip, math
T0 = time.time()
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fiscal as FI  # noqa: E402
RG = FI.RG
T_IMPORT = time.time() - T0
ROOT = FI.ROOT
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
Y0, Y1 = 51, 70


def ledger_series():
    """账本逐年：站着的房屋、人口（房屋 × 9，engine/rules.population）、粮食上限、供水上限（calibration：基数 8,000 + 蓄水池 15,000 + 水道 100,000，结构自带 capacity 优先）、拆房。"""
    W = json.load(open(os.path.join(ROOT, 'world.json'))); cal = json.load(open(os.path.join(ROOT, 'rules', 'calibration.json')))
    out = {}
    for Y in range(40, 71):
        st = [h for h in W['houses'] if h['built'] <= Y and (h['destroyed'] is None or h['destroyed'] > Y)]
        ss = [s for s in W['structures'] if s['built'] <= Y and (s.get('destroyed') is None or s['destroyed'] > Y)]
        water = cal['water']['base'] + sum(s.get('capacity', cal['water'][s['type']]) for s in ss if s['type'] in ('cistern', 'aqueduct'))
        out[Y] = dict(houses=len(st), people=len(st) * cal['people_per_house']['value'], food=RG.food_cap(Y), water=water,
                      demolished=sum(1 for h in W['houses'] if h['destroyed'] == Y))
    return out


def reconcile(X, F, L):
    rows = {}
    for Y in range(Y0, Y1 + 1):
        r = F[Y]; T = r['T']; R = X.years[Y]; own = R['own']
        led = L[Y]
        grain = float(T['粮/区']['down'].sum()); books = int(own.sum()); out_h = int(T['粮/页面外账本房屋']['in_above'].sum() / R['q'] + 0.5)
        levy_all = float(r['hh']['levy'].sum() + T['民政/页面外各坊（合计）']['in_below'].sum())
        comp_houses = float(T['民政/区长']['in_above'].sum())
        rows[Y] = dict(
            ledger_people=led['people'], ledger_houses=led['houses'], ledger_food=led['food'], ledger_water=led['water'], ledger_demolished=led['demolished'],
            grain_distributed=round(grain, 3), grain_diff=round(grain - led['food'], 6),
            books_page=books, houses_outside=out_h, houses_diff=books + out_h - led['houses'],
            people_page=int(R['size'].sum()), people_model=int(R['size'].sum()) + 9 * out_h, people_diff=int(R['size'].sum()) + 9 * out_h - led['people'],
            house_tax_total=round(levy_all, 3), house_tax_expected=round(X.P['tau'] * led['houses'], 3),
            demolition_comp_paid=round(comp_houses, 2),
            city_money_in=round(float(T['民政/城市长官']['in_below'][0]), 2), city_remit=round(float(T['民政/城市长官']['up'][0]), 2),
            city_down=round(float(T['民政/城市长官']['down'][0]), 2), city_kept=round(float(T['民政/城市长官']['kept'][0]), 2),
            bread_people_fed=int(round(R['fed'].sum())), bread_surplus_kept_by_owners=round(float(T['粮/面包簿（房主）']['kept'].sum()), 1),
            water_per_person=round(led['water'] / led['people'], 3))
    return rows


# ------------------------------------------------------------------ 四份请愿：资金路径与瓶颈
PETITIONS = {   # 走哪棵树、几层（v3 edicts_xero.json）、谁出钱、花多少（账本建筑 + 账本拆房 × 补偿）、自下而上凑多少
    '水': dict(levels=4, payer='prefect', works=['cistern_slope', 'r_carriers'], demol=55, levy_households=380, petitioners=742, ledger=62),
    '挤': dict(levels=4, payer='prefect', works=['r_exo'], demol=0, levy_households=0, petitioners=469, ledger=63),
    '信仰': dict(levels=3, payer='bishop_arian', works=['church_arian_brick'], demol=0, levy_households=0, petitioners=2435, ledger=64),
    '孤寡': dict(levels=5, payer='district_xero+bishop_nicene', works=['xenon_xerolophos'], demol=13, levy_households=0, petitioners=615, ledger=65),
}
PET_PARAM = dict(t_hop=0.25, build=0.5, raised=60.5)   # 每层转一次 0.25 年（按季开衙，假设）；施工 0.5 年；60 年年中提出


def routine_rates(X, F):
    """各出钱层级 AF61–70 每年「可自由支配的结余」（留存，扣掉账本工程之前）：城市长官、阿里乌派主教、尼西亚派主教、干山区长。"""
    def kept(Y, name, i):
        t = F[Y]['T'][name]; return float(t['kept'][i])
    rates = collections.defaultdict(list)
    for Y in range(61, 71):
        w = F[Y]['works']; add = collections.defaultdict(float)
        for wid, (p, c) in w.items():
            if p.startswith('prefect'): add['prefect'] += c
            elif p == 'bishop_arian': add['bishop_arian'] += c
            elif p.startswith('district_xero'): add['district_xero'] += c / 2; add['bishop_nicene'] += c / 2
        rates['prefect'].append(kept(Y, '民政/城市长官', 0) + add['prefect'] + (float(F[Y]['T']['民政/区长']['in_above'].sum()) if Y in (62, 65) else 0.0))   # 请愿相关的工程与拆房补偿加回
        rates['bishop_arian'].append(kept(Y, '教会/主教', 0) + add['bishop_arian'])
        rates['bishop_nicene'].append(kept(Y, '教会/主教', 1) + add['bishop_nicene'])
        rates['district_xero'].append(kept(Y, '民政/区长', X.xd) + add['district_xero'])
    return {k: float(np.mean(v)) for k, v in rates.items()}


def reserves_51_60(X, F):
    """各出钱层级 51–60 年留存累计（账本工程花掉的已扣）：变体「往年积蓄可以动用」。"""
    k = lambda name, i: sum(float(F[Y]['T'][name]['kept'][i]) for Y in range(51, 61))
    return dict(prefect=k('民政/城市长官', 0), bishop_arian=k('教会/主教', 0), bishop_nicene=k('教会/主教', 1), district_xero=k('民政/区长', X.xd))


def petitions(X, F, pp=None, queue_one_per_year=False, use_reserve=False):
    P = X.P; pp = dict(PET_PARAM, **(pp or {}))
    res0 = reserves_51_60(X, F) if use_reserve else collections.defaultdict(float)
    works = {w['id']: w for w in X.works}
    rates = routine_rates(X, F)
    out = {}; prefect_free = None
    order = sorted(PETITIONS, key=lambda k: (PETITIONS[k]['levels'], -PETITIONS[k]['petitioners']))
    pref_t = None; pref_year_used = set()
    for k in order:
        d = PETITIONS[k]
        build_cost = sum(works[w]['cost'] for w in d['works'])
        comp = d['demol'] * P['comp'] * P['V_h']           # 拆房补偿：城市长官出（与财政流同）
        bottom_up = d['levy_households'] * P['levy']
        relay = d['levels'] * pp['t_hop']; t_app = pp['raised'] + relay
        steps = dict(relay_years=relay)
        if d['payer'] == 'prefect':
            need = max(0.0, build_cost + comp - bottom_up - res0['prefect']); r = rates['prefect']
            if use_reserve: res0['prefect'] = max(0.0, res0['prefect'] - (build_cost + comp - bottom_up))
            start = t_app if pref_t is None else max(t_app, pref_t)          # 城市长官的结余按先后排队（钱）
            fund = need / r; t_done_money = start + fund
            steps.update(queue_wait_years=round(start - t_app, 3), fund_years=round(fund, 3), level_rate=round(r, 1), need=round(need, 1))
            pref_t = t_done_money
            t_done = t_done_money + pp['build']
            if queue_one_per_year:            # 另一种假设：城市长官一年只开一项请愿工程（衙门能力，不是钱）
                yr = math.floor(t_done)
                while yr in pref_year_used: yr += 1
                pref_year_used.add(yr); t_done = max(t_done, yr)
            bott = '城市长官（钱）' if fund > relay else '层层转呈（层级）'
        elif d['payer'] == 'bishop_arian':
            need = max(0.0, build_cost - res0['bishop_arian']); r = rates['bishop_arian']; fund = need / r
            t_done = t_app + fund + pp['build']
            steps.update(fund_years=round(fund, 3), level_rate=round(r, 1), need=round(need, 1))
            bott = '阿里乌派主教（钱）' if fund > relay else '层层转呈（层级）'
        else:
            need = build_cost; r1 = rates['district_xero']; r2 = rates['bishop_nicene']
            fund_half = max(0.0, need / 2 - res0['district_xero']) / r1; fund_joint = max(0.0, need - res0['district_xero'] - res0['bishop_nicene']) / (r1 + r2)     # 各出一半 vs 修士补差
            t_done = t_app + fund_half + pp['build']
            steps.update(fund_years=round(fund_half, 3), fund_years_if_monks_fill=round(fund_joint, 3), level_rate=round(r1, 1), monks_rate=round(r2, 1), need=round(need, 1),
                         predicted_if_monks_fill=math.floor(t_app + fund_joint + pp['build']))
            bott = '干山区长（钱：区一级最薄）' if fund_half > relay else '层层转呈（层级）'
        out[k] = dict(path=d, build_cost=round(build_cost, 1), demolition_comp=round(comp, 1), bottom_up=round(bottom_up, 1), steps=steps,
                      predicted_year=math.floor(t_done), predicted_t=round(t_done, 2), ledger_year=d['ledger'], bottleneck=bott)
    out['_rates'] = {k: round(v, 1) for k, v in rates.items()}
    if use_reserve: out['_reserves_51_60'] = {k: round(v, 1) for k, v in reserves_51_60(X, F).items()}
    return out


# ------------------------------------------------------------------ 偏袒可测化
def benefit(F, X, y0=Y0, y1=Y1):
    """每户 AF51–70 受益（份）：施舍 + 补偿 − 房屋税 − 凑铜板 − 征工人日 × 折价（房租、面包、军饷、行会钱、奉献不受 λ 影响）。"""
    b = np.zeros(X.G.NF)
    parts = {k: np.zeros(X.G.NF) for k in ('alms', 'comp', 'levy', 'cistern', 'corvee')}
    for Y in range(y0, y1 + 1):
        S = X.years[Y]['S']; h = F[Y]['hh']
        for k in parts:
            v = h[k] * (X.P['day'] if k == 'corvee' else 1.0)
            parts[k][S] += v
    b = parts['alms'] + parts['comp'] - parts['levy'] - parts['cistern'] - parts['corvee']
    return b, parts


def head_tenure(X, kind):
    """(节点, 现任户) → 在任年份。kind = fang / district / elder。"""
    ten = collections.defaultdict(list)
    for Y in range(Y0, Y1 + 1):
        arr = X.years[Y]['offices'][kind]
        for node, h in enumerate(arr.tolist()):
            if h >= 0: ten[(node, h)].append(Y)
    return ten


def favoritism(X, lam=0.5, K=12, seed=7):
    G = X.G
    F0 = X.run(Y0, Y1, lam=0.0); F1 = X.run(Y0, Y1, lam=lam)
    b0, p0 = benefit(F0, X); b1, p1 = benefit(F1, X)
    d = b1 - b0
    res = []
    ten = head_tenure(X, 'fang')
    # 每个 (坊, 坊长) 的辖区与亲疏：按在任年份逐年算（户在那年的坊）
    def node_metrics(fang, head, yrs, Fa, Fb):
        ex0 = (None, None); ing = 0.0; outg = 0.0; nin = set(); nout = set(); self_gain = 0.0; skim = 0.0
        lev_in = lev_out = ex_in = ex_out = 0.0; cnt = collections.Counter()
        art_in = art_out = 0.0
        for Y in yrs:
            R = X.years[Y]; idx = np.nonzero(R['fang'] == fang)[0]
            if not len(idx): continue
            a = X.aff(R, head, idx); S = R['S'][idx]; hA = Fa[Y]['hh']; hB = Fb[Y]['hh']
            def ben(h, ii): return h['alms'][ii] + h['comp'][ii] - h['levy'][ii] - h['cistern'][ii] - h['corvee'][ii] * X.P['day']
            db = ben(hB, idx) - ben(hA, idx); b0y = ben(hA, idx)
            isself = S == head; inn = (a > 0) & ~isself; out_ = a == 0
            ing += db[inn].sum(); outg += db[out_].sum(); self_gain += db[isself].sum()
            nin.update(S[inn].tolist()); nout.update(S[out_].tolist())
            art_in += b0y[inn].sum(); art_out += b0y[out_].sum(); cnt['in'] += int(inn.sum()); cnt['out'] += int(out_.sum())
            skim += float(Fb[Y]['T']['民政/坊长']['kept'][fang] - Fa[Y]['T']['民政/坊长']['kept'][fang])
            # 征工豁免（57）
            if Y == 57:
                el = ((~R['own'][idx]) & (R['men'][idx] >= 1)) | (R['own'][idx] & (R['men'][idx] >= 2))
                pk = hB['corvee'][idx] > 0; pk0 = hA['corvee'][idx] > 0
                ex_in = 1 - pk[inn & el].mean() if (inn & el).any() else float('nan'); ex_out = 1 - pk[out_ & el].mean() if (out_ & el).any() else float('nan')
                ex0 = (round(float(1 - pk0[inn & el].mean()), 3) if (inn & el).any() else None, round(float(1 - pk0[out_ & el].mean()), 3) if (out_ & el).any() else None)
        return dict(in_group_gain=round(ing, 2), out_group_loss=round(outg, 2), self_gain=round(self_gain, 2), skim_kept=round(skim, 2),
                    transfer=round(ing + self_gain + skim, 2), in_households=len(nin), out_households=len(nout),
                    artifact_in_minus_out_per_hh_year=round(art_in / max(cnt['in'], 1) - art_out / max(cnt['out'], 1), 4),
                    corvee_exempt_in=None if ex_in != ex_in else round(float(ex_in), 3), corvee_exempt_out=None if ex_out != ex_out else round(float(ex_out), 3), corvee_exempt_lambda0_in_out=ex0)
    # 对照：同坊里「也会被选任规则选中的那类户」（房主、有成年男人、屋里有租户、不是区长）坐这个位置会偏袒多少
    rng = np.random.default_rng(seed)
    alt_runs = []
    alts = {}
    for f in range(G.NFang):
        R = X.years[60]; h = R['offices']['fang'][f]
        if h < 0 or R['loc'][h] < 0: alts[f] = []; continue
        ht = R['hh_in_house'][R['loc'][h]] >= 2           # 现任屋里有没有租户：对照户必须同样（消掉「坊长兼房东」这个选任规则造成的差）
        isdz = np.isin(R['S'], R['offices']['district'])
        idx = np.nonzero((R['fang'] == f) & R['own'] & (R['men'] >= 1) & ((R['hh_in_house'] >= 2) == ht) & ~isdz & (R['S'] != h))[0]
        alts[f] = rng.permutation(R['S'][idx])[:K].tolist()
    for j in range(K):
        ov = {f: alts[f][j] for f in alts if len(alts[f]) > j}
        alt_runs.append((ov, X.run(Y0, Y1, lam=0.0, fang_head_override=ov), X.run(Y0, Y1, lam=lam, fang_head_override=ov)))
    for (fang, head), yrs in ten.items():
        m = node_metrics(fang, head, yrs, F0, F1)
        alt_t = []
        for ov, A0, A1 in alt_runs:
            if fang in ov and ov[fang] != head:
                alt_t.append(node_metrics(fang, ov[fang], yrs, A0, A1)['transfer'])
        m['alt_transfer_mean'] = round(float(np.mean(alt_t)), 2) if alt_t else None
        m['alt_n'] = len(alt_t); m['alt_transfer_std'] = round(float(np.std(alt_t)), 2) if len(alt_t) > 1 else None
        m['excess'] = round(m['transfer'] - (m['alt_transfer_mean'] or 0.0), 2)
        m['z'] = round(m['excess'] / m['alt_transfer_std'], 2) if m.get('alt_transfer_std') else None
        R = X.years[yrs[0]]; li = R['loc'][head]
        m['alt_rule'] = '同坊、房主、有成年男人、不是区长、屋里有没有租户与现任相同（60 年）'
        m.update(node='坊长', fang=int(fang), head=int(head), key=G.M['keys'][head], name=G.names[head], years=[yrs[0], yrs[-1]], n_years=len(yrs),
                 faith=RG.FAITHS[int(G.M['ff'][head])], origin=G.origins[int(G.M['fo'][head])], trade=G.trades[int(G.M['ft'][head])],
                 district=RG.DNAME.get(G.dnames[int(G.fdist[head])]), tenants_60=int(((X.years[60]['owner'] == head) & ~X.years[60]['own']).sum()) if X.years[60]['loc'][head] >= 0 else None)
        res.append(m)
    # 区长：57 征工配额（坊之间）
    dres = []
    for (dd, head), yrs in head_tenure(X, 'district').items():
        if 57 not in yrs: continue
        R = X.years[57]; fz = R['offices']['fang']
        fl = sorted(set(R['fang'][R['dist'] == dd].tolist()))
        q0 = {f: v for f, v in F0[57]['corvee_fq'].items() if f in fl}; q1 = {f: v for f, v in F1[57]['corvee_fq'].items() if f in fl}
        aff_f = {f: float(X.aff(R, head, np.array([R['loc'][fz[f]]]))[0]) if fz[f] >= 0 and R['loc'][fz[f]] >= 0 else 0.0 for f in fl}
        moved = sum(max(0, q0[f][1] - q1[f][1]) for f in fl if aff_f[f] > 0)
        dres.append(dict(node='区长', district=RG.DNAME.get(G.dnames[dd]), head=int(head), key=G.M['keys'][head], name=G.names[head],
                         quota_relief_to_friendly_fangs=int(moved), friendly_fangs=sum(1 for f in fl if aff_f[f] > 0), fangs=len(fl),
                         transfer=round(moved * X.P['corvee_days'] * X.P['day'], 2)))
    # 长老：施舍是否有缺口（没有缺口就没有裁量）
    short = {Y: (F1[Y]['alms_ratio'].tolist() if hasattr(F1[Y]['alms_ratio'], 'tolist') else F1[Y]['alms_ratio']) for Y in range(Y0, Y1 + 1)}
    # λ=0 的「规则造成的差」分布（不是发现）
    art = np.array([r['artifact_in_minus_out_per_hh_year'] for r in res]); tr = np.array([r['transfer'] for r in res]); ex = np.array([r['excess'] for r in res])
    dist = dict(nodes=len(res), artifact_lambda0=dict(p10=round(float(np.percentile(art, 10)), 4), p50=round(float(np.median(art)), 4), p90=round(float(np.percentile(art, 90)), 4)),
                transfer=dict(p10=round(float(np.percentile(tr, 10)), 2), p50=round(float(np.median(tr)), 2), p90=round(float(np.percentile(tr, 90)), 2), max=round(float(tr.max()), 2), total=round(float(tr.sum()), 2)),
                excess=dict(p10=round(float(np.percentile(ex, 10)), 2), p50=round(float(np.median(ex)), 2), p90=round(float(np.percentile(ex, 90)), 2), max=round(float(ex.max()), 2)),
                corr_transfer_vs_tenure_years=round(float(np.corrcoef(tr, [r['n_years'] for r in res])[0, 1]), 3))
    # 前 8：按 excess（超出同坊「同类」户坐这个位置的平均偏袒），户不重复
    seen = set(); top = []
    for r in sorted(res, key=lambda r: -r['excess']):
        if r['head'] in seen: continue
        seen.add(r['head']); top.append(r)
        if len(top) == 8: break
    top_raw = [dict(head=r['head'], name=r['name'], transfer=r['transfer']) for r in sorted(res, key=lambda r: -r['transfer'])[:8]]
    return dict(lam=lam, K=K, distribution=dist, top8=top, top8_by_raw_transfer=top_raw, district_heads=dres, alms_fill_ratio=short,
                total_shift=round(float(d[d > 0].sum()), 2)), res, (F0, F1)


def add_story(X, r):
    """给前 8 写一句：谁、在哪个位置、偏向谁、谁吃亏（字段拼接，不编情节）。"""
    G = X.G; head = r['head']; Y = 60 if X.years[60]['loc'][head] >= 0 else r['years'][0]
    R = X.years[Y]; idx = np.nonzero(R['fang'] == r['fang'])[0]; a = X.aff(R, head, idx)
    S = R['S'][idx]; fo = G.M['fo'][S]; ff = G.M['ff'][S]
    same_o = int(((fo == G.M['fo'][head]) & (S != head)).sum()); same_f = int(((ff == G.M['ff'][head]) & (S != head)).sum())
    r['fang_households'] = int(len(idx)); r['same_origin_in_fang'] = same_o; r['same_faith_in_fang'] = same_f
    return r


def bytes_and_query(X, F, years):
    """存储：节点表（每节点每年 收/留/上交/下发 4 个 float32）+ 偏袒裁量位（征工点名 1 bit/户·57 年；摊派系数 1 字节/户·年 只在 λ>0 时）。
    单户财政记录 = 户籍字段 + 参数 现算，O(1)。"""
    node_vals = 0
    for Y in range(Y0, Y1 + 1):
        for name, t in F[Y]['T'].items():
            if name.startswith('粮/面包簿') or name.startswith('民政/房主'): continue   # 房屋级 = 房主户字段 + 参数，现算
            node_vals += len(t['kept']) * 4
    raw = np.zeros(node_vals, np.float32).tobytes()
    vals = []
    for Y in range(Y0, Y1 + 1):
        for name, t in F[Y]['T'].items():
            if name.startswith('粮/面包簿') or name.startswith('民政/房主'): continue
            for c in ('in_below', 'kept', 'up', 'down'): vals.append(np.round(t[c], 2).astype(np.float32))
    blob = np.concatenate(vals).tobytes()
    pick_bits = np.packbits(np.isin(np.arange(X.G.NF), X.years[57]['S'][X.corvee_pick])).tobytes() if hasattr(X, 'corvee_pick') else b''
    fams = len(np.unique(np.concatenate([X.years[Y]['S'] for Y in range(Y0, Y1 + 1)])))
    gz = len(gzip.compress(blob + pick_bits, 9))
    # 单户查询：预先把每年每户的 9 个量放进 Python 列表（与 v3 Query 同法）
    t = time.perf_counter()
    Qt = {}
    for Y in range(Y0, Y1 + 1):
        S = X.years[Y]['S']; h = F[Y]['hh']; NF = X.G.NF
        def full(v):
            a = np.zeros(NF); a[S] = v; return a.tolist()
        Qt[Y] = {k: full(h[k]) for k in ('rent', 'levy', 'cistern', 'dues', 'offer', 'alms', 'stipend', 'comp', 'corvee', 'bread')}
    t_idx = time.perf_counter() - t
    rng = np.random.default_rng(1); picks = [(int(X.years[Y]['S'][rng.integers(len(X.years[Y]['S']))]), Y) for Y in rng.integers(Y0, Y1 + 1, 20000)]
    keys = ('rent', 'levy', 'cistern', 'dues', 'offer', 'alms', 'stipend', 'comp', 'corvee', 'bread')
    def rec(Fm, Y):
        T = Qt[Y]; return {k: T[k][Fm] for k in keys}
    a = time.perf_counter()
    for Fm, Y in picks: rec(Fm, Y)
    t_rec = (time.perf_counter() - a) / len(picks)
    bad = 0
    for Fm, Y in picks[:3000]:
        r = rec(Fm, Y); i = X.years[Y]['loc'][Fm]; bad += any(abs(r[k] - float(F[Y]['hh'][k][i])) > 1e-9 for k in keys)
    return dict(families=fams, node_table_raw=len(blob), corvee_bits=len(pick_bits), gzip=gz, per_family_raw=round((len(blob) + len(pick_bits)) / fams, 2),
                per_family_gzip=round(gz / fams, 2), query_index_s=round(t_idx, 3), query_rec_us=round(t_rec * 1e6, 2), verify_checked=3000, verify_mismatch=bad)


def main(scope, bench=False):
    t0 = time.time()
    G = RG.Registry(scope); years, t_reg = G.build(40, 70)
    rss_reg = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    X = FI.Fiscal(G, years)
    t = time.perf_counter(); F = X.run(41, 70); t_fis = time.perf_counter() - t
    t = time.perf_counter(); Fw = X.run(Y0, Y1); t_fis21 = time.perf_counter() - t
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    out = dict(scope=scope, params=X.P, build_cost=FI.BUILD_COST, works=X.works,
               seconds=dict(import_=round(T_IMPORT, 3), registry_build_31y=round(t_reg, 3), fiscal_30y=round(t_fis, 3), fiscal_21y_AF51_70=round(t_fis21, 3),
                            fiscal_per_year_ms=round(t_fis21 / 21 * 1000, 2)),
               peak_rss_mb_after_fiscal=round(rss, 1), rss_after_registry=round(rss_reg, 1))
    out['conservation_max_abs_err'] = FI.check_conservation(F)
    out['levels'] = {Y: v for Y, v in FI.level_table(F, years).items() if Y >= Y0}
    if scope == 'xero':
        L = ledger_series(); out['ledger'] = {Y: L[Y] for Y in range(Y0, Y1 + 1)}
        out['reconcile'] = reconcile(X, F, L)
        out['petitions'] = petitions(X, F); out['petitions_queue_rule'] = petitions(X, F, queue_one_per_year=True)
        out['petitions_reserve_usable'] = petitions(X, F, use_reserve=True)
        t = time.perf_counter(); fav, res, _ = favoritism(X); t_fav = time.perf_counter() - t
        for r in fav['top8']: add_story(X, r)
        out['favoritism'] = fav; out['seconds']['favoritism'] = round(t_fav, 3)
        json.dump(res, open(os.path.join(OUT, 'favoritism_nodes_xero.json'), 'w'), ensure_ascii=False, indent=0, default=float)
    out['bytes_query'] = bytes_and_query(X, F, years)
    out['peak_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    out['seconds']['total_in_process'] = round(time.time() - t0, 3)
    json.dump(out, open(os.path.join(OUT, f'fiscal_{scope}.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print(json.dumps({k: out[k] for k in ('seconds', 'conservation_max_abs_err', 'peak_rss_mb', 'bytes_query')}, ensure_ascii=False, default=float))
    return X, F, out


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(a[0] if a else 'xero', '--bench' in sys.argv)
