"""居民节点（试作，2026-10-18，主人：「居民首先得能被看见」「不能是纸片人」「角色的真正形态是他怎么活」）。
不写人，写行为：从底账（nodes_net.json 的房子、栈桥、喷泉、地标、街网）按规则挑出五个人，推出他们的
步态、负重、一天的节奏、同伴和地位，写成 docs/living/nodes/<q>/people.json。页面只负责照着演。
同一份底账、同一个年份，永远得到同样的五个人、同样的一天。没有一处用随机数挑人，只在并列时按房号定先后。

  python3 tools/cs/people/people.py nangang [年份]

——Hark（CS线）"""
import json, math, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from graph import StreetGraph, plen, live

Q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
Y = int(sys.argv[2]) if len(sys.argv) > 2 else 60
ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
SRC = os.path.join(ROOT, 'docs/living/nodes', Q, 'nodes_net.json')
D = json.load(open(SRC)); W, H = D['W'], D['H']; E = D['elev']; MPP = E['mpp']
G = StreetGraph(D, Y)
F = D['features']
inframe = lambda x, y: 4 < x < W - 4 and 4 < y < H - 4
def elev(x, y):
    i = max(0, min(E['w'] - 1, int(x / E['st']))); j = max(0, min(E['h'] - 1, int(y / E['st'])))
    return E['dm'][j * E['w'] + i] / 10

houses = [f for f in F if f['t'] == 'house' and live(f, Y)]
def poly(h): p = h['p']; return list(zip(p[::2], p[1::2]))
def center(h): P = poly(h); return (sum(p[0] for p in P) / len(P), sum(p[1] for p in P) / len(P))
def door(h):
    """门开在临街那条边（底账 fr）的中点，往街上走一步就是街面。"""
    P = poly(h); i = h.get('fr', 0) % len(P); a, b = P[i], P[(i + 1) % len(P)]
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); n = G.nearest(*m)
    return m, (n[1] if n else m), (n[0] if n else 99)
def lm_door(f):
    g = f['g']; cx = sum(p[0] for p in g) / len(g); cy = sum(p[1] for p in g) / len(g)
    best = None
    for p in g + [((g[k][0] + g[(k + 1) % len(g)][0]) / 2, (g[k][1] + g[(k + 1) % len(g)][1]) / 2) for k in range(len(g))]:
        if not inframe(*p): continue
        n = G.nearest(*p, rad=60)
        if n and (best is None or n[0] < best[0]): best = (n[0], p, n[1])
    return best
piers = []
for f in F:
    if f['t'] == 'pier' and live(f, Y):
        a, b = f['g']; na, nb = G.nearest(*a, rad=30), G.nearest(*b, rad=30)
        da = na[0] if na else 99; db = nb[0] if nb else 99
        root, tip = (a, b) if da <= db else (b, a)   # 离街近的那头是岸
        n = G.nearest(*root, rad=30)
        if n and n[0] < 12 and inframe(*root) and inframe(*tip): piers.append({'root': root, 'tip': tip, 'street': n[1], 'harbor': f.get('harbor'), 'w': f['w']})
fountains = [f for f in F if f['t'] == 'fountain' and f['k'] == 'fountain' and live(f, Y) and inframe(f['x'], f['y'])]
lms = {f['id']: f for f in F if f['t'] == 'landmark' and live(f, Y)}
used = set()
def route(a, b):
    r = G.route(a, b)
    assert r, ('无路', a, b)
    return r

# ---------- 挑人：每一条都只看底账 ----------
# 1 老渔夫：住在尤利安港栈桥边的人家（homes），在这块地上住得最久（建房年份最早）。年纪是从「住得最久」推出来的。
def pick_fisher():
    c = []
    for h in houses:
        if h.get('fn') != 'homes': continue
        m, s, dd = door(h)
        if dd > 8 or not inframe(*m): continue
        for p in piers:
            if p['harbor'] != 'harbor_julian': continue
            d = math.dist(s, p['street'])
            if d < 70: c.append((h['y0'], d, h['id'], h, p))
    c.sort(key=lambda t: (t[0], t[1], t[2]))
    return c[0]
# 2 商人：主街上带柱廊、最高的连排铺面（shops·row·po，ht 最大）。地位来自门脸：主街、柱廊、楼高。
def pick_merchant():
    c = [(-h['ht'], h['y0'], h['id'], h) for h in houses if h.get('fn') == 'shops' and h.get('ty') == 'row' and h.get('po') and str(h.get('sid', '')).startswith('m')
         and inframe(*center(h)) and door(h)[2] < 8]
    c.sort(key=lambda t: t[:3]); return c[0][3]
# 3 挑水的女人：住在坡上的民居，最近的喷泉在她家下坡 60–140 像素（约 50–120 米）处，高差最大的那户——回程满罐上坡最吃力。
def pick_water():
    c = []
    for h in houses:
        if h.get('fn') != 'homes' or h.get('ty') != 'casa' or h['id'] in used: continue
        m, s, dd = door(h)
        if dd > 8 or not inframe(*m): continue
        fs = sorted(fountains, key=lambda f: math.dist(s, (f['x'], f['y'])))
        if not fs: continue
        f = fs[0]; d = math.dist(s, (f['x'], f['y'])); dz = elev(*s) - elev(f['x'], f['y'])
        if 60 <= d <= 140 and dz > 0: c.append((-dz, h['id'], h, f))
    c.sort(key=lambda t: t[:2]); return c[0]
# 5 搬运工：粮仓（狄奥多西港边的 horrea）离栈桥最近的那一对；他住在离那座栈桥最近的民居。
def pick_porter():
    best = None
    for gid in ('horrea_alexandrina', 'horrea_theodosius'):
        if gid not in lms: continue
        ld = lm_door(lms[gid])
        if not ld: continue
        for p in piers:
            if p['harbor'] != 'harbor_theodosius': continue
            r = G.route(p['street'], ld[2])
            if r and (best is None or plen(r) < best[0]): best = (plen(r), gid, ld, p)
    _, gid, ld, p = best
    c = []
    for h in houses:
        if h.get('fn') != 'homes' or h['id'] in used: continue
        m, s, dd = door(h)
        if dd > 8 or not inframe(*m): continue
        d = math.dist(s, p['street'])
        if 25 < d < 160: c.append((d, h['id'], h))
    c.sort(key=lambda t: t[:2]); return c[0][2], gid, ld, p

fy0, fd, _, fh, fp = pick_fisher(); used.add(fh['id'])
mh = pick_merchant(); used.add(mh['id'])
wy = pick_water(); wh, wf = wy[2], wy[3]; used.add(wh['id'])
ph, pg, pld, pp = pick_porter(); used.add(ph['id'])
forum = lms.get('forum_theodosius'); fdoor = lm_door(forum) if forum else None

# ---------- 一天：五个时段。走路按真实步速算时长，停留补到时段结束 ----------
PH = ['黎明', '上午', '正午', '下午', '傍晚']
def mps(v): return v / MPP     # 米每秒 → 像素每秒

class Plan:
    def __init__(s): s.ph = [[] for _ in PH]
    def walk(s, k, path, gait, load=None, tag=None): s.ph[k].append({'a': 'walk', 'path': path, 'gait': gait, 'load': load, 'tag': tag})
    def stay(s, k, at, pose, face=None, load=None, sec=None, tag=None): s.ph[k].append({'a': 'stay', 'at': at, 'pose': pose, 'face': face, 'load': load, 'sec': sec, 'tag': tag})
    def hide(s, k, at, sec=None): s.ph[k].append({'a': 'hide', 'at': at, 'sec': sec})
GAIT = {
    # 步态语法：speed 米/秒，stride 步长米，stoop 前倾（弧度），bob 起伏，swing 摆臂，limp 跛（左右步时长差）
    'old':      {'speed': .72, 'stride': .48, 'stoop': .30, 'bob': .025, 'swing': .25, 'limp': .18},
    'old_load': {'speed': .62, 'stride': .42, 'stoop': .38, 'bob': .02, 'swing': .10, 'limp': .22},
    'child':    {'speed': 1.9, 'stride': .62, 'stoop': .12, 'bob': .07, 'swing': .9, 'limp': 0, 'skip': 1},
    'child_walk': {'speed': .9, 'stride': .40, 'stoop': .05, 'bob': .03, 'swing': .45, 'limp': 0},
    'rich':     {'speed': .95, 'stride': .62, 'stoop': -.06, 'bob': .012, 'swing': .18, 'limp': 0, 'center': 1},
    'servant':  {'speed': .95, 'stride': .55, 'stoop': .14, 'bob': .03, 'swing': .0, 'limp': 0},
    'woman':    {'speed': 1.15, 'stride': .55, 'stoop': .04, 'bob': .03, 'swing': .45, 'limp': 0},
    'woman_full': {'speed': .78, 'stride': .45, 'stoop': -.03, 'bob': .008, 'swing': .2, 'limp': 0},
    'porter_load': {'speed': .9, 'stride': .55, 'stoop': .55, 'bob': .02, 'swing': .0, 'limp': 0},
    'porter':   {'speed': 1.45, 'stride': .75, 'stoop': .10, 'bob': .045, 'swing': .6, 'limp': 0},
    'tired':    {'speed': 1.0, 'stride': .58, 'stoop': .22, 'bob': .03, 'swing': .3, 'limp': 0},
}
def r2(p): return [round(p[0], 1), round(p[1], 1)]
def toward(a, b, k): return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)

R = {}
# 老渔夫 + 孙子
fm, fs, _ = door(fh); pier_path = [fp['street'], fp['root'], toward(fp['root'], fp['tip'], .78)]
home2pier = route(fs, fp['street']) + pier_path[1:]
spot = toward(fp['root'], fp['tip'], .78); face = fp['tip']
F_ = Plan(); C_ = Plan()
F_.hide(0, fm, sec=8); F_.walk(0, [fm] + home2pier, 'old', 'net'); F_.stay(0, spot, 'stand', face, 'net', sec=10)
F_.stay(1, spot, 'mend', face, 'net')
F_.walk(2, list(reversed(home2pier)) + [fm], 'old_load', 'catch'); F_.stay(2, fm, 'sit', None, None)
F_.stay(3, fm, 'sit', None, None); F_.stay(4, fm, 'sit', None, None, sec=30); F_.hide(4, fm)
play = [fp['street'], toward(fp['street'], fp['root'], .6)]
C_.hide(0, fm, sec=8); C_.walk(0, [fm] + home2pier[:-1] + [toward(fp['root'], fp['tip'], .35)], 'child_walk', None, 'follow')
C_.stay(0, toward(fp['root'], fp['tip'], .35), 'stand', fp['tip'], sec=10)
C_.stay(1, toward(fp['root'], fp['tip'], .35), 'play', None, None, tag='play')
C_.walk(2, [toward(fp['root'], fp['tip'], .35)] + list(reversed(home2pier[:-1])) + [fm], 'child', None, 'ahead'); C_.stay(2, fm, 'wait', fp['street'])
C_.stay(3, fm, 'play', None, None, tag='play'); C_.stay(4, fm, 'play', None, sec=24, tag='play'); C_.hide(4, fm)
R['f'] = (F_, {'house': fh['id'], 'fn': fh['fn'], 'ty': fh['ty'], 'y0': fh['y0'], 'pier': r2(fp['root']), 'years_here': Y - fh['y0']})
R['c'] = (C_, {'house': fh['id'], 'with': 'f'})
# 商人 + 仆人
mm, ms, _ = door(mh); shopfront = toward(mm, ms, .6)
M_ = Plan(); S_ = Plan()
to_forum = route(ms, fdoor[2]) + [toward(fdoor[2], fdoor[1], .5)]
M_.hide(0, mm); M_.walk(1, [mm, shopfront], 'rich'); M_.stay(1, shopfront, 'sell', ms)
M_.walk(2, [shopfront] + to_forum, 'rich'); M_.stay(2, to_forum[-1], 'talk', fdoor[1])
M_.stay(3, to_forum[-1], 'talk', fdoor[1]); M_.walk(4, list(reversed(to_forum)) + [shopfront, mm], 'rich'); M_.hide(4, mm)
S_.hide(0, mm); S_.walk(1, [mm, toward(shopfront, mm, -.6)], 'servant', 'crate'); S_.stay(1, toward(shopfront, mm, -.6), 'stand', ms, 'crate')
S_.walk(2, [toward(shopfront, mm, -.6)] + to_forum, 'servant', 'crate', 'follow'); S_.stay(2, to_forum[-1], 'stand', fdoor[1], 'crate')
S_.stay(3, to_forum[-1], 'stand', fdoor[1], 'crate'); S_.walk(4, list(reversed(to_forum)) + [shopfront, mm], 'servant', 'crate', 'follow'); S_.hide(4, mm)
R['m'] = (M_, {'house': mh['id'], 'fn': mh['fn'], 'ty': mh['ty'], 'ht': mh['ht'], 'po': mh['po'], 'sid': mh['sid'], 'to': 'forum_theodosius'})
R['s'] = (S_, {'house': mh['id'], 'with': 'm'})
# 挑水的女人：一天三趟
wm, ws, _ = door(wh); fpt = (wf['x'], wf['y']); fn_ = G.nearest(*fpt, rad=60)
to_f = route(ws, fn_[1]) + [toward(fn_[1], fpt, .55)]
W_ = Plan()
for k in (0, 3, 4):
    W_.hide(k, wm, sec=6 if k else 4); W_.walk(k, [wm] + to_f, 'woman', 'jar_empty'); W_.stay(k, to_f[-1], 'queue', fpt, 'jar_empty', sec=26)
    W_.walk(k, list(reversed(to_f)) + [wm], 'woman_full', 'jar_full'); W_.hide(k, wm)
W_.stay(1, toward(wm, ws, .5), 'spin', ws); W_.hide(2, wm)
R['w'] = (W_, {'house': wh['id'], 'fn': wh['fn'], 'ty': wh['ty'], 'fountain': r2(fpt), 'climb_m': round(elev(*ws) - elev(*fpt), 1), 'dist_m': round(plen(to_f) * MPP)})
# 搬运工：栈桥 ↔ 粮仓，往返
hm, hs, _ = door(ph); g_in = toward(pld[2], pld[1], .5)
p2g = [toward(pp['root'], pp['tip'], .6), pp['root']] + route(pp['street'], pld[2]) + [g_in]
home2p = route(hs, pp['street']) + [pp['root'], toward(pp['root'], pp['tip'], .6)]
P_ = Plan(); P_.hide(0, hm, sec=4); P_.walk(0, [hm] + home2p, 'porter')
for k in (1, 3):
    P_.walk(k, p2g, 'porter_load', 'sack', 'loop'); P_.walk(k, list(reversed(p2g)), 'porter', None, 'loop')
P_.stay(2, toward(pld[2], pld[1], .2), 'rest', pld[1])
P_.walk(4, list(reversed(home2p)) + [hm], 'tired'); P_.hide(4, hm)
R['p'] = (P_, {'house': ph['id'], 'granary': pg, 'pier': r2(pp['root']), 'trip_m': round(plen(p2g) * MPP)})

# ---------- 排时间：每个时段的长度 = 所有人在这段里「必须」花的时间里最长的那个 + 余量 ----------
def need(a):
    if a['a'] == 'walk': return plen(a['path']) / mps(GAIT[a['gait']]['speed'])
    return a.get('sec') or 0
LOOPS = 2
lens = []
for k in range(len(PH)):
    m = 0
    for pl, _ in R.values():
        t = 0
        for a in pl.ph[k]: t += need(a) * (LOOPS if a.get('tag') == 'loop' else 1)
        m = max(m, t)
    lens.append(math.ceil(m + 25))
starts = [sum(lens[:k]) for k in range(len(PH))]
out = []
CAST = {
    'f': {'h': 1.62, 'build': .95, 'cloth': 'short', 'color': '#b8a788', 'hair': '#d9d4c8', 'beard': 1},
    'c': {'h': 1.15, 'build': .8, 'cloth': 'short', 'color': '#c9b48a', 'hair': '#3a2a1c'},
    'm': {'h': 1.72, 'build': 1.12, 'cloth': 'long', 'color': '#5a2f4a', 'trim': '#c9a34a', 'hair': '#2a1e16', 'beard': 1, 'hat': 1},
    's': {'h': 1.60, 'build': .9, 'cloth': 'short', 'color': '#8a7a5a', 'hair': '#2a1e16'},
    'w': {'h': 1.58, 'build': .92, 'cloth': 'long', 'color': '#a85a3c', 'veil': '#e8dfcb', 'hair': '#2a1e16'},
    'p': {'h': 1.74, 'build': 1.2, 'cloth': 'short', 'color': '#6e5038', 'hair': '#1e1610', 'bare': 1},
}
ROLE = {'f': '老渔夫', 'c': '孙子', 'm': '商人', 's': '商人家的仆人', 'w': '挑水的女人', 'p': '粮仓搬运工'}
for key, (pl, facts) in R.items():
    acts = []
    for k in range(len(PH)):
        t, T1 = starts[k], starts[k] + lens[k]
        seq = []; acts_k = pl.ph[k]; i = 0
        while i < len(acts_k):   # 连着的 loop 动作当一组，整组重复（扛着去、空手回，再扛着去……）
            if acts_k[i].get('tag') == 'loop':
                j = i
                while j < len(acts_k) and acts_k[j].get('tag') == 'loop': j += 1
                seq += acts_k[i:j] * LOOPS; i = j
            else: seq.append(acts_k[i]); i += 1
        fixed = sum(need(a) for a in seq if a['a'] == 'walk' or a.get('sec'))
        flex = [a for a in seq if a['a'] != 'walk' and not a.get('sec')]
        spare = max(0, T1 - t - fixed) / (len(flex) or 1)
        if not flex and seq: spare = 0
        for a in seq:
            d = need(a) if (a['a'] == 'walk' or a.get('sec')) else spare
            b = {kk: v for kk, v in a.items() if v is not None and kk not in ('sec', 'tag')}
            if a.get('tag') in ('follow', 'ahead', 'play'): b['tag'] = a['tag']
            if 'path' in b: b['path'] = [r2(p) for p in b['path']]
            for kk in ('at', 'face'):
                if kk in b: b[kk] = r2(b[kk])
            b['t0'] = round(t, 1); b['t1'] = round(t + d, 1); t += d; acts.append(b)
        if acts and acts[-1]['t1'] < T1:   # 时段还没完：原地等
            last = acts[-1]; at = last['path'][-1] if last['a'] == 'walk' else last['at']
            acts.append({'a': 'hide' if last['a'] == 'hide' else 'stay', 'at': at, 'pose': last.get('pose', 'stand'), 't0': round(t, 1), 't1': T1, **({'load': last['load']} if last.get('load') else {})})
    out.append({'id': key, 'n': list(R).index(key) + 1 if key in 'fmwpc' else None, 'role': ROLE[key], 'cast': CAST[key], 'facts': facts, 'acts': acts})
order = {'f': 1, 'm': 2, 'w': 3, 'c': 4, 'p': 5}
for o in out: o['n'] = order.get(o['id'])
res = {'q': Q, 'year': Y, 'mpp': MPP, 'phases': [[PH[k], starts[k], lens[k]] for k in range(len(PH))], 'T': sum(lens), 'gait': GAIT,
       'note': '居民节点试作：只从底账挑人、推行为。role 只给答案页用，主页面不显示任何字。——Hark（CS线）', 'people': out}
dst = os.path.join(ROOT, 'docs/living/nodes', Q, 'people.json')
json.dump(res, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
print('写出', dst, os.path.getsize(dst), '字节；一天', sum(lens), '秒', [(p[0], p[2]) for p in res['phases']])
for o in out: print(o['n'], o['role'], o['facts'])
