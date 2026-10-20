/* water（第 2 轮第 0 步从 3d.html 原样拆出）：海面（一块伸到地平线的平面）+ 地面贴图上的港池水色、港池岸线、石堤地皮。
   石堤和栈桥的立体几何归 buildings。港池是不是「水」（地形下不下到海底）由 core 的水陆蒙版定，不在这里。 */
export const name='water';
export const checkShot=1;
export function init(ctx){const {THREE,W,H}=ctx;
  const sea=new THREE.Mesh(new THREE.PlaneGeometry(20000,20000),new THREE.MeshLambertMaterial({color:0x5b8590}));sea.rotation.x=-Math.PI/2;sea.position.set(W/2,0,H/2);sea.receiveShadow=true;ctx.add(sea)}
export function paint(ctx,X){const {by}=ctx,path=g=>ctx.geom.pathRings(X,g),L=by.land[0];
  for(const f of by.water)if(f.k==='harbor'&&ctx.live(f)){X.beginPath();path(f.g);X.fillStyle='rgb(86,126,136)';X.fill();X.save();X.beginPath();path(L.g);X.clip();X.beginPath();path(f.g);X.strokeStyle='rgb(176,166,146)';X.lineWidth=5;X.stroke();X.restore()}
  for(const f of by.mole||[])if(ctx.live(f)){X.beginPath();path(f.g);X.fillStyle='rgb(196,184,160)';X.fill()}}
export function build(ctx){}
export function dispose(ctx){}
