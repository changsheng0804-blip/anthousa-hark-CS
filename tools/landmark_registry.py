"""All landmarks of the city read from gen/landmarks/*.json (the single source).
Fixed (historic) instances -> city.json landmarks, houses.json late zones, ground overlays, no-build circles, district influences.
Generated instances (rule != fixed) are placed by landmarks.py. `python3 landmark_registry.py check|sync` in living/<quarter>/."""
import json, os, sys, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'landmarks')
SPECS = {f[:-5]: json.load(open(os.path.join(D, f))) for f in sorted(os.listdir(D)) if f.endswith('.json')}
def fixed(quarter='xerolophos'):
    for sid, sp in SPECS.items():
        for it in sp.get('instances', {}).get('fixed', []):
            if it.get('quarter', quarter) == quarter: yield sid, sp, it
def by_key(quarter='xerolophos'): return {it['key']: (sid, sp, it) for sid, sp, it in fixed(quarter)}
def no_build(quarter='xerolophos'):
    """[(xy, radius)] in the old streets_xero order"""
    L = sorted(((sp.get('clear_rank', 9), it['xy'], sp['clear_radius']) for sid, sp, it in fixed(quarter) if 'clear_radius' in sp), key=lambda q: q[0])
    return [(xy, r) for _, xy, r in L]
def no_build_interior(quarter='xerolophos'):
    """circles where the street generator must not drop interior lanes (old NB[:2])"""
    return [(it['xy'], sp['clear_radius']) for sid, sp, it in sorted(fixed(quarter), key=lambda q: q[1].get('clear_rank', 9)) if sp.get('clear_interior')]
def clear_masks(quarter='xerolophos'):
    return [(it['xy'], sp['clear_mask_radius']) for sid, sp, it in fixed(quarter) if 'clear_mask_radius' in sp]
def influences(quarter='xerolophos'):
    """district pulls, by order: [(order, fn, kind, geom, r, built)] kind 'pt' | 'line'"""
    out = []
    for sid, sp, it in fixed(quarter):
        for inf in sp.get('influence', []):
            if 'line_r' in inf: out.append((inf['order'], inf['fn'], 'line', sp['line'], inf['line_r'], 0))
            else: out.append((inf['order'], inf['fn'], 'pt', it['xy'] if 'poly' not in it else None, inf['r'], it.get('built', 0) if inf.get('from_built') else 0, it))
    return sorted(out, key=lambda q: q[0])
def city_entry(it):
    d = {'id': it['key'], 'xy': it['xy'], 'name': it['name_zh'], 'story': it['story'], 'now': it['now']}
    if 'until' in it: d['until'] = it['until']
    return d
def sync(X, write=False):
    c = json.load(open(X + 'city.json')); H = json.load(open(X + 'houses.json')); G = json.load(open(X + 'ground.json'))
    K = by_key(); diff = 0
    for i, l in enumerate(c['landmarks']):
        if l['id'] in K:
            e = city_entry(K[l['id']][2])
            if e != l: diff += 1; print('city differs', l['id']); c['landmarks'][i] = e
    for k, (sid, sp, it) in K.items():
        if 'poly' in it:
            z = {'built': it['built'], 'p': it['poly']}
            if H['late'].get(k) != z: diff += 1; print('late differs', k); H['late'][k] = z
    for k, (sid, sp, it) in K.items():
        o = it.get('overlay')
        if o and o not in G: diff += 1; print('overlay missing', k)
    if write:
        json.dump(c, open(X + 'city.json', 'w'), ensure_ascii=False, indent=1); json.dump(H, open(X + 'houses.json', 'w'), separators=(',', ':'))
    print('registry vs data differences:', diff); return diff
if __name__ == '__main__':
    sync('./', write='sync' in sys.argv)
