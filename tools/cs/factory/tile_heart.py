"""CS 线 · /goal 2 项 4：把街区页的心跳（粮船日、家户推演）原样搬到瓦片页。python3 tile_heart.py <q>
  不重写：从 docs/living/<q>/index.html 里按标记剪出这几段，一字不改，包进一个函数，写成
  docs/living/tiles/heart/<q>.js（浏览器按需载入，进街区才下）：
    ① 工具（hash/rng/pick/clamp/dist）② 港框、陆海、地标表 ③ 房子与 nearestHouse ④ 家户推演（household/famAt/aliveAt）⑤ cs6 粮船日（FLEET）
  这样街区页上验过的东西（人走网、船走水路、敲门卡话、邻居不重样）在瓦片页里是同一份代码。
  外壳只做三件事：把街区页的全局（SCENE/PPL/houses/…）换成传进来的；ctx 用代理，指向瓦片页当前的画布；时钟由瓦片页给。
  街区页改了这几段，重跑本脚本即可。——Hark（CS线）"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
q = sys.argv[1] if len(sys.argv) > 1 else 'nangang'
src = open(os.path.join(ROOT, 'docs/living', q, 'index.html'), encoding='utf-8').read()
def cut(a, b, incl_b=False):
    i = src.index(a); j = src.index(b, i + len(a)); return src[i:j + (len(b) if incl_b else 0)]
UT = cut('function hash(s)', 'const HB=')
GEO = cut('const HB=', '/* ---------- houses ---------- */')
HOU = cut('const MAXY=60;', 'const late=HD.late;')
HH = cut('const NM=', 'function relLabel')
FL = cut('/* ---------- CS 线 · cs6 粮船日', '/* cs16 · backlog 3')
has_fleet = 'SCENE.fleet' in FL
# 街区页的 houseById 是线性查找，这里加索引
body = f'''
/* 以下五段取自 docs/living/{q}/index.html，一字不改（tile_heart.py 生成）。——Hark（CS线） */
const {{city,HD,SCENE,PPL,pplImg,cam}}=env;const W=1820,H=2048;
const ctx=new Proxy({{}},{{get:(_,k)=>{{const c=env.ctx(),v=c[k];return typeof v==='function'?v.bind(c):v}},set:(_,k,v)=>{{env.ctx()[k]=v;return true}}}});
let YEAR=60,clock=6.0,tkT=0;const $=id=>env.$(id);const smokes=[];const COLS=['#c98b3a','#9b3b2a','#d8cbb0','#3d5a80','#6b5a3a','#e0dccf','#7a4a6a'];
{UT}
{GEO}
{HOU}
{HH}
const _hid=new Map(houses.map(h=>[h.id,h]));function houseById(id){{return _hid.get(id)}}
{FL}
FLEET&&(FLEET.dockDraw=function(){{}});   /* 码头逐年长的遮盖：瓦片页的烤图已经按年画好 */
return {{houses,city,SCENE,household,famAt,aliveAt,
  get FLEET(){{return FLEET}},get YEAR(){{return YEAR}},set YEAR(v){{YEAR=v}},get clock(){{return clock}},set clock(v){{clock=v}},get dayIdx(){{return dayIdx}},set dayIdx(v){{dayIdx=v}},
  FW:W,FH:H,hash,rng}};
'''
os.makedirs(os.path.join(ROOT, 'docs/living/tiles/heart'), exist_ok=True)
out = os.path.join(ROOT, 'docs/living/tiles/heart', q + '.js')
open(out, 'w', encoding='utf-8').write(f'/* CS 线 · tile_heart.py 生成，勿手改 */\n(window.__HEART=window.__HEART||{{}}).{q}=function(env){{"use strict";{body}}};\n')
print(out, os.path.getsize(out), 'bytes', 'fleet' if has_fleet else 'no fleet')
