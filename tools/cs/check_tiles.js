// CS 线 · cs33 瓦片页冒烟 + 预算：在 jsdom 里跑 docs/living/tiles/index.html，按几种缩放量一屏要画几块、要下多少字节。
// /goal 2 2b：级间交叉淡入带（细一级 l-1 离换级不到 0.85 个倍频程）里，细一级的瓦片要提前取、淡入时叠画，一屏可画 80 块、字节放宽到 3 MB；大视野（细一级要 >64 块）不取不叠，仍守 40 块 / 1.5 MB。
// /goal 2 2c：z 在 0.76–1.45（街巷级淡入带）要提前把街和房子的数据取好，字节预算放宽到 3 MB。
// 用法：AH=<repo> node check_tiles.js   （模块在 /workspace/work/csjs）
const {JSDOM,VirtualConsole}=require('/workspace/work/csjs/node_modules/jsdom');const fs=require('fs'),path=require('path'),zlib=require('zlib');
const D=(process.env.AH||'/workspace/work/ah')+'/docs/living/tiles/';
const html=fs.readFileSync(D+'index.html','utf8');let errs=[];const req=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'http://x/living/tiles/',beforeParse(w){
 w.innerWidth=1920;w.innerHeight=1080;w.devicePixelRatio=1;
 w.fetch=async f=>{f=String(f);const p=path.join(D,f);if(!fs.existsSync(p))return{ok:false,json:async()=>null};if(f.startsWith('vec/'))req.push(f);const b=fs.readFileSync(p);return{ok:true,json:async()=>JSON.parse(b)}};
 const noop=new Proxy(function(){},{get:(t,k)=>noop,apply:()=>noop,set:()=>true});
 w.HTMLCanvasElement.prototype.getContext=()=>noop;
 w.Image=class{set src(s){this._s=s;req.push(s);const ok=fs.existsSync(path.join(D,s));setTimeout(()=>ok?this.onload&&this.onload():this.onerror&&this.onerror(),1)}get src(){return this._s}};
 w.Path2D=class{moveTo(){}lineTo(){}};
 w.requestAnimationFrame=f=>setTimeout(f,5);
}});
const w=dom.window;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{await sleep(300);const T=w.__TILES;if(!T){console.log('❌ 页面没起来',errs);process.exit(1)}
 const out=[];let bad=0;const BUD={tiles:40,bytes:1.5e6,houses:5000,walkers:600,ships:40};
 const views=[['全城',null],['街区',0.45],['街坊',1.0],['街巷',2.5],['贴近',5]];
 for(const Y of T.M.years){for(const [nm,z] of views){
   if(z!==null){const q=T.M.quarters.nangang;T.cam.x=q[0]+q[2]/2;T.cam.y=q[1]+q[3]/2;T.cam.z=z}else{T.cam.z=Math.min(1920/(T.M.grid[0]*T.M.tile_px),1080/(T.M.grid[1]*T.M.tile_px))*0.95;T.cam.x=T.M.grid[0]*T.M.tile_px/2;T.cam.y=T.M.grid[1]*T.M.tile_px/2}
   w.__TILES.setYear(Y);const r0=req.length;await sleep(z!==null&&z>=1.15?900:150);
   const got=req.slice(r0);const by=got.reduce((s,f)=>{const p=path.join(D,f);if(!fs.existsSync(p))return s;return s+(f.endsWith('.json')?zlib.gzipSync(fs.readFileSync(p)).length:fs.statSync(p).size)},0);
   const [bl,bf]=T.levelF(),band=bl>0&&bf<0.85&&z!==null;const ok=T.drawn<=(band?80:BUD.tiles)&&by<=((z!==null&&z>=0.76&&z<1.45)||band?3e6:BUD.bytes)&&T.hdrawn<=BUD.houses&&(z===null||z<T.STREET_Z||T.hdrawn>0)&&T.LIFE.walkers<=BUD.walkers&&T.LIFE.ships<=BUD.ships&&(z===null||z<T.STREET_Z||T.LIFE.walkers>0);bad+=!ok;out.push(`${ok?'✅':'❌'} ${Y} 年 ${nm}（级 ${T.level()}）：画 ${T.drawn} 块，新下载 ${got.length} 块 ${(by/1024).toFixed(0)} KB${T.hdrawn?'，矢量房子 '+T.hdrawn+' 栋，人 '+T.LIFE.walkers+'，船 '+T.LIFE.ships:''}`)}}
 // 定律：街巷级跑 20 秒模拟时间，人始终在 w 位为真的街上，船始终在水格（含四周）里；再拉到港口看船
 {const q=T.M.quarters.nangang;T.cam.x=q[0]+q[2]*0.6;T.cam.y=q[1]+q[3]*0.85;T.cam.z=2;w.__TILES.setYear(60);await sleep(400);
  let bw=0,bs=0,maxS=0;for(let k=0;k<40;k++){await sleep(30);const gi=T.M.street.ground_keys.indexOf(60),N=T.M.water_cells_n,C=T.M.water_cell,TP=T.M.tile_px;
   for(const [key,L] of T.LIFE.tiles){for(const p of L.W)if(!(p.q[9]>>gi&1))bw++;maxS=Math.max(maxS,T.LIFE.ships);
    for(const b of L.S){const tx=Math.floor(b.x/TP),ty=Math.floor(b.y/TP);const v=T.vtiles.get(tx+'_'+ty);const wg=v&&v.d&&v.d.wg&&v.d.wg['60'];const i=Math.floor((b.x-tx*TP)/C),j=Math.floor((b.y-ty*TP)/C);let ok=!!wg;if(wg)for(let a=-4;a<=4&&ok;a++)for(let c=-4;c<=4;c++){const ii=i+a,jj=j+c;if(ii<0||jj<0||ii>=N||jj>=N||wg[jj*N+ii]!=='1'){ok=false;break}}if(!ok)bs++}}}
  const ok=bw===0&&bs===0&&maxS>0;bad+=!ok;out.push(`${ok?'✅':'❌'} 定律：港口 40 帧里人踩出街 ${bw} 次，船身出水 ${bs} 次，同屏船 ${maxS} 条，人 ${T.LIFE.walkers}`)}
 console.log(out.join('\n'));console.log(`errors ${errs.length}`);errs.slice(0,3).forEach(e=>console.log('  ',e));process.exit(bad||errs.length?1:0)})();
