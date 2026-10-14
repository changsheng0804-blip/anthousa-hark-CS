// 叠层痕迹检查（2026-10-14）：traces.json 每条都有底账出处、编年史原文能在编年史里找到、页面按年显隐、点开出卡、能回到原来的年份。
//  1 每条 src 在 world.json 里查得到（ruin：结构 destroyed=since；spolia：结构 spolia_from 含来源；fire：eras 里有这一年的火）
//  1b 派生表清场（clearedcs<）：逐户对 cleared_cs.json / epic_cleared.json，户数、最早年一致；文案只说「N 年起…」一句事实，不编故事
//  2 文案每一句（中文名换回占位符后）都是编年史里的原句（不编）
//  3 火场焦痕：找到的烧毁房 ≥ 底账烧毁数的 70%（瓦片页房子按街道重排过，个别对不上）
//  4 页面：TRACES 全部载入；since 之前不在标记里、之后在；traceDraw 不抛错；showTrace 出卡且「回到」切到 back 年
// 用法：AH=<repo> node check_traces.js
const {JSDOM,VirtualConsole}=require('/workspace/work/csjs/node_modules/jsdom');const fs=require('fs'),path=require('path');
const D=(process.env.AH||'/workspace/work/ah')+'/docs/living/tiles/';
const html=fs.readFileSync(D+'index.html','utf8');let errs=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'http://x/living/tiles/',beforeParse(w){
 w.innerWidth=1920;w.innerHeight=1080;w.devicePixelRatio=1;
 w.fetch=async f=>{f=String(f);const p=path.join(D,f);if(!fs.existsSync(p))return{ok:false,json:async()=>null};const b=fs.readFileSync(p);return{ok:true,json:async()=>JSON.parse(b)}};
 const noop=new Proxy(function(){},{get:(t,k)=>noop,apply:()=>noop,set:()=>true});
 w.HTMLCanvasElement.prototype.getContext=()=>noop;
 w.Image=class{set src(s){this._s=s;const ok=fs.existsSync(path.join(D,s));setTimeout(()=>ok?this.onload&&this.onload():this.onerror&&this.onerror(),1)}get src(){return this._s}};
 w.Path2D=class{moveTo(){}lineTo(){}};
 w.requestAnimationFrame=f=>setTimeout(f,5);
}});
const w=dom.window;const sleep=ms=>new Promise(r=>setTimeout(r,ms));let bad=0;const out=[];const chk=(ok,m)=>{out.push((ok?'✅ ':'❌ ')+m);bad+=!ok};
const ROOT=(process.env.AH||'/workspace/work/ah');const WJ=JSON.parse(fs.readFileSync(ROOT+'/world.json','utf8'));const NZ=JSON.parse(fs.readFileSync(ROOT+'/docs/data.json','utf8')).names_zh;
const ST=Object.fromEntries(WJ.structures.map(s=>[s.id,s]));const CH=fs.readdirSync(ROOT+'/chronicle').filter(f=>f.endsWith('.md')).map(f=>fs.readFileSync(ROOT+'/chronicle/'+f,'utf8')).join('\n');
const sub=t=>t.replace(/\{\{([a-z_0-9]+)\}\}/g,(m,k)=>NZ[k]||(ST[k]&&ST[k].name)||k);const CHZ=sub(CH);
(async()=>{await sleep(700);const T=w.__TILES,TR=w.__TRACE;if(!T||!TR){console.log('❌ 页面没起来',errs);process.exit(1)}
 const TJ=JSON.parse(fs.readFileSync(D+'traces.json','utf8')).traces;
 const srcBad=TJ.filter(t=>{if(t.kind==='ruin'){const s=ST[t.id];return !s||s.destroyed!==t.since}if(t.kind==='spolia'){const [a,b]=t.id.split('<');return !ST[a]||!(ST[a].spolia_from||[]).includes(b)||ST[a].built!==t.since}if(t.kind==='cleared'&&t.id.startsWith('clearedcs<')){const who=t.id.slice(10);const R=['cleared_cs.json','epic_cleared.json'].flatMap(f=>fs.existsSync(D+f)?JSON.parse(fs.readFileSync(D+f,'utf8')).cleared.map(r=>Object.assign({_f:f},r)):[]).filter(r=>r.lm===who||r.epic===who);return !R.length||new Set(R.map(r=>r.id)).size!==t.n||Math.min(...R.map(r=>r.year))!==t.since}if(t.kind==='cleared'){const L=WJ.structures.find(x=>'cleared<'+x.id===t.id);return !L||L.built!==t.since||WJ.houses.filter(h=>h.cause==='cleared for '+L.name).length!==t.n}if(t.kind==='fire'){return !WJ.eras.some(e=>(e.events||[]).some(v=>v.type==='fire'&&v.year===t.since))}return true}).map(t=>t.name);
 chk(TJ.length>0&&!srcBad.length,`${TJ.length} 条痕迹都有底账出处`+(srcBad.length?'；查不到：'+srcBad.join('、'):''));
 const txtBad=TJ.filter(t=>!t.text||t.id.startsWith('clearedcs<')?!(t.text&&t.text.startsWith(t.since+' 年起')):t.text.split(/(?<=[。！？])/).some(x=>x.trim()&&!CHZ.includes(x.replace(/。$/,'').slice(0,12)))).map(t=>t.name);
 chk(!txtBad.length,'文案都是编年史原句'+(txtBad.length?'；对不上：'+txtBad.join('、'):''));
 const fireBad=TJ.filter(t=>t.kind==='fire').filter(t=>{const v=WJ.eras.flatMap(e=>e.events||[]).find(v=>v.type==='fire'&&v.year===t.since);return t.polys.length<0.7*v.houses}).map(t=>t.name+' '+t.polys.length);
 chk(!fireBad.length,'火场焦痕 ≥ 底账烧毁数的 70%：'+TJ.filter(t=>t.kind==='fire').map(t=>t.name+' '+t.polys.length).join('，')+(fireBad.length?'；不足：'+fireBad.join('、'):''));
 chk(TR.list().length===TJ.length,`页面载入 ${TR.list().length}/${TJ.length} 条`);
 let vis=[];for(const t of TJ){const yb=TR.STOPS.filter(y=>y<t.since).pop(),ya=TR.STOPS.find(y=>y>=t.since);
   if(yb!=null){T.setYear(yb);await sleep(30);if(TR.marks().some(m=>m.tr===TR.list().find(x=>x.id===t.id)))vis.push(t.name+' 提前出现')}
   T.setYear(ya);await sleep(30);if(!TR.marks().some(m=>m.tr&&m.tr.id===t.id))vis.push(t.name+' 该在不在');
   try{TR.draw(ya)}catch(e){vis.push(t.name+' 画时出错 '+e.message)}}
 chk(!vis.length,'按年显隐：发生前不在、发生后在，画时不出错'+(vis.length?'；'+vis.join('、'):''));
 let card=[];T.setYear(70);await sleep(30);for(const t of TR.list()){TR.show(t);const el=w.document.getElementById('evcard');if(!el||el.style.display!=='block'||!el.textContent.includes(t.name))card.push(t.name+' 没出卡');const b=w.document.getElementById('trback');const back=t.kind==='ruin'?t.since-1:t.back;if(b){b.onclick();await sleep(30);const want=TR.STOPS.includes(back)?back:T.M.years.find(k=>k>=back);if(T.curYear!==want)card.push(t.name+' 回到 '+want+' 实际 '+T.curYear);T.setYear(70)}else card.push(t.name+' 没有回到链接')}
 chk(!card.length,'点开出卡、「回到」切年'+(card.length?'；'+card.join('、'):''));
 console.log(out.join('\n'));console.log(`errors ${errs.length}`);errs.slice(0,3).forEach(e=>console.log('  ',e));process.exit(bad||errs.length?1:0)})();
