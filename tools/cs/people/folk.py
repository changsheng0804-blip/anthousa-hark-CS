"""户籍 + 社会关系 → 街上的人（2026-10-19）。
把以前写在每版页面里的户籍生成器（cs1…cs29 的 household()）搬到节点上，再把散在各处的关系合成一套：
  1. 每栋真房子按种子生出先后几家人（名字、从哪来、信什么、哪一行、生老病死、娶进嫁出）。
  2. 合并：同一个人在两本户籍里各有一份（女儿嫁出去 / 别家娶进来一个新妇），按「性别 + 出嫁年份 ±4 + 两家距离」
     认成同一个人，名字以娘家为准，两家从此是亲家。
  3. 户与户的关系不手写，按共同的键连：同一条街门挨门 → 邻居；同乡（外地来的）→ 同乡；
     码头上扛活的 → 最近那家码头/粮仓户是东家；家里记着债 → 附近粮商/钱商是债主；
     邻居里一家阿里乌派、一家尼西亚派 → 一半不来往。
  4. 关系决定人往哪走：扛活的去东家门口，回娘家的去娘家门口，欠债的去债主门口；
     孩子跟着母亲，没出嫁的女儿跟着母亲去打水；同一口喷泉的邻居妇人约好同时到，在喷泉边说话。
写 crowd.json（页面 crowd.js 读）。
  python3 tools/cs/people/folk.py nangang [年份] [户数]
——Hark（CS线）"""
import sys, os
sys.argv = sys.argv[:3] + ['0'] if len(sys.argv) > 3 else sys.argv
NH = int(os.environ.get('NH', '1400'))
exec(open(os.path.join(os.path.dirname(__file__), '_folk_base.py'), encoding='utf-8').read())
CITY = json.load(open(os.path.join(ROOT, 'docs/living/city.json'), encoding='utf-8'))
NM = [n for n in CITY['names_m'] if n != '狄奥多罗斯'] + ['格奥尔基奥斯','阿尔塞尼乌斯','佛提乌','雅各','米哈伊尔','狄米特里','马可','菲利普','科斯马斯','达米安','欧瑟比乌斯','利奥','提摩太','巴西尔','阿塔纳修斯','以撒','西奥菲勒斯','卡利尼科斯','安德烈亚斯','尼刻塔斯','君士坦丁','塞奥多图斯','阿加通','狄奥尼修斯','赫拉克勒奥斯','卢西安','欧蒂基乌斯','帕科米乌斯','索佐蒙','特里丰','瓦西里斯','克莱门特','忒奥格尼斯','阿波罗尼乌斯','埃皮法尼乌斯','格里高利','伊西多尔','约翰','以利亚','西门','斯特凡诺斯','德米特里乌斯','安提帕特','奥林匹奥斯','普罗科匹乌斯','塞维鲁斯']
NF = [n for n in CITY['names_f'] if n != '达芙涅'] + ['阿格尼丝','马克里娜','索菲娅','欧朵西娅','普尔喀丽娅','西奥多西娅','奥林匹娅丝','克里斯蒂娜','巴尔巴拉','费布罗妮娅','塔伊斯','妮娜','尤朵拉','玛尔塔','苏珊娜','阿波洛尼娅','安娜','忒克拉','伊琳娜','卡西娅','狄奥多拉','欧多克西娅','福柏','莉迪娅','菲洛梅娜','科琳娜','佐伊','伊莱妮','玛格丽塔','普丽斯卡','西尔维娅','卢西娅','多萝西娅','阿纳斯塔西娅','克劳迪娅','帕拉斯凯维','忒奥多特','赫丽娜','罗得','黛博拉','以斯帖','玛蒂娜','塞克斯蒂娅','康斯坦蒂娅']
ORIG, FAITH = CITY['origins'], CITY['faiths']
TR = dict(CITY['trades']); TR['market'] = ['卖油的', '卖布的', '卖鱼的', '卖果子的', '卖陶器的', '面包师']
OBJ = ['一盏印着凯乐符号的陶灯','一枚瓦伦斯的铜币，被摸得发亮','从{o}带来的一只陶罐，补过两次','一块蜡板，上面记着谁还欠他们钱','门楣上一个刻歪了的十字','一副骨头骰子，藏在枕头底下','一张蓝党的赛马签，已经输了','一小瓶从圣地带回来的油','一把铜钥匙，门早就换过了','墙角一尊没人敢扔的家神像','一卷写着孩子生日的莎草纸','一只少了把手的玻璃杯，是嫁妆']
ARRIVE = [(-999,0,'祖上就住在拜扎斯旧城'),(1,10,'跟着奠基的工程来的'),(11,20,'水渠修通后来的'),(21,30,'大教堂开工那几年来的'),(31,40,'跟着粮船进的城'),(41,47,'瓦伦斯在位时来的'),(48,50,'南港大火烧了原来的家，才搬来这里'),(51,55,'狄奥多西刚登基那几年来的'),(56,60,'跟着埃及的粮船来的')]
AWAY = ['去当了兵', '去码头上找活干', '去给一个石匠当学徒', '进了修道院', '跟着粮船出了海']
cen = lambda h: (sum(poly(h)[i][0] for i in range(len(poly(h)))) / len(poly(h)), sum(q[1] for q in poly(h)) / len(poly(h)))

# ---------- 抽户：有门、在画面里 ----------
cands = [h for h in houses if h.get('fn') in ('homes', 'shops', 'market', 'dock', 'horrea')]
rng.shuffle(cands)
POOL = []
for h in cands:
    if len(POOL) >= NH: break
    d = door(h)
    if d and inframe(*d[0]): h['_door'], h['_c'] = d, cen(h); POOL.append(h)
HID = {h['id']: i for i, h in enumerate(POOL)}

def lt_of(h):
    fn = h.get('fn'); s = h['_door'][1]; hb = nearest(s, piers); dh = math.dist(s, hb) if hb else 1e9
    if fn in ('dock', 'horrea') or (fn == 'homes' and dh < 260 and h['id'] % 3 == 0): return 'harbor'
    if fn == 'market': return 'market'
    if fn == 'shops' and (h.get('po') or (h.get('ht') or 0) >= 14): return 'forum'
    return 'other'

# ---------- 户籍：cs 页面里 household() 的移植，每栋房子一颗种子 ----------
def household(h):
    r = random.Random('hh%d' % h['id']); pick = lambda L: L[int(r.random() * len(L))]
    people, ev, used, fams = [], [], set(), []
    END = min(Y, (h['y1'] or 9999) - 1); lt = lt_of(h)
    def nm(sx):
        L = NM if sx == 'm' else NF
        for _ in range(12):
            n = pick(L)
            if n not in used: used.add(n); return n
        return pick(L)
    def lifespan():
        q = r.random()
        return int(r.random() * 5) if q < .22 else 5 + int(r.random() * 20) if q < .3 else 28 + int(r.random() * 45)
    B = -int(r.random() * 40) if h['y0'] < 1 else h['y0']; first = True
    while B <= END and len(fams) < 5:
        origin = '本城生' if ((first and h['y0'] < 1 and r.random() < .7) or (not first and r.random() < .35)) else pick([o for o in ORIG if o != '本城生'])
        fr = r.random(); faith = FAITH[0] if fr < .55 else FAITH[1] if fr < .8 else FAITH[2]
        fam = {'B': B, 'origin': origin, 'faith': faith, 'trade': pick(TR[lt] if lt in TR else TR['other']), 'people': []}; fams.append(fam)
        def P(p): p['fam'] = len(fams) - 1; p['h'] = h['id']; fam['people'].append(p); people.append(p); return p
        def E(y, t, who=()):
            if fam['B'] <= y <= END: ev.append((y, t, who))
        hA = 20 + int(r.random() * 18)
        head = P({'n': nm('m'), 's': 'm', 'b': B - hA, 'g': 0, 'head': True}); head['d'] = max(head['b'] + lifespan(), B + 1 + int(r.random() * 6))
        wife = P({'n': nm('f'), 's': 'f', 'b': head['b'] + 2 + int(r.random() * 8), 'g': 0, 'bride': True, 'sp': head}); wife['d'] = max(wife['b'] + lifespan(), B + 1); head['sp'] = wife
        arr = next(a[2] for a in ARRIVE if a[0] <= B <= a[1]); fam['arrive'] = arr
        def line(fa, mo, g):
            y = max(mo['b'] + 17, fa['b'] + 19, B - 25); end = min(mo['b'] + 40, mo['d'], fa['d'] + 1, Y); heir = False
            while True:
                y += 1 + int(r.random() * 3)
                if y > end: break
                sx = 'm' if r.random() < .5 else 'f'; k = P({'n': nm(sx), 's': sx, 'b': y, 'g': g + 1, 'fa': fa, 'mo': mo}); k['d'] = k['b'] + lifespan()
                life = k['d'] - k['b']
                if life < 5: E(k['d'], 'lost', (mo, fa))
                else: E(y, 'born', (mo, fa, k))
                if sx == 'm' and life > 21 and g < 4:
                    wy = k['b'] + 20 + int(r.random() * 6)
                    if not heir and wy < k['d'] and wy <= Y:
                        heir = True; br = P({'n': nm('f'), 's': 'f', 'b': k['b'] - 2 + int(r.random() * 6), 'g': g + 1, 'bride': True, 'married': wy, 'sp': k}); br['d'] = max(br['b'] + lifespan(), wy + 1); k['sp'] = br
                        E(wy, 'wed', (k, br)); line(k, br, g + 1)
                    else:
                        ly = k['b'] + 17 + int(r.random() * 5)
                        if ly < k['d'] and ly <= Y: k['left'] = ly; k['away'] = pick(AWAY)
                elif sx == 'f' and life > 17:
                    wy = k['b'] + 15 + int(r.random() * 5)
                    if wy < k['d'] and wy <= Y:
                        k['left'] = wy; k['wedout'] = wy; k['aim'] = (h['_c'][0] + (r.random() - .5) * 200, h['_c'][1] + (r.random() - .5) * 200)
        line(head, wife, 0)
        for p in fam['people']:
            if p['d'] <= END and p['d'] >= B and p['d'] - p['b'] >= 5 and not (p.get('left') and p['left'] <= p['d']): E(p['d'], 'died', (p,))
        last = B
        for p in fam['people']:
            if p['b'] > B + 60: continue
            o = min(p['left'], p['d']) if p.get('left') else p['d']; last = max(last, o)
        fam['out'] = last; first = False; B = last + 1 + int(r.random() * 3)
    obj = pick(OBJ).replace('{o}', '老家' if fams[0]['origin'] == '本城生' else fams[0]['origin'])
    f = fams[0]
    for x in fams:
        if x['B'] <= Y: f = x
    return {'h': h, 'fams': fams, 'cur': f, 'people': people, 'ev': ev, 'obj': obj, 'debt': '欠' in obj or r.random() < .14, 'lt': lt}

HH = [household(h) for h in POOL]
alive = lambda p: p['b'] <= Y < p['d'] and (not p.get('married') or p['married'] <= Y) and not (p.get('left') and p['left'] <= Y)
for hh in HH: hh['al'] = [p for p in HH and hh['fams'][hh['fams'].index(hh['cur'])]['people'] if alive(p)]

# ---------- 合并：嫁出去的女儿 = 别家户籍里娶进来的新妇 ----------
grid = {}
for i, h in enumerate(POOL): grid.setdefault((int(h['_c'][0] // 200), int(h['_c'][1] // 200)), []).append(i)
def near_houses(x, y, R):
    out = []
    for gx in range(int(x // 200) - (R // 200 + 1), int(x // 200) + R // 200 + 2):
        for gy in range(int(y // 200) - (R // 200 + 1), int(y // 200) + R // 200 + 2):
            for i in grid.get((gx, gy), []):
                d = math.dist((x, y), POOL[i]['_c'])
                if d < R: out.append((d, i))
    return sorted(out)
merged = 0
for i, hh in enumerate(HH):
    for k in hh['people']:
        if not k.get('wedout') or k['d'] <= Y: continue
        for d, j in near_houses(*k['aim'], 170):
            if j == i: continue
            br = next((b for b in HH[j]['people'] if b.get('bride') and b.get('married') and abs(b['married'] - k['wedout']) <= 4 and not b.get('natal') and alive(b)), None)
            if br:
                br['n'] = k['n']; br['b'] = k['b']; br['natal'] = (i, k); k['to'] = (j, br); merged += 1
                HH[j]['ties'] = HH[j].get('ties', []) + [(i, 'natal')]; hh['ties'] = hh.get('ties', []) + [(j, 'inlaw')]
                break

# ---------- 户与户：按共同的键连 ----------
def door_pt(i): return POOL[i]['_door'][0]
for i, hh in enumerate(HH):
    h = POOL[i]; T = hh.setdefault('ties', [])
    nb = [(d, j) for d, j in near_houses(*h['_c'], 60) if j != i and POOL[j].get('sid') == h.get('sid')][:3]
    for d, j in nb:
        a, b = hh['cur']['faith'], HH[j]['cur']['faith']
        cold = {a, b} == {'阿里乌派', '尼西亚派'} and (h['id'] + POOL[j]['id']) % 2 == 0
        T.append((j, 'cold' if cold else 'nb'))
    o = hh['cur']['origin']
    if o != '本城生':
        same = [(d, j) for d, j in near_houses(*h['_c'], 160) if j != i and HH[j]['cur']['origin'] == o and all(t[0] != j for t in T)][:2]
        T += [(j, 'home') for d, j in same]
    if hh['lt'] == 'harbor' and h.get('fn') == 'homes':
        emp = next(((d, j) for d, j in near_houses(*h['_c'], 320) if POOL[j].get('fn') in ('dock', 'horrea')), None)
        if emp: hh['emp'] = emp[1]; T.append((emp[1], 'boss')); HH[emp[1]].setdefault('ties', []).append((i, 'hand'))
    if hh['debt']:
        cr = next(((d, j) for d, j in near_houses(*h['_c'], 260) if j != i and HH[j]['cur']['trade'] in ('粮商', '银钱商', '卖油的', '卖布的')), None)
        if cr: hh['cred'] = cr[1]; T.append((cr[1], 'cred')); HH[cr[1]].setdefault('ties', []).append((i, 'debtor'))

# ---------- 每个人：在家里的位置 → 今天出不出门、去哪、跟谁 ----------
RT, RK = [], {}
def route_to(i, key, dst, why):
    k = (i, key)
    if k in RK: return RK[k]
    s = POOL[i]['_door'][1]
    if dst is None or math.dist(s, dst) < 25: RK[k] = None; return None
    r = G.route(s, dst)
    if not r: RK[k] = None; return None
    L = plen(r) * MPP
    if L < 25 or L > 1000: RK[k] = None; return None
    r = rdp([POOL[i]['_door'][0]] + r)
    RT.append({'h': POOL[i]['id'], 'why': why, 'len_m': round(L), 'path': [[round(p[0], 1), round(p[1], 1)] for p in r]}); RK[k] = len(RT) - 1; return RK[k]
mk_doors = [door(x) for x in markets]; mk_doors = [d[1] for d in mk_doors if d]
def plan(i, p, hh, rr):
    s = POOL[i]['_door'][1]; age = Y - p['b']; tr = hh['cur']['trade']; lt = hh['lt']
    if age < 4: return None
    if p['s'] == 'f' and age >= 15 or p['s'] == 'f' and p.get('bride'):
        if age >= 62 and rr.random() < .5: return None
        if p.get('natal') and rr.random() < .35:
            j = p['natal'][0]; return ('visit', route_to(i, 'n%d' % j, POOL[j]['_door'][1], 'visit'), j)
        f = nearest(s, fount)
        if f and math.dist(s, f) < 240: return ('water', route_to(i, 'w', f, 'water'), None)
        return ('market', route_to(i, 'm', nearest(s, mk_doors), 'market'), None)
    if p['s'] == 'm' and age >= 15:
        if age >= 62: return ('forum', route_to(i, 'f', nearest(s, forum), 'forum'), None) if rr.random() < .5 else None
        if hh.get('cred') is not None and p.get('head') and rr.random() < .5:
            j = hh['cred']; return ('debt', route_to(i, 'c%d' % j, POOL[j]['_door'][1], 'debt'), j)
        if lt == 'harbor':
            if hh.get('emp') is not None: j = hh['emp']; return ('haul', route_to(i, 'e%d' % j, POOL[j]['_door'][1], 'haul'), j)
            dst = nearest(s, granary) if granary and POOL[i]['id'] % 2 else nearest(s, piers); return ('haul', route_to(i, 'p', dst, 'haul'), None)
        if lt == 'market' or POOL[i].get('fn') == 'shops' and lt == 'other' and rr.random() < .4: return ('market', route_to(i, 'm', nearest(s, mk_doors), 'market'), None)
        if lt == 'forum': return ('forum', route_to(i, 'f', nearest(s, forum), 'forum'), None)
        return ('errand', route_to(i, 'm', nearest(s, mk_doors), 'errand'), None) if rr.random() < .5 else None
    return 'follow'

def rel(a, b):   # b 是 a 的什么人
    if a.get('sp') is b: return '丈夫' if b['s'] == 'm' else '妻子'
    if a.get('fa') is b: return '父亲'
    if a.get('mo') is b: return '母亲'
    if b.get('fa') is a or b.get('mo') is a: return '儿子' if b['s'] == 'm' else '女儿'
    sp = a.get('sp')
    if sp and (sp.get('fa') is b or sp.get('mo') is b): return '公公' if b['s'] == 'm' else '婆婆'
    if b.get('sp') and (b['sp'].get('fa') is a or b['sp'].get('mo') is a): return '儿媳' if b['s'] == 'f' else '女婿'
    if a.get('fa') and a.get('fa') is b.get('fa'): return ('哥哥' if b['b'] < a['b'] else '弟弟') if b['s'] == 'm' else ('姐姐' if b['b'] < a['b'] else '妹妹')
    for x in (a.get('fa'), a.get('mo')):
        if x and (x.get('fa') is b or x.get('mo') is b): return '爷爷' if b['s'] == 'm' else '奶奶'
    for x in (b.get('fa'), b.get('mo')):
        if x and (x.get('fa') is a or x.get('mo') is a): return '孙子' if b['s'] == 'm' else '孙女'
    return '家里人'

OUT, PID = [], {}
for i, hh in enumerate(HH):
    rr = random.Random('day%d' % POOL[i]['id'])
    head = next((p for p in hh['al'] if p.get('head')), None) or min((p for p in hh['al'] if p['s'] == 'm' and Y - p['b'] >= 18), key=lambda p: p['b'], default=None) or min(hh['al'], key=lambda p: p['b'], default=None)
    if not head: continue
    hh['headN'] = head['n']; hh['hd'] = head; mine = []
    for p in sorted(hh['al'], key=lambda p: p['b']):
        pl = plan(i, p, hh, rr)
        if pl == 'follow' and (Y - p['b'] < 5 or rr.random() < .45): continue   # 小的、或今天不出门的孩子留在家
        if pl is None or (pl != 'follow' and pl[1] is None): continue
        mine.append([p, pl])
    for it in mine:                                                  # 孩子跟母亲，没母亲在外跟父亲；没出嫁的女儿跟母亲去打水
        p, pl = it; age = Y - p['b']
        if pl == 'follow' or (p['s'] == 'f' and not p.get('bride') and age < 18 and not p.get('natal') and rr.random() < .6):
            lead = next((x for x, q in mine if x is p.get('mo') and q != 'follow' and q[0] != 'follow'), None) or next((x for x, q in mine if x is p.get('fa') and q != 'follow'), None)
            it[1] = ('follow', None, lead) if lead else None
    for p, pl in mine:
        if pl is None: continue
        PID[id(p)] = len(OUT); OUT.append({'p': p, 'i': i, 'pl': pl})

# ---------- 喷泉边的约伴：同一口喷泉的邻居妇人 ----------
byf = {}
for k, o in enumerate(OUT):
    if o['pl'][0] == 'water' and o['p'].get('bride'): byf.setdefault(o['i'], []).append(k)
meet = {}
for i, hh in enumerate(HH):
    for j, t in hh.get('ties', []):
        if t in ('nb', 'home') and i in byf and j in byf:
            a, b = byf[i][0], byf[j][0]
            fa, fb = RT[OUT[a]['pl'][1]]['path'][-1], RT[OUT[b]['pl'][1]]['path'][-1]
            if a not in meet and b not in meet and fa == fb: meet[a] = b; meet[b] = a

# ---------- 一句人话里的那件事：从底账里挑最要紧的一件 ----------
def fact(o):
    p, i = o['p'], o['i']; hh = HH[i]; age = Y - p['b']; c = []
    if p.get('natal'):
        j = p['natal'][0]; c.append((5, '娘家是%s的%s家，嫁过来%d年了' % (HH[j]['cur']['trade'], HH[j].get('headN') or '', Y - p['married'])))
    for y, kind, who in hh['ev']:
        if not any(w is p for w in who) and not (kind == 'died' and p.get('sp') is who[0]): continue
        if kind == 'died' and p.get('sp') is who[0] and Y - y <= 6: c.append((9, '%s前年死了，家里的担子落在%s身上' % ('男人' if p['s'] == 'f' else '女人', '她' if p['s'] == 'f' else '他') if Y - y <= 2 else '%s死了%d年了' % ('男人' if p['s'] == 'f' else '女人', Y - y)))
        if kind == 'born' and who[2] is not p and Y - y <= 2 and (who[0] is p or who[1] is p): c.append((8, '去年刚添了个%s' % ('儿子' if who[2]['s'] == 'm' else '女儿') if Y - y >= 1 else '家里刚添了个孩子'))
        if kind == 'lost' and (who[0] is p or who[1] is p): c.append((6 if Y - y < 8 else 3, '有个孩子没养大'))
        if kind == 'wed' and who[1] is p and Y - y <= 1: c.append((8, '今年才嫁过来'))
        if kind == 'wed' and who[0] is p and Y - y <= 1: c.append((7, '今年刚娶了亲'))
    f = hh['cur']
    if 48 <= f['B'] <= 50: c.append((6, '大火烧了原来的家，一家人才搬到这条街'))
    elif f['origin'] != '本城生' and age > 15: c.append((4, '一家人是从%s来的，%s' % (f['origin'], f['arrive'])))
    for j, t in hh.get('ties', []):
        if t == 'cold': c.append((6, '跟隔壁%s家不来往：一家%s，一家%s' % (HH[j].get('headN', ''), f['faith'], HH[j]['cur']['faith'])))
        if t == 'cred' and age > 20: c.append((7, '家里欠着%s家的钱' % HH[j].get('headN', '')))
        if t == 'boss' and p['s'] == 'm' and age > 15: c.append((5, '在%s家的码头上扛活' % HH[j].get('headN', '')))
    gone = [k for k in f['people'] if k.get('away') and (k.get('fa') is p or k.get('mo') is p) and k['d'] > Y]
    if gone: c.append((6, '%s%s，好几年没回来了' % ('儿子' + gone[0]['n'], gone[0]['away'])))
    if age >= 60: c.append((4, '在这条街上住了%d年' % (Y - max(f['B'], 0))))
    c.append((2, '家里有%s' % hh['obj']))
    rr = random.Random('f%d%s' % (POOL[i]['id'], p['n'])); c.sort(key=lambda x: -x[0] - rr.random() * 2.5)
    return c[0][1]

ROLE = lambda o: (lambda p, pl, age: 'child' if age < 12 else 'old' if age >= 60 else 'woman' if p['s'] == 'f' else
                  {'haul': 'laborer', 'market': 'trader', 'forum': 'rich', 'debt': 'commoner', 'errand': 'commoner'}.get(pl[0], 'commoner'))(o['p'], o['pl'], Y - o['p']['b'])
TIE = {'nb': '邻居', 'cold': '不来往的邻居', 'home': '同乡', 'boss': '东家', 'hand': '伙计', 'cred': '债主', 'debtor': '欠他家钱', 'natal': '娘家人', 'inlaw': '亲家'}
DIR8 = ['东', '东南', '南', '西南', '西', '西北', '北', '东北']
def where(i, j):
    a, b = POOL[i]['_c'], POOL[j]['_c']; d = math.dist(a, b) * MPP
    if d < 18: return '隔壁'
    k = int(((math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) + 360 + 22.5) % 360) // 45)
    return '往%s %d 米' % (DIR8[k], round(d / 10) * 10 or 10)
TYH = {'nb': '邻居', 'cold': '邻居·不来往', 'home': '同乡', 'boss': '东家', 'hand': '伙计家', 'cred': '债主', 'debtor': '欠他家钱', 'natal': '儿媳的娘家', 'inlaw': '女儿嫁过去'}
HOUT = []
for i, hh in enumerate(HH):
    f = hh['cur']; seen = set(); T = []
    for j, t in hh.get('ties', []):
        if (j, t) in seen: continue
        seen.add((j, t)); T.append([j, list(TYH).index(t)])
    HOUT.append([hh.get('headN', ''), f['trade'], f['origin'], f['faith'], f['arrive'], round(POOL[i]['_c'][0]), round(POOL[i]['_c'][1]), T])
LAB = {}
people = []
for k, o in enumerate(OUT):
    p, i, pl = o['p'], o['i'], o['pl']; hh = HH[i]; hd = hh['hd']
    lead = PID.get(id(pl[2])) if pl[0] == 'follow' and pl[2] else None
    ri = OUT[lead]['pl'][1] if lead is not None else pl[1]
    if ri is None: continue
    fam = [(PID[id(x)], rel(p, x)) for x in hh['al'] if x is not p and id(x) in PID]
    kin, soc = [], []
    if p.get('natal'):
        j, me = p['natal']; kin += [(PID[id(x)], '娘家·' + rel(me, x)) for x in HH[j]['al'] if id(x) in PID and x is not me]
    for q in hh['people']:
        if q.get('to') and id(q['to'][1]) in PID and rel(p, q) != '家里人': kin.append((PID[id(q['to'][1])], '嫁出去的' + rel(p, q)))
    adult = Y - p['b'] >= 15
    for j, t in hh.get('ties', []):
        if t in ('natal', 'inlaw'): continue
        if t in ('hand', 'debtor', 'boss', 'cred') and not (adult and (p is hd or pl[0] in ('haul', 'debt') or p.get('sp') is hd)): continue
        xs = [x for x in HH[j]['al'] if id(x) in PID and Y - x['b'] >= 15]
        if t in ('nb', 'cold', 'home'): xs = sorted(xs, key=lambda x: x['s'] != p['s'])[:1]
        soc += [(PID[id(x)], TIE[t]) for x in xs[:2]]
    ties = [t for t in fam[:4] + kin[:3] + soc[:4] if not t[1].endswith('家里人')]
    who = ('%s，%s' % (p['n'], hh['cur']['trade']) if p['s'] == 'm' else '%s，%s家的当家' % (p['n'], hh['cur']['trade'])) if p is hd else '%s，%s家的%s' % (p['n'], hd['n'] if hd else '', rel(hd, p) if hd else '人')
    tgt = HH[pl[2]].get('headN', '') if pl[0] in ('visit', 'haul', 'debt') and pl[2] is not None else ''
    people.append([k, ri, ROLE(o), p['s'], Y - p['b'], who, fact(o), pl[0], tgt, lead if lead is not None else -1, meet.get(k, -1), [[a, LAB.setdefault(b, len(LAB))] for a, b in ties], HID[POOL[i]['id']]])
out = {'q': Q, 'year': Y, 'mpp': MPP, 'routes': RT, 'people': people, 'labels': list(LAB), 'houses': HOUT, 'htie': list(TYH.values()),
       'fields': 'id 路线 身份 性别 年龄 一句谁 一件事 去干什么 去谁家 跟着谁 约了谁 关系[[人,称呼]] 户',
       'note': '户籍 + 社会关系：每个人是一栋真房子里活着的一口人；去哪、跟谁，由他在家里的位置和这户跟别户的关系推出来。——Hark（CS线）'}
dst = os.path.join(ROOT, 'docs/living/nodes', Q, 'crowd.json')
json.dump(out, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
# 给招牌和街名用的户表（signs.py 读）：房号 → 行当、籍贯
json.dump([[POOL[i]['id'], HH[i]['cur']['trade'], HH[i]['cur']['origin'], HH[i].get('headN', ''), HH[i]['cur']['B']] for i in range(len(POOL))], open(os.path.join(ROOT, 'docs/living/nodes', Q, 'folk_h.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
import collections
print('户', len(POOL), '合并的嫁娶', merged, '路线', len(RT), '上街的人', len(people), os.path.getsize(dst), '字节')
print(collections.Counter(x[7] for x in people)); print(collections.Counter(x[2] for x in people))
L2 = list(LAB); print('约伴', len(meet) // 2, '有外人关系的', sum(1 for x in people if any(not L2[t[1]] in ('父亲','母亲','儿子','女儿','丈夫','妻子','哥哥','弟弟','姐姐','妹妹') for t in x[11])))
for x in people[:14]: print(x[5], '|', x[6], '|', x[7], x[8], '|', [L2[t[1]] for t in x[11]])
