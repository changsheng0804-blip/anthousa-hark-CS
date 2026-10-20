/* house_kit · 三种民居类型怎么挑（确定性：只看底账属性 + 户 id 的种子）。——Hark（CS线）2026-10-20
   类型只决定「长什么样」，占地（p，box 版的 0.92 内缩 + 柱廊退进）和檐高（ht×1.15 像素）一律照 box 版，不改。
   A 临街公寓 insula：2–4 层，底层一排铺面（tabernae），上层窗 + 百叶，常有木挑廊（maenianum）、遮阳布。
   B 院宅 domus：临街几乎是一堵素墙，一扇门、几个高窗；占地够大就开内院（回廊柱 + 雨水池 impluvium，屋面向院里收）。
   C 仓 / 作坊：近港或码头 / 仓 / 水务户；砖石夹层墙、砖拱大门、高处通风缝、顺长边的两坡顶、门上木雨棚、吊货梁。
   规则（按顺序，先中先得）：
     ty 以 lm: 开头（喷泉、面包台阶、肉市这类小地标户）→ 不换，照旧 box。
     C：fn ∈ {dock, horrea, water} 或 ty = hall，或 fn ≠ homes 且离港池/栈桥 < 36 像素（≈30 m）且种子 < 0.7。
     A：层数 ≥ 2，且（fn ∈ {shops, market} 或 ty ∈ {row, insula, flat} 或 po = 1）且临 m/s 街（ty = insula 不要求临街）；
        另外 ty = casa、fn = homes、层数 ≥ 3、临 m 街的，种子 < 0.5 也当 A（主街上的出租楼）。
     B：其余。B 开内院的条件：不是平顶、短边 ≥ 12 像素、面积 ≥ 200 平方像素、层数 ≤ 3。
   层数 = round(檐高米 / 3.1)，限 1–4；C 是 round(檐高米 / 4.2)，限 1–2（仓的层高大）。 */
export const MPP=.84;
export function storeys(H,type){const m=H*MPP;return type==='C'?Math.max(1,Math.min(2,Math.round(m/4.2))):Math.max(1,Math.min(4,Math.round(m/3.1)))}
const RANK={m:0,s:1,c:2,l:3};
/* 临街边：rec.k 的 4 条边里，中点离哪条街（任何等级）最近；优先 m/s。柱廊户直接用柱廊那条边。 */
export function frontEdge(rec,env){if(rec.fr)return {e:rec.fr.e,k:rec.fr.k,portico:true};
  const k=rec.k;let best=null;
  for(let e=0;e<4;e++){const a=k[e],b=k[(e+1)%4],mx=(a[0]+b[0])/2,mz=(a[1]+b[1])/2,ex=b[0]-a[0],ez=b[1]-a[1],L=Math.hypot(ex,ez)||1;
    for(const s of env.streetsNear(mx,mz)){const [ax,az,bx,bz]=s.g,dx=bx-ax,dz=bz-az,L2=dx*dx+dz*dz||1,t=Math.max(0,Math.min(1,((mx-ax)*dx+(mz-az)*dz)/L2)),d=Math.hypot(ax+t*dx-mx,az+t*dz-mz);
      if(Math.abs((dx*ex+dz*ez)/Math.sqrt(L2)/L)<.6)continue;/* 街要大致顺着这条边 */
      const lim=s.w/2+(s.k==='m'?12:7);if(d>lim)continue;const sc=d+RANK[s.k]*4;if(!best||sc<best.sc)best={e,k:s.k,sc}}}
  return best}
export function area(p){let a=0;for(let i=0;i<4;i++){const j=(i+1)%4;a+=p[2*i]*p[2*j+1]-p[2*j]*p[2*i+1]}return Math.abs(a)/2}
export function pick(rec,env){const f=rec.f,fn=f.fn||'homes',ty=f.ty||'casa',hsh=env.hsh;
  if(ty.startsWith('lm:'))return null;
  const cx=(rec.k[0][0]+rec.k[2][0])/2,cz=(rec.k[0][1]+rec.k[2][1])/2,hd=env.harbourDist(cx,cz),fr=frontEdge(rec,env);
  const [u0,u1,v0,v1]=rec.u,short=Math.min(u1-u0,v1-v0),A=area(f.p);
  let type='B';
  if(fn==='dock'||fn==='horrea'||fn==='water'||ty==='hall'||(fn!=='homes'&&hd<36&&hsh(f.id,201)<.7))type='C';
  else{const ns=storeys(rec.H,'A'),street=fr&&(fr.k==='m'||fr.k==='s');
    if(ns>=2&&((fn==='shops'||fn==='market'||ty==='row'||ty==='insula'||ty==='flat'||f.po===1)&&(street||ty==='insula')))type='A';
    else if(ns>=3&&fn==='homes'&&fr&&fr.k==='m'&&hsh(f.id,202)<.5)type='A'}
  const court=type==='B'&&!rec.flat&&short>=12&&A>=200&&storeys(rec.H,'B')<=3;
  return {type,fr,court,ns:storeys(rec.H,type),hd}}
