/* props/site.js —— 摆放用的地理小工具（只读底账，不改）：多边形点测、房子占地网格、哪里是水/地、栈桥的根和头。
   归 props+flora 代理（CS 线，lookdev 第 2 轮）。 */
export function inRings(g,x,z){/* g: MultiPolygon [[ring, hole…]…]，奇偶规则 */let ins=false;for(const P of g)for(const r of P){for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])ins=!ins}}return ins}
export function inPoly(r,x,z){let ins=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])ins=!ins}return ins}
export function bboxOf(g){let x0=1e9,x1=-1e9,z0=1e9,z1=-1e9;for(const P of g)for(const r of P)for(const p of r){x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);z0=Math.min(z0,p[1]);z1=Math.max(z1,p[1])}return {x0,x1,z0,z1}}
export function segDist(x,z,a,b){const dx=b[0]-a[0],dz=b[1]-a[1],L2=dx*dx+dz*dz||1;let t=((x-a[0])*dx+(z-a[1])*dz)/L2;t=Math.max(0,Math.min(1,t));return Math.hypot(x-a[0]-t*dx,z-a[1]-t*dz)}

/* 当年的「场地」：房子网格、地标矩形、港池、石堤、栈桥。build 里每次现建（年份会变） */
export function makeSite(ctx){const {by,W,live}=ctx,CS=16,grid=new Map();
  const key=(i,j)=>i*4096+j;
  const houses=[];for(const f of by.house)if(live(f)){const p=f.p,q=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];houses.push(q);
    const xs=q.map(v=>v[0]),zs=q.map(v=>v[1]);for(let i=Math.floor((Math.min(...xs)-2)/CS);i<=Math.floor((Math.max(...xs)+2)/CS);i++)for(let j=Math.floor((Math.min(...zs)-2)/CS);j<=Math.floor((Math.max(...zs)+2)/CS);j++){const k=key(i,j);(grid.get(k)||grid.set(k,[]).get(k)).push(q)}}
  const lms=(by.landmark||[]).filter(live).map(f=>({f,r:ctx.geom.rectOf(f.g),poly:f.g}));
  const harbors=(by.water||[]).filter(f=>f.k==='harbor'&&live(f));
  const moles=(by.mole||[]).filter(live);
  const piers=(by.pier||[]).filter(live);
  const land=by.land[0];
  /* 点到房子（带边距 m）：把四边形向外推 m 再测 */
  function inHouse(x,z,m=1){const L=grid.get(key(Math.floor(x/CS),Math.floor(z/CS)));if(!L)return false;for(const q of L){const cx=(q[0][0]+q[1][0]+q[2][0]+q[3][0])/4,cz=(q[0][1]+q[1][1]+q[2][1]+q[3][1])/4;
      const e=q.map(v=>{const dx=v[0]-cx,dz=v[1]-cz,d=Math.hypot(dx,dz)||1;return [v[0]+dx/d*m*1.4,v[1]+dz/d*m*1.4]});if(inPoly(e,x,z))return true}return false}
  const inLandmark=(x,z,m=0)=>lms.some(l=>{const r=l.r,dx=x-r.cx,dz=z-r.cz,u=dx*r.ax+dz*r.az,v=-dx*r.az+dz*r.ax;return Math.abs(u)<=r.hu+m&&Math.abs(v)<=r.hv+m});
  const inMole=(x,z)=>moles.some(f=>inRings(f.g,x,z));
  const onPier=(x,z,m=0)=>piers.some(f=>segDist(x,z,f.g[0],f.g[1])<f.w/2+m);
  /* 水：在当年港池里（且不在石堤上），或者区内地形落到海平面以下；区外（x>W）只认港池 */
  function isWater(x,z){if(inMole(x,z))return false;if(harbors.some(f=>inRings(f.g,x,z)))return true;if(x>W-1||x<1||z<1||z>ctx.H-1)return false;return ctx.ground(x,z)<-2.5}
  /* 地：陆地多边形里且地面高于海平面，或在石堤上 */
  function isLand(x,z){if(inMole(x,z))return true;if(x>W-1)return false;return ctx.ground(x,z)>.6&&inRings(land.g,x,z)}
  /* 摆东西的高：石堤顶 3，栈桥面 1.6，其余跟地面 */
  function yAt(x,z){if(inMole(x,z))return Math.max(3,ctx.ground(x,z));return Math.max(0,ctx.ground(x,z))}
  return {houses,inHouse,inLandmark,inMole,onPier,isWater,isLand,yAt,lms,harbors,moles,piers,land}}

/* 栈桥：哪头在岸上（根）、哪头伸进水里（头） */
export function pierEnds(site,f){const [a,b]=f.g;const wa=site.isWater(a[0],a[1])?1:0,wb=site.isWater(b[0],b[1])?1:0;
  /* 两头都算水或都算地时，用离岸更远的那头当头：往外 6 像素看是不是水 */
  if(wa!==wb)return wb?{root:a,tip:b}:{root:b,tip:a};
  const dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),ux=dx/L,uz=dz/L;const sa=site.isWater(a[0]-ux*6,a[1]-uz*6)?1:0,sb=site.isWater(b[0]+ux*6,b[1]+uz*6)?1:0;
  return sb>=sa?{root:a,tip:b}:{root:b,tip:a}}
