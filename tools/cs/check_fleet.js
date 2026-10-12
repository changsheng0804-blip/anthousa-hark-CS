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
 const dry=(x,y)=>{for(const[dx,dy]of[[0,0],[6,0],[-6,0],[0,6],[0,-6]]){const c=ch(x+dx,y+dy);if(c!=='w')return true}return false};
 let wet=0,tot=0,swet=0,stot=0,eg=null;
 for(const Y of [40,50,57,60]){A.setYear(Y);const R=F.FLEET.crowd(Y);
  for(let cl=6;cl<23.5;cl+=.05){for(const m of R.crowd){const q=F.FLEET.pos(m,cl,R.g);if(!q)continue;tot++;if(!dry(q[0],q[1])){wet++;if(!eg)eg=[Y,cl.toFixed(2),m.kind,m.trade,q[0]|0,q[1]|0]}}
   if(process.env.DUMP&&Y===50)for(const m of R.crowd){const q=F.FLEET.pos(m,cl,R.g);if(q)require('fs').appendFileSync(process.env.DUMP,(q[0]|0)+','+(q[1]|0)+','+m.kind+'\\n')}
   for(const sh of F.FLEET.ships){if(cl<sh.t0)continue;const p=F.FLEET.shipPos(sh,cl);stot++;if(ch(p[0],p[1])!=='w')swet++}}}
 console.log('people in water',wet,'/',tot,eg?JSON.stringify(eg):'','ships on land',swet,'/',stot);if(wet||swet)bad++}
const K={};for(const Y of [50]){A.setYear(Y);for(const [per,cl] of [['morning',7],['day',12]]){const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);for(const h of hs){const k=F.FLEET.keyOf(h,Y,per);if(k)K[per+k]=(K[per+k]||0)+1}}}console.log(JSON.stringify(K));console.log('distinct lines',lines.size,'near pairs',pairs,'same-line near pairs',dup);
console.log('fleet cards',n,'bad',bad+(dup>pairs*.03?1:0));
A.setYear(50);A.clock=12;const m=F.FLEET.crowd(50).crowd.find(m=>m.trade==='搬运工');w.__cs.openHouse(m.h.id);console.log(c.querySelector('h2').textContent,'|',c.querySelector('.now').textContent);
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
