// CS 线 · 工厂 · 页面冒烟检查（任何街区）：在 jsdom 里把 docs/living/<q>/index.html 跑起来，拨到每个关键年，
// 数脚本报错、数站着的房子是不是和底账一样多、点开一栋房子有没有卡片。用法：AH=<repo> node check_page.js <q>
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs'),path=require('path');
const Q=process.argv[2];const D=(process.env.AH||'/workspace/work/ah')+'/docs/living/'+Q+'/';
const html=fs.readFileSync(D+'index.html','utf8');let errs=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));vc.on('error',e=>errs.push(String(e)));
const dom=new JSDOM(html.replace(/<script>/,'<script>window.__boot=(async()=>{').replace(/<\/script>(?![\s\S]*<\/script>)/,'})().catch(e=>console.log("BOOTERR",e.stack));</script>'),{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'http://x/',beforeParse(w){
 w.fetch=async f=>{f=String(f).split("?")[0];const p=path.join(D,f);if(!fs.existsSync(p))return{ok:false,json:async()=>({}),text:async()=>''};const b=fs.readFileSync(p);return{ok:true,json:async()=>JSON.parse(b),text:async()=>b.toString()}};
 const noop=new Proxy(function(){},{get:(t,k)=>k==='measureText'?()=>({width:10}):k==='createLinearGradient'||k==='createRadialGradient'||k==='createPattern'?()=>({addColorStop(){}}):k==='getImageData'?()=>({data:new Uint8ClampedArray(4)}):noop,apply:()=>noop,set:()=>true});
 w.HTMLCanvasElement.prototype.getContext=()=>noop;w.HTMLCanvasElement.prototype.toDataURL=()=>'';
 w.Image=class{constructor(){this.complete=true;this.width=10;this.height=10;this.naturalWidth=10}decode(){return Promise.resolve()}};
 w.HTMLImageElement.prototype.decode=function(){return Promise.resolve()};
 w.AudioContext=w.webkitAudioContext=function(){return noop};w.requestAnimationFrame=()=>0;w.matchMedia=()=>({matches:false,addListener(){}});
 w.console.log=(...a)=>{const s=a.join(' ');if(/BOOTERR|Error/.test(s))errs.push(s.slice(0,200))};
}});
const w=dom.window;
setTimeout(()=>{let out=[];try{const A=w.__anth;const S=JSON.parse(fs.readFileSync(D+'scene.json'));
 const L=JSON.parse(fs.readFileSync(D+(S.street_layout?S.street_layout.houses:'houses.json'))).houses;
 for(const k of S.keys){const Y=k[0];A.setYear(Y);const want=L.filter(h=>h[2]<=Y&&h[3]>Y).length;const got=A.houses.filter(h=>h.built<=Y&&h.destroyed>Y).length;out.push(`${Y}:${got}/${want}`);if(got!==want)errs.push(`year ${Y} houses ${got} != ${want}`)}
 const h=A.houses.find(h=>h.built<=S.keys[S.keys.length-1][0]&&h.destroyed>S.keys[S.keys.length-1][0]);w.__cs.openHouse(h.id);
 const card=w.document.querySelector('#cardbody');if(!card||!card.textContent.trim())errs.push('house card empty');
}catch(e){errs.push('TESTERR '+e.message)}
console.log(`page ${Q} years ${out.join(' ')} errors ${errs.length}`);errs.slice(0,5).forEach(e=>console.log('  ',e));process.exit()},6000);
