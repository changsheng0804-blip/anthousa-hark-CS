const src=require('fs').readFileSync(__dirname+'/check_talk.js','utf8').split('const w=dom.window;')[0];eval(src+`
const w=dom.window;setTimeout(()=>{try{const A=w.__anth;const c=w.document.getElementById('card');let bad=0,n=0,len=0,lens=[];
for(const Y of [20,40,55]){A.setYear(Y);const hs=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y);for(let i=0;i<hs.length;i+=7){w.__cs.openHouse(hs[i].id);const vis=[...c.querySelectorAll('h2,.meta,.now,.story,.cshook,.cstalk')].filter(e=>!e.closest('details')).map(e=>e.textContent).join(' ');lens.push(vis.length);
 let k=c.querySelector('[data-q=next]');for(let q=0;q<3&&k;q++){k.click();k=c.querySelector('[data-q=next]')}
 const p=c.querySelector('.cshook [data-p],.cshook [data-pf]');if(p){p.click();const nx=c.querySelector('.csstep [data-step]');if(nx)nx.click()}
 n++;const t=c.innerHTML;if(/undefined|NaN|null/.test(t.replace(/csans|data-[a-z]+=/g,''))){bad++;if(bad<4)console.log('BAD',c.textContent.slice(0,300))}}}
lens.sort((a,b)=>a-b);console.log('cards',n,'bad',bad,'visible chars median',lens[lens.length>>1],'p90',lens[Math.floor(lens.length*.9)]);
A.setYear(55);const h=A.houses.find(h=>h.built<=55&&h.destroyed>55&&!c.x);w.__cs.openHouse(A.houses.filter(h=>h.built<=50&&h.destroyed>55)[300].id);console.log(c.innerText||c.textContent.slice(0,400));c.querySelector('[data-q=next]').click();console.log('>>',c.querySelector('.cstalk').textContent)
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
