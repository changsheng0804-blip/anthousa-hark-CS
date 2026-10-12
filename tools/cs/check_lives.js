const src=require('fs').readFileSync(__dirname+'/check_talk.js','utf8').split('const w=dom.window;')[0];eval(src+`
const w=dom.window;setTimeout(()=>{try{const A=w.__anth,C=w.__cs2;A.setYear(55);
let t0=Date.now();const IN=C.csIncoming();console.log('index ms',Date.now()-t0,'targets',Object.keys(IN).length);
let n=0,bad=0;for(const h of A.houses){const hh=A.household(h);for(const p of hh.people){const B=C.csBeats(hh,p);n++;if(B.some(b=>/undefined|NaN|null/.test(b[1])||b[0]<1||b[0]>60)){bad++;if(bad<5)console.log('BAD',JSON.stringify(B).slice(0,300))}}}
console.log('people',n,'bad',bad);
let ex=null;for(const h of A.houses){const hh=A.household(h);const p=hh.people.find(p=>typeof p.to==='number'&&p.d>p.left+20&&p.b>5&&p.left<55);if(p){ex=[h,hh,p];break}}
const [h,hh,p]=ex;C.csBeats(hh,p).forEach(b=>console.log(b[0],b[2],b[1]));
const SP=C.csSpouse(p);A.setYear(Math.min(60,p.left+3));w.__cs.openHouse(SP.hid);const c=w.document.getElementById('card');console.log('target card:',c.querySelector('.ppl').textContent.slice(0,250));
const pf=c.querySelector('[data-pf]');if(pf){pf.click();console.log('person card:',c.querySelector('h2').textContent,'|',c.querySelector('.story').textContent);c.querySelectorAll('.csstep [data-step]')[1].click();console.log('step:',c.querySelector('.story').textContent)}
w.__cs.openHouse(h.id);const pp=c.querySelector('[data-p]');if(pp){pp.click();console.log('from house person:',c.querySelector('h2').textContent,c.querySelector('.csstep span').textContent)}
}catch(e){console.log('ERR',e.stack)}process.exit()},6000);`)
