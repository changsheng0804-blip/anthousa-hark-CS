// 粮船日：敲门卡不出错、邻居不重样、来码头的人都是底账里干这一行的人家
const src=require('fs').readFileSync((process.env.CSJS||'/workspace/work/csjs')+'/run_ng.js','utf8').split('const w=dom.window;')[0];eval(src+`
const w=dom.window;setTimeout(()=>{try{const A=w.__anth,F=w.__fleet;const c=w.document.getElementById('card');let bad=0,n=0,dup=0,lines=new Set(),pairs=0;
const fam=(h,Y)=>{const hh=A.household(h);let f=hh.fams[0];for(const x of hh.fams)if(x.B<=Y)f=x;return f};
for(const Y of [40,50,57]){A.setYear(Y);const R=F.FLEET.crowd(Y);
  for(const m of R.crowd){if(m.kind==='work'&&fam(m.h,Y).trade!==m.trade){bad++;console.log('WRONGTRADE',Y,m.h.id)}if(!(m.h.built<=Y&&m.h.destroyed>Y)){bad++;console.log('DEADHOME',Y,m.h.id)}}
  for(const t of R.tav)if(fam(t,Y).trade!=='酒馆老板'){bad++;console.log('NOTTAVERN')}
  for(const [per,cl] of [['morning',7],['day',12],['evening',19],['night',23]]){A.clock=cl;
    const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);const got=[];
    for(const h of hs){const l=F.FLEET.line(h,Y,per);if(l){got.push([h,l]);lines.add(l)}}
    for(let i=0;i<got.length;i++)for(let j=i+1;j<got.length;j++){const a=got[i][0],b=got[j][0];if(Math.hypot(a.cx-b.cx,a.cy-b.cy)<60){pairs++;if(got[i][1]===got[j][1])dup++}}
    for(let i=0;i<got.length;i+=9){w.__cs.openHouse(got[i][0].id);n++;const t=c.innerHTML;if(/undefined|NaN|null|\\{k\\}/.test(t.replace(/csans|data-[a-z]+=/g,''))){bad++;if(bad<4)console.log('BAD',c.textContent.slice(0,200))}}
  }
  console.log('Y',Y,'crowd',R.crowd.length,'kids',R.crowd.filter(m=>m.kind==='kid').length,'taverns',R.tav.length,'granary',R.g&&R.g.id)}
/* cs7 再来（所有者：人从海里走过去）→ 硬规则：人只走在陆地和港墙上，船只在水上 */
{const W=F.FLEET.C.walk;const ch=(x,y)=>{const j=Math.floor(y/W.R),i=Math.floor(x/W.R);return j<0||i<0||j>=W.H||i>=W.W?'w':W.quay[j*W.W+i]};
 const dry=(x,y)=>{const c=ch(x,y);return c!=='w'&&c!=='x'};   /* 收紧：本格必须是人走的网（底账和画都是陆地） */
 let wet=0,tot=0,swet=0,stot=0,eg=null;
 for(const Y of [40,50,57,60]){A.setYear(Y);const R=F.FLEET.crowd(Y);
  for(let cl=6;cl<23.5;cl+=.05){for(const m of R.crowd){const q=F.FLEET.pos(m,cl,R.g);if(!q)continue;tot++;if(!dry(q[0],q[1])){wet++;if(!eg)eg=[Y,cl.toFixed(2),m.kind,m.trade,q[0]|0,q[1]|0]}}
   if(process.env.DUMP&&Y===50)for(const m of R.crowd){const q=F.FLEET.pos(m,cl,R.g);if(q)require('fs').appendFileSync(process.env.DUMP,(q[0]|0)+','+(q[1]|0)+','+m.kind+'\\n')}
   if(Math.abs(cl-20)<.026)for(const h of R.tav)for(const[x,y]of F.FLEET.tavPeople(h)){tot++;if(!dry(x,y)){wet++;if(!eg)eg=[Y,'tavern',h.id]}}
   for(const sh of F.FLEET.ships){if(cl<sh.t0)continue;const p=F.FLEET.shipPos(sh,cl);stot++;if(ch(p[0],p[1])!=='w')swet++;if(!F.FLEET.C.speed||F.FLEET.C.speed>450||sh.ts<1.2)swet++   /* cs8 再来：船太快。大船一小时走不过 450 像素（约 30 米格子），整支船队要两三个钟头才进完港 */}}}
 console.log('people in water',wet,'/',tot,eg?JSON.stringify(eg):'','ships on land',swet,'/',stot);if(wet||swet)bad++}
/* cs9 再来（所有者：街上的人还在海里走——city.json 的路是别的街区抄来的）→ 城里所有沿街走的人、摊子：每个位置都要在人走的网上 */
{const W=F.FLEET.C.walk;const ch=(x,y)=>{const j=Math.floor(y/W.R),i=Math.floor(x/W.R);return j<0||i<0||j>=W.H||i>=W.W?'w':W.quay[j*W.W+i]};
 let n=0,wet=0,eg=null;for(const r of A.city.roads){for(let k=0;k<r.pts.length-1;k++){const a=r.pts[k],b=r.pts[k+1];const L=Math.hypot(b[0]-a[0],b[1]-a[1]);for(let u=0;u<=L;u+=4){const x=a[0]+(b[0]-a[0])*u/L,y=a[1]+(b[1]-a[1])*u/L;n++;const c=ch(x,y);if(c==='w'||c==='x'){wet++;if(!eg)eg=[r.id,x|0,y|0]}}}}
 console.log('street points in water',wet,'/',n,eg?JSON.stringify(eg):'');if(wet||!n)bad++}
/* cs11 · backlog 1：街上的人（520 个）和摊子（420 个）按全街走一遍，每个位置（含 ±8 像素的偏移）都要在人走的网上，不靠页面「遇水不画」兜底 */
{const FL=w.__fleet;let n=0,wet=0,eg=null,sn=0,swet=0,seg=null;
 for(const wk of FL.walkers){const r=FL.roads[wk.r];for(let s=0;s<=r.L;s+=3){const q=FL.walkerXY(wk,s);n++;if(!FL.walk(q[0],q[1])){wet++;if(!eg)eg=[wk.r,s|0,q[0]|0,q[1]|0]}}}
 for(const st of FL.stalls){sn++;if(!FL.walk(st.x,st.y)){swet++;if(!seg)seg=[st.x|0,st.y|0]}}
 console.log('walker samples in water',wet,'/',n,eg?JSON.stringify(eg):'','stalls in water',swet,'/',sn,seg?JSON.stringify(seg):'');if(wet||swet||!n)bad++}
/* cs12 · backlog 1：横贯南港的宽街（画上沙色的那条大街，y 从左 645 到右 560）上，每 100 像素一段至少有一个摊子或走的人（街道中线是从画上量的，不读 city.json） */
{const FL=w.__fleet;const WY=[[0,645],[200,638],[400,636],[600,626],[800,615],[1000,606],[1200,595],[1400,590],[1600,572],[1819,560]];
 const cy=x=>{for(let i=0;i<WY.length-1;i++)if(x<=WY[i+1][0]){const t=(x-WY[i][0])/(WY[i+1][0]-WY[i][0]);return WY[i][1]+t*(WY[i+1][1]-WY[i][1])}return WY[WY.length-1][1]};
 const cnt=new Array(18).fill(0);const near=(x,y)=>{if(x<0||x>=1800)return;if(Math.abs(y-cy(x))<45)cnt[Math.floor(x/100)]++};
 for(const st of FL.stalls)near(st.x,st.y);
 for(const wk of FL.walkers){const r=FL.roads[wk.r];for(let s=0;s<=r.L;s+=40){const q=FL.walkerXY(wk,s);near(q[0],q[1])}}
 const empty=cnt.map((c,i)=>c?-1:i*100).filter(i=>i>=0);
 console.log('wide street empty 100px segments',empty.length,'/ 18',JSON.stringify(empty),'counts',cnt.join(','));if(empty.length)bad++}
const K={};for(const Y of [50]){A.setYear(Y);for(const [per,cl] of [['morning',7],['day',12]]){const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);for(const h of hs){const k=F.FLEET.keyOf(h,Y,per);if(k)K[per+k]=(K[per+k]||0)+1}}}console.log(JSON.stringify(K));console.log('distinct lines',lines.size,'near pairs',pairs,'same-line near pairs',dup);
console.log('fleet cards',n,'bad',bad+(dup>pairs*.03?1:0));
A.setYear(50);A.clock=12;const m=F.FLEET.crowd(50).crowd.find(m=>m.trade==='搬运工');w.__cs.openHouse(m.h.id);console.log(c.querySelector('h2').textContent,'|',c.querySelector('.now').textContent);
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
