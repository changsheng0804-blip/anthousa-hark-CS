"""Pick the households that get generated stories, assign each a narrator (a real person living in a nearby storied house),
and print compact engine-derived briefs for the writer.
usage: python3 tools/select_households.py N > ../briefs.txt   (also writes tools/voices_selected.json)"""
import json, math, sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 220
H = json.load(open('../hh_all.json'))
deep = set(json.load(open('docs/living/xerolophos/stories.json')).keys()) | {'12231'}  # 12231 = Daphne's home

def fam_at(h, Y):
    f = h['fams'][0]
    for x in h['fams']:
        if x['B'] <= Y: f = x
    return f

def home(p, Y):  # living in the house that year (same rule as the page's aliveAt)
    return p['b'] <= Y < p['d'] and (not p['married'] or p['married'] <= Y) and not (p['left'] and p['left'] <= Y)

def alive(f, Y): return [p for p in f['people'] if home(p, Y)]

C = []
for h in H:
    if str(h['id']) in deep or h['destroyed'] <= 60 or h['built'] > 50: continue
    f50, f60 = fam_at(h, 50), fam_at(h, 60)
    if f50 is not f60 or not alive(f50, 50) or not alive(f50, 60): continue
    C.append(h)
C.sort(key=lambda h: math.hypot(h['cx'] - 505, h['cy'] - 1150))
S = C[:N]

def narrator(h):
    f = fam_at(h, 55); best = None
    for o in sorted((x for x in S if x is not h), key=lambda x: math.hypot(x['cx'] - h['cx'], x['cy'] - h['cy']))[:6]:
        of = fam_at(o, 55)
        for p in of['people']:
            if not home(p, 60): continue
            w0 = 60
            while w0 - 1 >= max(f['B'], of['B']) and home(p, w0 - 1) and (w0 - 1 - p['b']) >= 14: w0 -= 1
            if 60 - p['b'] < 14: continue
            d = math.hypot(o['cx'] - h['cx'], o['cy'] - h['cy'])
            key = (w0 + d / 40, )
            if best is None or key < best[0]: best = (key, o, of, p, w0)
    return best

sel = []
out = []
for h in S:
    f = fam_at(h, 55); nb = narrator(h)
    _, o, of, p, w0 = nb
    sel.append({'id': h['id'], 'fam': f['B'], 'nar': {'house': o['id'], 'n': p['n'], 'from': w0}})
    ppl = []
    for q in f['people']:
        if q['d'] < 30 or q['b'] > 60: continue
        s = f"{q['n']}{'♂' if q['s']=='m' else '♀'}{q['b']}-{q['d']}"
        if q['bride'] and q['g'] > 0: s += f"(媳,{q['married']}嫁入)"
        elif q['bride']: s += "(妻)"
        if q['left']: s += f"(→{q['left']}{'嫁' if q['s']=='f' else '离家'})"
        ppl.append(s)
    ev = [f"{y}:{t}" for y, t in h['ev'] if f['B'] <= y <= 60 and '出生' not in t]
    out.append(f"#{h['id']} 建{h['built']} {f['trade']}/{f['origin']}/{f['faith']} | 讲述:{o['id']}家({of['trade']}){p['n']}{'♂' if p['s']=='m' else '♀'}{p['b']} 可讲{max(w0,f['B'])}-60\n  人:{' '.join(ppl)}\n  事:{' | '.join(ev)}")
json.dump(sel, open('tools/voices_selected.json', 'w'), ensure_ascii=False)
print('\n'.join(out))
