/* flora（lookdev 第 2 轮，props+flora 代理）：树、灌木、葡萄架。全部实例网格 + 顶点色。
   树的位置/种类/年份/大小来自 WD.trees（[x, z, kind, y0, y1, size]），只能照用：
   - 柏 cypress：细干 + 两节锥，深绿（#2c3a24），高 ≈ 4.2×size（和第 1 轮一样高）
   - 橄榄 olive：歪干 + 几团灰绿树冠（#73796f），冠宽 ≈ 2.4×size
   - 园子 garden（第 1 轮不画）：矮干宽冠的果树（无花果 / 石榴，一半挂果）；约三成旁边搭一架葡萄
   - 灌木：橄榄和园子树脚下各 0–2 丛（月桂 / 迷迭香），只落在陆上、不进房子
   灌木和葡萄架是装饰，不是底账的树：位置由树的位置 + ctx.hsh 推出来，不新增「树」。 */
import * as K from './props/kit.js';
import {makeSite} from './props/site.js';
export const name='flora';
export const checkShot=3;
let T=null,MAT=null,G=null,LIVE=[];
export function init(ctx){T=ctx.THREE;K.setThree(T);MAT=new T.MeshLambertMaterial({vertexColors:true});
  G={cypress:[K.cypressGeo(0)],olive:[K.oliveGeo(0),K.oliveGeo(1)],garden:[K.gardenGeo(0),K.gardenGeo(1)],shrub:[K.shrubGeo(0),K.shrubGeo(1),K.shrubGeo(2)],pergola:[K.pergolaGeo()]}}
const mtx=(x,y,z,ry,sx,sy,sz)=>new T.Matrix4().compose(new T.Vector3(x,y,z),new T.Quaternion().setFromEuler(new T.Euler(0,ry,0)),new T.Vector3(sx,sy,sz));
export function build(ctx){const {WD,year:Y,hsh}=ctx,site=ctx.reg.propsSite||makeSite(ctx);
  ctx.reg.treeY=ctx.groundMesh;/* r3：树、灌木、葡萄架落在 terrain 网格上（ctx.groundMesh，同画出来的地面）；ground_check 读它 */
  const B={};for(const k in G)B[k]=G[k].map(()=>({m:[],c:[]}));
  const tint=(k,a)=>new T.Color(1,1,1).multiplyScalar(1-a+2*a*k);
  const okSpot=(x,z,m)=>site.isLand(x,z)&&!site.inHouse(x,z,m)&&!site.inLandmark(x,z,m);
  WD.trees.forEach((t,i)=>{if(!(t[3]<=Y&&(t[4]==null||t[4]>Y)))return;const [x,z,kind]=t,s=t[5],y=ctx.groundMesh(x,z),id=((x+(ctx.ox||0))*7+(z+(ctx.oz||0))*13)|0/* ctx.ox/oz：全城页近景窗口的原点（南港 = 0），树的样子按全城坐标定，窗口挪了不变 */,ry=hsh(id,1)*Math.PI*2,v=G[kind]?(hsh(id,2)*G[kind].length)|0:0;
    if(kind==='cypress'){const h=s*3.33*(.9+.2*hsh(id,3));B.cypress[0].m.push(mtx(x,y,z,ry,s*1.4,h,s*1.4));B.cypress[0].c.push(tint(hsh(id,4),.1))}
    else if(kind==='olive'){const k=s*.88*(.9+.2*hsh(id,3));B.olive[v].m.push(mtx(x,y,z,ry,k,k*(.9+.15*hsh(id,5)),k));B.olive[v].c.push(tint(hsh(id,4),.08))}
    else if(kind==='garden'){const k=s*.7*(.9+.2*hsh(id,3));B.garden[v].m.push(mtx(x,y,z,ry,k,k,k));B.garden[v].c.push(tint(hsh(id,4),.1));
      if(hsh(id,6)<.3){const a=hsh(id,7)*Math.PI*2,d=s*.8+3.2,px=x+Math.cos(a)*d,pz=z+Math.sin(a)*d;if(okSpot(px,pz,2.6)){B.pergola[0].m.push(mtx(px,ctx.groundMesh(px,pz),pz,a,1,1,1));B.pergola[0].c.push(tint(hsh(id,8),.08))}}}
    if(kind!=='cypress'){const n=(hsh(id,9)*3)|0;for(let j=0;j<n;j++){const a=hsh(id,20+j)*Math.PI*2,d=s*(.9+.9*hsh(id,30+j)),px=x+Math.cos(a)*d,pz=z+Math.sin(a)*d;if(!okSpot(px,pz,.6))continue;
      const w=(hsh(id,40+j)*3)|0,k=.8+.9*hsh(id,50+j);B.shrub[w].m.push(mtx(px,ctx.groundMesh(px,pz),pz,a*3,k,k,k));B.shrub[w].c.push(tint(hsh(id,60+j),.1))}}});
  LIVE=[];const stat={};
  for(const k in B)B[k].forEach((b,vi)=>{stat[k]=(stat[k]||0)+b.m.length;if(!b.m.length)return;const im=new T.InstancedMesh(G[k][vi],MAT,b.m.length);b.m.forEach((m,i)=>{im.setMatrixAt(i,m);im.setColorAt(i,b.c[i])});
    im.instanceMatrix.needsUpdate=true;im.instanceColor.needsUpdate=true;im.castShadow=true;im.receiveShadow=k==='shrub';ctx.add(im);LIVE.push(im)});
  window.__floraCheck=stat}
export function dispose(ctx){for(const im of LIVE){ctx.scene.remove(im);im.dispose()}LIVE=[]}
