"""CS 线 · /goal 3 项 5：编年史 → 事件落点。python3 chron_events.py → docs/living/tiles/events.json
编年史（chronicle/*.md，上游写的，只读）里每一句有地点的话 = 一个事件：
  ① 建造类：这个时代 accepted 里 op=build 的结构（{{id}} 占位符），位置 = world.json 里这个结构的几何中心，年 = 结构的 built；
  ② 灾害类：world.json eras[].events（火灾等，带 x,y,r、烧毁多少栋），文案取编年史里写了同一个烧毁数的那一句；
  文案 = 编年史原文里那一句（占位符换成中文名，名字表用上游 docs/data.json 的 names_zh）；句子太长就截含这个占位符的那几个分句，不改字、不编故事。
没法定位的（带「第 N 年」但没有地点：皇帝下诏、大公会议……）列在 unlocated 里，check_chronicle.py 读它。
画布 = 瓦片页盖住的那一块世界（x 从世界格 416 起），有的事件（水渠、城外田地、莫基乌斯小路……）在画布外：落点收到画布边上（off:true，记下偏出多少像素），收口时交所有者定要不要把画布往西扩。
坐标 = 瓦片页 0 级像素（和 meta.json、places.json 同一套）。——Hark（CS线）"""
import json, os, re, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
L = os.path.join(ROOT, 'docs', 'living'); M = json.load(open(os.path.join(L, 'tiles', 'meta.json')))
W = json.load(open(os.path.join(ROOT, 'world.json'))); NZ = json.load(open(os.path.join(ROOT, 'docs', 'data.json')))['names_zh']
S = M['scale']; OX, OY = M['origin']; CW, CH = M['grid'][0] * M['tile_px'], M['grid'][1] * M['tile_px']
ST = {t['id']: t for t in W['structures']}
CN = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def cn2int(s):
    if s.isdigit(): return int(s)
    if '十' in s:
        a, b = s.split('十'); return (CN[a] if a else 1) * 10 + (CN[b] if b else 0)
    return CN[s]
YEAR_RE = re.compile(r'第\s*([0-9]+|[一二三四五六七八九十]+)\s*年')
def px(wx, wy): return ((wx - OX) * S, (wy - OY) * S)
def geom_pts(g):
    c = g['coords']; return [c] if g['type'] == 'point' else c
def centre(g):
    """多边形取顶点平均，折线取沿线一半长度处，点取点本身（世界格）"""
    if g['type'] == 'point': return tuple(g['coords'])
    pts = g['coords']
    if g['type'] == 'line':
        seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]; half = sum(seg) / 2
        for i, d in enumerate(seg):
            if half <= d or i == len(seg) - 1:
                t = half / d if d else 0; return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
            half -= d
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
def extent_px(g):
    pts = geom_pts(g); xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; return max(max(xs) - min(xs), max(ys) - min(ys)) * S
def zoom_for(ext):   # 让这个东西占一屏（约 1000 px 宽）的一半多一点；点和小建筑落在 1.6（街巷级刚好换手之前）
    return round(max(0.35, min(1.6, 900 / max(ext, 1))), 2)
def subst(s): return re.sub(r'\{\{([a-z_0-9]+)\}\}', lambda m: NZ.get(m.group(1)) or ST.get(m.group(1), {}).get('name') or m.group(1), s)
def sentences(txt):
    out = []
    for para in txt.split('\n'):
        if not para.strip() or para.startswith('#'): continue
        for m in re.finditer(r'[^。！？]+[。！？]?[」”』）]?', para):
            s = m.group(0).strip()
            if s: out.append(s)
    return out
def excerpt(sent, key):
    """整句 ≤ 70 字就整句；否则取含 key 的分句，太短就并上前一个分句，再并后一个，直到 ≥ 14 字"""
    if len(sent) <= 70: return sent
    parts = re.split(r'(?<=[，；：])', sent); i = next((k for k, p in enumerate(parts) if key in p), 0); a = b = i
    while len(''.join(parts[a:b + 1])) < 14 and (a > 0 or b < len(parts) - 1):
        if a > 0: a -= 1
        elif b < len(parts) - 1: b += 1
    s = ''.join(parts[a:b + 1]).strip()
    return s.rstrip('，；：') + ('。' if not s.endswith(('。', '」', '”')) else '')
def place(g):
    cx, cy = px(*centre(g)); off = 0.0
    x, y = min(max(cx, 24), CW - 24), min(max(cy, 24), CH - 24)
    if (x, y) != (cx, cy): off = math.dist((x, y), (cx, cy))
    return round(x), round(y), round(off)
def build():
    ev, unl = [], []
    for e in W['eras']:
        f = os.path.join(ROOT, 'chronicle', f"{e['from']}_{e['to']}.md")
        if not os.path.exists(f): continue
        sents = sentences(open(f, encoding='utf-8').read()); used = set()
        for a in e['accepted']:
            if a.get('op') != 'build' or a['id'] not in ST: continue
            t = ST[a['id']]; key = '{{' + a['id'] + '}}'
            si = next((i for i, s in enumerate(sents) if key in s), None)
            if si is None: continue                      # 编年史没写这一条：不是编年史事件
            used.add(si); x, y, off = place(t['geom']); yr = YEAR_RE.search(sents[si]); ey = cn2int(yr.group(1)) if yr else None
            ev.append(dict(id=a['id'], kind='build', year=t['built'], era=[e['from'], e['to']], type=t['type'], name=NZ.get(a['id']) or t['name'],
                           text=subst(excerpt(sents[si], key)), x=x, y=y, z=zoom_for(extent_px(t['geom'])), off=off,
                           cite=ey if (ey is not None and ey >= e['from']) else None))
        for k, v in enumerate(e.get('events') or []):
            si = next((i for i, s in enumerate(sents) if str(v.get('houses', '')) in s and '烧' in s), None)
            if si is None: continue
            used.add(si); x, y, off = place(dict(type='point', coords=[v['x'], v['y']])); yr = YEAR_RE.search(sents[si])
            ev.append(dict(id=f"{v['type']}{v['year']}", kind=v['type'], year=v['year'], era=[e['from'], e['to']], type=v['type'], name=f"{v['year']} 年{ {'fire': '大火'}.get(v['type'], v['type']) }",
                           text=subst(excerpt(sents[si], str(v['houses']))), x=x, y=y, z=zoom_for(v.get('r', 10) * 2 * S), off=off,
                           cite=cn2int(yr.group(1)) if yr else None, houses=v.get('houses')))
        for i, s in enumerate(sents):
            if i in used: continue
            yr = YEAR_RE.search(s)
            if yr and cn2int(yr.group(1)) >= e['from']:
                unl.append(dict(year=cn2int(yr.group(1)), era=[e['from'], e['to']], text=subst(s), why='没有地点（句子里没有占位符，底账里也没有对应的结构或事件坐标）' if '{{' not in s else '占位符指向的结构不是这个时代新建的，只是背景'))
    ev.sort(key=lambda v: (v['year'], v['id']))
    return ev, unl
if __name__ == '__main__':
    ev, unl = build()
    json.dump(dict(canvas=[CW, CH], years=[min(v['year'] for v in ev), max(v['year'] for v in ev)], events=ev, unlocated=unl), open(os.path.join(L, 'tiles', 'events.json'), 'w'), ensure_ascii=False, indent=0)
    off = [v for v in ev if v['off']]
    print(len(ev), '件有落点的事件', len(off), '件在画布外（收到边上）', len(unl), '条没地点', '年份', ev[0]['year'], '到', ev[-1]['year'])
