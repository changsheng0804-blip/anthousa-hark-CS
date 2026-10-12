"""liu2 · 给建城 50 年以后才搬来的人家（包括 50–60 年间换了人家的房子）选讲述人、写提要。
Pick N families that moved in after AF50 (new houses, or houses whose family changed between 50 and 60),
nearest the liu1 cluster first; give each a narrator: a real person living in a nearby house through every year
the story covers (preferring houses that already have a story, so the gold threads link both ways).
usage: python3 tools/select_newcomers.py N > ../briefs2.txt     (appends to tools/voices_selected.json; needs ../hh_all.json)
"""
import json, math, sys, os
N = int(sys.argv[1]) if len(sys.argv) > 1 else 160
H = json.load(open('../hh_all.json'))
HB = {h['id']: h for h in H}
V = json.load(open('docs/living/xerolophos/voices.json'))
SELP = 'tools/voices_selected.json'
SEL = json.load(open(SELP))
deep = set(json.load(open('docs/living/xerolophos/stories.json')).keys()) | {'12231'}
taken = set(int(k) for k in V) | {s['id'] for s in SEL}

def fam_at(h, Y):
    f = h['fams'][0]
    for x in h['fams']:
        if x['B'] <= Y: f = x
    return f
def home(p, Y): return p['b'] <= Y < p['d'] and (not p['married'] or p['married'] <= Y) and not (p['left'] and p['left'] <= Y)
def span(h, f): return max(f['B'], h['built']), min(60, f['out'], h['destroyed'] - 1)

C = []
for h in H:
    if str(h['id']) in deep or h['id'] in taken: continue
    for f in h['fams']:
        if not (50 < f['B'] <= 60): continue
        lo, hi = span(h, f)
        if hi - lo < 1 and not (lo == hi == 60): continue
        if not any(home(p, hi) for p in f['people']) or not any(home(p, lo) for p in f['people']): continue
        C.append((h, f))
C.sort(key=lambda x: math.hypot(x[0]['cx'] - 505, x[0]['cy'] - 1150))
S = C[:N]
storied = taken | {h['id'] for h, _ in S}

def narrator(h, f):
    lo, hi = span(h, f); best = None
    near = sorted((o for o in H if o['id'] != h['id'] and o['built'] <= lo and o['destroyed'] > hi and str(o['id']) not in deep),
                  key=lambda o: math.hypot(o['cx'] - h['cx'], o['cy'] - h['cy']))[:14]
    for o in near:
        of = fam_at(o, hi)
        if of['B'] > lo: continue  # narrator's family must already live there when the story starts
        for p in of['people']:
            if not all(home(p, Y) for Y in range(lo, hi + 1)) or lo - p['b'] < 14: continue
            d = math.hypot(o['cx'] - h['cx'], o['cy'] - h['cy'])
            key = d / 40 - (2 if o['id'] in storied else 0)
            if best is None or key < best[0]: best = (key, o, of, p)
    return best

out = []; new = []
for h, f in S:
    nb = narrator(h, f)
    if not nb: continue
    _, o, of, p = nb
    lo, hi = span(h, f)
    new.append({'id': h['id'], 'fam': f['B'], 'nar': {'house': o['id'], 'n': p['n'], 'fam': of['B'], 'from': lo}})
    prev = [x for x in h['fams'] if x['B'] < f['B']]
    pv = ''
    if prev and h['built'] < f['B']:
        pf = prev[-1]; pv = f" 前一家:{pf['trade']}/{pf['origin']}，{pf['out']}年空出"
    ppl = []
    for q in f['people']:
        if q['d'] <= lo or q['b'] > 60: continue
        s = f"{q['n']}{'♂' if q['s']=='m' else '♀'}{q['b']}-{q['d']}"
        if q['bride'] and q['g'] > 0: s += f"(媳,{q['married']}嫁入)"
        elif q['bride']: s += "(妻)"
        if q['left']: s += f"(→{q['left']}{'嫁' if q['s']=='f' else '离家'})"
        ppl.append(s)
    ev = [f"{y}:{t}" for y, t in h['ev'] if lo <= y <= 60]
    out.append(f"#{h['id']} 建{h['built']} 搬来{f['B']} 可写{lo}-{hi} {f['trade']}/{f['origin']}/{f['faith']}{pv} | 讲述:{o['id']}家({of['trade']}/{of['origin']}/{of['faith']}){p['n']}{'♂' if p['s']=='m' else '♀'}{p['b']}\n  人:{' '.join(ppl)}\n  事:{' | '.join(ev)}")
json.dump(SEL + new, open(SELP, 'w'), ensure_ascii=False)
print('\n'.join(out))
print(f'选中 {len(new)} 户（候选 {len(C)}）', file=sys.stderr)
