"""交叉点探测：两条（或更多）规则在同一对人家身上互相拉扯的地方。
只有交叉点才值得存成强关系、写成故事；弱关系边每年现算后即丢。
"""
import math, collections
from data import LEDGER_EVENTS

TYPE_RULE = {'water': '同一口水', 'carrier': '同一口水', 'bread': '面包跟着房子走', 'faith': '信仰分线', 'hometown': '同乡带同乡',
             'trade': '同行聚街', 'landlord': '房东与租户', 'debt': '借贷与债', 'apprentice': '工钱与学徒', 'rival': '同行竞争',
             'patron': '恩主与门客', 'alms': '教会层级', 'evicted': '官府', 'levy': '官府', 'corvee': '官府', 'garrison': '军营'}

EVENT_TAGS = {48: {'fire', 'build'}, 49: {'faith'}, 51: {'faith'}, 52: {'faith'}, 54: {'water', 'build'}, 55: {'grain'},
              57: {'build'}, 62: {'water', 'build'}, 63: {'build'}, 64: {'faith'}, 65: {'alms'}}


def P_same_hometown_diff_faith(Y, a, b, types, A, B):
    # v0b：只在 51 年（阿里乌派被请出城里教堂）之后、一边阿里乌派一边尼西亚派时才算冲突；v0a 是任意两派不同就算
    return 'hometown' in types and {A['faith'], B['faith']} == {'阿里乌派', '尼西亚派'} and Y >= 51

def P_water_bread(Y, a, b, types, A, B):
    if 'water' not in types or A['owner'] == B['owner']: return False
    t = B if A['owner'] else A
    return bool(t['deaths'] or t['needy'])

def P_rival_fire(Y, a, b, types, A, B):
    return 'rival' in types and (A['refugee'] or B['refugee'])

def P_landlord_faith(Y, a, b, types, A, B):
    if 'landlord' not in types or Y < 51: return False
    return A['faith'] == '尼西亚派' and B['faith'] == '阿里乌派'

def P_debt_street(Y, a, b, types, A, B):
    return 'debt' in types and A['street'] and A['street'] == B['street']

def P_patron_faith(Y, a, b, types, A, B):
    return 'patron' in types and A['faith'] != B['faith']

def P_double_bind(Y, a, b, types, A, B):
    return 'landlord' in types and ('debt' in types or 'patron' in types)

def P_alms_split(Y, a, b, types, A, B, alms=None):
    return 'water' in types and A['needy'] and B['needy'] and (alms(A) is None) != (alms(B) is None)

def P_apprentice_faith(Y, a, b, types, A, B):
    return 'apprentice' in types and A['faith'] != B['faith']

# 单户 × 机构的交叉
def H_carrier_office(Y, s, nodes):
    return s['trade'] == '运水人' and any(t in ('evicted', 'corvee') for t, n in nodes) or \
        (s['trade'] == '运水人' and any(t == 'levy' for t, n in nodes) and (s['needy'] or s['deaths']))

def H_soldier_no_alms(Y, s, nodes):
    return bool(s['soldier']) and s['needy'] and not any(t == 'alms' for t, n in nodes)

PAIR_PATTERNS = [
    ('同乡异信', P_same_hometown_diff_faith, {'hometown', 'faith'}, {'faith'}),
    ('同水异粮', P_water_bread, {'water', 'bread'}, {'water', 'grain'}),
    ('火后同行对头', P_rival_fire, {'rival', 'trade'}, {'fire', 'build'}),
    ('正统房东·阿里乌派租户', P_landlord_faith, {'landlord', 'faith'}, {'faith'}),
    ('债主欠债同街', P_debt_street, {'debt', 'trade'}, {'grain'}),
    ('恩主门客异信', P_patron_faith, {'patron', 'faith'}, {'faith'}),
    ('房东兼债主/恩主', P_double_bind, {'landlord', 'debt'}, {'grain'}),
    ('同井施舍分线', P_alms_split, {'water', 'alms', 'faith'}, {'faith', 'alms'}),
    ('学徒拜异派师傅', P_apprentice_faith, {'apprentice', 'faith'}, {'faith', 'alms'}),
]
HOUSE_PATTERNS = [
    ('运水人摊上公家的事', H_carrier_office, {'carrier', 'evicted'}, {'water', 'build'}),
    ('儿子当兵·家里无男丁无施舍', H_soldier_no_alms, {'garrison', 'alms'}, {'alms'}),
]


def detect_year(Y, edges, ctx, alms_fn):
    """返回本年命中的交叉点：[(模式, a, b)]，以及 pair→types 供打分时统计涉及的规则。"""
    pairs = collections.defaultdict(set); nodes = collections.defaultdict(list)
    for a, b, t, note in edges:
        if b.startswith('@'): nodes[a].append((t, b)); continue
        pairs[(a, b)].add(t)
    hits = []
    for (a, b), types in pairs.items():
        A, B = ctx.by_key[a], ctx.by_key[b]
        for name, fn, rules, tags in PAIR_PATTERNS:
            ok = fn(Y, a, b, types, A, B, alms=alms_fn) if fn is P_alms_split else fn(Y, a, b, types, A, B)
            if ok: hits.append((name, a, b))
    # 同一对人家的反向边（无向类规则已排序；有向类可能 a/b 顺序不同）合并 types
    und = collections.defaultdict(set)
    for (a, b), t in pairs.items(): und[tuple(sorted((a, b)))] |= t
    for s in ctx.S:
        nd = nodes.get(s['key'], [])
        for name, fn, rules, tags in HOUSE_PATTERNS:
            if fn(Y, s, nd): hits.append((name, s['key'], (nd[0][1] if nd else '@')))
    return hits, und, nodes


def longest_run(ys):
    ys = sorted(set(ys)); best = cur = 1
    for p, q in zip(ys, ys[1:]):
        cur = cur + 1 if q == p + 1 else 1; best = max(best, cur)
    return best if ys else 0


def score(name, a, b, years, pair_types, snap):
    """戏剧性 = 涉及规则数 + 0.4×持续年数(≤10) + 与账本大事的贴近度 + 当事人家里的账本事（丧、拆房、缺男丁）。"""
    tags = next(t for n, f, r, t in PAIR_PATTERNS + HOUSE_PATTERNS if n == name)
    base_rules = next(r for n, f, r, t in PAIR_PATTERNS + HOUSE_PATTERNS if n == name)
    rules = {TYPE_RULE.get(t, t) for t in base_rules} | {TYPE_RULE[t] for t in pair_types}
    dur = longest_run(years)
    prox = 0.0; ev = None
    for y in years:
        for ey, (txt, w) in LEDGER_EVENTS.items():
            rel = 1.0 if EVENT_TAGS.get(ey, set()) & tags else 0.3
            v = w * rel * math.exp(-abs(y - ey))
            if v > prox: prox, ev = v, ey
    pers = 0.0
    for k in (a, b):
        s = snap.get(k)
        if not s: continue
        if s['died_in']: pers += 1.0
        if s['demolished']: pers += 1.5
        if s['was_needy']: pers += 0.5
    return round(len(rules) + 0.4 * min(dur, 10) + prox + pers, 2), sorted(rules), dur, ev


BACKGROUND = {'同一口水', '同行聚街'}  # 只说明「是邻居/同行」，几乎每对都有，算半条


def score_pair(prs, pair_types, snap, y0, y1):
    """一对人家（或一户×机构）上所有命中的模式合成一条强关系，打分：
    规则数（背景规则算 0.5）+ 1.5×(模式数-1) + 0.25×持续年数(≤8) + 账本大事贴近度 + 当事人家里的账本事 + 转折（在窗口里开始/结束各 0.5）。"""
    rules = set(); tags = set(); ys = set()
    for name, years in prs:
        base = next(r for n, f, r, t in PAIR_PATTERNS + HOUSE_PATTERNS if n == name)
        tags |= next(t for n, f, r, t in PAIR_PATTERNS + HOUSE_PATTERNS if n == name)
        rules |= {TYPE_RULE.get(t, t) for t in base}; ys |= set(years)
    rules |= {TYPE_RULE[t] for t in pair_types}
    wr = sum(0.5 if r in BACKGROUND else 1.0 for r in rules)
    dur = longest_run(ys)
    arian = any(s.get('arian') for s in snap.values())
    prox = 0.0; ev = None
    for y in ys:
        for ey, (txt, w) in LEDGER_EVENTS.items():
            et = EVENT_TAGS.get(ey, set())
            rel = 1.0 if (et & tags) and ('faith' not in et or arian) else 0.3
            v = w * rel * math.exp(-abs(y - ey))
            if v > prox: prox, ev = v, ey
    pers = 0.0
    for s in snap.values():
        if s['died_in']: pers += 1.0
        if s['demolished']: pers += 1.5
        if s['was_needy']: pers += 0.5
    turn = 0.5 * (min(ys) > y0) + 0.5 * (max(ys) < y1)
    sc = wr + 1.5 * (len(prs) - 1) + 0.25 * min(dur, 8) + prox + pers + turn
    return round(sc, 2), sorted(rules), dur, ev
