/* house_kit · 近处民居换细模（开关 ?flag=house_kit，默认关；关着时 buildings 一行都不走这里）。——Hark（CS线）2026-10-20
   做法：buildings.build 照旧把 5163 户 box 房合进大网格，同时记下每户楼身在各桶里的顶点区间（rec）。
   这里在 tick 里按相机距离挑近圈（≤ R = 180 像素 ≈ 150 m，离开到 R+20 才退），近圈的户：
     1. 把它 box 版的楼身顶点塌成一点（三角形面积 0，不画、不投影；柱廊照旧留着）；
     2. 按类型（typology.js）生成细模，按 48 像素的格子合并成网格（一格 2 个网格：图集材质 + 瓦材质）。
   出了近圈就把 box 顶点还原、删掉那格的细模。全是懒的：建城重建时一户细模都不生成（build 只多记区间），
   交互时每帧最多花 ~5 ms 生成，静帧（?still=1）在 __still() 时一次生成完。 */
import {HOUSE_KIT} from './flag.js';
import {bucket,meshOf} from '../geo.js';
import {buildAtlas} from './atlas.js';
import {pick} from './typology.js';
import {genHouse} from './gen.js';
export const on=HOUSE_KIT;
const R=180,RH=20,CELL=48,MOVE=10,BUDGET=5;
let T=null,MAT=null,ROOFM=null,S=null;
const still=new URLSearchParams(location.search).has('still');

function grid(items,cs,box){const G=new Map();for(const it of items){const [x0,z0,x1,z1]=box(it);for(let i=Math.floor(x0/cs);i<=Math.floor(x1/cs);i++)for(let j=Math.floor(z0/cs);j<=Math.floor(z1/cs);j++){const k=i*100003+j;if(!G.has(k))G.set(k,[]);G.get(k).push(it)}}
  return (x,z)=>G.get(Math.floor(x/cs)*100003+Math.floor(z/cs))||[]}

/* buildings.build 末尾调：rec = 每户楼身记录，meshes = {桶名: Mesh}，mats = buildings 的材质（借瓦） */
export function attach(ctx,{rec,meshes,mats,group}){const t0=performance.now();T=ctx.THREE;
  if(!MAT){const tex=new T.CanvasTexture(buildAtlas());tex.colorSpace=T.SRGBColorSpace;tex.anisotropy=Math.min(4,ctx.renderer.capabilities.getMaxAnisotropy());tex.generateMipmaps=true;tex.minFilter=T.LinearMipmapLinearFilter;
    MAT=new T.MeshLambertMaterial({vertexColors:true,side:T.DoubleSide,map:tex})}
  ROOFM=mats.roof;
  /* 街（所有等级）和港边点：只给类型判断用 */
  const st=(ctx.by.street||[]).filter(f=>ctx.live(f)),pad=f=>f.w/2+14;
  const streetsNear=grid(st,40,f=>{const [ax,az,bx,bz]=f.g,p=pad(f);return [Math.min(ax,bx)-p,Math.min(az,bz)-p,Math.max(ax,bx)+p,Math.max(az,bz)+p]});
  const hp=[];const dens=(a,b)=>{const n=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/8));for(let i=0;i<=n;i++)hp.push([a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n])};
  for(const f of ctx.by.water||[])if(f.k==='harbor'&&ctx.live(f))for(const P of f.g)for(const r of P)for(let i=0;i<r.length;i++)dens(r[i],r[(i+1)%r.length]);
  for(const f of ctx.by.pier||[])if(ctx.live(f))dens(f.g[0],f.g[1]);
  const HG=grid(hp,40,p=>[p[0]-40,p[1]-40,p[0]+40,p[1]+40]);
  const harbourDist=(x,z)=>{let d=1e9;for(const p of HG(x,z))d=Math.min(d,Math.hypot(p[0]-x,p[1]-z));return d};
  const env={hsh:ctx.hsh,streetsNear,harbourDist};
  const cells=new Map(),H=[];
  for(const r of rec){const c=[(r.k[0][0]+r.k[2][0])/2,(r.k[0][1]+r.k[2][1])/2],key=Math.floor(c[0]/CELL)*100003+Math.floor(c[1]/CELL);
    const h={r,cx:c[0],cz:c[1],cy:r.base+r.H/2,key,near:false,pk:undefined,hidden:null};H.push(h);if(!cells.has(key))cells.set(key,{key,hs:[],obj:[],near:0,tris:0});cells.get(key).hs.push(h)}
  S={ctx,meshes,group,env,cells,H,dirty:new Set(),last:null,touched:new Set(),gen_ms:0,gen_n:0,attach_ms:Math.round(performance.now()-t0),typ:{A:0,B:0,C:0,box:0,court:0}};
  publish()}

function hide(h){const {meshes}=S,r=h.r;h.hidden={};for(const n in r.r1){const a=r.r0[n],b=r.r1[n];if(b<=a||!meshes[n])continue;const arr=meshes[n].geometry.attributes.position.array;h.hidden[n]=arr.slice(a*3,b*3);
    const x=arr[a*3],y=arr[a*3+1],z=arr[a*3+2];for(let i=a;i<b;i++){arr[i*3]=x;arr[i*3+1]=y;arr[i*3+2]=z}S.touched.add(n)}}
function unhide(h){const {meshes}=S,r=h.r;if(!h.hidden)return;for(const n in h.hidden){const arr=meshes[n].geometry.attributes.position.array;arr.set(h.hidden[n],r.r0[n]*3);S.touched.add(n)}h.hidden=null}
function clearCell(c){for(const o of c.obj){S.group.remove(o);o.geometry.dispose()}c.obj=[];c.tris=0}
function buildCell(c){clearCell(c);const Bt=bucket(),Br=bucket();let n=0;
  for(const h of c.hs){if(h.near){if(h.pk===undefined)h.pk=pick(h.r,S.env);if(!h.pk){unhide(h);continue}if(!h.hidden)hide(h);const st=genHouse(Bt,Br,h.r,h.pk,S.env);h.court=st.court;n++}else unhide(h)}
  c.near=n;
  for(const [B,m] of [[Bt,MAT],[Br,ROOFM]]){const o=meshOf(T,B,m);if(!o)continue;o.userData.mod='buildings';o.userData.houseKit=1;S.group.add(o);c.obj.push(o);c.tris+=B.pos.length/9}}

/* buildings.tick 调：相机动了 ≥ MOVE 像素才重算近圈；脏格按距离排，静帧一次做完，交互每帧 ≤ BUDGET ms */
export function tick(ctx){if(!S)return;const p=ctx.camera.position;
  if(!S.last||Math.hypot(p.x-S.last[0],p.y-S.last[1],p.z-S.last[2])>=MOVE){S.last=[p.x,p.y,p.z];
    for(const h of S.H){const d=Math.hypot(h.cx-p.x,h.cy-p.y,h.cz-p.z),want=h.near?d<R+RH:d<R;if(want!==h.near){h.near=want;S.dirty.add(h.key)}}}
  if(!S.dirty.size)return;
  const t0=performance.now(),order=[...S.dirty].map(k=>S.cells.get(k)).sort((a,b)=>dist(a,p)-dist(b,p));
  for(const c of order){buildCell(c);S.dirty.delete(c.key);if(!still&&performance.now()-t0>BUDGET)break}
  for(const n of S.touched)S.meshes[n].geometry.attributes.position.needsUpdate=true;S.touched.clear();
  S.gen_ms+=performance.now()-t0;S.gen_n++;S.last_ms=Math.round(performance.now()-t0);publish()}
const dist=(c,p)=>{const h=c.hs[0];return Math.hypot(h.cx-p.x,h.cz-p.z)};

function publish(){let near=0,tris=0,hid=0,cells=0;const typ={A:0,B:0,C:0,box:0,court:0};
  for(const c of S.cells.values()){if(c.near)cells++;tris+=c.tris}
  for(const h of S.H)if(h.near){near++;if(!h.pk)typ.box++;else{typ[h.pk.type]++;if(h.court)typ.court++}if(h.hidden)for(const n in h.hidden)hid+=h.hidden[n].length/9}
  window.__houseKitStats={on:true,R,near,cells,kitTris:Math.round(tris),hiddenBoxTris:Math.round(hid),typ,attach_ms:S.attach_ms,gen_ms_total:Math.round(S.gen_ms),last_gen_ms:S.last_ms||0,pending:S.dirty.size}}

export function dispose(){if(!S)return;for(const c of S.cells.values())clearCell(c);S=null}
