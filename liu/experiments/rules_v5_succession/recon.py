"""规则预演 v5 · 继承对账（干山，AF40–70）。
  1 面包簿：一栋账本房屋一本（v3/v4 口径），持簿 = 房主户的户主；逐年 簿数 = 有人住的账本房屋数 = 房主户数，且每本簿都有户主持有
  2 人口守恒：在场人口(Y) = 在场人口(Y-1) + 出生 + 娶进 + 新户搬入 + 复户 − 死亡 − 离家 − 户结束带走；「其他」必须 0
  3 债随户继承：v2 must 里的债，债务户 / 债主户在债期内换了户主（继承事件）→ 随户继承；债期内户结束 → 债落空
  4 变体 B2：面包簿只能由成年男持有 → 房主户户主是寡妇 / 孤儿的年份失簿
usage: python3 recon.py
"""
import os, sys, json, time, collections, pickle
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import succession as SU  # noqa: E402

def recon(W):
    G = W.G; X = W.X; A = W.A; P = X['P']; fam = X['fam']
    pb, pd = np.array(P['b']), np.array(P['d']); pm, pl = np.array(P['m']), np.array(P['l']); pf = np.array(P['f'])
    fB = np.array(fam['B']); head = W.head; hk = W.hk
    out = dict(A=A, years={})
    # ---- 1 面包簿 + 4 B2
    b2_lost_hh = set(); b2_people = 0; transfers = collections.Counter()
    evY = collections.defaultdict(dict)
    for e in X[A]['events']: evY[e[1]][e[0]] = e[2]
    def inhouse(Y):
        h = (pb <= Y) & (Y < pd) & ((pm == 0) | (pm <= Y)) & ~((pl != 0) & (pl <= Y))
        pres = head[:, Y - SU.Y0] >= 0 if SU.Y0 <= Y <= SU.Y1 else np.zeros(len(fB), bool)
        return h & pres[pf]
    prev_in = inhouse(SU.Y0 - 1) if False else None
    tot_bad_pop = 0; flows_tot = collections.Counter()
    for Y in range(SU.Y0, SU.Y1 + 1):
        R = W.years[Y]; S = R['S']; yi = Y - SU.Y0
        owners = S[R['own']]
        nb = len(np.unique(R['rh'])); hold = head[owners, yi]; kind = hk[owners, yi]
        lost = owners[(kind == 1) | (kind == 2)]
        b2_lost_hh.update(lost.tolist()); b2_people += int(R['size'][R['own']][(kind == 1) | (kind == 2)].sum())
        for F in owners:
            ev = evY[Y].get(int(F))
            if ev: transfers[ev] += 1
        heads_ok = int((head[S, yi] >= 0).sum()) == len(S)
        # 户主在家（人表）
        cur = inhouse(Y)
        hp = head[S, yi]; head_home = bool(cur[hp].all())
        row = dict(books=nb, owner_households=len(owners), books_eq_owners=nb == len(owners), books_held=int((hold >= 0).sum()),
                   every_household_one_head=heads_ok, heads_at_home=head_home, b2_lost=len(lost))
        if Y > SU.Y0:
            prv = inhouse(Y - 1); ent = cur & ~prv; lev = prv & ~cur
            Fp = pf
            f_in = dict(出生=ent & (pb == Y), 娶进=ent & (pm == Y) & (pb != Y), 新户搬入=ent & (fB[Fp] == Y) & (pb != Y) & (pm != Y))
            rest_in = ent & ~(f_in['出生'] | f_in['娶进'] | f_in['新户搬入'])
            pres_now = head[:, yi] >= 0
            f_in['复户'] = rest_in & pres_now[Fp] & ~(head[:, yi - 1] >= 0)[Fp]
            other_in = rest_in & ~f_in['复户']
            f_out = dict(死亡=lev & (pd == Y), 离家=lev & (pd != Y) & (pl == Y))
            rest_out = lev & ~(f_out['死亡'] | f_out['离家'])
            f_out['户结束'] = rest_out & ~pres_now[Fp]
            other_out = rest_out & ~f_out['户结束']
            pop0, pop1 = int(prv.sum()), int(cur.sum())
            fin = {k: int(v.sum()) for k, v in f_in.items()}; fout = {k: int(v.sum()) for k, v in f_out.items()}
            resid = pop1 - pop0 - sum(fin.values()) + sum(fout.values()) - int(other_in.sum()) + int(other_out.sum())
            row.update(pop=pop1, inflow=fin, outflow=fout, other_in=int(other_in.sum()), other_out=int(other_out.sum()), resid=resid)
            tot_bad_pop += int(other_in.sum()) + int(other_out.sum()) + abs(resid)
            flows_tot.update(fin); flows_tot.update(fout)
            # 交叉核对：在场人口 = v1 size 之和
            row['pop_eq_v1_size'] = pop1 == int(G.M['size'][:, yi][head[:, yi] >= 0].sum())
        out['years'][Y] = row
    out['books_all_years_ok'] = all(r['books_eq_owners'] and r['books_held'] == r['books'] for r in out['years'].values())
    out['heads_ok'] = all(r['every_household_one_head'] and r['heads_at_home'] for r in out['years'].values())
    out['pop_other_or_resid_total'] = tot_bad_pop
    out['pop_eq_v1_all'] = all(r.get('pop_eq_v1_size', True) for r in out['years'].values())
    out['pop_flows_41_70'] = dict(flows_tot)
    out['book_transfers_by_succession'] = dict(transfers)
    out['b2'] = dict(lost_household_years=sum(r['b2_lost'] for r in out['years'].values()), lost_households=len(b2_lost_hh), lost_person_years=b2_people,
                     by_year={Y: r['b2_lost'] for Y, r in out['years'].items()})
    # ---- 3 债
    succ = collections.defaultdict(list); ends = {}
    for F, Y, ev, o, n in X[A]['events']:
        if ev in ('绝户', '迁走', '被拆'): ends[F] = Y
        elif ev != '复户': succ[F].append((Y, ev))
    debts = [m for m in W.must if m[0] == 'debt']
    inh = collections.Counter(); n_inh = 0; void = 0; kinds = collections.Counter()
    for _, deb, cred, y0, y1 in debts:
        hit = False
        for side, F in (('债务户', deb), ('债主户', cred)):
            ev = [e for Y, e in succ.get(F, []) if y0 < Y <= y1]
            if ev: inh[side] += 1; hit = True; kinds.update(ev)
        n_inh += hit
        if any(F in ends and y0 < ends[F] <= y1 for F in (deb, cred)): void += 1
    out['debts'] = dict(total=len(debts), inherited_any_side=n_inh, by_side=dict(inh), by_kind=dict(kinds), voided_by_household_end=void)
    return out


if __name__ == '__main__':
    t = time.time(); res = {}
    for A in (14, 16):
        W = SU.World('xero', A); res[A] = recon(W)
    res['seconds'] = round(time.time() - t, 2)
    json.dump(res, open(os.path.join(HERE, 'out', 'recon_xero.json'), 'w'), ensure_ascii=False, indent=1, default=int)
    for A in (14, 16):
        r = res[A]
        print(A, json.dumps({k: r[k] for k in r if k != 'years'}, ensure_ascii=False)[:1500])
    print('Y60', json.dumps(res[14]['years'][60], ensure_ascii=False)); print('s', res['seconds'])
