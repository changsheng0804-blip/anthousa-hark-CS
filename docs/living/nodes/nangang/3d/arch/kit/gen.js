/* house_kit · 参数化生成器：一户 → 两个桶（at = 图集材质，roof = buildings 的瓦材质）。——Hark（CS线）2026-10-20
   输入 rec（buildings 记下的 box 版几何：退进后的四角 k、底 base、檐高 y1、墙色 wcol、瓦色 rcol、平顶 flat、柱廊 fr）+ pick 的类型。
   墙线 = box 版墙线，檐高 = box 版檐高（底账 ht），凸出物（窗台、挑廊、遮阳布、雨棚）≤ 底账占地边 + 0.5 像素（同 box 版的出檐）。
   种子：ctx.hsh(户 id, 2xx)，同户同图。单位：像素（1 像素 ≈ 0.84 m）。 */
import {quad,tri,roofFace,linC,mul} from '../geo.js';
import {TILE,tileUV,WIN,SHOP,DOOR,WHD,T_TIMBER,T_STRIPE,T_CLOTH,T_WHITE,T_PAVE,T_WATER,T_RAIL} from './atlas.js';
const RT=3.2,O=.5;
const WU=tileUV(T_WHITE),WUV=[(WU.u0+WU.u1)/2,(WU.v0+WU.v1)/2];
const SHUT=[[112,80,52],[96,110,98],[92,104,116],[138,72,48],[120,98,64]].map(linC);
const CLOTH=[[198,150,92],[172,86,62],[222,208,178],[100,106,128],[180,120,70]].map(linC);
const TIMBER=linC([128,92,60]),TIMBER_D=linC([96,68,44]),STONE=linC([226,216,196]),BRICK=linC([150,86,58]),RIDGE=linC([232,222,204]),SOFFIT=linC([46,34,26]),MARBLE=linC([233,225,208]),WATER=linC([120,150,156]),PAVE=linC([214,204,186]);

/* 四边形，t = 图集格号（null = 白格，纯顶点色） */
function Q(B,a,b,c,d,col,t){if(t==null){quad(B,a,b,c,d,col,WUV,WUV,WUV,WUV);return}const U=tileUV(t);quad(B,a,b,c,d,col,[U.u0,U.v0],[U.u1,U.v0],[U.u1,U.v1],[U.u0,U.v1])}
/* 墙面坐标系：沿墙 s、高 y、向外 d */
function frame(a,b,cx,cz){const ex=b[0]-a[0],ez=b[1]-a[1],L=Math.hypot(ex,ez)||1;let nx=-ez/L,nz=ex/L;const mx=(a[0]+b[0])/2-cx,mz=(a[1]+b[1])/2-cz;if(nx*mx+nz*mz<0){nx=-nx;nz=-nz}
  return {a,L,ex:ex/L,ez:ez/L,nx,nz,P:(s,y,d)=>[a[0]+ex/L*s+nx*d,y,a[1]+ez/L*s+nz*d]}}
/* 贴墙的盒子：前面、顶、底、两端（背面贴墙不画）= 10 三角形 */
function boxF(B,F,s0,s1,y0,y1,d0,d1,col,t=null,{bottom=true}={}){const P=F.P;
  Q(B,P(s0,y0,d1),P(s1,y0,d1),P(s1,y1,d1),P(s0,y1,d1),col,t);
  Q(B,P(s0,y1,d1),P(s1,y1,d1),P(s1,y1,d0),P(s0,y1,d0),mul(col,1.04),t);
  if(bottom)Q(B,P(s0,y0,d0),P(s1,y0,d0),P(s1,y0,d1),P(s0,y0,d1),mul(col,.7),t);
  Q(B,P(s0,y0,d0),P(s0,y0,d1),P(s0,y1,d1),P(s0,y1,d0),mul(col,.86),t);Q(B,P(s1,y0,d1),P(s1,y0,d0),P(s1,y1,d0),P(s1,y1,d1),mul(col,.86),t)}
/* 竖柱（6 棱柱 + 方顶板） */
function prism(B,x,z,r,y0,y1,col,n=6){for(let i=0;i<n;i++){const a0=i/n*Math.PI*2,a1=(i+1)/n*Math.PI*2,c=mul(col,.9+.1*Math.cos(a0));Q(B,[x+Math.cos(a0)*r,y0,z+Math.sin(a0)*r],[x+Math.cos(a1)*r,y0,z+Math.sin(a1)*r],[x+Math.cos(a1)*r*.88,y1,z+Math.sin(a1)*r*.88],[x+Math.cos(a0)*r*.88,y1,z+Math.sin(a0)*r*.88],c)}}

/* 一面墙：层表 st = [{y0,y1,roles[]}]，nb 开间 */
function wallFace(B,F,st,nb,kind,wcol,base,S){const bw=F.L/nb,P=F.P;
  Q(B,P(0,base-3,0),P(F.L,base-3,0),P(F.L,base,0),P(0,base,0),mul(wcol,.72));/* 勒脚 */
  if(S.socle)boxF(B,F,-.08,F.L+.08,base-.4,base+.55,0,.12,mul(wcol,.78),null,{bottom:false});/* 墙基线脚 */
  st.forEach((L,li)=>{const h=L.y1-L.y0;
    for(let i=0;i<nb;i++){const s0=i*bw,s1=s0+bw,role=L.roles[i]||'blank',t=TILE[role][kind];Q(B,P(s0,L.y0,0),P(s1,L.y0,0),P(s1,L.y1,0),P(s0,L.y1,0),wcol,t);
      if(role==='winOpen'||role==='winShut'||role==='winArch'){const ws0=s0+WIN.x0*bw,ws1=s0+WIN.x1*bw,wy0=L.y0+WIN.y0*h,wy1=L.y0+WIN.y1*h;
        boxF(B,F,ws0-.12,ws1+.12,wy0-.16,wy0,0,.2,STONE);S.win++;
        /* 窗框：两侧边框 + 过梁（真几何，低太阳下有一道影） */boxF(B,F,ws0-.14,ws0,wy0,wy1+.06,0,.09,mul(STONE,.97),null,{bottom:false});boxF(B,F,ws1,ws1+.14,wy0,wy1+.06,0,.09,mul(STONE,.97),null,{bottom:false});boxF(B,F,ws0-.2,ws1+.2,wy1+.06,wy1+.26,0,.13,STONE);
        if(role==='winOpen'){const lw=(ws1-ws0)/2,c=L.shut,an=1.15+.25*((i*7+li*3)%3)/2,cs=Math.cos(an)*lw,sn=Math.sin(an)*lw;
          Q(B,P(ws0,wy0,.02),P(ws0-cs,wy0,sn),P(ws0-cs,wy1,sn),P(ws0,wy1,.02),c,T_TIMBER);Q(B,P(ws1,wy0,.02),P(ws1+cs,wy0,sn),P(ws1+cs,wy1,sn),P(ws1,wy1,.02),c,T_TIMBER)}}
      else if(role==='shopOpen'||role==='shopShut'){const top=L.y0+SHOP.y1*h;boxF(B,F,s0+SHOP.x0*bw-.1,s0+SHOP.x1*bw+.1,top-.05,top+.3,0,.16,TIMBER_D,T_TIMBER);
        if(role==='shopOpen')boxF(B,F,s0+(SHOP.x0+.04)*bw,s0+(SHOP.x0+.58)*bw,L.y0,L.y0+1.2,0,Math.min(.55,S.proj),mul(wcol,.92),null,{bottom:false})}
      else if(role==='door'){const d0=s0+DOOR.x0*bw,d1=s0+DOOR.x1*bw,top=L.y0+DOOR.y1*h;boxF(B,F,d0-.3,d0,L.y0,top,0,.18,STONE);boxF(B,F,d1,d1+.3,L.y0,top,0,.18,STONE);boxF(B,F,d0-.45,d1+.45,top,top+.35,0,.24,STONE);boxF(B,F,d0-.2,d1+.2,L.y0-.05,L.y0+.15,0,.45,STONE,null,{bottom:false})}
      else if(role==='whDoor')S.whd.push([s0+bw/2,L.y0+WHD.y1*h,bw])}
    if(li>0)boxF(B,F,-.05,F.L+.05,L.y0-.13,L.y0+.13,0,.14,kind?BRICK:mul(STONE,.97))});
  const top=st[st.length-1].y1;boxF(B,F,-.05,F.L+.05,top-.4,top,0,.2,mul(STONE,.95))}

/* 四坡 / 两坡顶（同 box 版的形：屋脊顺长边、坡 ≈23°、出檐 O）；返回 {ya} */
function roofHip(Bt,Br,rec,gable,kind,F4,beams){const [u0,u1,v0,v1]=rec.u,C=rec.C,y1=rec.y1,hu=(u1-u0)/2,hv=(v1-v0)/2,mu=(u0+u1)/2,mv=(v0+v1)/2,along=hu>=hv,Hh=along?hu:hv,Hs=along?hv:hu,rh=Hs*.42,rc=rec.rcol;
  const L=(a,b)=>along?C(mu+a,mv+b):C(mu+b,mv+a),rr=gable?Hh:Math.max(0,Hh-Hs),ya=y1+rh,rx=gable?Hh+O:rr,AR=L(-rx,0),BR=L(rx,0),A3=[AR[0],ya,AR[1]],B3=[BR[0],ya,BR[1]];
  const e=(sa,sb)=>{const q=L(sa*(Hh+O),sb*(Hs+O));return [q[0],y1-O*.42,q[1]]},e00=e(-1,-1),e10=e(1,-1),e11=e(1,1),e01=e(-1,1);
  roofFace(Br,[e00,e10,B3,A3],e00,e10,rc,RT);roofFace(Br,[e11,e01,A3,B3],e11,e01,rc,RT);
  if(gable){const w0=L(-Hh,-Hs),w1=L(-Hh,Hs),w2=L(Hh,Hs),w3=L(Hh,-Hs),A=L(-Hh,0),Bq=L(Hh,0),U=tileUV(TILE.blank[kind]),c=rec.wcol;
    tri(Bt,[w1[0],y1,w1[1]],[w0[0],y1,w0[1]],[A[0],ya,A[1]],c,[U.u0,U.v0],[U.u1,U.v0],[(U.u0+U.u1)/2,U.v0+(U.v1-U.v0)*.5]);tri(Bt,[w3[0],y1,w3[1]],[w2[0],y1,w2[1]],[Bq[0],ya,Bq[1]],c,[U.u0,U.v0],[U.u1,U.v0],[(U.u0+U.u1)/2,U.v0+(U.v1-U.v0)*.5])}
  else{roofFace(Br,[e01,e00,A3],e01,e00,mul(rc,.94),RT);roofFace(Br,[e10,e11,B3],e10,e11,mul(rc,.94),RT)}
  const cap=(p,q,w)=>{const dx=q[0]-p[0],dz=q[2]-p[2],Ln=Math.hypot(dx,dz)||1,nx=-dz/Ln*w,nz=dx/Ln*w,l=.15;Q(Bt,[p[0]+nx,p[1]+l,p[2]+nz],[q[0]+nx,q[1]+l,q[2]+nz],[q[0]-nx,q[1]+l,q[2]-nz],[p[0]-nx,p[1]+l,p[2]-nz],RIDGE);Q(Bt,[p[0],p[1]+l+.12,p[2]],[q[0],q[1]+l+.12,q[2]],[q[0]+nx,q[1]+l,q[2]+nz],[p[0]+nx,p[1]+l,p[2]+nz],mul(RIDGE,.85))};
  if(rx>.01)cap(A3,B3,.3);if(!gable){cap(e00,A3,.24);cap(e01,A3,.24);cap(e10,B3,.24);cap(e11,B3,.24)}
  /* 檐口：瓦头一道深色封檐 + 檐底板 */
  const ee=[e00,e10,e11,e01];for(let i=0;i<4;i++){if(gable&&(i===1||i===3))continue;const a=ee[i],b=ee[(i+1)%4];Q(Bt,[a[0],a[1]-.28,a[2]],[b[0],b[1]-.28,b[2]],b,a,mul(rc,.55))}
  const w=[C(u0,v0),C(u1,v0),C(u1,v1),C(u0,v1)],eo=along?[e00,e10,e11,e01]:[e00,e01,e11,e10];for(let i=0;i<4;i++){const a=w[i],b=w[(i+1)%4];Q(Bt,[b[0],y1,b[1]],[a[0],y1,a[1]],eo[i],eo[(i+1)%4],SOFFIT)}
  /* 檐下椽头（一排小木头，人眼高时檐口有节奏）+ 檐口瓦当（一排小三角） */
  if(beams)for(const F of F4){const n=Math.floor(F.L/.75);for(let j=0;j<n;j++){const s=(j+.5)*F.L/n;boxF(Bt,F,s-.08,s+.08,y1-.3,y1-.06,0,O*.85,TIMBER_D,null,{bottom:true})}}
  for(let i=0;i<4;i++){if(gable&&(i===1||i===3))continue;const a=ee[i],b=ee[(i+1)%4],Ln=Math.hypot(b[0]-a[0],b[2]-a[2]),n=Math.floor(Ln/.45);for(let j=0;j<n;j++){const t0=(j+.25)/n,t1=(j+.75)/n,tm=(j+.5)/n,p=t=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t],q0=p(t0),q1=p(t1),qm=p(tm);tri(Bt,q0,q1,[qm[0],qm[1]+.14,qm[2]],mul(rc,.6),WUV,WUV,WUV)}}
  return {ya}}

/* 院宅的环形屋面 + 内院（四面朝院的墙、回廊、铺地、雨水池） */
function courtyard(Bt,Br,rec,P,S,nsSt,kind){const [u0,u1,v0,v1]=rec.u,C=rec.C,y1=rec.y1,base=rec.base,hu=(u1-u0)/2,hv=(v1-v0)/2,mu=(u0+u1)/2,mv=(v0+v1)/2,rc=rec.rcol,hsh=S.hsh,id=rec.f.id;
  const d=Math.max(3.6,Math.min(7,Math.min(hu,hv)*.55)),cu=hu-d,cv=hv-d;if(cu<2||cv<2)return false;
  const L=(a,b)=>C(mu+a,mv+b),R4=(a,b,y)=>[[-a,-b],[a,-b],[a,b],[-a,b]].map(([x,z])=>{const q=L(x,z);return [q[0],y,q[1]]});
  const eo=R4(hu+O,hv+O,y1-O*.42),ri=R4(hu-d/2,hv-d/2,y1+d/2*.42),ei=R4(cu+.35,cv+.35,y1-.2);
  for(let i=0;i<4;i++){const j=(i+1)%4;roofFace(Br,[eo[i],eo[j],ri[j],ri[i]],eo[i],eo[j],rc,RT);roofFace(Br,[ei[j],ei[i],ri[i],ri[j]],ei[j],ei[i],mul(rc,.9),RT);
    const a=ri[i],b=ri[j];Q(Bt,[a[0],a[1]+.15,a[2]],[b[0],b[1]+.15,b[2]],[b[0],b[1]+.3,b[2]],[a[0],a[1]+.3,a[2]],RIDGE)}
  /* 檐底板（外圈） */const w=[C(u0,v0),C(u1,v0),C(u1,v1),C(u0,v1)];for(let i=0;i<4;i++){const a=w[i],b=w[(i+1)%4];Q(Bt,[b[0],y1,b[1]],[a[0],y1,a[1]],eo[i],eo[(i+1)%4],SOFFIT)}
  /* 朝院的墙：frame 的「向外」= 朝院心 */
  const ck=[L(-cu,-cv),L(cu,-cv),L(cu,cv),L(-cu,cv)],ctr=L(0,0);
  for(let i=0;i<4;i++){const a=ck[(i+1)%4],b=ck[i],F=frame(a,b,a[0]+b[0]-ctr[0],a[1]+b[1]-ctr[1]);/* 内墙法线朝院心（参考点 = 院心关于墙中点的对称点） */
    const nb=Math.max(1,Math.round(F.L/3.6)),st=nsSt.map((Ls,li)=>({...Ls,shut:SHUT[Math.floor(hsh(id,230+i)*SHUT.length)],roles:Array.from({length:nb},(_,k)=>li===0?(hsh(id,240+i*8+k)<.35?'door':'winOpen'):(hsh(id,250+i*8+k)<.5?'winShut':'winOpen'))}));
    wallFace(Bt,F,st,nb,kind,mul(rec.wcol,.95),base,S)}
  /* 回廊：柱 + 额枋 + 单坡廊顶（墙 → 柱列） */
  const g=1.4,pu=cu-g,pv=cv-g,h0=nsSt[0].y1-base;
  if(pu>1&&pv>1){const pc=[L(-pu,-pv),L(pu,-pv),L(pu,pv),L(-pu,pv)],ya=base+Math.min(h0-.2,4);
    for(let i=0;i<4;i++){const a=pc[i],b=pc[(i+1)%4],Ln=Math.hypot(b[0]-a[0],b[1]-a[1]),n=Math.max(1,Math.round(Ln/2.4));for(let k=0;k<n;k++){const t=k/n;prism(Bt,a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,.22,base,ya-.25,MARBLE);S.col++}
      const F=frame(a,b,ctr[0]*2-(a[0]+b[0])/2,ctr[1]*2-(a[1]+b[1])/2);boxF(Bt,F,-.25,Ln+.25,ya-.25,ya+.25,-.25,.25,MARBLE)}
    const wl=R4(cu,cv,ya+1.1),pl=R4(pu-.3,pv-.3,ya+.2);for(let i=0;i<4;i++){const j=(i+1)%4;roofFace(Br,[pl[j],pl[i],wl[i],wl[j]],pl[j],pl[i],mul(rc,.92),RT)}}
  /* 院地 + 雨水池 */const fl=R4(pu>1?pu:cu,pv>1?pv:cv,base+.06);Q(Bt,fl[0],fl[1],fl[2],fl[3],PAVE,T_PAVE);
  const iu=Math.max(.8,(pu>1?pu:cu)*.4),iv=Math.max(.8,(pv>1?pv:cv)*.4),im=R4(iu,iv,base+.32),io=R4(iu+.25,iv+.25,base+.32);
  for(let i=0;i<4;i++){const j=(i+1)%4;Q(Bt,io[i],io[j],im[j],im[i],STONE);const a=io[i],b=io[j];Q(Bt,[a[0],base+.06,a[2]],[b[0],base+.06,b[2]],b,a,mul(STONE,.8))}
  Q(Bt,[im[0][0],base+.22,im[0][2]],[im[1][0],base+.22,im[1][2]],[im[2][0],base+.22,im[2][2]],[im[3][0],base+.22,im[3][2]],WATER,T_WATER);
  return true}

/* 平顶：屋面（铺地格）+ 女儿墙 + 压顶；有时一架葡萄棚 */
function flatRoof(Bt,rec,F4,S,pergola){const y1=rec.y1,k=rec.k,c=mul(rec.wcol,.84);Q(Bt,[k[0][0],y1,k[0][1]],[k[3][0],y1,k[3][1]],[k[2][0],y1,k[2][1]],[k[1][0],y1,k[1][1]],c,T_PAVE);
  for(const F of F4){const P=F.P;Q(Bt,P(0,y1,0),P(F.L,y1,0),P(F.L,y1+.7,0),P(0,y1+.7,0),rec.wcol);Q(Bt,P(0,y1,-.25),P(F.L,y1,-.25),P(F.L,y1+.7,-.25),P(0,y1+.7,-.25),mul(rec.wcol,.85));boxF(Bt,F,-.05,F.L+.05,y1+.7,y1+.85,-.3,.08,STONE)}
  if(pergola){const F=F4[0],F2=F4[2],d=Math.min(F4[1].L,F4[3].L);if(F.L>5&&d>5){const P=F.P,s0=F.L*.2,s1=F.L*.7,dd=-Math.min(3.5,d*.45);
    for(const s of [s0,s1])for(const dv of [-.6,dd]){const q=P(s,0,dv);prism(Bt,q[0],q[2],.12,y1,y1+2.1,TIMBER,4)}
    for(const dv of [-.6,dd])boxF(Bt,F,s0-.3,s1+.3,y1+2.1,y1+2.3,dv-.1,dv+.1,TIMBER,T_TIMBER);
    for(let s=s0;s<=s1;s+=.6)Q(Bt,P(s-.06,y1+2.32,-.4),P(s+.06,y1+2.32,-.4),P(s+.06,y1+2.32,dd-.2),P(s-.06,y1+2.32,dd-.2),TIMBER_D)}}}

/* 层表：底层高一点（铺面 / 仓门），柱廊户的临街底层要高过廊顶 */
function storeyTable(rec,ns,first=1.22){const H=rec.y1-rec.base,w=[first];for(let i=1;i<ns;i++)w.push(i===ns-1&&ns>2?.92:1);const s=w.reduce((a,b)=>a+b,0);let y=rec.base;return w.map(x=>{const y0=y;y+=H*x/s;return {y0,y1:y}})}

export function genHouse(Bt,Br,rec,pk,env){const f=rec.f,id=f.id,hsh=env.hsh,type=pk.type,k=rec.k;
  const cx=(k[0][0]+k[1][0]+k[2][0]+k[3][0])/4,cz=(k[0][1]+k[1][1]+k[2][1]+k[3][1])/4;
  const kind=type==='C'?(hsh(id,203)<.92?1:0):(rec.kind==='opus'?1:0);
  const S={win:0,col:0,whd:[],hsh,proj:.5,socle:type!=='C'||hsh(id,215)<.5};
  const F4=[0,1,2,3].map(i=>frame(k[i],k[(i+1)%4],cx,cz));
  /* 每条边向外到底账占地边还剩多少（box 版内缩了 8%）：凸出物 ≤ 这个 + 0.5 */
  const lp=[[f.p[0],f.p[1]],[f.p[2],f.p[3]],[f.p[4],f.p[5]],[f.p[6],f.p[7]]];
  const margin=F4.map(F=>{const m=F.P(F.L/2,0,0);let best=1e9;for(let i=0;i<4;i++){const a=lp[i],b=lp[(i+1)%4],dx=b[0]-a[0],dz=b[1]-a[1],L2=dx*dx+dz*dz||1,t=Math.max(0,Math.min(1,((m[0]-a[0])*dx+(m[2]-a[1])*dz)/L2));best=Math.min(best,Math.hypot(a[0]+t*dx-m[0],a[1]+t*dz-m[2]))}return Math.min(best,2)});
  const fe=pk.fr?pk.fr.e:Math.floor(hsh(id,204)*4),portico=!!rec.fr;
  const ns=pk.ns,st=storeyTable(rec,ns,type==='A'?1.25:type==='C'?1.1:1.08);
  if(portico&&type==='A'&&ns>1){const yt=Math.min(rec.y1-.1,rec.base+Math.min(rec.H*.72,4.3)+2.6);if(yt<st[1].y1-1.6)st[0].y1=st[1].y0=yt}
  const bwBase=type==='C'?4.6+hsh(id,205)*1.2:3.4+hsh(id,205)*1.2;
  const shutCol=SHUT[Math.floor(hsh(id,206)*SHUT.length)],rhythm=Math.floor(hsh(id,207)*3);/* 0 每间一窗、1 隔间、2 成对 */
  const winRole=(i,li,j)=>{const r=hsh(id,300+i*41+li*7+j);if(rhythm===1&&j%2===1)return 'blank';if(rhythm===2&&j%3===2)return 'blank';return r<.42?'winOpen':r<.82?'winShut':'winArch'};
  F4.forEach((F,i)=>{const nb=Math.max(1,Math.round(F.L/bwBase)),front=i===fe,back=i===(fe+2)%4;S.proj=Math.min(1.4,margin[i]+.5);
    const sts=st.map((L,li)=>{let roles;
      if(type==='A'){roles=Array.from({length:nb},(_,j)=>{if(li===0){if(front||(!back&&hsh(id,260+i*9+j)<.55))return hsh(id,270+i*9+j)<.62?'shopOpen':'shopShut';return hsh(id,280+i*9+j)<.25?'door':'blank'}
        if(back&&hsh(id,290+i*9+j)<.4)return 'blank';return winRole(i,li,j)})}
      else if(type==='B'){const dj=Math.floor(nb/2);roles=Array.from({length:nb},(_,j)=>{if(li===0){if(front&&j===dj)return 'door';return hsh(id,310+i*9+j)<(front?.3:.15)?'slit':'blank'}
        const r=hsh(id,320+i*9+j+li*3);return r<(front?.5:.38)?(r<.12?'winOpen':'winShut'):r<(front?.66:.48)?'slit':'blank'})}
      else{const ph=Math.floor(hsh(id,330+i)*2);roles=Array.from({length:nb},(_,j)=>{if(li===0){if(front&&(j+ph)%2===0)return 'whDoor';if(!front&&!back&&hsh(id,340+i*9+j)<.25)return 'whDoor';return 'whVent'}
        const r=hsh(id,350+i*9+j);return r<.45?'winArch':r<.65?'winShut':'whVent'})}
      return {...L,roles,shut:SHUT[Math.floor(hsh(id,360+i*5+li)*SHUT.length)]||shutCol}});
    S.whd=[];wallFace(Bt,F,sts,nb,kind,rec.wcol,rec.base,S);
    const bw=F.L/nb,P=F.P;
    /* A：临街挑廊（2 层底，不在柱廊上）+ 铺面遮阳布 */
    if(type==='A'&&front){const D=Math.min(1.1,margin[i]+.5);
      if(ns>=2&&D>.6&&hsh(id,208)<(portico?.45:.65)&&sts[1].y1-sts[1].y0>2.4){const yb=sts[1].y0,top=ns>2?sts[1].y1-.15:rec.y1-.3,s0=.25,s1=F.L-.25;
        boxF(Bt,F,s0,s1,yb-.22,yb,0,D,TIMBER,T_TIMBER);boxF(Bt,F,s0,s1,yb,yb+.95,D-.12,D,TIMBER,T_RAIL);
        for(let j=0;j<=nb;j++){const s=Math.max(s0,Math.min(s1,j*bw));boxF(Bt,F,s-.09,s+.09,yb,top,D-.2,D-.02,TIMBER_D);boxF(Bt,F,s-.07,s+.07,yb-1,yb-.22,0,D*.6,TIMBER_D)}
        if(ns>2){const q0=P(s0-.1,top+.02,0),q1=P(s1+.1,top+.02,0),q2=P(s1+.1,top-.45,D+.2),q3=P(s0-.1,top-.45,D+.2);roofFace(Br,[q3,q2,q1,q0],q3,q2,mul(rec.rcol,.95),RT)}}
      const cl=CLOTH[Math.floor(hsh(id,209)*CLOTH.length)],AD=Math.min(1.3,margin[i]+.5);
      if(!portico)for(let j=0;j<nb;j++){if(sts[0].roles[j]!=='shopOpen'&&sts[0].roles[j]!=='shopShut')continue;if(hsh(id,370+j)>.6)continue;
        const s0=j*bw+.12,s1=(j+1)*bw-.12,yt=sts[0].y0+SHOP.y1*(sts[0].y1-sts[0].y0)+.35,ys=yt-.75;
        Q(Bt,P(s0,yt,.02),P(s1,yt,.02),P(s1,ys,AD),P(s0,ys,AD),cl,T_STRIPE);Q(Bt,P(s0,ys,AD),P(s1,ys,AD),P(s1,ys-.3,AD),P(s0,ys-.3,AD),mul(cl,.85),T_STRIPE)}}
    /* C：主门木雨棚 + 吊货梁 */
    if(type==='C'&&front&&S.whd.length){const [s,top,w]=S.whd[Math.floor(hsh(id,210)*S.whd.length)],D=Math.min(1.4,margin[i]+.6);
      if(hsh(id,211)<.7){const y=top+.55,q0=P(s-w*.42,y+.5,0),q1=P(s+w*.42,y+.5,0),q2=P(s+w*.42,y,D),q3=P(s-w*.42,y,D);roofFace(Br,[q3,q2,q1,q0],q3,q2,mul(rec.rcol,.95),RT);for(const ds of [-w*.38,w*.38])boxF(Bt,F,s+ds-.08,s+ds+.08,y-.9,y,0,D*.8,TIMBER_D)}
      if(ns>=2||rec.H>7){const y=rec.y1-1.1;boxF(Bt,F,s-.13,s+.13,y,y+.28,0,Math.min(1.6,margin[i]+.9),TIMBER,T_TIMBER);const q=P(s,y,Math.min(1.5,margin[i]+.8));prism(Bt,q[0],q[2],.05,y-1.4,y,TIMBER_D,4)}}});
  /* 屋顶 */
  let court=false;
  if(rec.flat)flatRoof(Bt,rec,F4,S,hsh(id,212)<.35);
  else if(pk.court)court=courtyard(Bt,Br,rec,null,S,st,kind);
  if(!rec.flat&&!court)roofHip(Bt,Br,rec,type==='C'?true:hsh(id,213)<.22,kind,F4,type!=='B'||hsh(id,214)<.4);
  return {court,win:S.win,col:S.col}}
