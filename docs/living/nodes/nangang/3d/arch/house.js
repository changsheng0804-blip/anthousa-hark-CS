/* buildings · 民居 + 临街柱廊。——Hark（CS线）2026-10-20 lookdev 第 2 轮
   占地、高度、年份一律照底账（house.p / ht / y0,y1），这里只决定「长什么样」：
   - 墙按整层数映射立面贴图（窗不被截半），开间按墙长取整；
   - 屋顶缓坡 ≈23°，出檐 0.5 像素，檐下有深色檐底板（人眼高时读得出檐口）；
   - 柱廊：面向 m/s 街的铺面（或底账 po=1、主街成排的 row）把前墙退进去一个廊深，在原墙线上立柱、架额枋、搭单坡瓦顶。
     柱廊在占地以内，不侵占街面。frontage 先读 ctx.reg.frontage（streets 写），没有就自己按最近的 m/s 街段算。 */
import {linC,mul,wall,quad,tri,roofFace,box} from './geo.js';

export const STH=4.2, BAY=4.5, RT=3.2;
/* 灰泥色（sRGB，按美术圣经调色板 + 晒褪） */
const WALLS={stucco:[[248,238,214],[238,208,156],[230,186,128],[214,162,104],[236,196,162],[200,146,96],[244,220,172],[246,230,200],[190,136,92]],opus:[[236,214,176],[222,190,144],[210,176,130]]};
const ROOFS=[[206,116,56],[186,94,46],[166,80,40],[128,70,40],[218,144,80],[150,76,44],[108,58,36],[194,104,52]];
const OPUS_P={fine:.7,water:.6,garrison:.8,market:.45,shops:.35,horrea:1,dock:.5,planned:.3,homes:.22,workshop:.3,garden:.2};
const FLAT={workshop:.45,garden:.5,water:.12,garrison:.15,homes:.15,market:.04,shops:.05,dock:.25,planned:.1,horrea:0};
export const RIDGE=linC([232,222,204]),SOFFIT=linC([46,34,26]), CEIL=linC([96,78,60]), MARBLE_C=linC([233,223,204]);

const snapB=B=>{const o={};for(const n in B)o[n]=B[n].pos.length/3;return o};
/* 街段网格：只收 m/s 街，给 frontage 兜底用 */
export function streetGrid(ctx){const G=new Map(),CS=40,key=(i,j)=>i*100003+j;
  for(const f of ctx.by.street||[]){if(!ctx.live(f)||(f.k!=='m'&&f.k!=='s'))continue;const [ax,az,bx,bz]=f.g,pad=f.w/2+16;
    for(let i=Math.floor((Math.min(ax,bx)-pad)/CS);i<=Math.floor((Math.max(ax,bx)+pad)/CS);i++)for(let j=Math.floor((Math.min(az,bz)-pad)/CS);j<=Math.floor((Math.max(az,bz)+pad)/CS);j++){const k=key(i,j);if(!G.has(k))G.set(k,[]);G.get(k).push(f)}}
  /* reg.frontage（streets 写，v1）：户 id → 面向它的街边点；没有就 null，下面按街段自己算 */
  let fm=null;const F=ctx.reg.frontage;if(F&&Array.isArray(F.sides)){fm=new Map();for(const q of F.sides)if(q.house!=null&&(q.k==='m'||q.k==='s')&&!fm.has(q.house))fm.set(q.house,q)}
  return {fm,near(x,z){return G.get(key(Math.floor(x/CS),Math.floor(z/CS)))||[]}}}
function segInfo(x,z,s){const [ax,az,bx,bz]=s.g,dx=bx-ax,dz=bz-az,L2=dx*dx+dz*dz||1,t=Math.max(0,Math.min(1,((x-ax)*dx+(z-az)*dz)/L2)),L=Math.sqrt(L2);return {d:Math.hypot(ax+t*dx-x,az+t*dz-z),ex:dx/L,ez:dz/L}}

/* 哪条边临街：返回 {e:0..3, k} 或 null。e 是局部矩形的边：0 = v-，1 = u+，2 = v+，3 = u- */
export function frontage(ctx,f,C,u0,u1,v0,v1,SG){const mids=[C((u0+u1)/2,v0),C(u1,(v0+v1)/2),C((u0+u1)/2,v1),C(u0,(v0+v1)/2)],dirs=[C(u1,v0),C(u1,v1),C(u0,v1),C(u0,v0)],starts=[C(u0,v0),C(u1,v0),C(u1,v1),C(u0,v1)];
  /* streets 的 reg.frontage（v1）：sides[] 每条 {k,x,z,nx,nz,house}；FM = 户 id → 最近那条（buildings.build 里建） */
  const rf=SG.fm&&SG.fm.get(f.id);if(rf){let bi=0,bd=1e9;mids.forEach((m,i)=>{const d=Math.hypot(m[0]-rf.x,m[1]-rf.z);if(d<bd){bd=d;bi=i}});return {e:bi,k:rf.k}}
  let best=null;for(let e=0;e<4;e++){const m=mids[e],ex=dirs[e][0]-starts[e][0],ez=dirs[e][1]-starts[e][1],L=Math.hypot(ex,ez)||1;
    for(const s of SG.near(m[0],m[1])){const q=segInfo(m[0],m[1],s);if(Math.abs(q.ex*ex/L+q.ez*ez/L)<.8)continue;const lim=s.w/2+(s.k==='m'?14:6);if(q.d<lim&&(!best||q.d<best.d))best={e,k:s.k,d:q.d,L}}}
  return best}

/* 一户：B = {stucco, opus, roof, plain}，COLS = 柱子列表 */
export function house(ctx,B,f,SG,COLS,rec){const r0=rec?snapB(B):null;const {hsh,elevPx,geom:{quadAxes}}=ctx,p=f.p,P=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];
  const cx=(p[0]+p[2]+p[4]+p[6])/4,cz=(p[1]+p[3]+p[5]+p[7])/4,ins=P.map(q=>[cx+(q[0]-cx)*.92,cz+(q[1]-cz)*.92]);
  const r=quadAxes(ins),C=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v];let u0=-r.hu,u1=r.hu,v0=-r.hv,v1=r.hv;
  const base=elevPx(cx,cz)+1.5,H=Math.max(3,(f.ht||5)*1.15),fn=f.fn||'homes';
  const kind=hsh(f.id,21)<(OPUS_P[fn]??.25)?'opus':'stucco',WP=WALLS[kind],wc=WP[Math.floor(hsh(f.id,3)*WP.length)];
  const wcol=linC(mul(wc,.96+.08*hsh(f.id,4))),rc=ROOFS[Math.floor(hsh(f.id,14)*ROOFS.length)],rcol=linC(mul(rc,.92+.16*hsh(f.id,15)));
  /* 柱廊 */
  let fr=null;const shopish=fn==='shops'||fn==='market'||f.po===1||(f.ty==='row'&&fn!=='dock');
  if(shopish&&r.hv>2.6)fr=frontage(ctx,f,C,u0,u1,v0,v1,SG);
  if(fr&&!(fr.k==='m'||(fr.k==='s'&&(fn==='shops'||fn==='market'||f.po===1))))fr=null;
  let pd=0;if(fr){const deep=(fr.e%2===0)?(v1-v0):(u1-u0);pd=Math.min(4,deep*.3);if(pd<2.2)fr=null}
  const o0={u0,u1,v0,v1};
  if(fr){if(fr.e===0)v0+=pd;else if(fr.e===1)u1-=pd;else if(fr.e===2)v1-=pd;else u0+=pd}
  const k=[C(u0,v0),C(u1,v0),C(u1,v1),C(u0,v1)],y1=base+H,ns=Math.max(1,Math.min(3,Math.round(H/STH))),vt=ns/3,WB=B[kind+((fn==='shops'||fn==='market'||fn==='dock')?'Shop':'')],uoff=Math.floor(hsh(f.id,5)*4);
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4],L=Math.hypot(b[0]-a[0],b[1]-a[1]),nb=Math.max(1,Math.round(L/BAY));
    wall(WB,a,b,base-3,base,mul(wcol,.8),nb,.005,.005,uoff);wall(WB,a,b,base,y1,wcol,nb,0,vt,uoff)}
  const flat=hsh(f.id,17)<(FLAT[fn]??.1);
  const hu=(u1-u0)/2,hv=(v1-v0)/2,mu=(u0+u1)/2,mv=(v0+v1)/2,O=.5;/* 出檐 */
  if(flat){const kk=[C(u0,v0),C(u0,v1),C(u1,v1),C(u1,v0)];quad(B.plain,[kk[0][0],y1,kk[0][1]],[kk[1][0],y1,kk[1][1]],[kk[2][0],y1,kk[2][1]],[kk[3][0],y1,kk[3][1]],mul(wcol,.82));
    /* 女儿墙压顶：一圈深线 */for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4];wall(B.plain,a,b,y1,y1+.45,mul(wcol,.7),0,0,0)}}
  else{/* 屋脊沿长边 */const along=hu>=hv,Hh=along?hu:hv,Hs=along?hv:hu,rh=Hs*.42,gable=hsh(f.id,17)<.12+(FLAT[fn]??.1)+.18&&f.ty!=='casa';
    const L=(a,b)=>along?C(mu+a,mv+b):C(mu+b,mv+a);/* a 沿脊，b 横脊 */
    const rr=gable?Hh:Math.max(0,Hh-Hs),ya=y1+rh,A=[...L(-rr,0)],Bq=[...L(rr,0)],rx=gable?Hh+O:rr,AR=L(-rx,0),BR=L(rx,0),A3=[AR[0],ya,AR[1]],B3=[BR[0],ya,BR[1]];
    const e=(sa,sb)=>{const q=L(sa*(Hh+O),sb*(Hs+O));return [q[0],y1-O*.42,q[1]]};
    const e00=e(-1,-1),e10=e(1,-1),e11=e(1,1),e01=e(-1,1);
    roofFace(B.roof,[e00,e10,B3,A3],e00,e10,rcol,RT);roofFace(B.roof,[e11,e01,A3,B3],e11,e01,rcol,RT);
    if(gable){const w0=L(-Hh,-Hs),w1=L(-Hh,Hs),w2=L(Hh,Hs),w3=L(Hh,-Hs),gc=[A[0],ya,A[1]],gd=[Bq[0],ya,Bq[1]];
      tri(WB,[w1[0],y1,w1[1]],[w0[0],y1,w0[1]],gc,wcol,[0,vt],[Hs*2/BAY,vt],[Hs/BAY,vt+.06]);tri(WB,[w3[0],y1,w3[1]],[w2[0],y1,w2[1]],gd,wcol,[0,vt],[Hs*2/BAY,vt],[Hs/BAY,vt+.06])}
    else{roofFace(B.roof,[e01,e00,A3],e01,e00,mul(rcol,.94),RT);roofFace(B.roof,[e10,e11,B3],e10,e11,mul(rcol,.94),RT)}
    /* 屋脊和斜脊压一道白灰（石灰抹的脊瓦）：每户屋顶里有清楚的线 */
    const cap=(p,q,w)=>{const dx=q[0]-p[0],dz=q[2]-p[2],L=Math.hypot(dx,dz)||1,nx=-dz/L*w,nz=dx/L*w,lift=.14;quad(B.plain,[p[0]+nx,p[1]+lift,p[2]+nz],[q[0]+nx,q[1]+lift,q[2]+nz],[q[0]-nx,q[1]+lift,q[2]-nz],[p[0]-nx,p[1]+lift,p[2]-nz],RIDGE)};
    if(rx>0.01)cap(A3,B3,.32);if(!gable){cap(e00,A3,.26);cap(e01,A3,.26);cap(e10,B3,.26);cap(e11,B3,.26)}
    /* 檐底板：墙顶一圈到檐口，朝下，深色 */
    const w=[C(u0,v0),C(u1,v0),C(u1,v1),C(u0,v1)],ee=along?[e00,e10,e11,e01]:[e00,e01,e11,e10];
    for(let i=0;i<4;i++){const a=w[i],b=w[(i+1)%4],ea=ee[i],eb=ee[(i+1)%4];quad(B.plain,[b[0],y1,b[1]],[a[0],y1,a[1]],ea,eb,SOFFIT)}}
  /* house_kit（开关，默认关）：记下这户「楼身」在各桶里的顶点区间（柱廊不算），近处换细模时把它塌掉；不改任何几何 */
  if(rec)rec.push({f,r0,r1:snapB(B),k,base,y1,H,wcol,rcol,kind,fr,flat,u:[u0,u1,v0,v1],o0,C,nc:COLS.length});
  /* 柱廊几何 */
  if(fr){const hc=Math.min(H*.72,4.3),yb=base,ya=base+hc,o=o0;let a,b,ia,ib;/* a→b = 原墙线（柱子立在上面），ia/ib = 退进去的新墙线 */
    if(fr.e===0){a=C(o.u0,o.v0);b=C(o.u1,o.v0);ia=C(o.u0,v0);ib=C(o.u1,v0)}else if(fr.e===1){a=C(o.u1,o.v0);b=C(o.u1,o.v1);ia=C(u1,o.v0);ib=C(u1,o.v1)}
    else if(fr.e===2){a=C(o.u1,o.v1);b=C(o.u0,o.v1);ia=C(o.u1,v1);ib=C(o.u0,v1)}else{a=C(o.u0,o.v1);b=C(o.u0,o.v0);ia=C(u0,o.v1);ib=C(u0,o.v0)}
    const dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),ex=dx/L,ez=dz/L,nx=ia[0]-a[0],nz=ia[1]-a[1],nl=Math.hypot(nx,nz)||1,ix=nx/nl,iz=nz/nl;
    const n=Math.max(1,Math.round(L/3.6));for(let i=0;i<n;i++){const t=(i+.5)/n,x=a[0]+dx*t+ix*.55,z=a[1]+dz*t+iz*.55;COLS.push([x,yb,z,hc,.95+.1*hsh(f.id,40+i)])}
    /* 额枋 */const mid=[(a[0]+b[0])/2+ix*.55,(a[1]+b[1])/2+iz*.55];box(B.plain,mid,L/2,.5,ya,ya+.7,ex,ez,MARBLE_C);
    /* 廊顶：天花（朝下）+ 单坡瓦顶（从墙上到额枋外沿） */
    const yt=Math.min(y1-.1,ya+1.9),A0=[a[0]-ix*.4,ya+.7,a[1]-iz*.4],B0=[b[0]-ix*.4,ya+.7,b[1]-iz*.4];
    quad(B.plain,[ia[0],ya,ia[1]],[ib[0],ya,ib[1]],[b[0],ya,b[1]],[a[0],ya,a[1]],CEIL);
    roofFace(B.roof,[B0,A0,[ia[0],yt,ia[1]],[ib[0],yt,ib[1]]],B0,A0,mul(rcol,.95),RT);
    /* 廊顶外沿的封檐（遮住天花和瓦之间的缝） */wall(B.plain,[A0[0],A0[2]],[B0[0],B0[2]],ya,ya+.75,mul(MARBLE_C,.92),0,0,0)}
  return fr?1:0}
