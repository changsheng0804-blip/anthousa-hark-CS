"""检查狄奥多西广场一景的演员表没有和数据打架（2026-11-05，CS 线）。失败返回 1。
  对 folk.py 第 65 年户籍逐人比：名字/一句谁、性别、年龄、身份、家里的事、户主、行当、籍贯、信仰、来历、房号一字不差；
  房子第 65 年还在（nodes.json）、不在广场框里；跟着谁 = 户籍里的「跟着谁」；关系是户籍关系的子集；没有一个人出场两次；
  摆摊的行当 = 他家行当；抄写员、运水人、脚夫的身份对得上；「此刻」里点到的别人的名字对得上；
  再和第 60 年的 crowd.json 比：同一栋房子里同名同性别的人，年龄刚好差 5 岁（只报告，不算失败——五年里有生有死有改嫁）。
  python3 tools/cs/scene/check_forum_cast.py        # 会先跑 folk.py nangang 65（FOLK65=目录 可复用）
——Hark（CS线）"""
import json, os, subprocess, sys, tempfile, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
TMP = os.environ.get('FOLK65') or tempfile.mkdtemp(prefix='folk65_')
if not os.path.exists(os.path.join(TMP, 'crowd.json')):
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/cs/people/folk.py'), 'nangang', '65'], check=True, env={**os.environ, 'NH': '2800', 'FOLK_OUT': TMP}, stdout=subprocess.DEVNULL)
S = json.load(open(os.path.join(TMP, 'crowd.json'), encoding='utf-8')); SFH = json.load(open(os.path.join(TMP, 'folk_h.json'), encoding='utf-8'))
K = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/forum/cast.json'), encoding='utf-8'))
ND = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/nodes.json'), encoding='utf-8'))
C60 = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/crowd.json'), encoding='utf-8')); F60 = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/folk_h.json'), encoding='utf-8'))
HOUSE = {f['id']: f for f in ND['features'] if f['t'] == 'house'}
SP = {p[0]: p for p in S['people']}; bad = []; info = collections.Counter()
def err(m):
    bad.append(m)
ids = [p[0] for p in K['people']]
if len(ids) != len(set(ids)): err('有人出场两次')
if len(K['people']) != len(K['cast']): err('people 和 cast 条数不一样')
names = {p[0]: p[5].split('，')[0] for p in K['people']}
for p, c in zip(K['people'], K['cast']):
    pid = p[0]; s = SP.get(pid)
    if not s: err(f'{pid} 不在第 65 年户籍里'); continue
    if c['id'] != pid: err(f'{pid} cast 顺序错了')
    for k, nm in [(2, '身份'), (3, '性别'), (4, '年龄'), (5, '一句谁'), (6, '家里的事'), (7, '去干什么'), (8, '去谁家')]:
        if p[k] != s[k]: err(f'{pid} {nm}：{p[k]} ≠ 户籍 {s[k]}')
    h = K['houses'][p[12]]; sh = S['houses'][s[12]]; hid = SFH[s[12]][0]
    if h[:7] != sh[:7] or h[7] != hid: err(f'{pid} 户：{h} ≠ 户籍 {sh[:7]} 房 {hid}')
    f = HOUSE.get(hid)
    if not f or not (f['y0'] <= 65 and (f.get('y1') is None or f['y1'] > 65)): err(f'{pid} 的房子 {hid} 第 65 年不在')
    elif 1365 <= h[5] <= 1507 and 256 <= h[6] <= 370: err(f'{pid} 的房子在广场框里')
    if c['kind'] == 'follow':
        if s[9] != c['lead'] or p[9] != c['lead']: err(f'{pid} 跟着 {c["lead"]}，户籍里跟着 {s[9]}')
    elif p[9] != -1: err(f'{pid} 不该跟着人')
    src_t = {(a, l) for a, l in s[11]}
    for a, l in p[11]:
        if (a, l) not in src_t: err(f'{pid} 关系 {a},{l} 户籍里没有')
        if a not in names: err(f'{pid} 关系指向不在场的人 {a}')
    trade = h[1]
    if c['kind'] == 'stall' and c['trade'] != trade: err(f'{pid} 摆{c["trade"]}的摊，家里是{trade}')
    if c['kind'] == 'scribe' and trade != '抄写员': err(f'{pid} 抄写员？家里是{trade}')
    if c['kind'] == 'carrier' and trade != '运水人': err(f'{pid} 运水？家里是{trade}')
    if c['kind'] == 'porter' and p[2] != 'laborer': err(f'{pid} 脚夫？身份 {p[2]}')
    if c['kind'] in ('stall', 'scribe', 'petition', 'notable', 'idler', 'porter', 'carrier', 'water', 'shopper', 'crosser') and p[4] < 15: err(f'{pid} {p[4]} 岁去{c["kind"]}')
    if c['kind'] == 'shopper' and names.get(c['stall']) not in c['now']: err(f'{pid} 「此刻」里的摊主名字对不上')
    if c['kind'] == 'petition' and not any(names[d['id']] in c['now'] for d in K['desks']): err(f'{pid} 「此刻」里的抄写员名字对不上')
    if c['kind'] == 'follow':
        lab = next((K['labels'][l] for a, l in p[11] if a == c['lead']), '家里人')
        if lab not in c['now']: err(f'{pid} 跟着的称呼不对')
    info[c['kind']] += 1
# 第 65 年和第 60 年：同房同名同性别的人，年龄差 5
H60 = {F60[i][0]: i for i in range(len(F60))}; P60 = collections.defaultdict(list)
for q in C60['people']: P60[q[12]].append(q)
both = ok = 0; diff = []
for p in K['people']:
    hid = K['houses'][p[12]][7]
    if hid not in H60: continue
    m = [q for q in P60[H60[hid]] if q[5].split('，')[0] == p[5].split('，')[0] and q[3] == p[3]]
    if not m: continue
    both += 1
    if any(p[4] - q[4] == 5 for q in m): ok += 1
    else: diff.append((p[5], p[4], [q[4] for q in m]))
for b in bad[:40]: print('✗', b)
print('人', len(K['people']), dict(info))
print(f'和第 60 年比：同房同名同性别 {both} 人，年龄差 5 岁的 {ok} 人' + (f'；不差 5 的：{diff[:5]}' if diff else ''))
print('✓ 演员表和户籍对得上' if not bad else f'✗ {len(bad)} 处对不上')
sys.exit(1 if bad else 0)
