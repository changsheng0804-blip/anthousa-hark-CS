"""规则预演 v0 · 运行器
usage: python3 run.py SCOPE [PARAMS]     SCOPE = sample | xero | city ；PARAMS 默认 rules.json
输出 out/SCOPE[_naive].json：每年每类边数、交叉点（全量计数 + 前 50 名细节）、分数分布、运行时间、峰值内存。
弱关系边不落盘；落盘的只有统计和交叉点。
"""
import sys, os, json, time, resource, collections, math
sys.path.insert(0, os.path.dirname(__file__))
import data
import rules as RM
from rules import household_state, edges_of_year, alms_source, RULES
from cross import detect_year, score_pair, longest_run

HERE = os.path.dirname(os.path.abspath(__file__))


def ONLY(P):
    skip = set(P.get('lazy_skip', []))
    return {n for _, n, _ in RULES if n not in skip} if skip else None


def load_scope(scope):
    if scope == 'city': return data.load_city()
    W = data.load_xero()
    if scope == 'sample':
        ids = set(json.load(open(os.path.join(HERE, 'sample.json')))['houses'])
        W = dict(W, houses=[h for h in W['houses'] if h['id'] in ids], full=W['houses'])
    return W


def hard_years(houses, P):
    lo, hi = P['debt']['base_years']; rate = {}
    for Y in range(lo, hi + 1):
        ppl = dead = 0
        for h in houses:
            s = household_state(h, Y)
            if s: ppl += s['size'] + len(s['deaths']); dead += len(s['deaths'])
        rate[Y] = dead / max(ppl, 1)
    v = list(rate.values()); m = sum(v) / len(v); sd = (sum((x - m) ** 2 for x in v) / len(v)) ** .5
    return sorted(Y for Y, r in rate.items() if r > m + P['debt']['z'] * sd), {Y: round(r, 4) for Y, r in rate.items()}


def main(scope, pfile='rules.json', part=None, merge=False):
    P = json.load(open(os.path.join(HERE, pfile)))
    tag = scope + ('' if pfile == 'rules.json' else '_' + os.path.splitext(pfile)[0].replace('rules_', ''))
    RM.OWNER_BEFORE = P['bread']['owner_before']
    t0 = time.time()
    W = load_scope(scope)
    t_load = time.time() - t0
    houses = W['houses']
    hy, rates = hard_years(W.get('full', houses), P)
    cache = {}
    def states_of(Y):
        if Y not in cache: cache[Y] = [s for s in (household_state(h, Y) for h in houses) if s]
        return cache[Y]
    G = dict(water=W['water'], ovens=W['ovens'], places=W['places'], hard_years=hy, states_of=states_of)
    y0, y1 = P['years']
    Y0, Y1 = (map(int, part.split('-')) if part else (y0, y1))
    import pickle, glob
    if merge:
        per_year = {}; occ = collections.defaultdict(list); pt = collections.defaultdict(set); flags = collections.defaultdict(dict)
        hh_count = {}; edge_total = 0; t_rules = t_cross = 0.0; rss_parts = []; t_parts = 0.0
        for f in sorted(glob.glob(os.path.join(data.CACHE, f'rules_v0_part_{tag}_[0-9]*.pkl'))):
            d = pickle.load(open(f, 'rb'))
            per_year.update(d['per_year']); hh_count.update(d['hh_count']); edge_total += d['edge_total']
            t_rules += d['t_rules']; t_cross += d['t_cross']; rss_parts.append(d['rss']); t_parts += d['elapsed']
            for k, v in d['occ'].items(): occ[k] += v
            for k, v in d['pt'].items(): pt[k] |= v
            for k, v in d['flags'].items(): flags[k].update(v)
        return finish(scope, pfile, tag, P, houses, hy, rates, per_year, occ, pt, flags, hh_count, edge_total, t_rules, t_cross, t_load, t0, extra=dict(parts=len(rss_parts), part_seconds_sum=round(t_parts, 1), part_peak_rss_mb=max(rss_parts)))
    per_year = {}; occ = collections.defaultdict(list); pt = collections.defaultdict(set); flags = collections.defaultdict(dict)
    hh_count = {}; edge_total = 0; t_rules = 0.0; t_cross = 0.0
    for Y in range(Y0, Y1 + 1):
        S = states_of(Y); hh_count[Y] = len(S)
        a = time.time(); E, ctx = edges_of_year(S, Y, P, G, only=ONLY(P)); t_rules += time.time() - a
        c = collections.Counter(t for _, _, t, _ in E); per_year[Y] = dict(c); edge_total += len(E)
        a = time.time()
        hits, und, nodes = detect_year(Y, E, ctx, lambda s: alms_source(s, Y, P['church']))
        for name, x, y in hits:
            occ[(name, x, y)].append(Y)
            pt[(name, x, y)] |= und.get(tuple(sorted((x, y))), set())
        for s in S:
            flags[s['key']][Y] = (bool(s['deaths']), s['needy'], s['h']['destroyed'] <= y1 + 1, s['faith'] == '阿里乌派', s['trade'])
        t_cross += time.time() - a
        cache.pop(Y - P['debt']['years'] - 1, None)
    if part:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        pickle.dump(dict(per_year=per_year, hh_count=hh_count, edge_total=edge_total, t_rules=t_rules, t_cross=t_cross, rss=rss,
                         elapsed=time.time() - t0, occ=dict(occ), pt=dict(pt), flags=dict(flags)),
                    open(os.path.join(data.CACHE, f'rules_v0_part_{tag}_{part}.pkl'), 'wb'))
        print('part', part, 'done', round(time.time() - t0, 1), 's', round(rss), 'MB'); return
    return finish(scope, pfile, tag, P, houses, hy, rates, per_year, occ, pt, flags, hh_count, edge_total, t_rules, t_cross, t_load, t0)


def finish(scope, pfile, tag, P, houses, hy, rates, per_year, occ, pt, flags, hh_count, edge_total, t_rules, t_cross, t_load, t0, extra=None):
    y1 = P['years'][1]
    # 打分：同一对人家（或一户×机构）上的所有模式合成一条强关系
    y0 = P['years'][0]
    by_pair = collections.defaultdict(list); ptu = collections.defaultdict(set)
    for (name, a, b), ys in occ.items():
        k = (a, b) if b.startswith('@') else tuple(sorted((a, b)))
        by_pair[k].append((name, sorted(ys))); ptu[k] |= pt[(name, a, b)]
    rows = []
    for (a, b), prs0 in by_pair.items():
        mg = collections.defaultdict(set)
        for n, yy in prs0: mg[n] |= set(yy)
        prs = [(n, sorted(v)) for n, v in mg.items()]
        ys = sorted({y for _, yy in prs for y in yy}); snap = {}
        for k in (a, b):
            f = flags.get(k)
            if not f: continue
            snap[k] = dict(died_in=any(f.get(y, (0,))[0] for y in ys), was_needy=any(f.get(y, (0, 0))[1] for y in ys),
                           demolished=any(v[2] for v in f.values()), arian=any(v[3] for v in f.values()))
        sc, rl, dur, ev = score_pair(prs, ptu[(a, b)], snap, y0, y1)
        rows.append(dict(patterns=sorted(n for n, _ in prs), a=a, b=b, years=ys, dur=dur, score=sc, rules=rl, near_event=ev,
                         pattern_years={n: [yy[0], yy[-1]] for n, yy in prs}))
    rows.sort(key=lambda r: (-r['score'], r['a'], r['b']))
    hits_total = len(occ)
    # 重复骨架：模式组合 + 是否同行 + 双方信仰（排序）
    def skel(r):
        tr = [next(iter(flags[k].values()))[4] if k in flags else '@' for k in (r['a'], r['b'])]
        fa = sorted(('阿' if any(v[3] for v in flags[k].values()) else '非') if k in flags else '@' for k in (r['a'], r['b']))
        return '|'.join(r['patterns']) + ('|同行' if tr[0] == tr[1] else '|异行') + '|' + ''.join(fa)
    sk_all = collections.Counter(skel(r) for r in rows)
    sk_top = collections.Counter(skel(r) for r in rows[:100])
    # 选故事用的前 8：贪心，同一户只用一次，同一骨架最多 2 个
    used = set(); usk = collections.Counter(); picks = []
    for r in rows:
        ks = {r['a'], r['b']} - {x for x in (r['b'],) if x.startswith('@')}
        if ks & used or usk[skel(r)] >= 2: continue
        picks.append(dict(r, skeleton=skel(r))); used |= ks; usk[skel(r)] += 1
        if len(picks) == 8: break
    elapsed = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    hist = collections.Counter(int(r['score']) for r in rows)
    pat = collections.Counter(n for r in rows for n in r['patterns'])
    out = dict(scope=scope, params=pfile, hard_years=hy, death_rate=rates,
               houses=len(houses), households_per_year=hh_count, edges_per_year=per_year, edges_total=edge_total,
               edges_by_type={t: sum(v.get(t, 0) for v in per_year.values()) for t in sorted({t for v in per_year.values() for t in v})},
               crossings=len(rows), pattern_hits=hits_total, crossings_by_pattern=dict(pat), score_hist=dict(sorted(hist.items())),
               skeletons=len(sk_all), top_skeleton_share=dict(sk_top.most_common(5)), biggest_skeletons=dict(sk_all.most_common(5)),
               picks=picks, top=rows[:60], seconds=dict(total=round(elapsed, 1), load=round(t_load, 1), rules=round(t_rules, 1), cross=round(t_cross, 1)),
               peak_rss_mb=round(rss, 1), **(extra or {}))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, 'out', tag + '.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(rows, open(os.path.join(data.CACHE, f'rules_v0_cross_{tag}.json'), 'w'), ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ('scope', 'params', 'houses', 'hard_years', 'edges_total', 'edges_by_type', 'crossings', 'pattern_hits', 'crossings_by_pattern', 'score_hist', 'skeletons', 'top_skeleton_share', 'seconds', 'peak_rss_mb')}, ensure_ascii=False))
    print('households/yr', hh_count)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    part = next((x[7:] for x in sys.argv if x.startswith('--part=')), None)
    main(a[0], a[1] if len(a) > 1 else 'rules.json', part=part, merge='--merge' in sys.argv)
