#!/usr/bin/env python3
"""/goal 4 项 7（G6）：把刘线户籍旁车（liu/main experiments/city_system_v6/tiles_join/reg/{40,50,60}/）按我们瓦片重新装箱，写 docs/living/tiles/reg/。
刘线的旁车是按他们当时对接的瓦片分文件的，房子有抖动，约 8% 的户落在邻块文件里；我们的 vec 里每栋房带底账 id（h[5]），
所以这里按 id 取刘线的记录（内容一字不改），装进这栋房所在的 vec 瓦片的文件，只装那一年站着、且刘线有记录的户。
用法：python3 tools/cs/factory/reg_pack.py [刘线旁车目录]（默认从 git 的 liu/main 取）；瓦片重烤后要重跑。
——Hark（CS线）"""
import json, os, re, sys, glob, subprocess, tempfile, shutil, tarfile, io
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T = os.path.join(ROOT, 'docs', 'living', 'tiles'); OUT = os.path.join(T, 'reg')
src = sys.argv[1] if len(sys.argv) > 1 else None
if not src:
    tmp = tempfile.mkdtemp(); p = subprocess.run(['git', '-C', ROOT, 'archive', 'liu/main', 'experiments/city_system_v6/tiles_join/reg'], capture_output=True, check=True)
    tarfile.open(fileobj=io.BytesIO(p.stdout)).extractall(tmp); src = os.path.join(tmp, 'experiments/city_system_v6/tiles_join/reg')
TP = json.load(open(os.path.join(T, 'meta.json')))['tile_px']
F = ['id', 'd', 'fang', 'parish', 'water', 'watch', 'guild', 'office']; rec = {}
for Y in (40, 50, 60):
    m = rec[Y] = {}
    for f in glob.glob(os.path.join(src, str(Y), '*.json')):
        d = json.load(open(f)); assert d['f'] == F and d['Y'] == Y
        for r in d['h']:
            if r and len(r) == 8: m[r[0]] = r
vec = {}
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    k = os.path.basename(f)[:-5]
    for h in json.load(open(f))['h']:
        lid = h[5] if len(h) > 5 else None
        if isinstance(lid, str) and re.fullmatch(r'h\d+', lid):
            vec.setdefault(k, []).append((lid, h[0], h[1]))
            # 页面按房子的平面中心（前 4 点）算瓦片，vec 按 8 点（含影子）的中心分块，两者在瓦片边上可差一块：平面中心 ±1.5 px 所在的瓦片也装一份
            o = h[3]; cx = sum(o[0:8:2]) / 4; cy = sum(o[1:8:2]) / 4
            for dx in (-1.5, 0, 1.5):
                for dy in (-1.5, 0, 1.5):
                    kk = '%d_%d' % (int((cx + dx) // TP), int((cy + dy) // TP))
                    if kk != k: vec.setdefault(kk, []).append((lid, h[0], h[1]))
shutil.rmtree(OUT, ignore_errors=True); n = nb = 0
for Y in (40, 50, 60):
    os.makedirs(os.path.join(OUT, str(Y)), exist_ok=True)
    for k, hs in vec.items():
        rows = list({lid: rec[Y][lid] for lid, b, e in hs if b <= Y < e and lid in rec[Y]}.values())
        if not rows: continue
        b = json.dumps({'Y': Y, 'f': F, 'h': rows}, ensure_ascii=False, separators=(',', ':')).encode(); open(os.path.join(OUT, str(Y), k + '.json'), 'wb').write(b); n += 1; nb += len(b)
open(os.path.join(OUT, 'SOURCE.md'), 'w', encoding='utf8').write('''# 户籍旁车 reg/{40,50,60}/{tx}_{ty}.json

来源：刘线（liuzhijie820802-a11y/anthousa-liuzhijie）liu/main 8034184，experiments/city_system_v6/tiles_join/reg/；记录内容一字未改。
由刘线 city_system v6 按 world.json 生成（区、教区、供水组由账本推出；坊、哨、职务是刘线的模型假设）。
装箱：tools/cs/factory/reg_pack.py 按我们瓦片 vec 里每栋房的底账 id（h[5]）重新分文件，只装那一年站着且刘线有记录的户。
CS 瓦片页只在敲门卡点开时才懒取这栋房所在瓦片的一个文件，按 id 找这户；找不到的房子不显示这一行。
''')
print(f'reg 旁车：{n} 个文件，{nb/1e6:.2f} MB（来源 {sum(len(v) for v in rec.values())} 条）')
