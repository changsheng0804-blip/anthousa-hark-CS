"""CS 线 · 工厂 · 第二段：配方 → scene.json + city.json + 公用素材
只从两样东西来：底账切出来的 frame.json / houses.json，和 quarters/<q>.json 配方（名字、一句话、气氛）。
页面是所有街区共用的一份（template = docs/living/nangang/index.html），这里原样拷过去；accept 查它和模板一字不差。
用法: python scene_auto.py <q>"""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIV = os.path.join(ROOT, 'docs', 'living'); TPL = os.path.join(LIV, 'nangang')
ASSETS = ['index.html', 'people.json', 'people.png', 'daphne.jpg', 'theodoros.jpg', 'kits']
GENERIC = ['names_m', 'names_f', 'origins', 'faiths', 'trades', 'today']


def pre(q): return {'nangang': 'ng'}.get(q, q[:2])


def main():
    q = sys.argv[1]; Q = os.path.join(LIV, q); R = json.load(open(os.path.join(HERE, 'quarters', q + '.json')))
    fr = json.load(open(os.path.join(Q, 'frame.json'))); HS = json.load(open(os.path.join(Q, 'houses.json')))
    keys = R['keys']; last = max(keys); p = pre(q)
    for a in ASSETS:
        s, d = os.path.join(TPL, a), os.path.join(Q, a)
        if os.path.isdir(s):
            shutil.rmtree(d, ignore_errors=True); shutil.copytree(s, d)
        else: shutil.copy(s, d)
    old = json.load(open(os.path.join(Q, 'scene.json'))) if os.path.exists(os.path.join(Q, 'scene.json')) else {}
    n_up = sum(1 for h in HS['houses'] if h[2] <= last)
    st = {s['id']: s for s in fr['structures']}
    lms = []
    ZH = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'city', 'names_zh.json')))
    for k in list(HS['late']) + [s['id'] for s in fr['structures'] if s['id'] in R['names'] and s['id'] not in HS['late'] and s['geom'] == 'polygon']:
        s = st[k]; nm = R['names'].get(k) or ZH.get(k) or s['name']   # cs36：全城中文名表兜底
        story = R.get('stories', {}).get(k) or f"{nm}，建城 {s['built']} 年建成。"
        lms.append({'id': k, 'xy': s['xy'], 'name': nm, 'story': story, 'now': R.get('now', {}).get(k, {})})
    if not lms:   # cs36：框里一座地标也没有（海岸、墙外）——给街区本身一个落脚点，敲门卡的「最近地标」才不会落空
        lms.append({'id': 'homes_' + q, 'xy': [910, 1024], 'name': R['title'], 'story': R['hook'], 'now': {}})
    # 镜头起点：最后一个关键年住得最密的地方
    import collections
    g = collections.Counter((int(sum(h[4][0::2]) / 4 // 200), int(sum(h[4][1::2]) / 4 // 200)) for h in HS['houses'] if h[2] <= last < h[3])
    (gx, gy), _ = g.most_common(1)[0]; home = [gx * 200 + 100, gy * 200 + 100]
    tc = json.load(open(os.path.join(TPL, 'city.json')))
    city = {k: tc[k] for k in GENERIC}
    oc = json.load(open(os.path.join(Q, 'city.json'))) if os.path.exists(os.path.join(Q, 'city.json')) else {}
    city.update(roads=oc.get('roads', []), landmarks=lms, harbor_box=[-9999, -9999, -9990, -9990], coast_line=[[-9999, -9999], [-9999, -9990]])
    json.dump(city, open(os.path.join(Q, 'city.json'), 'w'), ensure_ascii=False)
    names = '、'.join(l['name'] for l in lms)
    link = R.get('link')
    lt = json.load(open(os.path.join(LIV, link, 'scene.json')))['title'] if link else ''
    sc = {'id': q, 'title': R['title'], 'intro': False, 'nodaph': True,
          'keys': [[k, f'{p}_af{k}.jpg', 'bare.jpg' if i == 0 else f'{p}_af{keys[i - 1]}.jpg'] for i, k in enumerate(keys)],
          'other': {'label': f'← 去{lt}', 'url': f'../{link}/'} if link else {'label': '← 回城东尖角', 'url': '../'},
          'home': home, 'shack': [0, 0], 'arian': [0, 0], 'ticker': R['ticker'], 'greet': '',
          'banner': f'<div style="font-size:13px;opacity:.7;letter-spacing:2px">{R["teaser"]}</div><h2 style="margin:8px 0 10px">{R["title"]}</h2>'
                    f'<div style="line-height:1.7">{names}。<br>{n_up:,} 栋房子，没有一笔是人画的。<br><b>{R["hook"]}</b></div>',
          'info': (f'房子、街道、公共建筑的位置和每栋房子建成、拆毁的年份，都来自安托萨历史引擎的底账。画面由 AI 依引擎底图绘制：建城 {"、".join(map(str, keys))} 年各一张，'
                  '街和房子由程序照底账一户一户排上街；中间的年份按每栋房子的建成年份长出来。整个街区由 make_quarter.py 一条命令从底账长出来，上线前过一遍自动验收。') if q in ('nangang', 'jinjiao') else
                  (f'房子、街道、公共建筑的位置和每栋房子建成、拆毁的年份，都来自安托萨历史引擎的底账。AI 只画地标：每座公共建筑画一次，全城共用，按底账的地基贴回去；建城 {"、".join(map(str, keys))} 年各一张底图，'
                  '沙地、水面、焦土、街和房子全由全城同一套规则照底账生成，所以街区之间接得上。整个街区由 make_quarter.py 一条命令从底账长出来，上线前过一遍自动验收。'),
          'paint': old.get('paint') or {'说明': 'repaint.py 照这个从 AI 原画还原每张年代画；原画在 tools/cs/factory/raw/<q>/'}}
    for k in ('walk', 'zones', 'zone_labels', 'street_layout', 'halls', 'hall_blocks'):
        if k in old: sc[k] = old[k]
    if old.get('next') and 'next' not in sc: sc['next'] = old['next']   # cs36：重长自己时别把下一块的链接丢了
    json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
    ip = os.path.join(Q, 'index.html'); h = open(ip).read()   # cs36：标签页标题跟街区走（模板里写死了南港）
    import re as _re; open(ip, 'w').write(_re.sub(r'<title>[^<]*</title>', f'<title>活着的安托萨 · {R["title"]}</title>', h, count=1))
    if link:   # 来回能走：对面街区的 next 指回来
        lp = os.path.join(LIV, link, 'scene.json'); L = json.load(open(lp))
        if not any((L.get(s) or {}).get('url') == f'../{q}/' for s in ('other', 'next')) and (L.get('next') or {}).get('url') not in [f'../{n}/' for n in os.listdir(LIV)]:   # cs36：对面已经链着别的街区就不抢（抢了会断链），交给验收报红
            L['next'] = {'label': f'去{R["title"]} →', 'url': f'../{q}/'}; json.dump(L, open(lp, 'w'), ensure_ascii=False)
    print('scene', q, len(lms), 'landmarks', n_up, 'houses to', last)


if __name__ == '__main__':
    main()
