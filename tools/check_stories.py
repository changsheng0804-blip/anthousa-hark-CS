"""刘线 · 故事核对脚本：生成的人家故事不许和底账打架。
Checks every generated household story (docs/living/xerolophos/voices.json, or batch files given on the command line)
against the engine ledger and the page's own household derivation:
  - the house exists, is standing in every year a story line is dated, and the family named is the family living there;
  - every person named is in that family (or is the narrator / a tied neighbour / a named character) and is alive and at home that year
    (a person may be mentioned after death only with a death word in the same line);
  - every age 'N 岁' matches someone named in the line;
  - every building named is already built that year (or under construction, with a construction word, at most 3 years early);
  - fires, the Arian expulsion, Adrianople only after they happened; no disaster the ledger does not have;
  - faith, origin and trade words agree with the family (or the narrator's family / a tied neighbour);
  - the narrator lives in the house they speak from, in every year they speak about;
  - (liu2) the 'now' line has a version for each time of day (morning/day/evening/night) with no words from the wrong hour,
    and nothing that puts a hill family at the quay or at sea unless their trade takes them there;
  - (liu4) every street named is in the upstream ledger (facts_upstream/addr.json) and already carries that name that year;
    a '…巷/…街/…大道' that is no known street is flagged;
  - (liu2) repetition across the whole street: tools/dedup.py — one image in at most 3 households, one 6-character stock phrase in at most 3.
usage:
  python3 tools/check_stories.py                      # check voices.json (exit 1 on any failure)
  python3 tools/check_stories.py batch1.json ...      # check raw batches; prints failures per house
  python3 tools/check_stories.py --merge OUT.json batch*.json   # merge passing entries (adds fam/nar/nowY), report dropped
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedup import repetition, MOTIF_MAX, PHRASE_N, PHRASE_MAX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'docs', 'living', 'xerolophos')

def load_households():
    out = subprocess.run(['node', os.path.join(ROOT, 'tools', 'export_households.js'), XD], capture_output=True, text=True, check=True).stdout
    return {h['id']: h for h in json.loads(out)}

HH = load_households()
DEEP = json.load(open(os.path.join(XD, 'stories.json'), encoding='utf-8'))
CITY = json.load(open(os.path.join(XD, 'city.json'), encoding='utf-8'))
SEL_PATH = os.path.join(ROOT, 'tools', 'voices_selected.json')
SEL = {s['id']: s for s in json.load(open(SEL_PATH, encoding='utf-8'))} if os.path.exists(SEL_PATH) else {}

# ---- ledger: structures and their build year ----
BUILT = {}
wpath = os.path.join(ROOT, 'world.json')
NAMES_ZH = json.load(open(os.path.join(ROOT, 'i18n', 'i18n.json'), encoding='utf-8'))['names_zh']
if os.path.exists(wpath):
    W = json.load(open(wpath, encoding='utf-8'))
    for s in W['structures']: BUILT[s['id']] = s['built']
    FIRES = sorted(ev['year'] for e in W['eras'] for ev in e.get('events', []) if ev['type'] == 'fire')
    QUAKES = [ev['year'] for e in W['eras'] for ev in e.get('events', []) if ev['type'] != 'fire']
else:  # fallback: same facts as world.json at year 60 (engine/build_all.py)
    for l in CITY['landmarks']: BUILT[l['id']] = 1
    FIRES, QUAKES = [19, 38, 48], []
for k, v in json.load(open(os.path.join(XD, 'houses.json')))['late'].items(): BUILT[k] = v['built']
STRUCT_WORDS = {}  # chinese word -> built year
for sid, zh in NAMES_ZH.items():
    if sid in BUILT and len(zh) >= 3: STRUCT_WORDS[zh] = BUILT[sid]
for l in CITY['landmarks']:
    if l['id'] in BUILT: STRUCT_WORDS[l['name'].split(' · ')[0]] = BUILT[l['id']]
STRUCT_WORDS.update({  # aliases used in prose
    '运水人的蓄水池': 54, '新蓄水池': 54, '新池子': 54, '半山腰的池子': 54, '坡下的池子': 54,
    '莫德斯图斯': 41, '蓄水池': 41, '城外的院子': 52, '城墙外的院子': 52, '聚会所': 52,
    '特罗阿德粮仓': 46, '亚历山大粮仓': 55, '大教堂': 30, '浴场': 25, '水渠桥': 11, '阿纳斯塔西娅': 49,
    '狄奥多西广场': 57, '大喷泉': 44, '宁芙': 44, '圣使徒': 11, '兵营': 11,
})
STRUCT_RE = sorted(STRUCT_WORDS, key=len, reverse=True)
BUILDING_WORDS = re.compile('开工|在修|在盖|动工|工地|打地基|奠基')
EVENTS = [  # (pattern, earliest year)
    (re.compile('南港大火|南港那场火|南港的火'), 48),
    (re.compile('阿里乌派.{0,8}(请出|赶出|不许进)|(请出|赶出).{0,6}教堂'), 51),
    (re.compile('阿德里安堡'), 49),
]
BANNED = re.compile('地震|瘟疫|鼠疫|饥荒|洪水|海啸') if not QUAKES else re.compile('海啸')
# ---- (liu4) street names: upstream spatial facts, read-only (docs/living/xerolophos/facts_upstream/addr.json) ----
ADDR_PATH = os.path.join(XD, 'facts_upstream', 'addr.json')
STREET_YEARS = {}  # name -> list of (from, to) the street carried that name
if os.path.exists(ADDR_PATH):
    for nm0, y0, R in json.load(open(ADDR_PATH, encoding='utf-8'))['streets']:
        for nm, a, b in R: STREET_YEARS.setdefault(nm, []).append((max(a, y0), b))
STREET_RE = sorted(STREET_YEARS, key=len, reverse=True)
STREET_SUFFIX = re.compile('巷|街|大道')
STREET_GENERIC = set('条全满上在着隔沿过回出一两半这那整后前对大小穿临当看的下里到逛进去跨')

def check_streets(t, y, errs, where):
    """every street named must exist in the upstream ledger and already carry that name in year y;
    a '…巷/…街/…大道' that is not a known street name is flagged (generic 整条街/满街/上街 are fine)."""
    covered = [False] * len(t)
    for nm in STREET_RE:
        i = t.find(nm)
        while i >= 0:
            if not any(covered[i:i + len(nm)]):
                for k in range(i, i + len(nm)): covered[k] = True
                if not any(a <= y < b for a, b in STREET_YEARS[nm]):
                    yrs = '、'.join(f'{a}–{b - 1 if b < 999 else "今"}' for a, b in STREET_YEARS[nm])
                    errs.append(f'{where}: 街名 {nm} 在建城 {y} 年还没有（这个名字用于 {yrs} 年）')
            i = t.find(nm, i + 1)
    if not STREET_YEARS: return
    for m in STREET_SUFFIX.finditer(t):
        if covered[m.start()]: continue
        prev = t[m.start() - 1] if m.start() else ''
        if not prev or prev in STREET_GENERIC or not ('\u4e00' <= prev <= '\u9fff'): continue
        errs.append(f'{where}: “{t[max(0, m.start() - 3):m.end()]}”像街名，但底账里没有这条街')

DEATH = re.compile('死|去世|走了|没了|埋|坟|夭折|没留住|下葬|忌日|过世|不在了|没能')

# ---- time of day (liu2) ----
PERIODS = ('morning', 'day', 'evening', 'night')
PERIOD_BAD = {  # words that contradict the hour
    'morning': [('黄昏|傍晚|半夜|深夜|夜里|月亮|星星|掌灯|点灯|天黑|收摊|打烊|关门', '清晨版本里出现了夜晚/黄昏的词')],
    'day': [('天不亮|天没亮|黄昏|傍晚|半夜|深夜|月亮|星星|掌灯|天黑|鸡叫|睡着了', '白天版本里出现了清晨/夜里的词')],
    'evening': [('天不亮|天没亮|清早|一早|晌午|正午|鸡叫|半夜|深夜', '黄昏版本里出现了清晨/深夜的词')],
    'night': [('天不亮就|清早|一早|晌午|正午|太阳(底下|正)|大中午', '夜里版本里出现了白天的词')],
}
# things that do not belong on the dry hill unless the family's trade takes them there (a water-carrier may sell water at the quay)
HILL_BAD = [
    ('码头|粮船|渔网|补网|出海|港口|船上', '山上的人家此刻不在码头/海上', {'运水人'}),
]

# ---- lexicons ----
NAMES = set()
for f in (os.path.join(XD, 'index.html'),):
    src = open(f, encoding='utf-8').read()
    for m in re.finditer(r"const N[MF]=city\.names_[mf]\.filter\([^)]*\)\.concat\(\[([^\]]*)\]\)", src):
        NAMES |= set(re.findall(r"'([^']+)'", m.group(1)))
NAMES |= set(CITY['names_m']) | set(CITY['names_f'])
CHARS = {'达芙涅': (29, 999), '狄奥多罗斯': (-5, 999), '尼刻塔斯': (-3, 999), '米隆': (37, 999)}
for sid, S in DEEP.items():
    for m in S['members']:
        if not m['n'].startswith('小猫'): CHARS.setdefault(m['n'][1:] if m['n'].startswith('小') else m['n'], (m['b'], m['d']))
NAMES |= set(CHARS)
NAME_RE = sorted(NAMES, key=len, reverse=True)
FAITHS = {'阿里乌派': '阿里乌派', '尼西亚派': '尼西亚派', '旧神': '还拜旧神'}
ORIGINS = [o for o in CITY['origins'] if o != '本城生']
TRADE_WORDS = {'陶匠': '陶匠', '窑': '陶匠', '面包师': '面包师', '面包铺': '面包师', '织工': '织工', '织机': '织工',
               '鞋匠': '鞋匠', '鞋铺': '鞋匠', '酒馆': '酒馆老板', '运水人': '运水人', '扁担': '运水人'}
CN = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
def cn2int(s):
    if s.isdigit(): return int(s)
    if s.startswith('十'): s = '一' + s
    n = 0
    if '十' in s:
        a, b = s.split('十', 1); n = CN.get(a, 1) * 10 + (CN.get(b, 0) if b else 0)
    else:
        n = CN.get(s, -1)
    return n

def fam_at(h, Y):
    f = h['fams'][0]
    for x in h['fams']:
        if x['B'] <= Y: f = x
    return f
def home(p, Y):
    return p['b'] <= Y < p['d'] and (not p['married'] or p['married'] <= Y) and not (p['left'] and p['left'] <= Y)

def strip_structs(t):
    found = []
    for w in STRUCT_RE:
        if w in t:
            found.append(w); t = t.replace(w, '□')
    return t, found

def names_in(t):
    t, _ = strip_structs(t)
    out = []; i = 0
    while i < len(t):
        for n in NAME_RE:
            if t.startswith(n, i):
                # '小X' is fine; skip names glued inside a longer unknown word? keep simple
                out.append(n); i += len(n); break
        else:
            i += 1
    return out

def person(fam, n):
    return [p for p in fam['people'] if p['n'] == n]

def check_line(t, y, ctx, errs, where, memory=False):
    """ctx: dict fam, house, nar_people(list), tie_fams(list of (fam)), allow_names"""
    if BANNED.search(t): errs.append(f'{where}: 提到底账里没有的灾害')
    check_streets(t, y, errs, where)
    for pat, y0 in EVENTS:
        if pat.search(t) and y < y0: errs.append(f'{where}: {pat.pattern[:8]}… 在 {y0} 年才发生')
    if '大火' in t and y < FIRES[0]: errs.append(f'{where}: {y} 年之前没有大火')
    for m in re.finditer(r'(?:建城|第)\s*(\d+)\s*年', t):
        N = int(m.group(1))
        if N > y: errs.append(f'{where}: 提到将来的第 {N} 年')
        if '火' in t[m.end():m.end() + 6] and N not in FIRES: errs.append(f'{where}: 第 {N} 年没有大火')
    t2, structs = strip_structs(t)
    for nm in STREET_RE: t2 = t2.replace(nm, '□')  # liu4: 运水人巷/埃及人巷/哥特人巷 are street names, not trade/origin words
    for w in structs:
        b = STRUCT_WORDS[w]
        if b > y and not (BUILDING_WORDS.search(t) and b - 3 <= y):
            errs.append(f'{where}: {w} 要到建城 {b} 年才建成')
    fam = ctx['fam']
    if '我' in t and ctx.get('nar_fam'):  # the narrator talking about their own household
        nfm = ctx['nar_fam']; ctx = dict(ctx, other_faiths=ctx['other_faiths'] | {nfm['faith']}, other_origins=ctx['other_origins'] | {nfm['origin']}, other_trades=ctx['other_trades'] | {nfm['trade']})
    for w, fv in FAITHS.items():
        if w in t2 and fv != fam['faith'] and fv not in ctx['other_faiths']:
            errs.append(f'{where}: 信仰 {w} 与这家（{fam["faith"]}）不符')
    for o in ORIGINS:
        if o in t2 and o != fam['origin'] and o not in ctx['other_origins']:
            errs.append(f'{where}: 籍贯 {o} 与这家（{fam["origin"]}）不符')
    for w, tv in TRADE_WORDS.items():
        if w in t2 and tv != fam['trade'] and tv not in ctx['other_trades']:
            errs.append(f'{where}: 行当 {w} 与这家（{fam["trade"]}）不符')
    named = names_in(t)
    ages_ok = set()
    has_death = bool(DEATH.search(t))
    for n in named:
        ok = False
        cands = person(fam, n)
        for p in cands:
            if p['b'] <= y and (memory or home(p, y) or (p['left'] and p['left'] <= y) or (y >= p['d'] and has_death) or (y == p['d'])):
                ok = True; ages_ok |= {y - p['b'], p['d'] - p['b']}
                if memory: ages_ok |= set(range(0, min(y, p['d']) - p['b'] + 1))
        for f2 in ctx['tie_fams']:
            for p in person(f2, n):
                if p['b'] <= y < p['d']: ok = True; ages_ok |= {y - p['b']}
        if n in CHARS and CHARS[n][0] <= y <= CHARS[n][1] and not cands: ok = True
        if n == ctx.get('nar_name'): ok = True
        if not ok: errs.append(f'{where}: {n} 在建城 {y} 年不在这家（或还没出生 / 已不在）')
    for m in re.finditer(r'([0-9]+|[零一二两三四五六七八九十]+)\s*岁', t):
        a = cn2int(m.group(1))
        if named and a not in ages_ok and not re.search(r'不到|快|多|几|上下', t[max(0, m.start() - 2):m.end()]):
            errs.append(f'{where}: “{m.group(0)}”对不上这一行里任何人的年龄')

def check_entry(hid, e, sel=None):
    errs = []
    try: hid = int(hid)
    except ValueError: return None, [f'{hid}: 房号不是数字']
    if str(hid) in DEEP: return None, [f'{hid}: 是手写故事的房子，不许覆盖']
    h = HH.get(hid)
    if not h: return None, [f'{hid}: 底账里没有这栋房子']
    sel = sel or SEL.get(hid)
    if not sel: return None, [f'{hid}: 不在选中的人家名单里']
    fam = next((f for f in h['fams'] if f['B'] == sel['fam']), None)
    if fam is None: return None, [f'{hid}: 这栋房子没有建城 {sel["fam"]} 年搬来的人家']
    nh = HH.get(sel['nar']['house'])
    nf = (next((f for f in nh['fams'] if f['B'] == sel['nar']['fam']), None) if 'fam' in sel['nar'] else fam_at(nh, 55)) if nh else None
    nar = [p for p in (nf['people'] if nf else []) if p['n'] == sel['nar']['n']]
    ties = e.get('ties', [])
    tie_fams = []
    for tie in ties:
        th = HH.get(int(tie[0]))
        if not th or int(tie[0]) == hid: errs.append(f'{hid}: 连线到不存在的房子 {tie[0]}'); continue
        if not (th['built'] <= tie[2] < th['destroyed']): errs.append(f'{hid}: 连线的房子 {tie[0]} 在建城 {tie[2]} 年还不存在'); continue
        tie_fams.append(fam_at(th, tie[2]))
    ctx = {'fam': fam, 'nar_name': sel['nar']['n'], 'tie_fams': tie_fams + ([nf] if nf else []),
           'other_faiths': {f['faith'] for f in tie_fams}, 'other_origins': {f['origin'] for f in tie_fams},
           'other_trades': {f['trade'] for f in tie_fams} | {f['trade'] for f in h['fams'] if f['B'] < fam['B']},  # liu2: the family that lived here before may be named by trade
           'nar_fam': nf}
    lo, hi = max(fam['B'], h['built']), min(60, fam['out'], h['destroyed'] - 1)
    life = e.get('life', [])
    if not (2 <= len(life) <= 3): errs.append(f'{hid}: 人生线应有 2–3 条，现在 {len(life)} 条')
    prev = -999
    for i, (y, t) in enumerate(life):
        if not isinstance(y, int) or not (lo <= y <= hi): errs.append(f'{hid} 第{i+1}条: 建城 {y} 年不在这家住在这里的年份（{lo}–{hi}）')
        if y < prev: errs.append(f'{hid}: 人生线年份没有按顺序')
        prev = y
        if not nar or not home(nar[0], y) or y < nf['B']: errs.append(f'{hid} 第{i+1}条: 讲述人 {sel["nar"]["n"]} 在建城 {y} 年还没住在隔壁')
        check_line(t, y, ctx, errs, f'{hid} 第{i+1}条({y})')
    # 'now' lines (liu2: one per time of day — morning/day/evening/night; a plain string is still accepted)
    # valid years = every person named in any version is home
    now = e.get('now', '')
    nowY = None
    if isinstance(now, dict):
        miss = [k for k in PERIODS if not now.get(k)]
        if miss: errs.append(f'{hid}: “此刻”缺时辰版本 {"/".join(miss)}')
        for k, t in now.items():
            if k not in PERIODS: errs.append(f'{hid}: “此刻”的时辰 {k} 不认识')
            for pat, why in PERIOD_BAD.get(k, []):
                if re.search(pat, t): errs.append(f'{hid} 此刻.{k}: {why}')
            for pat, why, trades in HILL_BAD:
                if re.search(pat, t) and fam['trade'] not in trades: errs.append(f'{hid} 此刻.{k}: {why}')
    nowAll = '。'.join(now.values()) if isinstance(now, dict) else now
    if now:
        ns = [n for n in names_in(nowAll)]
        ys = [Y for Y in range(lo, hi + 1) if all(any(home(p, Y) for p in person(fam, n)) for n in ns if person(fam, n) or n not in CHARS)]
        if not ys: errs.append(f'{hid}: “此刻”里的人从没同时在家')
        else:
            # longest contiguous run that ends at the latest year
            a = b = ys[-1]
            while a - 1 in ys: a -= 1
            # the 'now' line describes the story's present: from the last story line on (or an explicit nowFrom)
            a = max(a, e.get('nowFrom', life[-1][0] if life else a))
            if a > b: errs.append(f'{hid}: “此刻”在故事的最后一条之后就不成立了'); a = b
            nowY = [a, b]
            for Y in (a, b):
                for k, t in (now.items() if isinstance(now, dict) else [('', now)]):
                    check_line(t, Y, ctx, errs, f'{hid} 此刻{"." + k if k else ""}({Y})')
    else: errs.append(f'{hid}: 缺“此刻”')
    obj = e.get('obj')
    if not (isinstance(obj, list) and len(obj) == 2): errs.append(f'{hid}: 缺屋里的物件')
    else: check_line(obj[0] + '。' + obj[1], hi, ctx, errs, f'{hid} 物件', memory=True)
    for tie in ties:
        if len(tie) == 3: check_line(tie[1], tie[2], ctx, errs, f'{hid} 连线({tie[2]})')
    out = dict(e); out['fam'] = fam['B']; out['nar'] = {'house': sel['nar']['house'], 'n': sel['nar']['n']}; out['nowY'] = nowY
    if 'fam' in sel['nar']: out['nar']['fam'] = sel['nar']['fam']
    return out, errs

def main(argv):
    merge = None
    if argv and argv[0] == '--merge': merge = argv[1]; argv = argv[2:]
    files = argv or [os.path.join(XD, 'voices.json')]
    entries = {}
    for f in files:
        for k, v in json.load(open(f, encoding='utf-8')).items(): entries[k] = v
    good, bad = {}, {}
    for k, v in entries.items():
        out, errs = check_entry(k, v)
        if errs: bad[k] = errs
        else: good[k] = out
    for k, errs in bad.items():
        for x in errs: print('✗', x)
    rep = repetition({k: v for k, v in entries.items()})
    for x in rep: print('✗ 查重', x)
    if rep: print(f'查重：{len(rep)} 行超过上限（同一意象 ≤{MOTIF_MAX} 户，同一 {PHRASE_N} 字套话 ≤{PHRASE_MAX} 户）')
    print(f'核对 {len(entries)} 户：通过 {len(good)}，未通过 {len(bad)}')
    if merge:
        json.dump(good, open(merge, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        print(f'写入 {merge}：{len(good)} 户（未通过的已丢弃）')
        return 0
    return 1 if (bad or rep) else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
