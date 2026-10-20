/* props/kit.js —— 港口生活的程序化部件（代码，不是图）。归 props+flora 代理（CS 线，lookdev 第 2 轮）。
   每个部件 = 一块合并好的 BufferGeometry（位置 + 法线 + 顶点色），原点在部件脚下中心，+x = 船头 / 前方，y 向上。
   单位 = 页面像素（1 像素 ≈ 0.84 米）。实例化在 props.js / flora.js 里做（InstancedMesh + instanceColor 微调色）。 */
let T=null;
export function setThree(three){T=three}
const C=hex=>{const c=new T.Color(hex);return [c.r,c.g,c.b]};

/* 合并：parts = [{g, m?(Matrix4), c:[r,g,b] | (x,y,z)=>[r,g,b]}]；全部转成非索引 */
export function merge(parts){let n=0;const gs=parts.map(p=>{let g=p.g.index?p.g.toNonIndexed():p.g.clone();if(p.m)g.applyMatrix4(p.m);if(!g.attributes.normal)g.computeVertexNormals();n+=g.attributes.position.count;return g});
  const pos=new Float32Array(n*3),nor=new Float32Array(n*3),col=new Float32Array(n*3);let o=0;
  gs.forEach((g,i)=>{const P=g.attributes.position.array,N=g.attributes.normal.array,c=parts[i].c,k=g.attributes.position.count;pos.set(P,o*3);nor.set(N,o*3);
    for(let j=0;j<k;j++){const cc=typeof c==='function'?c(P[j*3],P[j*3+1],P[j*3+2]):c;col[(o+j)*3]=cc[0];col[(o+j)*3+1]=cc[1];col[(o+j)*3+2]=cc[2]}o+=k;g.dispose()});
  const G=new T.BufferGeometry();G.setAttribute('position',new T.BufferAttribute(pos,3));G.setAttribute('normal',new T.BufferAttribute(nor,3));G.setAttribute('color',new T.BufferAttribute(col,3));G.computeBoundingSphere();return G}

const M=()=>new T.Matrix4();
const TRS=(x,y,z,rx=0,ry=0,rz=0,sx=1,sy=1,sz=1)=>M().compose(new T.Vector3(x,y,z),new T.Quaternion().setFromEuler(new T.Euler(rx,ry,rz,'YXZ')),new T.Vector3(sx,sy,sz));
/* 两点之间的细杆（绳、桁、桨）：box 沿 a→b */
function rod(a,b,r){const A=new T.Vector3(...a),B=new T.Vector3(...b),d=B.clone().sub(A),L=d.length();const g=new T.BoxGeometry(r,L,r);g.translate(0,L/2,0);
  const q=new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());g.applyMatrix4(M().compose(A,q,new T.Vector3(1,1,1)));return g}
function cylY(r0,r1,h,seg=6){const g=new T.CylinderGeometry(r1,r0,h,seg,1);g.translate(0,h/2,0);return g}

/* ---- 船壳：按站位放样（u ∈ [-1,1]，+1 船头）。
   L 全长、B 最大宽、H 舷高（水线以上）、D 吃水、sheer 首尾起翘、bow 船头尖度（越大越尖）、open=true 敞口小艇 ---- */
function hull({L,B,H,D,sheer=1.6,bow=1.4,stern=1.0,open=false,cTop,cHull,cWale,cIn}){
  const NS=14,sec=[[0,-1],[.55,-.78],[.9,-.3],[1,.25],[1,1]];/* 半剖面：(宽比, 高比) 从龙骨到舷缘 */
  const pos=[],col=[];const st=[];
  for(let i=0;i<=NS;i++){const u=-1+2*i/NS,a=Math.abs(u),e=u>0?bow:stern,w=Math.pow(Math.max(0,1-Math.pow(a,1.8)),.5*e)*.5*B+.04,
    sh=H+sheer*Math.pow(a,3)*(u>0?1:1.25),dk=D*(1-.35*a*a);st.push({x:u*L/2,w,sh,dk})}
  const P=(s,k,side)=>{const q=sec[k];return [s.x,q[1]<0?q[1]*s.dk:q[1]*s.sh,side*q[0]*s.w]};
  const tri=(a,b,c,cc)=>{pos.push(...a,...b,...c);for(let j=0;j<3;j++)col.push(...cc)};
  for(let i=0;i<NS;i++)for(const side of [1,-1])for(let k=0;k<sec.length-1;k++){const a=P(st[i],k,side),b=P(st[i+1],k,side),c=P(st[i+1],k+1,side),d=P(st[i],k+1,side);
    const cc=k>=3?cTop:(k===2?cWale:cHull);if(side>0){tri(a,b,c,cc);tri(a,c,d,cc)}else{tri(a,c,b,cc);tri(a,d,c,cc)}}
  /* 首尾封口 */for(const [i,sg] of [[0,-1],[NS,1]]){const s=st[i];for(let k=0;k<sec.length-1;k++){const a=P(s,k,1),b=P(s,k+1,1),c=P(s,k+1,-1),d=P(s,k,-1);if(sg>0){tri(a,b,c,cHull);tri(a,c,d,cHull)}else{tri(a,c,b,cHull);tri(a,d,c,cHull)}}}
  /* 甲板（敞口小艇就是船舱底，低一点） */const dy=open?-.2*D:.82;for(let i=0;i<NS;i++){const s0=st[i],s1=st[i+1],y0=open?dy:Math.min(s0.sh,s1.sh)*dy,w0=s0.w*.96,w1=s1.w*.96;
    tri([s0.x,y0,-w0],[s1.x,y0,-w1],[s1.x,y0,w1],cIn);tri([s0.x,y0,-w0],[s1.x,y0,w1],[s0.x,y0,w0],cIn);
    if(open){/* 内舷 */tri([s0.x,y0,w0],[s1.x,y0,w1],[s1.x,s1.sh,s1.w*.94],cIn);tri([s0.x,y0,w0],[s1.x,s1.sh,s1.w*.94],[s0.x,s0.sh,s0.w*.94],cIn);
      tri([s0.x,y0,-w0],[s1.x,s1.sh,-s1.w*.94],[s1.x,y0,-w1],cIn);tri([s0.x,y0,-w0],[s0.x,s0.sh,-s0.w*.94],[s1.x,s1.sh,-s1.w*.94],cIn)}}
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.computeVertexNormals();
  return {g,c:(x,y,z)=>{/* 按三角形自带色：用位置找回不了，所以单独存 */return null},col,st}}
function hullPart(o){const h=hull(o);const n=h.g.attributes.position.count,colArr=h.col;return {g:h.g,c:null,_col:colArr,st:h.st}}
/* merge 的变体：允许 part 自带逐顶点色数组 */
function mergeX(parts){const flat=[];for(const p of parts){if(p._col){const g=p.g;g.setAttribute('color',new T.Float32BufferAttribute(p._col,3));flat.push({g,c:'own'})}else flat.push(p)}
  let n=0;const gs=flat.map(p=>{let g=p.g.index?p.g.toNonIndexed():p.g;if(p.m)g=g.clone().applyMatrix4(p.m);if(!g.attributes.normal)g.computeVertexNormals();n+=g.attributes.position.count;return g});
  const pos=new Float32Array(n*3),nor=new Float32Array(n*3),col=new Float32Array(n*3);let o=0;
  gs.forEach((g,i)=>{const k=g.attributes.position.count;pos.set(g.attributes.position.array,o*3);nor.set(g.attributes.normal.array,o*3);
    if(flat[i].c==='own')col.set(g.attributes.color.array,o*3);else for(let j=0;j<k;j++)col.set(flat[i].c,(o+j)*3);o+=k});
  const G=new T.BufferGeometry();G.setAttribute('position',new T.BufferAttribute(pos,3));G.setAttribute('normal',new T.BufferAttribute(nor,3));G.setAttribute('color',new T.BufferAttribute(col,3));G.computeBoundingSphere();return G}

const PAL=()=>({tar:C(0x3a2a1e),hull:C(0x5e4128),wale:C(0x2c1f16),top:C(0x8a6440),deck:C(0x9c7a52),mast:C(0x6b4c30),sail:C(0xd9ccad),sail2:C(0xc9b48c),rope:C(0x4a3a2a),red:C(0x8c3b2a),ochre:C(0xa8743a),blue:C(0x3b4a6b)});

/* 圆腹商船（corbita / 粮船）：深腹、高尾鹅颈、主桅收帆、前斜桅、双舵桨、尾舱 */
export function roundShip(variant=0){const p=PAL(),L=36,B=10,H=3.6,D=2.2;
  const hp=hullPart({L,B,H,D,sheer:2.2,bow:1.2,stern:.9,cTop:variant?p.top:p.ochre,cHull:p.hull,cWale:p.wale,cIn:p.deck});const parts=[hp];
  const deckY=H*.82,mx=L*.06;
  parts.push({g:cylY(.42,.3,24),m:TRS(mx,deckY,0),c:p.mast});                     /* 主桅 */
  parts.push({g:rod([mx,deckY+20,-11],[mx,deckY+20,11],.35),c:p.mast});           /* 帆桁 */
  parts.push({g:new T.CylinderGeometry(.9,.9,21,6).rotateX(Math.PI/2),m:TRS(mx+.35,deckY+19.2,0),c:variant?p.sail2:p.sail});/* 收起的帆 */
  parts.push({g:rod([L/2-1,H+1.5,0],[L/2+4.5,H+7,0],.3),c:p.mast});               /* 前斜桅 artemon */
  for(const s of [-1,1]){parts.push({g:rod([mx,deckY+23.5,0],[L/2-1,H+1.8,s*.4],.09),c:p.rope});parts.push({g:rod([mx,deckY+23.5,0],[-L/2+3,H+2.2,s*3.6],.09),c:p.rope});
    parts.push({g:rod([mx,deckY+20,s*11],[-L/2+5,H+1,s*3.8],.07),c:p.rope});
    parts.push({g:rod([-L/2+4,H+2.6,s*(B/2+.3)],[-L/2+1.5,-D*.9,s*(B/2+.9)],.45),c:p.wale})}/* 舵桨 */
  parts.push({g:new T.BoxGeometry(6,2.6,B*.62),m:TRS(-L/2+7.5,deckY+1.3,0),c:p.top});           /* 尾舱 */
  parts.push({g:new T.BoxGeometry(6.6,.35,B*.7),m:TRS(-L/2+7.5,deckY+2.75,0),c:p.wale});
  parts.push({g:rod([-L/2+.6,H+1.6,0],[-L/2-1.6,H+5.2,0],.8),c:p.wale});               /* 鹅颈尾柱 */
  parts.push({g:new T.BoxGeometry(5,1.2,B*.55),m:TRS(L*.22,deckY+.6,0),c:p.sail2});      /* 甲板上的货（盖布） */
  return mergeX(parts)}

/* 窄长沿岸船（带桨的小商船 / 小桨帆船）：低舷、单桅、两排桨收在舷边 */
export function galley(){const p=PAL(),L=30,B=5.6,H=2.2,D=1.3;
  const parts=[hullPart({L,B,H,D,sheer:1.6,bow:2.2,stern:1.1,cTop:p.red,cHull:p.tar,cWale:p.wale,cIn:p.deck})];
  parts.push({g:cylY(.3,.22,16),m:TRS(L*.1,H*.8,0),c:p.mast});
  parts.push({g:rod([L*.1,H*.8+13,-7.5],[L*.1,H*.8+13,7.5],.25),c:p.mast});
  parts.push({g:new T.CylinderGeometry(.65,.65,14,6).rotateX(Math.PI/2),m:TRS(L*.1+.3,H*.8+12.4,0),c:p.sail});
  for(let i=0;i<8;i++){const x=-L*.32+i*L*.075;for(const s of [-1,1])parts.push({g:rod([x,H+.2,s*B*.48],[x-1.2,-.1,s*(B*.5+5.5)],.18),c:p.mast})}/* 桨，靠泊时斜放 */
  parts.push({g:rod([L/2-.5,H+.6,0],[L/2+3,H+.2,0],.5),c:p.wale});                     /* 船艏冲角状龙骨头 */
  for(const s of [-1,1])parts.push({g:rod([-L/2+2.5,H+1.4,s*(B/2+.2)],[-L/2+.5,-D*.8,s*(B/2+.6)],.35),c:p.wale});
  parts.push({g:new T.BoxGeometry(3.2,1.3,B*.6),m:TRS(-L/2+4.5,H*.8+.65,0),c:p.top});
  return mergeX(parts)}

/* 小艇（驳船 / 渔船）：敞口，两道横坐板，长 9 */
export function skiff(){const p=PAL(),L=9,B=2.8,H=.9,D=.5;const parts=[hullPart({L,B,H,D,sheer:.5,bow:1.6,stern:1.3,open:true,cTop:p.top,cHull:p.hull,cWale:p.wale,cIn:p.deck})];
  for(const x of [-1.6,1.4])parts.push({g:new T.BoxGeometry(.35,.15,B*.86),m:TRS(x,H*.55,0),c:p.mast});
  for(const s of [-1,1])parts.push({g:rod([.2,H*.7,s*.9],[-3.2,H*.6,s*.3],.14),c:p.mast});
  return mergeX(parts)}
/* 驳船（往大船上搬货用）：宽平，舱里堆麻袋 */
export function lighter(){const p=PAL(),L=13,B=4.4,H=1.1,D=.6;const parts=[hullPart({L,B,H,D,sheer:.35,bow:.9,stern:.8,open:true,cTop:p.top,cHull:p.tar,cWale:p.wale,cIn:p.deck})];
  const sk=sackGeo();for(let i=0;i<7;i++){const x=-3.5+(i%4)*2.1+(i>3?1:0),z=i>3?.7:-.6,y=i>3?.9:.35;parts.push({g:sk.clone(),m:TRS(x,y-.1,z,0,i*.7,0,1,1,1),c:C(0xb89e70)})}
  parts.push({g:rod([-L/2+.6,H,0],[-L/2-2.4,-.3,0],.3),c:p.wale});
  return mergeX(parts)}

/* ---- 货 ---- */
export function amphoraGeo(){const pts=[[.0,0],[.15,.1],[.34,.6],[.3,.95],[.1,1.22],[.12,1.42],[0,1.44]].map(q=>new T.Vector2(q[0],q[1]));
  const g=new T.LatheGeometry(pts,5);/* 双耳：一块横贯瓶颈的薄板 */return merge([{g,c:[1,1,1]},{g:new T.BoxGeometry(.5,.24,.06).translate(0,1.24,0),c:[.92,.92,.92]}])}
export function sackGeo(){/* 枕头形：细分的盒子，中间鼓、四角收、顶上压扁一点 */const g=new T.BoxGeometry(1.15,.5,.8,2,1,2).toNonIndexed(),P=g.attributes.position;
  for(let i=0;i<P.count;i++){let x=P.getX(i),y=P.getY(i),z=P.getZ(i);const cx=Math.abs(x)<.01,cz=Math.abs(z)<.01;if(cx&&cz){y*=1.35}else if(cx){z*=1.12;y*=1.1}else if(cz){x*=1.08;y*=1.1}else{x*=.86;z*=.82;y*=.8}
    P.setXYZ(i,x,y+.25,z)}g.computeVertexNormals();return g}
export function sackMerged(){return merge([{g:sackGeo(),c:[1,1,1]}])}
export function crateGeo(){const parts=[{g:new T.BoxGeometry(1.2,.95,.95).translate(0,.475,0),c:[1,1,1]}];
  for(const y of [.08,.87])parts.push({g:new T.BoxGeometry(1.24,.1,.99).translate(0,y,0),c:[.7,.7,.7]});return merge(parts)}
export function baleGeo(){return merge([{g:new T.CylinderGeometry(.42,.42,1.1,7).rotateZ(Math.PI/2).translate(0,.42,0),c:[1,1,1]},{g:new T.TorusGeometry(.43,.05,3,7).rotateY(Math.PI/2).translate(0,.42,0),c:[.55,.5,.42]}])}
export function bollardGeo(){const st=C(0x6d675c),r=C(0x4a3a2a);return merge([{g:cylY(.38,.32,1.1,6),c:st},{g:new T.CylinderGeometry(.42,.42,.18,6).translate(0,1.12,0),c:st},{g:new T.TorusGeometry(.4,.09,3,6).rotateX(Math.PI/2).translate(0,.7,0),c:r}])}
/* 手推车：两轮、车斗、把手 */
export function cartGeo(){const p=PAL(),parts=[{g:new T.BoxGeometry(2.2,.5,1.4).translate(0,1.05,0),c:p.top}];
  for(const s of [-1,1]){parts.push({g:new T.TorusGeometry(.62,.1,3,9).translate(0,.62,s*.82),c:p.wale});parts.push({g:rod([-1.1,1.1,s*.5],[-2.6,.7,s*.5],.12),c:p.mast})}
  parts.push({g:new T.BoxGeometry(1.4,.45,1),m:TRS(.1,1.45,0),c:C(0xcdbb94)});return merge(parts)}

/* 踏轮吊车（polyspastos）：A 字主臂向前（+x，朝水）斜出，底座踏轮、拉索、吊着一包货 */
export function craneGeo(){const p=PAL(),wood=C(0x6e5034),dark=C(0x3f2e20),parts=[];const H=17,lean=5.5;
  for(const s of [-1,1])parts.push({g:rod([-1,0,s*2.2],[lean,H,s*.35],.5),c:wood});            /* 两条主臂 */
  parts.push({g:rod([lean,H,-.8],[lean,H,.8],.4),c:wood});
  for(const s of [-1,1])parts.push({g:rod([-6,0,s*1.8],[lean,H,s*.3],.18),c:p.rope});           /* 后拉索 */
  parts.push({g:new T.BoxGeometry(8,.5,5.2),m:TRS(-2.5,.25,0),c:dark});                          /* 底座 */
  const R=3.4;parts.push({g:new T.TorusGeometry(R,.28,4,16),m:TRS(-3,R+.5,0,0,0,0,1,1,1),c:wood});/* 踏轮（立在 xy 面） */
  parts.push({g:new T.TorusGeometry(R,.28,4,16),m:TRS(-3,R+.5,1.6),c:wood});
  for(let k=0;k<6;k++){const a=k*Math.PI/6;parts.push({g:rod([-3-Math.cos(a)*R,R+.5-Math.sin(a)*R,.8],[-3+Math.cos(a)*R,R+.5+Math.sin(a)*R,.8],.16),c:wood})}
  for(let k=0;k<10;k++){const a=k*Math.PI/5;parts.push({g:rod([-3+Math.cos(a)*R,R+.5+Math.sin(a)*R,0],[-3+Math.cos(a)*R,R+.5+Math.sin(a)*R,1.6],.14),c:wood})}
  for(const s of [-1,1])parts.push({g:rod([-3,0,s*1.4],[-3,R+.6,s*1.2],.3),c:wood});
  parts.push({g:rod([-3,R+.5,.8],[lean,H,0],.08),c:p.rope});                                    /* 起吊绳 */
  parts.push({g:rod([lean+.3,H,0],[lean+.3,6,0],.09),c:p.rope});
  const sk=sackGeo();parts.push({g:sk,m:TRS(lean+.3,4.6,0,0,0,0,1.6,1.8,1.6),c:C(0xcdbb94)});
  return merge(parts)}

/* ---- 植物（flora 用） ---- */
function lumpy(det,seed,amp){const g=new T.IcosahedronGeometry(1,det),P=g.attributes.position;const h=(i,k)=>{let x=Math.imul(i+seed*131|0,2654435761)^Math.imul(k,40503);x^=x>>>15;x=Math.imul(x,2246822519);x^=x>>>13;return ((x>>>0)%1000)/1000};
  /* 同一顶点（非索引化前）共用：按坐标取哈希，免得裂缝 */for(let i=0;i<P.count;i++){const x=P.getX(i),y=P.getY(i),z=P.getZ(i),k=Math.round((x*7+y*13+z*17)*100);const r=1+amp*(h(k,1)-.5)*2;P.setXYZ(i,x*r,y*r,z*r)}g.computeVertexNormals();return g}
/* 橄榄：歪干 + 三团灰绿树冠（原点 = 树脚，高 ≈ 2.4，冠宽 ≈ 2.4；按 size 缩放） */
export function oliveGeo(v=0){const tr=C(0x5a4a3a),f1=C(0x73796f),f2=C(0x868c76),f3=C(0x5f6a58);const parts=[];
  parts.push({g:rod([0,0,0],[.25+.1*v,1.1,.1],.32),c:tr});parts.push({g:rod([.25,1.0,.1],[-.35,1.5,-.2],.2),c:tr});
  const L=[[.3,1.75,.2,.95,f1],[-.55,1.55,-.3,.8,f3],[.05,2.05,-.45,.75,f2],[.0,1.45,.65,.7,f1]];
  L.forEach((l,i)=>{parts.push({g:lumpy(i<2?1:0,v*7+i,.22),m:TRS(l[0],l[1],l[2],0,0,0,l[3],l[3]*.72,l[3]),c:l[4]})});return merge(parts)}
/* 柏：细干 + 两节锥（上节更尖），深绿 */
export function cypressGeo(v=0){const tr=C(0x4a3a2c),f1=C(0x2c3a24),f2=C(0x37482c);return merge([{g:cylY(.12,.1,.5,5),c:tr},
  {g:new T.ConeGeometry(.5,.62,8).translate(0,.55+.31,0),c:f2},{g:new T.ConeGeometry(.4,.62,8).translate(0,.95,0),c:f1},{g:new T.SphereGeometry(.47,8,4).scale(1,.6,1).translate(0,.5,0),c:f2}])}
/* 园子树（无花果 / 石榴 / 果树）：矮干、宽冠、两团，偏黄绿 */
export function gardenGeo(v=0){const tr=C(0x5a4632),f1=C(0x5e7a3c),f2=C(0x6f8a46),fr=C(0x9a3a2a);const parts=[{g:rod([0,0,0],[.1,.9,0],.26),c:tr}];
  parts.push({g:lumpy(1,30+v,.18),m:TRS(.15,1.35,0,0,0,0,1.15,.75,1.05),c:f1});parts.push({g:lumpy(0,40+v,.2),m:TRS(-.5,1.15,.35,0,0,0,.7,.55,.7),c:f2});
  if(v%2)for(let k=0;k<4;k++)parts.push({g:new T.OctahedronGeometry(.12,0),m:TRS(Math.cos(k*1.7)*.9,1.15+(k%2)*.3,Math.sin(k*1.7)*.85),c:fr});return merge(parts)}
/* 灌木（月桂 / 夹竹桃 / 迷迭香）：低矮一团 */
export function shrubGeo(v=0){const cs=[C(0x4f5e3a),C(0x5d6b45),C(0x6a6e50)];return merge([{g:lumpy(0,60+v,.28),m:TRS(0,.42,0,0,0,0,.75,.5,.7),c:cs[v%3]},{g:lumpy(0,70+v,.25),m:TRS(.45,.3,.2,0,0,0,.45,.35,.45),c:cs[(v+1)%3]}])}
/* 葡萄架（pergola）：四柱 + 横梁 + 一层不齐的叶 */
export function pergolaGeo(){const wood=C(0x6b5038),leaf=C(0x5a7038),leaf2=C(0x6c8240);const parts=[];
  for(const x of [-2,2])for(const z of [-1.2,1.2])parts.push({g:cylY(.1,.1,2.1,4),m:TRS(x,0,z),c:wood});
  for(const z of [-1.2,1.2])parts.push({g:new T.BoxGeometry(4.4,.14,.14),m:TRS(0,2.1,z),c:wood});
  for(let i=0;i<5;i++)parts.push({g:new T.BoxGeometry(.1,.1,2.8),m:TRS(-2+i,2.18,0),c:wood});
  for(let i=0;i<6;i++)parts.push({g:lumpy(0,80+i,.3),m:TRS(-1.9+i*.76,2.3,(i%2?.35:-.3),0,0,0,.6,.22,.95),c:i%2?leaf:leaf2});
  for(const x of [-2,2])parts.push({g:lumpy(0,90+x,.3),m:TRS(x,1.1,1.2,0,0,0,.25,1,.25),c:leaf});
  return merge(parts)}
