"""刘线 liu4 · 把 tools/batches/liu4_streets.json 的改写应用到 voices.json。
每条改写：替换某户人生线的某一条；应用前核对改写里提到的街名中有这户那年真正所在的街（facts_upstream/addr.json）。
usage: python3 tools/apply_streets.py [--dry]"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'docs', 'living', 'xerolophos')
V = json.load(open(os.path.join(XD, 'voices.json'), encoding='utf-8'))
A = json.load(open(os.path.join(XD, 'facts_upstream', 'addr.json'), encoding='utf-8'))
P = json.load(open(os.path.join(ROOT, 'tools', 'batches', 'liu4_streets.json'), encoding='utf-8'))
def names(si, Y):
    return [r[0] for r in A['streets'][si][2] if r[1] <= Y < r[2]]
bad = 0
for k, v in P.items():
    if k.startswith('_'): continue
    i, t = v
    y = V[k]['life'][i][0]
    run = next((r for r in A['h'][k][1] if r[2] <= y < r[3]), None)
    own = names(run[0], y) if run else []
    if not any(n in t for n in own):
        print(f'✗ {k} 第{i+1}条({y}): 没提到这户那年所在的街 {own}'); bad += 1
    V[k]['life'][i][1] = t
print(f'改写 {len(P) - 1} 户，街名对不上 {bad}')
if '--dry' not in sys.argv and not bad:
    json.dump(V, open(os.path.join(XD, 'voices.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('写入 voices.json')
sys.exit(1 if bad else 0)
