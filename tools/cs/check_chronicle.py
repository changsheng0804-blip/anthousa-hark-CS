"""CS 线 · /goal 3 项 5：check_chronicle。编年史（上游 chronicle/*.md，只读）里每一条有地点的事件，都要在 docs/living/tiles/events.json 里有落点。
独立于 chron_events.py 的算法，自己再从编年史和底账查一遍：
  1 每个「编年史写了、且是这个时代新建」的结构（占位符 ∩ eras[].accepted 的 build）都有事件，年 = 结构 built，
  2 底账里每件灾害事件（eras[].events，带坐标）编年史里写了的都有事件，位置 = 底账坐标 ±1 px，
  3 落点在画布里；没偏出画布的，落点落在结构的包围盒里（±2 px），偏出画布的，记 off（偏出多少像素）并列给所有者，
  4 文案是编年史原文的一段（占位符换成中文名之后），不是编出来的，不含 {{ }}，
  5 文案里写了「第 N 年」的，N 和事件的年一致（N 比时代起点小的是「第二年」这种相对说法，不算），
  6 年份覆盖：事件年落在 chronicle 全部时段（-657 到 70）里，每个时代至少一件，
  7 没法定位的（带年份、没有地点）列在 unlocated 里，逐条打印。
页面那头（落点跟年份淡入淡出、点了能飞过去并切年）由 check_tiles.js 查（/goal 3 项 7 起）。用法：python3 tools/cs/check_chronicle.py ——Hark（CS线）"""
import json, os, re, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
L = os.path.join(ROOT, 'docs', 'living', 'tiles'); M = json.load(open(os.path.join(L, 'meta.json')))
W = json.load(open(os.path.join(ROOT, 'world.json'))); NZ = json.load(open(os.path.join(ROOT, 'docs', 'data.json')))['names_zh']
ST = {t['id']: t for t in W['structures']}; S = M['scale']; OX, OY = M['origin']; CW, CH = M['grid'][0] * M['tile_px'], M['grid'][1] * M['tile_px']
red = 0; lines = []
def chk(ok, msg):
    global red
    lines.append(('✅ ' if ok else '❌ ') + msg); red += (not ok)
ef = os.path.join(L, 'events.json')
if not os.path.exists(ef):
    chk(False, 'docs/living/tiles/events.json 不存在（先跑 tools/cs/factory/chron_events.py）'); print('\n'.join(lines)); sys.exit(1)
E = json.load(open(ef)); EV = {v['id']: v for v in E['events']}
def subst(s): return re.sub(r'\{\{([a-z_0-9]+)\}\}', lambda m: NZ.get(m.group(1)) or ST.get(m.group(1), {}).get('name') or m.group(1), s)
CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def cn(s):
    if s.isdigit(): return int(s)
    if '十' in s: a, b = s.split('十'); return (CN[a] if a else 1) * 10 + (CN[b] if b else 0)
    return CN[s]
miss = []; wrong = []; offs = []; nl = 0; eras_seen = {}; badtext = []; badyear = []; badpos = []; total = 0
for e in W['eras']:
    f = os.path.join(ROOT, 'chronicle', f"{e['from']}_{e['to']}.md")
    if not os.path.exists(f): continue
    raw = open(f, encoding='utf-8').read(); text = subst(raw)
    ids = set(re.findall(r'\{\{([a-z_0-9]+)\}\}', raw))
    for a in e['accepted']:
        if a.get('op') != 'build' or a['id'] not in ids or a['id'] not in ST: continue
        total += 1; t = ST[a['id']]; v = EV.get(a['id'])
        if not v: miss.append(f"{a['id']}（{t['built']} 年）"); continue
        if v['year'] != t['built']: wrong.append(f"{a['id']} 事件年 {v['year']} ≠ 底账 built {t['built']}")
        eras_seen[(e['from'], e['to'])] = eras_seen.get((e['from'], e['to']), 0) + 1
        # 落点
        pts = t['geom']['coords'] if t['geom']['type'] != 'point' else [t['geom']['coords']]
        xs = [(p[0] - OX) * S for p in pts]; ys = [(p[1] - OY) * S for p in pts]
        if v['off']:
            offs.append((a['id'], t['built'], v['off']))
            if not (v['x'] <= 24 or v['y'] <= 24 or v['x'] >= CW - 24 or v['y'] >= CH - 24): badpos.append(f"{a['id']} 标了偏出画布，落点却不在画布边上")
        elif not (min(xs) - 2 <= v['x'] <= max(xs) + 2 and min(ys) - 2 <= v['y'] <= max(ys) + 2): badpos.append(f"{a['id']} 落点 ({v['x']},{v['y']}) 不在结构包围盒里")
        if not (0 <= v['x'] <= CW and 0 <= v['y'] <= CH): badpos.append(f"{a['id']} 落点出了画布")
        # 文案
        tx = v['text']
        if '{{' in tx or not tx: badtext.append(f"{a['id']} 文案空或带占位符")
        elif tx.rstrip('。，；：') not in text.replace('\n', '') and tx not in text: badtext.append(f"{a['id']} 文案不是编年史原文：{tx[:30]}…")
        if v.get('cite') is not None and v['cite'] != v['year']: badyear.append(f"{a['id']} 文案写第 {v['cite']} 年，底账 {v['year']}")
    for ev in e.get('events') or []:
        si = [s for s in re.split(r'[。]', text) if str(ev.get('houses', '')) in s and '烧' in s]
        if not si: continue
        total += 1; v = EV.get(f"{ev['type']}{ev['year']}")
        if not v: miss.append(f"{ev['type']}{ev['year']}"); continue
        eras_seen[(e['from'], e['to'])] = eras_seen.get((e['from'], e['to']), 0) + 1
        px_, py_ = (ev['x'] - OX) * S, (ev['y'] - OY) * S
        if abs(v['x'] - px_) > 1 or abs(v['y'] - py_) > 1: badpos.append(f"{v['id']} 落点和底账坐标差 >1 px")
        if v['year'] != ev['year']: wrong.append(f"{v['id']} 年不对")
        if v.get('cite') is not None and v['cite'] != v['year']: badyear.append(f"{v['id']} 文案写第 {v['cite']} 年")
        if v['text'] not in text.replace('\n', ''): badtext.append(f"{v['id']} 文案不是编年史原文")
chk(not miss, f'编年史里有地点的事件 {total} 件，都有落点' + (f'；缺：{"、".join(miss)}' if miss else ''))
chk(not wrong, '事件年 = 底账建成年/发生年' + (f'；{"；".join(wrong)}' if wrong else ''))
chk(not badpos, f'落点位置对（画布内、没偏出的落在结构包围盒里、灾害对底账坐标）' + (f'；{"；".join(badpos)}' if badpos else ''))
chk(not badtext, '文案都是编年史原文、没有占位符' + (f'；{"；".join(badtext)}' if badtext else ''))
chk(not badyear, '文案里写的「第 N 年」和事件年一致' + (f'；{"；".join(badyear)}' if badyear else ''))
lo, hi = E['years']; chk(lo <= -657 + 0 and hi >= 65 and all(-657 <= v['year'] <= 70 for v in E['events']), f'事件年份 {lo} 到 {hi}，都在编年史时段（-657 到 70）里')
allera = [(e['from'], e['to']) for e in W['eras'] if os.path.exists(os.path.join(ROOT, 'chronicle', f"{e['from']}_{e['to']}.md"))]
chk(all(eras_seen.get(k) for k in allera), f'{len(allera)} 个时代每个都至少一件事件（' + '、'.join(f'{a}–{b}:{eras_seen.get((a, b), 0)}' for a, b in allera) + '）')
# 8 年份轴（/goal 3 项 6）：烤好的年份覆盖 -657 到 70——0 年以后每 10 年一套，0 年以前间隔 ≤260 年；每个时代里至少有一个烤好的年份；
#   每个年份的级 0、级 1 瓦片数都对得上 meta（落地的文件 + 指到别年的别名），瓦片总体积 ≤ 80 MB
Y_ = M['years']; AL = M.get('alias', {})
gaps_ = [b - a for a, b in zip(Y_, Y_[1:])]
chk(Y_ == sorted(set(Y_)) and Y_[0] <= -657 and Y_[-1] >= 70 and all(g <= (10 if a >= 0 else 260) for a, g in zip(Y_, gaps_)), f'年份轴 {Y_[0]} 到 {Y_[-1]}，共 {len(Y_)} 个年份，0 年后每 10 年、0 年前 ≤260 年一个（建城年 -657 单算一档）')
noyr = [f"{e['from']}–{e['to']}" for e in W['eras'] if not any(e['from'] <= y <= e['to'] for y in Y_)]
chk(not noyr, '每个时代里至少有一个烤好的年份' + (f'；缺：{"、".join(noyr)}' if noyr else ''))
bad_ = []
for y in Y_:
    for l in ('0', '1'):
        n = M['levels'][l].get(str(y), {}).get('tiles', -1)
        have = len([f for f in os.listdir(os.path.join(L, str(y), l))]) if os.path.isdir(os.path.join(L, str(y), l)) else 0
        al = len(AL.get(f'{y}/{l}', {}))
        if have + al != n: bad_.append(f'{y} 年级 {l}：meta {n} 块，落地 {have} + 别名 {al}')
chk(not bad_, '每个年份级 0、级 1 的瓦片都在（落地文件 + 别名 = meta 块数）' + (f'；{"；".join(bad_[:4])}' if bad_ else ''))
tot_ = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(L) for f in fs)
chk(tot_ <= 80 * 1024 * 1024, f'瓦片总体积 {tot_ / 1048576:.1f} MB ≤ 80 MB')
# 9 页面那头（/goal 3 项 7）：check_chron_page.js 在 jsdom 里跑瓦片页——事件全载入、按年淡入淡出、点一下飞过去并切年、出卡、年份轴能拖
import subprocess
_js = os.path.join(HERE, 'check_chron_page.js')
if os.path.isdir('/workspace/work/csjs/node_modules'):
    r_ = subprocess.run(['node', _js], capture_output=True, text=True, env=dict(os.environ, NODE_PATH='/workspace/work/csjs/node_modules', AH=ROOT), timeout=300)
    pl_ = [l for l in r_.stdout.splitlines() if l[:1] in '✅❌']
    for l in pl_: lines.append('页面 · ' + l)
    red += sum(l.startswith('❌') for l in pl_) + (1 if r_.returncode and not any(l.startswith('❌') for l in pl_) else 0)
else:
    chk(False, '页面那头没法查：/workspace/work/csjs/node_modules（jsdom）不在')
print('\n'.join(lines))
print(f"— 偏出画布、落点收到边上的 {len(offs)} 件（要所有者定画布要不要往西扩）：" + '、'.join(f'{i}({y}年，偏 {o}px)' for i, y, o in offs))
print(f"— 没法定位的 {len(E['unlocated'])} 条（带年份、没有地点）：")
for u in E['unlocated']: print(f"   {u['year']} 年 · {u['text'][:40]} —— {u['why'][:14]}")
print(f"check_chronicle: {red} 条不过"); sys.exit(1 if red else 0)
