/* terrain · 区外（lookdev 第 2 轮，——Hark（CS线）2026-10-20）
   让南港不再是一座孤岛：
   1. 区外陆地：真实海岸（OSM）+ SRTM 高程烘成的粗网格（框边附近 64 像素一格，远处 192 像素一格），
      高度公式同 core ground()（海底 -6 → 陆地），框边一圈顶点运行时用 ctx.ground() 取高，再加一圈裙边盖缝。
      地面贴图自己一张（不碰 core 的共享画布）：土、干草、灌丛、石、城外田块、城里按全城底账房屋画的「远看屋顶色斑」。
   2. 远岸剖面：远平面（far 9000 像素）以外的真实地物（王子群岛、亚洲岸、马尔马拉南岸群山、乌卢达山……）
      画在一圈跟着相机走的环上（半径 RR，远平面以内），按真实方位、真实仰角（扣地球曲率）摆，所以任何机位看都在对的地平线上。
      环下半圈是「远海裙」，颜色 = 远处被雾吃掉的海，把海面平面到地平线之间补齐。
   数据：./outer_data.js（docs/cs/lookdev/r2/terrain/bake_outer.py 烘的）。 */
import D from './outer_data.js';

async function inflate(b64, Type) {
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const buf = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream('deflate'))).arrayBuffer();
  return new Type(buf);
}
const HGT = await inflate(D.hgt, Int16Array), CELL = await inflate(D.cell, Uint8Array);
const UC = await inflate(D.urban.c, Uint8Array), UY = await inflate(D.urban.y, Uint8Array);

let RR = 8300;              /* 远岸环半径（像素）：跟着相机远平面走，= far × 0.922（far 9000 时 8300）。r2 合并时 core 把 far 提到 16000，环跟着搬远，雾在环上的比例不变 */
const RR_OF = c => (c && c.far ? c.far : 9000) * 8300 / 9000;
const EX = 1.3;             /* 和 core 的高程夸张一致 */
const KR = 7 / 6, RE = 6371000;
const NA = 720;             /* 每 0.5° 一列 */

let ctxR = null, geo = null, mesh = null, skirt = null, tex = null, base = null, TX = null;
let ring = null, lastKey = '';
const BX = [D.xs[0], D.zs[0], D.xs[D.xs.length - 1], D.zs[D.zs.length - 1]];

/* ---------- 地面贴图（区外专用，2048 宽，逐像素算：不用几十万次 canvas 调用，免得软件渲染吃内存） ---------- */
const ih = (x, y, s) => { let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(s, 2246822519)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
function vn(x, y, s) { const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j, u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
  const a = ih(i, j, s), b = ih(i + 1, j, s), c = ih(i, j + 1, s), d = ih(i + 1, j + 1, s); return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v; }
function paintBase(ctx) {
  const TW = 2048, sc = TW / (BX[2] - BX[0]), TH = Math.round((BX[3] - BX[1]) * sc);
  base = document.createElement('canvas'); base.width = TW; base.height = TH;
  const X = base.getContext('2d', {willReadFrequently: true});
  /* 陆地蒙版：沙岸（描边）= 128，陆地 = 255 */
  X.setTransform(sc, 0, 0, sc, -BX[0] * sc, -BX[1] * sc); X.fillStyle = '#000'; X.fillRect(BX[0], BX[1], BX[2] - BX[0], BX[3] - BX[1]);
  X.beginPath(); for (const r of D.rings) { X.moveTo(r[0][0], r[0][1]); for (let i = 1; i < r.length; i++) X.lineTo(r[i][0], r[i][1]); X.closePath(); }
  X.lineJoin = 'round'; X.strokeStyle = '#808080'; X.lineWidth = 14; X.stroke(); X.fillStyle = '#fff'; X.fill('evenodd');
  const img = X.getImageData(0, 0, TW, TH), px = img.data;
  const nx = D.xs.length, xs = D.xs, zs = D.zs, U = D.urban;
  /* 坡度：高度格 → 每格坡度（像素/像素） */
  const slope = new Float32Array((nx - 1) * (zs.length - 1));
  for (let j = 0; j < zs.length - 1; j++) for (let i = 0; i < nx - 1; i++) { const h = HGT[j * nx + i] / 8; slope[j * (nx - 1) + i] = Math.hypot((HGT[j * nx + i + 1] / 8 - h) / (xs[i + 1] - xs[i]), (HGT[(j + 1) * nx + i] / 8 - h) / (zs[j + 1] - zs[j])); }
  let ci = 0, cj = 0;
  for (let y = 0; y < TH; y++) {
    const z = BX[1] + (y + .5) / sc; while (cj < zs.length - 2 && zs[cj + 1] <= z) cj++; ci = 0;
    for (let x = 0; x < TW; x++) {
      const o = (y * TW + x) * 4, m = px[o], wx = BX[0] + (x + .5) / sc;
      if (m < 40) { px[o] = 86; px[o + 1] = 126; px[o + 2] = 136; px[o + 3] = 255; continue; }       /* 海（同区内海色底） */
      if (m < 200) { px[o] = 216; px[o + 1] = 200; px[o + 2] = 160; px[o + 3] = 255; continue; }     /* 沙岸 */
      while (ci < nx - 2 && xs[ci + 1] <= wx) ci++;
      const sl = slope[cj * (nx - 1) + ci];
      let r = 206, g = 194, b = 160;                                                                   /* 区内同款底色 */
      /* 大斑块：干草金 / 灰绿灌丛 / 裸土，三层噪声 */
      const n1 = vn(wx / 420, z / 420, 1) * .6 + vn(wx / 160, z / 160, 2) * .4, n2 = vn(wx / 260, z / 260, 3);
      if (n1 > .55) { const t = Math.min(1, (n1 - .55) * 4) * .55; r += (196 - r) * t; g += (172 - g) * t; b += (100 - b) * t; }
      if (n2 < .38) { const t = Math.min(1, (.38 - n2) * 4) * .5; r += (124 - r) * t; g += (126 - g) * t; b += (82 - b) * t; }
      /* 灌丛点（坡上更密）和石灰岩露头（陡坡） */
      const n3 = vn(wx / 14, z / 14, 4), dens = .70 - Math.min(.22, sl * 1.4) - (n2 < .45 ? .08 : 0);
      if (n3 > dens) { const t = Math.min(1, (n3 - dens) * 6) * .75; r += (82 - r) * t; g += (92 - g) * t; b += (54 - b) * t; }
      else if (sl > .08 && vn(wx / 22, z / 22, 5) > .74 - sl) { r = 216; g = 210; b = 194; }
      /* 城外田块：按 900 像素的区块定朝向，块里切小长方形，深浅交替、边上一道田埂 */
      const ui = Math.floor((wx - U.box[0]) / U.cs), uj = Math.floor((z - U.box[1]) / U.cs), uk = (ui >= 0 && uj >= 0 && ui < U.w && uj < U.h) ? uj * U.w + ui : -1;
      const inCity = uk >= 0 && UC[uk] > 0;
      if (!inCity && sl < .06 && vn(wx / 700, z / 700, 6) > .45) {
        const bi = Math.floor(wx / 900), bj = Math.floor(z / 900), an = ih(bi, bj, 7) * 3.1416, ca = Math.cos(an), sa = Math.sin(an);
        const u = (wx * ca + z * sa) / (60 + ih(bi, bj, 8) * 60), v = (-wx * sa + z * ca) / (40 + ih(bi, bj, 9) * 40), fu = u - Math.floor(u), fv = v - Math.floor(v), q = ih(Math.floor(u), Math.floor(v), 10);
        const t = .45; const fr = q < .4 ? [188, 162, 94] : q < .75 ? [138, 132, 78] : [172, 148, 112];
        r += (fr[0] - r) * t; g += (fr[1] - g) * t; b += (fr[2] - b) * t;
        if (fu < .06 || fv < .08) { r *= .82; g *= .82; b *= .8; }
      }
      px[o] = r; px[o + 1] = g; px[o + 2] = b; px[o + 3] = 255;
    }
  }
  X.setTransform(1, 0, 0, 1, 0, 0); X.putImageData(img, 0, 0);
  TX = {sc, X0: BX[0], Z0: BX[1]};
}
/* 每次重建：当年的城市格（全城底账房屋，半数建成的年份 ≤ 当年才算）→ 一张小 DataTexture，着色器按它画屋顶色斑 */
let UT = null;
function paintYear(ctx) {
  const U = D.urban, Y = ctx.year, a = UT.image.data;
  for (let k = 0; k < U.w * U.h; k++) a[k] = (UC[k] && UY[k] - 100 <= Y) ? Math.min(255, UC[k] * 1.6) : 0;
  UT.needsUpdate = true;
}
/* 着色器补近处细节（贴图 8 像素一格，近看会糊）：城里约 9×7 像素一户的瓦色斑和户缝，城外 10 像素的灌丛点；
   按屏幕上一个像素覆盖多少世界像素（fwidth）淡出，远处退回平均色，不闪 */
function detailShader(mat, ctx) {
  const U = D.urban;
  mat.onBeforeCompile = sh => {
    sh.uniforms.uUrb = {value: UT}; sh.uniforms.uUrbBox = {value: new ctx.THREE.Vector4(U.box[0], U.box[1], U.w * U.cs, U.h * U.cs)};
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vXZ;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvXZ = (modelMatrix * vec4(position, 1.0)).xz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec2 vXZ; uniform sampler2D uUrb; uniform vec4 uUrbBox;
float th(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
vec3 lin(vec3 c){ return pow(c / 255.0, vec3(2.2)); }`)
      .replace('#include <map_fragment>', `#include <map_fragment>
{
  float wpp = length(fwidth(vXZ));                       // 一个屏幕像素 ≈ 多少世界像素
  float det = 1.0 - smoothstep(2.0, 6.0, wpp);
  vec2 uv = (vXZ - uUrbBox.xy) / uUrbBox.zw;
  float u = (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) ? texture2D(uUrb, uv).r : 0.0;
  if (u > 0.003) {
    vec2 g = vXZ / vec2(9.0, 7.0); vec2 id = floor(g + vec2(0.0, floor(vXZ.x / 9.0) * 0.37)); vec2 f = fract(g);
    float h1 = th(id), h2 = th(id + 17.3);
    vec3 roof = h2 < 0.15 ? lin(vec3(226., 214., 186.)) : h2 < 0.55 ? lin(vec3(178., 104., 62.)) : h2 < 0.85 ? lin(vec3(140., 82., 52.)) : lin(vec3(96., 66., 46.));
    vec3 dirt = lin(vec3(150., 124., 96.));
    float occ = step(h1, u * 0.9);
    float gap = (f.x > 0.84 || f.y > 0.80) ? 0.5 : 1.0;
    vec3 near = mix(dirt, roof * gap, occ);
    vec3 avg = mix(dirt, lin(vec3(160., 98., 64.)) * 0.92, u * 0.9);
    diffuseColor.rgb = mix(diffuseColor.rgb, mix(avg, near, det), min(1.0, u * 1.5));
  } else if (det > 0.0 && diffuseColor.g > diffuseColor.b * 1.08) {   // 陆地（不是海色）上的灌丛点
    vec2 g = vXZ / 11.0; vec2 id = floor(g); vec2 f = fract(g) - 0.5; float h = th(id + 3.1);
    float r = 0.18 + 0.22 * th(id + 9.7);
    float dot_ = (h < 0.32 && length(f) < r) ? 1.0 : 0.0;
    diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(0.55, 0.62, 0.48), dot_ * det * 0.8);
  }
}`);
  };
  mat.customProgramCacheKey = () => 'terrain-outer-detail';
}

/* ---------- 网格 ---------- */
export function init(ctx) {
  const {THREE} = ctx; ctxR = ctx;
  paintBase(ctx);
  const cv = document.createElement('canvas'); cv.width = base.width; cv.height = base.height;
  cv.getContext('2d').drawImage(base, 0, 0); base = null;
  tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = ctx.renderer.capabilities.getMaxAnisotropy();
  const nx = D.xs.length, nz = D.zs.length, pos = new Float32Array(nx * nz * 3), uv = new Float32Array(nx * nz * 2), idx = [];
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
    const k = j * nx + i; pos[k * 3] = D.xs[i]; pos[k * 3 + 1] = HGT[k] / 8; pos[k * 3 + 2] = D.zs[j];
    uv[k * 2] = (D.xs[i] - BX[0]) / (BX[2] - BX[0]); uv[k * 2 + 1] = 1 - (D.zs[j] - BX[1]) / (BX[3] - BX[1]);
  }
  for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) if (CELL[j * (nx - 1) + i]) { const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1; idx.push(a, c, b, b, c, d); }
  geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geo.setIndex(idx);
  UT = new THREE.DataTexture(new Uint8Array(D.urban.w * D.urban.h), D.urban.w, D.urban.h, THREE.RedFormat, THREE.UnsignedByteType);
  UT.magFilter = UT.minFilter = THREE.LinearFilter; UT.flipY = false;
  const mat = new THREE.MeshLambertMaterial({map: tex}); detailShader(mat, ctx);
  mesh = new THREE.Mesh(geo, mat); mesh.receiveShadow = true; mesh.name = 'terrain-outer'; ctx.add(mesh);
  /* 框边裙：沿南港框一圈，每 8 像素一段，从 ground() 垂到 -12，盖住粗细两套网格之间的缝 */
  const per = [], W = D.W, Hh = D.H, st = 8;
  for (let x = 0; x < W; x += st) per.push([x, 0]); for (let z = 0; z < Hh; z += st) per.push([W, z]);
  for (let x = W; x > 0; x -= st) per.push([x, Hh]); for (let z = Hh; z > 0; z -= st) per.push([0, z]); per.push([0, 0]);
  const sp = new Float32Array(per.length * 6), su = new Float32Array(per.length * 4), si = [];
  per.forEach(([x, z], k) => { sp.set([x, 0, z, x, -12, z], k * 6); const u = (x - BX[0]) / (BX[2] - BX[0]), v = 1 - (z - BX[1]) / (BX[3] - BX[1]); su.set([u, v, u, v], k * 4); if (k) { const a = (k - 1) * 2; si.push(a, a + 1, a + 2, a + 2, a + 1, a + 3); } });
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(sp, 3)); sg.setAttribute('uv', new THREE.BufferAttribute(su, 2)); sg.setIndex(si); sg.userData.per = per;
  skirt = new THREE.Mesh(sg, new THREE.MeshLambertMaterial({map: tex, side: THREE.DoubleSide})); skirt.name = 'terrain-skirt'; ctx.add(skirt);
  initRing(ctx);
}

export function build(ctx) {
  /* 框边一圈顶点按 core 的 ground() 取高（当年石堤/港池可能改到框边） */
  const p = geo.attributes.position.array, nx = D.xs.length, nz = D.zs.length, W = D.W, Hh = D.H;
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
    const x = D.xs[i], z = D.zs[j], onX = (x === 0 || x === W) && z >= 0 && z <= Hh, onZ = (z === 0 || z === Hh) && x >= 0 && x <= W;
    if (onX || onZ) p[(j * nx + i) * 3 + 1] = ctx.ground(Math.min(W - .5, Math.max(.5, x)), Math.min(Hh - .5, Math.max(.5, z)));
  }
  geo.attributes.position.needsUpdate = true; geo.computeVertexNormals();
  const sp = skirt.geometry.attributes.position.array, per = skirt.geometry.userData.per;
  per.forEach(([x, z], k) => { sp[k * 6 + 1] = ctx.ground(Math.min(W - .5, Math.max(.5, x)), Math.min(Hh - .5, Math.max(.5, z))) - .3; });
  skirt.geometry.attributes.position.needsUpdate = true; skirt.geometry.computeVertexNormals();
  paintYear(ctx);
  /* reg.horizon：water 想让远海裙和自己的海色一致，就在 build 里写 ctx.reg.horizon.sea = THREE.Color */
  RR = RR_OF(ctx.camera); ctx.reg.horizon = {sea: null, haze: 1, radius: RR};
  lastKey = '';
}

/* ---------- 远岸环 ---------- */
function initRing(ctx) {
  const {THREE} = ctx, mk = (name, order) => {
    const g = new THREE.BufferGeometry(), pos = new Float32Array((NA + 1) * 2 * 3), col = new Float32Array((NA + 1) * 2 * 3), idx = [];
    for (let k = 0; k < NA; k++) { const a = k * 2; idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3); }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.setIndex(idx);
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({vertexColors: true, fog: false, side: THREE.DoubleSide}));
    m.frustumCulled = false; m.name = name; m.renderOrder = order; ctx.add(m); return m;
  };
  ring = {sea: mk('horizon-sea', 0), far: mk('horizon-far', 1), near: mk('horizon-near', 2)};
}
const fogFactor = (f, d) => !f ? 0 : f.isFogExp2 ? 1 - Math.exp(-((f.density * d) ** 2)) : Math.min(1, Math.max(0, (d - f.near) / (f.far - f.near)));
/* 每帧（still 模式在出图前）把环搬到相机脚下，按相机高度重算仰角；相机没动就不算 */
export function tick(ctx) {
  if (!ring) return;
  const {THREE, camera: c, scene} = ctx, fog = scene.fog;
  const fogC = (fog && fog.color) || (scene.background && scene.background.isColor ? scene.background : new THREE.Color(0xbfd0d4));
  const seaBase = (ctx.reg.horizon && ctx.reg.horizon.sea) || new THREE.Color(0x5b8590);
  const key = [c.position.x | 0, c.position.y.toFixed(1), c.position.z | 0, fogC.getHexString(), seaBase.getHexString(), (ctx.reg.horizon && ctx.reg.horizon.haze) || 1, fog ? fog.near + ',' + fog.far : ''].join('|');
  const rr = RR_OF(c); if (rr !== RR) { RR = rr; if (ctx.reg.horizon) ctx.reg.horizon.radius = RR; lastKey = ''; }
  if (key === lastKey) return; lastKey = key;
  const h = Math.max(1, c.position.y) * D.mpp, dip = Math.sqrt(2 * h / (KR * RE)), cx = c.position.x, cz = c.position.z, cy = c.position.y;
  const Y = a => cy + RR * Math.tan(a);
  const ff = fogFactor(fog, RR), seaC = seaBase.clone().lerp(fogC, ff);
  const nearC = new THREE.Color(0x56646f), farC = new THREE.Color(0x6a7890), tmp = new THREE.Color();
  /* reg.horizon.haze：sky 想让远岸更淡/更清楚就写一个倍数（1 = 默认） */
  const hz = Math.min(1.2, Math.max(.5, (ctx.reg.horizon && ctx.reg.horizon.haze) || 1));
  const LO = new Float32Array(NA), HI = new Float32Array(NA);
  for (const [name, m] of Object.entries(ring)) {
    const P = m.geometry.attributes.position.array, C = m.geometry.attributes.color.array, pr = D.prof[name];
    if (name !== 'sea') {
      for (let k = 0; k < NA; k++) { const d0 = pr.d0[k], H = pr.H[k] * EX, dH = pr.dH[k];
        if (!d0) { LO[k] = HI[k] = NaN; continue; }
        HI[k] = Math.atan((H - h) / dH);
        LO[k] = name === 'far' ? -dip : Math.max(Math.atan((-d0 * d0 / (2 * KR * RE) - h) / d0), -0.2);
        if (HI[k] < LO[k]) HI[k] = LO[k]; }
      /* 没有地的列：贴着旁边有地那列的底收成一条线（不拉出尖刺）；两边都没有就收在地平线上 */
      /* 岛/岸的两端那一列收矮一点（只有一侧有地的列容易拉成尖刺） */
      for (let k = 0; k < NA; k++) if (!isNaN(LO[k]) && (isNaN(LO[(k + NA - 1) % NA]) || isNaN(LO[(k + 1) % NA]))) HI[k] = LO[k] + (HI[k] - LO[k]) * .35;
      for (let k = 0; k < NA; k++) if (isNaN(LO[k])) { const a = LO[(k + NA - 1) % NA], b = LO[(k + 1) % NA]; LO[k] = HI[k] = !isNaN(a) ? a : !isNaN(b) ? b : -dip; }
      for (let k = 0; k < NA; k++) if (isNaN(HI[k])) HI[k] = LO[k];
      /* 单列尖峰削平（r2 合并：far 提到 16000 后雾薄了，亚洲岸近段相邻列 dH 一远一近，拉出锯齿）：比两邻都高的列压到两邻较高者 */
      if (name === 'near') { const T = HI.slice(); for (let k = 0; k < NA; k++) { const a = T[(k + NA - 1) % NA], b = T[(k + 1) % NA]; if (T[k] > a && T[k] > b) HI[k] = Math.max(LO[k], Math.max(a, b)); } }
    }
    for (let k = 0; k <= NA; k++) {
      const kk = k % NA, az = kk / 2 * Math.PI / 180, dx = Math.sin(az), dz = Math.cos(az);
      let lo, hi, col;
      if (name === 'sea') { lo = -0.21; hi = -dip; col = seaC; }
      else {
        lo = LO[kk]; hi = HI[kk];
        /* 空气透视：真实距离越远越接近雾色；坡面按方位哈希有一点明暗 */
        const dist = pr.dH[kk] || 20000, haze = Math.min(.92, (name === 'far' ? .66 : .48) + dist / 200000) * hz;
        col = tmp.copy(name === 'far' ? farC : nearC).multiplyScalar(.9 + .2 * ctx.hsh(kk, name === 'far' ? 7 : 8)).lerp(fogC, haze);
      }
      const a = k * 6;
      P[a] = cx + dx * RR; P[a + 1] = Y(lo); P[a + 2] = cz + dz * RR;
      P[a + 3] = cx + dx * RR; P[a + 4] = Y(hi); P[a + 5] = cz + dz * RR;
      /* 远海裙：靠地平线那边稍亮一点（远海反天光） */
      const top = name === 'sea' ? tmp.copy(col).lerp(fogC, .35) : col;
      C[a] = col.r; C[a + 1] = col.g; C[a + 2] = col.b; C[a + 3] = top.r; C[a + 4] = top.g; C[a + 5] = top.b;
    }
    /* 三层错开一点半径，深度上远海裙在最后、近岸在最前 */
    const s = name === 'sea' ? 1.004 : name === 'far' ? 1.002 : 1;
    if (s !== 1) for (let k = 0; k <= NA; k++) for (const o of [0, 3]) { const a = k * 6 + o; P[a] = cx + (P[a] - cx) * s; P[a + 2] = cz + (P[a + 2] - cz) * s; }
    m.geometry.attributes.position.needsUpdate = true; m.geometry.attributes.color.needsUpdate = true;
  }
}
export function dispose() {}
