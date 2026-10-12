const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs'),path=require('path');
const D=require('path').join(__dirname,'../../docs/living/xerolophos/');
const html=fs.readFileSync(D+'index.html','utf8');
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.log('JSERR',e.message,(e.detail&&e.detail.stack||'').slice(0,300)));vc.on('error',e=>console.log('ERR',e));vc.on('log',(...a)=>console.log('LOG',...a));
const dom=new JSDOM(html.replace(/<script>/,'<script>window.__boot=(async()=>{').replace(/<\/script>(?![\s\S]*<\/script>)/,'})().catch(e=>console.log("BOOTERR",e.stack));</script>'),{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'http://x/',beforeParse(w){
 w.fetch=async f=>{f=String(f).split("?")[0];const p=path.join(D,f);if(!fs.existsSync(p))return{ok:false,json:async()=>({})};const b=fs.readFileSync(p);return{ok:true,json:async()=>JSON.parse(b),text:async()=>b.toString()}};
 const noop=new Proxy(function(){},{get:(t,k)=>k==='measureText'?()=>({width:10}):k==='createLinearGradient'||k==='createRadialGradient'||k==='createPattern'?()=>({addColorStop(){}}):k==='getImageData'?()=>({data:new Uint8ClampedArray(4)}):noop,apply:()=>noop,set:()=>true});
 w.HTMLCanvasElement.prototype.getContext=()=>noop;w.HTMLCanvasElement.prototype.toDataURL=()=>'';
 w.Image=class{constructor(){this.complete=true;this.width=10;this.height=10;this.naturalWidth=10}decode(){return Promise.resolve()}};
 w.HTMLImageElement.prototype.decode=function(){return Promise.resolve()};
 w.AudioContext=w.webkitAudioContext=function(){return noop};w.requestAnimationFrame=()=>0;w.matchMedia=()=>({matches:false,addListener(){}});
}});
const w=dom.window;
setTimeout(()=>{try{
 const A=w.__anth;if(!A){console.log('no __anth');process.exit()}
 A.setYear(55);
 const hs=A.houses.filter(h=>h.built<=55&&h.destroyed>55);console.log('houses alive',hs.length);
 let n=0,errs=0;
 for(const h of hs){const hh=A.household(h);const al=A.aliveAt(hh,55);if(!al.length)continue;
  for(const q of ['from','work','family','house','city','faith','nb','talk']){for(const sp of al.filter(p=>55-p.b>=7)){try{const a=w.__cs.csAnswer(hh,55,q,sp);if(!a||/undefined|NaN|null/.test(a)){errs++;if(errs<6)console.log('BAD',h.id,q,sp.n,a)}}catch(e){errs++;if(errs<6)console.log('EXC',q,e.message)}n++}}}
 console.log('answers',n,'bad',errs);
 const h=hs.find(h=>A.VOICES[h.id])||hs[0];const hh=A.household(h);const al=A.aliveAt(hh,55).filter(p=>55-p.b>=7);
 for(const q of ['from','work','family','house','city','faith','nb','talk'])console.log(q,'|',al[0].n,55-al[0].b,'|',w.__cs.csAnswer(hh,55,q,al[0]));
 const h2=hs[123];const hh2=A.household(h2);const al2=A.aliveAt(hh2,55).filter(p=>55-p.b>=7);if(al2.length){const sp=al2[al2.length-1];for(const q of ['from','family','city','faith'])console.log(q,'|',sp.n,55-sp.b,'|',w.__cs.csAnswer(hh2,55,q,sp))}
}catch(e){console.log('TESTERR',e.stack)}process.exit()},6000);
