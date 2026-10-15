#!/usr/bin/env python3
"""刘线 → CS：把刘线经济层/表面层（economy_v21 骤降路径 → surface_v23）按底账 id 分包成敲门卡旁车，写 docs/living/xerolophos/econ/。
照 tools/cs/factory/reg_pack.py 的模式：数据原样取自刘线（默认 git 的 liu/main，没有就 origin/main、main），按底账 id 重新装箱；
页面只在点开敲门卡时懒取这栋房所在分组的一个文件（econ/g{id//64}.json），没旁车不显示。
每户每年（建城 40–70，31 档）一条：行当（以经济层为准 = surface_v23 trades.json）、经济层生计、房况档/存量%、门面、关门原因、
出租/租住、贫困标记、收入/净收入/支出/年末现钱、最大进项/开销，「为什么看起来这样」短句（按刘线页面 surfWhy 的模板逐字生成）。
另写 econ/chron.json：街道（人流/关门铺面/乞讨/作坊烟）、港口（船/脚夫/零工/仓库）、市集、教堂施舍队的 40–70 年表（小文件，页面不预载）。
用法：python3 liu/tools/econ_pack.py [刘线 docs/living/xerolophos 目录 | git ref]
——Hark（刘线）"""
import json, os, sys, glob, subprocess, tempfile, tarfile, io, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
X = os.path.join(ROOT, 'docs', 'living', 'xerolophos'); OUT = os.path.join(X, 'econ')
G = 64                       # 分组：底账 id // 64 一个文件
Y0, Y1 = 40, 70
arg = sys.argv[1] if len(sys.argv) > 1 else None
src = None; ref_used = None
if arg and os.path.isdir(arg): src = arg; ref_used = arg
else:
    for ref in ([arg] if arg else ['liu/main', 'origin/main', 'main']):
        p = subprocess.run(['git', '-C', ROOT, 'archive', ref, 'docs/living/xerolophos'], capture_output=True)
        if p.returncode == 0:
            tmp = tempfile.mkdtemp(); tarfile.open(fileobj=io.BytesIO(p.stdout)).extractall(tmp)
            src = os.path.join(tmp, 'docs/living/xerolophos'); ref_used = ref + ' ' + subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', ref], capture_output=True, text=True).stdout.strip(); break
assert src and os.path.exists(os.path.join(src, 'surface_AF70.json')), '找不到刘线 surface_AF*.json'
TR = json.load(open(os.path.join(src, 'trades.json')))
S = {y: json.load(open(os.path.join(src, f'surface_AF{y}.json'))) for y in range(Y0, Y1 + 1)}
D0 = S[Y1]; LIV = D0['liv']; MAINT = D0['maint']; FAC = D0['facade']; TYPES = D0['types']; W = D0['why']; TERM = TR['term']
for y, d in S.items(): assert d['liv'] == LIV and d['maint'] == MAINT and d['facade'] == FAC and d['types'] == TYPES and d['why'] == W, y

def num(v): return '%.1f' % (round(v * 10) / 10)
def fill(t, o):
    import re
    return re.sub(r'\{(\w+)\}', lambda m: str(o[m.group(1)]) if o.get(m.group(1)) is not None else m.group(0), t)
def why(d, r):   # 刘线页面 surfWhy 的逐字移植
    ten = r[4] > 0; trend = '' if r[30] is None or r[30] < 0 else ('和去年同一档。' if r[30] == r[0] else '去年是「' + MAINT[r[30]] + '」。')
    o = dict(owner='房东' if ten else '这家', rep=num(r[11]), need=num(r[12]), ocash=num(r[13]), onet=num(r[14]), built=r[25],
             sales=num(r[15]), craft=num(r[16]), liv=LIV[r[2]], dalms=num(r[18]), loan=num(r[19]), lsrc=r[20] or '别人', alms=num(r[17]),
             cond=r[26], wear='%.2f' % (r[27] or 0), rs='%.2f' % (r[28] or 0), age=r[29], trend=trend)
    out = [fill(W['m0new'], o) if (r[0] == 0 and d['year'] - r[25] < 3) else fill(W['m%d' % r[0]], o)]
    if r[1] == 1: out.append(fill(W['f1'], o))
    elif r[1] == 2: out.append(fill(W['f2'], o))
    elif r[1] == 3: out.append(fill(W['f3c'] if r[6] == 1 else W['f3'] if r[6] == 2 else W['f3z'], o))
    if r[5] & 2: out.append(fill(W['p_smoke'], o))
    if r[5] & 4: out.append(fill(W['p_loan'], o))
    if r[5] & 8: out.append(fill(W['p_alms'], o))
    return ''.join(out)
def trcode(i, y):
    s = TR['h'].get(str(i)); k = y - Y0
    if not s or s[k] == '.': return -1
    return ord(s[k]) - 97

F = ['行当(term 下标,-1 无)', '经济层生计(liv 下标)', '房况档(maint)', '房况存量%', '门面(facade)', '标记(1贫困 2灶冷 4借债 8领施舍)', '关门原因(1低营收关门转业 2原定铺不在营 3零营收)',
     '出租栋数', '租住(1=租房东的房)', '收入', '净收入', '支出', '年末现钱', '最大进项类(types)', '最大进项额', '最大开销类(types)', '最大开销额',
     '账本建成年', '房龄', '今年折旧', '修房摊到本栋', '上年房况档(-1 无)', '卖货', '手工品', '施舍', '亏空施舍', '借入', '借自(lsrc 下标,-1 无)']
recs = {}
for y in range(Y0, Y1 + 1):
    d = S[y]
    for k, r in d['houses'].items():
        i = int(k); recs.setdefault(i, {})[y] = r
# 分组要覆盖 CS 干山页面上每一栋房的 id（没有旁车的组也写一个空文件，免得页面取到 404 报错）
page_ids = [h[0] for h in json.load(open(os.path.join(X, 'houses.json')))['houses']]
groups = sorted({i // G for i in page_ids} | {i // G for i in recs})
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
nf = nb = nh = 0; WHY_REF = {}
for g in groups:
    ws = []; wi = {}; H = {}; nchk = 0
    for i in sorted(x for x in recs if x // G == g):
        rows = []
        for y in range(Y0, Y1 + 1):
            r = recs[i].get(y)
            if r is None: rows.append(None); continue
            ls = r[20] or ''
            if ls and ls not in wi: wi[ls] = len(ws); ws.append(ls)
            rows.append([trcode(i, y), r[2], r[0], r[26], r[1], r[5], r[6], r[3], 1 if r[4] > 0 else 0,
                         round(r[7], 1), round(r[8], 1), round(r[9], 1), round(r[10], 1), r[21], round(r[22], 1), r[23], round(r[24], 1),
                         r[25], r[29], round(r[27] or 0, 2), round(r[28] or 0, 2), -1 if r[30] is None else r[30],
                         round(r[15], 1), round(r[16], 1), round(r[17], 1), round(r[18], 1), round(r[19], 1), wi[ls] if ls else -1])
            WHY_REF['h%d' % i, y] = why(S[y], r)
        H['h%d' % i] = rows; nh += 1
    j = {'g': g, 'y0': Y0, 'y1': Y1, 'f': F, 'term': TERM, 'craft_liv': TR['craft_liv'], 'craft_fine': TR['craft_fine'], 'liv': LIV, 'maint': MAINT, 'facade': FAC, 'types': TYPES,
         'path': {str(y): S[y]['path'] for y in range(Y0, Y1 + 1)}, 'why': W, 'lsrc': ws, 'h': H}
    b = json.dumps(j, ensure_ascii=False, separators=(',', ':')).encode(); open(os.path.join(OUT, 'g%d.json' % g), 'wb').write(b); nf += 1; nb += len(b)
# 年表
ch = {'y0': Y0, 'y1': Y1, 'level': D0['level'], 'nodes': {}, 'streets': {}, 'city': {}}
for y in range(Y0, Y1 + 1):
    d = S[y]; sm = d['summary']
    ch['city'][str(y)] = {'path': d['path'], 'ships': round(sm['ships'], 1), 'poor_city': sm['poor_city'], 'poor_page': sm['poor_page'], 'nosmoke_page': sm['nosmoke_page'],
                          'closed_shopfronts_city': sm['closed_shopfronts_city'], 'closed_shopfronts_page': sm['closed_shopfronts_page'], 'alms_city': sm['alms_city'], 'maint_page': sm['maint_page']}
    for n in d['nodes']:
        e = ch['nodes'].setdefault(n['id'], {'kind': n['kind'], 'name': n['name'], 'x': n['x'], 'y': n['y'], 'inpage': n['inpage'], 'by': {}})
        e['by'][str(y)] = {k: v for k, v in n.items() if k not in ('id', 'kind', 'name', 'x', 'y', 'inpage')}
    for s in d['streets']:
        e = ch['streets'].setdefault(str(s['si']), {'x': s['x'], 'y': s['y'], 'by': {}})
        e['by'][str(y)] = [s['h'], s['open'], s['ws'], s['closed'], s['crowd'], s['smoke'], s['beg'], s['beg_spot']]
ch['street_f'] = ['房数', '开张铺', '作坊', '关门铺面', '人流档(level)', '作坊烟声档', '领施舍户', '乞讨点(1=是)']
b = json.dumps(ch, ensure_ascii=False, separators=(',', ':')).encode(); open(os.path.join(OUT, 'chron.json'), 'wb').write(b)
open(os.path.join(OUT, 'SOURCE.md'), 'w', encoding='utf8').write(f'''# 生计/房况旁车 econ/g{{id//{G}}}.json + chron.json

来源：刘线（liuzhijie820802-a11y/anthousa-liuzhijie）{ref_used}，docs/living/xerolophos/surface_AF40…70.json + trades.json；数值原样取，未改。
- 经济层：experiments/economy_v21（25d9843）骤降路径（AF65 到港 ×0.3）逐年流；表面层：experiments/surface_v22（f64ab4c）+ surface_v23（91a16d3）。
- 行当以经济层为准（surface_v23 trades.json：每栋每年生计码，40 年前按 40 年回推）；手工铺/作坊的细分（陶匠/织工/鞋匠/铜匠）以页面原散列行当为准，旁车只给经济层用语。
- 房况 = 存量四档（折旧 0.6×(0.6+0.8×房龄/60)×(1+0.5×(1−C/V))、修房按栋摊回、档界 0.90/0.75/0.55）。**已知偏高：AF70 干山破败 36.2%（全城 39.0%），折旧基数待 surface_v24 修。**
- 「为什么」短句：旁车带模板（why，取自 surface_AF*.json）和所需数字，页面按刘线 surfWhy 逐字拼；liu/tools/econ_why_sample.json 是 Python 端生成的抽样，check_econ 比对。
- 覆盖：干山页面房屋（底账 id = 页面 id，AF40 2,638 户 → AF70 4,605 户，含账本 AF61–70 新建 208 栋）；这里没有的房子敲门卡不显示这一段。
装箱：liu/tools/econ_pack.py 按底账 id//{G} 分组，每组一个文件；CS 干山页只在敲门卡点开时才取这栋房所在组的一个文件。
重跑：python3 liu/tools/econ_pack.py（默认 git archive liu/main）。
''')
json.dump({'%s|%d' % k: v for k, v in list(WHY_REF.items())[::97]}, open(os.path.join(ROOT, 'liu', 'tools', 'econ_why_sample.json'), 'w'), ensure_ascii=False)   # check_econ 用：页面生成的短句要与刘线 surfWhy 逐字一致（抽样）
print(f'econ 旁车：{nf} 个文件、{nh} 户，{nb/1e6:.2f} MB；chron.json {len(b)/1e3:.0f} KB；来源 {ref_used}')
