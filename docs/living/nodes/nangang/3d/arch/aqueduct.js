/* buildings · 水道桥（底账 aqueduct 要素，如 aq_hadrian）：沿折线一路的拱廊。——Hark（CS线）2026-10-20
   桥面（水槽）按地面的大尺度平均高度走、几乎不起伏（重力输水），桥墩一直落到地面，
   所以谷地里自然出现两三层拱、坡上只剩一层或埋进地里。拱洞是贴图透明（alphaTest），两面各一张，不做逐拱几何。
   地面高：优先 ctx.reg.terrainY(x,z)（terrain 若把区外地形铺开可以写它），否则 ctx.ground。 */
import {linC,mul,quad} from './geo.js';
export const BAYA=9, TH=17, HW=2.6;
const STONE=linC([226,194,150]),CAP=linC([206,176,136]);
/* B = {arc, plain} */
export function aqueduct(ctx,B,f){const gy=(x,z)=>{const t=ctx.reg.terrainY;const v=t?t(x,z):null;return v==null?ctx.ground(x,z):v};
  const P=f.g,S=[];let s=0;for(let i=0;i<P.length-1;i++){const [ax,az]=P[i],[bx,bz]=P[i+1],L=Math.hypot(bx-ax,bz-az),n=Math.max(1,Math.ceil(L/6));for(let j=0;j<n;j++){const t=j/n;S.push({x:ax+(bx-ax)*t,z:az+(bz-az)*t,s:s+L*t})}s+=L}
  const last=P[P.length-1];S.push({x:last[0],z:last[1],s});
  for(const q of S)q.g=gy(q.x,q.z);
  const N=S.length,avg=(arr,i,w)=>{let a=0,c=0;for(let j=Math.max(0,i-w);j<=Math.min(N-1,i+w);j++){a+=arr[j];c++}return a/c};
  const g=S.map(q=>q.g),t0=S.map((q,i)=>Math.max(avg(g,i,45)+36,q.g+9)),top=S.map((q,i)=>avg(t0,i,8));
  /* 每个点的法线（相邻段平均） */
  for(let i=0;i<N;i++){const a=S[Math.max(0,i-1)],b=S[Math.min(N-1,i+1)],dx=b.x-a.x,dz=b.z-a.z,L=Math.hypot(dx,dz)||1;S[i].nx=-dz/L;S[i].nz=dx/L}
  /* r3：桥墩底按「桥身全宽下最低的网格地面」落（原来按中线的光滑 ground，横坡上一侧会悬空）；登记给 ground_check */
  for(const q of S){const F=ctx.footing([[q.x+q.nx*HW,q.z+q.nz*HW],[q.x-q.nx*HW,q.z-q.nz*HW],[q.x,q.z]]);q.g=Math.min(q.g,F.min)}
  for(let i=0;i<N-1;i++){const a=S[i],b=S[i+1];if(a.x<0||a.z<0||a.x>ctx.W||a.z>ctx.H)continue;ctx.foot({kind:'aqueduct',id:f.id+':'+i,pts:[[a.x+a.nx*HW,a.z+a.nz*HW],[b.x+b.nx*HW,b.z+b.nz*HW],[b.x-b.nx*HW,b.z-b.nz*HW],[a.x-a.nx*HW,a.z-a.nz*HW]],bottom:Math.min(a.g,b.g)-4,floor:1e9})}
  for(let i=0;i<N-1;i++){const a=S[i],b=S[i+1],ta=top[i],tb=top[i+1],da=ta-4,db=tb-4,ya=a.g-4,yb=b.g-4,ua=a.s/BAYA,ub=b.s/BAYA;
    const vv=(d,y)=>1-(d-y)/TH;
    for(const sd of [1,-1]){const ax=a.x+a.nx*HW*sd,az=a.z+a.nz*HW*sd,bx=b.x+b.nx*HW*sd,bz=b.z+b.nz*HW*sd;
      quad(B.arc,[ax,ya,az],[bx,yb,bz],[bx,db,bz],[ax,da,az],STONE,[ua,vv(da,ya)],[ub,vv(db,yb)],[ub,1],[ua,1]);
      /* 水槽侧墙（实心）+ 压顶檐 */
      quad(B.plain,[ax,da,az],[bx,db,bz],[bx,tb,bz],[ax,ta,az],mul(STONE,.95));
      const ox=a.nx*.6*sd,oz=a.nz*.6*sd,px=b.nx*.6*sd,pz=b.nz*.6*sd;quad(B.plain,[ax+ox,da-.1,az+oz],[bx+px,db-.1,bz+pz],[bx+px,db+.9,bz+pz],[ax+ox,da+.9,az+oz],CAP)}
    /* 拱廊底面（桥墩之间的拱腹看不见，给一条深色顶） + 水槽顶盖 */
    const l=[a.x+a.nx*HW,a.z+a.nz*HW],r=[a.x-a.nx*HW,a.z-a.nz*HW],l2=[b.x+b.nx*HW,b.z+b.nz*HW],r2=[b.x-b.nx*HW,b.z-b.nz*HW];
    quad(B.plain,[l[0],ta,l[1]],[l2[0],tb,l2[1]],[r2[0],tb,r2[1]],[r[0],ta,r[1]],CAP);
    quad(B.plain,[r[0],da,r[1]],[r2[0],db,r2[1]],[l2[0],db,l2[1]],[l[0],da,l[1]],mul(STONE,.45))}
  return N}
