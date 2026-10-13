"""核对 stories.json：每个故事的年份、人、街、门牌、户的状况、规则边都要在账本/页面推演/规则现算里成立；
正文里出现的人名、两位数年份、街名都必须在 claims 里被核对过。
usage: python3 check_stories.py   （不通过则退出码 1）"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data, rules as RM, run
from rules import household_state, edges_of_year, water_source, Ctx
from data import home, LEDGER_EVENTS

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, 'rules.json'))); RM.OWNER_BEFORE = P['bread']['owner_before']
SCOPE = os.environ.get('SCOPE', 'sample')  # SCOPE=xero 时用整个干山现算的边核对
W = run.load_scope(SCOPE)
H = {h['id']: h for h in W['houses']}
hy, _ = run.hard_years(W.get('full', W['houses']), P)
cache = {}
def states_of(Y):
    if Y not in cache: cache[Y] = [s for s in (household_state(h, Y) for h in W['houses']) if s]
    return cache[Y]
G = dict(water=W['water'], ovens=W['ovens'], places=W['places'], hard_years=hy, states_of=states_of)
EC = {}
def edges(Y):
    if Y not in EC: EC[Y] = edges_of_year(states_of(Y), Y, P, G)
    return EC[Y]

src = open(os.path.join(data.XD, 'index.html'), encoding='utf8').read()
city = json.load(open(os.path.join(data.XD, 'city.json')))
extra = re.findall(r"concat\(\[([^\]]*)\]\)", src)
NAMES = set(city['names_m']) | set(city['names_f'])
for e in extra: NAMES |= set(re.findall(r"'([^']+)'", e))
A = json.load(open(os.path.join(data.FU, 'addr.json')))
STREETS = {n for s in A['streets'] for n, f, t in s[2]}
JN = {}
for o in W['ovens'] + [w for w in W['water'] if w['kind'] == 'well']: JN[o['id']] = o.get('streets', [])

def fam(hid, Y):
    f, _ = data.fam_at(H[hid], Y); return f
def person(hid, Y, n):
    f = fam(hid, Y)
    c = [p for p in f['people'] if p['n'] == n and (home(p, Y) or p['d'] == Y or p.get('left') == Y or p.get('married') == Y)]
    return c[0] if c else None
def st(hid, Y): return household_state(H[hid], Y)

def scan(text, vocab):
    found = []; i = 0; V = sorted(vocab, key=len, reverse=True)
    while i < len(text):
        m = next((v for v in V if text.startswith(v, i)), None)
        if m: found.append(m); i += len(m)
        else: i += 1
    return found

def check(s):
    errs = []; c = s['claims']; E = lambda m: errs.append(m)
    years = set()
    for n, hid, Y, kind, *v in c.get('people', []):
        years.add(Y); p = person(hid, Y, n)
        if not p: E(f'人 {n} 在 {hid} 第 {Y} 年不存在'); continue
        if kind == 'home' and not home(p, Y): E(f'{n} 第 {Y} 年不在家')
        if kind == 'died' and not (p['d'] == Y and home(p, Y - 1)): E(f'{n} 不是第 {Y} 年死的（d={p["d"]}）')
        if kind == 'age' and not (home(p, Y) and Y - p['b'] == v[0]): E(f'{n} 第 {Y} 年不是 {v[0]} 岁（{Y - p["b"]}）')
        if kind == 'age_at_death' and not (p['d'] == Y and Y - p['b'] == v[0]): E(f'{n} 死时不是 {v[0]} 岁')
        if kind == 'married_out' and not (p['s'] == 'f' and p['left'] == Y): E(f'{n} 不是第 {Y} 年出嫁')
        if kind == 'bride' and not (p['bride'] and p['married'] == Y): E(f'{n} 不是第 {Y} 年嫁进来')
    for n, hid, Y in c.get('streets', []):
        if hid == 'junction':
            if n not in JN.get(Y, []): E(f'{n} 不在 {Y} 的路口街名里 {JN.get(Y)}')
            continue
        years.add(Y); t = st(hid, Y)
        if not t or t['street'] != n: E(f'{hid} 第 {Y} 年不在 {n}（{t and t["street"]}）')
    for hid, Y, num in c.get('nums', []):
        years.add(Y); t = st(hid, Y)
        if not t or t['num'] != num: E(f'{hid} 第 {Y} 年门牌不是 {num}（{t and t["num"]}）')
    for hid, Y, kind, *v in c.get('household', []):
        years.add(Y); t = st(hid, Y)
        if not t: E(f'{hid} 第 {Y} 年没人住'); continue
        ok = {'kids': lambda: t['kids'] == v[0], 'tenant': lambda: not t['owner'], 'owner': lambda: t['owner'],
              'needy': lambda: t['needy'], 'not_needy': lambda: not t['needy'], 'size': lambda: t['size'] == v[0],
              'faith': lambda: t['faith'] == v[0], 'trade': lambda: t['trade'] == v[0], 'origin': lambda: t['origin'] == v[0], 'arrived': lambda: t['B'] == Y,
              'only_man': lambda: [p['n'] for p in t['mem'] if p['s'] == 'm' and Y - p['b'] >= 16] == [v[0]],
              'only_adult': lambda: [p['n'] for p in t['mem'] if Y - p['b'] >= 16] == [v[0]],
              'kids_under16': lambda: sum(Y - p['b'] < 16 for p in t['mem']) == v[0],
              'eldest_man': lambda: max((p for p in t['mem'] if p['s'] == 'm'), key=lambda p: Y - p['b'])['n'] == v[0],
              'eldest_son': lambda: max((p for p in t['mem'] if p['s'] == 'm' and p['g'] > 0 and not p['bride']), key=lambda p: Y - p['b'])['n'] == v[0],
              'widow_of': lambda: (lambda d: d is not None and d['s'] == 'm' and d['d'] == Y)(person(hid, Y, v[0])) and any(p['bride'] and p['s'] == 'f' for p in t['mem']),
              }[kind]()
        if not ok: E(f'{hid} 第 {Y} 年 {kind} {v} 不成立')
    for typ, a, b, Y in c.get('edges', []):
        years.add(Y); es, _ = edges(Y)
        und = typ in RM.UNDIRECTED
        if not any(t == typ and ((x, y) == (a, b) or (und and (x, y) == (b, a))) for x, y, t, _ in es): E(f'第 {Y} 年没有 {typ} 边 {a}→{b}')
    for typ, a, Y, *b in c.get('no_edges', []):
        years.add(Y); es, _ = edges(Y)
        if any(t == typ and x == a and (not b or y == b[0]) for x, y, t, _ in es): E(f'第 {Y} 年 {a} 竟还有 {typ} 边（作为发出方）')
    for k, Y, wid in c.get('water_src', []):
        years.add(Y); es, ctx = edges(Y)
        ws = water_source(ctx.by_key[k], ctx)
        if not ws or ws[1]['id'] != wid: E(f'{k} 第 {Y} 年喝的不是 {wid}')
    for Y in c.get('hard_years', []):
        years.add(Y)
        if Y not in hy: E(f'{Y} 不是规则推出的灾年 {hy}')
    for Y in c.get('ledger', []):
        years.add(Y)
        if Y not in LEDGER_EVENTS: E(f'{Y} 年账本没有大事')
    # 正文扫描
    txt = s['text']
    for y in re.findall(r'(?<!\d)(\d{2})(?!\d)', txt):
        if int(y) not in years: E(f'正文年份 {y} 没被核对')
    claimed_n = {p[0] for p in c.get('people', [])}
    for n in set(scan(txt, NAMES)):
        if n not in claimed_n: E(f'正文人名 {n} 没被核对')
    claimed_s = {x[0] for x in c.get('streets', [])}
    for n in set(scan(txt, STREETS)):
        if n not in claimed_s: E(f'正文街名 {n} 没被核对')
    for bad in re.findall(r'[\u4e00-\u9fff]{1,4}(?:巷|街|大道)', txt):
        if not any(bad.endswith(x) for x in STREETS) and not bad.endswith('同街'):
            E(f'像街名却不在底账里：{bad}')
    TW = {'面包': '面包师', '烤面包': '面包师', '酒馆': '酒馆老板', '运水人': '运水人', '织工': '织工', '织机': '织工', '陶匠': '陶匠', '鞋匠': '鞋匠'}
    hs = c.get('household', [])
    for w in set(scan(txt.replace('面包配给', '').replace('领面包', '').replace('有面包', '').replace('运水人蓄水池', ''), TW)):
        if not any(h[2] == 'trade' and h[3] == TW[w] for h in hs): E(f'正文行当「{w}」没被核对')
    for o in ('色雷斯', '安条克', '比提尼亚', '卡帕多西亚', '亚历山大里亚'):
        if o in txt and not any(h[2] == 'origin' and h[3] == o for h in hs): E(f'正文籍贯 {o} 没被核对')
    for f in ('阿里乌派', '尼西亚派'):
        if f in txt and not any(h[2] == 'faith' and h[3] == f for h in hs): E(f'正文信仰 {f} 没被核对')
    n = len([x for x in re.split(r'[。！？]', txt) if x.strip()])
    if not 3 <= n <= 4: E(f'句数 {n} 不在 3–4')
    return errs

if __name__ == '__main__':
    S = json.load(open(os.path.join(HERE, 'stories.json')))
    bad = 0
    for s in S:
        e = check(s)
        print(f"#{s['rank']} {'/'.join(s['patterns'])}: {'通过' if not e else '不通过'}")
        for x in e: print('   ', x)
        bad += bool(e)
    sys.exit(1 if bad else 0)
