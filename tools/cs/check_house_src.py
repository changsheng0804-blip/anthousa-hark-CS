"""check_house_src：房子几何只认上游 tools/house_types.py；vec 零件带年份区间；同一栋房子立架/建成/换瓦/塌顶各年画面不同。"""
import sys, os, json, glob, re
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')); sys.path.insert(0, os.path.join(R, 'tools', 'cs', 'factory'))
bad = 0
def ok(c, m):
    global bad
    print(('✅ ' if c else '❌ ') + m); bad += (not c)
src = open(os.path.join(R, 'tools/cs/factory/house_types.py')).read()
ok(len(src.splitlines()) < 40 and 'house_types_upstream' in src, '1 CS 的 house_types 是薄壳（<40 行，加载上游）')
import house_types as H
up = open(os.path.join(R, 'tools/house_types.py')).read()
ok(hasattr(H, 'at') and hasattr(H, 'life_end') and 'def life_end' in up, '2 几何函数来自上游（有 life_end/at 一生阶段）')
hs = json.load(open(os.path.join(R, 'docs/living/nangang/houses_street.json')))['houses']
# 3 一生各年画面不同
def pick():
    for h in hs:
        if h[3] < 900 and h[2] >= 2 and h[3] - h[2] > 45 and not str(h[9]).startswith('lm:'): return h
h = pick(); by, parts, sh = H.geom(h); b, e = h[2], h[3]; E = H.life_end(h)
def sig(Y): return json.dumps(H.at(parts, Y), sort_keys=True, default=str)
ys = [b - 1 if False else b, b + 1, b + 5, b + 25, b + 40, E]
ok(len({sig(y) for y in ys}) >= 4, '3 同一栋房子 %s 年（立架/建成/换瓦/长苔/塌顶）至少 4 种不同画面' % ys)
# 4 vec 零件带区间
vf = sorted(glob.glob(os.path.join(R, 'docs/living/tiles/vec/*')))[:400]
import gzip
n = r = 0
for f in vf:
    try: d = json.load(open(f))
    except Exception: continue
    for hh in d.get('h', []):
        for q in hh[4]: n += 1; r += len(q) > 3
ok(n > 0 and r > 0, '4 烤出的 vec 零件带年份区间（%d/%d 个零件有区间）' % (r, n))
page = open(os.path.join(R, 'docs/living/tiles/index.html')).read()
ok('stageSig' in page and 'y0!==undefined' in page, '5 页面按年挑零件，贴图缓存带阶段')
print('red', bad); sys.exit(1 if bad else 0)
