"""狄奥多西广场一景（第 65 年，一个下午）的「演员表」（2026-11-05，CS 线）。
人一个都不新写：先用 folk.py 按第 65 年重跑一遍户籍（FOLK_OUT 写到临时目录，不碰节点的 crowd.json），
再从住在广场周围的人家里挑人，按他家的行当和他在家里的位置派一个下午的去处：
  柱廊里摆摊（广场边的银钱商 / 丝绸商 / 香料商 / 金匠……家的人，钱商街在南、香料街在西，所以钱商摆南廊、香料摆西廊）、
  凯旋门里侧代写状子的抄写员和排队的人、凯旋门下说事的富户、纪功柱下闲坐的老人和街坊、
  梅塞大道上穿过广场的脚夫和运水人、去大宁芙殿打水的妇人、逛摊子的人、穿过广场办事的人、跟着大人的孩子。
名字、户主、行当、籍贯、信仰、哪年来的、家里的一件事，全是 folk.py 的原文；「此刻」那半句是按派的去处拼的（notes.md 写明）。
写 docs/living/nodes/nangang/forum/cast.json（页面 3d/scene_forum.js 读）。
  python3 tools/cs/scene/forum_cast.py            # 会先跑 folk.py nangang 65（约 20 秒）
——Hark（CS线）"""
import json, math, os, random, subprocess, sys, tempfile, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
Y = 65
TMP = os.environ.get('FOLK65') or tempfile.mkdtemp(prefix='folk65_')
if not os.path.exists(os.path.join(TMP, 'crowd.json')):
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/cs/people/folk.py'), 'nangang', str(Y)], check=True,
                   env={**os.environ, 'NH': '2800', 'FOLK_OUT': TMP}, stdout=subprocess.DEVNULL)
C = json.load(open(os.path.join(TMP, 'crowd.json'), encoding='utf-8'))
FH = json.load(open(os.path.join(TMP, 'folk_h.json'), encoding='utf-8'))
ND = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/nodes.json'), encoding='utf-8'))
assert C['year'] == Y
LAB = C['labels']; HS = C['houses']
HOUSE = {f['id']: f for f in ND['features'] if f['t'] == 'house'}
live = lambda f: f['y0'] <= Y and (f.get('y1') is None or f['y1'] > Y)
FORUM = next(f for f in ND['features'] if f['t'] == 'landmark' and f['id'] == 'forum_theodosius')
CX, CZ = 1436.0, 313.0
X0, Z0, X1, Z1 = 1365, 256, 1507, 370
D, DC = 11, 1.25                     # 柱廊进深、柱心离院边（forum.js）
K = 1 / .84
R = random.Random('forum-65-afternoon')
dist = lambda p: math.hypot(p[0] - CX, p[1] - CZ)

PEOPLE = C['people']; BY = {p[0]: p for p in PEOPLE}
hpos = lambda p: (HS[p[12]][5], HS[p[12]][6])
near = sorted([p for p in PEOPLE if dist(hpos(p)) < 380], key=lambda p: (dist(hpos(p)), p[0]))
used = set(); cast = []
def adult(p): return p[4] >= 15
def take(p, kind, spot, face=None, path=None, pose='stand', load=None, now='', extra=None):
    used.add(p[0]); cast.append(dict(id=p[0], kind=kind, spot=spot, face=face, path=path, pose=pose, load=load, now=now, **(extra or {})))

# ---------- 柱廊里的摊位：沿内墙（d = 8.6）每 5 px 一个，人面朝院子 ----------
def wing_spots(k):
    if k == 'N': return [((x, Z0 + D - 8.4), (0, 1)) for x in range(1381, 1493, 6)]
    if k == 'S': return [((x, Z1 - D + 8.4), (0, -1)) for x in range(1381, 1493, 6)]
    if k == 'W': return [((X0 + D - 8.4, z), (1, 0)) for z in list(range(270, 286, 6)) + list(range(338, 357, 6))]
    if k == 'E': return [((X1 - D + 8.4, z), (-1, 0)) for z in list(range(270, 289, 6)) + list(range(306, 357, 6))]
WING_OF = {'银钱商': 'S', '香料商': 'W', '丝绸商': 'N', '金匠': 'E'}
FILL = ['卖油的', '卖果子的', '小贩', '卖鱼的', '裁缝', '鞋匠', '织工', '面包师']
WNAME = {'N': '北柱廊', 'S': '南柱廊', 'W': '西柱廊', 'E': '东柱廊'}
GOODS = {'银钱商': '一张钱桌，上面摞着铜币和一杆小秤', '丝绸商': '几匹染过的丝', '香料商': '一排香料罐', '金匠': '一只小匣子，里面是戒指和搭扣',
         '卖油的': '几只油罐', '卖果子的': '一筐无花果', '小贩': '一筐零碎', '卖鱼的': '一篮咸鱼', '裁缝': '几件缝好的短袍', '鞋匠': '一排鞋', '织工': '几卷布', '面包师': '一筐饼'}
free = {k: wing_spots(k) for k in 'NSWE'}
stalls = []
def seller_of(hidx):
    cand = [p for p in near if p[12] == hidx and adult(p) and p[0] not in used]
    head = HS[hidx][0]
    cand.sort(key=lambda p: (not p[5].startswith(head + '，') if head else 1, -p[4]))
    return cand[0] if cand else None
houses_by_trade = collections.defaultdict(list)
for hidx in sorted({p[12] for p in near}, key=lambda i: dist((HS[i][5], HS[i][6]))):
    houses_by_trade[HS[hidx][1]].append(hidx)
order = []
for t in ['银钱商', '丝绸商', '香料商', '金匠']: order += [(t, h) for h in houses_by_trade[t]]
for t in FILL: order += [(t, h) for h in houses_by_trade[t][:3]]
for t, hidx in order:
    w = WING_OF.get(t)
    wings = [w] if w and free[w] else [k for k in 'NSEW' if free[k]]
    if not wings: break
    k = wings[0]; spot, face = free[k].pop(0) if t in WING_OF else free[k].pop()
    p = seller_of(hidx)
    if not p: free[k].insert(0, (spot, face)); continue
    take(p, 'stall', [round(spot[0], 2), round(spot[1], 2)], face, pose='sell', now=f'在{WNAME[k]}摆着自家的摊子：{GOODS.get(t, "一点货")}。', extra={'wing': k, 'trade': t})
    stalls.append({'id': p[0], 'x': spot[0], 'z': spot[1], 'fx': face[0], 'fz': face[1], 'trade': t, 'wing': k, 'h': p[12]})
    # 同户的第二个大人在摊子旁边搭手（有就加，没有不硬凑）
    q = next((x for x in near if x[12] == hidx and adult(x) and x[0] not in used), None)
    if q and R.random() < .5:
        sx, sz = spot[0] - face[1] * 1.6, spot[1] + face[0] * 1.6
        take(q, 'stall', [round(sx, 2), round(sz, 2)], face, pose='stand', now=f'在{WNAME[k]}自家摊子边上搭手。', extra={'wing': k, 'trade': t, 'helper': p[0]})

# ---------- 凯旋门里侧：抄写员摆桌代写状子，前面排着找人说理的 ----------
scribes = [h for h in houses_by_trade['抄写员']]
desks = []
for i, hidx in enumerate(scribes[:6]):
    p = seller_of(hidx)
    if not p: continue
    z = 290 + i * 6 if i < 3 else 320 + (i - 3) * 6
    x = 1384.5
    take(p, 'scribe', [x, z], (1, 0), pose='sit', now='在凯旋门里侧摆了张小桌，替不识字的人写状子、写信。', extra={'trade': '抄写员'})
    desks.append({'id': p[0], 'x': x + 1.0, 'z': z})
peti = [p for p in near if p[0] not in used and adult(p) and p[7] in ('debt', 'visit') and p[9] == -1]
for i, d in enumerate(desks):
    for j in range(2):
        if not peti: break
        p = peti.pop(0)
        why = '欠着人家的钱，' if p[7] == 'debt' else ''
        take(p, 'petition', [d['x'] + 2.2 + j * 1.5, d['z'] + (j - .5) * .6], (-1, 0), pose='queue' if j else 'talk',
             now=f'{why}排在抄写员{BY[d["id"]][5].split("，")[0]}的桌前，等着请他写一纸状子。')

# ---------- 凯旋门下：有身份的人说事 ----------
rich = [p for p in near if p[0] not in used and adult(p) and p[2] == 'rich']
for i, p in enumerate(rich[:10]):
    x = 1374.5 + (i % 2) * 3.2; z = [292, 297.5, 302, 320, 325.5][i // 2]; f = (-1, 0) if i % 2 else (1, 0)
    take(p, 'notable', [x, z], f, pose='talk', now='站在凯旋门的门洞下，跟人说事。')

# ---------- 纪功柱下：闲坐的、说话的 ----------
idle = [p for p in near if p[0] not in used and adult(p) and p[9] == -1 and (p[2] in ('old', 'commoner')) and p[7] in ('forum', 'errand', 'visit', 'market')]
n_idle = min(36, len(idle))
for i, p in enumerate(idle[:n_idle]):
    a = i / n_idle * 2 * math.pi + R.random() * .1
    sit = p[2] == 'old' or i % 3 == 0
    r = (6.7 if sit else 8.6 + (i % 4) * 1.3) / max(abs(math.cos(a)), abs(math.sin(a)))   # 柱基台阶是方的（半边 5.9 px）：沿方框排
    x, z = CX + math.cos(a) * r, CZ + math.sin(a) * r
    f = (math.cos(a), math.sin(a)) if sit else (-math.sin(a) * (1 if i % 2 else -1), math.cos(a) * (1 if i % 2 else -1))
    take(p, 'idler', [round(x, 2), round(z, 2)], [round(f[0], 3), round(f[1], 3)], pose='sit' if sit else 'talk',
         now='坐在纪功柱的台阶下歇脚，看人来人往。' if sit else '在纪功柱下跟街坊闲聊。')

# ---------- 梅塞大道：脚夫（全南港的扛活人里离广场最近的）和运水人家，从凯旋门进、东门出（一半反着走） ----------
MESE = [(1300, 315.5), (1340, 313), (1366, 311), (1380, 309.5), (1410, 302), (1436, 298), (1462, 297), (1496, 298.5), (1508, 297), (1545, 293.5), (1585, 289.5)]
def mese(rev, side):
    P = [(x, z + side) for x, z in MESE]; return [list(map(lambda v: round(v, 2), q)) for q in (P[::-1] if rev else P)]
laborers = sorted([p for p in PEOPLE if p[0] not in used and p[2] == 'laborer' and adult(p)], key=lambda p: (dist(hpos(p)), p[0]))[:20]
for i, p in enumerate(laborers):
    rev = i % 2 == 1
    take(p, 'porter', None, path=mese(rev, (-2.2 if rev else 2.2) + (i % 3) * .6), load='sack',
         now=f'扛着麻袋走梅塞大道，从{"东门进、凯旋门出" if rev else "凯旋门进、东门出"}，穿过广场。')
carriers = [p for p in near if p[0] not in used and adult(p) and HS[p[12]][1] == '运水人' and p[9] == -1][:12]
for i, p in enumerate(carriers):
    rev = i % 2 == 0
    take(p, 'carrier', None, path=mese(rev, (-3.4 if rev else 3.4)), load='jar_full', now='顶着水罐走梅塞大道，给东边的人家送水。')

# ---------- 去大宁芙殿打水：从南拱门进、北拱门出，往东北去泉宫（chronicle：广场划在瓦伦斯大喷泉旁边） ----------
LANE = [(1446, 392), (1444, 371), (1452, 345), (1453, 290), (1444, 256), (1452, 238), (1470, 226), (1530, 210)]
water = [p for p in near if p[0] not in used and adult(p) and p[7] == 'water' and p[3] == 'f' and p[9] == -1][:26]
for i, p in enumerate(water):
    side = ((i % 5) - 2) * 1.1
    take(p, 'water', None, path=[[round(x + side, 2), z] for x, z in LANE], load='jar_empty', now='拿着空罐穿过广场，去大宁芙殿打水。')

# ---------- 逛摊子：柱廊走道上，从一个摊子走到另一个摊子 ----------
shop = [p for p in near if p[0] not in used and adult(p) and p[7] in ('market', 'errand', 'water', 'visit') and p[9] == -1 and p[2] in ('woman', 'commoner')][:40]
for i, p in enumerate(shop):
    a, b = R.sample(stalls, 2) if len(stalls) > 2 else (stalls[0], stalls[-1])
    if a['wing'] != b['wing']:
        b = R.choice([s for s in stalls if s['wing'] == a['wing'] and s is not a] or [a])
    aw = (a['x'] + a['fx'] * 2.4, a['z'] + a['fz'] * 2.4); bw = (b['x'] + b['fx'] * 2.4, b['z'] + b['fz'] * 2.4)
    take(p, 'shopper', None, path=[[round(aw[0], 2), round(aw[1], 2)], [round(bw[0], 2), round(bw[1], 2)]],
         now=f'在{WNAME[a["wing"]]}一个摊子一个摊子地看，问{BY[b["id"]][5].split("，")[0]}家的价。', extra={'stall': b['id']})

# ---------- 穿过广场办事：在四个口之间走 ----------
GATES = {'W': (1352, 312.5), 'E': (1520, 296), 'N': (1444, 245), 'S': (1445, 383)}
pairs = [('W', 'N'), ('S', 'E'), ('N', 'S'), ('W', 'S'), ('E', 'N'), ('S', 'W')]
cross = [p for p in near if p[0] not in used and adult(p) and p[9] == -1][:30]
for i, p in enumerate(cross):
    a, b = pairs[i % len(pairs)]
    A, B = GATES[a], GATES[b]
    mid = (CX + (R.random() - .5) * 60, CZ + (R.random() - .5) * 50)
    def segd(a, b):
        ax, az, bx, bz = a[0], a[1], b[0], b[1]; L = (bx - ax) ** 2 + (bz - az) ** 2 or 1
        u = max(0, min(1, ((CX - ax) * (bx - ax) + (CZ - az) * (bz - az)) / L)); return math.hypot(ax + u * (bx - ax) - CX, az + u * (bz - az) - CZ)
    for _ in range(40):
        if min(segd(A, mid), segd(mid, B)) > 10: break
        mid = (CX + (R.random() - .5) * 90, CZ + (R.random() - .5) * 80)
    take(p, 'crosser', None, path=[list(A), [round(mid[0], 2), round(mid[1], 2)], list(B)],
         now=f'穿过广场去办事，从{ {"W": "凯旋门", "E": "东门", "N": "北拱门", "S": "南拱门"}[a]}进来。')

# ---------- 跟着大人的人（孩子、没出嫁的女儿……）：领头的人在场就跟着 ----------
NF = 0
for p in PEOPLE:
    if NF >= 30: break
    if p[0] in used or p[9] == -1 or p[9] not in used: continue
    L = next(c for c in cast if c['id'] == p[9])
    if L['kind'] not in ('shopper', 'water', 'crosser', 'stall') or sum(1 for c in cast if c.get('lead') == L['id']) >= 1: continue
    NF += 1
    take(p, 'follow', None, now='跟着' + next((LAB[t[1]] for t in p[11] if t[0] == L['id']), '家里人') + '。', extra={'lead': L['id']})

# ---------- 纪功柱北边空地上玩的孩子（大人不在广场上的） ----------
kids = [p for p in near if p[0] not in used and p[2] == 'child' and 6 <= p[4] <= 12][:12]
for i, p in enumerate(kids):
    x = 1418 + (i % 7) * 4.4; z = 286 + (i // 7) * 4.5
    take(p, 'kid', [x, z], (1 if i % 2 else -1, 0), pose='play', now='跟别家的孩子在广场北边的石板地上追着玩。')

# ---------- 打包 ----------
H2 = {}; rows = []
for c in cast:
    p = BY[c['id']]; h = p[12]
    if h not in H2: H2[h] = len(H2)
    ties = [[a, l] for a, l in p[11] if a in used]
    rows.append([p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], c.get('lead', -1) if c['kind'] == 'follow' else -1, -1, ties, H2[h]])
houses = [None] * len(H2)
for h, j in H2.items():
    hid = FH[h][0]; assert live(HOUSE[hid]), hid
    houses[j] = HS[h][:7] + [hid]
out = {'q': 'nangang', 'year': Y, 'mpp': C['mpp'], 'labels': LAB, 'htie': C['htie'],
       'houses_fields': '户主 行当 籍贯 信仰 哪年来的 x z 房号', 'houses': houses,
       'fields': C['fields'], 'people': rows, 'cast': cast, 'stalls': stalls, 'desks': desks,
       'src': 'tools/cs/people/folk.py nangang 65（NH=2800，FOLK_OUT 临时目录）→ tools/cs/scene/forum_cast.py',
       'note': '狄奥多西广场，第 65 年的一个下午。每个人都是 folk.py 第 65 年户籍里的一口人；「此刻」是按派的去处拼的。——Hark（CS线）'}
dst = os.path.join(ROOT, 'docs/living/nodes/nangang/forum/cast.json'); os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('人', len(cast), collections.Counter(c['kind'] for c in cast), '摊', len(stalls), '户', len(houses), os.path.getsize(dst), '字节')
