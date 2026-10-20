/* buildings（第 2 轮第 0 步从 3d.html 原样拆出）：5163 户房子（墙 + 四坡/山墙/平顶，合成一个顶点色网格）、
   地标部件（广场、粮仓、宁芙殿、蓄水池、孤寡院）、栈桥、石堤。
   房子的位置/占地/高度/年份来自底账（WD house: p、ht、fn、id、y0/y1），只能照用。可再分到 3d/arch/。 */
export const name='buildings';
export const checkShot=4;
const STY={market:[[236,222,192],[198,104,58]],shops:[[234,220,190],[192,100,60]],fine:[[244,238,226],[200,112,66]],workshop:[[196,162,116],[142,86,58]],water:[[216,222,220],[176,98,66]],garrison:[[198,196,188],[150,92,72]],homes:[[228,212,182],[186,94,60]],garden:[[206,182,140],[166,100,66]]};
const FLAT={workshop:.45,garden:.5,water:.12,garrison:.15,homes:.12,market:.05,shops:.06};
const MARBLE=[238,232,218],STONE=[222,212,190],ROOF=[186,98,62];
let T=null,HM=null,LMG=null,VMAT=null,colGeo=null,domeGeo=null,mats=null,quadAxes=null,RQ=null,hsh=null;

function pushBuilding(B,P,base,h,wall,roof,kind,pitch=.38){/* B: {pos,col}; P 4 角（任意顺序都按轴重建） */
  const r=quadAxes(P),c=(u,v)=>[r.cx+r.ax*u-r.az*v,r.cz+r.az*u+r.ax*v];
  const k=[c(-r.hu,-r.hv),c(r.hu,-r.hv),c(r.hu,r.hv),c(-r.hu,r.hv)],y0=base-3,y1=base+h;
  const tri=(a,b,cc,col)=>{B.pos.push(...a,...b,...cc);for(let i=0;i<3;i++)B.col.push(col[0]/255,col[1]/255,col[2]/255)};
  const quad=(a,b,cc,d,col)=>{tri(a,b,cc,col);tri(a,cc,d,col)};
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4];quad([a[0],y0,a[1]],[b[0],y0,b[1]],[b[0],y1,b[1]],[a[0],y1,a[1]],wall)}
  if(kind==='flat'){quad([k[0][0],y1,k[0][1]],[k[3][0],y1,k[3][1]],[k[2][0],y1,k[2][1]],[k[1][0],y1,k[1][1]],wall.map(v=>v*.92));return}
  const rh=r.hv*2*pitch,rr=Math.max(0,r.hu-r.hv*(kind==='gable'?0:1)),A=c(-rr,0),Bb=c(rr,0),ya=y1+rh;const o=1.06;/* 出檐 */
  const kk=k.map(p=>[r.cx+(p[0]-r.cx)*o,r.cz+(p[1]-r.cz)*o]);
  quad([kk[0][0],y1,kk[0][1]],[A[0],ya,A[1]],[Bb[0],ya,Bb[1]],[kk[1][0],y1,kk[1][1]],roof);
  quad([kk[2][0],y1,kk[2][1]],[Bb[0],ya,Bb[1]],[A[0],ya,A[1]],[kk[3][0],y1,kk[3][1]],roof);
  if(kind==='gable'){tri([k[1][0],y1,k[1][1]],[Bb[0],ya,Bb[1]],[k[2][0],y1,k[2][1]],wall);tri([k[3][0],y1,k[3][1]],[A[0],ya,A[1]],[k[0][0],y1,k[0][1]],wall)}
  else{tri([kk[1][0],y1,kk[1][1]],[Bb[0],ya,Bb[1]],[kk[2][0],y1,kk[2][1]],roof);tri([kk[3][0],y1,kk[3][1]],[A[0],ya,A[1]],[kk[0][0],y1,kk[0][1]],roof)}}
function meshOf(B,mat){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(B.pos,3));g.setAttribute('color',new T.Float32BufferAttribute(B.col,3));g.computeVertexNormals();const m=new T.Mesh(g,mat);m.castShadow=m.receiveShadow=true;return m}
function cyl(x,y,z,r,h,m){const o=new T.Mesh(colGeo,m);o.scale.set(r,h,r);o.position.set(x,y+h/2,z);o.castShadow=true;LMG.add(o)}
function dome(x,y,z,r,m,sy=1){const o=new T.Mesh(domeGeo,m);o.scale.set(r,r*sy,r);o.position.set(x,y,z);o.castShadow=true;LMG.add(o)}

/* ---- 地标部件（代码，不是图） ---- */
const PARTS={
 forum(B,f,r,b){const d=10,h=8;for(const s of [-1,1]){pushBuilding(B,RQ(r,-r.hu,s*r.hv,r.hu,s*(r.hv-d)),b,h,MARBLE,ROOF,'hip',.3);pushBuilding(B,RQ(r,s*r.hu,-r.hv+d,s*(r.hu-d),r.hv-d),b,h,MARBLE,ROOF,'hip',.3)}
  for(let u=-r.hu+d+3;u<r.hu-d;u+=6)for(const s of [-1,1]){const x=r.cx+r.ax*u-r.az*s*(r.hv-d-2),z=r.cz+r.az*u+r.ax*s*(r.hv-d-2);cyl(x,b,z,.9,h,mats.marble)}
  cyl(r.cx,b,r.cz,2.4,34,mats.marble);dome(r.cx,b+34,r.cz,2.6,mats.gold,1.4)},
 granary(B,f,r,b){const n=Math.max(2,Math.round(r.hv*2/16)),bw=(r.hv*2-4)/n;for(let i=0;i<n;i++){const v0=-r.hv+2+i*bw;pushBuilding(B,RQ(r,-r.hu+3,v0,r.hu-3,v0+bw-4),b,7+2*hsh(f.seed,i),STONE,[176,92,58],'gable',.42)}},
 nymphaeum(B,f,r,b){const R_=Math.min(r.hu,r.hv*1.6)*.85,a0=Math.atan2(r.az,r.ax);for(let k=0;k<=14;k++){const t=Math.PI+k/14*Math.PI+a0,x=r.cx+Math.cos(t)*R_,z=r.cz+Math.sin(t)*R_*.6;cyl(x,b,z,1.6,14,mats.marble)}
  const w=new T.Mesh(new T.CircleGeometry(R_*.75,32,0,Math.PI),mats.water);w.rotation.x=-Math.PI/2;w.rotation.z=-a0;w.scale.y=.6;w.position.set(r.cx,b+.6,r.cz);LMG.add(w)},
 cistern(B,f,r,b){for(let u=-r.hu+6;u<r.hu-3;u+=9)for(let v=-r.hv+6;v<r.hv-3;v+=9)dome(r.cx+r.ax*u-r.az*v,b,r.cz+r.az*u+r.ax*v,3.8,mats.dome,.6);pushBuilding(B,RQ(r,r.hu-12,r.hv-10,r.hu-2,r.hv-2),b,6,STONE,ROOF,'hip')},
 xenon(B,f,r,b){const d=9;for(const s of [-1,1]){pushBuilding(B,RQ(r,-r.hu,s*r.hv,r.hu,s*(r.hv-d)),b,9,STONE,ROOF,'hip');pushBuilding(B,RQ(r,s*r.hu,-r.hv+d,s*(r.hu-d),r.hv-d),b,9,STONE,ROOF,'hip')}
  pushBuilding(B,RQ(r,-8,-6,8,6),b,10,MARBLE,MARBLE,'flat');dome(r.cx,b+10,r.cz,5.5,mats.dome)}};
PARTS.monument=PARTS.nymphaeum;PARTS.monastery=PARTS.xenon;

export function init(ctx){T=ctx.THREE;({quadAxes,RQ}=ctx.geom);hsh=ctx.hsh;
  LMG=new T.Group();ctx.add(LMG);
  VMAT=new T.MeshLambertMaterial({vertexColors:true,side:T.DoubleSide});
  colGeo=new T.CylinderGeometry(.9,1,1,8);domeGeo=new T.SphereGeometry(1,16,8,0,Math.PI*2,0,Math.PI/2);
  mats={marble:new T.MeshLambertMaterial({color:0xf2eee4}),water:new T.MeshLambertMaterial({color:0x6fa2aa}),dome:new T.MeshLambertMaterial({color:0x9a8a74}),gold:new T.MeshLambertMaterial({color:0xc8a046}),mole:new T.MeshLambertMaterial({color:0xc4b8a0})}}

export function build(ctx){const {by,elevPx}=ctx,live=ctx.live;
  const B={pos:[],col:[]};
  for(const f of by.house){if(!live(f))continue;const p=f.p,P=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];const cx=(p[0]+p[2]+p[4]+p[6])/4,cz=(p[1]+p[3]+p[5]+p[7])/4;
    const s=STY[f.fn]||STY.homes,k=.9+.2*hsh(f.id,14),roof=s[1].map(v=>v*k),wall=s[0].map(v=>v*(.95+.08*hsh(f.id,3)));const ins=P.map(q=>[cx+(q[0]-cx)*.92,cz+(q[1]-cz)*.92]);
    pushBuilding(B,ins,elevPx(cx,cz)+1.5,Math.max(3,(f.ht||5)*1.15),wall,roof,hsh(f.id,17)<(FLAT[f.fn]||.12)?'flat':'hip')}
  for(const f of by.landmark||[])if(live(f)){const r=ctx.geom.rectOf(f.g);(PARTS[f.k]||PARTS.granary)(B,f,r,elevPx(r.cx,r.cz)+1.6)}
  for(const f of by.pier||[])if(live(f)){const [a,b]=f.g,dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),nx=-dz/L*f.w/2,nz=dx/L*f.w/2;
    pushBuilding(B,[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]],-1,2.6,[120,88,56],[150,112,74],'flat')}
  /* 防波堤：底账港池落海的那圈，挤出成石堤 */
  for(const f of by.mole||[])if(live(f))for(const P of f.g){const sh=new T.Shape(P[0].map(p=>new T.Vector2(p[0],p[1])));for(const r of P.slice(1))sh.holes.push(new T.Path(r.map(p=>new T.Vector2(p[0],p[1]))));
    const g=new T.ExtrudeGeometry(sh,{depth:9,bevelEnabled:false});g.rotateX(Math.PI/2);g.translate(0,3,0);const m=new T.Mesh(g,mats.mole);m.castShadow=m.receiveShadow=true;LMG.add(m)}
  HM=ctx.add(meshOf(B,VMAT))}

export function dispose(ctx){
  if(HM){ctx.scene.remove(HM);HM.geometry.dispose();HM=null}
  for(const o of LMG.children)if(o.geometry&&o.geometry!==colGeo&&o.geometry!==domeGeo)o.geometry.dispose();
  LMG.clear()}
