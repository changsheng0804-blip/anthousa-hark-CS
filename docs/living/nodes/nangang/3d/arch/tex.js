/* buildings · 程序化画布贴图（代码画，不是图）——Hark（CS线）2026-10-20 lookdev 第 2 轮
   墙贴图是「接近白的底 + 细节」，颜色由顶点色乘上去（每户的灰泥色、瓦色由 ctx.hsh 定）。
   砖带、窗洞、门洞、瓦垄都在这里画：几何只给盒子，细节交给贴图，三角形不爆。
   约定：u 沿墙水平重复（一个开间），v 自下而上（canvas 底 = v0，three 默认 flipY）。 */
function rng(seed){let s=seed>>>0;return ()=>{s=(s+0x6D2B79F5)>>>0;let t=s;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296}}
function cv(w,h){const c=document.createElement('canvas');c.width=w;c.height=h;return c}
const rgb=(r,g,b,a=1)=>`rgba(${r|0},${g|0},${b|0},${a})`;
/* 画布坐标 y 向下；helper：按 v（0=底，1=顶）画 */
function speckle(X,w,h,R,n,base,amp,alpha=.5){for(let i=0;i<n;i++){const x=R()*w,y=R()*h,k=base+(R()-.5)*amp;X.fillStyle=rgb(k,k*.97,k*.92,alpha*R());X.fillRect(x,y,1+R()*2,1+R()*2)}}
/* 一道砖带：从 y 起 n 皮砖（画布 y），每皮 ch 高 */
function brickBand(X,w,y,n,ch,R,dark=0){for(let i=0;i<n;i++){const yy=y+i*ch;X.fillStyle=rgb(132,112,94);X.fillRect(0,yy,w,ch);/* 灰缝（偏深，远看整条砖带是一道深红线） */
  let x=-R()*12;while(x<w){const bw=10+R()*7,k=R();X.fillStyle=rgb(112+k*30-dark,48+k*16-dark*.6,30+k*10-dark*.4);X.fillRect(x+.5,yy+.75,bw-1,ch-1.25);x+=bw}}}
/* 石块层：浅色大块石灰石 */
function stoneCourses(X,w,y0,y1,ch,R,lite=230){for(let y=y0;y<y1;y+=ch){let x=-R()*30;X.fillStyle=rgb(lite-70,lite-80,lite-92);X.fillRect(0,y,w,2);while(x<w){const bw=20+R()*26,k=lite-8+R()*16;X.fillStyle=rgb(k,k*.95,k*.86);X.fillRect(x+1,y+2,bw-2,ch-2.5);x+=bw}}}
function planks(X,x0,y0,w,h,R){X.fillStyle=rgb(112,76,46);X.fillRect(x0,y0,w,h);for(let x=x0;x<x0+w;x+=6){X.fillStyle=rgb(60,40,24);X.fillRect(x,y0,1.5,h)}X.fillStyle=rgb(44,34,28);for(const f of [.2,.75])X.fillRect(x0,y0+h*f,w,3)}
function archPath(X,cx,top,hw,bottom){X.beginPath();X.moveTo(cx-hw,bottom);X.lineTo(cx-hw,top+hw);X.arc(cx,top+hw,hw,Math.PI,0);X.lineTo(cx+hw,bottom);X.closePath()}
/* 窗/门：深色洞口 + 过梁 + 窗台 + 一点木百叶 */
function opening(X,cx,top,w,h,R,{arch=false,shutter=true,brickArch=false}={}){const hw=w/2,bot=top+h;
  if(arch&&brickArch){X.fillStyle=rgb(150,84,56);archPath(X,cx,top-5,hw+5,bot);X.fill()}
  X.fillStyle=rgb(26,20,16);if(arch){archPath(X,cx,top,hw,bot);X.fill()}else X.fillRect(cx-hw,top,w,h);
  X.fillStyle=rgb(48,36,28);X.fillRect(cx-hw+2,top+h*.55,w-4,h*.45);/* 洞里的一点深浅 */
  if(!arch){X.fillStyle=rgb(212,204,186);X.fillRect(cx-hw-4,top-5,w+8,5)}/* 过梁 */
  X.fillStyle=rgb(205,196,176);X.fillRect(cx-hw-3,bot,w+6,4);/* 窗台 */
  if(shutter){const k=R();X.fillStyle=k<.5?rgb(118,82,52):rgb(86,96,92);X.fillRect(cx-hw-w*.34,top+1,w*.3,h-2);X.fillRect(cx+hw+w*.04,top+1,w*.3,h-2)}}

/* 民居立面：1 开间 × 3 层（v 0–1 = 3 层）。kind 'stucco' 灰泥 + 层间砖线；'opus' 砖石夹层（opus mixtum） */
export function facade(kind,seed,shop=false){const w=128,h=384,S=h/3,c=cv(w,h),X=c.getContext('2d'),R=rng(seed);
  if(kind==='stucco'){X.fillStyle=rgb(240,236,228);X.fillRect(0,0,w,h);speckle(X,w,h,R,900,226,40,.35);
    /* 层间：三皮砖的束腰线 */for(let i=1;i<3;i++)brickBand(X,w,h-i*S-9,3,6,R);
    /* 墙脚 + 污渍 */X.fillStyle=rgb(176,164,146);X.fillRect(0,h-14,w,14);const g=X.createLinearGradient(0,h-60,0,h-14);g.addColorStop(0,rgb(200,190,170,0));g.addColorStop(1,rgb(150,136,116,.55));X.fillStyle=g;X.fillRect(0,h-60,w,46)}
  else{X.fillStyle=rgb(232,234,236);X.fillRect(0,0,w,h);
    /* 每层：石块 + 两道 4 皮砖带 */for(let i=0;i<3;i++){const y0=h-(i+1)*S;stoneCourses(X,w,y0,y0+S,12,R,226);brickBand(X,w,y0+2,4,6,R);brickBand(X,w,y0+S*.52,4,6,R)}
    X.fillStyle=rgb(160,146,126);X.fillRect(0,h-12,w,12)}
  /* 底层：住家是门，铺面（shop）是整开间的大洞 + 柜台 + 货；楼上：窗 */
  if(shop){X.fillStyle=rgb(200,190,170);X.fillRect(w*.06,h-S+S*.12,w*.88,S*.08);X.fillStyle=rgb(22,16,12);X.fillRect(w*.1,h-S+S*.2,w*.8,S*.8-12);
    X.fillStyle=rgb(70,46,28);X.fillRect(w*.1,h-S*.36,w*.8,S*.36-12);X.fillStyle=rgb(150,104,60);X.fillRect(w*.1,h-S*.38,w*.8,5);/* 柜台 */
    for(let i=0;i<5;i++){const k=R();X.fillStyle=k<.33?rgb(176,120,60):k<.66?rgb(150,60,40):rgb(200,180,130);X.beginPath();X.arc(w*(.2+i*.15),h-S*.42,5+R()*4,0,Math.PI*2);X.fill()}}
  else{opening(X,w/2,h-S+S*.28,w*.36,S*.64,R,{arch:kind==='opus',shutter:false,brickArch:kind==='opus'});X.fillStyle=rgb(92,62,40);X.fillRect(w/2-w*.15,h-S+S*.34,w*.3,S*.56)}/* 门板 */
  for(let i=1;i<3;i++){const y0=h-(i+1)*S;opening(X,w/2,y0+S*.24,w*.3,S*.46,R,{arch:kind==='opus',shutter:kind!=='opus',brickArch:kind==='opus'})}
  /* 檐下一道深影线（每层顶）——远看就是一户户的檐口 */
  X.fillStyle=rgb(90,78,64,.75);for(let i=0;i<3;i++)X.fillRect(0,h-(i+1)*S,w,4);X.fillStyle=rgb(250,246,236,.8);for(let i=0;i<3;i++)X.fillRect(0,h-(i+1)*S+4,w,3);
  return c}

/* 筒瓦：u 沿檐重复，v 顺坡。一张 = 6 垄 × 4 皮 */
export function roof(seed){const w=128,h=128,c=cv(w,h),X=c.getContext('2d'),R=rng(seed);X.fillStyle=rgb(236,232,226);X.fillRect(0,0,w,h);
  const n=6,cw=w/n;for(let i=0;i<n;i++){const g=X.createLinearGradient(i*cw,0,(i+1)*cw,0);g.addColorStop(0,rgb(150,142,134));g.addColorStop(.15,rgb(232,228,222));g.addColorStop(.45,rgb(255,253,250));g.addColorStop(.8,rgb(224,218,210));g.addColorStop(1,rgb(132,124,116));X.fillStyle=g;X.fillRect(i*cw,0,cw,h)}
  for(let j=0;j<4;j++){const y=j*h/4;X.fillStyle=rgb(96,86,78,.7);X.fillRect(0,y,w,3);X.fillStyle=rgb(255,250,244,.35);X.fillRect(0,y+3,w,2)}
  /* 每片瓦深浅（晒褪色、补过的） */for(let i=0;i<n;i++)for(let j=0;j<4;j++){const k=R();if(k<.35){X.fillStyle=k<.15?rgb(60,40,30,.22):rgb(255,240,220,.18);X.fillRect(i*cw+2,j*h/4+3,cw-4,h/4-3)}}
  return c}

/* 粮仓长墙：2 个开间（u 0–1），v 0–1 = 整面墙高（不重复）。砖石夹层，上排拱窗，开间 A 底下有拱门 */
export function granaryWall(seed){const w=256,h=256,c=cv(w,h),X=c.getContext('2d'),R=rng(seed);X.fillStyle=rgb(232,234,236);X.fillRect(0,0,w,h);
  stoneCourses(X,w,0,h,10,R,242);for(let y=14;y<h-14;y+=50)brickBand(X,w,y,4,5,R,10);
  X.fillStyle=rgb(150,138,118);X.fillRect(0,h-10,w,10);
  for(let b=0;b<2;b++){const cx=b*w/2+w/4;opening(X,cx,h*.14,w*.075,h*.15,R,{arch:true,shutter:false,brickArch:true});
    if(b===0){opening(X,cx,h*.5,w*.2,h*.5-10,R,{arch:true,shutter:false,brickArch:true});planks(X,cx-w*.085,h*.66,w*.17,h*.34-10,R)}
    else opening(X,cx,h*.56,w*.07,h*.12,R,{arch:true,shutter:false,brickArch:true})}
  return c}
/* 粮仓山墙（对着码头）：u 0–1 = 墙宽，v 0–1 = 墙身 + 山尖。大拱门、上面三联拱窗、山尖一个圆窗 */
export function granaryGable(seed,wallFrac){const w=256,h=256,c=cv(w,h),X=c.getContext('2d'),R=rng(seed);X.fillStyle=rgb(232,234,236);X.fillRect(0,0,w,h);
  stoneCourses(X,w,0,h,9,R,242);for(let y=8;y<h-12;y+=44)brickBand(X,w,y,4,5,R,10);X.fillStyle=rgb(150,138,118);X.fillRect(0,h-9,w,9);
  const wy=h*(1-wallFrac);/* 墙身顶的画布 y */
  X.fillStyle=rgb(196,184,160);X.fillRect(0,wy-4,w,6);/* 檐口线 */
  opening(X,w/2,h-(h-wy)*.62,w*.3,(h-wy)*.62-9,R,{arch:true,shutter:false,brickArch:true});planks(X,w*.36,h-(h-wy)*.42,w*.28,(h-wy)*.42-9,R);
  /* 壁柱：两侧和三分点各一道浅色石条，左缘一条影 */for(const px of [.03,.97,.12,.88]){const x=px*w;X.fillStyle=rgb(244,236,220);X.fillRect(x-7,wy,14,h-wy-9);X.fillStyle=rgb(84,70,56,.9);X.fillRect(x+7,wy,4,h-wy-9)}
  for(const dx of [-.3,.3])opening(X,w/2+dx*w,h-(h-wy)*.42,w*.08,(h-wy)*.2,R,{arch:true,shutter:false,brickArch:true});
  for(const dx of [-.3,0,.3])opening(X,w/2+dx*w,wy+(h-wy)*.1,w*.07,(h-wy)*.16,R,{arch:true,shutter:false,brickArch:true});
  X.fillStyle=rgb(150,84,56);X.beginPath();X.arc(w/2,wy*.62,w*.07,0,Math.PI*2);X.fill();X.fillStyle=rgb(26,20,16);X.beginPath();X.arc(w/2,wy*.62,w*.05,0,Math.PI*2);X.fill();
  return c}

/* 水道桥：1 开间 × 1 层拱（RGBA，拱洞透明）。v 自下而上 0–1 = 一层 */
export function arcade(seed){const w=128,h=128,c=cv(w,h),X=c.getContext('2d'),R=rng(seed);X.fillStyle=rgb(232,234,236);X.fillRect(0,0,w,h);
  stoneCourses(X,w,0,h,9,R,214);brickBand(X,w,4,3,4,R,8);brickBand(X,w,h*.36,3,4,R,8);
  X.fillStyle=rgb(190,178,156);X.fillRect(0,0,w,4);X.fillRect(0,h*.3,w,4);/* 拱脚线 */
  /* 拱洞 → 透明，拱圈砖 */X.fillStyle=rgb(150,90,62);archPath(X,w/2,h*.3-6,w*.34+6,h);X.fill();
  X.globalCompositeOperation='destination-out';archPath(X,w/2,h*.3,w*.34,h+2);X.fill();X.globalCompositeOperation='source-over';
  return c}

export function texOf(T,canvas,{repeat=true,aniso=4}={}){const t=new T.CanvasTexture(canvas);t.colorSpace=T.SRGBColorSpace;if(repeat){t.wrapS=t.wrapT=T.RepeatWrapping}else{t.wrapS=T.RepeatWrapping;t.wrapT=T.ClampToEdgeWrapping}t.anisotropy=aniso;t.generateMipmaps=true;t.minFilter=T.LinearMipmapLinearFilter;return t}
