/* props（lookdev 第 2 轮，props+flora 代理）：港口生活。
   - 船：当年在用的每座栈桥恰好泊一条大船（圆腹粮船 / 窄长桨船），贴着栈桥一侧，船身全在水里、不压别的栈桥和别的船。
   - 小艇和驳船：沿码头岸边零星泊着（另算，不计入「每座栈桥一条船」）。
   - 吊车：码头岸边和粮仓前，踏轮吊车，主臂朝水。
   - 货：码头岸带和粮仓前的麻袋堆、双耳罐（立排 + 卧垛）、木箱、草捆、手推车。
   全部实例化（每种部件一个 InstancedMesh），确定性（ctx.hsh），船在 tick 里轻轻起伏。
   读：pier、mole、water(harbor)、landmark(granary)、house（只用来避开房子）。不改任何底账要素。
   自查：window.__propsCheck（每座在用栈桥 → 船），docs/cs/lookdev/r2/props/ 里的脚本复核。 */
import * as K from './props/kit.js';
import {makeSite,pierEnds,segDist,bboxOf,inRings} from './props/site.js';
export const name='props';
export const checkShot=4;

let T=null,MAT=null,G={},LIVE=[],SHIPS=[],SH_MESH=new Map();
const TAU=Math.PI*2;

export function init(ctx){T=ctx.THREE;K.setThree(T);
  MAT=new T.MeshLambertMaterial({vertexColors:true});
  G={round0:K.roundShip(0),round1:K.roundShip(1),galley:K.galley(),skiff:K.skiff(),lighter:K.lighter(),
     amph:K.amphoraGeo(),sack:K.sackMerged(),crate:K.crateGeo(),bale:K.baleGeo(),cart:K.cartGeo(),crane:K.craneGeo(),bollard:K.bollardGeo()}}

/* 一个实例桶：收集矩阵 + 颜色，最后变成一个 InstancedMesh */
function bucket(){return {m:[],c:[]}}
function flush(ctx,key,b,{shadow=true,recv=false}={}){if(!b.m.length)return null;const im=new T.InstancedMesh(G[key],MAT,b.m.length);
  b.m.forEach((m,i)=>{im.setMatrixAt(i,m);im.setColorAt(i,b.c[i])});im.instanceMatrix.needsUpdate=true;if(im.instanceColor)im.instanceColor.needsUpdate=true;
  im.castShadow=shadow;im.receiveShadow=recv;im.userData.kind=key;ctx.add(im);LIVE.push(im);return im}
const mtx=(x,y,z,ry,s=1,sy=s,rx=0,rz=0)=>new T.Matrix4().compose(new T.Vector3(x,y,z),new T.Quaternion().setFromEuler(new T.Euler(rx,ry,rz,'YXZ')),new T.Vector3(s,sy,s));
/* 部件的 +x 朝 (ux,uz)：three 里绕 y 转 θ 后 +x → (cosθ, -sinθ)，所以 θ = atan2(-uz, ux) */
const yawOf=(ux,uz)=>Math.atan2(-uz,ux);

/* ---- 码头场地栅格：港池 / 石堤 / 栈桥用 2D 画布光栅化，再按地形分水陆，BFS 出到水、到岸的距离 ---- */
const STEP=1.5;
function zoneRaster(ctx,site,bb){const nx=Math.ceil((bb.x1-bb.x0)/STEP)+1,nz=Math.ceil((bb.z1-bb.z0)/STEP)+1;
  const cv=document.createElement('canvas');cv.width=nx;cv.height=nz;const X=cv.getContext('2d',{willReadFrequently:true});X.setTransform(1/STEP,0,0,1/STEP,-bb.x0/STEP,-bb.z0/STEP);
  const fill=(g,col)=>{X.beginPath();ctx.geom.pathRings(X,g);X.fillStyle=col;X.fill('evenodd')};
  X.globalCompositeOperation='lighter';for(const f of site.harbors)fill(f.g,'#0000ff');for(const f of site.moles)fill(f.g,'#00ff00');
  X.strokeStyle='#ff0000';X.lineCap='butt';for(const f of site.piers){X.beginPath();X.moveTo(f.g[0][0],f.g[0][1]);X.lineTo(f.g[1][0],f.g[1][1]);X.lineWidth=f.w;X.stroke()}
  const D=X.getImageData(0,0,nx,nz).data,N=nx*nz,cls=new Int8Array(N);/* 0 空、1 水、2 地、3 栈桥 */
  for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){const k=j*nx+i,x=bb.x0+i*STEP,z=bb.z0+j*STEP,r=D[k*4],g=D[k*4+1],b=D[k*4+2];
    if(r>128){cls[k]=3;continue}if(g>128){cls[k]=2;continue}if(b>128){cls[k]=1;continue}if(x>ctx.W-1||x<1||z<1||z>ctx.H-1){cls[k]=0;continue}
    const gr=ctx.ground(x,z);cls[k]=gr<-2.5?1:(gr>.3?2:0)}
  /* 倒角距离变换（两遍扫，3-4 权近似欧氏），单位像素 */
  const bfs=src=>{const d=new Float32Array(N);for(let k=0;k<N;k++)d[k]=src(cls[k])?0:1e9;const a=STEP,b=STEP*1.414;
    for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){const k=j*nx+i;let v=d[k];if(i>0)v=Math.min(v,d[k-1]+a);if(j>0){v=Math.min(v,d[k-nx]+a);if(i>0)v=Math.min(v,d[k-nx-1]+b);if(i<nx-1)v=Math.min(v,d[k-nx+1]+b)}d[k]=v}
    for(let j=nz-1;j>=0;j--)for(let i=nx-1;i>=0;i--){const k=j*nx+i;let v=d[k];if(i<nx-1)v=Math.min(v,d[k+1]+a);if(j<nz-1){v=Math.min(v,d[k+nx]+a);if(i<nx-1)v=Math.min(v,d[k+nx+1]+b);if(i>0)v=Math.min(v,d[k+nx-1]+b)}d[k]=v}
    return d};
  const dW=bfs(c=>c===1),dL=bfs(c=>c===2||c===3);
  const at=(x,z)=>{const i=Math.round((x-bb.x0)/STEP),j=Math.round((z-bb.z0)/STEP);return (i<0||j<0||i>=nx||j>=nz)?-1:j*nx+i};
  /* 梯度：指向离水更远（往岸里） */
  const grad=(d,x,z)=>{const e=STEP*2,f=(a,b)=>{const k=at(a,b);return k<0?0:Math.min(d[k],60)};let gx=f(x+e,z)-f(x-e,z),gz=f(x,z+e)-f(x,z-e);const L=Math.hypot(gx,gz)||1;return [gx/L,gz/L]};
  return {bb,nx,nz,cls,dW,dL,at,grad}}

export function build(ctx){const t0=performance.now(),TM={};const {hsh}=ctx,site=makeSite(ctx);TM.site=Math.round(performance.now()-t0);ctx.reg.propsSite=site;SHIPS=[];SH_MESH=new Map();
  const B={round0:bucket(),round1:bucket(),galley:bucket(),skiff:bucket(),lighter:bucket(),amph:bucket(),sack:bucket(),crate:bucket(),bale:bucket(),cart:bucket(),crane:bucket(),bollard:bucket()};
  const col=(hex,k,amt=.1)=>{const c=new T.Color(hex);const f=1-amt+2*amt*k;return c.multiplyScalar(f)};
  const white=new T.Color(1,1,1);

  /* ---------- 1. 每座在用栈桥一条大船 ---------- */
  const check={year:ctx.year,piers_in_use:site.piers.length,ships_at_piers:0,per_pier:[],fallbacks:0};
  const placed=[];/* {x,z,ux,uz,L,Bm} */
  const clear=(x,z,ux,uz,L,Bm,pIdx)=>{let bad=0;const nx=-uz,nz=ux;
    for(const [a,b] of [[0,0],[.48,0],[-.48,0],[.3,.45],[.3,-.45],[-.3,.45],[-.3,-.45],[0,.5],[0,-.5],[.15,.5],[-.15,-.5]]){const px=x+ux*a*L+nx*b*Bm,pz=z+uz*a*L+nz*b*Bm;
      if(!site.isWater(px,pz))bad++;if(site.onPier(px,pz,.6))bad+=2}
    for(const o of placed){const d=segDist(x,z,[o.x-o.ux*o.L*.5,o.z-o.uz*o.L*.5],[o.x+o.ux*o.L*.5,o.z+o.uz*o.L*.5]);const d2=segDist(o.x,o.z,[x-ux*L*.5,z-uz*L*.5],[x+ux*L*.5,z+uz*L*.5]);if(Math.min(d,d2)<(Bm+o.Bm)/2+1)bad+=3}
    return bad};
  site.piers.forEach((f,pi)=>{const id=(f.g[0][0]*7+f.g[0][1]*13)|0,{root,tip}=pierEnds(site,f),dx=tip[0]-root[0],dz=tip[1]-root[1],PL=Math.hypot(dx,dz),ux=dx/PL,uz=dz/PL,nx=-uz,nz=ux;
    const r=hsh(id,1),kind=PL>=40&&r<.62?(hsh(id,2)<.5?'round0':'round1'):'galley',L0=kind==='galley'?30:36,B0=kind==='galley'?5.6+11:10;/* 桨伸出去，占宽算上 */
    const s0=hsh(id,3)<.5?1:-1,fwd=hsh(id,4)<.7?1:-1;let best=null;
    for(const sc of [1,.85,.72,.6,.5])for(const side of [s0,-s0])for(const t of [.55,.45,.65,.35,.75]){const L=L0*sc,Bm=B0*sc,off=f.w/2+Bm/2+.8;
      const along=Math.min(PL-L*.35,Math.max(L*.35,PL*t)),x=root[0]+ux*along+nx*side*off,z=root[1]+uz*along+nz*side*off;const bad=clear(x,z,ux,uz,L,Bm,pi);
      if(!best||bad<best.bad)best={x,z,L,Bm,sc,side,bad};if(bad===0)break}
    if(best.bad>0)check.fallbacks++;
    const sux=ux*fwd,suz=uz*fwd;placed.push({x:best.x,z:best.z,ux:sux,uz:suz,L:best.L,Bm:best.Bm});
    const ph=hsh(id,5)*TAU,bk=B[kind];bk.m.push(mtx(best.x,0,best.z,yawOf(sux,suz),best.sc));bk.c.push(col(0xffffff,hsh(id,6),.08));
    SHIPS.push({kind,i:bk.m.length-1,x:best.x,z:best.z,yaw:yawOf(sux,suz),s:best.sc,ph,amp:.12+.08*hsh(id,7)});
    check.ships_at_piers++;check.per_pier.push({pier:pi,harbor:f.harbor,y0:f.y0,a:f.g[0],b:f.g[1],w:f.w,kind,scale:+best.sc.toFixed(2),x:+best.x.toFixed(1),z:+best.z.toFixed(1),len:+best.L.toFixed(1),clear:best.bad===0})});

  TM.ships=Math.round(performance.now()-t0);
  /* ---------- 2. 码头场地：两座港池（外扩 50）+ 每座粮仓（外扩 80） ---------- */
  const zones=[];const zh=[];for(const f of site.harbors){const b=bboxOf(f.g);zones.push({bb:{x0:b.x0-50,x1:b.x1+50,z0:b.z0-50,z1:b.z1+50},w:.8,id:f.id,step:5})}
  for(const l of site.lms)if(l.f.k==='granary'){const xs=l.f.g.map(p=>p[0]),zs=l.f.g.map(p=>p[1]);zh.push({bb:{x0:Math.min(...xs)-80,x1:Math.max(...xs)+80,z0:Math.min(...zs)-80,z1:Math.max(...zs)+80},w:1.5,gran:l,id:l.f.id,step:4})}
  zones.unshift(...zh);/* 粮仓区先摆（更密），港区后摆，格子占过的不重复 */
  const taken=new Map();const tkey=(x,z)=>Math.floor(x/3.4)*8192+Math.floor(z/3.4);/* 4 像素格子：同一格只放一堆，区域重叠时不重复 */
  const nearGran=(x,z,m)=>site.lms.some(l=>l.f.k==='granary'&&(()=>{const r=l.r,dx=x-r.cx,dz=z-r.cz,u=dx*r.ax+dz*r.az,v=-dx*r.az+dz*r.ax;return Math.abs(u)<=r.hu+m&&Math.abs(v)<=r.hv+m})());
  const cranes=[],boats=[],bollards=[],zc={};let nClusters=0;
  zones.forEach((Z,zi)=>{const R=zoneRaster(ctx,site,Z.bb),bb=Z.bb;
    /* 2a 吊车：陆上码头岸边（离水 1–3，不上石堤），彼此 ≥ 40，避开房子；候选按哈希排序取前几个，栈桥根附近优先 */
    const maxCr=Z.gran?3:Math.max(2,Math.round(site.piers.filter(p=>p.harbor===Z.id).length/3)),cand=[];
    for(let j=0;j<R.nz;j+=2)for(let i=0;i<R.nx;i+=2){const k=j*R.nx+i;if(R.cls[k]!==2||R.dW[k]>3||R.dW[k]<1)continue;const x=bb.x0+i*STEP,z=bb.z0+j*STEP;
      if(Z.gran&&!nearGran(x,z,45))continue;const nearRoot=site.piers.some(p=>Math.min(Math.hypot(p.g[0][0]-x,p.g[0][1]-z),Math.hypot(p.g[1][0]-x,p.g[1][1]-z))<16);
      cand.push({x,z,k,s:hsh((x*3+z*5)|0,21)*(nearRoot?.4:1)})}
    cand.sort((a,b)=>a.s-b.s);let nCr=0;
    for(const c of cand){if(nCr>=maxCr)break;const {x,z}=c;if(cranes.some(o=>Math.hypot(o.x-x,o.z-z)<40))continue;if(site.inMole(x,z)||site.inHouse(x,z,5)||site.inLandmark(x,z,3))continue;
      const g=R.grad(R.dW,x,z);cranes.push({x:x+g[0]*2.5,z:z+g[1]*2.5,ux:-g[0],uz:-g[1]});nCr++}
    let wet=0;for(let k=0;k<R.cls.length;k++)if(R.cls[k]===1){wet++;if(wet>200)break}const inland=wet<=200;/* 不靠水的粮仓：门前货少一半 */
    /* 2b 货堆：抖动网格 5 像素，岸带（离水 1.5–14）或粮仓前（离粮仓 ≤ 30） */
    for(let z=bb.z0;z<bb.z1;z+=Z.step)for(let x=bb.x0;x<bb.x1;x+=Z.step){const sd=((x*13+z*7)|0),jx=x+(hsh(sd,31)-.5)*Z.step*.6,jz=z+(hsh(sd,32)-.5)*Z.step*.6,k=R.at(jx,jz);if(k<0||R.cls[k]!==2)continue;
      const dw=R.dW[k],fore=nearGran(jx,jz,18);if(!((dw>=1.5&&dw<=(Z.gran?20:10))||fore))continue;
      const p=(inland?.5:1)*Math.min(.95,Z.w*(fore?.8:(dw<=6?.55:.3))*(!Z.gran&&site.inMole(jx,jz)?.45:1));if(hsh(sd,33)>p)continue;
      const tk=tkey(jx,jz);if(taken.has(tk))continue;if(site.inHouse(jx,jz,1.5)||site.inLandmark(jx,jz,1.2))continue;if(cranes.some(c=>Math.hypot(c.x-jx,c.z-jz)<7))continue;taken.set(tk,1);
      const g=R.grad(R.dW,jx,jz),tx=-g[1],tz=g[0];cluster(ctx,site,B,jx,jz,tx,tz,sd,col,white);nClusters++;zc[Z.id]=(zc[Z.id]||0)+1}
    /* 2b' 系船桩：岸沿（离水 0.8–2）每 ≈ 6 像素一根 */
    for(let z=bb.z0;z<bb.z1;z+=3)for(let x=bb.x0;x<bb.x1;x+=3){const k=R.at(x,z);if(k<0||R.cls[k]!==2)continue;const dw=R.dW[k];if(dw<.8||dw>2.2)continue;const sd=((x*5+z*19)|0);if(hsh(sd,61)>.5)continue;
      if(bollards.some(b=>Math.abs(b.x-x)<5&&Math.abs(b.z-z)<5))continue;if(site.inHouse(x,z,.5))continue;bollards.push({x,z})}
    /* 2c 小艇、驳船：水里离岸 2.5–7，离栈桥 ≥ 7，彼此 / 离大船 ≥ 12 */
    for(let z=bb.z0;z<bb.z1;z+=6)for(let x=bb.x0;x<bb.x1;x+=6){const sd=((x*11+z*17)|0);if(hsh(sd,41)>(Z.gran?.8:.3))continue;const jx=x+(hsh(sd,42)-.5)*4,jz=z+(hsh(sd,43)-.5)*4,k=R.at(jx,jz);if(k<0||R.cls[k]!==1)continue;
      const dl=R.dL[k];if(dl<2.5||dl>(Z.gran?12:7))continue;if(site.onPier(jx,jz,7))continue;if(!Z.gran&&!site.harbors.some(h=>inRings(h.g,jx,jz)))continue;if(boats.some(b=>Math.hypot(b.x-jx,b.z-jz)<(Z.gran?10:12))||placed.some(o=>segDist(jx,jz,[o.x-o.ux*o.L*.5,o.z-o.uz*o.L*.5],[o.x+o.ux*o.L*.5,o.z+o.uz*o.L*.5])<o.Bm/2+8))continue;
      const g=R.grad(R.dL,jx,jz);/* dL 的梯度指向离岸更远，切线 = 垂直 */let tx=-g[1],tz=g[0];if(hsh(sd,44)<.5){tx=-tx;tz=-tz}
      const kind=hsh(sd,45)<.62?'skiff':'lighter',L=kind==='skiff'?9:13;let ok=true;for(const a of [-.5,-.25,0,.25,.5])for(const b of [-1,1]){const px=jx+tx*a*L+(-tz)*b*2.2,pz=jz+tz*a*L+tx*b*2.2;if(!site.isWater(px,pz)||site.onPier(px,pz,.5))ok=false}
      if(!ok)continue;boats.push({x:jx,z:jz,ux:tx,uz:tz,kind,sd})}
  });
  for(const b of bollards){B.bollard.m.push(mtx(b.x,site.yAt(b.x,b.z),b.z,0));B.bollard.c.push(white)}
  for(const c of cranes){B.crane.m.push(mtx(c.x,site.yAt(c.x,c.z),c.z,yawOf(c.ux,c.uz)));B.crane.c.push(white)}
  for(const b of boats){const bk=B[b.kind];bk.m.push(mtx(b.x,0,b.z,yawOf(b.ux,b.uz)));bk.c.push(col(0xffffff,hsh(b.sd,46),.12));SHIPS.push({kind:b.kind,i:bk.m.length-1,x:b.x,z:b.z,yaw:yawOf(b.ux,b.uz),s:1,ph:hsh(b.sd,47)*TAU,amp:.1})}

  TM.zones=Math.round(performance.now()-t0);
  /* ---------- 3. 出网格 ---------- */
  LIVE=[];
  for(const k of ['round0','round1','galley','skiff','lighter']){const im=flush(ctx,k,B[k],{recv:true});if(im)SH_MESH.set(k,im)}
  for(const k of ['amph','sack','crate','bale','cart','crane','bollard'])flush(ctx,k,B[k]);
  check.shore_boats=boats.length;check.cranes=cranes.length;check.clusters=nClusters;check.zone_clusters=zc;check.items={};for(const k in B)check.items[k]=B[k].m.length;
  TM.total=Math.round(performance.now()-t0);check.ms=TM;window.__propsCheck=check}

/* 一堆货：局部坐标 u 沿岸（tx,tz），v 往岸里（-tz,tx 的反向随便，堆是对称的） */
function cluster(ctx,site,B,x,z,tx,tz,sd,col,white){const {hsh}=ctx,r=hsh(sd,34),vx=-tz,vz=tx;const put=(bk,u,v,yy,ry,s,c,sy=s,rx=0,rz=0)=>{const px=x+tx*u+vx*v,pz=z+tz*u+vz*v;if(site.inHouse(px,pz,.4))return;
    bk.m.push(mtx(px,site.yAt(px,pz)+yy,pz,yawOf(tx,tz)+ry,s,sy,rx,rz));bk.c.push(c)};
  const k=i=>hsh(sd,50+i);
  if(r<.12){/* 沿岸一长溜麻袋：两层 */const n=4+Math.floor(k(1)*4),s=.95+.1*k(4);for(let l=0;l<2;l++)for(let a=0;a<n-l;a++)for(let b=0;b<2-l;b++)put(B.sack,(a-(n-l-1)/2)*1.25*s,(b-(1-l)/2)*.95*s,l*.5*s,(k(20+a+b*7)-.5)*.4,s,col(0xb89e70,k(30+a*3+b+l*17),.1))}
  else if(r<.36){/* 麻袋金字塔 */const n=2+Math.floor(k(1)*3),d=1+Math.floor(k(2)*2),lay=1+Math.floor(k(3)*3),s=.95+.15*k(4);
    for(let l=0;l<lay&&n-l>0;l++)for(let a=0;a<n-l;a++)for(let b=0;b<Math.max(1,d-(l>0?1:0));b++){const c=col(0xb89e70,k(10+l*9+a*3+b),.1);put(B.sack,(a-(n-l-1)/2)*1.3*s,(b-(d-1)/2)*.95*s,l*.5*s,(k(20+a+b)-.5)*.5,s,c)}}
  else if(r<.70){/* 双耳罐：立着一排排，有时旁边一垛卧着的 */const a=2+Math.floor(k(1)*3),b=2+Math.floor(k(2)*2),s=.85+.25*k(3),base=k(4)<.5?0xa8643c:0xb87a4e;
    for(let i=0;i<a;i++)for(let j=0;j<b;j++){const tilt=(k(10+i*3+j)-.5)*.3;put(B.amph,(i-(a-1)/2)*.78*s,(j-(b-1)/2)*.78*s,0,k(30+i+j)*6,s,col(base,k(40+i*3+j),.12),s,tilt,0)}
    if(k(5)<.45)for(let l=0;l<3;l++)for(let i=0;i<3-l;i++)put(B.amph,(i-(2-l)/2)*.72*s,(b/2+1.4)*.78*s,.36*s+l*.6*s,Math.PI/2,s,col(base,k(60+l*3+i),.12),s,0,Math.PI/2)}
  else if(r<.86){/* 木箱 */const n=1+Math.floor(k(1)*4),s=.9+.25*k(2);for(let i=0;i<n;i++){const st=i>=2&&k(10+i)<.6;put(B.crate,((i%2)-.5)*1.3*s,st?0:(Math.floor(i/2)-.3)*1.05*s,st?.95*s:0,(k(20+i)-.5)*.4,s,col(0x8a6640,k(30+i),.14))}}
  else if(r<.95){/* 草捆 / 布捆 */const n=2+Math.floor(k(1)*4);for(let i=0;i<n;i++)put(B.bale,(i%3-1)*.9,Math.floor(i/3)*1.1,0,(k(10+i)-.5)*.3,1,col(k(2)<.5?0xb9a06a:0xa89878,k(20+i),.1))}
  else put(B.cart,0,0,0,(k(1)-.5)*1.2,1,white)}

export function tick(ctx,t){/* 船：极轻的起伏和横摇（still 模式下 t 固定 → 同图） */if(!SHIPS.length)return;const m=new T.Matrix4(),q=new T.Quaternion(),e=new T.Euler(),v=new T.Vector3(),s=new T.Vector3();const dirty=new Set();
  for(const S of SHIPS){const im=SH_MESH.get(S.kind);if(!im)continue;const w=t*.9+S.ph;v.set(S.x,Math.sin(w)*S.amp,S.z);e.set(Math.sin(w*.8+1)*.02,S.yaw,Math.sin(w*.6)*.012,'YXZ');q.setFromEuler(e);s.set(S.s,S.s,S.s);m.compose(v,q,s);im.setMatrixAt(S.i,m);dirty.add(im)}
  for(const im of dirty)im.instanceMatrix.needsUpdate=true}

export function dispose(ctx){for(const im of LIVE){ctx.scene.remove(im);im.dispose()}LIVE=[];SHIPS=[];SH_MESH=new Map()}
