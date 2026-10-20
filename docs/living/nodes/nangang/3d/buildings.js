/* buildings（lookdev 第 2 轮第 1 波）：5163 户房子 + 临街柱廊、地标部件（广场、粮仓、宁芙殿、蓄水池、孤寡院）、水道桥、栈桥、石堤。
   房子的位置/占地/高度/年份来自底账（WD house: p、ht、fn、id、y0/y1、po），只能照用；样子由 3d/arch/ 的部件和画布贴图给：
   - arch/tex.js      程序化贴图：灰泥立面、砖石夹层（opus mixtum）立面、筒瓦、粮仓长墙/山墙、水道桥拱（透明拱洞）
   - arch/house.js    民居：整层立面、缓坡出檐、檐底板；面向 m/s 街的铺面退出柱廊（柱 = 实例网格）
   - arch/granary.js  粮仓：并排山墙长仓、扶壁、拱门
   - arch/aqueduct.js 水道桥：桥面按地势平均高走，桥墩落地，谷里自然多层
   一种材质一个合并网格（墙×2、瓦、粮仓墙×2、拱廊、素色），柱子一个 InstancedMesh：draw call 个位数。
   reg.frontage（streets 写）有就用，没有就按最近的 m/s 街段自己算。——Hark（CS线）2026-10-20 */
import * as TX from './arch/tex.js';
import {bucket,meshOf,linC,mul,wall,quad,tri,roofFace,columnGeo} from './arch/geo.js';
import {house,streetGrid,STH,BAY,RT,SOFFIT} from './arch/house.js';
import {granary,GABLE_WALL_FRAC} from './arch/granary.js';
import {aqueduct} from './arch/aqueduct.js';
export const name='buildings';
export const checkShot=4;
const MARBLE=[238,232,218],STONE=[222,212,190],ROOF=[186,98,62];
let T=null,LMG=null,MESHES=[],COLM=null,colGeo=null,domeGeo=null,cylGeo=null,mats=null,quadAxes=null,RQ=null,hsh=null;

function cyl(x,y,z,r,h,m){const o=new T.Mesh(cylGeo,m);o.scale.set(r,h,r);o.position.set(x,y+h/2,z);o.castShadow=true;LMG.add(o)}
function dome(x,y,z,r,m,sy=1){const o=new T.Mesh(domeGeo,m);o.scale.set(r,r*sy,r);o.position.set(x,y,z);o.castShadow=true;LMG.add(o)}
/* 地标用的方块楼：砖石夹层立面 + 四坡/平顶（P 4 角，按轴重建） */
function block(B,P,base,h,wallS,roofS,kind,pitch=.42){const r=quadAxes(P),C=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v],k=[C(-r.hu,-r.hv),C(r.hu,-r.hv),C(r.hu,r.hv),C(-r.hu,r.hv)],y1=base+h;
  const wc=linC(wallS),rc=linC(roofS),ns=Math.max(1,Math.min(3,Math.round(h/STH)));
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4],L=Math.hypot(b[0]-a[0],b[1]-a[1]),nb=Math.max(1,Math.round(L/BAY));wall(B.opus,a,b,base-3,base,mul(wc,.8),nb,.005,.005);wall(B.opus,a,b,base,y1,wc,nb,0,ns/3)}
  if(kind==='flat'){quad(B.plain,[k[0][0],y1,k[0][1]],[k[3][0],y1,k[3][1]],[k[2][0],y1,k[2][1]],[k[1][0],y1,k[1][1]],mul(wc,.85));return}
  const O=.5,rh=r.hv*pitch,rr=Math.max(0,r.hu-r.hv),e=(u,v)=>{const q=C(u,v);return [q[0],y1-.2,q[1]]},t=u=>{const q=C(u,0);return [q[0],y1+rh,q[1]]};
  const e00=e(-r.hu-O,-r.hv-O),e10=e(r.hu+O,-r.hv-O),e11=e(r.hu+O,r.hv+O),e01=e(-r.hu-O,r.hv+O),A=t(-rr),Bq=t(rr);
  roofFace(B.roof,[e00,e10,Bq,A],e00,e10,rc,RT);roofFace(B.roof,[e11,e01,A,Bq],e11,e01,rc,RT);roofFace(B.roof,[e01,e00,A],e01,e00,rc,RT);roofFace(B.roof,[e10,e11,Bq],e10,e11,rc,RT);
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4],ee=[e00,e10,e11,e01];quad(B.plain,[b[0],y1,b[1]],[a[0],y1,a[1]],ee[i],ee[(i+1)%4],SOFFIT)}}

/* ---- 地标部件（代码，不是图） ---- */
const PARTS={
 forum(B,f,r,b,ctx){const d=10,h=8;for(const s of [-1,1]){block(B,RQ(r,-r.hu,s*r.hv,r.hu,s*(r.hv-d)),b,h,MARBLE,ROOF,'hip',.36);block(B,RQ(r,s*r.hu,-r.hv+d,s*(r.hu-d),r.hv-d),b,h,MARBLE,ROOF,'hip',.36)}
  for(let u=-r.hu+d+3;u<r.hu-d;u+=6)for(const s of [-1,1]){const x=r.cx+r.ax*u-r.az*s*(r.hv-d-2),z=r.cz+r.az*u+r.ax*s*(r.hv-d-2);ctx._cols.push([x,b,z,h,2.5])}
  cyl(r.cx,b,r.cz,2.4,34,mats.marble);dome(r.cx,b+34,r.cz,2.6,mats.gold,1.4)},
 granary(B,f,r,b,ctx){granary(ctx,B,f,r,b)},
 nymphaeum(B,f,r,b,ctx){const R_=Math.min(r.hu,r.hv*1.6)*.85,a0=Math.atan2(r.az,r.ax);for(let k=0;k<=14;k++){const t=Math.PI+k/14*Math.PI+a0,x=r.cx+Math.cos(t)*R_,z=r.cz+Math.sin(t)*R_*.6;ctx._cols.push([x,b,z,14,4.4])}
  const w=new T.Mesh(new T.CircleGeometry(R_*.75,32,0,Math.PI),mats.water);w.rotation.x=-Math.PI/2;w.rotation.z=-a0;w.scale.y=.6;w.position.set(r.cx,b+.6,r.cz);LMG.add(w)},
 cistern(B,f,r,b){for(let u=-r.hu+6;u<r.hu-3;u+=9)for(let v=-r.hv+6;v<r.hv-3;v+=9)dome(r.cx+r.ax*u-r.az*v,b,r.cz+r.az*u+r.ax*v,3.8,mats.dome,.6);block(B,RQ(r,r.hu-12,r.hv-10,r.hu-2,r.hv-2),b,6,STONE,ROOF,'hip')},
 xenon(B,f,r,b){const d=9;for(const s of [-1,1]){block(B,RQ(r,-r.hu,s*r.hv,r.hu,s*(r.hv-d)),b,9,STONE,ROOF,'hip');block(B,RQ(r,s*r.hu,-r.hv+d,s*(r.hu-d),r.hv-d),b,9,STONE,ROOF,'hip')}
  block(B,RQ(r,-8,-6,8,6),b,10,MARBLE,MARBLE,'flat');dome(r.cx,b+10,r.cz,5.5,mats.dome)}};
PARTS.monument=PARTS.nymphaeum;PARTS.monastery=PARTS.xenon;

export function init(ctx){T=ctx.THREE;({quadAxes,RQ}=ctx.geom);hsh=ctx.hsh;
  LMG=new T.Group();ctx.add(LMG);
  cylGeo=new T.CylinderGeometry(.9,1,1,8);domeGeo=new T.SphereGeometry(1,16,8,0,Math.PI*2,0,Math.PI/2);colGeo=columnGeo(T);
  const A=ctx.renderer.capabilities.getMaxAnisotropy(),an=Math.min(4,A);
  const lam=(map,extra={})=>new T.MeshLambertMaterial({vertexColors:true,side:T.DoubleSide,map,...extra});
  const arcTex=TX.texOf(T,TX.arcade(7),{aniso:an});
  mats={stucco:lam(TX.texOf(T,TX.facade('stucco',11),{aniso:an})),opus:lam(TX.texOf(T,TX.facade('opus',12),{aniso:an})),stuccoShop:lam(TX.texOf(T,TX.facade('stucco',16,true),{aniso:an})),opusShop:lam(TX.texOf(T,TX.facade('opus',17,true),{aniso:an})),roof:lam(TX.texOf(T,TX.roof(13),{aniso:an})),
    gwall:lam(TX.texOf(T,TX.granaryWall(14),{repeat:false,aniso:an})),ggable:lam(TX.texOf(T,TX.granaryGable(15,GABLE_WALL_FRAC),{repeat:false,aniso:an})),
    arc:lam(arcTex,{alphaTest:.5}),plain:lam(null),
    column:new T.MeshLambertMaterial({color:0xe9dfcc}),
    marble:new T.MeshLambertMaterial({color:0xf2eee4}),water:new T.MeshLambertMaterial({color:0x6fa2aa}),dome:new T.MeshLambertMaterial({color:0x9a8a74}),gold:new T.MeshLambertMaterial({color:0xc8a046}),mole:new T.MeshLambertMaterial({color:0xc4b8a0})};
  mats.arcDepth=new T.MeshDepthMaterial({depthPacking:T.RGBADepthPacking,map:arcTex,alphaTest:.5})}

export function build(ctx){const {by,elevPx}=ctx,live=ctx.live;
  const B={stucco:bucket(),opus:bucket(),stuccoShop:bucket(),opusShop:bucket(),roof:bucket(),plain:bucket(),gwall:bucket(),ggable:bucket(),arc:bucket()},COLS=[];ctx._cols=COLS;
  const SG=streetGrid(ctx);let nPort=0,nH=0;
  for(const f of by.house){if(!live(f))continue;nH++;nPort+=house(ctx,B,f,SG,COLS)}
  for(const f of by.landmark||[])if(live(f)){const r=ctx.geom.rectOf(f.g);(PARTS[f.k]||PARTS.granary)(B,f,r,elevPx(r.cx,r.cz)+1.6,ctx)}
  let nAq=0;for(const f of by.aqueduct||[])if(live(f))nAq+=aqueduct(ctx,B,f);
  /* 栈桥、石堤：几何照旧（第 1 轮的样子），别的带（水、码头）不受这一轮影响 */
  const PB={pos:[],col:[],uv:[]};
  for(const f of by.pier||[])if(live(f)){const [a,b]=f.g,dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),nx=-dz/L*f.w/2,nz=dx/L*f.w/2;pierBox(PB,[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]],-1,2.6,[120,88,56])}
  if(PB.pos.length){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(PB.pos,3));g.setAttribute('color',new T.Float32BufferAttribute(PB.col,3));g.computeVertexNormals();const m=new T.Mesh(g,mats.pier||(mats.pier=new T.MeshLambertMaterial({vertexColors:true,side:T.DoubleSide})));m.castShadow=m.receiveShadow=true;MESHES.push(ctx.add(m))}
  for(const f of by.mole||[])if(live(f))for(const P of f.g){const sh=new T.Shape(P[0].map(p=>new T.Vector2(p[0],p[1])));for(const r of P.slice(1))sh.holes.push(new T.Path(r.map(p=>new T.Vector2(p[0],p[1]))));
    const g=new T.ExtrudeGeometry(sh,{depth:9,bevelEnabled:false});g.rotateX(Math.PI/2);g.translate(0,3,0);const m=new T.Mesh(g,mats.mole);m.castShadow=m.receiveShadow=true;LMG.add(m)}
  for(const k of ['stucco','opus','stuccoShop','opusShop','roof','plain','gwall','ggable','arc']){const m=meshOf(T,B[k],mats[k]);if(!m)continue;if(k==='arc')m.customDepthMaterial=mats.arcDepth;MESHES.push(ctx.add(m))}
  if(COLS.length){COLM=new T.InstancedMesh(colGeo,mats.column,COLS.length);const M=new T.Matrix4(),c=new T.Color();
    COLS.forEach((q,i)=>{const rr=q[4]>1.2?q[4]:.95;M.makeScale(rr,q[3],rr).setPosition(q[0],q[1],q[2]);COLM.setMatrixAt(i,M);const g=.86+.14*hsh(i,77);c.setRGB(g,g*.985,g*.95);COLM.setColorAt(i,c)});
    COLM.castShadow=true;COLM.receiveShadow=true;ctx.add(COLM)}
  delete ctx._cols;window.__bldStats={houses:nH,porticoes:nPort,columns:COLS.length,aqueductSamples:nAq,frontageFromStreets:SG.fm?SG.fm.size:0}}
/* 栈桥：第 1 轮的平顶盒（原样：sRGB/255 直接当顶点色，保持水和码头带不动） */
function pierBox(B,P,base,h,col){const r=quadAxes(P),c=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v],k=[c(-r.hu,-r.hv),c(r.hu,-r.hv),c(r.hu,r.hv),c(-r.hu,r.hv)],y0=base-3,y1=base+h,cc=col.map(v=>v/255),c2=col.map(v=>v*.92/255);
  const t=(a,b,d,cl)=>{B.pos.push(...a,...b,...d);for(let i=0;i<3;i++)B.col.push(...cl)},q=(a,b,d,e,cl)=>{t(a,b,d,cl);t(a,d,e,cl)};
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4];q([a[0],y0,a[1]],[b[0],y0,b[1]],[b[0],y1,b[1]],[a[0],y1,a[1]],cc)}
  q([k[0][0],y1,k[0][1]],[k[3][0],y1,k[3][1]],[k[2][0],y1,k[2][1]],[k[1][0],y1,k[1][1]],c2)}

export function dispose(ctx){
  for(const m of MESHES){ctx.scene.remove(m);m.geometry.dispose()}MESHES=[];
  if(COLM){ctx.scene.remove(COLM);COLM.dispose();COLM=null}
  for(const o of LMG.children)if(o.geometry&&o.geometry!==cylGeo&&o.geometry!==domeGeo)o.geometry.dispose();
  LMG.clear()}
