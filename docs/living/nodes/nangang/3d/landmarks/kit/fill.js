/* landmarks 部件 · 地标材质里的天光补光（不是灯：sky 的灯、曝光都不动）。——Hark（CS线）2026-10-20
   从 nymphaeum.js 的 withFill 搬出来给以后的地标共用（宁芙殿自己那份没动，保住机位 6 逐像素不变）。
   sky 的太阳在方位 300°、高 14°：朝东、朝南的面整片背光，只吃均匀环境光，柱子线脚全是平的。
   这里按世界法线加一项「西南边亮天和铺地的反光」：outgoingLight += 反照率 × uFill × (底量 + (1−底量)·max(N·L_fill, 0))；不吃阴影。
   makeFill(T, {color, dir, base}) → withFill(mat, key)：给材质挂 onBeforeCompile，customProgramCacheKey 用 key 区分。
   可选 bounce: [r,g,b]（10-20 第 2 轮，广场凯旋门的拱腹）：再加一项铺地往上的反光 反照率 × bounce × max(−N·up, 0)，
   只照朝下的面（拱腹、檐口底）；不给 bounce 时着色器和以前一字不差。 */
export function makeFill(T, o = {}) {
  const U = {
    uFill: { value: new T.Color(...(o.color || [0.22, 0.235, 0.25])) },
    uFillDir: { value: new T.Vector3(...(o.dir || [-0.55, 0.5, 0.67])).normalize() },   // 西南偏上（x 东、z 南）
  };
  const base = (o.base ?? 0.15).toFixed(3), tag = o.tag || 'lm';
  if (o.bounce) U.uBounce = { value: new T.Color(...o.bounce) };
  const bnc = o.bounce ? `{vec3 dn=normalize((viewMatrix*vec4(0.,-1.,0.,0.)).xyz);outgoingLight+=diffuseColor.rgb*uBounce*max(dot(normal,dn),0.);}` : '';
  const withFill = (mat, key) => {
    mat.onBeforeCompile = s => {
      Object.assign(s.uniforms, U);
      s.fragmentShader = 'uniform vec3 uFill;uniform vec3 uFillDir;\n' + (o.bounce ? 'uniform vec3 uBounce;\n' : '') + s.fragmentShader.replace('#include <opaque_fragment>',
        `{vec3 fd=normalize((viewMatrix*vec4(uFillDir,0.)).xyz);float k=${base}+(1.-${base})*max(dot(normal,fd),0.);outgoingLight+=diffuseColor.rgb*uFill*k;}${bnc}
        #include <opaque_fragment>`);
    };
    mat.customProgramCacheKey = () => 'cs-fill-' + tag + '-' + key;
    return mat;
  };
  withFill.uniforms = U;
  return withFill;
}
