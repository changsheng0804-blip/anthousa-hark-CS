// CS 线 · cs33 瓦片页冒烟 + 预算：在 jsdom 里跑 docs/living/tiles/index.html，按几种缩放量一屏要画几块、要下多少字节。
// 用法：AH=<repo> node check_tiles.js   （模块在 /workspace/work/csjs）
const {JSDOM,VirtualConsole}=require('/workspace/work/csjs/node_modules/jsdom');const fs=require('fs'),path=require('path');
const D=(process.env.AH||'/workspace/work/ah')+'/docs/living/tiles/';
const html=fs.readFileSync(D+'index.html','utf8');let errs=[];const req=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'http://x/living/tiles/',beforeParse(w){
 w.innerWidth=1920;w.innerHeight=1080;w.devicePixelRatio=1;
 w.fetch=async f=>{const b=fs.readFileSync(path.join(D,String(f)));return{ok:true,json:async()=>JSON.parse(b)}};
 const noop=new Proxy(function(){},{get:(t,k)=>noop,apply:()=>noop,set:()=>true});
 w.HTMLCanvasElement.prototype.getContext=()=>noop;
 w.Image=class{set src(s){this._s=s;req.push(s);const ok=fs.existsSync(path.join(D,s));setTimeout(()=>ok?this.onload&&this.onload():this.onerror&&this.onerror(),1)}get src(){return this._s}};
 w.requestAnimationFrame=f=>setTimeout(f,5);
}});
const w=dom.window;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{await sleep(300);const T=w.__TILES;if(!T){console.log('❌ 页面没起来',errs);process.exit(1)}
 const out=[];let bad=0;const BUD={tiles:40,bytes:1.5e6};
 const views=[['全城',null],['街区',0.45],['街坊',1.0],['街巷',2.5]];
 for(const Y of T.M.years){for(const [nm,z] of views){
   if(z!==null){const q=T.M.quarters.nangang;T.cam.x=q[0]+q[2]/2;T.cam.y=q[1]+q[3]/2;T.cam.z=z}else{T.cam.z=Math.min(1920/(T.M.grid[0]*T.M.tile_px),1080/(T.M.grid[1]*T.M.tile_px))*0.95;T.cam.x=T.M.grid[0]*T.M.tile_px/2;T.cam.y=T.M.grid[1]*T.M.tile_px/2}
   w.__TILES.setYear(Y);const r0=req.length;await sleep(150);
   const got=req.slice(r0);const by=got.reduce((s,f)=>s+(fs.existsSync(path.join(D,f))?fs.statSync(path.join(D,f)).size:0),0);
   const ok=T.drawn<=BUD.tiles&&by<=BUD.bytes;bad+=!ok;out.push(`${ok?'✅':'❌'} ${Y} 年 ${nm}（级 ${T.level()}）：画 ${T.drawn} 块，新下载 ${got.length} 块 ${(by/1024).toFixed(0)} KB`)}}
 console.log(out.join('\n'));console.log(`errors ${errs.length}`);errs.slice(0,3).forEach(e=>console.log('  ',e));process.exit(bad||errs.length?1:0)})();
