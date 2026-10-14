"""CS 线 · 叠层（palimpsest）最小实验：当年的城市里留着过去的痕迹。python3 traces.py → docs/living/tiles/traces.json
每一条痕迹都只从底账推（world.json 只读 + 编年史原文 + 已烘的 vec），没有出处就不画：
  ① ruin   拆掉的结构（destroyed 不为空）：拆毁那年起在原线上留一道浅痕。文案 = 编年史里提到它的句子（优先拆毁那个纪元的）。
  ② spolia 用了旧料的结构（spolia_from）：落成起在它身上标一个点，文案 = 编年史里说它用旧料的那句 + 旧料出处的建成/拆毁年。
  ③ fire   火灾（eras[].events type=fire）：烧掉的房子（vec 里 e==火灾年、脚印中心在火圈内）留焦痕，8 年里淡去；
           火场标记一直在，卡上列出火场上后来建起的结构（底账几何中心在火圈内、建成年晚于火灾）。
每条带 src（底账出处），check_traces.js 逐条核。坐标 = 瓦片页 0 级像素。——Hark（CS线）"""
import json, os, glob, math
import chron_events as CE

W, NZ, ST, px, L = CE.W, CE.NZ, CE.ST, CE.px, CE.L
VD = os.path.join(L, 'tiles', 'vec')

def zh(i): return NZ.get(i) or ST[i]['name']

def chron_sents():
    out = []
    for e in W['eras']:
        f = os.path.join(CE.ROOT, 'chronicle', f"{e['from']}_{e['to']}.md")
        if os.path.exists(f):
            for s in CE.sentences(open(f, encoding='utf-8').read()): out.append((e['from'], e['to'], s))
    return out
SENTS = chron_sents()

def find(id_, prefer_year=None, must=None):
    """编年史里含 {{id}} 的句子；prefer_year 落在哪个纪元就先取那个纪元的；must 是句子还得含的字"""
    key = '{{' + id_ + '}}'; hits = [(a, b, s) for a, b, s in SENTS if key in s and (must is None or must in s)]
    if not hits: return None
    if prefer_year is not None:
        hits.sort(key=lambda h: 0 if h[0] <= prefer_year <= h[1] else 1)
    a, b, s = hits[0]; return dict(text=CE.subst(CE.excerpt(s, key)), era=[a, b])

def next_about(id_, year, words):
    """含 {{id}} 那句之后 3 句内第一句含 words 之一的（编年史常在下一句才说用了旧料）"""
    key = '{{' + id_ + '}}'
    for i, (a, b, t) in enumerate(SENTS):
        if key in t and a <= year <= b:
            for j in range(i + 1, min(i + 4, len(SENTS))):
                if any(w in SENTS[j][2] for w in words): return CE.subst(SENTS[j][2])
    return None

def near(g, x, y, R):
    return any(math.hypot(a - x, b - y) <= R for a, b in pts(g))

def pts(g):
    c = g['coords']; c = [c] if g['type'] == 'point' else c
    return [[round(v, 1) for v in px(x, y)] for x, y in c]

def build():
    T = []
    for s in W['structures']:
        if s.get('destroyed') is not None:
            c = find(s['id'], s['destroyed']); P = pts(s['geom']); cx, cy = CE.place(s['geom'])[:2]
            if not c or not (c['era'][0] <= s['destroyed'] <= c['era'][1]):   # 拆毁那个纪元没点它的名：取同年一起拆的兄弟结构那句（编年史常把墙和门写在一句里）
                sib = [t['id'] for t in W['structures'] if t['id'] != s['id'] and t.get('destroyed') == s['destroyed']]
                c2 = next((find(i, s['destroyed']) for i in sib if find(i, s['destroyed'])), None)
                if c2 and c2['era'][0] <= s['destroyed'] <= c2['era'][1]: c = c2; cx, cy = CE.place(s['geom'])[:2]
            T.append(dict(kind='ruin', id=s['id'], name=zh(s['id']) + '旧址', since=s['destroyed'], built=s['built'], line=P,
                          closed=s['geom']['type'] == 'polygon', x=cx, y=cy, text=c and c['text'], src=f"world.json structures/{s['id']} destroyed={s['destroyed']}"))
        for f in s.get('spolia_from') or []:
            c = find(s['id'], s['built']); cx, cy = CE.place(s['geom'])[:2]; o = ST[f]
            nx = next_about(s['id'], s['built'], ('石', '料', '旧'))
            if c and nx: c['text'] = c['text'] + nx
            T.append(dict(kind='spolia', id=s['id'] + '<' + f, name=zh(s['id']) + '的旧石', since=s['built'], x=cx, y=cy, text=c and c['text'],
                          from_name=zh(f), from_built=o['built'], from_destroyed=o.get('destroyed'), back=o['built'],
                          src=f"world.json structures/{s['id']} spolia_from={f}"))
    # ④ cleared 为建地标拆掉的房子（houses[].cause = 'cleared for <结构英文名>'）：落成起在地标上标一个点，卡上说拆了几栋，可回到落成前一年看原来的街坊
    BYN = {t['name']: t for t in W['structures']}; CL = {}
    for h in W['houses']:
        c = h.get('cause') or ''
        if c.startswith('cleared for ') and c[12:] in BYN: CL.setdefault(c[12:], []).append(h)
    for nm, hs in sorted(CL.items(), key=lambda kv: -len(kv[1])):
        if len(hs) < 10: continue
        t = BYN[nm]; c = find(t['id'], t['built']); cx, cy = CE.place(t['geom'])[:2]
        T.append(dict(kind='cleared', id='cleared<' + t['id'], name=zh(t['id']) + '下的旧街坊', since=t['built'], x=cx, y=cy + 6, n=len(hs), text=c and c['text'],
                      back=t['built'] - 1, src=f"world.json houses cause='cleared for {nm}' ×{len(hs)}"))
    # ⑤ 派生表清场（合流①②）：地标卡（cleared_cs.json，谭线 v31 卡经 landmarks_city.py 放）和史诗脚印（epic_cleared.json）拆掉的房子，
    #    按「为谁拆」归成一处旧街坊；落成起在地标上标一个点，卡上说拆了几栋，可回到落成前一年看原来的街坊。
    KZ = {'macellum': '肉鱼市', 'kiln': '砖窑', 'fountain': '喷泉', 'bread_steps': '面包台阶', 'cemetery': '墓地'}
    G = {}
    for fn, key in (('cleared_cs.json', 'lm'), ('epic_cleared.json', 'epic')):
        fp = os.path.join(L, 'tiles', fn)
        if not os.path.exists(fp): continue
        for r in json.load(open(fp))['cleared']:
            g = G.setdefault((fn, r[key]), dict(fn=fn, who=r[key], kind=r.get('for') or 'epic', rows=[]))
            g['rows'].append(r)
    CEN = {}
    want = {g['who'] for g in G.values() if g['fn'] == 'cleared_cs.json'}
    hid = {int(str(r['id']).lstrip('h')) for g in G.values() for r in g['rows']}
    for fn in glob.glob(os.path.join(VD, '*.json')):
        for h in json.load(open(fn)).get('h', []):
            if len(h) > 5 and len(h[3]) >= 8 and (h[5] in want or str(h[5]).lstrip('h').isdigit() and int(str(h[5]).lstrip('h')) in hid):
                CEN.setdefault(h[5], (sum(h[3][0:8:2]) / 4, sum(h[3][1:8:2]) / 4))
    for (fn, who), g in sorted(G.items(), key=lambda kv: -len(kv[1]['rows'])):
        rows = g['rows']; since = min(r['year'] for r in rows); n = len({r['id'] for r in rows})
        if fn == 'epic_cleared.json':
            nm = zh(who); src = f"epic_cleared.json epic={who} ×{n}（world.json 史诗脚印）"
            pts_ = [CEN[r['id']] for r in rows if r['id'] in CEN]
            if not pts_: continue
            cx = sum(p[0] for p in pts_) / len(pts_); cy = sum(p[1] for p in pts_) / len(pts_)
            line = f"{since} 年起{nm}的脚印压到这里。"
        else:
            if who not in CEN: continue
            nm = KZ.get(g['kind'], g['kind']); cx, cy = CEN[who]
            src = f"cleared_cs.json lm={who} for={g['kind']} ×{n}（谭线 v31 地标卡，landmarks_city.py）"
            line = f"{since} 年起这里改成{nm}。"
        T.append(dict(kind='cleared', id='clearedcs<' + str(who), name=nm + '下的旧街坊', since=since, x=round(cx), y=round(cy) + 6, n=n,
                      text=line, back=since - 1, src=src))
    V = []
    for fn in glob.glob(os.path.join(VD, '*.json')):
        for h in json.load(open(fn)).get('h', []):
            if len(h[3]) >= 8: V.append(h)
    EV = {v['id']: v for v in json.load(open(os.path.join(L, 'tiles', 'events.json')))['events']}
    for e in W['eras']:
        for v in e.get('events') or []:
            if v['type'] != 'fire': continue
            fx, fy = px(v['x'], v['y']); R = v['r'] * CE.S; polys = []
            for h in V:
                if h[1] != v['year']: continue
                sh = h[3]; cx = sum(sh[0:8:2]) / 4; cy = sum(sh[1:8:2]) / 4
                if math.hypot(cx - fx, cy - fy) <= R * 1.05: polys.append([round(c, 1) for c in sh[:8]])
            later = sorted(((t['built'], zh(t['id'])) for t in W['structures'] if t['built'] > v['year'] and near(t['geom'], fx, fy, R)), key=lambda x: x[0])
            ev = EV.get(f"fire{v['year']}")
            T.append(dict(kind='fire', id=f"fire{v['year']}", name=f"{v['year']} 年火场", since=v['year'], x=round(fx), y=round(fy), r=round(R),
                          polys=polys, later=[dict(year=y, name=n) for y, n in later], text=ev and ev['text'], back=v['year'] - 1,
                          src=f"world.json eras/{e['from']}_{e['to']} events fire year={v['year']} houses={v['houses']}"))
    return T

if __name__ == '__main__':
    T = build()
    json.dump(dict(traces=T), open(os.path.join(L, 'tiles', 'traces.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    for t in T: print(t['kind'], t['name'], t['since'], len(t.get('polys', [])), [l['name'] + str(l['year']) for l in t.get('later', [])], (t['text'] or '无文案')[:50])
