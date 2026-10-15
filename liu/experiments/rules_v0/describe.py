"""把交叉点还原成可写的事实：两户各年的户主、街、行当、信仰、籍贯、家里的生死，和双方之间每年现算出来的边。"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(__file__))
import data, rules as RM, run
from rules import household_state, edges_of_year

def facts(W, P, key, years):
    hid, B = key.split(':'); hid = int(hid) if hid.isdigit() else hid; B = int(B)
    h = next(x for x in W['houses'] if x['id'] == hid)
    f = next(x for x in h['fams'] if x['B'] == B)
    out = dict(key=key, house=hid, trade=f['trade'], faith=f['faith'], origin=f['origin'], B=B, built=h['built'], destroyed=h['destroyed'], fn=h['fn'])
    yrs = {}
    for Y in range(min(years) - 1, max(years) + 2):
        s = household_state(h, Y)
        if not s or s['key'] != key: continue
        yrs[Y] = dict(street=s['street'], num=s['num'], owner=s['owner'], needy=s['needy'], men=s['men'], kids=s['kids'],
                      mem=[f"{p['n']}{'♂' if p['s']=='m' else '♀'}{Y-p['b']}" for p in s['mem']], deaths=[p['n'] for p in s['deaths']], head=s['head'])
    out['years'] = yrs
    return out

def describe(scope, rows, pfile='rules.json'):
    P = json.load(open(os.path.join(run.HERE, pfile))); RM.OWNER_BEFORE = P['bread']['owner_before']
    W = run.load_scope(scope)
    hy, _ = run.hard_years(W.get('full', W['houses']), P)
    cache = {}
    def states_of(Y):
        if Y not in cache: cache[Y] = [s for s in (household_state(h, Y) for h in W['houses']) if s]
        return cache[Y]
    G = dict(water=W['water'], ovens=W['ovens'], places=W['places'], hard_years=hy, states_of=states_of)
    need = sorted({y for r in rows for y in r['years']})
    E = {Y: edges_of_year(states_of(Y), Y, P, G)[0] for Y in need}
    res = []
    for r in rows:
        ks = {r['a'], r['b']}
        ed = collections.defaultdict(set)
        for Y in r['years']:
            for a, b, t, note in E[Y]:
                if a in ks and (b in ks or (b.startswith('@') and r['b'].startswith('@'))):
                    ed[f'{t}:{note}'].add(Y)
        d = dict(r, edges={k: [min(v), max(v), len(v)] for k, v in ed.items()},
                 A=facts(W, P, r['a'], r['years']))
        if not r['b'].startswith('@'): d['B'] = facts(W, P, r['b'], r['years'])
        res.append(d)
    return res

if __name__ == '__main__':
    scope = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    rows = json.load(open(os.path.join(data.CACHE, f'rules_v0_cross_{scope}.json')))[:n]
    json.dump(describe(scope, rows), sys.stdout, ensure_ascii=False)
