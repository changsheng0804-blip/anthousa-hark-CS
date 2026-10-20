/* streets（lookdev 第 2 轮）：街面。
   两层：
   1) paint：共享地面贴图上的街（m/s/c/l 四级，路缘深色 + 路面）和地标地皮——远景、空中机位靠它（不清画布，只往上画）。
   2) build：贴地薄网格 + 程序化贴图（streets/tex.js），近景靠它：
      主街 m = 车道大石板（错缝、缝、两道磨亮的车辙、两边水沟）+ 两侧路缘石 + 抬高的人行道（铺到房子门口）；
      支街 s = 小一号、更旧的石板 + 低路缘；巷 c = 卵石；小巷 l = 夯土 + 浅辙；地标地皮（广场等）= 大石板。
      网格高度照抄 terrain 网格的三角插值（ctx.ground 在 4 像素格点上），再抬一点 + polygonOffset，不和地面打架。
   写 ctx.reg.frontage（街面朝向：每个街节点两侧的路缘、到房子门口的距离、面向的那户 id）；buildings 读不到就当没有。
   顺手：底账里水务户（fn=water）门前是主街/支街的，在人行道上放一座公共水池（喷泉）。
   确定性：只用 ctx.hsh。——Hark（CS线）2026-10-20 */
import {slabs,cobbles,earth} from './streets/tex.js';
export const name='streets';
export const checkShot=2;

/* ---- 1) 地面贴图层（远景） ---- */
const SC={m:['rgba(118,104,86,.7)','rgb(188,176,154)'],s:['rgba(140,118,88,.4)','rgb(204,188,154)'],c:['rgba(140,118,88,.3)','rgb(206,190,156)'],l:[null,'rgba(212,196,162,.9)']};
export function paint(ctx,X){const {by}=ctx;X.lineCap='round';
  for(let pas=0;pas<2;pas++)for(const k of 'lcsm'){const col=SC[k][pas];if(!col)continue;X.strokeStyle=col;for(const f of by.street){if(f.k!==k||!ctx.live(f))continue;const q=f.g;X.beginPath();X.moveTo(q[0],q[1]);X.lineTo(q[2],q[3]);X.lineWidth=f.w+(pas?0:2);X.stroke()}}
  for(const f of by.landmark||[])if(ctx.live(f)){X.beginPath();f.g.forEach((p,i)=>i?X.lineTo(p[0],p[1]):X.moveTo(p[0],p[1]));X.closePath();X.fillStyle=f.k==='forum'?'rgb(226,218,198)':'rgb(212,200,174)';X.fill()}}

/* ---- 2) 近景网格 ---- */
/* 剖面（页面像素，1 px ≈ 0.84 m）：m 宽 15 → 车道 ±5.2、路缘石 5.2–5.6、人行道 5.6 → 房门（≤ 22）；s 宽 8 → 路缘 3.6–4.0 */
const PROF={m:{kerb:5.2,kw:.36,curb:.2,lift:.11},s:{kerb:3.62,kw:.38,curb:.13,lift:.08},c:{lift:.06},l:{lift:.04}};
const TILE={m:10.4,s:7.24,c:4,l:6,walk:6,plaza:12,kerb:3};/* 贴图一块覆盖多少页面像素（沿街） */
let T=null,M=null,meshes=[],TEX=null;

function mkMat(t,off,ns=.9){const m=new T.MeshLambertMaterial({map:t.map,normalMap:t.normal,normalScale:new T.Vector2(ns,ns),vertexColors:true,side:T.DoubleSide,polygonOffset:true,polygonOffsetFactor:-off,polygonOffsetUnits:-off*2});return m}
function canvasTex(c,rw=true){const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=8;t.generateMipmaps=true;t.minFilter=T.LinearMipmapLinearFilter;return t}
function pack(o){return {map:Object.assign(canvasTex(o.map),{colorSpace:T.SRGBColorSpace}),normal:canvasTex(o.normal)}}

export function init(ctx){T=ctx.THREE;const h=ctx.hsh,hi=ctx.quality!=='preview';const N1=hi?1024:512,N2=hi?512:256;
  TEX={
    m:pack(slabs(h,{N:N1,seed:3,rows:[N1*.045,N1*.085],cols:[N1*.07,N1*.15],base:[184,180,170],var:.09,grout:N1*.0022,groutCol:[96,86,72],bevel:N1*.005,ruts:[.34,.66],rutW:.045,gutter:.06,wear:.6,nstr:1.4})),
    walk:pack(slabs(h,{N:N2,seed:5,rows:[N2*.07,N2*.12],cols:[N2*.08,N2*.15],base:[182,174,158],var:.09,grout:N2*.004,groutCol:[100,90,76],bevel:N2*.01,wear:.8,nstr:1.3})),
    s:pack(slabs(h,{N:N2,seed:9,rows:[N2*.06,N2*.11],cols:[N2*.08,N2*.16],base:[180,170,152],var:.12,grout:N2*.005,groutCol:[92,80,64],bevel:N2*.01,ruts:[.42,.58],rutW:.05,gutter:.07,wear:1,nstr:1.5})),
    c:pack(cobbles(h,{N:N2,seed:11,cells:hi?22:14,gap:.22,base:[170,158,138],dirt:[128,108,82],var:.16,mud:.8})),
    l:pack(earth(h,{N:N2,seed:13,base:[176,152,116],ruts:[.36,.64],rutW:.09})),
    plaza:pack(slabs(h,{N:N1,seed:17,rows:[N1*.07,N1*.1],cols:[N1*.09,N1*.16],base:[208,202,188],var:.1,grout:N1*.003,groutCol:[96,88,76],bevel:N1*.005,wear:.5,nstr:1.2})),
    kerb:pack(slabs(h,{N:256,seed:19,rows:[110,190],cols:[256,256],base:[190,184,170],var:.1,grout:2,groutCol:[100,92,80],bevel:10,wear:.4,nstr:1.2}))};
  M={m:mkMat(TEX.m,4),walk:mkMat(TEX.walk,5),s:mkMat(TEX.s,3),c:mkMat(TEX.c,2,1.1),l:mkMat(TEX.l,1,.7),plaza:mkMat(TEX.plaza,5),kerb:mkMat(TEX.kerb,5),
     marble:new T.MeshLambertMaterial({color:0xe6dfcf}),water:new T.MeshLambertMaterial({color:0x5f7f7c})}}

/* terrain 网格的高度（4 px 格，a,c,b / b,c,d 两个三角）——照抄它，薄网格才贴得住 */
function terrainH(ctx){const S=4,W=ctx.W,H=ctx.H,nx=Math.ceil(W/S)+1,nz=Math.ceil(H/S)+1,G=new Float32Array(nx*nz).fill(NaN);
  const g=(i,j)=>{i=Math.max(0,Math.min(nx-1,i));j=Math.max(0,Math.min(nz-1,j));const k=j*nx+i;let v=G[k];if(v!==v){v=G[k]=ctx.ground(Math.min(W,i*S),Math.min(H,j*S))}return v};
  return (x,z)=>{const fx0=x/S,fz0=z/S,i=Math.floor(fx0),j=Math.floor(fz0),fx=fx0-i,fz=fz0-j;
    if(fx+fz<=1)return g(i,j)+(g(i+1,j)-g(i,j))*fx+(g(i,j+1)-g(i,j))*fz;
    return g(i+1,j+1)+(g(i,j+1)-g(i+1,j+1))*(1-fx)+(g(i+1,j)-g(i+1,j+1))*(1-fz)}}

/* 网格累加器 */
function B(){return {p:[],u:[],c:[],i:[],n:0}}
function vtx(b,x,y,z,u,v,c){b.p.push(x,y,z);b.u.push(u,v);b.c.push(c,c,c*.985);return b.n++}
/* 双面材质：背面时 three 自己翻法线，所以绕向不用管；立面和顶面共点的（路缘、人行道）拆成平面法线，免得法线互相抵消 */
function geomOf(b,flat){let g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(b.p,3));g.setAttribute('uv',new T.Float32BufferAttribute(b.u,2));g.setAttribute('color',new T.Float32BufferAttribute(b.c,3));g.setIndex(b.i);if(flat){const n=g.toNonIndexed();g.dispose();g=n}g.computeVertexNormals();return g}

/* 把一段段的街接成折线（同级、首尾相接） */
function chains(ctx){const key=(x,z)=>Math.round(x*10)+','+Math.round(z*10),out=[];
  for(const k of 'mscl'){const segs=ctx.by.street.filter(f=>f.k===k&&ctx.live(f)&&Math.hypot(f.g[2]-f.g[0],f.g[3]-f.g[1])>.05);const st=new Map(),en=new Map(),used=new Set();
    segs.forEach((f,i)=>{const a=key(f.g[0],f.g[1]),b=key(f.g[2],f.g[3]);if(!st.has(a))st.set(a,[]);st.get(a).push(i);if(!en.has(b))en.set(b,[]);en.get(b).push(i)});
    const take=(m,kk)=>{const L=m.get(kk);if(!L)return -1;for(const i of L)if(!used.has(i)){used.add(i);return i}return -1};
    segs.forEach((f,i)=>{if(used.has(i))return;used.add(i);const pts=[[f.g[0],f.g[1]],[f.g[2],f.g[3]]];let w=f.w;
      for(;;){const e=pts[pts.length-1],j=take(st,key(e[0],e[1]));if(j<0)break;pts.push([segs[j].g[2],segs[j].g[3]])}
      for(;;){const s=pts[0],j=take(en,key(s[0],s[1]));if(j<0)break;pts.unshift([segs[j].g[0],segs[j].g[1]])}
      out.push({k,w,pts,id:out.length})})}
  return out}

/* 加密到 ≤ step，算切线/法线（斜接，限 2 倍）和沿街长度 */
function frame(pts,step){const P=[pts[0]];for(let i=1;i<pts.length;i++){const a=P[P.length-1],b=pts[i],L=Math.hypot(b[0]-a[0],b[1]-a[1]);if(L<1e-3)continue;const n=Math.ceil(L/step);for(let k=1;k<=n;k++)P.push([a[0]+(b[0]-a[0])*k/n,a[1]+(b[1]-a[1])*k/n])}
  const n=P.length,N=[],S=[0];for(let i=0;i<n;i++){const a=P[Math.max(0,i-1)],b=P[Math.min(n-1,i+1)];let tx=b[0]-a[0],tz=b[1]-a[1];const l=Math.hypot(tx,tz)||1;tx/=l;tz/=l;
    let mx=-tz,mz=tx,sc=1;if(i>0&&i<n-1){const d0x=P[i][0]-P[i-1][0],d0z=P[i][1]-P[i-1][1],l0=Math.hypot(d0x,d0z)||1;sc=Math.min(2,1/Math.max(.5,Math.abs((-d0z/l0)*mx+(d0x/l0)*mz)))}
    N.push([mx*sc,mz*sc]);if(i)S.push(S[i-1]+Math.hypot(P[i][0]-P[i-1][0],P[i][1]-P[i-1][1]))}
  return {P,N,S}}

/* 空间格（16 px）：街段、房子 */
function grid(cell){const m=new Map();return {add(x0,z0,x1,z1,o){for(let i=Math.floor(x0/cell);i<=Math.floor(x1/cell);i++)for(let j=Math.floor(z0/cell);j<=Math.floor(z1/cell);j++){const k=i*65536+j;if(!m.has(k))m.set(k,[]);m.get(k).push(o)}},
  at(x,z){return m.get(Math.floor(x/cell)*65536+Math.floor(z/cell))||[]}}}
const inQuad=(q,x,z)=>{let s=0;for(let i=0;i<4;i++){const ax=q[i*2],az=q[i*2+1],bx=q[(i+1)%4*2],bz=q[(i+1)%4*2+1],c=(bx-ax)*(z-az)-(bz-az)*(x-ax);if(c===0)continue;const sg=c>0?1:-1;if(s&&sg!==s)return false;s=sg}return true};
function segDist(x,z,g){const dx=g[2]-g[0],dz=g[3]-g[1],L2=dx*dx+dz*dz||1,t=Math.max(0,Math.min(1,((x-g[0])*dx+(z-g[1])*dz)/L2));return Math.hypot(x-g[0]-t*dx,z-g[1]-t*dz)}

export function build(ctx){const hsh=ctx.hsh,TH=terrainH(ctx),CH=chains(ctx);
  /* 街段格（交叉口判断）+ 房子格（门口距离） */
  const SG=grid(16),HG=grid(16);
  CH.forEach(c=>{for(let i=1;i<c.pts.length;i++){const a=c.pts[i-1],b=c.pts[i];const g=[a[0],a[1],b[0],b[1]];SG.add(Math.min(a[0],b[0])-10,Math.min(a[1],b[1])-10,Math.max(a[0],b[0])+10,Math.max(a[1],b[1])+10,{g,w:c.w,k:c.k,ch:c.id})}});
  for(const f of ctx.by.house||[])if(ctx.live(f)){const p=f.p;HG.add(Math.min(p[0],p[2],p[4],p[6]),Math.min(p[1],p[3],p[5],p[7]),Math.max(p[0],p[2],p[4],p[6]),Math.max(p[1],p[3],p[5],p[7]),f)}
  const crossed=(x,z,ch)=>{for(const s of SG.at(x,z))if(s.ch!==ch&&s.k!=='l'&&segDist(x,z,s.g)<s.w/2+.3)return true;return false};
  const houseAt=(x,z)=>{for(const f of HG.at(x,z))if(inQuad(f.p,x,z))return f;return null};
  const R={m:B(),walk:B(),s:B(),c:B(),l:B(),kerb:B(),plaza:B()},front=[],tint=(a,b)=>.9+.14*hsh(a,b);

  for(const c of CH){const pr=PROF[c.k],F=frame(c.pts,c.k==='m'?3:4),n=F.P.length;if(n<2)continue;const hw=c.w/2;
    const Y=(x,z)=>TH(x,z)+pr.lift,tile=TILE[c.k];
    /* 车道/路面：横向 4–6 列 */
    const cw=pr.kerb||hw,cols=c.k==='m'?4:c.k==='l'?1:2,b=R[c.k],base=b.n;
    for(let i=0;i<n;i++){const [x,z]=F.P[i],[mx,mz]=F.N[i],t=tint(c.id*4099+i,1);for(let j=0;j<=cols;j++){const o=-cw+2*cw*j/cols,px=x+mx*o,pz=z+mz*o;vtx(b,px,Y(px,pz),pz,F.S[i]/tile,j/cols,t*(1-.06*Math.pow(Math.abs(o/cw),6)))}}
    for(let i=0;i<n-1;i++)for(let j=0;j<cols;j++){const a=base+i*(cols+1)+j,bb=a+1,cc=a+cols+1,d=cc+1;b.i.push(a,bb,cc,bb,d,cc)}
    if(!pr.kerb)continue;
    /* 两侧：路缘石（立面 + 顶）、人行道（m） */
    for(const sg of [-1,1]){
      const ok=[],outer=[],who=[];
      for(let i=0;i<n;i++){const [x,z]=F.P[i],[mx,mz]=F.N[i];ok.push(!crossed(x+mx*sg*(cw+.2),z+mz*sg*(cw+.2),c.id));
        let o=hw+1,hh=null;const dmax=c.k==='m'?22:12;for(let d=cw+.8;d<=dmax;d+=1){const f=houseAt(x+mx*sg*d,z+mz*sg*d);if(f){o=Math.max(cw+.8,d-.25);hh=f;break}}outer.push(o);who.push(hh)}
      /* 柱廊下的地坪是连续的：窗口内取最大（补房子之间的缝），再取中值去尖 */
      const mx=outer.map((v,i)=>{let m=v;for(let d=-4;d<=4;d++){const w=outer[Math.min(n-1,Math.max(0,i+d))];if(w>m)m=w}return Math.min(22,m)});
      const os=mx.map((v,i)=>[mx[Math.max(0,i-1)],v,mx[Math.min(n-1,i+1)]].sort((p,q)=>p-q)[1]);
      for(let i=0;i<n;i+=c.k==='m'?2:3){const [x,z]=F.P[i],l=Math.hypot(F.N[i][0],F.N[i][1]);front.push({k:c.k,chain:c.id,x:+x.toFixed(1),z:+z.toFixed(1),nx:+(F.N[i][0]/l*sg).toFixed(3),nz:+(F.N[i][1]/l*sg).toFixed(3),kerb:cw,edge:+os[i].toFixed(1),house:who[i]?who[i].id:null})}
      const K=R.kerb,W_=R.walk;
      for(let i=0;i<n-1;i+=2){const i1=Math.min(n-1,i+2);if(!ok[i]||!ok[i1]||(i+1<n&&!ok[i+1]))continue;/* 路缘、人行道隔一个节点取一段，省三角形 */
        const q=[i,i1].map(ii=>{const [x,z]=F.P[ii],[mx,mz]=F.N[ii],at=o=>[x+mx*sg*o,z+mz*sg*o],y0=Y(...at(cw)),top=TH(...at(cw))+pr.lift+pr.curb;return {at,y0,top,s:F.S[ii],o:os[ii]}});
        /* 路缘立面 + 顶：v 0..0.3 立面、0.3..1 顶 */
        const k0=K.n,t=tint(c.id*31+i,2);
        for(const e of q){const A=e.at(cw),Bq=e.at(cw+pr.kw);vtx(K,A[0],e.y0-.05,A[1],e.s/TILE.kerb,0,t*.8);vtx(K,A[0],e.top,A[1],e.s/TILE.kerb,.3,t);vtx(K,Bq[0],e.top,Bq[1],e.s/TILE.kerb,1,t)}
        const f=sg>0?[0,3,1,1,3,4, 1,4,2,2,4,5]:[0,1,3,1,4,3, 1,2,4,2,5,4];for(const v of f)K.i.push(k0+v);
        if(c.k!=='m')continue;
        /* 人行道：路缘外沿 → 房门；外沿立面落到地 */
        const w0=W_.n;
        for(const e of q){const A=e.at(cw+pr.kw),Bq=e.at(e.o),Mq=e.at((cw+pr.kw+e.o)/2),wt=tint(c.id*77+i,3);const yA=TH(...A)+pr.lift+pr.curb,yB=TH(...Bq)+pr.lift+pr.curb,yM=TH(...Mq)+pr.lift+pr.curb;
          /* 世界坐标 uv，块子不跟着街弯 */
          vtx(W_,A[0],yA,A[1],A[0]/TILE.walk,A[1]/TILE.walk,wt);vtx(W_,Mq[0],yM,Mq[1],Mq[0]/TILE.walk,Mq[1]/TILE.walk,wt*.97);vtx(W_,Bq[0],yB,Bq[1],Bq[0]/TILE.walk,Bq[1]/TILE.walk,wt*.86);vtx(W_,Bq[0],TH(...Bq)-.1,Bq[1],Bq[0]/TILE.walk,Bq[1]/TILE.walk+.03,wt*.7)}
        const g=sg>0?[0,4,1,1,4,5, 1,5,2,2,5,6, 2,6,3,3,6,7]:[0,1,4,1,5,4, 1,2,5,2,6,5, 2,3,6,3,7,6];for(const v of g)W_.i.push(w0+v)}}}

  /* 地标地皮（广场、院子）：按四角双线性铺 5 px 格，石板按世界坐标 */
  for(const f of ctx.by.landmark||[])if(ctx.live(f)&&f.g.length===4){const P=f.g,b=R.plaza,base=b.n,L=Math.max(Math.hypot(P[1][0]-P[0][0],P[1][1]-P[0][1]),Math.hypot(P[3][0]-P[0][0],P[3][1]-P[0][1])),n=Math.max(2,Math.ceil(L/5));
    for(let j=0;j<=n;j++)for(let i=0;i<=n;i++){const u=i/n,v=j/n,x=(P[0][0]*(1-u)+P[1][0]*u)*(1-v)+(P[3][0]*(1-u)+P[2][0]*u)*v,z=(P[0][1]*(1-u)+P[1][1]*u)*(1-v)+(P[3][1]*(1-u)+P[2][1]*u)*v;vtx(b,x,TH(x,z)+.14,z,x/TILE.plaza,z/TILE.plaza,tint(f.seed||7,i*131+j)*.5+.5)}
    for(let j=0;j<n;j++)for(let i=0;i<n;i++){const a=base+j*(n+1)+i,bb=a+1,cc=a+n+1,d=cc+1;b.i.push(a,bb,cc,bb,d,cc)}}

  const per={};for(const k in R){if(!R[k].n)continue;per[k]=R[k].i.length/3;const m=new T.Mesh(geomOf(R[k],k==='kerb'||k==='walk'),M[k]);m.receiveShadow=true;m.castShadow=k==='walk'||k==='kerb';m.name='streets.'+k;ctx.add(m);meshes.push(m)}

  /* 水务户门前的公共水池：同一户取中间那条朝向记录 */
  const byH=new Map();for(const e of front)if(e.house!=null){if(!byH.has(e.house))byH.set(e.house,[]);byH.get(e.house).push(e)}
  const fg=new T.Group(),placed=[];let nf=0;
  for(const f of ctx.by.house||[])if(f.fn==='water'&&ctx.live(f)&&byH.has(f.id)){const L=byH.get(f.id),e=L[L.length>>1];if(e.edge-e.kerb<2.2)continue;if(placed.some(q=>Math.hypot(q[0]-e.x,q[1]-e.z)<40))continue;placed.push([e.x,e.z]);/* 一段街一座就够 */
    const d=(e.kerb+PROF[e.k].kw+e.edge)/2+.2,x=e.x+e.nx*d,z=e.z+e.nz*d,y=TH(x,z)+PROF[e.k].lift+PROF[e.k].curb,ang=Math.atan2(e.nx,e.nz);
    const g=new T.Group();g.position.set(x,y,z);g.rotation.y=ang;
    const box=(w,h,dd,px,py,pz,mat)=>{const o=new T.Mesh(new T.BoxGeometry(w,h,dd),mat);o.position.set(px,py,pz);o.castShadow=o.receiveShadow=true;g.add(o)};
    box(2.6,.85,1.3,0,.42,0,M.marble);box(2.6,2.4,.35,0,1.2,.75,M.marble);box(.5,.3,.3,0,1.7,.45,M.marble);
    const w=new T.Mesh(new T.PlaneGeometry(2.2,.9),M.water);w.rotation.x=-Math.PI/2;w.position.set(0,.87,-.05);g.add(w);fg.add(g);nf++}
  if(nf){fg.name='streets.fountains';ctx.add(fg);meshes.push(fg)}
  ctx.reg.frontage={v:1,note:'streets 写：m/s 街每隔几个节点、每侧一条：x,z 街心点；nx,nz 朝外单位法线；kerb 路缘距街心；edge 人行道外沿/房门距街心（无房 = 半宽+1）；house 面向的那户 id 或 null。页面像素。',sides:front,fountains:nf,tris:per}}

export function dispose(ctx){for(const m of meshes){ctx.scene.remove(m);m.traverse(o=>{if(o.geometry)o.geometry.dispose()})}meshes=[]}
