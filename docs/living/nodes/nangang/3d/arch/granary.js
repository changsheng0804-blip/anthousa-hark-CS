/* buildings · 国家粮仓（horrea）：一排并肩的山墙长仓，山墙朝短边（码头一侧），砖石夹层墙、扶壁、拱门、高窗、缓坡瓦顶。
   位置和占地 = 底账 landmark 的矩形（rectOf），只在占地内排列，长仓数按占地宽取整。——Hark（CS线）2026-10-20 */
import {linC,mul,wall,quad,tri,roofFace,box} from './geo.js';
import {RT} from './house.js';
export const GABLE_WALL_FRAC=.7;
const STONE=linC([246,226,188]),ROOF=[178,104,62];
/* B = {gwall, ggable, roof, plain} */
/* r3_ground_scale：每座长仓按自己的占地落地（地坪 = 占地下最高地面，墙脚伸到最低地面 −0.6，坡上不再漏空/埋门）；hs = 史诗夸张（高 ×1.2，占地不动） */
export function granary(ctx,B,f,r,base0,hs=1){const {hsh}=ctx,C=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v];
  const gap=5,n=Math.max(2,Math.round(r.hu*2/23)),bw=(r.hu*2-4-(n-1)*gap)/n,v0=-r.hv+2,v1=r.hv-2,len=v1-v0;
  for(let i=0;i<n;i++){const ua=-r.hu+2+i*(bw+gap),ub=ua+bw;
    const FP=[C(ua-1,v0-1),C(ub+1,v0-1),C(ub+1,v1+1),C(ua-1,v1+1)],FT=ctx.footing(FP,2.5),base=FT.max+.08,bot=FT.min-.6;ctx.foot({kind:'landmark:granary',id:f.id+':'+i,pts:FP,bottom:bot,floor:base});
    const h=(15.5+2.5*hsh(f.seed,i))*hs,y1=base+h,rise=bw/2*.46,yr=y1+rise,um=(ua+ub)/2;
    const wcol=mul(STONE,.94+.1*hsh(f.seed,10+i)),rcol=linC(mul(ROOF,.9+.18*hsh(f.seed,20+i)));
    /* 长墙（沿 v）：贴图 2 开间一张，v 0–1 = 墙高 */
    const nb=Math.max(1,Math.round(len/14));
    for(const [ux,flip] of [[ua,1],[ub,0]]){const a=C(ux,flip?v1:v0),b=C(ux,flip?v0:v1);wall(B.gwall,a,b,bot,base,mul(wcol,.8),nb,.01,.01);wall(B.gwall,a,b,base,y1,wcol,nb,0,1);
      /* 扶壁：开间之间，贴图里实墙那一段（u .44–.56） */const out=flip?-1:1;
      for(let j=1;j<nb*2;j++){const v=v0+len*j/(nb*2),w=.55,d=1.0*out,hb=h*.78;const p=[C(ux,v-w),C(ux+d,v-w),C(ux+d,v+w),C(ux,v+w)];
        wall(B.gwall,p[0],p[1],bot,base+hb,wcol,.12,0,hb/h,.44);wall(B.gwall,p[1],p[2],bot,base+hb,wcol,.12,0,hb/h,.44);wall(B.gwall,p[2],p[3],bot,base+hb,wcol,.12,0,hb/h,.44);
        /* 斜顶 */quad(B.plain,[p[1][0],base+hb,p[1][1]],[p[2][0],base+hb,p[2][1]],[p[3][0],base+hb+.9,p[3][1]],[p[0][0],base+hb+.9,p[0][1]],mul(wcol,.85))}}
    /* 山墙（两端）：v 0–.7 墙身，山尖到 1 */
    for(const [vv,s] of [[v1,1],[v0,-1]]){const a=s>0?C(ua,vv):C(ub,vv),b=s>0?C(ub,vv):C(ua,vv),m=C(um,vv);
      wall(B.ggable,a,b,bot,base,mul(wcol,.8),1,.005,.005);wall(B.ggable,a,b,base,y1,wcol,1,0,GABLE_WALL_FRAC);
      tri(B.ggable,[a[0],y1,a[1]],[b[0],y1,b[1]],[m[0],yr,m[1]],wcol,[0,GABLE_WALL_FRAC],[1,GABLE_WALL_FRAC],[.5,1]);
      /* 浮雕：壁柱（两角 + 两道）、两道腰线、檐口线。凸出来的面在低太阳下受光，背光的山墙上也读得出结构 */
      const ou=s*.55,PL=(u,w)=>{const p0=C(u-w,vv),p1=C(u+w,vv),p2=C(u+w,vv+ou),p3=C(u-w,vv+ou);for(const [x,y] of [[p0,p3],[p3,p2],[p2,p1]])wall(B.gwall,x,y,bot,y1,wcol,.12,0,1,.44)};
      for(const t of [.03,.97,.3,.7])PL(ua+bw*t,.5);
      for(const [hh,th,oo] of [[h*.36,.35,.45],[h*.7,.35,.45],[h,.55,.75]]){const yb=base+hh-th,yt=base+hh,q0=C(ua-.3,vv+s*oo),q1=C(ub+.3,vv+s*oo),r0=C(ua-.3,vv),r1=C(ub+.3,vv);
        wall(B.plain,q0,q1,yb,yt,mul(wcol,.92),0,0,0);quad(B.plain,[r0[0],yt,r0[1]],[r1[0],yt,r1[1]],[q1[0],yt,q1[1]],[q0[0],yt,q0[1]],mul(wcol,1.02));quad(B.plain,[r0[0],yb,r0[1]],[q0[0],yb,q0[1]],[q1[0],yb,q1[1]],[r1[0],yb,r1[1]],mul(wcol,.6))}
      /* 大门上的单坡瓦檐 + 两根木撑（码头卸货时遮雨） */
      const pw=bw*.44,po=2.6*s,yh=base+h*.68,yl=base+h*.58,P=(u,v,y)=>{const q=C(u,v);return [q[0],y,q[1]]};
      const w0=P(um-pw,vv,yh),w1=P(um+pw,vv,yh),o1=P(um+pw,vv+po,yl),o0=P(um-pw,vv+po,yl);roofFace(B.roof,[o0,o1,w1,w0],o0,o1,rcol,RT);
      quad(B.plain,[w0[0],yh-.35,w0[2]],[w1[0],yh-.35,w1[2]],[o1[0],yl-.35,o1[2]],[o0[0],yl-.35,o0[2]],mul(rcol,.35));
      for(const du of [-pw*.92,-pw*.36,pw*.36,pw*.92]){const q=C(um+du,vv+po*.85);box(B.plain,q,.22,.22,bot,yl,r.ax,r.az,linC([96,66,40]),false)}}
    /* 瓦顶：两坡，出檐 .7、山墙外挑 .9 */
    const O=.7,G=.9,e=(u,v,y)=>{const q=C(u,v);return [q[0],y,q[1]]};
    const L0=e(ua-O,v0-G,y1-O*.46),L1=e(ua-O,v1+G,y1-O*.46),R0=e(ub+O,v0-G,y1-O*.46),R1=e(ub+O,v1+G,y1-O*.46),T0=e(um,v0-G,yr+.15),T1=e(um,v1+G,yr+.15);
    roofFace(B.roof,[L0,L1,T1,T0],L0,L1,rcol,RT);roofFace(B.roof,[R1,R0,T0,T1],R1,R0,rcol,RT);
    /* 屋脊压条 + 檐底 */const ridge=mul(rcol,.7);quad(B.plain,[T0[0]-r.ax*.35,T0[1]+.25,T0[2]-r.az*.35],[T1[0]-r.ax*.35,T1[1]+.25,T1[2]-r.az*.35],[T1[0]+r.ax*.35,T1[1]+.25,T1[2]+r.az*.35],[T0[0]+r.ax*.35,T0[1]+.25,T0[2]+r.az*.35],ridge)}
  return n}
