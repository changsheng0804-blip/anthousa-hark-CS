/* CS 线 · 南港 3D 渲染器 · core（导演）——2026-10-20 lookdev 第 2 轮第 0 步，从 3d.html 拆出来。
   只有 core 能改本文件（见 docs/cs/lookdev/MODULE_CONTRACT.md）。core 管：渲染器、相机、控制、数据载入、
   年份重建循环、地面贴图画布（各模块按顺序往上画）、水陆蒙版和 ground()、机位钩子、注册表。不管任何「样子」。
   坐标：x = 页面像素 x，z = 页面像素 y，y = 高度（像素，1 像素 ≈ 0.84 米）。

   模块接口（每个 3d/*.js）：
     export const name='water';  export const checkShot=1;
     export function init(ctx){}       可选，只调一次（建材质、常驻网格、灯）
     export function paint(ctx,X){}    可选，每次重建往地面贴图画自己那层（X = 2D 画布，已设好页面像素坐标；core 每层前后 save/restore）
     export function build(ctx){}      每次重建（年份变了）调一次：按 ctx.year 把东西加进场景（用 ctx.add）
     export function dispose(ctx){}    每次重建前调：清掉上一次 build 加的东西
     export function tick(ctx,t){}     可选，每帧（still 模式下只在 __still() 时调，t 固定 = 机位的 t，默认 0）
   顺序（init / paint / build / tick 都按这个）：sky → terrain → water → streets → buildings → props → flora → crowd。
   streets 在 buildings 之前，所以 streets 写的 reg.frontage 到 buildings 时已经在。 */
import * as THREE from 'three';
import {MapControls} from 'three/addons/controls/MapControls.js';
import * as sky from './sky.js';
import * as terrain from './terrain.js';
import * as water from './water.js';
import * as streets from './streets.js';
import * as buildings from './buildings.js';
import * as props from './props.js';
import * as flora from './flora.js';
import * as crowd from './crowd.js';

export const MODULES=[sky,terrain,water,streets,buildings,props,flora,crowd];
const $=id=>document.getElementById(id);
const QS=new URLSearchParams(location.search);
/* ?only=a,b：只建这些模块（单模块自查）。sky 和 terrain 是舞台，总是开着（灯和地面贴图都在它们身上）。 */
const ONLY=QS.get('only')?new Set(['sky','terrain',...QS.get('only').split(',').map(s=>s.trim())]):null;
const ACTIVE=MODULES.filter(m=>!ONLY||ONLY.has(m.name));

const WD=await fetch('nodes.json').then(r=>r.json());
const W=WD.W,H=WD.H,E=WD.elev,MPP=E.mpp;
export const hsh=(n,k=0)=>{let x=(Math.imul(n|0,2654435761)+Math.imul(k,40503))>>>0;x^=x>>>15;x=Math.imul(x,2246822519)>>>0;x^=x>>>13;return (x>>>0)/4294967296};
const by={};for(const f of WD.features)(by[f.t]=by[f.t]||[]).push(f);
const EX=1.3;/* 高度夸张一点，七丘才显得出来 */
function elevPx(x,y){const s=E.st,gx=Math.max(0,Math.min(E.w-1.001,x/s)),gy=Math.max(0,Math.min(E.h-1.001,y/s)),i=gx|0,j=gy|0,fx=gx-i,fy=gy-j,g=(a,b)=>E.dm[b*E.w+a]/10;
  const m=(g(i,j)*(1-fx)+g(i+1,j)*fx)*(1-fy)+(g(i,j+1)*(1-fx)+g(i+1,j+1)*fx)*fy;return m/MPP*EX}

/* ---- 共享几何小工具（地标、粮仓、广场等都用） ---- */
export function quadAxes(P){/* P: 4 角 [x,z]；返回中心、长轴、半长半宽 */const cx=(P[0][0]+P[1][0]+P[2][0]+P[3][0])/4,cz=(P[0][1]+P[1][1]+P[2][1]+P[3][1])/4;
  const ux=P[1][0]-P[0][0],uz=P[1][1]-P[0][1],vx=P[3][0]-P[0][0],vz=P[3][1]-P[0][1],Lu=Math.hypot(ux,uz),Lv=Math.hypot(vx,vz);
  return Lu>=Lv?{cx,cz,ax:ux/Lu,az:uz/Lu,hu:Lu/2,hv:Lv/2}:{cx,cz,ax:vx/Lv,az:vz/Lv,hu:Lv/2,hv:Lu/2}}
export function rectOf(G){let cx=0,cz=0;for(const q of G){cx+=q[0];cz+=q[1]}cx/=G.length;cz/=G.length;let best=null;for(let i=0;i<G.length;i++){const a=G[i],b=G[(i+1)%G.length],L=Math.hypot(b[0]-a[0],b[1]-a[1]);if(!best||L>best.L)best={L,ax:(b[0]-a[0])/L,az:(b[1]-a[1])/L}}
  let hu=0,hv=0;for(const q of G){const dx=q[0]-cx,dz=q[1]-cz;hu=Math.max(hu,Math.abs(dx*best.ax+dz*best.az));hv=Math.max(hv,Math.abs(-dx*best.az+dz*best.ax))}return {cx,cz,ax:best.ax,az:best.az,hu,hv}}
export const RQ=(r,u0,v0,u1,v1)=>{const c=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v];return [c(u0,v0),c(u1,v0),c(u1,v1),c(u0,v1)]};
/* 多边形环 → 2D 路径（地面贴图各层共用） */
export const pathRings=(X,g)=>{for(const P of g)for(const ring of P){X.moveTo(ring[0][0],ring[0][1]);for(let i=1;i<ring.length;i++)X.lineTo(ring[i][0],ring[i][1]);X.closePath()}};

/* ---- three：渲染器、相机、控制 ---- */
const rnd=new THREE.WebGLRenderer({antialias:true});rnd.setPixelRatio(Math.min(1.5,devicePixelRatio));rnd.setSize(innerWidth,innerHeight);rnd.shadowMap.enabled=true;rnd.shadowMap.type=THREE.PCFSoftShadowMap;document.body.prepend(rnd.domElement);
const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,2,9000);cam.position.set(560,520,1900);
const ctl=new MapControls(cam,rnd.domElement);ctl.target.set(800,0,1250);ctl.maxPolarAngle=1.42;ctl.minDistance=40;ctl.maxDistance=3200;ctl.enableDamping=true;ctl.dampingFactor=.12;ctl.update();

/* ---- 地面贴图画布：terrain 画底（海色、陆地、等高带），water 画港池和石堤地皮，streets 画街和地标地皮；terrain 的网格把它披上 ---- */
const TS=Math.min(2,4096/H),tex=document.createElement('canvas');tex.width=Math.round(W*TS);tex.height=Math.round(H*TS);const X=tex.getContext('2d');
const gtex=new THREE.CanvasTexture(tex);gtex.colorSpace=THREE.SRGBColorSpace;gtex.anisotropy=rnd.capabilities.getMaxAnisotropy();

/* ---- 水陆蒙版（core 管，因为 ground() 大家都用）：陆地 + 当年石堤 = 白，当年港池 = 黑，糊一下 ---- */
const mask=document.createElement('canvas');mask.width=Math.ceil(W/4);mask.height=Math.ceil(H/4);const MX=mask.getContext('2d');let MD=null;
function buildMask(){const L=by.land[0];MX.setTransform(.25,0,0,.25,0,0);MX.fillStyle='#000';MX.fillRect(0,0,W,H);
  const fillRings=(g,col)=>{MX.beginPath();for(const P of g)for(const r of P){MX.moveTo(r[0][0],r[0][1]);for(const p of r)MX.lineTo(p[0],p[1]);MX.closePath()}MX.fillStyle=col;MX.fill('evenodd')};
  fillRings(L.g,'#fff');
  for(const f of by.mole||[])if(ctx.live(f))fillRings(f.g,'#fff');
  for(const f of by.water||[])if(f.k==='harbor'&&ctx.live(f))fillRings(f.g,'#000');
  /* 岸边软化：地形按覆盖率在海底和陆地之间过渡，免得岸成一级级台阶 */const M2=document.createElement('canvas');M2.width=mask.width;M2.height=mask.height;const m2=M2.getContext('2d');m2.filter='blur(1.5px)';m2.drawImage(mask,0,0);
  MD=m2.getImageData(0,0,mask.width,mask.height).data}
function cover(x,y){const fx=Math.max(0,Math.min(mask.width-1.001,x/4-.5)),fy=Math.max(0,Math.min(mask.height-1.001,y/4-.5)),i=fx|0,j=fy|0,a=fx-i,b=fy-j,g=(u,v)=>MD[(v*mask.width+u)*4]/255;return (g(i,j)*(1-a)+g(i+1,j)*a)*(1-b)+(g(i,j+1)*(1-a)+g(i+1,j+1)*a)*b}
/* 地面高（海底 -6 → 陆地），x,z 页面像素 */
const ground=(x,y)=>{const c=cover(x,y),t=Math.min(1,Math.max(0,(c-.3)/.4)),s=t*t*(3-2*t);return -6+(elevPx(x,y)+7.5)*s};

/* ---- ctx：交给每个模块 ---- */
let CUR=null;
export const ctx={THREE,scene,camera:cam,renderer:rnd,controls:ctl,WD,by,W,H,year:+$('yr').value,
  live:f=>f.y0<=ctx.year&&(f.y1==null||f.y1>ctx.year),elevPx,ground,hsh,
  geom:{quadAxes,rectOf,RQ,pathRings},
  groundCanvas:tex,groundTex:gtex,groundScale:TS,
  reg:{},                       /* 共享注册表：生产者写、消费者读（如 reg.frontage、reg.slots.fountain）；每次重建前清空 */
  quality:QS.get('quality')||'high',QS,time:0,
  add(o){o.userData.mod=CUR;scene.add(o);return o},   /* 模块往场景里加东西一律用它：core 按模块数三角形 */
  only:ONLY?[...ONLY]:null,modules:ACTIVE.map(m=>m.name)};

function tris(o){let n=0;o.traverse(c=>{if(!c.isMesh||!c.geometry)return;const g=c.geometry,t=(g.index?g.index.count:(g.attributes.position?g.attributes.position.count:0))/3;n+=t*(c.isInstancedMesh?c.count:1)});return Math.round(n)}
for(const m of ACTIVE){CUR=m.name;m.init?.(ctx)}CUR=null;
let built=false;
function rebuild(){const t0=performance.now();ctx.reg={};const stats={};
  if(built)for(const m of ACTIVE){CUR=m.name;m.dispose?.(ctx)}
  X.setTransform(TS,0,0,TS,0,0);
  for(const m of ACTIVE)if(m.paint){X.save();X.setTransform(TS,0,0,TS,0,0);const t=performance.now();m.paint(ctx,X);X.restore();stats[m.name]={paint_ms:Math.round(performance.now()-t)}}
  buildMask();
  for(const m of ACTIVE){CUR=m.name;const t=performance.now();m.build?.(ctx);(stats[m.name]=stats[m.name]||{}).build_ms=Math.round(performance.now()-t)}
  CUR=null;gtex.needsUpdate=true;built=true;
  for(const o of scene.children){const k=o.userData.mod;if(k)(stats[k]=stats[k]||{}).tris=(stats[k].tris||0)+tris(o)}
  window.__modStats=stats;window.__buildMs=Math.round(performance.now()-t0);
  console.info('[3d] build',window.__buildMs,'ms',JSON.stringify(stats))}
rebuild();

let pend=0;$('yr').oninput=e=>{ctx.year=+e.target.value;$('yl').textContent='建城 '+ctx.year+' 年';clearTimeout(pend);pend=setTimeout(rebuild,60)};
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rnd.setSize(innerWidth,innerHeight)});
const TICK=ACTIVE.filter(m=>m.tick);
let fN=0,fT=performance.now(),T0=performance.now();window.__fps=0;
const frame=()=>{ctl.update();if(TICK.length){ctx.time=(performance.now()-T0)/1000;for(const m of TICK)m.tick(ctx,ctx.time)}rnd.render(scene,cam);fN++;const t=performance.now();if(t-fT>1000){window.__fps=fN*1000/(t-fT);$('fps').textContent=window.__fps.toFixed(0)+' fps';fN=0;fT=t}};
rnd.setAnimationLoop(frame);
window.__view=(px,py,pz,tx,ty,tz)=>{cam.position.set(px,py,pz);ctl.target.set(tx,ty,tz);ctl.update()};
window.__setYear=Y=>{ctx.year=Y;$('yr').value=Y;rebuild()};
window.__ctx=ctx;
/* lookdev 机位钩子（2026-10-20）：?shot=N 读 shots.json 的固定机位；?clean=1 藏掉界面。不带参数时什么都不变。 */
if(QS.has('clean'))for(const id of ['tag','bar','fps'])$(id).style.display='none';
let SHOT_T=0;
window.__applyShot=s=>{if(s.year!=null&&s.year!==ctx.year){ctx.year=s.year;$('yr').value=s.year;$('yl').textContent='建城 '+ctx.year+' 年';rebuild()}
  const gy=(x,z)=>s.eye?Math.max(0,ground(x,z)):0,p=s.pos,t=s.target;ctl.maxPolarAngle=Math.PI/2+.15;ctl.minDistance=1;SHOT_T=s.t||0;
  cam.fov=s.fov||40;cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();cam.position.set(p[0],p[1]+gy(p[0],p[2]),p[2]);ctl.target.set(t[0],t[1]+gy(t[0],t[2]),t[2]);ctl.update();window.__shot=s.id};
if(QS.has('shot')){try{const S=await fetch('shots.json').then(r=>r.json()),s=S.shots.find(x=>String(x.id)===QS.get('shot')||x.name===QS.get('shot'));if(s)window.__applyShot(s)}catch(e){console.warn('shots.json',e)}}
/* ?still=1：不跑动画循环，只在 __still() 时画一帧并交出 PNG（无头截图用）。tick 的 t 固定 = 机位的 t，保证同代码同机位同图。 */
window.__still=()=>{ctl.update();ctx.time=SHOT_T;for(const m of TICK)m.tick(ctx,SHOT_T);rnd.render(scene,cam);return rnd.domElement.toDataURL('image/png')};
if(QS.has('still'))rnd.setAnimationLoop(null);
window.__ready=1;
