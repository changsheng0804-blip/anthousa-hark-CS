/* sky-atmosphere（lookdev 第 2 轮第 1 波）：低太阳、天空穹、空气透视雾、天光、阴影、色调映射和调色。
   可以动：太阳方向/颜色、天光、天空穹、雾、阴影参数、ctx.renderer 的色调映射/曝光/输出色彩。不准动任何物体的材质。
   要点：
   - 一个世界只有一个太阳，不按机位换：方位 300°（西北偏西）、高 14°。机位 1（向北）、4（向北偏东）从左边来；
     机位 2（顺主街向东）从左后方来——左侧铺面背光、右侧受光；机位 3（向南俯看）从右后方来，长投影往左前方铺。
   - 调色写成 three 的 CustomToneMapping（替换 ShaderChunk 里那一个函数），在每个材质的片元里做，不加后期 pass：
     曝光 → 暖白平衡 → ACES 曲线 → 显示空间分段 S 形反差（支点上下各一个强度）+ 暗/亮部分离色调 + 加饱和 + 黑位。
   - 天空穹：跟着相机走的大球（半径 8000 < 相机 far 9000），天顶色 + 地平线霾 + 太阳晕 + 薄云 + 太阳盘。
   - 雾（空气透视）：替换 three 的 fog 片段，霾色按视线方向取（skyHaze，和穹的地平线同一个函数），
     太阳一侧暖亮、背光一侧冷暗；并且先走同一条色调映射/输出，再混——所以远海、远岸和天在任何方向都无缝。
     注意：这改的是全局 ShaderChunk，所有 fog:true 的材质都会用上（这正是要的）。
   - 阴影相机按太阳方向收窄：光空间横向 ±1800 像素；纵向 ±560（低太阳下地面上 ≈ ±2300 像素），贴图 4096×2048。
   - 别的模块：ctx.reg.sun（DirectionalLight）、ctx.reg.sky（sunDir、地平线/天顶/金色、fog）在 build 里写。
   - ?skyp={"exp":1.2,...} 只用于调参（覆盖下面 P 的键），不带时完全按默认。 */
export const name='sky';
export const checkShot=1;

const P={
  az:300, el:14,                 /* 太阳方位（度，北=0 顺时针）和高度角：夏天傍晚，西北偏西 */
  sun:0xffe6cc, sunI:8.3,        /* 太阳色（暖白）、强度：太阳偏中性，暖色主要来自白平衡和天光，屋顶（机位 3）才不会过暖 */
  hemiSky:0xbcb8b0, hemiGnd:0x5a3c22, hemiI:1.1,   /* 天光：朝上的面吃冷灰天光（水面仍是青色），竖墙一半吃暖褐地面反光 → 阴影里的墙是暖褐 */
  zenith:0x9294a0, horizon:0xf2d2a2, glow:0xffc27a, /* 天空：天顶淡灰蓝（参考图的天顶不是饱和蓝）、地平线暖白、太阳一侧金 */
  hazeLo:0.52, hazeHi:1.6, hazePow:3,  /* 地平线霾：背光一侧 / 太阳一侧的亮度倍数，及向太阳收拢的快慢 */
  hazeCool:0xc9d2da, hazeCoolK:0.85,  /* 背光一侧的霾偏冷（远海发青灰），太阳一侧保持暖 */
  skyGam:5.0,                   /* 地平线→天顶的过渡速度（越大蓝得越快） */
  fogNear:900, fogFar:9000,     /* 空气透视：900 像素外开始起霾，到相机 far(9000) 全进霾；tick 里跟着 camera.far 走 */
  exp:0.70,                      /* 曝光 */
  wb:[1.05,1.0,0.92],            /* 白平衡（线性乘子；天空穹和雾不吃它） */
  con:0.30,                      /* 支点以下的反差（暗部往下压） */
  pivot:0.42,                    /* S 形的支点（显示空间） */
  hiCon:0.95,                    /* 支点以上的反差（亮部往上推） */
  sat:1.2,                       /* 饱和 */
  shTint:[1.04,1.0,0.94],        /* 暗部色调（参考图的阴影是暖褐，不是蓝黑） */
  hiTint:[1.02,1.0,0.94],        /* 亮部色调（暖） */
  black:0.0                      /* 黑位下压 */
};

let SUN=null,DOME=null;
const v3=a=>'vec3('+a.map(x=>(+x).toFixed(4)).join(',')+')';

function installGrade(THREE){
  const SC=THREE.ShaderChunk,key='tonemapping_pars_fragment';
  const custom=`vec3 CustomToneMapping( vec3 color ) {
	color *= toneMappingExposure * ${v3(P.wb)};
	const mat3 ACESIn = mat3( vec3( 0.59719, 0.07600, 0.02840 ), vec3( 0.35458, 0.90834, 0.13383 ), vec3( 0.04823, 0.01566, 0.83777 ) );
	const mat3 ACESOut = mat3( vec3( 1.60475, -0.10208, -0.00327 ), vec3( -0.53108, 1.10813, -0.07276 ), vec3( -0.07367, -0.00605, 1.07602 ) );
	color = ACESIn * ( color / 0.6 );
	color = RRTAndODTFit( color );
	color = saturate( ACESOut * color );
	vec3 d = pow( color, vec3( 1.0 / 2.2 ) );
	float l = dot( d, vec3( 0.2126, 0.7152, 0.0722 ) );
	float pv = ${(+P.pivot).toFixed(4)};
	float x = l < pv ? pv * pow( l / pv, 1.0 + ${(+P.con).toFixed(4)} ) : 1.0 - ( 1.0 - pv ) * pow( ( 1.0 - l ) / ( 1.0 - pv ), 1.0 + ${(+P.hiCon).toFixed(4)} );
	d *= x / max( l, 1e-4 );
	float w = smoothstep( 0.0, 0.75, x );
	d *= mix( ${v3(P.shTint)}, ${v3(P.hiTint)}, w );
	float l2 = dot( d, vec3( 0.2126, 0.7152, 0.0722 ) );
	d = mix( vec3( l2 ), d, ${(+P.sat).toFixed(4)} );
	d = max( d - ${(+P.black).toFixed(4)}, 0.0 ) / ( 1.0 - ${(+P.black).toFixed(4)} );
	return pow( saturate( d ), vec3( 2.2 ) );
}`;
  SC[key]=SC[key].replace(/vec3 CustomToneMapping\( vec3 color \) \{[^}]*\}/,custom);
}

function sunDir(THREE){const a=P.az*Math.PI/180,e=P.el*Math.PI/180;
  /* x=东，z=南（页面 y 向下），y=上 */return new THREE.Vector3(Math.sin(a)*Math.cos(e),Math.sin(e),-Math.cos(a)*Math.cos(e)).normalize()}

/* 地平线霾色（线性、未除白平衡）：按水平方向和太阳的夹角变亮——太阳那边亮而暖，背光那边暗一些。
   天空穹的地平线和雾（空气透视）共用这一个函数，所以远处的海/地和天在任何方向都无缝。太阳固定，方向写成常量。 */
function hazeGLSL(THREE,dir){const c=h=>{const k=new THREE.Color(h);return v3([k.r,k.g,k.b])};
  const hc=new THREE.Color(P.horizon).lerp(new THREE.Color(P.glow),0.10);
  const sh=new THREE.Vector2(dir.x,dir.z).normalize();
  return `vec3 skyHaze( vec3 d ) {
	vec2 h = d.xz; float hl = length( h ); h = hl > 1e-4 ? h / hl : vec2( 0.0 );
	float hb = 0.5 + 0.5 * dot( h, vec2( ${sh.x.toFixed(5)}, ${sh.y.toFixed(5)} ) );
	float k = mix( ${(+P.hazeLo).toFixed(4)}, ${(+P.hazeHi).toFixed(4)}, pow( hb, ${(+P.hazePow).toFixed(3)} ) );
	vec3 hcol = mix( ${v3([hc.r,hc.g,hc.b])}, ${c(P.hazeCool)}, ${(+P.hazeCoolK).toFixed(4)} * ( 1.0 - hb ) * ( 1.0 - hb ) );
	return hcol * k + ${c(P.glow)} * ( 0.22 * pow( hb, 4.0 ) );
}`}

/* skyHaze 的 JS 版（hb = 0 背光 … 1 正对太阳），线性色 */
function hazeJS(THREE,hb){const hc=new THREE.Color(P.horizon).lerp(new THREE.Color(P.glow),0.10);
  const col=hc.clone().lerp(new THREE.Color(P.hazeCool),P.hazeCoolK*(1-hb)*(1-hb)).multiplyScalar(P.hazeLo+(P.hazeHi-P.hazeLo)*Math.pow(hb,P.hazePow));
  return col.add(new THREE.Color(P.glow).multiplyScalar(0.22*Math.pow(hb,4)))}

function installFog(THREE,dir){const SC=THREE.ShaderChunk,WB=v3(P.wb);
  SC.fog_pars_vertex='#ifdef USE_FOG\n\tvarying float vFogDepth;\n\tvarying vec3 vFogWDir;\n#endif';
  SC.fog_vertex='#ifdef USE_FOG\n\tvFogDepth = - mvPosition.z;\n\tvFogWDir = transpose( mat3( viewMatrix ) ) * mvPosition.xyz;\n#endif';
  SC.fog_pars_fragment=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	varying vec3 vFogWDir;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
	${hazeGLSL(THREE,dir)}
#endif`;
  SC.fog_fragment=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	/* three 在色调映射和输出色彩之后才混雾，所以霾色也要走同一条路，才和天空穹（同样先调色再输出）对得上 */
	vec3 fogC = skyHaze( normalize( vFogWDir ) ) / ${WB};
	#ifdef TONE_MAPPING
		fogC = toneMapping( fogC );
	#endif
	fogC = linearToOutputTexel( vec4( fogC, 1.0 ) ).rgb;
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogC, fogFactor );
#endif`}

function makeDome(THREE,dir){
  const lin=h=>new THREE.Color(h);  /* THREE.Color 读 hex 时已转到线性工作空间 */
  const mat=new THREE.ShaderMaterial({
    uniforms:{uSun:{value:dir.clone()},uZen:{value:lin(P.zenith)},uGlow:{value:lin(P.glow)},uSunC:{value:lin(P.sun)},uGam:{value:P.skyGam},uWB:{value:new THREE.Vector3(...P.wb)}},
    vertexShader:`varying vec3 vDir;void main(){vDir=normalize((modelMatrix*vec4(position,0.0)).xyz);vec4 p=projectionMatrix*viewMatrix*modelMatrix*vec4(position,1.0);gl_Position=p.xyww;}`,
    fragmentShader:`uniform vec3 uSun,uZen,uGlow,uSunC;uniform float uGam;uniform vec3 uWB;varying vec3 vDir;
      ${hazeGLSL(THREE,dir)}
      float h21(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}
      float vn(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(h21(i),h21(i+vec2(1,0)),f.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x),f.y);}
      float fbm(vec2 p){float s=0.0,a=.5;for(int i=0;i<4;i++){s+=a*vn(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return s;}
      void main(){vec3 d=normalize(vDir);float y=d.y;
        float t=clamp(y,0.0,1.0);
        vec3 hc=skyHaze(d);
        vec3 c=mix(hc,uZen,1.0-exp(-t*uGam));
        float cs=dot(d,uSun);float g=max(cs,0.0);
        float hz=exp(-t*9.0);
        c=mix(c,uGlow*1.3,(0.6*pow(g,8.0)+0.3*pow(g,3.0))*(0.3+0.7*hz)*step(0.0,y));
        /* 薄云：投到高空平面上的 fbm */
        if(y>0.01){vec2 q=d.xz/(y+0.06)*0.9;float n=fbm(q*vec2(1.1,1.8)+vec2(3.1,0.0));float cl=smoothstep(0.55,0.85,n)*smoothstep(0.01,0.12,y)*(1.0-smoothstep(0.35,0.8,y));
          vec3 cc=mix(hc*1.2,uGlow*1.6,0.5*pow(g,2.0)+0.2);c=mix(c,cc,cl*0.7);}
        /* 太阳盘 + 晕 */
        c+=uSunC*(smoothstep(0.99955,0.99975,cs)*30.0+pow(g,600.0)*4.0)*step(0.0,y);
        gl_FragColor=vec4(c/uWB,1.0);  /* 穹不吃白平衡：调色里的暖白平衡只给受光物体，天色按 P 里写的出 */
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    side:THREE.BackSide,depthWrite:false,depthTest:true,fog:false});
  const m=new THREE.Mesh(new THREE.SphereGeometry(8000,48,24),mat);m.frustumCulled=false;m.renderOrder=-1000;
  m.onBeforeRender=(r,s,cam)=>{m.position.copy(cam.position);m.updateMatrixWorld()};
  return m}

export function init(ctx){const {THREE,scene,W,H,renderer}=ctx;
  try{const o=ctx.QS&&ctx.QS.get('skyp');if(o)Object.assign(P,JSON.parse(o))}catch(e){console.warn('skyp',e)}
  installGrade(THREE);
  const dir0=sunDir(THREE);installFog(THREE,dir0);
  renderer.toneMapping=THREE.CustomToneMapping;renderer.toneMappingExposure=P.exp;
  const dir=sunDir(THREE);
  /* 雾色 = 地平线色（再带一点太阳暖光），这样远处融进天空穹的地平线 */
  /* fog.color 本身不再被雾用（霾色按方向在着色器里算），但别的模块（如 water 的倒影低空色）会读它：
     给它一个「非太阳一侧」的地平线霾色（hb=0.3，和 skyHaze 同一公式），免得倒影整片都是太阳那边的金色 */
  const fogC=hazeJS(THREE,0.3);fogC.r/=P.wb[0];fogC.g/=P.wb[1];fogC.b/=P.wb[2];
  scene.background=fogC.clone();scene.fog=new THREE.Fog(fogC,P.fogNear,P.fogFar);
  ctx.add(new THREE.HemisphereLight(P.hemiSky,P.hemiGnd,P.hemiI));
  const sun=new THREE.DirectionalLight(P.sun,P.sunI);
  const cx=W/2,cz=H/2,D=3200;sun.position.set(cx+dir.x*D,dir.y*D,cz+dir.z*D);sun.target.position.set(cx,0,cz);ctx.add(sun);ctx.add(sun.target);
  sun.castShadow=true;sun.shadow.mapSize.set(4096,2048);
  /* 光空间：left/right = 横向（垂直太阳方向的地面），top/bottom = 沿太阳方向（地上被 1/sin(高度) 拉长） */
  Object.assign(sun.shadow.camera,{left:-1800,right:1800,top:560,bottom:-560,near:200,far:6400});sun.shadow.camera.updateProjectionMatrix();
  sun.shadow.bias=-0.0004;sun.shadow.normalBias=.9;
  SUN=sun;DOME=makeDome(THREE,dir);ctx.add(DOME)}
/* reg.sun：别的模块要太阳方向（如水面高光）就读它，不要自己再建灯。reg.sky：雾色/地平线色/太阳方向，水面倒影可用 */
export function build(ctx){ctx.reg.sun=SUN;ctx.reg.sky={haze:hb=>hazeJS(ctx.THREE,hb),sunDir:SUN?SUN.position.clone().sub(SUN.target.position).normalize():null,horizon:P.horizon,zenith:P.zenith,glow:P.glow,fog:ctx.scene.fog}}
export function dispose(ctx){}
/* 雾必须正好在相机 far 处到 1，才能把远裁剪面（海面平面/远岸被切掉的那条硬边）藏进霾里。
   core 将来调 far 时这里自动跟上：fogFar = far，fogNear 按默认比例（900/9000）。 */
export function tick(ctx){const f=ctx.scene.fog,c=ctx.camera;if(f&&c&&f.far!==c.far){f.far=c.far;f.near=c.far*P.fogNear/9000}}
