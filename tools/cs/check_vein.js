const src=require('fs').readFileSync((process.env.CSJS||'/workspace/work/csjs')+'/run_ng.js','utf8').split('const w=dom.window;')[0];eval(src+`
const w=dom.window;setTimeout(()=>{try{const A=w.__anth,V=w.__vein;const c=w.document.getElementById('card');let bad=0,n=0;const out=[];
V.veinToggle(true);
for(let Y=30;Y<=60;Y++){A.setYear(Y);if(Y<33)continue;const R=V.VEIN.at(Y);
  // 一致：面包房那栋房子，敲门卡上的那家人这一年就是面包师
  for(const b of R.bak){const f=V.famAt(A.household(b.h),Y);if(f.trade!=='面包师'){bad++;console.log('NOTBAKER',Y,b.h.id,f.trade)}if(!(b.h.built<=Y&&b.h.destroyed>Y)){bad++;console.log('DEADBAKERY',Y,b.h.id)}}
  for(const s of R.steps){if(s.lost&&s.lost.destroyed!==Y){bad++;console.log('LOSTWRONG',Y)}}
  out.push(Y+':'+R.gra.map(g=>g.id.slice(7,10)).join('+')+' 炉'+R.bak.length+' 阶'+R.steps.length+(R.steps.some(s=>s.lost)?' 断'+R.steps.filter(s=>s.lost).length:'')+(R.bak.some(b=>b.detour)?' 绕'+R.bak.filter(b=>b.detour).length:''));
  const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);for(let i=0;i<hs.length;i+=97){V.veinCard(hs[i]);n++;const t=c.innerHTML;if(/undefined|NaN|null|\\[object/.test(t)){bad++;if(bad<5)console.log('BAD',c.textContent.slice(0,200))}}}
console.log(out.join(' | '));console.log('vein cards',n,'bad',bad);
A.setYear(48);const R=V.VEIN.at(48);const s=R.steps.find(s=>s.lost);if(s){const h=A.houses.filter(h=>h.built<=48&&h.destroyed>48).sort((a,b)=>((a.cx-s.x)**2+(a.cy-s.y)**2)-((b.cx-s.x)**2+(b.cy-s.y)**2))[3];V.veinCard(h);console.log(c.textContent);V.veinToggle(false);w.__cs.openHouse(h.id);console.log('普通卡：',c.querySelector('.now')&&c.querySelector('.now').textContent)}
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
