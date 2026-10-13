#!/usr/bin/env python3
"""Put each encounter in front of the house it names (on the nearest road live that year) and prefix its place with the street name.
Run after streets_xero.py + name_streets.py."""
import json, math
X = '/workspace/projects/618d22bb-ba67-4a65-bd41-39bbe9c6f6cd/living/xerolophos/'
SN = json.load(open(X + 'streetnames.json')); H = {h[0]: h for h in json.load(open(X + 'houses.json'))['houses']}
SEG = json.load(open(X + 'streets.json')); raw = json.load(open(X + 'scenes.json')); L = raw if isinstance(raw, list) else raw['scenes']
MAP = {'忒克拉家门口': 13068, '面包铺门口': 13821, '哥特兵家门口': 14251, '马卡里亚家门口': 13196, '教书先生的台阶上': 12250, '安娜家的新门口': 17158, '埃及水手家门口': 17084}
def nm(x, y, Y):
    b = None
    for st in SN:
        n = [r[0] for r in st['r'] if r[1] <= Y < r[2]]
        if not n or st['y'] > Y: continue
        for (ax, ay), (bx, by) in zip(st['p'][:-1], st['p'][1:]):
            dx, dy = bx - ax, by - ay; t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy + 1e-9))); d = math.hypot(x - ax - t * dx, y - ay - t * dy)
            if b is None or d < b[0]: b = (d, n[0])
    return b
for e in L:
    w = e['where'].split(' · ')[-1]; Y = e['y'][0]
    if w in MAP:
        h = H[MAP[w]]; p = h[4]; cx = sum(p[0::2]) / 4; cy = sum(p[1::2]) / 4; best = None
        for q in SEG:
            if q[6] > Y or (len(q) > 7 and q[7] and q[7] <= Y) or q[5] == 'm': continue
            ax, ay, bx, by = q[:4]; dx, dy = bx - ax, by - ay; t = max(0, min(1, ((cx - ax) * dx + (cy - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
            px, py = ax + t * dx, ay + t * dy; d = math.hypot(cx - px, cy - py)
            if best is None or d < best[0]: best = (d, px, py)
        d, px, py = best; e['at'] = [round(px + (cx - px) / max(d, 1e-6) * 2), round(py + (cy - py) / max(d, 1e-6) * 2)]
    b = nm(*e['at'], Y)
    e['where'] = (b[1] + ' · ' + w) if b and b[0] < 45 else w
    print(e['y'], e['where'], e['at'])
json.dump(raw, open(X + 'scenes.json', 'w'), ensure_ascii=False, indent=1)
