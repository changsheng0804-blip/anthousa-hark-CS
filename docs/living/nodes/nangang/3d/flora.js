/* flora（第 2 轮第 0 步从 3d.html 原样拆出）：树。柏 = 锥，橄榄 = 球（园子树不画），实例网格。归 props+flora 代理。
   树的位置/种类/年份/大小来自 WD.trees（[x, z, kind, y0, y1, size]），只能照用。 */
export const name='flora';
export const checkShot=3;
let cyp=null,oli=null;
export function init(ctx){const {THREE,WD}=ctx;
  cyp=new THREE.InstancedMesh(new THREE.ConeGeometry(1,1,7).translate(0,.5,0),new THREE.MeshLambertMaterial({color:0x3c5534}),WD.trees.length);
  oli=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),new THREE.MeshLambertMaterial({color:0x7c8c5e}),WD.trees.length);cyp.castShadow=oli.castShadow=true;ctx.add(cyp);ctx.add(oli)}
export function build(ctx){const {THREE,WD,year:Y}=ctx,M4=new THREE.Matrix4();
  let nc=0,no=0;for(const t of WD.trees){if(!(t[3]<=Y&&(t[4]==null||t[4]>Y))||t[2]==='garden')continue;const y=ctx.elevPx(t[0],t[1])+1.5,s=t[5];
    if(t[2]==='cypress'){M4.makeScale(s*.7,s*4.2,s*.7).setPosition(t[0],y,t[1]);cyp.setMatrixAt(nc++,M4)}else{M4.makeScale(s*1.2,s*1,s*1.2).setPosition(t[0],y+s*1.1,t[1]);oli.setMatrixAt(no++,M4)}}
  cyp.count=nc;oli.count=no;cyp.instanceMatrix.needsUpdate=oli.instanceMatrix.needsUpdate=true}
export function dispose(ctx){}
