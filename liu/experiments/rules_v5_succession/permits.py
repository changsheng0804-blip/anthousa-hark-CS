"""规则预演 v5 第二段 · 许可链（干山，四份请愿）。只 import v4（不运行写 out/ 的脚本）。

钱就绪时刻 t_m 来自 v4 petitions(use_reserve=True)（官库/主教可动用 51–60 积蓄，已定）减去施工 0.5 年；
之后请愿要过若干「批准关」，过完再施工 0.5 年。

批准人（假设 P1，按《狄奥多西法典》式的分工）：
  修水 水    三个区长转呈（并行，取最慢）→ 城市长官批            立场：不分派（全城公共事）
  开新区 挤  三个区长转呈（并行）→ 城市长官批                    立场：租户（挤的是租户；有租户的区长=房东，不一致）
  盖堂 信仰  阿里乌派主教（同派，一致）→ 堂址区长（干山）→ 城市长官   立场：阿里乌派
  救济 孤寡  三个区长转呈（并行）→ 尼西亚派主教（合办出钱方）       立场：阿里乌派（615 户缺男丁里 336 户阿里乌派，最多）
城市长官、两位主教在户籍外：城市长官、尼西亚派主教 = 尼西亚派，阿里乌派主教 = 阿里乌派（固定，假设）。
区长逐年从 years[Y]['offices']['district'] 读（干山页面只含 广场 2 / 港口 3 / 干山 4 三区；0/1 区全空、不算关）。

一关的规则（唯一参数 D_u，单位年）：
  当年在任者与请愿方立场一致 → 当场放行；
  不一致（或空缺：上级代签）→ 放行时刻 = min(t + D_u, 之后第一个「在任者一致」的年初)。
"""
import math, collections
import numpy as np

BUILD = 0.5
NICENE, ARIAN, PAGAN = 1, 0, 2   # 与 v3 RG.FAITHS = ['阿里乌派','尼西亚派','还拜旧神'] 一致
FIXED = dict(prefect=NICENE, bishop_nicene=NICENE, bishop_arian=ARIAN)
DIST_IN_PAGE = (2, 3, 4)
XD = 4
CHAIN = {
    '水': dict(party=('any', None), gates=[('districts',), ('prefect',)], ledger=62, what='修水'),
    '挤': dict(party=('tenant', None), gates=[('districts',), ('prefect',)], ledger=63, what='开新区'),
    '信仰': dict(party=('faith', ARIAN), gates=[('bishop_arian',), ('district', XD), ('prefect',)], ledger=64, what='盖堂'),
    '孤寡': dict(party=('faith', ARIAN), gates=[('districts',), ('bishop_nicene',)], ledger=65, what='救济'),
}


def aligned_house(R, F, party):
    """户 F 在年 R 是否与请愿方立场一致。F<0（空缺）= 不一致。"""
    if F < 0: return False
    li = R['loc'][F]
    if li < 0: return False
    kind, v = party
    if kind == 'any': return True
    if kind == 'faith': return int(R['faith'][li]) == v
    if kind == 'tenant': return int(((R['owner'] == F) & ~R['own']).sum()) == 0   # 自己没有租户（不是房东）
    raise ValueError(kind)


def gate_ok(years, gate, Y, party):
    if gate[0] in FIXED:
        kind, v = party
        return kind in ('any', 'tenant') or FIXED[gate[0]] == v
    R = years[Y]
    return aligned_house(R, int(R['offices']['district'][gate[1]]), party)


def pass_gate(years, gate, t, party, D_u, Ymax=70):
    Y = math.floor(t)
    if gate_ok(years, gate, min(Y, Ymax), party): return t, None
    for Y2 in range(Y + 1, Ymax + 1):
        if Y2 >= t + D_u: break
        if gate_ok(years, gate, Y2, party): return float(Y2), '换人'
    return t + D_u, '压 D_u'


def run_chain(years, k, t_m, D_u):
    c = CHAIN[k]; t = t_m; log = []
    for g in c['gates']:
        if g[0] == 'districts':
            outs = [pass_gate(years, ('district', d), t, c['party'], D_u) for d in DIST_IN_PAGE]
            t2 = max(o[0] for o in outs)
            log.append(dict(gate='三区长', t_in=round(t, 3), t_out=round(t2, 3), each={d: (round(o[0], 3), o[1]) for d, o in zip(DIST_IN_PAGE, outs)}))
        else:
            t2, why = pass_gate(years, g, t, c['party'], D_u)
            log.append(dict(gate={'prefect': '城市长官', 'bishop_nicene': '尼西亚派主教', 'bishop_arian': '阿里乌派主教', 'district': '干山区长'}[g[0]],
                            t_in=round(t, 3), t_out=round(t2, 3), why=why))
        t = t2
    return t, log


def petitions_with_permits(years, money, D_u):
    """money = v4 petitions(..., use_reserve=True) 的输出。返回 {k: dict(year, t, permit_wait, money_wait, log)}。"""
    out = {}
    for k in CHAIN:
        t_m = money[k]['predicted_t'] - BUILD
        t_p, log = run_chain(years, k, t_m, D_u)
        t_done = t_p + BUILD
        out[k] = dict(year=math.floor(t_done + 1e-9), t=round(t_done, 3), money_ready_t=round(t_m, 3), permit_wait=round(t_p - t_m, 3),
                      total_wait_from_raise=round(t_done - 60.5, 3), log=log, ledger=CHAIN[k]['ledger'])
    return out


def calibrate(years, money, lo=0.0, hi=5.0, step=0.01):
    """G1 下扫 D_u，返回使四份请愿年份 = 账本 62/63/64/65 的区间与中点。"""
    ok = []
    for D in np.arange(lo, hi + 1e-9, step):
        r = petitions_with_permits(years, money, float(D))
        if all(r[k]['year'] == CHAIN[k]['ledger'] for k in CHAIN): ok.append(round(float(D), 4))
    if not ok: return None
    # 可能不连续：取包含点最多的连续段
    segs = []; s = [ok[0]]
    for a, b in zip(ok, ok[1:]):
        if b - a <= step * 1.5: s.append(b)
        else: segs.append(s); s = [b]
    segs.append(s); best = max(segs, key=len)
    return dict(interval=[best[0], best[-1]], D_u=round((best[0] + best[-1]) / 2, 3), segments=[[x[0], x[-1]] for x in segs], step=step)
