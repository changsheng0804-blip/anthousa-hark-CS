/* house_kit · 共享贴图图集（代码画，不是图）。2048×1024，一格 256²，8 列 × 4 行。——Hark（CS线）2026-10-20
   墙格 = 一个开间 × 一层，底是接近白的灰泥 / 砖石夹层（颜色由顶点色乘上去，同 arch/tex.js 的约定），细节画在格里。
   窗洞、铺面洞口的位置用下面的 WIN / SHOP / DOOR 常量，几何（窗台、百叶、柜台、门框）照同一组数放，所以贴图和几何对得上。
   v 自下而上（画布底 = v0，three 默认 flipY）。图集不能平铺：每个开间每层一个四边形，UV 内缩 4 像素防 mip 串色。 */
export const TS=256, AW=2048, AH=1024;
/* 格内比例（u 0..1 左→右，v 0..1 下→上） */
export const WIN={x0:.34,x1:.66,y0:.34,y1:.80}, SHOP={x0:.08,x1:.92,y0:0,y1:.80}, DOOR={x0:.32,x1:.68,y0:0,y1:.74}, SLIT={x0:.45,x1:.55,y0:.58,y1:.86}, WHD={x0:.16,x1:.84,y0:0,y1:.86};
const ROLES=['shopOpen','shopShut','winOpen','winShut','winArch','blank','slit','door','whDoor','whVent'];
/* 格号：kind 0 = 灰泥、1 = 砖石夹层，每种 10 格（0–19）；20 木板、21 条纹布、22 素布、23 白（无贴图的东西用它）、24 石铺地、25 水 */
export const TILE={};ROLES.forEach((r,i)=>{TILE[r]=[i,10+i]});
export const T_TIMBER=20,T_STRIPE=21,T_CLOTH=22,T_WHITE=23,T_PAVE=24,T_WATER=25,T_RAIL=26;
export function tileUV(t){const c=t%8,r=(t/8)|0,i=4/AW,j=4/AH;return {u0:c*TS/AW+i,u1:(c+1)*TS/AW-i,v0:1-(r+1)*TS/AH+j,v1:1-r*TS/AH-j}}

function rng(seed){let s=seed>>>0;return ()=>{s=(s+0x6D2B79F5)>>>0;let t=s;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296}}
const rgb=(r,g,b,a=1)=>`rgba(${r|0},${g|0},${b|0},${a})`;
function speckle(X,x0,y0,w,h,R,n,base,amp,alpha=.45){for(let i=0;i<n;i++){const k=base+(R()-.5)*amp;X.fillStyle=rgb(k,k*.97,k*.92,alpha*R());X.fillRect(x0+R()*w,y0+R()*h,1+R()*2.5,1+R()*2.5)}}
function brickBand(X,x0,y,w,n,ch,R){for(let i=0;i<n;i++){const yy=y+i*ch;X.fillStyle=rgb(132,112,94);X.fillRect(x0,yy,w,ch);let x=x0-R()*12;while(x<x0+w){const bw=10+R()*7,k=R();X.fillStyle=rgb(118+k*30,52+k*16,32+k*10);X.fillRect(Math.max(x0,x+.5),yy+.75,Math.min(bw-1,x0+w-x-.5),ch-1.25);x+=bw}}}
function stones(X,x0,y0,w,h,ch,R){for(let y=y0;y<y0+h;y+=ch){X.fillStyle=rgb(196,186,170);X.fillRect(x0,y,w,1.5);let x=x0-R()*40;while(x<x0+w){const bw=40+R()*40,k=226+R()*20;X.fillStyle=rgb(k,k*.96,k*.88);X.fillRect(Math.max(x0,x+1),y+1.5,Math.min(bw-2,x0+w-x-1),Math.min(ch-2,y0+h-y-1.5));x+=bw}}}
function planks(X,x0,y0,w,h,R,dir='v',tone=[118,82,52]){X.fillStyle=rgb(...tone);X.fillRect(x0,y0,w,h);X.fillStyle=rgb(tone[0]*.5,tone[1]*.5,tone[2]*.5);
  if(dir==='v')for(let x=x0;x<x0+w;x+=7+R()*3)X.fillRect(x,y0,1.6,h);else for(let y=y0;y<y0+h;y+=9+R()*3)X.fillRect(x0,y,w,1.6);
  for(let i=0;i<w*h/90;i++){X.fillStyle=rgb(tone[0]*(.8+R()*.4),tone[1]*(.8+R()*.4),tone[2]*(.8+R()*.4),.35);X.fillRect(x0+R()*w,y0+R()*h,1,3+R()*6)}}
function archPath(X,cx,top,hw,bottom){X.beginPath();X.moveTo(cx-hw,bottom);X.lineTo(cx-hw,top+hw);X.arc(cx,top+hw,hw,Math.PI,0);X.lineTo(cx+hw,bottom);X.closePath()}
function darkHole(X,x,y,w,h){const g=X.createLinearGradient(0,y,0,y+h);g.addColorStop(0,rgb(18,13,10));g.addColorStop(1,rgb(44,33,25));X.fillStyle=g;X.fillRect(x,y,w,h)}

/* 一格墙底：kind 0 灰泥（近白 + 斑 + 勒脚污渍），1 砖石夹层（石块层 + 两道砖带） */
function base(X,x0,y0,kind,R){const s=TS;
  if(kind===0){X.fillStyle=rgb(242,238,228);X.fillRect(x0,y0,s,s);speckle(X,x0,y0,s,s,R,900,226,40);
    for(let i=0;i<14;i++){X.fillStyle=rgb(196,182,156,.025+R()*.035);X.beginPath();X.ellipse(x0+R()*s,y0+R()*s,30+R()*70,14+R()*40,0,0,7);X.fill()}
    for(let i=0;i<6;i++){X.strokeStyle=rgb(150,136,116,.35);X.lineWidth=1;X.beginPath();let x=x0+R()*s,y=y0+R()*s;X.moveTo(x,y);for(let k=0;k<5;k++){x+=(R()-.5)*14;y+=4+R()*8;X.lineTo(x,y)}X.stroke()}}
  else{X.fillStyle=rgb(236,232,222);X.fillRect(x0,y0,s,s);stones(X,x0,y0,s,s,26,R);brickBand(X,x0,y0+s*.30,s,4,5,R);brickBand(X,x0,y0+s*.80,s,4,5,R)}
  /* 下沿污渍（每层下半部一点潮痕，远看不花） */const g=X.createLinearGradient(0,y0+s*.82,0,y0+s);g.addColorStop(0,rgb(120,104,84,0));g.addColorStop(1,rgb(120,104,84,.22));X.fillStyle=g;X.fillRect(x0,y0+s*.82,s,s*.18)}
const px=(x0,u)=>x0+u*TS, py=(y0,v)=>y0+(1-v)*TS;/* 格内 (u,v) → 画布 */
function lintel(X,x0,y0,u0,u1,v,R,stone=true){X.fillStyle=stone?rgb(214,206,188):rgb(92,64,40);X.fillRect(px(x0,u0)-6,py(y0,v)-10,(u1-u0)*TS+12,10);X.fillStyle=rgb(60,48,36,.5);X.fillRect(px(x0,u0)-6,py(y0,v),(u1-u0)*TS+12,2)}
function sill(X,x0,y0,u0,u1,v){X.fillStyle=rgb(206,198,180);X.fillRect(px(x0,u0)-5,py(y0,v),(u1-u0)*TS+10,6)}
const DRAW={
  shopOpen(X,x0,y0,R){const o=SHOP,g=X.createLinearGradient(0,py(y0,o.y1),0,py(y0,0));g.addColorStop(0,rgb(34,26,20));g.addColorStop(1,rgb(96,74,54));X.fillStyle=g;X.fillRect(px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,o.y1*TS);
    for(let u=o.x0+.08;u<o.x1-.06;u+=.1){X.fillStyle=rgb(150+R()*60,96+R()*40,50,.9);X.fillRect(px(x0,u),py(y0,o.y1)+6,6,18+R()*16)}
    /* 里面的架子和罐 */for(const v of [.55,.32]){X.fillStyle=rgb(88,62,40);X.fillRect(px(x0,o.x0)+8,py(y0,v),(o.x1-o.x0)*TS-16,4);for(let u=o.x0+.06;u<o.x1-.05;u+=.07+R()*.04){const k=R();X.fillStyle=k<.4?rgb(178,92,52):k<.7?rgb(206,164,108):rgb(150,118,80);X.beginPath();X.ellipse(px(x0,u),py(y0,v)-11,8,12,0,0,7);X.fill();X.fillStyle=rgb(255,240,210,.25);X.fillRect(px(x0,u)-4,py(y0,v)-19,2,10)}}
    /* 折起的门板（两侧） */planks(X,px(x0,o.x0),py(y0,o.y1),18,o.y1*TS,R,'v',[110,76,48]);planks(X,px(x0,o.x1)-18,py(y0,o.y1),18,o.y1*TS,R,'v',[110,76,48]);
    lintel(X,x0,y0,o.x0,o.x1,o.y1,R,false)},
  shopShut(X,x0,y0,R){const o=SHOP;planks(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,o.y1*TS,R,'v',[104,72,46]);X.fillStyle=rgb(48,36,28);X.fillRect(px(x0,(o.x0+o.x1)/2)-1,py(y0,o.y1),3,o.y1*TS);for(const v of [.2,.62])X.fillRect(px(x0,o.x0),py(y0,v),(o.x1-o.x0)*TS,4);lintel(X,x0,y0,o.x0,o.x1,o.y1,R,false)},
  winOpen(X,x0,y0,R){const o=WIN;darkHole(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,(o.y1-o.y0)*TS);X.fillStyle=rgb(70,52,36);X.fillRect(px(x0,(o.x0+o.x1)/2)-1,py(y0,o.y1),2,(o.y1-o.y0)*TS);lintel(X,x0,y0,o.x0,o.x1,o.y1,R);sill(X,x0,y0,o.x0,o.x1,o.y0)},
  winShut(X,x0,y0,R){const o=WIN,k=R();planks(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,(o.y1-o.y0)*TS,R,'v',k<.5?[112,80,52]:[92,104,96]);X.fillStyle=rgb(40,32,26);X.fillRect(px(x0,(o.x0+o.x1)/2)-1,py(y0,o.y1),3,(o.y1-o.y0)*TS);lintel(X,x0,y0,o.x0,o.x1,o.y1,R);sill(X,x0,y0,o.x0,o.x1,o.y0)},
  winArch(X,x0,y0,R){const o=WIN,cx=px(x0,(o.x0+o.x1)/2),hw=(o.x1-o.x0)*TS/2;X.fillStyle=rgb(150,86,56);archPath(X,cx,py(y0,o.y1)-7,hw+7,py(y0,o.y0));X.fill();X.fillStyle=rgb(22,16,12);archPath(X,cx,py(y0,o.y1),hw,py(y0,o.y0));X.fill();sill(X,x0,y0,o.x0,o.x1,o.y0)},
  blank(){},
  slit(X,x0,y0,R){const o=SLIT;darkHole(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,(o.y1-o.y0)*TS);sill(X,x0,y0,o.x0,o.x1,o.y0);lintel(X,x0,y0,o.x0,o.x1,o.y1,R)},
  door(X,x0,y0,R){const o=DOOR;X.fillStyle=rgb(210,202,184);X.fillRect(px(x0,o.x0)-12,py(y0,o.y1)-14,(o.x1-o.x0)*TS+24,o.y1*TS+14);
    planks(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,o.y1*TS,R,'v',[150,104,64]);X.fillStyle=rgb(30,24,18);X.fillRect(px(x0,.5)-1,py(y0,o.y1),3,o.y1*TS);
    for(let v=.1;v<o.y1;v+=.12)for(const u of [o.x0+.05,.45,.55,o.x1-.05]){X.fillStyle=rgb(40,34,28);X.beginPath();X.arc(px(x0,u),py(y0,v),2.2,0,7);X.fill()}},
  whDoor(X,x0,y0,R){const o=WHD,cx=px(x0,.5),hw=(o.x1-o.x0)*TS/2,top=py(y0,o.y1);X.fillStyle=rgb(150,84,56);archPath(X,cx,top-10,hw+10,py(y0,0));X.fill();
    X.save();archPath(X,cx,top,hw,py(y0,0));X.clip();planks(X,cx-hw,top,hw*2,o.y1*TS,R,'v',[100,70,44]);X.fillStyle=rgb(34,26,20);X.fillRect(cx-1,top,3,o.y1*TS);X.fillRect(cx-hw,py(y0,.3),hw*2,5);X.fillRect(cx-hw,py(y0,.58),hw*2,5);X.restore()},
  whVent(X,x0,y0,R){for(const u of [.3,.7]){const o={x0:u-.025,x1:u+.025,y0:.62,y1:.84};darkHole(X,px(x0,o.x0),py(y0,o.y1),(o.x1-o.x0)*TS,(o.y1-o.y0)*TS)}}
};
export function buildAtlas(){const c=document.createElement('canvas');c.width=AW;c.height=AH;const X=c.getContext('2d');X.fillStyle='#fff';X.fillRect(0,0,AW,AH);
  const at=t=>[(t%8)*TS,((t/8)|0)*TS];
  ROLES.forEach((r,i)=>{for(const k of [0,1]){const t=TILE[r][k],[x0,y0]=at(t),R=rng(9100+t*37);X.save();X.beginPath();X.rect(x0,y0,TS,TS);X.clip();base(X,x0,y0,k,R);DRAW[r](X,x0,y0,R);X.restore()}});
  {const [x0,y0]=at(T_TIMBER);planks(X,x0,y0,TS,TS,rng(5),'h',[226,214,196])}
  {const [x0,y0]=at(T_STRIPE);for(let i=0;i<8;i++){X.fillStyle=i%2?'#f2ece0':'#9a948a';X.fillRect(x0+i*TS/8,y0,TS/8,TS)}speckle(X,x0,y0,TS,TS,rng(6),400,200,60,.25)}
  {const [x0,y0]=at(T_RAIL);planks(X,x0,y0,TS,TS,rng(9),'v',[230,218,200]);X.fillStyle=rgb(40,30,22);for(let x=10;x<TS;x+=21)X.fillRect(x0+x,y0+30,8,TS-60);X.fillStyle=rgb(200,186,166);X.fillRect(x0,y0,TS,30);X.fillRect(x0,y0+TS-30,TS,30)}
  {const [x0,y0]=at(T_CLOTH);X.fillStyle='#ece6da';X.fillRect(x0,y0,TS,TS);speckle(X,x0,y0,TS,TS,rng(7),500,200,60,.3)}
  {const [x0,y0]=at(T_WHITE);X.fillStyle='#fff';X.fillRect(x0,y0,TS,TS)}
  {const [x0,y0]=at(T_PAVE);const R=rng(8);X.fillStyle='#bdb5a6';X.fillRect(x0,y0,TS,TS);for(let y=0;y<TS;y+=32)for(let x=-(y/32%2)*16;x<TS;x+=32){const k=214+R()*28;X.fillStyle=rgb(k,k*.97,k*.9);X.fillRect(x0+Math.max(0,x)+2,y0+y+2,28,28)}}
  {const [x0,y0]=at(T_WATER);const g=X.createLinearGradient(0,y0,0,y0+TS);g.addColorStop(0,'#8fa6a8');g.addColorStop(1,'#5f7c80');X.fillStyle=g;X.fillRect(x0,y0,TS,TS)}
  return c}
