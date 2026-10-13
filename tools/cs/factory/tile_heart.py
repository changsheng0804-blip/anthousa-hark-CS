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
# 性能：FLEET.crowd(Y) 每年第一次要 ~300 ms（逐户找路 + 栈桥配人），整块卡一帧。逻辑一字不改，只把函数改成生成器、在两个大循环头上各放一个 yield，
# 页面每帧给 ~4 ms 慢慢算；街区页、验收用的同步 FLEET.crowd(Y) 照旧（把生成器一口气跑完）。
_h = "FLEET.crowd=function(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const r="
assert _h in FL and "for(const h of hs){const hh=household(h);" in FL and "for(const m of pool){const t=" in FL and "FLEET.cache[Y]=R;return R};" in FL, 'fleet_day 原文变了，tile_heart 要跟着改'
FL = FL.replace(_h, "FLEET.crowdGen=function*(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const r=")
FL = FL.replace("for(const h of hs){const hh=household(h);", "for(const h of hs){yield;const hh=household(h);")
FL = FL.replace("for(const m of pool){const t=", "for(const m of pool){yield;const t=")
_b = "for(let qi=0;qi<Q2.length&&!found&&qi<40000;qi++){const[a,b]=Q2[qi];"
assert _b in FL
FL = FL.replace(_b, "for(let qi=0;qi<Q2.length&&!found&&qi<40000;qi++){if(qi%1200===0)yield;const[a,b]=Q2[qi];")
FL = FL.replace("FLEET.cache[Y]=R;return R};", "FLEET.cache[Y]=R;return R};\n  FLEET.crowd=function(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const g=FLEET.crowdGen(Y);let s;while(!(s=g.next()).done);return s.value};",1)
# ── 项 4b：敲门卡。同样原样剪：今日一句(todayFor)、分区名、时辰、renderCard 整个、cs1 敲门问话、cs2 跟一个人走一生。
#    只有三处不是原文：点击处理（街区页挂在 document 上，这里改成函数 cardClick，逻辑逐行照抄）、showCard/openHouse/closeCard（换成瓦片页的卡片 DOM）、
#    blip/flyTo/setYear（换成瓦片页的相机）。
TD = cut('const TODAY_HILL=', 'const IM=')
ZN = cut('const ZNAME=', 'function drawZoneLabels')
PO = cut('function periodOf', '\n') 
RL = cut('function relLabel', 'function periodOf')
RC = cut('function tiePos', '/* ---------- CS 线 · cs1')
C1 = cut('/* ---------- CS 线 · cs1', 'document.addEventListener(\'click\',e=>{const t=e.target.closest')
C1 = re.sub(r"window\.__cs=\{[^\n]*\n", "", C1)
C2 = cut('/* ---------- CS 线 · cs2', 'setTimeout(()=>{try{csIncoming()')
CARD = '\n'.join([TD, ZN, PO, RL, RC, C1, C2])
# 性能：csIncoming 一口气要 ~250 ms（全部家户 + 逐个配婚）。逻辑一字不改，只把两个循环切成可以分帧做的片（页面每帧给 ~4 ms），卡片需要时仍可一口气做完（csIncoming() 照旧返回完整结果）。
_old = "function csIncoming(){if(CSIN)return CSIN;CSIN={};const all=[];for(const o of houses){if(o.built>MAXY)continue;const hh=household(o);hh.people.forEach((p,i)=>{if(typeof p.to==='number')all.push([o,p,i])})}all.sort((a,b)=>a[1].left-b[1].left);for(const [o,p,i] of all){const sp=csSpouse(p);if(sp){(CSIN[sp.hid]=CSIN[sp.hid]||[]).push({from:o.id,pi:i});CSHUS.set(sp.hus,{p,from:o})}}return CSIN}"
assert _old in CARD, 'csIncoming 原文变了，tile_heart 要跟着改'
_new = "let CSST=null;function csIncoming(){csIncStep(1e9);return CSIN}\nfunction csIncStep(ms){if(CSIN&&!CSST)return true;const t0=performance.now();if(!CSST){CSIN={};CSST={all:[],hi:0,i:0,sorted:false}}const S=CSST;\n  while(S.hi<houses.length){const o=houses[S.hi++];if(o.built>MAXY)continue;const hh=household(o);hh.people.forEach((p,i)=>{if(typeof p.to==='number')S.all.push([o,p,i])});if(performance.now()-t0>ms)return false}\n  if(!S.sorted){S.all.sort((a,b)=>a[1].left-b[1].left);S.sorted=true}\n  while(S.i<S.all.length){const [o,p,i]=S.all[S.i++];const sp=csSpouse(p);if(sp){(CSIN[sp.hid]=CSIN[sp.hid]||[]).push({from:o.id,pi:i});CSHUS.set(sp.hus,{p,from:o})}if(performance.now()-t0>ms)return false}\n  CSST=null;return true}"
CARD = CARD.replace(_old, _new)
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
/* ── 项 4b 敲门卡（取自街区页，见 tile_heart.py 注释）── */
const late=HD.late;const STORIES=env.STORIES||{{}},VOICES=env.VOICES||{{}};let sel=null,threads=[],threadT=0;const VEIN=null;
const showCard=html=>env.showCard(html),blip=()=>{{}},flyTo=(x,y,z)=>env.flyTo(x,y,z),setYear=y=>env.setYear(y);
{CARD}
function openHouse(id){{const h=houseById(id);if(!h)return null;sel={{kind:'house',hh:household(h)}};renderCard();return h}}
function closeCard(){{sel=null;threads=[]}}
function cardClick(t){{if(!sel)return;
  if(t.dataset.p!==undefined&&sel.kind==='house'){{sel={{kind:'person',hid:sel.hh.h.id,pi:+t.dataset.p,step:-1}};renderCard();return}}
  if(t.dataset.pf){{const [hid,pi]=t.dataset.pf.split(':').map(Number);sel={{kind:'person',hid,pi,step:-1}};renderCard();return}}
  if(t.dataset.step!==undefined&&sel.kind==='person'){{csGoStep(+t.dataset.step);return}}
  if(t.dataset.go&&sel.kind!=='house'){{const id=+t.dataset.go;const tg=houseById(id);if(tg){{openHouse(id);flyTo(tg.cx,tg.cy,Math.max(env.cam.z,1.6))}}return}}
  if(sel.kind!=='house')return;
  if(t.dataset.go){{const id=+t.dataset.go;const tg=houseById(id);if(tg){{openHouse(id);flyTo(tg.cx,tg.cy,Math.max(env.cam.z,1.6))}}return}}
  if(t.dataset.q==='next'&&sel.cs){{sel.cs.n++}}renderCard()}}
const WG={{}};function warmCrowd(ms){{if(!FLEET||!FLEET.crowdGen||YEAR<FLEET.C.from||FLEET.cache[YEAR])return true;const g=WG[YEAR]||(WG[YEAR]=FLEET.crowdGen(YEAR)),t0=performance.now();for(;;){{const s=g.next();if(s.done)return true;if(performance.now()-t0>ms)return false}}}}
FLEET&&(FLEET.dockDraw=function(){{}});   /* 码头逐年长的遮盖：瓦片页的烤图已经按年画好 */
return {{houses,houseById,city,SCENE,household,famAt,aliveAt,nearestHouse,openHouse,closeCard,cardClick,renderCard,csIncoming,csIncStep,warmCrowd,get sel(){{return sel}},periodOf,
  get FLEET(){{return FLEET}},get YEAR(){{return YEAR}},set YEAR(v){{YEAR=v}},get clock(){{return clock}},set clock(v){{clock=v}},get dayIdx(){{return dayIdx}},set dayIdx(v){{dayIdx=v}},
  FW:W,FH:H,hash,rng}};
'''
os.makedirs(os.path.join(ROOT, 'docs/living/tiles/heart'), exist_ok=True)
out = os.path.join(ROOT, 'docs/living/tiles/heart', q + '.js')
open(out, 'w', encoding='utf-8').write(f'/* CS 线 · tile_heart.py 生成，勿手改 */\n(window.__HEART=window.__HEART||{{}}).{q}=function(env){{"use strict";{body}}};\n')
print(out, os.path.getsize(out), 'bytes', 'fleet' if has_fleet else 'no fleet')
