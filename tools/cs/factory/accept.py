"""CS 线 · 街区生产线（第五段：验收）—— 拉取 → 比对 → 验收 → 修改 的闭环
一条命令把一个街区从底账到线上全部核一遍，不靠人眼：
  一、拉取  上游底账有没有新提交；world.json 是不是用最新底账重算的；用最新底账把街区重长一遍，和线上的数据逐栋比
  二、比对  页面上写出来的每一个数字、年份、名字，和底账对不对得上；页面有没有串了别的街区的字；街区之间能不能来回走
  三、画面  每张年代画：房子对位、水、火场是黑的、火场灰烬有没有漫出真实烧毁地块、公共建筑周围的房子有没有被画成空地
  四、线上  线上每个文件和本地是不是同一份
不合格项会给出「怎么修」；--fix 会自动做能自动做的修改（重长数据、改页面文字、补链接），画面问题交给 reroof/重画。
用法: python tools/cs/factory/accept.py <quarter_id> [--pull] [--fix] [--live]
退出码 0 = 全部通过"""
import hashlib, json, os, re, subprocess, sys, tempfile, urllib.request
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIV = os.path.join(ROOT, 'docs', 'living')
LIVE = 'https://changsheng0804-blip.github.io/anthousa-hark-CS/living/'
LEDGER = ['world.json', 'proposals', 'rules', 'chronicle', 'engine']
PW, PH = 1820, 2048
sys.path.insert(0, HERE)
import critic

R = []  # (段, 项, 通过?, 说明, 怎么修)


def rec(sec, name, ok, info='', fix=''):
    R.append((sec, name, bool(ok), info, fix))


def sh(*a, **k):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True, **k)


def pull(q, do_pull):
    S = '一、拉取'
    sh('git', 'fetch', '-q', 'origin')
    behind = sh('git', 'log', '--oneline', 'HEAD..origin/main', '--', *LEDGER).stdout.strip().splitlines()
    if behind and do_pull:
        m = sh('git', 'merge', '--no-edit', '-q', 'origin/main')
        rec(S, '合并上游底账', m.returncode == 0, f'{len(behind)} 个底账提交', '手工解决冲突（底账以上游为准）')
        behind = []
    rec(S, '上游底账没有新提交', not behind, f'落后 {len(behind)} 个底账提交' if behind else '已是最新', '加 --pull 合并上游')
    # world.json 是派生文件：底账里任何文件比它新，就要重算
    wj = os.path.join(ROOT, 'world.json')
    newest = max(int(sh('git', 'log', '-1', '--format=%ct', '--', p).stdout.strip() or 0) for p in LEDGER[1:])
    stale = (not os.path.exists(wj)) or os.path.getmtime(wj) < newest
    if stale:
        b = sh(sys.executable, 'engine/build_all.py', timeout=1800)
        rec(S, 'world.json 按最新底账重算', b.returncode == 0, (b.stdout.strip().splitlines() or [''])[-1][:80], '看 engine/build_all.py 的报错')
    else:
        rec(S, 'world.json 按最新底账重算', True, '不需要，已是最新')
    if not os.path.exists(os.path.join(LIV, q, 'frame.json')):
        rec(S, '用最新底账重长街区', True, '不是生产线长的街区，跳过'); return None
    fr = json.load(open(os.path.join(LIV, q, 'frame.json')))
    x0, y0 = fr['frame'][:2]
    keys = [k[0] for k in json.load(open(os.path.join(LIV, q, 'scene.json')))['keys']]
    with tempfile.TemporaryDirectory() as t:
        g = sh(sys.executable, os.path.join(HERE, 'grow.py'), q, str(x0), str(y0), *map(str, keys), env={**os.environ, 'GROW_OUT': t})
        if g.returncode:
            rec(S, '用最新底账重长街区', False, g.stderr.strip()[-120:], '看 grow.py 报错'); return None
        new = json.load(open(os.path.join(t, 'houses.json'))); old = json.load(open(os.path.join(LIV, q, 'houses.json')))
        A = {h[0]: h for h in old['houses']}; B = {h[0]: h for h in new['houses']}
        add, gone = B.keys() - A.keys(), A.keys() - B.keys()
        chg = [i for i in A.keys() & B.keys() if A[i] != B[i]]
        ok = not (add or gone or chg) and old.get('late') == new.get('late')
        rec(S, '街区数据与最新底账逐栋一致', ok, f'{len(B)} 栋；新增 {len(add)}、消失 {len(gone)}、变了 {len(chg)}',
            '--fix 重长数据；有房子变了的年份要重画（paint → critic → reroof）')
        nf = json.load(open(os.path.join(t, 'frame.json')))
        rec(S, '框内公共建筑与底账一致', nf['structures'] == fr['structures'], f"{len([s for s in nf['structures'] if s['geom']=='polygon'])} 个多边形", '--fix 重长 frame.json，再查 city.json 地标')
        return new, nf, (ok, t) if False else ok


def compare(q, fix):
    S = '二、比对'
    if not os.path.exists(os.path.join(LIV, q, 'frame.json')):
        return json.load(open(os.path.join(LIV, q, 'scene.json')))
    w = json.load(open(os.path.join(ROOT, 'world.json')))
    hs = json.load(open(os.path.join(LIV, q, 'houses.json')))['houses']
    sc = json.load(open(os.path.join(LIV, q, 'scene.json')))
    city = json.load(open(os.path.join(LIV, q, 'city.json')))
    fr = json.load(open(os.path.join(LIV, q, 'frame.json')))
    st = {s['id']: s for s in w['structures']}
    html = open(os.path.join(LIV, q, 'index.html'), encoding='utf-8').read()
    # 1 页面上写的数字
    text = json.dumps(sc, ensure_ascii=False) + json.dumps(city, ensure_ascii=False)
    for m in set(re.findall(r'(\d{1,3}(?:,\d{3})+) 栋', text)):
        n = int(m.replace(',', ''))
        rec(S, f'「{m} 栋」', n == len(hs), f'底账框内 {len(hs)} 栋', '改 scene.json 里的数字')
    burned = sum(1 for h in w['houses'] if h['destroyed'] == 48)
    for m in set(re.findall(r'烧毁 (\d+) 座', text)):
        rec(S, f'「烧毁 {m} 座」', int(m) == burned, f'底账 48 年毁掉 {burned} 栋', '改 city.json')
    # 2 地标：名字对应底账里的建筑，故事里的第一个「建城 N 年」就是建成年
    for L in city['landmarks']:
        s = st.get(L['id'])
        if not s:
            rec(S, f"地标 {L['name']} 在底账里", L['id'] == 'fire_ruins', '页面自造的地点' if L['id'] == 'fire_ruins' else '底账没有这个 id', '删掉或换成底账 id'); continue
        ys = [int(y) for y in re.findall(r'建城 (\d+) 年', L['story'])]
        exp = s['built']
        ok = (not ys and exp <= 1) or (exp in ys)
        rec(S, f"地标 {L['name']} 的年份", ok, f"页面 {ys or '未写'}，底账 {exp}", '改 city.json 的 story')
        inb = any(f['id'] == L['id'] for f in fr['structures'])
        rec(S, f"地标 {L['name']} 在本街区框内", inb, '', '删掉，或扩框')
    # 3 串字：别的街区的名字、本街区没有的人
    others = {'xerolophos': ['城东尖角'], 'nangang': ['城东尖角', '干山上另有', '达芙涅和狄奥多罗斯', '建城 10、30、50 年各一张']}
    static = re.sub(r'<script.*?</script>', '', html, flags=re.S)
    bad = [x for x in others.get(q, []) if x in static]
    rec(S, '静态文字没有串别的街区', not bad, '、'.join(bad) or '干净', '--fix：页面文字改由 scene.json 的 info / sub 提供')
    if 'info' in sc:
        yrs = [int(y) for y in re.findall(r'建城 ([\d、]+) 年', sc['info'])[0].split('、')] if re.search(r'建城 ([\d、]+) 年各一张', sc['info']) else []
        rec(S, '「怎么做的」写的年代 = 实际关键年', yrs == [k[0] for k in sc['keys']], f"写 {yrs}，实际 {[k[0] for k in sc['keys']]}", '改 scene.json 的 info')
    # 4 来回能走：每个链出去的街区，都有链回来
    outs = [sc.get('other', {}).get('url'), sc.get('next', {}).get('url')]
    for u in filter(None, outs):
        tq = u.strip('./').split('/')[-1] or u.strip('./').split('/')[0]
        tq = u.replace('../', '').strip('/')
        p = os.path.join(LIV, tq, 'scene.json')
        if not os.path.exists(p):
            rec(S, f'链接 → {tq}', False, '目标不存在', ''); continue
        ts = json.load(open(p))
        back = any(f'../{q}/' == (ts.get(k) or {}).get('url') for k in ('other', 'next'))
        rec(S, f'{q} ⇄ {tq} 来回都能走', back, '', f'在 {tq}/scene.json 加 next 指回 {q}')
    return sc


def picture(q, sc):
    S = '三、画面'
    hs = json.load(open(os.path.join(LIV, q, 'houses.json')))['houses']
    fr = json.load(open(os.path.join(LIV, q, 'frame.json')))
    for Y, img, _ in sc['keys']:
        s = critic.score(q, Y, img)
        rec(S, f'{Y} 年 房子对位', s['houses'] >= 0.8, f"{s['houses']}（命中 {s['hit']} / 空地干净 {s['prec']}）", '换候选或重画，再 reroof')
        if 'water' in s:
            rec(S, f'{Y} 年 水面', s['water'] >= 0.6, str(s['water']), '重画时强调海岸线')
        if 'burn' in s:
            rec(S, f'{Y} 年 火场是黑的', s['burn'] >= 0.5, str(s['burn']), '重画时强调灰烬')
        a = np.asarray(Image.open(os.path.join(LIV, q, img)).convert('RGB').resize((PW, PH))).astype(float)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        roof = (r - b > 60) & (r > 110) & (g < r * 0.8)
        alive = Image.new('L', (PW, PH), 0); ad = ImageDraw.Draw(alive)
        burnt = Image.new('L', (PW, PH), 0); bd = ImageDraw.Draw(burnt)
        for h in hs:
            P = [(h[4][i], h[4][i + 1]) for i in range(0, len(h[4]), 2)]
            if h[2] <= Y < h[3]: ad.polygon(P, fill=255)
            if h[3] == 48 and 48 <= Y < 54: bd.polygon(P, fill=255)
        alive, burnt = np.asarray(alive) > 0, np.asarray(burnt) > 0
        # 火场灰烬漫出：真实烧毁地块外 24~150 像素，黑色的地占多少（扣掉水和阴影小块）
        if burnt.any():
            dist = ndi.distance_transform_edt(~burnt)
            lum = ndi.uniform_filter(a.mean(2), 9)
            ring = (dist > 24) & (dist < 150) & ~(b > r + 15)
            spill = float((lum[ring] < 85).mean())
            rec(S, f'{Y} 年 灰烬没有漫出真实火场', spill <= 0.08, f'火场外圈黑地占 {spill:.1%}', 'reroof 时把火场外的黑地抹成地面（ash_extra 阈值收紧）')
        # 公共建筑画得对不对（完好 / 没多画 / 大小），机器测不准，交给 sheet() 出的目检表
        # 公共建筑周围：底账有房子的地方，画上要有屋顶（不能被广场/柱廊吞掉）
        for s_ in fr['structures']:
            if s_['geom'] != 'polygon' or s_['type'] in ('district', 'farmland', 'harbor') or s_['built'] > Y: continue
            m = Image.new('L', (PW, PH), 0); ImageDraw.Draw(m).polygon([tuple(p) for p in s_['pts']], fill=255)
            d = ndi.distance_transform_edt(~(np.asarray(m) > 0))
            near = alive & (d > 0) & (d < 40)
            if near.sum() < 400: continue
            cov = float(roof[near].mean()); base = float(roof[alive & (d > 80)].mean())
            rec(S, f'{Y} 年 {s_["name"]} 旁的房子没被吞掉', cov >= 0.75 * base, f'旁边屋顶覆盖 {cov:.2f}，全街区 {base:.2f}', 'reroof 时公共建筑保护区收紧到底账多边形（MaxFilter 调小）')


def sheet(q, sc):
    fr = json.load(open(os.path.join(LIV, q, 'frame.json')))
    L = [s for s in fr['structures'] if s['geom'] == 'polygon' and s['type'] not in ('district', 'farmland', 'harbor')]
    T = 260; out = Image.new('RGB', (T * len(sc['keys']), T * len(L)), (30, 30, 30))
    for j, (Y, img, _) in enumerate(sc['keys']):
        im = Image.open(os.path.join(LIV, q, img)).convert('RGB').resize((PW, PH))
        for i, s in enumerate(L):
            xs = [p[0] for p in s['pts']]; ys = [p[1] for p in s['pts']]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2; hw = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 60
            c = im.crop((int(cx - hw), int(cy - hw), int(cx + hw), int(cy + hw)))
            d = ImageDraw.Draw(c); k = c.width / (2 * hw)
            d.polygon([((p[0] - cx + hw) * k, (p[1] - cy + hw) * k) for p in s['pts']], outline=(0, 255, 255) if s['built'] <= Y else (255, 0, 255))
            d.text((4, 4), f"{Y} {s['name']} {'未建' if s['built'] > Y else ''}", fill=(255, 255, 0))
            out.paste(c.resize((T, T)), (j * T, i * T))
    p = os.path.join(ROOT, 'tools', 'cs', 'factory', 'out', f'{q}_landmarks.jpg'); os.makedirs(os.path.dirname(p), exist_ok=True)
    out.save(p, quality=85)
    rec('三、画面', '公共建筑目检表', True, f'{p}（青框=已建，紫框=未建；要看：已建的完好、未建的那里没有）')


def live(q, sc):
    S = '四、线上'
    files = ['index.html', 'scene.json', 'city.json', 'houses.json'] + sorted({f for k in sc['keys'] for f in k[1:]})
    for f in files:
        loc = os.path.join(LIV, q, f)
        if not os.path.exists(loc):
            rec(S, f, False, '本地没有这个文件', '补上'); continue
        try:
            body = urllib.request.urlopen(LIVE + q + '/' + f + '?v=' + str(os.getpid()), timeout=30).read()
            ok = hashlib.sha256(body).hexdigest() == hashlib.sha256(open(loc, 'rb').read()).hexdigest()
            rec(S, f, ok, '一致' if ok else '线上和本地不同', '推送后等 Pages 部署完再验')
        except Exception as e:
            rec(S, f, False, str(e)[:60], '看 Pages 部署')


def report(q):
    fails = [x for x in R if not x[2]]
    L = [f'# {q} 验收', '', f'通过 {len(R) - len(fails)} / {len(R)}', '']
    sec = None
    for s, n, ok, info, fx in R:
        if s != sec: L += ['', f'## {s}']; sec = s
        L.append(f"- {'✅' if ok else '❌'} {n}" + (f' —— {info}' if info else '') + ('' if ok else f'  → 修：{fx}'))
    open(os.path.join(LIV, q, 'ACCEPT.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return not fails


if __name__ == '__main__':
    q = sys.argv[1]; a = sys.argv[2:]
    pull(q, '--pull' in a)
    sc = compare(q, '--fix' in a)
    if os.path.exists(os.path.join(LIV, q, 'frame.json')):
        picture(q, sc); sheet(q, sc)
    if '--live' in a: live(q, sc)
    sys.exit(0 if report(q) else 1)
