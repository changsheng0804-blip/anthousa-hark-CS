/* sky-atmosphere（第 2 轮第 0 步从 3d.html 原样拆出）：天空底色、雾、天光、太阳和阴影。
   可以动：太阳方向/颜色、天光、天空穹、雾、阴影参数、ctx.renderer 的色调映射/曝光/输出色彩。不准动任何物体的材质。 */
export const name='sky';
export const checkShot=1;
export function init(ctx){const {THREE,scene,W,H}=ctx;
  scene.background=new THREE.Color(0xbfd0d4);scene.fog=new THREE.Fog(0xbfd0d4,1400,3800);
  ctx.add(new THREE.HemisphereLight(0xf4ecd8,0x6f6450,1.25));
  const sun=new THREE.DirectionalLight(0xfff1d6,2.1);sun.position.set(W/2-900,1100,H/2-1300);sun.target.position.set(W/2,0,H/2);ctx.add(sun);ctx.add(sun.target);
  sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-1500,right:1500,top:1500,bottom:-1500,near:100,far:4000});sun.shadow.bias=-0.0006;sun.shadow.normalBias=.6;
  SUN=sun}
let SUN=null;
/* reg.sun：别的模块要太阳方向（如水面高光）就读它，不要自己再建灯 */
export function build(ctx){ctx.reg.sun=SUN}
export function dispose(ctx){}
