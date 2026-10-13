"""规则预演 v5 · 预计算：逐户逐年户主与继承事件（只读 v0 数据层，缓存到仓库外 ../rules_v5_<scope>.pkl）。
户序与 rules_v1/prep.py 的 arrays 完全相同（房子顺序 × fams 顺序），所以户号 F 可直接对上 v1/v2/v3 的户。
户主规则（假设 S1，家谱只有辈分 g 字段、没有父子指针，亲属按辈分推）：
  初始：在家成年男（≥A）里辈分最小、最年长的；没有 → 同辈媳妇（寡妇）；没有 → 在家最年长者（孤儿当家）
  户主不在家（死 / 离家）→ 继承顺序 儿子(g0+1 成年男) → 寡妇(g0 媳妇) → 兄弟(g0 成年男) → 孙子(g0+2) → 其他成年男 → 孤儿(最年长在家者)
  寡妇 / 孤儿 / 其他当家时，户里儿子（家主辈 +1）或孙子（+2）满 A 岁即接手（「儿子满龄」「孙子满龄」）
  户结束：Y ≥ 房子拆年 → 被拆；Y ≥ 下一家搬入年 → 迁走；其余无人在家 → 绝户
A = 14（主），16（变体）。
usage: python3 prep5.py xero|city
"""
import sys, os, time, pickle, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rules_v0'))
import data as D0  # noqa: E402  (v0 数据层，只读)

YR0, YR1 = 40, 70
NY = YR1 - YR0 + 1
KIND = ['男', '寡妇', '孤儿', '其他成年男']          # 户主身份
EV = ['儿子', '儿子满龄', '寡妇', '兄弟', '孙子', '孙子满龄', '其他成年男', '孤儿', '绝户', '迁走', '被拆', '复户']


def cache_path(scope): return os.path.join(D0.CACHE, f'rules_v5_{scope}.pkl')


def succession(houses, A):
    """返回 head[F,yi]（全局人号，-1 = 不在场）、hkind[F,yi]、events[(F,Y,ev,old,new)]、人表。"""
    P = dict(n=[], s=[], b=[], d=[], g=[], bride=[], m=[], l=[], to=[], f=[])
    fam = dict(h=[], B=[], Bn=[], origin=[], faith=[], trade=[], p0=[], name=[])
    for i, h in enumerate(houses):
        for j, f in enumerate(h['fams']):
            fam['h'].append(i); fam['B'].append(f['B'])
            fam['Bn'].append(h['fams'][j + 1]['B'] if j + 1 < len(h['fams']) else 10 ** 6)
            fam['origin'].append(f['origin']); fam['faith'].append(f['faith']); fam['trade'].append(f['trade'])
            fam['p0'].append(len(P['n']))
            fam['name'].append((f['people'][0]['n'] if f['people'] else '?') + '家')
            for p in f['people']:
                P['n'].append(p['n']); P['s'].append(p['s'] == 'm'); P['b'].append(p['b']); P['d'].append(p['d']); P['g'].append(p['g'])
                P['bride'].append(bool(p['bride'])); P['m'].append(p['married'] or 0); P['l'].append(p['left'] or 0)
                P['to'].append(p['to']); P['f'].append(len(fam['B']) - 1)
    Fn = len(fam['B']); fam['p0'].append(len(P['n']))
    hb = np.array([h['built'] for h in houses]); hd = np.array([h['destroyed'] for h in houses])
    b = np.array(P['b']); d = np.array(P['d']); s = np.array(P['s']); g = np.array(P['g']); br = np.array(P['bride'])
    m = np.array(P['m']); l = np.array(P['l'])
    head = np.full((Fn, NY), -1, np.int32); hk = np.full((Fn, NY), -1, np.int8); events = []
    for F in range(Fn):
        a, z = fam['p0'][F], fam['p0'][F + 1]
        if a == z: continue
        bb, dd, ss, gg, bbr, mm, ll = b[a:z], d[a:z], s[a:z], g[a:z], br[a:z], m[a:z], l[a:z]
        hi = fam['h'][F]; B, Bn = fam['B'][F], fam['Bn'][F]
        cur = -1; kind = -1; lord = None; active = False
        for Y in range(max(YR0, B), YR1 + 1):
            yi = Y - YR0
            home = (bb <= Y) & (Y < dd) & ((mm == 0) | (mm <= Y)) & ~((ll != 0) & (ll <= Y))
            stand = hb[hi] <= Y < hd[hi] and B <= Y < Bn
            if not (stand and home.any()):
                if active:
                    ev = '被拆' if Y >= hd[hi] else '迁走' if Y >= Bn else '绝户'
                    events.append((F, Y, ev, a + cur, -1)); active = False; cur = -1
                if Y >= hd[hi] or Y >= Bn: break
                continue
            age = Y - bb
            am = home & ss & (age >= A)

            def oldest(mask):
                ix = np.nonzero(mask)[0]
                return int(ix[np.argmin(bb[ix])]) if len(ix) else -1
            if not active:
                first = (Y == max(YR0, B))
                if am.any():
                    g0 = gg[am].min(); cur = oldest(am & (gg == g0)); kind = 0; lord = g0
                elif (home & bbr & ~ss).any():
                    g0 = gg[home & bbr & ~ss].min(); cur = oldest(home & bbr & ~ss & (gg == g0)); kind = 1; lord = g0
                else:
                    cur = oldest(home); kind = 2; lord = gg[cur] - 1
                if not first: events.append((F, Y, '复户', -1, a + cur))
                active = True
            elif home[cur]:
                if kind != 0:                                   # 摄政：儿 / 孙满龄接手
                    for dg, ev in ((1, '儿子满龄'), (2, '孙子满龄')):
                        c = oldest(am & (gg == lord + dg))
                        if c >= 0:
                            events.append((F, Y, ev, a + cur, a + c)); cur = c; kind = 0; lord = gg[c]; break
            else:
                g0 = lord
                order = [('儿子', am & (gg == g0 + 1), 0), ('寡妇', home & bbr & ~ss & (gg == g0), 1), ('兄弟', am & (gg == g0), 0),
                         ('孙子', am & (gg == g0 + 2), 0), ('其他成年男', am, 3), ('孤儿', home, 2)]
                for ev, mask, k in order:
                    c = oldest(mask)
                    if c >= 0:
                        events.append((F, Y, ev, a + cur, a + c)); cur = c; kind = k
                        if k in (0, 3): lord = gg[c]
                        break
            head[F, yi] = a + cur; hk[F, yi] = kind
    return head, hk, events, P, fam


def build(scope):
    t0 = time.time()
    W = D0.load_city() if scope == 'city' else D0.load_xero()
    t_load = time.time() - t0
    out = dict(scope=scope, YR0=YR0, YR1=YR1, KIND=KIND)
    for A in (14, 16):
        t = time.time()
        head, hk, ev, P, fam = succession(W['houses'], A)
        out[A] = dict(head=head, hk=hk, events=ev, seconds=round(time.time() - t, 2))
    out['P'] = P; out['fam'] = fam
    out['hid'] = [h['id'] for h in W['houses']]
    out['hbuilt'] = np.array([h['built'] for h in W['houses']]); out['hdest'] = np.array([h['destroyed'] for h in W['houses']])
    pickle.dump(out, open(cache_path(scope), 'wb'), protocol=5)
    import collections
    c = collections.Counter(e[2] for e in out[14]['events'])
    print(json.dumps(dict(scope=scope, families=len(fam['B']), people=len(P['n']), load_s=round(t_load, 2),
                          succ_s={A: out[A]['seconds'] for A in (14, 16)}, total_s=round(time.time() - t0, 2),
                          events14=dict(c), cache_bytes=os.path.getsize(cache_path(scope))), ensure_ascii=False))


def load(scope): return pickle.load(open(cache_path(scope), 'rb'))


if __name__ == '__main__':
    build(sys.argv[1])
