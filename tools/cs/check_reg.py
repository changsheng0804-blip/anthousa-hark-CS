#!/usr/bin/env python3
"""/goal 4 G6 检查：刘线户籍旁车（reg）进敲门卡——资产与对接部分。页面行为见 check_reg.js。
 ① tiles/reg/{40,50,60}/{tx}_{ty}.json 都在（取自刘线 liu/main experiments/city_system_v6/tiles_join/reg，原样），旁边有 SOURCE.md 注明来源；
 ② 每块旁车的 f 字段顺序是 id,d,fang,parish,water,watch,guild,office，h 条目要么 null、要么 [id]（那一年不在世）、要么 8 项；
 ③ 对接：瓦片 vec 里带底账 id 的房子（h[5] = 'h数字'，那一年站着的），在同块同年旁车里按 id 找得到的比例 ≥ 85%（找不到的敲门卡就不显示这一行）；
 ④ 区、教区在页面的中文名表里都有（不然卡上会露出 d_xxx 这种代号）；
 ⑤ 体积：旁车 gzip 后 ≤ 0.5 MB、整个 tiles 目录 ≤ 80 MB（G7）。
——Hark（CS线）"""
import json, os, sys, glob, re, gzip
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
T = os.path.join(ROOT, 'docs', 'living', 'tiles'); R = os.path.join(T, 'reg'); bad = []
def need(c, m):
    if not c: bad.append(m)
need(os.path.exists(os.path.join(R, 'SOURCE.md')), '没有 tiles/reg/SOURCE.md（来源注明）')
if os.path.exists(os.path.join(R, 'SOURCE.md')):
    s = open(os.path.join(R, 'SOURCE.md'), encoding='utf8').read(); need('刘线' in s and 'liu/main' in s, 'SOURCE.md 没写刘线 / liu/main')
F = ['id', 'd', 'fang', 'parish', 'water', 'watch', 'guild', 'office']
side = {}; zraw = 0; zgz = 0; ds = set(); ps = set()
for Y in (40, 50, 60):
    fs = glob.glob(os.path.join(R, str(Y), '*.json')); need(len(fs) >= 50, f'reg/{Y} 只有 {len(fs)} 个文件')
    for f in fs:
        b = open(f, 'rb').read(); zraw += len(b); zgz += len(gzip.compress(b)); d = json.loads(b)
        need(d.get('f') == F and d.get('Y') == Y, f'{f} 字段/年份不对')
        k = os.path.basename(f)[:-5]; m = {}
        for r in d['h']:
            need(r is None or (isinstance(r, list) and len(r) in (1, 8)), f'{f} 条目形状不对')
            if r and len(r) == 8:
                m[r[0]] = r; ds.add(r[1])
                for p in (r[3] if isinstance(r[3], list) else [r[3]]): ps.add(p)
        side[(Y, k)] = m
need(zgz <= 0.5e6, f'旁车 gzip {zgz/1e6:.2f} MB > 0.5 MB')
# ③ 对接
tot = hit = 0
for f in glob.glob(os.path.join(T, 'vec', '*.json')):
    k = os.path.basename(f)[:-5]; d = json.load(open(f))
    for h in d['h']:
        lid = h[5] if len(h) > 5 else None
        if not (isinstance(lid, str) and re.fullmatch(r'h\d+', lid)): continue
        for Y in (40, 50, 60):
            if h[0] <= Y < h[1]:
                tot += 1; hit += lid in side.get((Y, k), {})
cov = hit / max(1, tot); need(tot > 5000 and cov >= .85, f'按 id 对上 {hit}/{tot} = {cov:.1%}（要 ≥85%）')
# ④ 中文名
html = open(os.path.join(T, 'index.html'), encoding='utf8').read()
for v in sorted(ds | ps): need(("'%s'" % v in html) or (v + ':') in html, f'页面没有 {v} 的中文名')
# ⑤ 体积
tot_b = sum(os.path.getsize(os.path.join(dp, n)) for dp, _, ns in os.walk(T) for n in ns)
need(tot_b <= 80e6, f'tiles 总量 {tot_b/1e6:.1f} MB > 80 MB')
print(f'旁车：{len(side)} 块，原始 {zraw/1e6:.2f} MB / gzip {zgz/1e6:.2f} MB；按 id 对上 {hit}/{tot} = {cov:.1%}；tiles 总量 {tot_b/1e6:.1f} MB')
print('\n'.join(bad) or '✅ 全过'); sys.exit(1 if bad else 0)
