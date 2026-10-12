"""刘线 · 查重：同一个意象、同一句套话，全街不许出现太多次。
Repetition check for the generated household stories (voices.json).
  - MOTIFS: named images / plot templates that wore out in liu1 (widowers, jar-for-cloth, the bowl on the wall, the orphan alone in an empty house …).
    Each motif may appear in at most MOTIF_MAX households.
  - PHRASES: any run of PHRASE_N characters (after masking out personal names, building names, origins) may appear in at most PHRASE_MAX households.
usage:
  python3 tools/dedup.py [voices.json]          # stats: top motifs / phrases and which households go over
  python3 tools/dedup.py --flag [voices.json]   # list every over-budget line (household, field, text) to rewrite
Imported by check_stories.py (repetition() returns the list of failures).
"""
import json, os, re, sys, collections

MOTIF_MAX = 3
PHRASE_N = 6
PHRASE_MAX = 3

MOTIFS = {
    '鳏夫': '鳏夫|光棍',
    '罐子换布': '罐.{0,8}换.{0,6}布|布.{0,8}换.{0,6}罐',
    '碗挂在墙上/门口': '碗.{0,10}(挂|钉)|(挂|钉).{0,6}碗|墙上.{0,6}碗',
    '酒碗是他的位置': '他的位置|她的位置',
    '南港搬上来': '南港.{0,4}(搬|上来|上山)',
    '大火以后搬来': '大火以后.{0,4}(搬|上来|上山|来的)',
    '一屋子孩子': '一屋子(孩子|女儿|儿子|娃)',
    '一个接一个': '一个接一个|一个跟一个|一年一个',
    '独守空屋/一个人守着': '一个人守|独自守|守着空|空屋|空房子|空荡荡',
    '孤儿': '孤儿|没爹没娘|爹娘都(死|没)',
    '没留住': '没留住',
    '没养大/没挺过': '没养大|没挺过|没活过',
    '进了修道院': '修道院|修院|修士',
    '跟着粮船出海': '粮船出了?海|跟着粮船|上了粮船|随船|上船|随粮船|上了船',
    '去码头找活': '码头上?找活',
    '跟我一个名字': '跟我一个名字|跟我同名|和我一个名字|跟我一样|我的名字|同一个名字|跟我同名',
    '刻痕': '刻了?.{0,3}(道|痕)',
    '一个人X带孩子': '一个人(揉面|做鞋|开酒馆|挑水|织布|烧窑|守窑).{0,4}带',
    '门口的红布': '红布',
    '留下的鞋': '没人穿的鞋|一排小鞋|小鞋',
    '头巾': '头巾',
    '擀面杖': '擀面杖',
    '扁担': '扁担',
    '兑了水': '兑了?水',
    '嗓门大': '嗓门',
    '半条街都听得见': '半条街',
    '天不亮': '天不亮|天没亮',
    '抢生意': '抢.{0,2}(生意|客人)',
    '送一篮饼': '一篮.{0,2}饼|送.{0,3}饼',
    '从不催账': '催账|赊账|赊',
    '女儿织布比儿子细': '比儿子细',
    '泥比南港': '泥比',
    '请全街喝酒': '全街',
    '一个铜子': '铜子|铜板',
    '他们说/据说': '据说',
    '我们两家都': '我们两家都|两家都(做|开|挑|卖|织)',
    '换了十几年': '换了十几年|换过.{0,3}不少',
    '多给一块/多扯一尺': '多给.{0,2}一块|多扯一尺|多留一罐|多挑一罐',
    '常坐在一起': '常坐在一起|坐在一起',
    '没再娶/没再嫁': '没再娶|没再嫁|续弦|续娶|改嫁|再没娶|再没娶人|没再成家|一直单着|还单着|不再娶|再也没娶',
    '一句话不说': '一句话(也)?不说|一句话也没说|一路没说话',
    '进门第二年就死了': '进门.{0,3}(第二年|一年)就?死',
    '在门口站了很久': '门口站了(很久|半天)',
    '我们俩都是寡妇': '都是寡妇|两个寡妇',
    '撑起了/挑起了': '挑起了|撑起了',
    '小罐子陪葬': '小罐子?.{0,6}(埋|陪)',
    '下山扛活': '下山扛活|扛活',
    '背起水罐': '背起.{0,4}水罐|水罐背|背上了水罐|接了.{0,3}水路|接过.{0,4}水',
    '孩子在X里睡/爬': '睡在面|在织机底下|在酒桶|在酒瓮|在泥堆|面缸里|面口袋',
    '炉火没灭': '(火|炉).{0,4}(没灭|不能凉|从没灭)',
}
MOTIF_RE = {k: re.compile(v) for k, v in MOTIFS.items()}
# daily-routine templates of the time-of-day 'now' lines (liu2): looser cap, since a baker does knead every morning,
# but the same stock beat may not open every other household's morning.
NOW_MOTIF_MAX = 6
NOW_MOTIFS = {
    '泡皮子': '泡(上)?皮子', '去交鞋/交布': '交鞋|交布|去交', '在灯下': '灯下', '歇脚': '歇脚', '叫醒': '叫醒|摇醒|拍醒',
    '坐上织机': '坐上织机', '开窑': '开窑', '数孩子': '数孩子|个个数|数了数|点了点人头', '发面': '发面|发好面', '喂奶': '喂奶|喂[^，。]{1,6}奶',
    '扛柴': '扛柴|搬柴|劈柴', '去打水': '去打水|去池边', '搬罐子': '搬罐子|搬酒罐|搬酒', '冲罐子': '冲.{0,2}罐', '擦桌子': '擦桌子',
    '在门口做饭': '门口做饭', '在门口打闹': '打闹', '在门口等': '在门口等', '领着弟妹': '领着弟妹|叫醒弟妹', '守着窑': '守着窑',
    '跟在后面': '跟在后面', '铺子吵': '吵成一团|吵得像', '一个人守着': '一个人守', '把罐子排在门口': '排在门口',
    '没有客人': '没有客人|没几个客人', '扒开窑': '扒开窑|推开窑门', '浸皮子': '皮子浸|皮子泡', '踩响织机': '踩响织机|踩下踏板|踩踏板',
    '提着罐子出门': '(提|拎)着?罐子出门|挑罐出门|拎.{0,4}小罐', '抱着鞋/扛布下坡': '(抱着鞋|扛布|扛着.{0,3}布|把布送|把鞋送|抱着.{0,4}鞋)下?坡?', '往里扛': '往里扛',
    '卸门板': '卸(了)?门板', '推空瓮': '空瓮', '盖好面团': '盖好|盖上(湿)?布', '借着炉光': '借着(炉|窑)', '吹火': '吹火', '摸过孩子': '摸过', '拉起来': '拉起来|拽起来',
    '抱着婴儿': '抱着[^，。]{2,6}(坐|站|在门|晒)', '灶前': '灶前', '编草绳': '编草绳|编筐', '倚门': '倚门|倚着门|门框', '屋里只剩': '屋里只剩|只剩他', '各自睡下': '各自睡下|睡下了', '在门口玩': '在门口玩',
}
NOW_MOTIF_RE = {k: re.compile(v) for k, v in NOW_MOTIFS.items()}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'docs', 'living', 'xerolophos')
PUNCT = re.compile('[｜，。、？！：；“”‘’—…「」《》（）() \n·]')

def _masks():
    city = json.load(open(os.path.join(XD, 'city.json'), encoding='utf-8'))
    words = set(city['names_m']) | set(city['names_f']) | set(city.get('origins', []))
    src = open(os.path.join(XD, 'index.html'), encoding='utf-8').read()
    for m in re.finditer(r"const N[MF]=city\.names_[mf]\.filter\([^)]*\)\.concat\(\[([^\]]*)\]\)", src):
        words |= set(re.findall(r"'([^']+)'", m.group(1)))
    names_zh = json.load(open(os.path.join(ROOT, 'i18n', 'i18n.json'), encoding='utf-8'))['names_zh']
    words |= {v for v in names_zh.values() if len(v) >= 2}
    words |= {l['name'].split(' · ')[0] for l in city['landmarks']}
    words |= {'特罗阿德粮仓', '亚历山大粮仓', '阿纳斯塔西娅', '亚历山大里亚', '卡帕多西亚', '阿里乌派', '尼西亚派', '建城'}
    return sorted((w for w in words if len(w) >= 2), key=len, reverse=True)
MASK = None

def nows(e):
    n = e.get('now', '')
    return list(n.values()) if isinstance(n, dict) else [n]

def fields(e):
    """(field, text) pairs of one household entry"""
    out = []
    n = e.get('now', '')
    if isinstance(n, dict):
        for k, v in n.items(): out.append(('now.' + k, v))
    elif n: out.append(('now', n))
    for i, (y, t) in enumerate(e.get('life', [])): out.append((f'life{i}', t))
    if e.get('obj'): out.append(('obj', e['obj'][0] + '。' + e['obj'][1]))
    for i, t in enumerate(e.get('ties', [])): out.append((f'tie{i}', t[1]))
    return out

def masked(t):
    global MASK
    if MASK is None: MASK = _masks()
    for w in MASK:
        if w in t: t = t.replace(w, '■')
    return t

def grams(t):
    t = masked(t)
    return {t[i:i + PHRASE_N] for i in range(len(t) - PHRASE_N + 1) if not PUNCT.search(t[i:i + PHRASE_N]) and '■' not in t[i:i + PHRASE_N]}

def entries_of(V):
    """voices.json values may be one entry or a list of entries (a house that changed families)"""
    for k, v in V.items():
        for j, e in enumerate(v if isinstance(v, list) else [v]):
            yield (f'{k}' if not isinstance(v, list) else f'{k}#{j}'), e

def tally(V):
    motif = collections.defaultdict(list)   # motif -> [(key, field)]
    phrase = collections.defaultdict(list)  # gram -> [(key, field)]
    for key, e in entries_of(V):
        seen_m, seen_p = set(), set()
        for f, t in fields(e):
            for m, r in MOTIF_RE.items():
                if r.search(t) and m not in seen_m: seen_m.add(m); motif[m].append((key, f))
            for g in grams(t):
                if g not in seen_p: seen_p.add(g); phrase[g].append((key, f))
    return motif, phrase

def tally_now(V):
    occ = collections.defaultdict(list)  # (motif) -> [(key, field)] counted per line, now.* fields only
    for key, e in entries_of(V):
        for f, t in fields(e):
            if not f.startswith('now'): continue
            for m, r in NOW_MOTIF_RE.items():
                if r.search(t): occ[m].append((key, f))
    return occ

def over(V, motif_max=MOTIF_MAX, phrase_max=PHRASE_MAX):
    """lines over budget: the first `max` households keep the image, the rest are flagged (stable order = file order)"""
    motif, phrase = tally(V)
    flags = collections.defaultdict(set)
    for m, occ in tally_now(V).items():
        for key, f in occ[NOW_MOTIF_MAX:]: flags[(key, f)].add('此刻套路「' + m + '」')
    for m, occ in motif.items():
        for key, f in occ[motif_max:]: flags[(key, f)].add('意象「' + m + '」')
    for g, occ in phrase.items():
        for key, f in occ[phrase_max:]: flags[(key, f)].add('套话「' + g + '」')
    return flags, motif, phrase

def repetition(V):
    flags, motif, phrase = over(V)
    errs = []
    for (key, f), why in sorted(flags.items()):
        errs.append(f'{key} {f}: 重复 ' + '、'.join(sorted(why)))
    return errs

def stats(V, top=15):
    motif, phrase = tally(V)
    print('意象（出现户数，上限 %d）:' % MOTIF_MAX)
    for m, occ in sorted(motif.items(), key=lambda x: -len(x[1]))[:top]: print(f'  {len(occ):4d}  {m}')
    print('套话（%d 字，出现户数，上限 %d）:' % (PHRASE_N, PHRASE_MAX))
    # merge overlapping grams: report a gram only if not contained in a longer equally-frequent one is overkill; just top list
    for g, occ in sorted(phrase.items(), key=lambda x: -len(x[1]))[:top]: print(f'  {len(occ):4d}  {g}')
    nowo = tally_now(V)
    print('此刻套路（出现行数，上限 %d）:' % NOW_MOTIF_MAX)
    for m, occ in sorted(nowo.items(), key=lambda x: -len(x[1]))[:8]: print(f'  {len(occ):4d}  {m}')
    mm = max((len(v) for v in motif.values()), default=0); pm = max((len(v) for v in phrase.values()), default=0)
    print(f'最高频意象 {mm} 户，最高频套话 {pm} 户')
    return mm, pm

if __name__ == '__main__':
    a = sys.argv[1:]
    flag = bool(a and a[0] == '--flag')
    if flag: a = a[1:]
    V = json.load(open(a[0] if a else os.path.join(XD, 'voices.json'), encoding='utf-8'))
    if flag:
        flags, _, _ = over(V)
        E = dict(entries_of(V))
        for (key, f), why in sorted(flags.items()):
            t = dict(fields(E[key]))[f]
            print(f'{key}\t{f}\t{"、".join(sorted(why))}\t{t}')
        print(len(flags), 'lines over budget', file=sys.stderr)
    else:
        stats(V)
