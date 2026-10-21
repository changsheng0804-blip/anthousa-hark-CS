"""规则预演 v4 · 财政层：在 v3 户籍 + 治理树上逐年记「收多少、留多少、上交多少、下发多少」。

单位：份 = 一人一年的口粮（账本 food 上限的单位；calibration.json：一人一年吃 200–250 kg 粮）。钱一律折成份。
账本已有的量（推得出）：粮食上限、站着的账本房屋（每区每年）、人口（= 房屋 × 9）、拆房栋数与年份、征工户数（v2/v3 规则）、
  凑铜板户数（v0/v1 规则）、面包簿（v3：一栋一本）、施舍资格（v3：缺男丁 14 岁 ∧ 本派那年有施舍的地方）、建筑占地与材料（proposals / world.json）。
账本没有的（假设，见 PARAM，§报告「假设表」给依据与敏感度）：房屋税、租金、行会钱、奉献、施舍额、军饷、补偿、各级截留比例、上交皇库比例、造价。

五棵树（每个节点一行：in = 自筹 + 自下 + 自上；out = 上交 + 下发 + 留存；逐节点守恒，误差 < 1e-6）：
  粮：城市长官 →（账本 5 区）→ 坊（页面内）/ 页面外账本房屋（合计）→ 面包簿（房主）→ 屋里各户
  民政钱：户（租户交房租）→ 房主（交房屋税）→ 坊长（截 α）→ 区长（截 β）→ 城市长官（军饷、补偿、工程；上交皇库）→ 皇库
  教会：户（奉献）→ 教区长老（截 ε）→ 教区 → 主教（留 κ 作建堂/神职，其余下发施舍）→ 教区 → 长老 → 缺男丁户；65 起施舍交寡妇孤儿之家（不分派）
  行会：户（行会钱，即 collatio lustralis）→ 行会头（截 γ）→ 行会 → 城市长官
  兵营：城市长官 → 城门兵营 → 兵户（军饷）
偏袒（裁量空间，λ 为假设的偏袒强度；λ=0 = v3 中性规则，逐条复现 v3 征工）：
  坊长：房屋税/凑铜板摊派、57 征工点名、拆房补偿下发时的截留；区长：57 征工配额分到坊；长老：施舍不够时谁先领。
  亲疏 A(经手人, 户) = 自家 3 + 自家租户 2 + 同乡 1 + 同派 1（≤ 4，假设）。
usage: python3 fiscal.py xero|city [--bench]
"""
import os, sys, json, time, math, collections, resource
T0 = time.time()
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(HERE, '..', 'rules_v3_registry')
sys.path.insert(0, V3); sys.path.insert(1, os.path.join(HERE, '..', 'rules_v1')); sys.path.insert(2, os.path.join(HERE, '..', 'rules_v0'))
import registry as RG  # noqa: E402  (v3，只读复用)
import edicts as ED    # noqa: E402  (v3，只读复用：拆房落到户、凑铜板)
T_IMPORT = time.time() - T0
ARIAN, NICENE, PAGAN = RG.ARIAN, RG.NICENE, RG.PAGAN

# ------------------------------------------------------------------ 假设（全部可调；敏感度 ±50% 见 sensitivity.py）
PARAM = dict(
    tau=0.5,      # 房屋税：每栋账本房屋每年 0.5 份（房主交）
    rho=1.0,      # 房租：每家租户每年 1.0 份交给房主
    delta=0.3,    # 行会钱（collatio lustralis 折年）：每户每年 0.3 份
    omega=0.3,    # 奉献：每户入教区的人家每年 0.3 份
    alpha=0.10,   # 坊长截留（办事钱）
    beta=0.10,    # 区长截留
    gamma=0.10,   # 行会头截留
    eps=0.05,     # 教区长老截留
    kappa=0.40,   # 主教留作神职/建堂的比例（下限；施舍需要少于预算时剩下的也留）
    alms=1.0,     # 施舍：每户缺男丁（有资格）人家每年 1.0 份
    sigma=1.0,    # 军饷补贴：每户兵户每年 1.0 份（城市长官 → 兵营）
    remit=0.5,    # 城市长官把钱收入的 50% 上交皇库
    V_h=30.0,     # 一栋普通房屋的价值（份）
    comp=0.5,     # 拆房补偿 = comp × V_h 给房主
    reloc=1.0,    # 租户搬迁费（份/户）
    levy=1.0,     # 修水凑铜板：每户 1.0 份（54、62）
    corvee_days=30, day=0.015,   # 57 征工：每户出 30 个人日；一个人日折 0.015 份
    lam=0.0,      # 偏袒强度（0 = 中性规则）
    skim=0.5,     # λ=1 时补偿对外人最多截 50%
)
CORVEE_TOTAL = 140
BUILD_COST = dict(timber=0.5, brick_domestic=1.0, brick_civic=1.5, cistern=2.0, marble=4.0, road=0.3)   # 每平方单位（144 m²）造价 = 系数 × V_h（假设）


ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
# 账本工程（world.json 的建筑，AF41–70）由谁出钱（推得出的：faction 字段 + chronicle 叙述；分摊是假设 W1）
WORK_PAYER = {'cistern_carriers': 'prefect+levy', 'cistern_slope': 'prefect+levy', 'r_carriers': 'prefect', 'r_exo': 'prefect',
              'church_arian_brick': 'bishop_arian', 'arian_meeting': 'bishop_arian', 'xenon_xerolophos': 'district_xero+bishop_nicene',
              'forum_theodosius': 'emperor', 'cistern_modestus': 'emperor', 'nymphaeum_maius': 'emperor', 'horrea_troadensia': 'merchants',
              'horrea_alexandrina': 'merchants', 'church_anastasia': 'church_private'}


def ledger_works(P):
    """账本建筑的造价 = 占地（平方单位，1 单位 = 12 m）× 系数 × V_h；路 = 长 × 宽 × 0.3 × V_h（系数是假设）。"""
    W = json.load(open(os.path.join(ROOT, 'world.json')))
    out = []
    for s in W['structures']:
        if not (41 <= s['built'] <= 70) or s['type'] == 'district': continue
        g = s['geom']; c = np.array(g['coords'], float)
        mats = (s.get('dna') or {}).get('materials') or []; scale = (s.get('dna') or {}).get('scale')
        if g['type'] == 'line':
            L = float(np.hypot(*np.diff(c, axis=0).T).sum()); area = L * s.get('width', 1.0); k = BUILD_COST['road']
        else:
            x, y = c[:, 0], c[:, 1]; area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            if s['type'] == 'cistern': k = BUILD_COST['cistern']
            elif 'marble_revetted' in mats: k = BUILD_COST['marble']
            elif 'timber' in mats: k = BUILD_COST['timber']
            elif scale == 'domestic': k = BUILD_COST['brick_domestic']
            else: k = BUILD_COST['brick_civic']
        out.append(dict(id=s['id'], type=s['type'], year=s['built'], faction=s.get('faction'), area=round(area, 1), k=k,
                        cost=round(area * k * P['V_h'], 1), payer=WORK_PAYER.get(s['id'], s.get('faction'))))
    return out


class Fiscal:
    def __init__(self, G, years, P=None):
        self.G = G; self.years = years; self.P = dict(PARAM, **(P or {}))
        self.NT = len(G.trades); self.ND = len(G.dnames)
        self.fo = G.M['fo']; self.ff = G.M['ff']
        WL = G.WL; self.WLd = G.WLd
        self.stand_d = {Y: np.bincount(self.WLd[(WL['built'] <= Y) & (WL['dest'] > Y)], minlength=self.ND) for Y in years}
        self.dest_d = {Y: np.bincount(self.WLd[WL['dest'] == Y], minlength=self.ND) for Y in years}
        self.works = ledger_works(self.P)
        self.xd = G.dnames.index('d_xerolophos')
        self.levy_mask = {Y: ED.levy(G, years[Y], Y) for Y in (54, 62) if Y in years}
        self.evict = {}
        for Y in (48, 54, 57, 62, 65):
            if Y in years and Y - 1 in years:
                Rp = years[Y - 1]; m = WL['dest'][Rp['rh']] == Y
                self.evict[Y] = Rp['S'][m]

    # ---- 亲疏
    def aff(self, R, head, idx):
        """head = 户号（全局），idx = 本年本地下标数组。"""
        if head < 0: return np.zeros(len(idx))
        S = R['S']; F = S[idx]
        a = 3.0 * (F == head) + 2.0 * ((R['owner'][idx] == head) & (F != head)) + 1.0 * (self.fo[F] == self.fo[head]) + 1.0 * (self.ff[F] == self.ff[head])
        return np.minimum(a, 4.0)

    # ---- 坊内摊派（房屋税 / 凑铜板）：总额不变，按 1 − λ·A/8 加权（假设）
    def assess(self, R, idx, base, head, lam):
        if lam == 0 or len(idx) == 0: return base.copy()
        w = 1.0 - lam * self.aff(R, head, idx) / 8.0
        tot = base.sum(); x = base * w
        return x * (tot / x.sum()) if x.sum() > 0 else base.copy()

    # ---- 57 征工：区长把配额分到坊（按户数 × (1 − λ·A(区长, 坊长)/8) 最大余数），坊长点名（中性 G3 次序 + λ·A）
    def corvee(self, R, lam, head_override=None):
        G = self.G; S, n = R['S'], len(R['S']); men = R['men']; own = R['own']; kr = G.keyrank[S]
        def lr(w, tot):
            w = np.asarray(w, float); q = tot * w / max(w.sum(), 1e-12); fl = np.floor(q).astype(int)
            for i in np.argsort(-(q - fl), kind='stable')[:tot - fl.sum()]: fl[i] += 1
            return fl
        elig = ((~own) & (men >= 1)) | (own & (men >= 2)); pri = np.where(~own, 0, 1)
        dl = sorted(set(R['dist'].tolist())); dq = lr([int((R['dist'] == d).sum()) for d in dl], CORVEE_TOTAL)
        fz = R['offices']['fang'].copy(); dz = R['offices']['district']
        if head_override: 
            for f, h in head_override.items(): fz[f] = h
        pick = np.zeros(n, bool); fq = {}
        for d, qd in zip(dl, dq):
            fl = sorted(set(R['fang'][R['dist'] == d].tolist()))
            w = np.array([int((R['fang'] == f).sum()) for f in fl], float)
            if lam:
                dh = dz[d]
                if dh >= 0:
                    a = np.array([self.aff(R, dh, np.array([R['loc'][fz[f]]]))[0] if fz[f] >= 0 and R['loc'][fz[f]] >= 0 else 0.0 for f in fl])
                    w = w * (1 - lam * a / 8.0)
            fqs = lr(w, int(qd)); carry = 0
            for f, qf in zip(fl, fqs):
                idx = np.nonzero((R['fang'] == f) & elig)[0]
                o = np.lexsort((kr[idx], -men[idx], pri[idx])); idx = idx[o]
                if lam and len(idx) and fz[f] >= 0:
                    sc = np.arange(len(idx)) / len(idx) + lam * self.aff(R, fz[f], idx) / 4.0
                    idx = idx[np.argsort(sc, kind='stable')]
                k = min(len(idx), int(qf) + carry); carry = int(qf) + carry - k
                pick[idx[:k]] = True; fq[f] = (int(qf), k)
        return pick, fq

    # ---- 一年
    def year(self, Y, lam=None, fang_head_override=None, elder_override=None):
        P = self.P; lam = P['lam'] if lam is None else lam
        G = self.G; R = self.years[Y]; S = R['S']; n = len(S); own = R['own']; loc = R['loc']
        fz = R['offices']['fang'].copy(); dz = R['offices']['district']; ez = R['offices']['elder'].copy(); gz = R['offices']['guild']
        if fang_head_override:
            for f, h in fang_head_override.items(): fz[f] = h
        if elder_override:
            for k, h in elder_override.items(): ez[k] = h
        ND, NF = self.ND, G.NFang
        oloc = loc[R['owner']]                                      # 房主的本地下标
        hh = dict(rent=np.zeros(n), levy=np.zeros(n), cistern=np.zeros(n), dues=np.zeros(n), offer=np.zeros(n),
                  alms=np.zeros(n), alms_need=np.zeros(n), stipend=np.zeros(n), comp=np.zeros(n), corvee=np.zeros(n), bread=R['fed'].copy())
        T = {}                                                      # 节点表：名 → dict(in_self,in_below,in_above,up,down,kept) 数组
        def node(name, k): T[name] = {c: np.zeros(k) for c in ('in_self', 'in_below', 'in_above', 'up', 'down', 'kept')}; return T[name]
        # ================= 粮（账本）
        q = R['q']; st = self.stand_d[Y]; books_d = np.bincount(R['dist'][own], minlength=ND); out_d = st - books_d
        g_city = node('粮/城市长官', 1); g_city['in_self'][0] = RG.food_cap(Y); g_city['down'][0] = q * st.sum(); g_city['kept'][0] = RG.food_cap(Y) - q * st.sum()
        g_d = node('粮/区', ND); g_d['in_above'][:] = q * st; g_d['down'][:] = q * st
        g_out = node('粮/页面外账本房屋', ND); g_out['in_above'][:] = q * out_d; g_out['kept'][:] = q * out_d
        books_f = np.bincount(R['fang'][own], minlength=NF)
        g_f = node('粮/坊', NF); g_f['in_above'][:] = q * books_f; g_f['down'][:] = q * books_f
        g_b = node('粮/面包簿（房主）', n)            # 只在房主下标上有值
        fed_by_owner = np.bincount(oloc, weights=R['fed'], minlength=n)
        g_b['in_above'][own] = q; g_b['down'][own] = fed_by_owner[own]; g_b['kept'][own] = q - fed_by_owner[own]
        # ================= 民政钱
        ten = ~own
        hh['rent'][ten] = P['rho']
        rent_in = np.bincount(oloc[ten], minlength=n) * P['rho']
        base_levy = np.where(own, P['tau'], 0.0)
        levy = base_levy.copy()
        cis = np.zeros(n)
        if Y in self.levy_mask: cis[self.levy_mask[Y]] = P['levy']
        for f in range(NF):
            idx = np.nonzero(R['fang'] == f)[0]
            if not len(idx): continue
            if lam:
                levy[idx] = self.assess(R, idx, base_levy[idx], fz[f], lam)
                if cis[idx].any(): cis[idx] = self.assess(R, idx, cis[idx], fz[f], lam)
        hh['levy'] = levy; hh['cistern'] = cis
        # 拆房补偿（账本拆房：前一年登记在那栋账本房屋上的户）：城市长官 → 区长 → 坊长（λ 时对外人截留）→ 房主 / 租户
        comp_hh = np.zeros(n); comp_skim_f = np.zeros(NF); comp_pass_f = np.zeros(NF)
        comp_city_out = 0.0
        if Y in self.evict:
            Rp = self.years[Y - 1]; ev = self.evict[Y]; li = Rp['loc'][ev]
            amt = np.where(Rp['own'][li], P['comp'] * P['V_h'], P['reloc'])
            # 按「前一年」的坊结算（被拆户今年还在名册上的，钱记到今年的户）
            fp = Rp['fang'][li]
            for f in np.unique(fp):
                m = fp == f; head = (Rp['offices']['fang'][f] if not fang_head_override or f not in fang_head_override else fang_head_override[f])
                a = amt[m]
                if lam and head >= 0:
                    sk = a * lam * P['skim'] * (1 - self.aff(Rp, head, li[m]) / 4.0)
                else: sk = np.zeros(len(a))
                comp_skim_f[f] += sk.sum(); comp_pass_f[f] += a.sum()
                now = loc[ev[m]]; ok = now >= 0
                np.add.at(comp_hh, now[ok], (a - sk)[ok])
                comp_skim_f[f] += 0.0
                # 页面上已经不在的户（迁走）：钱照发，记在「已迁走」上（只有几户）
                self._gone = getattr(self, '_gone', 0) + float((a - sk)[~ok].sum())
            comp_city_out = comp_pass_f.sum()
        hh['comp'] = comp_hh
        # 房主节点（房屋）：in = 房租 + 自筹；out = 房屋税 + 凑铜板（只算本户自己的，见户表）；kept = in − out
        h_o = node('民政/房主（房屋）', n)
        h_o['in_below'][own] = rent_in[own]
        need = levy[own]; h_o['up'][own] = need
        h_o['in_self'][own] = np.maximum(0, need - rent_in[own]); h_o['kept'][own] = rent_in[own] + h_o['in_self'][own] - need
        # 坊长节点
        up_f = np.bincount(R['fang'], weights=levy + cis, minlength=NF)
        c_f = node('民政/坊长', NF)
        c_f['in_below'][:] = up_f; c_f['kept'][:] = P['alpha'] * np.bincount(R['fang'], weights=levy, minlength=NF)
        c_f['up'][:] = up_f - c_f['kept']
        c_f['in_above'][:] = comp_pass_f; c_f['down'][:] = comp_pass_f - comp_skim_f; c_f['kept'][:] += comp_skim_f
        # 页面外账本房屋（每栋一户交房屋税，未建模的坊长截 α）
        c_out = node('民政/页面外各坊（合计）', ND)
        c_out['in_below'][:] = P['tau'] * out_d; c_out['kept'][:] = P['alpha'] * P['tau'] * out_d; c_out['up'][:] = (1 - P['alpha']) * P['tau'] * out_d
        dout = self.dest_d[Y].astype(float)
        page_ev_d = np.zeros(ND)
        if Y in self.evict:
            Rp = self.years[Y - 1]; li = Rp['loc'][self.evict[Y]]
            page_ev_houses = np.bincount(Rp['dist'][li][Rp['own'][li]], minlength=ND)
            page_ev_d = np.bincount(Rp['dist'][li], weights=np.where(Rp['own'][li], P['comp'] * P['V_h'], P['reloc']), minlength=ND)
            dout = np.maximum(dout - page_ev_houses, 0)
        c_out['in_above'][:] = dout * P['comp'] * P['V_h']; c_out['down'][:] = c_out['in_above']
        # 区长
        dist_of_f = np.asarray(G.fang_dist)
        upf_d = np.bincount(dist_of_f, weights=c_f['up'], minlength=ND)
        lev_d = np.bincount(dist_of_f, weights=np.bincount(R['fang'], weights=levy, minlength=NF), minlength=ND) * (1 - P['alpha']) + c_out['up']
        c_d = node('民政/区长', ND)
        c_d['in_below'][:] = upf_d + c_out['up']; c_d['kept'][:] = P['beta'] * lev_d
        # 凑铜板不截区长那一份：直接送到工程（54/62 的池子）→ 记作区长「上交」到城市长官的工程账
        c_d['up'][:] = c_d['in_below'] - c_d['kept']
        comp_d = np.bincount(dist_of_f, weights=comp_pass_f, minlength=ND) + c_out['in_above']
        c_d['in_above'][:] = comp_d; c_d['down'][:] = comp_d
        # 行会
        hh['dues'][:] = P['delta']
        gk = R['dist'] * self.NT + R['trade']
        dues_g = np.bincount(gk, weights=hh['dues'], minlength=ND * self.NT)
        u_h = node('行会/行会头', ND * self.NT); u_h['in_below'][:] = dues_g; u_h['kept'][:] = P['gamma'] * dues_g; u_h['up'][:] = dues_g - u_h['kept']
        u_out = node('行会/页面外（合计）', ND); u_out['in_below'][:] = P['delta'] * out_d; u_out['kept'][:] = P['gamma'] * P['delta'] * out_d; u_out['up'][:] = u_out['in_below'] - u_out['kept']
        u_g = node('行会/行会', self.NT)
        u_g['in_below'][:] = np.bincount(np.arange(ND * self.NT) % self.NT, weights=u_h['up'], minlength=self.NT); u_g['up'][:] = u_g['in_below']
        # 兵营
        gar = R['garrison']; hh['stipend'][gar] = P['sigma']
        b_n = node('兵营/城门兵营', 1); b_n['in_above'][0] = P['sigma'] * gar.sum(); b_n['down'][0] = b_n['in_above'][0]
        # 57 征工（人力，另记人日；折份只用来测偏袒）
        corvee_fq = None
        if Y == 57:
            pick, corvee_fq = self.corvee(R, lam, fang_head_override)
            hh['corvee'][pick] = P['corvee_days']
            self.corvee_pick = pick
        # ================= 教会
        fa = R['faith']; par = R['parish']; inpar = (fa != PAGAN) & (par >= 0)
        hh['offer'][inpar] = P['omega']
        ek = R['fang'] * 3 + fa
        offer_e = np.bincount(ek[inpar], weights=hh['offer'][inpar], minlength=NF * 3)
        has_e = ez >= 0
        e_n = node('教会/教区长老', NF * 3)
        e_n['in_below'][:] = offer_e; e_n['kept'][:] = np.where(has_e, P['eps'] * offer_e, 0); e_n['up'][:] = offer_e - e_n['kept']
        p_ids = sorted(set(par[inpar].tolist())); NPAR = 5
        par_e = np.full(NF * 3, -1); par_e[ek[inpar]] = par[inpar]
        p_n = node('教会/教区', NPAR)
        p_n['in_below'][:] = np.bincount(np.maximum(par_e, 0), weights=np.where(par_e >= 0, e_n['up'], 0), minlength=NPAR); p_n['up'][:] = p_n['in_below']
        bishop_of_par = np.array([NICENE, NICENE, ARIAN, ARIAN, ARIAN])
        b_in = np.bincount(bishop_of_par, weights=p_n['up'], minlength=3)[:2]
        bp = node('教会/主教', 2)          # 0 阿里乌派、1 尼西亚派
        bp['in_below'][:] = b_in
        ent = R['alms'].astype(float) * P['alms']; hh['alms_need'] = ent
        xenon = Y >= self.G.P['church']['xenon_from']
        budget = (1 - P['kappa']) * b_in
        if not xenon:
            need_b = np.array([ent[fa == ARIAN].sum(), ent[fa == NICENE].sum()])
            give_b = np.minimum(budget, need_b); bp['down'][:] = give_b; bp['kept'][:] = b_in - give_b
            ratio = np.where(need_b > 0, give_b / np.maximum(need_b, 1e-12), 1.0)
            # 施舍沿 主教 → 教区 → 长老 下发：每个长老拿本组需要 × 本派比例；长老在本组里分（λ：亲疏优先）
            alms = np.zeros(n)
            for k in np.unique(ek[ent > 0]):
                idx = np.nonzero((ek == k) & (ent > 0))[0]; f_ = fa[idx[0]]
                pot = ent[idx].sum() * ratio[0 if f_ == ARIAN else 1]
                alms[idx] = self.share(R, idx, ent[idx], pot, ez[k], lam)
            e_n['in_above'][:] = np.bincount(ek, weights=alms, minlength=NF * 3); e_n['down'][:] = e_n['in_above']
            p_n['in_above'][:] = np.bincount(np.maximum(par, 0), weights=np.where(par >= 0, alms, 0), minlength=NPAR); p_n['down'][:] = p_n['in_above']
            # 51 年阿里乌派无教区：没有施舍（v3 规则：alms=False），这里自然为 0
            x_n = node('教会/寡妇孤儿之家', 1)
        else:
            # 65 起：两位主教把施舍预算交寡妇孤儿之家（挂干山区），不分派地发给所有缺男丁户；不够按比例（λ 时由坊长代发，按亲疏）
            x_n = node('教会/寡妇孤儿之家', 1)
            give = budget.copy(); bp['down'][:] = give; bp['kept'][:] = b_in - give
            x_n['in_above'][0] = give.sum(); need = ent.sum(); paid = min(need, give.sum())
            ratio = paid / need if need > 0 else 1.0
            alms = np.zeros(n)
            for f in range(NF):
                idx = np.nonzero((R['fang'] == f) & (ent > 0))[0]
                if len(idx): alms[idx] = self.share(R, idx, ent[idx], ent[idx].sum() * ratio, fz[f], lam)
            x_n['down'][0] = alms.sum(); x_n['kept'][0] = give.sum() - alms.sum()
        hh['alms'] = alms
        # ================= 城市长官（钱）
        c_c = node('民政/城市长官', 1)
        c_c['in_below'][0] = c_d['up'].sum() + u_g['up'].sum() + u_out['up'].sum()
        c_c['up'][0] = P['remit'] * c_c['in_below'][0]
        c_c['down'][0] = b_n['in_above'][0] + c_d['in_above'].sum()
        c_c['kept'][0] = c_c['in_below'][0] - c_c['up'][0] - c_c['down'][0]
        # ================= 账本工程（谁出钱：WORK_PAYER，假设 W1；花的是该级当年留存，不够就动用往年积蓄 → kept 为负）
        w_n = node('工程', 1); wl = [w for w in self.works if w['year'] == Y]; spent = {}
        for w in wl:
            c = w['cost']; p = w['payer']
            if p.startswith('prefect'):
                c_c['down'][0] += c; c_c['kept'][0] -= c; w_n['in_above'][0] += c
            elif p == 'bishop_arian':
                bp['down'][0] += c; bp['kept'][0] -= c; w_n['in_above'][0] += c
            elif p == 'district_xero+bishop_nicene':
                c_d['down'][self.xd] += c / 2; c_d['kept'][self.xd] -= c / 2; bp['down'][1] += c / 2; bp['kept'][1] -= c / 2; w_n['in_above'][0] += c
            else:
                w_n['in_self'][0] += c        # 皇库 / 粮商 / 私宅：树外出钱
            spent[w['id']] = (p, c)
        w_n['kept'][0] = w_n['in_above'][0] + w_n['in_self'][0]
        return dict(works=spent, Y=Y, hh=hh, T=T, corvee_fq=corvee_fq, alms_ratio=ratio)

    def share(self, R, idx, ent, pot, head, lam):
        """施舍不够时的分法：中性 = 按比例；λ 时按 (1 + λ·A) 权重注水，每户不超过应得。"""
        if pot >= ent.sum() - 1e-12: return ent.copy()
        if lam == 0 or head < 0: return ent * (pot / ent.sum())
        w = 1.0 + lam * self.aff(R, head, idx)
        out = np.zeros(len(idx)); left = pot; act = np.ones(len(idx), bool)
        for _ in range(len(idx) + 1):
            if left <= 1e-12 or not act.any(): break
            x = left * w * act / (w * act).sum()
            cap = ent - out; over = act & (x >= cap)
            if over.any():
                out[over] = ent[over]; left -= cap[over].sum(); act &= ~over
            else:
                out += x; left = 0
        return out

    def run(self, y0, y1, **kw):
        return {Y: self.year(Y, **kw) for Y in range(y0, y1 + 1)}


def check_conservation(F):
    worst = 0.0
    for Y, r in F.items():
        for name, t in r['T'].items():
            d = t['in_self'] + t['in_below'] + t['in_above'] - t['up'] - t['down'] - t['kept']
            worst = max(worst, float(np.abs(d).max()) if len(d) else 0.0)
    return worst


def level_table(F, years):
    """每级每年：收（自筹+自下+自上）、留、上交、下发。"""
    rows = {}
    for Y, r in F.items():
        rows[Y] = {}
        for name, t in r['T'].items():
            rows[Y][name] = dict(nodes=int((t['in_self'] + t['in_below'] + t['in_above'] > 1e-12).sum()),
                                 income=round(float((t['in_self'] + t['in_below'] + t['in_above']).sum()), 2), self_funded=round(float(t['in_self'].sum()), 2),
                                 kept=round(float(t['kept'].sum()), 2), up=round(float(t['up'].sum()), 2), down=round(float(t['down'].sum()), 2))
    return rows
