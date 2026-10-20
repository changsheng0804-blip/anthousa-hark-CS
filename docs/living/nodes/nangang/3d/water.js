/* water（lookdev 第 2 轮第 1 波）：海面 + 港池水 + 岸线。——Hark（CS线）2026-10-20
   一块伸到地平线的海面平面（y=0），材质是 MeshPhong + onBeforeCompile（灯、阴影、雾、色调映射都走 three 自己的），注入：
   - 浪：一张代码里算出来的可平铺浪高图（整数波矢的正弦和，hsh 定相位），五档尺度（331 px 大涌 → 4 px 碎波）在世界 xz 上滚动，近处细浪横向拉长、浪尖挑亮，远处压平免得闪；
   - 倒影：半分辨率平面镜面反射（镜像相机 + y≥−0.5 全局裁剪面，tick 里渲），浪法线扰动采样；preview 档关掉，改用天色渐变；
   - 太阳：读 ctx.reg.sun（不加灯），Phong 高光是阴影里会灭的尖亮点，再加一条宽一点的太阳反光带；
   - 深浅：build 时按 core 蒙版同样的规则在 4 像素格上画岸，算「离岸距离场」（倒角距离）+ 港池标记，港池偏绿、外海偏蓝；
   - 岸边泡沫：距离场最近几像素一圈，用浪高图打碎。
   地面贴图上画：港池水色（被海面盖住，留着给地形下沉的过渡）、港池/海岸的湿痕（陆地一侧一道深色）、石堤地皮。
   不管：哪里是水（core 的蒙版）、石堤和栈桥的立体（buildings）、灯（sky）。 */
export const name='water';
export const checkShot=1;

const SH={step:4};          // 距离场一格 = 4 页面像素
let SEA=null,MAT=null,U=null,RT=null,MIRROR=null,SHORE=null,WAVE=null,FRAMES=0;

/* 可平铺浪高图：256²，高度 = Σ a·sin(2π(kx·u+ky·v)+φ)，整数波矢保证四边接得上；RGB 存法线 xz（0.5 为平），A 存高度（泡沫打碎用） */
function waveTex(ctx){const {THREE,hsh}=ctx,N=256,h=new Float32Array(N*N),gx=new Float32Array(N*N),gz=new Float32Array(N*N),W=[];
  for(let i=0;i<28;i++){let kx=Math.round((hsh(9100+i,1)*2-1)*9),ky=Math.round((hsh(9100+i,2)*2-1)*9);if(!kx&&!ky)kx=1+i%3;
    /* 主风向偏东南：把波矢往一个方向拉，浪才有走向 */ky=Math.round(ky*.6+Math.sign(ky||1)*1);const k=Math.hypot(kx,ky);W.push([kx,ky,1/Math.pow(k,1.15),hsh(9100+i,3)*6.2832])}
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){let s=0,dx=0,dz=0;const u=x/N,v=y/N;for(const [kx,ky,a,ph] of W){const q=6.2832*(kx*u+ky*v)+ph,c=Math.cos(q);s+=a*Math.sin(q);dx+=a*c*kx;dz+=a*c*ky}const k=y*N+x;h[k]=s;gx[k]=dx;gz[k]=dz}
  let hm=0,gm=0;for(let k=0;k<N*N;k++){hm=Math.max(hm,Math.abs(h[k]));gm=Math.max(gm,Math.abs(gx[k]),Math.abs(gz[k]))}
  const d=new Uint8Array(N*N*4);for(let k=0;k<N*N;k++){d[k*4]=128+127*gx[k]/gm;d[k*4+1]=128+127*gz[k]/gm;d[k*4+2]=255;d[k*4+3]=128+127*h[k]/hm}
  const t=new THREE.DataTexture(d,N,N,THREE.RGBAFormat);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.needsUpdate=true;return t}

const VERT_PARS='varying vec3 vWPos;\n';
const FRAG_PARS=`varying vec3 vWPos;
uniform sampler2D uWave,uShore,uRefl;uniform vec4 uShoreRect,uOff0,uOff1;uniform mat4 uTexMat;uniform float uReflOn,uWaveAmp,uReflK;uniform vec2 uReflPx;
uniform vec3 uDeep,uShallow,uFoam,uSkyLo,uSkyHi,uSunDir,uSunCol;
vec3 wN;vec2 wG;float wL,wD,wH,wS,wHb,e_a,wDist;vec3 wR;
`;
/* 法线：三档浪（大涌 / 中浪 / 碎波）叠起来，远处按距离压平（不然地平线一片噪点）；结果是世界空间 wN，再转视空间交给 Phong */
const FRAG_NORMAL=`{vec2 p=vWPos.xz;float dist=length(cameraPosition-vWPos);
  vec4 a=texture2D(uWave,p/331.+uOff0.xy),b=texture2D(uWave,p*vec2(1.,-1.)/97.+uOff0.zw),c=texture2D(uWave,p*vec2(1./64.,1./23.)+uOff1.xy),e=texture2D(uWave,p*vec2(-1./26.,1./8.7)+uOff1.zw),f=texture2D(uWave,p*vec2(1./11.,-1./4.1)+uOff1.wz*1.7);
  float slick=texture2D(uWave,p*vec2(1./2600.,1./800.)+.37).a*.7+texture2D(uWave,p.yx/1100.+.11).a*.3;wS=smoothstep(.42,.62,slick);
  vec2 q=mat2(.94,.34,-.34,.94)*p;wL=smoothstep(.6,.72,texture2D(uWave,q*vec2(1./3400.,1./520.)+vec2(.13,.71)).a)*smoothstep(.45,.6,texture2D(uWave,q*vec2(1./1500.,1./2100.)+.29).a)*smoothstep(500.,1300.,dist);
  wG=(a.xy-.5)*.45+(b.xy-.5)*.65+(c.xy-.5)*.85+((e.xy-.5)*.7+(f.xy-.5)*.5/(1.+dist/250.))/(1.+dist/500.);wH=a.a*.3+b.a*.3+c.a*.25+e.a*.15;e_a=mix(.5,c.a*.5+e.a*.5,1./(1.+dist/600.));wR=vec3(c.a,e.a,f.a);wDist=dist;
  wG*=uWaveAmp*mix(.45,1.35,wS)/(1.+dist/3500.);
  wN=normalize(vec3(wG.x,1.,wG.y));
  vec2 su=(p-uShoreRect.xy)/uShoreRect.zw;bool out_=su.x<0.||su.y<0.||su.x>1.||su.y>1.;vec4 st=texture2D(uShore,su);wD=out_?1.:st.r;wHb=out_?0.:st.g;
  normal=normalize((viewMatrix*vec4(wN,0.)).xyz);}
`;
/* 水体颜色：离岸近 = 港池绿，远 = 外海蓝（ART_BIBLE 调色板） */
const FRAG_COLOR=`{float sh=max(wHb*(1.-smoothstep(.0,.5,wD)*.55),(1.-smoothstep(0.,.12,wD))*.7);diffuseColor.rgb=mix(uDeep,uShallow,sh);}
`;
/* 倒影 + 太阳反光带 + 岸边泡沫，加在 Phong 结果上（之后 three 自己做色调映射、色彩空间、雾） */
const FRAG_OUT=`{vec3 V=normalize(cameraPosition-vWPos);float nv=max(dot(wN,V),0.);
  float F=.02+.98*pow(1.-nv,5.);
  vec3 R=reflect(-V,wN);vec3 sky=mix(uSkyLo,uSkyHi,smoothstep(0.,.5,R.y));
  vec3 refl=sky;
  if(uReflOn>.5){vec4 pr=uTexMat*vec4(vWPos.x,0.,vWPos.z,1.);vec2 ru=pr.xy/pr.w+wG*uReflPx;refl=texture2D(uRefl,clamp(ru,.001,.999)).rgb;}
  vec3 tint=diffuseColor.rgb/max(dot(diffuseColor.rgb,vec3(.3,.59,.11)),1e-3);refl*=mix(vec3(1.),tint,mix(.35,.6,smoothstep(600.,2500.,wDist)));
  outgoingLight=mix(outgoingLight,refl*uReflK,clamp(F*mix(.8,1.1,wS),0.,.62));
  outgoingLight*=.9+.22*e_a;
  /* 风带：外海上一条条细长的平水带，反天光更亮（只在远处） */
  outgoingLight=mix(outgoingLight,refl,wL*.32*(1.-wHb));
  /* 碎波挑亮：细浪的浪尖朝向天空，一道道亮线（近处才有，远处让 mipmap 平均掉） */
  float near=1./(1.+wDist/1000.);float rip=smoothstep(.54,.66,wR.y*.55+wR.z*.45)*near;
  outgoingLight=mix(outgoingLight,refl*1.22,rip*.62);outgoingLight*=1.-.3*smoothstep(.42,.28,wR.x*.6+wR.y*.4)*near;
  outgoingLight*=mix(.6,1.,smoothstep(.0,.008,wD));
  float sg=max(dot(R,uSunDir),0.);outgoingLight+=uSunCol*(pow(sg,60.)*.35+pow(sg,600.)*1.6)*smoothstep(-.05,.15,uSunDir.y);
  float fo=smoothstep(.001,.004,wD)*(1.-smoothstep(.006,.012,wD));float brk=smoothstep(.5,.62,wH+.2*(1.-wD/.02));fo*=brk;
  outgoingLight=mix(outgoingLight,uFoam*(.55+.45*max(uSunDir.y,0.)),fo*.4);}
`;

export function init(ctx){const {THREE,W,H,renderer}=ctx;
  WAVE=waveTex(ctx);
  /* 离岸距离场（build 里按当年蒙版重算，纹理常驻） */
  const sw=Math.ceil(W/SH.step)+1,shh=Math.ceil(H/SH.step)+1;SHORE=new THREE.DataTexture(new Uint8Array(sw*shh*2),sw,shh,THREE.RGFormat);
  SHORE.magFilter=THREE.LinearFilter;SHORE.minFilter=THREE.LinearFilter;SHORE.wrapS=SHORE.wrapT=THREE.ClampToEdgeWrapping;SHORE.flipY=false;SHORE.unpackAlignment=2;SH.w=sw;SH.h=shh;
  const hi=ctx.quality!=='preview';
  if(hi){RT=new THREE.WebGLRenderTarget(16,16,{type:THREE.HalfFloatType,minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,depthBuffer:true});MIRROR=new THREE.PerspectiveCamera()}
  const C=h=>new THREE.Color(h);
  U={uWave:{value:WAVE},uShore:{value:SHORE},uRefl:{value:RT?RT.texture:null},uShoreRect:{value:new THREE.Vector4(-SH.step/2,-SH.step/2,sw*SH.step,shh*SH.step)},
    uOff0:{value:new THREE.Vector4()},uOff1:{value:new THREE.Vector4()},uTexMat:{value:new THREE.Matrix4()},uReflOn:{value:hi?1:0},uWaveAmp:{value:.42},uReflK:{value:.85},uReflPx:{value:new THREE.Vector2(.05,.06)},
    uDeep:{value:C(0x1d607c)},uShallow:{value:C(0x3e6748)},uFoam:{value:C(0xe8e2d2)},uSkyLo:{value:C(0xd6d2c4)},uSkyHi:{value:C(0x8fb0c4)},
    uSunDir:{value:new THREE.Vector3(0,1,0)},uSunCol:{value:new THREE.Color(1,1,1)}};
  MAT=new THREE.MeshPhongMaterial({color:0x2f6a78,specular:0x6a6a60,shininess:220});
  MAT.onBeforeCompile=s=>{Object.assign(s.uniforms,U);
    s.vertexShader=VERT_PARS+s.vertexShader.replace('#include <project_vertex>','#include <project_vertex>\nvWPos=(modelMatrix*vec4(transformed,1.)).xyz;');
    s.fragmentShader=FRAG_PARS+s.fragmentShader.replace('#include <normal_fragment_maps>',FRAG_NORMAL).replace('#include <color_fragment>','#include <color_fragment>\n'+FRAG_COLOR).replace('#include <opaque_fragment>',FRAG_OUT+'#include <opaque_fragment>')};
  MAT.customProgramCacheKey=()=>'cs-water-1';
  SEA=new THREE.Mesh(new THREE.PlaneGeometry(20000,20000),MAT);SEA.rotation.x=-Math.PI/2;SEA.position.set(W/2,0,H/2);SEA.receiveShadow=true;
  ctx.add(SEA)}

/* 地面贴图：港池水色、湿痕、石堤地皮 */
export function paint(ctx,X){const {by,W,H}=ctx,path=g=>ctx.geom.pathRings(X,g),L=by.land[0];
  const harbors=by.water.filter(f=>f.k==='harbor'&&ctx.live(f));
  for(const f of harbors){X.beginPath();path(f.g);X.fillStyle='rgb(78,104,96)';X.fill()}
  /* 湿痕：陆地一侧沿水线一道深色（海岸只描真岸线，跳过贴着页边的那几段；港池边整圈描） */
  const coast=new Path2D(),onEdge=(a,b)=>{const e=1;return (a[0]<e&&b[0]<e)||(a[0]>W-e&&b[0]>W-e)||(a[1]<e&&b[1]<e)||(a[1]>H-e&&b[1]>H-e)};
  for(const P of L.g)for(const r of P)for(let i=0;i<r.length;i++){const a=r[i],b=r[(i+1)%r.length];if(onEdge(a,b))continue;coast.moveTo(a[0],a[1]);coast.lineTo(b[0],b[1])}
  X.save();X.beginPath();path(L.g);X.clip();X.lineJoin=X.lineCap='round';
  X.strokeStyle='rgba(150,138,112,.35)';X.lineWidth=6;X.stroke(coast);X.strokeStyle='rgba(92,86,70,.6)';X.lineWidth=2.5;X.stroke(coast);
  for(const f of harbors){X.beginPath();path(f.g);X.strokeStyle='rgba(150,138,112,.35)';X.lineWidth=6;X.stroke();X.beginPath();path(f.g);X.strokeStyle='rgba(88,84,68,.65)';X.lineWidth=2.5;X.stroke()}
  X.restore();
  for(const f of by.mole||[])if(ctx.live(f)){X.beginPath();path(f.g);X.fillStyle='rgb(196,184,160)';X.fill();X.strokeStyle='rgba(84,80,64,.8)';X.lineWidth=2.5;X.stroke()}}

/* 离岸距离场：按 core 蒙版同样的规则（陆地 + 当年石堤 = 岸，当年港池 = 水）在 4 像素格上画一遍，只拿来上色，不决定哪里是水；
   岸格为 0，其余两遍倒角距离（8 邻域），R 存 min(255, 距离像素/2)，G 存「在当年港池里」 */
function shoreField(ctx){const {w,h,step}=SH,N=w*h,D=new Float32Array(N),INF=1e9,by=ctx.by,path=(X,g)=>ctx.geom.pathRings(X,g);
  const cv=document.createElement('canvas');cv.width=w;cv.height=h;const X=cv.getContext('2d',{willReadFrequently:true});X.setTransform(1/step,0,0,1/step,.5,.5);
  X.fillStyle='#000';X.fillRect(-step,-step,(w+2)*step,(h+2)*step);
  X.beginPath();path(X,by.land[0].g);X.fillStyle='#f00';X.fill('evenodd');
  for(const f of by.mole||[])if(ctx.live(f)){X.beginPath();path(X,f.g);X.fillStyle='#f00';X.fill('evenodd')}
  X.globalCompositeOperation='lighter';
  for(const f of by.water)if(f.k==='harbor'&&ctx.live(f)){X.beginPath();path(X,f.g);X.fillStyle='#0f0';X.fill('evenodd')}
  X.globalCompositeOperation='source-over';
  const P=X.getImageData(0,0,w,h).data;
  for(let k=0;k<N;k++){const land=P[k*4]>127&&!(P[k*4+1]>200);D[k]=land?0:INF}
  const a=step,b=step*Math.SQRT2;
  for(let j=0;j<h;j++)for(let i=0;i<w;i++){const k=j*w+i;let v=D[k];if(!v)continue;if(i>0)v=Math.min(v,D[k-1]+a);if(j>0){v=Math.min(v,D[k-w]+a);if(i>0)v=Math.min(v,D[k-w-1]+b);if(i<w-1)v=Math.min(v,D[k-w+1]+b)}D[k]=v}
  for(let j=h-1;j>=0;j--)for(let i=w-1;i>=0;i--){const k=j*w+i;let v=D[k];if(!v)continue;if(i<w-1)v=Math.min(v,D[k+1]+a);if(j<h-1){v=Math.min(v,D[k+w]+a);if(i<w-1)v=Math.min(v,D[k+w+1]+b);if(i>0)v=Math.min(v,D[k+w-1]+b)}D[k]=v}
  const o=SHORE.image.data;for(let k=0;k<N;k++){o[k*2]=Math.min(255,D[k]/2);o[k*2+1]=P[k*4+1]}SHORE.needsUpdate=true}

export function build(ctx){shoreField(ctx)}
export function dispose(ctx){}

/* 每帧：浪滚动（t 固定时同图）、太阳方向、半分辨率镜面倒影 */
export function tick(ctx,t){if(!U)return;const {THREE,camera:cam,renderer:rnd,scene}=ctx;
  U.uOff0.value.set(t*.0021,t*.0013,-t*.0047,t*.0031);U.uOff1.value.set(t*.011,-t*.007,0,0);
  const sun=ctx.reg.sun;if(sun){const d=new THREE.Vector3().subVectors(sun.position,sun.target.position).normalize();U.uSunDir.value.copy(d);U.uSunCol.value.copy(sun.color).multiplyScalar(sun.intensity)}
  if(scene.fog&&scene.fog.color)U.uSkyLo.value.copy(scene.fog.color);
  if(!RT)return;
  if(cam.position.y<=0.5){U.uReflOn.value=0;return}U.uReflOn.value=1;
  const sz=rnd.getDrawingBufferSize(new THREE.Vector2()),rw=Math.max(16,sz.x>>1),rh=Math.max(16,sz.y>>1);if(RT.width!==rw||RT.height!==rh)RT.setSize(rw,rh);
  cam.updateMatrixWorld();const p=cam.position,dir=cam.getWorldDirection(new THREE.Vector3()),up=new THREE.Vector3(0,1,0).applyQuaternion(cam.quaternion);
  MIRROR.position.set(p.x,-p.y,p.z);MIRROR.up.set(up.x,-up.y,up.z);MIRROR.lookAt(p.x+dir.x,-(p.y+dir.y),p.z+dir.z);
  MIRROR.projectionMatrix.copy(cam.projectionMatrix);MIRROR.projectionMatrixInverse.copy(cam.projectionMatrixInverse);MIRROR.updateMatrixWorld();MIRROR.matrixWorldInverse.copy(MIRROR.matrixWorld).invert();
  U.uTexMat.value.set(.5,0,0,.5, 0,.5,0,.5, 0,0,.5,.5, 0,0,0,1).multiply(MIRROR.projectionMatrix).multiply(MIRROR.matrixWorldInverse);
  const prevRT=rnd.getRenderTarget(),prevClip=rnd.clippingPlanes,prevAuto=rnd.shadowMap.autoUpdate,prevXr=rnd.xr.enabled;
  SEA.visible=false;rnd.clippingPlanes=[CLIP||(CLIP=new THREE.Plane(new THREE.Vector3(0,1,0),.5))];if(FRAMES>0)rnd.shadowMap.autoUpdate=false;rnd.xr.enabled=false;
  rnd.setRenderTarget(RT);rnd.clear();rnd.render(scene,MIRROR);
  rnd.setRenderTarget(prevRT);rnd.clippingPlanes=prevClip;rnd.shadowMap.autoUpdate=prevAuto;rnd.xr.enabled=prevXr;SEA.visible=true;FRAMES++}
let CLIP=null;
