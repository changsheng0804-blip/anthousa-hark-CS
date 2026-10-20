/* streets/tex.js —— 街面的程序化贴图（全部在代码里画，不下载、不贴照片）。
   每张贴图 = 颜色画布 + 由高度场算出的法线画布，两向都可平铺（坐标取模）。
   确定性：只用 hsh(seed,k)，不用 Math.random。——Hark（CS线）2026-10-20 */

const clamp=(v,a,b)=>v<a?a:v>b?b:v;

/* 可平铺的值噪声：周期 P 个格点，n 格点/边 */
function vnoise(hsh,seed,P){const g=new Float32Array(P*P);for(let i=0;i<P*P;i++)g[i]=hsh(seed*7919+i,3);
  return (u,v)=>{/* u,v ∈ [0,1) 平铺 */const x=((u%1)+1)%1*P,y=((v%1)+1)%1*P,i=x|0,j=y|0,fx=x-i,fy=y-j,sx=fx*fx*(3-2*fx),sy=fy*fy*(3-2*fy),
    a=g[j*P+i],b=g[j*P+(i+1)%P],c=g[((j+1)%P)*P+i],d=g[((j+1)%P)*P+(i+1)%P];return (a*(1-sx)+b*sx)*(1-sy)+(c*(1-sx)+d*sx)*sy}}
function fbm(hsh,seed,base){const o=[vnoise(hsh,seed,base),vnoise(hsh,seed+1,base*2),vnoise(hsh,seed+2,base*4),vnoise(hsh,seed+3,base*8)];
  return (u,v)=>(o[0](u,v)*.5+o[1](u,v)*.25+o[2](u,v)*.15+o[3](u,v)*.1)}

/* 高度场 → 法线画布（tangent space，平铺取模） */
function normalCanvas(Hf,N,str){const c=document.createElement('canvas');c.width=c.height=N;const X=c.getContext('2d'),im=X.createImageData(N,N),d=im.data;
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){const h=(i,j)=>Hf[((j+N)%N)*N+((i+N)%N)];
    const dx=(h(x+1,y)-h(x-1,y))*str,dy=(h(x,y+1)-h(x,y-1))*str,l=Math.hypot(dx,dy,1),k=(y*N+x)*4;
    d[k]=(-dx/l*.5+.5)*255;d[k+1]=(dy/l*.5+.5)*255;d[k+2]=(1/l*.5+.5)*255;d[k+3]=255}
  X.putImageData(im,0,0);return c}
function colorCanvas(C,N){const c=document.createElement('canvas');c.width=c.height=N;const X=c.getContext('2d'),im=X.createImageData(N,N);im.data.set(C);X.putImageData(im,0,0);return c}

/* ---- 石板（主街车道、人行道、广场、支街）：成排的「行」，行内石板宽窄不一，相邻行错缝 ----
   o: {N, rows:[min,max] 行深（贴图像素）, cols:[min,max] 石板宽, base:[r,g,b], var 明暗幅度, grout 缝宽, groutCol,
       ruts:[v0,v1,…] 车辙中心（0..1，沿 v），rutW, gutter 两边（v=0、v=1）沟宽, wear 0..1, seed}
   行沿 u 方向排（u = 沿街），石板在 v 方向切开（v = 横过街）。 */
export function slabs(hsh,o){const N=o.N,S=o.seed||1,C=new Uint8ClampedArray(N*N*4),Hf=new Float32Array(N*N);
  const id=new Int32Array(N*N),ed=new Float32Array(N*N);/* 每像素：石板编号、到石板边的距离 */
  /* 行：沿 u 切 N 像素成若干行（行深和为 N，平铺） */
  const rows=[];{let u=0,k=0;while(u<N){let d=Math.round(o.rows[0]+(o.rows[1]-o.rows[0])*hsh(S*131+k,1));if(N-u-d<o.rows[0])d=N-u;rows.push([u,d]);u+=d;k++}}
  let sid=0;const tone=[],tint=[];
  rows.forEach(([u0,du],r)=>{/* 本行在 v 方向切石板，起点错开，绕回平铺 */
    const off=Math.floor(hsh(S*977+r,2)*N);const cuts=[];let v=0,k=0;while(v<N){let w=Math.round(o.cols[0]+(o.cols[1]-o.cols[0])*hsh(S*313+r*97+k,4));if(N-v-w<o.cols[0])w=N-v;cuts.push([v,w]);v+=w;k++}
    for(const [v0,w] of cuts){const me=sid++;tone.push((hsh(S*51+me,5)-.5)*2);tint.push((hsh(S*53+me,6)-.5)*2);
      for(let uu=u0;uu<u0+du;uu++)for(let vv=v0;vv<v0+w;vv++){const y=(vv+off)%N,x=uu,p=y*N+x;id[p]=me;ed[p]=Math.min(uu-u0+.5,u0+du-uu-.5,vv-v0+.5,v0+w-vv-.5)}}});
  const n1=fbm(hsh,S*11+1,8),n2=fbm(hsh,S*11+7,32),nw=fbm(hsh,S*11+13,4),n3=fbm(hsh,S*11+17,48),n4=fbm(hsh,S*11+19,24);
  const g=o.grout,b=o.base,gc=o.groutCol||[70,62,52];
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){const p=y*N+x,u=x/N,v=y/N,s=id[p],e=ed[p];
    /* 车辙：沿街的两条亮、低、光滑的带 */let rut=0;if(o.ruts)for(const rv of o.ruts){const dv=Math.abs(v-rv);rut=Math.max(rut,clamp(1-dv/o.rutW,0,1))}rut=rut*rut*(3-2*rut);
    /* 沟：v 两边发暗、发湿 */let gut=0;if(o.gutter){gut=clamp(1-Math.min(v,1-v)/o.gutter,0,1);gut*=gut}
    const wear=(o.wear||0)*(nw(u,v)-.35);
    let h=0,L,cr=b[0],cg=b[1],cb=b[2];
    const ej=e+(n3(u,v)-.5)*g*2.2+(hsh(s,11)-.5)*g*.8;/* 缝宽不匀、石板边不直 */
    const chip=hsh(s,12)<.25&&e<g*3.5&&n4(u,v)>.62;/* 缺角/崩边 */
    if(ej<g||chip){/* 缝：深、低 */const t=clamp(Math.max(0,ej)/g,0,1);h=-1+t*.4;L=.42+.18*t+.1*n2(u,v);cr=gc[0];cg=gc[1];cb=gc[2]}
    else{const bev=clamp((ej-g)/(o.bevel||3),0,1);h=bev*bev*(3-2*bev)*.9+ (n2(u,v)-.5)*.35 - rut*.25;
      L=1+tone[s]*o.var+(n1(u,v)-.5)*.3+(n2(u,v)-.5)*.22;L*=.84+.16*bev;/* 边上磨圆、发暗 */L+=rut*.14-wear*.12;if(hsh(s,13)<.06)L*=.8;/* 后换的石板 */
      const ti=tint[s]*.025;cr*=1+ti;cb*=1-ti}
    L*=1-gut*.38;/* 沟脏 */
    /* 零星裂纹和缺角 */if(e>=g&&hsh(s,9)<.08){const t=Math.abs(((x*0.7+y*0.3+s*13)%((o.cols[0]+o.rows[0])))-(o.rows[0]*.6));if(t<.8){L*=.68;h-=.5}}
    const k=p*4;C[k]=cr*L;C[k+1]=cg*L;C[k+2]=cb*L;C[k+3]=255;Hf[p]=h}
  return {map:colorCanvas(C,N),normal:normalCanvas(Hf,N,o.nstr||1.6)}}

/* ---- 卵石 / 碎石（巷子）：平铺的 Voronoi，每格一块圆头石，缝里是土 ---- */
export function cobbles(hsh,o){const N=o.N,G=o.cells,S=o.seed||7,C=new Uint8ClampedArray(N*N*4),Hf=new Float32Array(N*N);
  const pts=[];for(let j=0;j<G;j++)for(let i=0;i<G;i++){const q=j*G+i;pts.push([(i+.15+.7*hsh(S*17+q,1))/G,(j+.15+.7*hsh(S*17+q,2))/G])}
  const n2=fbm(hsh,S*5+3,32),nd=fbm(hsh,S*5+9,6),b=o.base,dirt=o.dirt;
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){const u=(x+.5)/N,v=(y+.5)/N,ci=Math.floor(u*G),cj=Math.floor(v*G);let d1=9,d2=9,best=0;
    for(let dj=-1;dj<=1;dj++)for(let di=-1;di<=1;di++){const ii=(ci+di+G)%G,jj=(cj+dj+G)%G,P=pts[jj*G+ii];let px=P[0]+Math.floor((ci+di)/G)*1,py=P[1]+Math.floor((cj+dj)/G)*1;
      /* 绕回 */if(ci+di<0)px=P[0]-1;else if(ci+di>=G)px=P[0]+1;else px=P[0];if(cj+dj<0)py=P[1]-1;else if(cj+dj>=G)py=P[1]+1;else py=P[1];
      const d=Math.hypot(u-px,v-py);if(d<d1){d2=d1;d1=d;best=jj*G+ii}else if(d<d2)d2=d}
    const e=(d2-d1)*G;/* 到缝的距离（格单位） */const r=clamp(e/o.gap,0,1),dome=Math.sqrt(clamp(r*1.4,0,1));
    const p=y*N+x,k=p*4,t=(hsh(S*29+best,4)-.5)*2;let cr,cg,cb,L;
    if(r<.25){cr=dirt[0];cg=dirt[1];cb=dirt[2];L=.62+.25*nd(u,v)}else{cr=b[0]*(1+t*.05);cg=b[1];cb=b[2]*(1-t*.05);L=(1+t*o.var+(n2(u,v)-.5)*.2)*(.72+.28*dome)}
    const mud=clamp((nd(u,v)-.55)*2.2,0,1)*(o.mud||0);L*=1-mud*.25;
    C[k]=cr*L;C[k+1]=cg*L;C[k+2]=cb*L;C[k+3]=255;Hf[p]=r<.25?-1:dome-.2+(n2(u,v)-.5)*.2}
  return {map:colorCanvas(C,N),normal:normalCanvas(Hf,N,o.nstr||2.2)}}

/* ---- 夯土（小巷）：土色起伏 + 碎石子 + 两道踩出来的浅辙 ---- */
export function earth(hsh,o){const N=o.N,S=o.seed||3,C=new Uint8ClampedArray(N*N*4),Hf=new Float32Array(N*N);
  const n1=fbm(hsh,S*3+1,4),n2=fbm(hsh,S*3+2,16),n3=fbm(hsh,S*3+5,64),b=o.base;
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){const u=x/N,v=y/N,p=y*N+x,k=p*4;let L=1+(n1(u,v)-.5)*.35+(n2(u,v)-.5)*.2+(n3(u,v)-.5)*.18,h=(n2(u,v)-.5)*.8+(n3(u,v)-.5)*.6;
    for(const rv of o.ruts||[]){const dv=Math.abs(v-rv)/o.rutW;if(dv<1){const w=1-dv*dv;L-=w*.1;h-=w*.6}}
    const q=Math.floor(x/3)*977+Math.floor(y/3)*31;if(hsh(S*101+q,7)<.05){L+=.22*(hsh(q,8)-.3);h+=.8}/* 石子 */
    C[k]=b[0]*L;C[k+1]=b[1]*L;C[k+2]=b[2]*L;C[k+3]=255;Hf[p]=h}
  return {map:colorCanvas(C,N),normal:normalCanvas(Hf,N,o.nstr||1.2)}}
