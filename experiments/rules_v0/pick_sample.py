"""选样本片区：干山上一块圆形片区，AF55 在住 50–80 户，跨 ≥3 条街（每条 ≥5 户）、≥3 种街区功能、阿里乌派与尼西亚派都 ≥8 户。写 sample.json。"""
import json, math, collections, sys
sys.path.insert(0, '.')
import data
from rules import household_state
W = data.load_xero(); H = W['houses']
S55 = [s for s in (household_state(h, 55) for h in H) if s]
best = None
for cx in range(100, 1900, 40):
    for cy in range(0, 2100, 40):
        for r in (110, 130, 150, 170):
            m = [s for s in S55 if math.hypot(s['x'] - cx, s['y'] - cy) <= r]
            if not 50 <= len(m) <= 80: continue
            st = collections.Counter(s['street'] for s in m if s['street'])
            fn = collections.Counter(s['fn'] for s in m)
            fa = collections.Counter(s['faith'] for s in m)
            tr = collections.Counter(s['trade'] for s in m)
            big = [k for k, v in st.items() if v >= 5]
            if len(big) < 3 or len(fn) < 3 or fa['阿里乌派'] < 8 or fa['尼西亚派'] < 8 or len(tr) < 6: continue
            key = (len(fn) + len(big) + min(fa['尼西亚派'], fa['阿里乌派']) / 10, -abs(len(m) - 65))
            if best is None or key > best[0]: best = (key, cx, cy, r, m, st, fn, fa)
key, cx, cy, r, m, st, fn, fa = best
ids = sorted({h['id'] for h in H if math.hypot(h['x'] - cx, h['y'] - cy) <= r})
json.dump(dict(center=[cx, cy], radius=r, houses=ids, households_af55=len(m), streets=dict(st), fn=dict(fn), faith=dict(fa)),
          open('sample.json', 'w'), ensure_ascii=False, indent=1)
print(cx, cy, r, len(ids), len(m), dict(st), dict(fn), dict(fa))
