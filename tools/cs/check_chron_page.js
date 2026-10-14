// CS 线 · /goal 3 项 7：编年史事件在瓦片页上的那一头（check_chronicle.py 调它）。在 jsdom 里跑 docs/living/tiles/index.html：
//  1 页面载入的事件 = events.json 的每一件（一件不少），每件带 show_year（烤好的年份里 ≥ 事件年的第一个），
//  2 每件事件在它的 show_year 上亮（alpha 1），在它发生以前的年份不亮；拖到别的年份时淡出（alpha 随年份单调下降到 0），
//  3 每年份至少亮一件（该年有事件的话）；年份切换时是交叉淡入淡出（fade 中间值介于两年的亮度之间），
//  4 每件事件点一下（markHit 命中落点）→ flyTo 的目标 = 事件落点 + z，并且同时切到 show_year，
//  5 年份轴：有一根 range（#yrs）覆盖全部烤好的年份，拖动（input 事件）切年，切年也带动它，
//  6 点开事件出一张卡：年、名字、编年史原文一句（#evcard）。
// 用法：AH=<repo> node check_chron_page.js
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
(async()=>{await sleep(500);const T=w.__TILES;if(!T){console.log('❌ 页面没起来',errs);process.exit(1)}
 const EJ=JSON.parse(fs.readFileSync(D+'events.json','utf8')).events,YS=T.M.years;const EV=T.events||[];
 const byId=Object.fromEntries(EV.map(v=>[v.id,v]));const lost=EJ.filter(e=>!byId[e.id]).map(e=>e.id);
 chk(EV.length===EJ.length&&!lost.length,`页面载入 ${EV.length} 件事件，events.json 有 ${EJ.length} 件`+(lost.length?`；缺：${lost.slice(0,6).join('、')}…`:''));
 const sy=e=>YS.find(y=>y>=e.year);const badSY=EJ.filter(e=>byId[e.id]&&byId[e.id].show_year!==sy(e)).map(e=>e.id);
 chk(EV.length>0&&!badSY.length,'每件事件的 show_year = 烤好的年份里 ≥ 事件年的第一个'+(badSY.length?`；不对：${badSY.slice(0,6).join('、')}`:''));
 if(!T.evAlpha){chk(false,'页面没有 evAlpha（事件按年淡入淡出）');}
 else{
  const noLit=EV.filter(e=>T.evAlpha(e,e.show_year)<0.999).map(e=>e.id);
  const early=EV.filter(e=>YS.some(y=>y<e.year&&T.evAlpha(e,y)>0)).map(e=>e.id);
  const nonmono=EV.filter(e=>{let p=1;for(const y of YS.filter(y=>y>=e.show_year)){const a=T.evAlpha(e,y);if(a>p+1e-9)return true;p=a}return false}).map(e=>e.id);
  const fades=EV.filter(e=>YS.some(y=>y>e.show_year&&T.evAlpha(e,y)>0&&T.evAlpha(e,y)<1)).length;
  chk(!noLit.length&&!early.length&&!nonmono.length,`事件在 show_year 亮、发生以前不亮、之后单调淡出（淡出带里有 ${fades} 件）`+(noLit.concat(early,nonmono).length?`；不对：${noLit.concat(early,nonmono).slice(0,6).join('、')}`:''));
  const dark=YS.filter(y=>EJ.some(e=>sy(e)===y)&&!EV.some(e=>T.evAlpha(e,y)>0.5));
  chk(!dark.length,`有事件的年份（${YS.filter(y=>EJ.some(e=>sy(e)===y)).join('、')}）每年至少亮一件`+(dark.length?`；黑的：${dark.join('、')}`:''));
  // 交叉淡入淡出：从 a 年切到 b 年的一瞬，亮度 = a 年的；等淡完 = b 年的
  const e0=EV.find(e=>e.show_year>YS[0]);if(e0&&T.evAlphaNow){T.setYear(YS[0]);await sleep(600);T.setYear(e0.show_year);const a1=T.evAlphaNow(e0);await sleep(900);const a2=T.evAlphaNow(e0);
   chk(a1<0.2&&a2>0.999,`切年交叉淡入：${e0.name}（${e0.show_year} 年）刚切时 ${a1.toFixed(2)}，淡完 ${a2.toFixed(2)}`)}else chk(false,'页面没有 evAlphaNow（切年时的交叉淡入）');
 }
 // 点一下 → 飞过去 + 切年 + 出卡
 let flyBad=[],cardBad=[],n=0;const W=1920;
 for(const e of EV){T.cancelFly();w.document.getElementById('evcard')&&(w.document.getElementById('evcard').style.display='none');
  {const mates=EV.filter(o=>o!==e&&Math.hypot(o.x-e.x,o.y-e.y)<8);   // 同一处叠着别的事件时，挑一个这件事最亮的年份去点
   const ok=y=>T.evAlpha(e,y)>=0.3&&mates.every(o=>T.evAlpha(o,y)<=T.evAlpha(e,y)+1e-9);const ny=YS.filter(y=>y!==e.show_year&&ok(y))[0];T.setYear(ny!=null?ny:e.show_year)}   // 当前年故意不是它的年（落点还在淡出带里，点得中），点了要切过来
  T.cam.x=e.x;T.cam.y=e.y;T.cam.z=0.3;
  await sleep(250);   // 等切年淡完（交叉淡入期间两年的亮度混着，点哪件取决于淡到哪）
  const hit=T.markHit(W/2,T.H/2);const F=T.FLY;
  if(!(hit&&T.flying&&F&&Math.abs(F.x1-e.x)<1&&Math.abs(F.y1-e.y)<1&&Math.abs(F.z1-e.z)<0.01&&T.curYear===e.show_year))flyBad.push(e.id);
  const c=w.document.getElementById('evcard');if(!(c&&c.style.display!=='none'&&c.textContent.includes(e.name)&&c.textContent.includes(e.text.slice(0,12))&&c.textContent.includes(String(Math.abs(e.year)))))cardBad.push(e.id);n++;
  T.cancelFly()}
 chk(n>0&&!flyBad.length,`点一下落点就飞到事件、同时切到 show_year：${n-flyBad.length}/${n}`+(flyBad.length?`；不行：${flyBad.slice(0,6).join('、')}`:''));
 chk(n>0&&!cardBad.length,`点开事件出卡（年 + 名字 + 编年史原文）：${n-cardBad.length}/${n}`+(cardBad.length?`；不行：${cardBad.slice(0,6).join('、')}`:''));
 // 年份轴
 const r=w.document.getElementById('yrs');
 chk(!!r&&r.type==='range'&&+r.min===0&&+r.max===YS.length-1,'年份轴 #yrs 是一根 range，盖住全部烤好的年份（'+YS.length+' 个）');
 if(r){const i=Math.floor(YS.length/2);r.value=i;r.dispatchEvent(new w.Event('input',{bubbles:true}));chk(T.curYear===YS[i],`拖轴到第 ${i} 格 → 切到 ${YS[i]} 年（实际 ${T.curYear}）`);
  T.setYear(YS[1]);chk(+r.value===1,'切年带动轴（按钮、点事件切年，轴跟着动）')}
 console.log(out.join('\n'));console.log(`errors ${errs.length}`);errs.slice(0,3).forEach(e=>console.log('  ',e));process.exit(bad||errs.length?1:0)})();
