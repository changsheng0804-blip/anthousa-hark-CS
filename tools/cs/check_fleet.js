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
/* cs15 · backlog 2（节奏）：① 船的真实速度不过 450 像素/小时，最后一段（离泊位 70 像素内）要明显慢下来、25 像素内不到巡航速度的一半；② 散场分三拨：码头上的人走的钟点聚成 3 堆，堆与堆之间空 0.2 小时以上，每堆至少 15% */
{const FS=F.FLEET;const V=FS.C.speed;let peak=0,s70=0,s25=0,bad2=[];
 for(const sh of FS.ships){if(!sh.path)continue;let L=0;for(let k=1;k<sh.path.length;k++)L+=Math.hypot(sh.path[k][0]-sh.path[k-1][0],sh.path[k][1]-sh.path[k-1][1]);
  let prev=FS.shipPos(sh,sh.t0),tr=0;const dt=.005;let lastV=1e9,mono=true;
  for(let c=sh.t0+dt;c<sh.t0+sh.ts+.05;c+=dt){if(sh.main&&c>=FS.C.snap-.01)break;const p=FS.shipPos(sh,c);const d=Math.hypot(p[0]-prev[0],p[1]-prev[1]);tr+=d;const v=d/dt;prev=p;if(tr>L)break;
   peak=Math.max(peak,v);const rem=L-tr;if(rem<=70&&rem>25)s70=Math.max(s70,v);if(rem<=25&&rem>3)s25=Math.max(s25,v);if(rem<=140){if(v>lastV*1.12+2)mono=false;lastV=Math.min(lastV,v)   /* 拐角处直线距离会让测出来的速度抖 10% 左右，容许 12% */}}
  if(!mono)bad2.push('速度回升')}
 const ok1=peak<=450&&s70<=.8*V&&s25<=.5*V&&!bad2.length;
 let ok2=true,info='';for(const Y of [40,50,57,60]){A.setYear(Y);const bs=F.FLEET.crowd(Y).crowd.filter(m=>m.kind==='work').map(m=>m.back).sort((a,b)=>a-b);const gr=[[bs[0]]];for(let i=1;i<bs.length;i++){if(bs[i]-bs[i-1]>=.2)gr.push([]);gr[gr.length-1].push(bs[i])}
  const small=gr.filter(g=>g.length<bs.length*.15).length;if(gr.length!==3||small){ok2=false;info+=' Y'+Y+':'+gr.length+'堆'}}
 console.log('ship peak speed',peak|0,'px/h (<=450); at 70px',s70|0,'at 25px',s25|0,bad2.join(),'| leave waves',ok2?'3 waves':info);if(!ok1||!ok2)bad++}
/* cs16 · backlog 3：会动的东西登记册（页面里的 csMovers）——每一种都要登记，并在 40/48/50/57/60 年逐种检查：land 的点要在人走的网上，water 的要在水里，off 的要在画外，absent 的不能有点 */
{const FL=w.__fleet;const REQ=['街上的人','摊子','烟囱的烟','工地上的人','面包房炉烟','早市队伍','码头人群','酒馆门口的人','大船队','旧版停泊船','旧版海上帆影','旧版进港船','赛马','海鸥'];
 const Wd=FL.FLEET.C.walk;const res={},miss=new Set(REQ);let badk=[];
 for(const Y of [40,48,50,57,60]){A.setYear(Y);const mv=FL.movers(Y);
  for(const m of mv){miss.delete(m.kind);const r=res[m.kind]||(res[m.kind]={n:0,bad:0,dom:m.domain,eg:null});
   for(const [x,y] of m.pts){r.n++;const c=FL.cell(x,y);let ok=true;
    if(m.domain==='land')ok=FL.walk(x,y);else if(m.domain==='water')ok=c==='w';else if(m.domain==='off')ok=x<0||y<0||x>Wd.W*Wd.R||y>Wd.H*Wd.R;else if(m.domain==='absent')ok=false;
    if(!ok){r.bad++;if(!r.eg)r.eg=[Y,x|0,y|0]}}}}
 const src=require('fs').readFileSync(__dirname+'/../../docs/living/nangang/index.html','utf8');
 const fr=src.slice(src.indexOf('function frame(now)'));const KNOWN=new Set(['NAMED','SCENES','city.landmarks','glows','bubbles','threads','head','buildingNow','chariots','gulls','seaShips','smokes']);
 const loops=[...new Set([...fr.matchAll(/for\(const\s+\[?[\w,\s]*\]?\s+of\s+([\w.]+)\)/g)].map(m=>m[1]))].filter(n=>!KNOWN.has(n));
 const tot=Object.values(res).reduce((a,r)=>a+r.bad,0);
 console.log('movers',Object.keys(res).length,'kinds; missing',[...miss].join(',')||'none','; off-domain',JSON.stringify(Object.fromEntries(Object.entries(res).filter(([k,r])=>r.bad).map(([k,r])=>[k,r.bad+'/'+r.n+' '+JSON.stringify(r.eg)]))),'; unregistered frame loops',loops.join(',')||'none');
 if(miss.size||tot)bad++}
const K={};for(const Y of [50]){A.setYear(Y);for(const [per,cl] of [['morning',7],['day',12]]){const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);for(const h of hs){const k=F.FLEET.keyOf(h,Y,per);if(k)K[per+k]=(K[per+k]||0)+1}}}console.log(JSON.stringify(K));console.log('distinct lines',lines.size,'near pairs',pairs,'same-line near pairs',dup);
{const FS=F.FLEET,ps=FS.C.pier_spots||[];const cnt=[];for(const Y of [40,50,57,60]){A.setYear(Y);const Rr=FS.crowd(Y);cnt.push(Rr.crowd.filter(m=>ps.some(s=>Math.hypot(m.spot[0]-s[0],m.spot[1]-s[1])<16)).length)}
 console.log('people standing on piers per year',cnt.join(','),'pier spots',ps.length);/* cs19 暂时放宽：原来要 ≥4 个站位、每年 ≥8 人，其中 3 个站位其实站在船上（查收图抓到）。backlog 1「真栈桥认不全」修好后改回 */ /* cs20：蒙版生成的 60 年画让真栈桥出到 5 个，恢复严格 */ if(ps.length<4||cnt.some(v=>v<8))bad++;
 const lo=[];for(const Y of [50,57,60]){const Rr=FS.crowd(Y);const per=ps.map(s=>Rr.crowd.filter(m=>Math.hypot(m.spot[0]-s[0],m.spot[1]-s[1])<16).length);lo.push(per.join('/'));if(per.some(v=>v<2))bad++}
 console.log('people per pier spot (year 50/57/60, each >=2)',lo.join(' | '))}
/* cs22 · 码头逐年长（所有者 2026-10-12 提）：栈桥按底账一座座建成。港挖成以前没有；最后一座不晚于最后一个关键年；至少分三个年份建成；
   每年的人只站在当年已建成的栈桥上，没建成的栈桥上没人、没有站位；建前两年是工地 */
{const FS=w.__fleet.FLEET,C=FS.C,D=C.docks||[];const yrs=new Set(D.map(d=>d.from));const hb=C.harbor_from||C.from;const last=Math.max(...(w.__anth.keys||[60]));
 let bad3=[];if(D.length<3)bad3.push('栈桥 '+D.length+' 座');if(yrs.size<3)bad3.push('只在 '+yrs.size+' 个年份建成');
 if(D.some(d=>d.from<=hb))bad3.push('港挖成那年就有栈桥');{const nb=D.filter(d=>(w.__anth.keys||[40,50,60]).some(k=>d.from>k-10&&!(d.borrow&&d.borrow[k]))).length;if(nb)bad3.push(nb+' 座没建成的栈桥借不到水（会平涂成色块）');const DP=w.__anth.SCENE?w.__anth.SCENE.dock_patch:null;}if(D.some(d=>d.from>60))bad3.push('60 年还没建完');
 const inD=(x,y,d)=>d.rects.some(r=>x>=r[0]-2&&x<=r[0]+r[2]+2&&y>=r[1]-2&&y<=r[1]+r[3]+2);let on=0;
 for(const Y of [36,40,45,50,57,60]){const R=FS.crowd(Y);const dead=D.filter(d=>d.from>Y);
  for(const m of R.crowd){if(dead.some(d=>inD(m.spot[0],m.spot[1],d)||m.path.some(p=>inD(p[0],p[1],d)))){on++;if(on<3)console.log('ON UNBUILT DOCK',Y,m.h.id)}}}
 const work=[40,45,50,57].map(Y=>D.filter(d=>d.from>Y&&d.from-2<=Y).length);
 {const Fl=w.__fleet.FLEET;if(Fl&&Fl.shipN){const ys=[34,40,45,48,57,60],ns=ys.map(Y=>Fl.shipN(Y)),pr=ys.map(Y=>Fl.crowd(Y).crowd.filter(c=>c.kind==='work').length);let mono=true;for(let k=1;k<ns.length;k++)if(ns[k]<ns[k-1]||pr[k]<pr[k-1]*0.8)mono=false;
  console.log('ships by year',ys.map((Y,k)=>Y+':'+ns[k]+'/'+pr[k]).join(' '),mono&&ns[0]<ns[ns.length-1]?'ok':'BAD ships do not grow with docks')}}
console.log('docks',D.length,'built years',[...yrs].sort().join(','),'people on unbuilt docks',on,'docks under construction (40/45/50/57)',work.join(','),bad3.join(' '));
 if(bad3.length||on)bad++}
console.log('fleet cards',n,'bad',bad+(dup>pairs*.03?1:0));
A.setYear(50);A.clock=12;const m=F.FLEET.crowd(50).crowd.find(m=>m.trade==='搬运工');w.__cs.openHouse(m.h.id);console.log(c.querySelector('h2').textContent,'|',c.querySelector('.now').textContent);
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
