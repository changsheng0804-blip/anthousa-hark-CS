/* terrain（第 2 轮第 0 步从 3d.html 原样拆出）：地面贴图的底层（海色底、陆地、沙岸、等高带）+ 高程网格。
   网格披的是 core 的地面贴图 ctx.groundTex（water、streets 也往上画）。高度用 ctx.ground(x,z)（core 的水陆蒙版 + 高程）。
   第 2 轮（——Hark（CS线）2026-10-20）：区外陆地 + 远岸环在 ./terrain/outer.js（区内这部分一个像素没改）。 */
import * as outer from './terrain/outer.js';
export const name='terrain';
export const checkShot=3;
const SEG=4;let tg=null,nx=0,nz=0;
export function paint(ctx,X){const {W,H,WD,by}=ctx,path=g=>ctx.geom.pathRings(X,g);
  X.fillStyle='rgb(86,126,136)';X.fillRect(0,0,W,H);
  const L=by.land[0];X.save();X.beginPath();path(L.g);X.lineJoin='round';X.strokeStyle='rgb(216,200,160)';X.lineWidth=14;X.stroke();X.fillStyle='rgb(206,194,160)';X.fill();X.clip();
  WD.bands.forEach((b,i)=>{X.beginPath();path(b.g);X.fillStyle=`rgba(${110+i*2},${104+i*2},${60},${.05+.01*i})`;X.fill();X.strokeStyle='rgba(120,96,60,.12)';X.lineWidth=.6;X.stroke()});
  X.restore()}
export function init(ctx){const {THREE,W,H}=ctx;nx=Math.ceil(W/SEG)+1;nz=Math.ceil(H/SEG)+1;tg=new THREE.BufferGeometry();
  const pos=new Float32Array(nx*nz*3),uv=new Float32Array(nx*nz*2),idx=[];for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){const k=j*nx+i;pos[k*3]=Math.min(W,i*SEG);pos[k*3+2]=Math.min(H,j*SEG);uv[k*2]=pos[k*3]/W;uv[k*2+1]=1-pos[k*3+2]/H}
  for(let j=0;j<nz-1;j++)for(let i=0;i<nx-1;i++){const a=j*nx+i,b=a+1,c=a+nx,d=c+1;idx.push(a,c,b,b,c,d)}tg.setAttribute('position',new THREE.BufferAttribute(pos,3));tg.setAttribute('uv',new THREE.BufferAttribute(uv,2));tg.setIndex(idx);
  const terr=new THREE.Mesh(tg,new THREE.MeshLambertMaterial({map:ctx.groundTex}));terr.receiveShadow=true;ctx.add(terr);
  outer.init(ctx)}
export function build(ctx){const p=tg.attributes.position.array;for(let k=0;k<nx*nz;k++)p[k*3+1]=ctx.ground(p[k*3],p[k*3+2]);tg.attributes.position.needsUpdate=true;tg.computeVertexNormals();
  outer.build(ctx)}
export function tick(ctx,t){outer.tick(ctx,t)}
export function dispose(ctx){}
