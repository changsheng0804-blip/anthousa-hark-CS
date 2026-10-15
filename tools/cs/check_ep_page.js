// 谭线史诗画页面检查（2026-10-15）：ep.json 载入；epDraw 在街道级按年画对的块、竞技场按时钟换四刻；不抛错。
// 原叠层痕迹检查头部复用：traces.json 每条都有底账出处、编年史原文能在编年史里找到、页面按年显隐、点开出卡、能回到原来的年份。
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
(async()=>{await sleep(700);const T=w.__TILES,E=w.__EP,H=w.__HEART;if(!T||!E){console.log('❌ 页面没起来',errs);process.exit(1)}
 const EJ=JSON.parse(fs.readFileSync(D+'ep.json','utf8'));chk(E.data&&Object.keys(E.data.t).length===Object.keys(EJ.t).length,`ep.json 载入 ${E.data?Object.keys(E.data.t).length:0} 块`);
 const k=Object.keys(EJ.race)[0];const seq=EJ.race[k];const yd=seq[seq.length-1][0];
 const ms=[2,9,13,19].map(h=>E.race(k,70,h));chk(new Set(ms).size===4&&ms.every(Boolean),'竞技场 70 年 清晨/上午/正午/黄昏 四个时刻取到四张不同的图');
 const bad=[];for(const [kk,sq] of Object.entries(EJ.t)){const y0=sq[0][0];if(y0>-657&&E.at(kk,y0-1))bad.push(kk+' 早到');if(E.at(kk,y0)!==sq[0][1])bad.push(kk+' 不对')}
 chk(!bad.length,'每块第一张在该出现那年才出现'+(bad.length?'；'+bad.slice(0,5).join('、'):''));
 let err=null;try{const x0=600*14.21875-(EJ.tile_px||455)*0,y0=0;E.draw(60,0,0,8000,6000);E.draw(1,0,0,8000,6000)}catch(e){err=e.message}
 await sleep(60);chk(!err,'epDraw 不抛错'+(err?'：'+err:''));try{E.draw(60,0,0,20000,12000)}catch(e){};chk(E.drawn>0&&E.loaded>0,`街道级 60 年画了 ${E.drawn} 块（已下 ${E.loaded} 张）`);
 chk(!errs.length,'页面无报错'+(errs.length?'：'+errs.slice(0,3).join(' | '):''));
 console.log(out.join('\n'));console.log('errors',bad?bad.length:0);process.exit(out.some(l=>l.startsWith('❌'))?1:0)})();
