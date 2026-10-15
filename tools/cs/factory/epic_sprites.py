#!/usr/bin/env python3
"""谭线交接 ②–⑨ 接进瓦片：拿谭线 epic_core.py（tools/cs/factory/tan/，原样，只改仓库路径与比例）当画师。
每个视图（谭线 render_* 的画框，或整条城墙/水道）在每个「画面会变的年份」画一遍，只画史诗建筑本身（不画地面、路、树、房子：那些瓦片自己有），
透明底，按世界坐标切成 level-0 瓦片（455 px），同一块内容不变就不另存。竞技场单独一层，按一天里的时刻分四种（谭线 ⑨ 赛车日：dawn/filling/race/dusk），不进底账。
年份全部读 world.json（phases / built / destroyed）；开工到完工之间逐年画（谭线 rising() 按进度升高）。
  输出 docs/living/tiles/ep/<file>.webp + tiles/ep.json：{"t": {"tx_ty": [[年, 文件或 null], …]}, "race": {"tx_ty": [[年, {时刻: 文件}], …]}}
  python3 tools/cs/factory/epic_sprites.py
——Hark（CS线）"""
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T = os.path.join(ROOT, 'docs', 'living', 'tiles'); M = json.load(open(os.path.join(T, 'meta.json')))
os.environ['EPIC_S'] = str(M['scale'])
sys.path.insert(0, os.path.join(HERE, 'tan'))
import epic_core as E
from PIL import Image, ImageDraw
from shapely.geometry import Point, box, Polygon, LineString
from shapely.ops import unary_union
import numpy as np
X0, Y0 = M['origin']; SC = M['scale']; TP = M['tile_px']; GX, GY = M['grid']; YMIN, YMAX = min(M['years']), max(M['years'])
ST = E.ST; INF = 9999
OUT = os.path.join(T, 'ep'); os.makedirs(OUT, exist_ok=True)

def apostles(c, Y):   # 谭线 render_apostles 里画圣使徒的那一段（原样搬出，去掉地面/路/房）
    E.baths(c, Y); E.open_cistern(c, Y, 'cistern_modestus')
    if Y < 11: return
    pg = c.poly_local(ST['church_apostles']['geom']['coords'])
    cen = pg.centroid; x0, y0, x1, y1 = pg.bounds; arm = (x1 - x0) / 2; thick = arm * 0.36
    c.d.polygon(c.T(pg.buffer(16, join_style=2).exterior.coords), fill=(208, 198, 176, 255))
    arms = [box(cen.x - arm, cen.y - thick, cen.x + arm, cen.y + thick), box(cen.x - thick, cen.y - arm, cen.x + thick, cen.y + arm)]
    mx, my = x1 + 2, cen.y   # CS 线：陵墓圆堂贴着东臂端头（谭线原在端头外 22 px，压到底账脚印外的房子）；半径 18→14
    E.shadow(c, unary_union(arms + [Point(mx, my).buffer(14, 24)]), 28)
    st, parts, fr = E.phase('church_apostles', Y); cross = unary_union(arms)
    if st == 'done':
        for g in sorted(arms, key=lambda g: -g.bounds[2] + g.bounds[0]): E.prism(c, g, 28, roof=(194, 98, 66), wall=(222, 206, 176), sh=False)
        E.dome(c, cen.x, cen.y, thick * 1.1, 28, drum=10)
    elif st == 'frame': E.site(c, cross.buffer(3), 111, 10, stones=True); E.rising(c, cross, 28, fr, 112); E.crane(c, cen.x, cen.y + 4, 44)
    else: E.site(c, cross.buffer(3), 111, 30)
    rot = Point(mx, my).buffer(14, 24)
    if st == 'done' or 'mausoleum' in parts: E.prism(c, rot, 22, roof=E.LEAD, wall=(220, 210, 190), ridge=False, sh=False); E.dome(c, mx, my, 13, 22)
    else: E.site(c, rot.buffer(2), 113, 8, stones=False); E.rising(c, rot, 22, fr, 114)
    E.people(c, pg.buffer(15).difference(pg.buffer(2)), 40, 9)

def horn(c, Y):   # 谭线 render_horn 的史诗部分
    E.harbor(c, 'harbor_prosphorion', Y, 6 if Y < 1 else 8, 401, land='s', lights=Y >= 1)
    E.harbor(c, 'harbor_neorion', Y, 12, 501, land='s')
    E.horrea(c, 'warehouse_horn', Y); E.horrea(c, 'horrea_troadensia', Y)
    tst, _, tfr = E.phase('tower_horn', Y); t = c.poly_local(ST['tower_horn']['geom']['coords']).buffer(3, join_style=2)
    if tst == 'site': E.site(c, t.buffer(4), 751, 8)
    elif tst == 'frame': E.rising(c, t, 34, tfr, 752, wall=(170, 150, 118))
    elif tst == 'done':
        E.prism(c, t, 34, roof=(190, 176, 146), wall=(170, 150, 118), ridge=False); x0, y0, x1, y1 = t.bounds
        for k in range(int((x1 - x0) / 3)): c.d.rectangle([(x0 + k * 3) * E.SS, (y0 - 37) * E.SS, (x0 + k * 3 + 1.6) * E.SS, (y0 - 34) * E.SS], fill=(190, 176, 146, 255))

def core(c, Y):   # 谭线 render_core 的史诗部分；竞技场另成一层（赛车日），梅塞柱廊 CS 线自己画
    if Y < 1: return
    E.cistern(c, Y); E.palace(c, Y)
    E.basilica(c, ST['church_peace']['geom']['coords'], Y, 'peace', atrium=True, roof_h=24, sid='church_peace')
    if Y >= 30: E.basilica(c, ST['church_megale']['geom']['coords'], Y, 'megale', atrium=True, roof_h=34, wonder=True, sid='church_megale')
    E.forum_founder(c, Y); E.milion(c, Y)

MOMENTS = {'dawn': (0.0, None), 'filling': (0.45, None), 'race': (1.0, 0.35), 'dusk': (0.12, None)}
def hippo(m):
    def f(c, Y):
        if E.phase('hippodrome', Y)[0] is None: return
        cr, lap = MOMENTS[m]; E.hippodrome(c, Y, crowd=cr, lap=lap)
    return f

def line_box(sid, pad=6):
    xs = [p[0] for p in ST[sid]['geom']['coords']]; zs = [p[1] for p in ST[sid]['geom']['coords']]
    return max(min(xs) - pad, X0), max(min(zs) - pad - 4, Y0), min(max(xs) + pad, X0 + GX * TP / SC), min(max(zs) + pad, Y0 + GY * TP / SC)

# 视图：(名字, 画框世界坐标, 画法, 管的结构)。城门、城门外教堂（谭线 west）整座在瓦片图外（x < 416），不画。
VIEWS = [
    ('core', (598, 436, 706, 512), core, ['cistern_founder', 'palace_great', 'church_peace', 'church_megale', 'forum_founder', 'col_founder', 'milion']),
    ('apostles', (437, 334, 485, 388), apostles, ['church_apostles', 'baths_constantius', 'cistern_modestus']),
    ('shore', (462, 486, 596, 536), lambda c, Y: [E.harbor(c, 'harbor_julian', Y, 15, 201), E.harbor(c, 'harbor_theodosius', Y, 9, 301)] + [E.horrea(c, k, Y) for k in ('granary_founder', 'horrea_theodosius', 'horrea_alexandrina')],
        ['harbor_julian', 'harbor_theodosius', 'granary_founder', 'horrea_theodosius', 'horrea_alexandrina']),
    ('gate', (396, 452, 444, 494), lambda c, Y: E.barracks(c, Y), ['barracks_gate']),
    ('horn', (598, 344, 676, 402), horn, ['harbor_prosphorion', 'harbor_neorion', 'warehouse_horn', 'horrea_troadensia', 'tower_horn']),
    ('aqueduct', line_box('aq_great', 30), lambda c, Y: [E.aqueduct(c, Y), E.nymphaeum(c, Y)], ['aq_great', 'aqb_middle', 'aqb_valley', 'nymphaeum_great']),
    ('forum_theo', (528, 420, 572, 452), lambda c, Y: [E.nymph_maius(c, Y), E.forum_theo(c, Y)], ['forum_theodosius', 'nymphaeum_maius']),
    ('wall', line_box('wall_founder', 8), lambda c, Y: E.city_wall(c, Y, c.poly_local(ST['gate_founder']['geom']['coords'])), ['wall_founder']),
]
RACE = [('hippo_' + m, (598, 436, 706, 512), hippo(m), ['hippodrome']) for m in MOMENTS]

def years_of(ids):
    ys = set()
    for k in ids:
        s = ST[k]; ph = s.get('phases') or []
        ys.add(max(YMIN, s['built'] if not ph else min(s['built'], ph[0]['year'])))
        if s.get('destroyed') is not None: ys.add(s['destroyed'])
        if ph:
            ys |= {p['year'] for p in ph}
            ys |= set(range(ph[0]['year'], max(p['year'] for p in ph)))   # 工期里逐年升高
    if 'aq_great' in ids:   # 暗渠埋地：渠线上的房子何年起、何年拆，那年就得重出一帧（否则旧帧的暗渠压在新房上）
        s = ST['aq_great']; t0 = min([s['built']] + [p['year'] for p in s.get('phases') or []])
        ys |= {y for h in houses_on_aq() for y in (h[0], h[1]) if y > t0}
    return sorted(y for y in ys if YMIN <= y <= YMAX)

def houses_on_aq():
    global AQH
    if AQH is None:
        import glob
        L = LineString([((x - X0) * SC, (z - Y0) * SC) for x, z in ST['aq_great']['geom']['coords']]).buffer(12)
        AQH = [h for f in glob.glob(os.path.join(T, 'vec', '*.json')) for h in json.load(open(f))['h']
               if not str(h[5]).startswith('epic') and len(h[3]) >= 8 and L.intersects(Polygon(list(zip(h[3][0:8:2], h[3][1:8:2])))) ]
    return AQH
AQH = None

CACHE = os.environ.get('EPIC_CACHE', '/workspace/work/raw/epic_cache'); os.makedirs(CACHE, exist_ok=True)
import inspect
BASE_H = hashlib.sha1(open(os.path.join(HERE, 'tan', 'epic_core.py'), 'rb').read() + open(os.path.join(ROOT, 'world.json'), 'rb').read()).digest()
def vkey(view):   # 缓存键 = 谭线画师 + 底账 + 这个视图自己的画框与画法源码（改一个视图只重画它）
    name, bx, fn, ids = view
    try: src = inspect.getsource(fn)
    except (OSError, TypeError): src = ''
    if name == 'apostles': src += inspect.getsource(apostles)
    return hashlib.sha1(BASE_H + repr((name, bx, ids)).encode() + src.encode()).hexdigest()[:8]
def render(view, Y):
    name, (x0, z0, x1, z1), fn, ids = view
    f = os.path.join(CACHE, f'{vkey(view)}_{name}_{Y}.png')   # 画一张要几十秒：落盘缓存，可分几趟、几个进程跑（--render i/n）
    if os.path.exists(f): return Image.open(f).convert('RGBA'), ((x0 - X0) * SC, (z0 - Y0) * SC)
    im, off = _render(view, Y); im.save(f); return im, off
def _render(view, Y):
    name, (x0, z0, x1, z1), fn, ids = view
    c = E.Canvas(x0, z0, x1, z1); E.ground(c, Y)            # ground 只为算出水面遮罩（港口切海面用）
    c.im = Image.new('RGBA', c.im.size, (0, 0, 0, 0)); c.d = ImageDraw.Draw(c.im, 'RGBA')
    fn(c, Y)
    im = c.im.resize((c.w, c.h), Image.LANCZOS)
    off = ((x0 - X0) * SC, (z0 - Y0) * SC)
    if name == 'aqueduct': im = bury(im, off, Y)
    return im, off

HOUSES = None
def bury(im, off, Y):
    """大水道地面段是封顶埋地的暗渠（底账：仅留检修井）：后来盖在渠线上的房子，那里不画暗渠（石拱桥和喷泉楼脚印里照画）"""
    global HOUSES
    if HOUSES is None:
        import glob
        HOUSES = [h for f in glob.glob(os.path.join(T, 'vec', '*.json')) for h in json.load(open(f))['h'] if not str(h[5]).startswith('epic') and len(h[3]) >= 8]
    keep = [Polygon([((x - X0) * SC - off[0], (z - Y0) * SC - off[1]) for x, z in ST[k]['geom']['coords']]).buffer(6) for k in ('aqb_outer', 'aqb_middle', 'aqb_valley', 'nymphaeum_great')]
    mk = Image.new('L', im.size, 0); d = ImageDraw.Draw(mk)
    for h in HOUSES:
        if not (h[0] <= Y < h[1]): continue
        pts = [(h[3][i] - off[0], h[3][i + 1] - off[1]) for i in range(0, 8, 2)]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > im.width or max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > im.height: continue
        d.polygon([(x, y - dy) for x, y in pts for dy in (0,)], fill=255); d.polygon([(x, y - 4) for x, y in pts], fill=255)   # 连同暗渠抬高的 2.5 px 立面
    for g in keep: d.polygon(list(g.exterior.coords), fill=0)
    a = np.asarray(im).copy(); a[..., 3] = np.where(np.asarray(mk) > 0, 0, a[..., 3])
    return Image.fromarray(a)

def tiles_of(layers):
    """layers: [(RGBA 图, (px, py))] → {(tx,ty): RGBA 455×455}，只留有内容的块"""
    out = {}
    for im, (px, py) in layers:
        a = np.asarray(im)[..., 3]
        if not a.any(): continue
        for ty in range(max(0, int(py // TP)), min(GY, int((py + im.height) // TP) + 1)):
            for tx in range(max(0, int(px // TP)), min(GX, int((px + im.width) // TP) + 1)):
                t = out.get((tx, ty)) or Image.new('RGBA', (TP, TP), (0, 0, 0, 0))
                t.alpha_composite(im, (int(round(px - tx * TP)), int(round(py - ty * TP)))) if False else t.paste(im, (int(round(px - tx * TP)), int(round(py - ty * TP))), im)
                out[(tx, ty)] = t
    return {k: v for k, v in out.items() if np.asarray(v)[..., 3].max() > 8}

SAVED = {}
def save(t):
    a = np.asarray(t); h = hashlib.sha1(a.tobytes()).hexdigest()[:12]
    if h not in SAVED:
        f = h + '.webp'; t.save(os.path.join(OUT, f), 'WEBP', quality=82, method=6); SAVED[h] = f
    return SAVED[h]

def bake(views):
    """→ {tile: [[年, 文件|None], …]}：每个年份把所有视图在该年的画面合起来；同一块与上一年相同就不记"""
    YS = sorted({y for v in views for y in years_of(v[3])}); cache = {}; idx = {}; last = {}
    for Y in YS:
        layers = []
        for v in views:
            vy = [y for y in years_of(v[3]) if y <= Y]
            if not vy: continue
            k = vy[-1]
            if cache.get(v[0], (None,))[0] != k: cache[v[0]] = (k, render(v, k))   # 每个视图只留当前那一年（全留会吃光 7 GB 内存）
            layers.append(cache[v[0]][1])
        tl = tiles_of(layers)
        for key in set(tl) | set(last):
            f = save(tl[key]) if key in tl else None
            if last.get(key) != f: idx.setdefault(f'{key[0]}_{key[1]}', []).append([Y, f]); last[key] = f
        print(Y, len(tl), 'tiles', flush=True)
    return idx

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--render':   # 只把第 i 份（共 n 份）视图×年份画进缓存
        i, n = map(int, sys.argv[2].split('/')); jobs = [(v, y) for v in VIEWS + RACE for y in years_of(v[3])]
        for j, (v, y) in enumerate(jobs):
            if j % n == i: render(v, y); print(v[0], y, flush=True)
        sys.exit(0)
    for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
    base = bake(VIEWS)
    race = {}
    for m in MOMENTS:
        for k, seq in bake([v for v in RACE if v[0] == 'hippo_' + m]).items():
            for y, f in seq:
                ent = next((e for e in race.setdefault(k, []) if e[0] == y), None)
                if not ent: ent = [y, {}]; race[k].append(ent)
                ent[1][m] = f
    for k in race: race[k].sort(key=lambda e: e[0])
    D = {'src': 'tools/cs/factory/epic_sprites.py（谭线 epic_core.py，handoff-cs ②–⑨）', 'tile_px': TP, 'views': {v[0]: v[3] for v in VIEWS}, 'moments': {'dawn': [0, 8], 'filling': [8, 11], 'race': [11, 17], 'dusk': [17, 21]}, 't': base, 'race': race}
    json.dump(D, open(os.path.join(T, 'ep.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    n = len(os.listdir(OUT)); b = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print('files', n, 'bytes', b, 'base tiles', len(base), 'race tiles', len(race))
