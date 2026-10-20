/* 人群渲染（压力试作，2026-10-19）。人一多，不能再一人一套 mesh：
   - 每个身体部件一张 InstancedMesh（躯干、头、袍、短裙、大腿×2、小腿×2、上臂×2、前臂×2、各种负重），
     不管多少人，绘制调用数都固定（约 20 次）。每帧在 CPU 上按姿势通道算每个部件的矩阵。
   - 三档：近（关节人，跟主角同一套姿势引擎）→ 远（一根着色小柱 + 负重的颜色块）→ 视野外不算。
   - 每个人的位置是时间的纯函数（路线 × 速度 × 出发时刻），不存状态：看不见的人一点不花钱。
   - 别人对你的反应：商人走过时，身边的人躬身让到一边。
   ——Hark（CS线） */
import {hash, rng, pickTemper, gaitOf, blank, walk, stay, carry, OVER, env} from './pose.js?v=20261019y';

const PAL = {   // 衣色：染过的贵、素的便宜。都是按意图给的范围，人人从里面抽
  rich: ['#5a2f4a', '#3f3a6a', '#7a2a2a', '#2f4a3a'], trader: ['#4f6a3a', '#7a5a2a', '#5a6a7a', '#8a6a3a'],
  woman: ['#a85a3c', '#6a4a7a', '#3c6a8a', '#9a7a3a', '#8a3c3c'], laborer: ['#6e5038', '#7a6a50', '#5a4a38'],
  commoner: ['#b8a788', '#a89a7a', '#c9b48a', '#9a8a6a', '#8a7a5a'], child: ['#c9b48a', '#b8a080', '#d0c09a'],
  old: ['#9a8e74', '#8a826a', '#a89a80'],
};
const SKIN = ['#c89a74', '#b98c6a', '#d0a07a', '#a87a58'];
// 长卷缩远时按「在干什么」上色：打水蓝、扛货褐、市场赭黄、广场紫、跑腿绿。近看仍是衣服本来的颜色
const ACTC = {water: '#2f6fb0', haul: '#7a4a1e', market: '#c8901a', forum: '#8a2a5a', errand: '#4f7a34'};
const LOADC = {sack: '#d2c3a0', jar_full: '#b5683e', jar_empty: '#b5683e', crate: '#8a6a48', basket: '#a8864e'};

const SASH = {woman: '#9a3028', trader: '#c8901a', rich: '#24386a', laborer: '#a89068', old: '#4a3c30', commoner: '#6a4a2a'};   // 腰带：身份色，中景小人上也留得住
export function initCrowd(E) {
  const {THREE, scene, elevPx, isLand, MPP, EX, data, T, getMerchant} = E;
  const M = 1 / MPP, N = E.n;
  const R = data.routes.map(r => { const P = r.path; let L = 0; const cum = [0]; for (let i = 1; i < P.length; i++) { L += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]); cum.push(L) } return {...r, L, cum} });

  // ---------- 铺人：第 i 个人分到第 i % 路线数 条路；意图来自路线（底账推出），长相和步态由种子抽 ----------
  const P = [], lastOn = new Map();
  // 户籍版（folk.py）：每个人是一栋真房子里的一口人，去哪、跟谁都写在底账推出来的数据里
  const FOLK = data.people, LAB = data.labels || [], NN = FOLK ? Math.min(N, FOLK.length) : N, BYID = new Map();
  if (FOLK) for (let i = 0; i < NN; i++) BYID.set(FOLK[i][0], i);
  for (let i = 0; i < NN; i++) {
    const F = FOLK && FOLK[i], ri = F ? F[1] : i % R.length, r = F ? {...R[ri], why: F[7] === 'follow' ? R[ri].why : F[7]} : R[ri], seed = hash(r.h + ':' + (F ? F[5] : i)), U = rng(seed);
    let role = F ? F[2] : r.intent;
    if (!F && role === 'commoner') { const x = U(); role = x < .16 ? 'child' : x < .3 ? 'old' : x < .65 ? 'woman' : 'commoner' }
    const out = {child: 'child_walk', old: 'old', woman: 'woman', rich: 'rich', trader: 'trader', laborer: 'porter', commoner: 'walker'}[role];
    const back = {woman: r.why === 'water' ? 'woman_full' : 'woman', laborer: 'porter_load', trader: 'trader_load', old: 'old', child: 'child_walk', rich: 'rich', commoner: 'walker'}[role];
    const kid = role === 'child', loadOut = r.why === 'water' && !kid ? 'jar_empty' : null;
    const loadBack = kid ? null : r.why === 'water' ? 'jar_full' : role === 'laborer' ? 'sack' : role === 'trader' ? (U() < .6 ? 'crate' : 'basket') : r.why === 'errand' && U() < .4 ? 'basket' : null;
    if (!F && r.why === 'water' && role !== 'woman') role = 'woman';
    const h = role === 'child' ? (F ? Math.min(1.45, .78 + F[4] * .065) : 1.0 + U() * .3) : role === 'woman' ? 1.5 + U() * .14 : role === 'old' ? 1.55 + U() * .14 : 1.6 + U() * .18;
    const b = role === 'laborer' ? 1.1 + U() * .15 : role === 'rich' ? 1.05 + U() * .15 : role === 'child' ? .78 + U() * .08 : .88 + U() * .16;
    const nb = lastOn.get(ri) || [];
    const u = pickTemper(seed, [out, back], {h}, nb.slice(-4)); nb.push(u); lastOn.set(ri, nb);   // 同一条路上的人尽量不像
    const go = gaitOf(out, u), gb = gaitOf(back, u);
    const pal = PAL[role] || PAL.commoner, col = pal[Math.floor(U() * pal.length)];
    const fem = F ? F[3] === 'f' : role === 'woman', long = role === 'rich' || role === 'woman' || (role === 'old' && (F ? fem : U() < .4));
    const pauseFar = r.why === 'water' ? 18 + U() * 20 : r.why === 'market' ? 40 + U() * 60 : r.why === 'forum' ? 80 + U() * 80 : r.why === 'haul' ? 6 + U() * 8 : r.why === 'visit' ? 60 + U() * 60 : r.why === 'debt' ? 25 + U() * 20 : 20 + U() * 30;
    const pauseHome = 30 + U() * 120;
    const L = r.L / M, tOut = L / go.speed, tBack = L / gb.speed, cyc = tOut + pauseFar + tBack + pauseHome;
    P.push({i, r, role, go, gb, h, b, k: h / 1.7, col: new THREE.Color(col), skin: new THREE.Color(SKIN[Math.floor(U() * SKIN.length)]),
      leg: new THREE.Color(long ? col : role === 'laborer' || role === 'child' ? SKIN[0] : '#7a6a50'), sash: SASH[role] ? new THREE.Color(SASH[role]) : null, long, veil: role === 'woman' || (F && role === 'old' && fem), hat: role === 'rich' && U() < .5,
      loadOut, loadBack, pauseFar, pauseHome, tOut, tBack, cyc, off: U() * cyc, dens: U(), ph0: U() * 6.28,
      farPose: r.why === 'water' ? 'queue' : r.why === 'haul' ? 'rest' : r.why === 'market' ? 'sell' : r.why === 'forum' || r.why === 'visit' || r.why === 'debt' ? 'talk' : 'stand',
      F, so: go.speed, sb: gb.speed, lag: 0, sideX: 0,
      act: new THREE.Color(ACTC[r.why] || ACTC.errand), x: 0, z: 0, dir: 0, vis: false});
  }

  if (FOLK) {                                                                // 约伴、跟随：同一个时钟。先对齐约伴，再让跟着的人抄领头人的时钟
    const tie = o => { o.ties = []; for (const [id, l] of o.F[11]) { const j = BYID.get(id); if (j != null) o.ties.push([P[j], LAB[l]]) } o.rel = new Map(o.ties.map(t => [t[0], t[1]])) };
    for (const o of P) { tie(o); const j = BYID.get(o.F[10]); o.mate = j != null ? P[j] : null }
    for (const o of P) { const m = o.mate; if (!m || m.i < o.i) continue;
      const pf = Math.max(o.pauseFar, m.pauseFar); o.pauseFar = m.pauseFar = pf + 30; o.farPose = m.farPose = 'talk';
      const cyc = Math.max(o.cyc, m.cyc) - Math.max(o.pauseFar, 0) + pf + 30; for (const q of [o, m]) q.cyc = q.tOut + q.pauseFar + q.tBack + Math.max(20, cyc - q.tOut - q.pauseFar - q.tBack);
      m.cyc = o.cyc = Math.max(o.cyc, m.cyc); m.off = ((o.off + o.tOut - m.tOut) % o.cyc + o.cyc) % o.cyc; m.dens = o.dens }
    for (const o of P) { const j = BYID.get(o.F[9]); if (j == null) continue; const L = P[j]; o.lead = L;
      for (const k of ['off', 'cyc', 'tOut', 'tBack', 'pauseFar', 'dens', 'so', 'sb']) o[k] = L[k];
      o.lag = (.7 + (o.i % 3) * .45) * M; o.sideX = (o.i & 1 ? .5 : -.5); o.farPose = o.role === 'child' ? 'stand' : L.farPose }
  }
  // ---------- 部件：每样一张 InstancedMesh。几何按 k=1、b=1 建，个子和胖瘦放在根矩阵的缩放里 ----------
  const MAT = new THREE.MeshLambertMaterial({color: '#ffffff'});
  // 人小到几个像素时，后期的描墨会把整个人涂黑：这时让人在颜色缓冲里写 alpha 0，后期见了就不按颜色分界描（法线那一遍也不画人）
  const NOINK = {value: 0}, inkHook = sh => { sh.uniforms.uNoInk = NOINK; sh.fragmentShader = 'uniform float uNoInk;\n' + sh.fragmentShader.replace('#include <dithering_fragment>', '#include <dithering_fragment>\n if (uNoInk > .5) gl_FragColor.a = 0.;') };
  MAT.onBeforeCompile = inkHook;
  const cyl = (r0, r1, h, seg = 6) => new THREE.CylinderGeometry(r1, r0, h, seg).translate(0, -h / 2, 0);
  const parts = {};
  const mk = (name, geo, cap) => { const m = new THREE.InstancedMesh(geo, MAT, cap); m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); m.count = 0; m.frustumCulled = false;
    m.setColorAt(0, new THREE.Color()); scene.add(m); parts[name] = m; return m };
  // 帧图的行：身份 × 负重 × 步态（中景小人用，见下面 buildAtlas）
  const VK = new Map(), VREP = [];
  const vkey = (o, load, gait) => { const k = o.role + '|' + o.long + '|' + o.veil + '|' + o.hat + '|' + (load || '') + '|' + (gait ? 'w' : o.farPose);
    let v = VK.get(k); if (v == null) { v = VREP.length; VK.set(k, v); VREP.push({o, load, gait, pose: o.farPose}) } return v };
  for (const o of P) { o.vOut = vkey(o, o.loadOut, o.go); o.vBack = vkey(o, o.loadBack, o.gb); o.vFar = vkey(o, o.loadOut, null) }
  const capN = Math.max(64, N, VREP.length * 8 * 7);
  // 外形：不加人数、不加骨头，只把几何换成有轮廓的（窄腰宽肩、衣摆带褶），再加手和一条腰带
  const lathe = (pts, seg, fold = 0, foldY = -1e9) => { const g = new THREE.LatheGeometry(pts.map(q => new THREE.Vector2(q[0], q[1])), seg), a = g.attributes.position;
    for (let i = 0; i < a.count; i++) { const x = a.getX(i), y = a.getY(i), z = a.getZ(i); if (y > foldY) continue; const th = Math.atan2(z, x), f = 1 + fold * Math.sin(th * 5) * Math.min(1, (foldY - y) / .3); a.setX(i, x * f); a.setZ(i, z * f) }
    g.computeVertexNormals(); return g };
  mk('chest', lathe([[.13, 0], [.15, .1], [.16, .3], [.2, .48], [.17, .56], [.07, .6], [0, .6]], 8).scale(1, 1, .72), capN);   // 胸背扁、肩宽
  mk('sash', new THREE.CylinderGeometry(.165, .17, .07, 8).translate(0, .04, 0).scale(1, 1, .76), capN);
  mk('skirt', lathe([[.25, -.27], [.22, -.12], [.17, .05], [0, .05]], 10, .06, -.12).scale(1, 1, .85), capN);   // 短衫下摆，有褶
  mk('robe', lathe([[.33, -.78], [.29, -.6], [.2, -.25], [.16, 0], [.15, .05], [0, .05]], 12, .07, -.45).scale(1, 1, .85), capN);   // 长袍：下摆张开，有褶
  mk('head', new THREE.SphereGeometry(.11, 7, 5).translate(0, .14, 0), capN);
  mk('cap', new THREE.SphereGeometry(.115, 7, 4, 0, Math.PI * 2, 0, Math.PI * .5).translate(0, .15, -.01), capN);
  mk('veil', new THREE.CylinderGeometry(.12, .2, .32, 7, 1, true).translate(0, .02, -.02), capN); parts.veil.material = MAT.clone(); parts.veil.material.side = THREE.DoubleSide; parts.veil.material.onBeforeCompile = inkHook;
  mk('hat', new THREE.CylinderGeometry(.1, .12, .1, 7).translate(0, .27, 0), capN);
  // 职业配件：每种多一次绘制，只给戴的人算
  mk('straw', new THREE.ConeGeometry(.3, .16, 12).translate(0, .3, 0), capN);                       // 脚夫的斗笠
  mk('pole', new THREE.BoxGeometry(.035, .035, 1.5), capN);                                        // 扁担
  mk('apron', new THREE.BoxGeometry(.3, .42, .025).translate(0, -.16, .17), capN);                 // 商贩的围裙
  mk('beard', new THREE.ConeGeometry(.065, .16, 6).rotateX(Math.PI).translate(0, .02, .09), capN); // 老人的胡子
  mk('cane', cyl(.016, .016, 1, 5), capN);                                                         // 拐杖：高度按手到地面拉
  mk('hem', new THREE.CylinderGeometry(.335, .34, .07, 12, 1, true).translate(0, -.74, 0).scale(1, 1, .85), capN);   // 长袍下摆的镶边
  for (const s of ['L', 'R']) { mk('th' + s, cyl(.075, .06, .46), capN); mk('sh' + s, cyl(.055, .045, .44), capN); mk('ft' + s, new THREE.BoxGeometry(.09, .06, .22).translate(0, -.03, .05), capN);
    mk('up' + s, cyl(.055, .045, .3), capN); mk('lo' + s, cyl(.045, .035, .28), capN); mk('hd' + s, new THREE.SphereGeometry(.045, 5, 4).scale(1, 1.3, .8).translate(0, -.03, 0), capN) }
  const jarPts = [[0, 0], [.07, .02], [.13, .12], [.14, .26], [.09, .38], [.05, .44], [.07, .5], [0, .5]].map(q => new THREE.Vector2(q[0], q[1]));
  mk('sack', new THREE.SphereGeometry(.3, 7, 5).scale(1.25, .7, .9), capN);
  mk('jar', new THREE.LatheGeometry(jarPts, 7), capN);
  mk('crate', new THREE.BoxGeometry(.42, .3, .32), capN);
  mk('far', new THREE.CylinderGeometry(.2, .24, 1.6, 5).translate(0, .8, 0), capN);           // 远处：一根着色小柱
  // 远处的地上色带：走路的人拖一道椭圆，停着的人铺一片圆。很多人叠起来，热闹的街就成了一条流动的色带，喷泉和市场成一团
  mk('trail', new THREE.CircleGeometry(1, 12).rotateX(-Math.PI / 2), capN);
  parts.trail.material = new THREE.MeshBasicMaterial({color: '#ffffff', transparent: true, opacity: .28, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2});
  parts.trail.renderOrder = 1;
  mk('farLoad', new THREE.BoxGeometry(.5, .4, .5).translate(0, 1.75, 0), capN);              // 远处：负重的色块（顶在头上那一块）

  // ---------- 矩阵链 ----------
  const m4 = () => new THREE.Matrix4();
  const Mroot = m4(), Mhip = m4(), Mtor = m4(), Mneck = m4(), Mj = m4(), Mk = m4(), Mt = m4(), Mtmp = m4();
  const E3 = new THREE.Euler(), Qn = new THREE.Quaternion(), Vp = new THREE.Vector3(), Vs = new THREE.Vector3(1, 1, 1);
  function local(out, x, y, z, rx, ry, rz) { E3.set(rx, ry, rz, 'XYZ'); Qn.setFromEuler(E3); Vp.set(x, y, z); return out.compose(Vp, Qn, Vs) }
  const cnt = {}; for (const k in parts) cnt[k] = 0;
  let MASK = false; const CLOTH = new THREE.Color('#ffffff'), C_W = new THREE.Color(1, 1, 1), C_K = new THREE.Color(0, 0, 0);
  function put(name, mat, col) { const m = parts[name], c = cnt[name]++; m.setMatrixAt(c, mat); if (MASK) col = col === CLOTH ? C_W : C_K; if (col) m.setColorAt(c, col) }
  const C_INK = new THREE.Color('#3a2e22'), C_VEIL = new THREE.Color('#e8dfcb'), C_HAIR = new THREE.Color('#2a1e16'), C_GOLD = new THREE.Color('#c9a34a'), C_GREY = new THREE.Color('#d9d4c8'), C_STRAW = new THREE.Color('#c8ac6a'), C_WOOD = new THREE.Color('#6a4a2a'), C_APRON = new THREE.Color('#ddd2b6');
  const LC = {}; for (const k in LOADC) LC[k] = new THREE.Color(LOADC[k]);

  function drawFull(o, Pp, load) {
    Vp.set(o.x, o.y, o.z); E3.set(0, o.dir, 0); Qn.setFromEuler(E3); Vs.set(M * o.b, M * EX * o.k, M * o.b); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
    Mhip.multiplyMatrices(Mroot, local(Mt, 0, .92 * (1 + Pp.bob) + Pp.lift / o.k, 0, 0, 0, Pp.hip));
    Mtor.multiplyMatrices(Mhip, local(Mt, 0, 0, 0, Pp.stoop, Pp.twist, Pp.side));
    const pole = o.role === 'laborer' && !load, cane = o.role === 'old';
    if (pole) Pp.arms[1] = [.9, 1.75, 0];                                    // 手扶着肩上的扁担
    if (cane) Pp.arms[1] = [.35, .35, .05];
    put('chest', Mtor, o.col); if (o.sash) put('sash', Mtor, o.sash);
    if (o.long) { Mtmp.multiplyMatrices(Mhip, local(Mt, 0, 0, 0, (Pp.legs[0][0] - Pp.legs[1][0]) * .08, 0, 0)); put('robe', Mtmp, o.col); if (o.sash && o.role !== 'old') put('hem', Mtmp, o.sash) } else put('skirt', Mtor, o.col);
    if (o.role === 'trader') put('apron', Mhip, C_APRON);
    if (pole) { Mtmp.multiplyMatrices(Mtor, local(Mt, .17, .62, .1, 0, 0, 0)); put('pole', Mtmp, C_WOOD);
      for (const z of [-.68, .78]) { Mj.multiplyMatrices(Mtmp, local(Mt, 0, -.32, z, 0, 0, 0)); Mj.scale(Vp.set(.55, .7, .55)); put('crate', Mj, LC.basket) } }
    Mneck.multiplyMatrices(Mtor, local(Mt, 0, .6, 0, Pp.neck, Pp.headYaw, 0));
    put('head', Mneck, o.skin); put(o.veil ? 'veil' : 'cap', Mneck, o.veil ? C_VEIL : o.role === 'old' ? C_GREY : C_HAIR);
    if (o.hat) put('hat', Mneck, C_GOLD);
    if (o.role === 'laborer') put('straw', Mneck, C_STRAW);
    if (o.role === 'old' && !o.veil) put('beard', Mneck, C_GREY);
    for (let i = 0; i < 2; i++) {
      const s = i ? 1 : -1, S = i ? 'R' : 'L';
      Mj.multiplyMatrices(Mhip, local(Mt, s * .1, 0, 0, -Pp.legs[i][0], 0, 0)); put('th' + S, Mj, o.leg);
      Mk.multiplyMatrices(Mj, local(Mt, 0, -.46, 0, Pp.legs[i][1], 0, 0)); put('sh' + S, Mk, o.long ? o.col : o.skin);
      Mtmp.multiplyMatrices(Mk, local(Mt, 0, -.44, 0, 0, 0, 0)); put('ft' + S, Mtmp, C_INK);
      const A = Pp.arms[i];
      Mj.multiplyMatrices(Mtor, local(Mt, s * .22, .56, 0, -A[0], 0, (i ? -1 : 1) * (.08 + A[2]))); put('up' + S, Mj, o.role === 'laborer' ? o.skin : o.col);
      Mk.multiplyMatrices(Mj, local(Mt, 0, -.3, 0, -A[1], 0, 0)); put('lo' + S, Mk, o.long && o.role !== 'laborer' ? o.col : o.skin);   // 长袍的人袖子盖到手腕
      Mtmp.multiplyMatrices(Mk, local(Mt, 0, -.28, 0, 0, 0, 0)); put('hd' + S, Mtmp, o.skin);
      if (cane && i === 1) { const hx = Mtmp.elements[12], hy = Mtmp.elements[13], hz = Mtmp.elements[14];   // 拐杖从手里直直落到地上
        Vp.set(hx, hy, hz); Qn.identity(); Vs.set(M * o.b, Math.max(.1, hy - o.y), M * o.b); Mj.compose(Vp, Qn, Vs); Vs.set(1, 1, 1); put('cane', Mj, C_WOOD) }
      if (i === 0 && load === 'basket') { Mtmp.multiplyMatrices(Mk, local(Mt, 0, -.3, 0, 0, 0, 0)); Mtmp.scale(Vp.set(.6, .6, .6)); put('crate', Mtmp, LC.basket) }
    }
    if (load === 'sack') { Mtmp.multiplyMatrices(Mtor, local(Mt, 0, .66, -.16, 0, 0, 0)); put('sack', Mtmp, LC.sack) }
    else if (load === 'crate') { Mtmp.multiplyMatrices(Mtor, local(Mt, 0, .28, .3, 0, 0, 0)); put('crate', Mtmp, LC.crate) }
    else if (load === 'jar_full') { Mtmp.multiplyMatrices(Mneck, local(Mt, 0, .28, -.02, 0, 0, 0)); put('jar', Mtmp, LC.jar_full) }
    else if (load === 'jar_empty') { Mtmp.multiplyMatrices(Mtor, local(Mt, .2, .05, .08, 0, 0, -.5)); put('jar', Mtmp, LC.jar_empty) }
  }
  function drawFar(o, load, k = 1) {   // k：长卷缩远时把柱子放大，让人流在纸上看得出来
    Vp.set(o.x, o.y, o.z); E3.set(0, o.dir, 0); Qn.setFromEuler(E3); Vs.set(M * o.b * k, M * EX * o.k * k, M * o.b * k); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
    const w = Math.min(1, (k - 1) / 1.5);
    if (w > 0) { CT.copy(o.col).lerp(o.act, .35 + .65 * w); put('far', Mroot, CT) } else put('far', Mroot, o.col);
    if (load) put('farLoad', Mroot, LC[load]);
    if (k > 1.3) {                                                           // 只在长卷缩远时铺色带
      const walking = o.seg !== 'far', s = M * k;
      Vp.set(o.x, o.y + .4, o.z);                                            // o.y 就是街面（地形 +1.5），色带压在街面上
      Vs.set(walking ? 2.4 * s : 4.5 * s, 1, walking ? 8 * s : 4.5 * s);     // 尺寸按画面而不是按真人：缩远后一米不到一个像素
      Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
      put('trail', Mroot, o.act);
    }
  }
  const CT = new THREE.Color();

  // ---------- 中景小人：开场用自己的关节人拍一张帧图，远处每人只画一张小片 ----------
  // 帧图每一行是一种「身份 × 负重 × 步态」，一行 8 个朝向 × (6 帧走路 + 1 帧站着)。衣服拍成白色，片上再染各人的衣色；
  // alpha 里记哪里是衣服（0.5）哪里不是（1），外轮廓描一圈墨，跟长卷的线稿对得上。只在长卷斜俯（方位固定）时用。
  const TW = 32, TH = 48, NF = 7, ND = 8, FOOT = .1;
  const SH = 2.5 * M * EX, SW = SH * TW / TH;                              // 一格在世界里的大小（k=1）
  let SPR = null;
  function buildAtlas(rnd) {
    const V = VREP.length, cols = ND * NF, W = cols * TW, H = V * TH;
    const rt = new THREE.WebGLRenderTarget(W, H, {depthBuffer: true});
    const sc = new THREE.Scene(); sc.add(new THREE.HemisphereLight(0xffffff, 0xb8a888, 2.2)); const sun = new THREE.DirectionalLight(0xffffff, 1.0); sun.position.set(-700, 900, -500); sc.add(sun);
    const TL = 36 * Math.PI / 180, up = new THREE.Vector3(0, Math.cos(TL), -Math.sin(TL)), DIRV = new THREE.Vector3(0, Math.sin(TL), Math.cos(TL));
    const O = new THREE.Vector3(0, -20000, 0), cam = new THREE.OrthographicCamera(0, W / TW * SW, H / TH * SH, 0, 1, 400);
    cam.position.copy(O).addScaledVector(DIRV, 200); cam.up.copy(up); cam.lookAt(O);
    // 相机放在 O 处，左下角对着 O：第 (i,j) 格的脚在 O + 右×(i+.5)×SW + 上×(j+FOOT)×SH
    const shoot = mask => {
      for (const k in cnt) cnt[k] = 0;
      VREP.forEach((v, j) => { for (let dI = 0; dI < ND; dI++) for (let f = 0; f < NF; f++) {
        const i = dI * NF + f, Pp = blank(); if (f < NF - 1 && v.gait) walk(Pp, v.gait, f / (NF - 1) * Math.PI * 2); else stay(Pp, v.pose, 3.1, 1);
        carry(Pp, v.load);
        const q = O.clone().addScaledVector(new THREE.Vector3(1, 0, 0), (i + .5) * SW).addScaledVector(up, (j + FOOT) * SH);
        const o = v.o, f0 = {x: q.x, y: q.y, z: q.z, dir: dI * Math.PI / 4, b: o.b, k: 1, col: CLOTH, skin: o.skin, leg: o.leg.equals(o.col) ? CLOTH : o.leg, long: o.long, veil: o.veil, hat: o.hat, role: o.role, sash: o.sash};
        drawFull(f0, Pp, v.load) } });
      const keep = [];
    for (const k in parts) { const m = parts[k]; m.count = cnt[k]; m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; keep.push([m, m.parent, m.material]); sc.add(m);
        if (mask) m.material = BASIC }
      rnd.setRenderTarget(rt); rnd.setClearColor(0x000000, 0); rnd.clear(); rnd.render(sc, cam); rnd.setRenderTarget(null);
      for (const [m, par, mat] of keep) { par.add(m); m.material = mat }
      const buf = new Uint8Array(W * H * 4); rnd.readRenderTargetPixels(rt, 0, 0, W, H, buf); return buf };
    const BASIC = new THREE.MeshBasicMaterial({color: '#ffffff', side: THREE.DoubleSide});
    const oldCC = rnd.getClearColor(new THREE.Color()), oldA = rnd.getClearAlpha();
    const col = shoot(false); MASK = true; const msk = shoot(true); MASK = false;
    rnd.setClearColor(oldCC, oldA); rt.dispose();
    const out = new Uint8Array(W * H * 4), A = i => col[i * 4 + 3] > 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = y * W + x;
      if (!A(i)) {                                                           // 外面一圈墨：画在剪影外面，不吃掉里面的衣色
        const nb = (x % TW > 0 && A(i - 1)) || (x % TW < TW - 1 && A(i + 1)) || (y % TH > 0 && A(i - W)) || (y % TH < TH - 1 && A(i + W));
        if (nb) { out[i * 4] = 60; out[i * 4 + 1] = 46; out[i * 4 + 2] = 34; out[i * 4 + 3] = 200 } continue }
      out[i * 4] = col[i * 4]; out[i * 4 + 1] = col[i * 4 + 1]; out[i * 4 + 2] = col[i * 4 + 2]; out[i * 4 + 3] = msk[i * 4] > 128 ? 128 : 255 }
    const tex = new THREE.DataTexture(out, W, H, THREE.RGBAFormat); tex.magFilter = tex.minFilter = THREE.NearestFilter; tex.generateMipmaps = false; tex.needsUpdate = true;
    const mat = new THREE.ShaderMaterial({uniforms: {map: {value: tex}, ink: {value: 1}, grid: {value: new THREE.Vector2(cols, V)}, up: {value: up}, size: {value: new THREE.Vector2(SW, SH)}, foot: {value: FOOT}},
      vertexShader: `attribute float aFrame; uniform vec2 grid, size; uniform vec3 up; uniform float foot; varying vec2 vUv; varying vec3 vCol;
        void main(){ vec3 c = (instanceMatrix * vec4(0., 0., 0., 1.)).xyz; float s = length(instanceMatrix[0].xyz);
          vec3 p = c + vec3(1., 0., 0.) * (uv.x - .5) * size.x * s + up * (uv.y - foot) * size.y * s;
          float fi = mod(aFrame, grid.x), fj = floor(aFrame / grid.x); vUv = (vec2(fi, fj) + uv) / grid; vCol = instanceColor;
          gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.); }`,
      fragmentShader: `uniform sampler2D map; uniform float ink; varying vec2 vUv; varying vec3 vCol;
        void main(){ vec4 t = texture2D(map, vUv); if (t.a < .1) discard; if (t.a > .7 && t.a < .9) { if (ink < .5) discard; gl_FragColor = vec4(t.rgb, 0.); return; }
          vec3 g = vec3(1. / 2.2); gl_FragColor = vec4(t.a < .7 ? pow(vCol, g) * (.55 + .6 * t.r) : pow(t.rgb, g) * .9, 0.); }`   /* 小人只有几个像素：按衣服的本色画（不走线性压暗），明暗只留一点 */   /* alpha 0：告诉后期这里是小人，别按颜色分界描墨 */});
    const mesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).translate(.5, .5, 0), mat, Math.max(64, N));
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); mesh.frustumCulled = false; mesh.count = 0; mesh.setColorAt(0, new THREE.Color());
    const fa = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(64, N)), 1); fa.setUsage(THREE.DynamicDrawUsage); mesh.geometry.setAttribute('aFrame', fa);
    scene.add(mesh); parts.spr = mesh; cnt.spr = 0;
    SPR = {mesh, fa, cols, V, W, H, out, col}; return SPR;
  }
  function drawSprite(o, k, frame) {
    const n = cnt.spr++, dI = ((Math.round(o.dir / (Math.PI / 4)) % ND) + ND) % ND;
    Vp.set(o.x, o.y, o.z); Qn.identity(); const s = o.k * k; Vs.set(s, s, s); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
    SPR.mesh.setMatrixAt(n, Mroot); const w = Math.min(1, (k - 1) / 1.5);
    SPR.mesh.setColorAt(n, w > 0 ? CT.copy(o.col).lerp(o.act, .35 + .65 * w) : o.col);
    SPR.fa.array[n] = frame.v * SPR.cols + dI * NF + frame.f;
  }

  // ---------- 时间 → 位置（纯函数） ----------
  const pathAt = (r, s) => { const P = r.path, C = r.cum; let lo = 0, hi = C.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (C[m] <= s) lo = m; else hi = m }
    const l = C[hi] - C[lo] || 1, u = Math.min(1, Math.max(0, (s - C[lo]) / l)); return [P[lo][0] + (P[hi][0] - P[lo][0]) * u, P[lo][1] + (P[hi][1] - P[lo][1]) * u, Math.atan2(P[hi][0] - P[lo][0], P[hi][1] - P[lo][1])] };
  const DENS = [[0, .15], [.12, .5], [.3, .95], [.5, 1], [.7, .85], [.85, .45], [1, .15]];   // 一天里街上有几成人
  const dens = f => { for (let i = 1; i < DENS.length; i++) if (f <= DENS[i][0]) { const a = DENS[i - 1], b = DENS[i], u = (f - a[0]) / (b[0] - a[0]); return a[1] + (b[1] - a[1]) * u } return .15 };
  const ground = (x, z) => isLand(x, z) ? elevPx(x, z) + 1.5 : 1.6;
  const frus = new THREE.Frustum(), PV = new THREE.Matrix4(), SPH = new THREE.Sphere(new THREE.Vector3(), 2);
  const stat = {active: 0, full: 0, far: 0, ms: 0, gest: 0, bow: 0};

  let frame = 0, NEARP = [];
  function tick(t, view) {
    const t0 = performance.now(); frame++;
    for (const k in cnt) cnt[k] = 0;
    const cam = view.cam; PV.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); frus.setFromProjectionMatrix(PV);
    const cx = cam.position.x, cz = cam.position.z, fullR2 = (view.fullM / MPP) ** 2, D = dens((t % T) / T);
    const mer = getMerchant && getMerchant();
    let act = 0, nf = 0, ng = 0, nbow = 0, ngr = 0; const NEARN = []; const gestR2 = (25 / MPP) ** 2, boost = view.farBoost || 1;
    for (const o of P) {
      if (o.dens > D) continue;
      const r = o.r; let c = (t + o.off) % o.cyc, x, z, d, a, load = null, g = null, s = 0;
      if (c < o.tOut) { s = Math.max(0, c * o.so * M - o.lag); [x, z, d] = pathAt(r, s); g = o.go; load = o.loadOut }
      else if ((c -= o.tOut) < o.pauseFar) { [x, z, d] = pathAt(r, r.L); a = o.farPose; load = o.loadOut; d += Math.PI }
      else if ((c -= o.pauseFar) < o.tBack) { s = Math.max(0, c * o.sb * M - o.lag); [x, z, d] = pathAt(r, r.L - s); d += Math.PI; g = o.gb; load = o.loadBack }
      else continue;                                                        // 在家里
      const ld = o.lead;
      if (g) { const side = (ld ? (ld.go.center ? 0 : (ld.i & 1 ? .8 : -.8)) + o.sideX : g.center ? 0 : (o.i & 1 ? .8 : -.8)) * M; x += Math.cos(d) * side; z -= Math.sin(d) * side }
      else if (o.mate || ld) { const k = ld ? o.sideX * 1.4 : (o.mate.i < o.i ? .5 : -.5); x += Math.cos(d) * k * M; z -= Math.sin(d) * k * M; if (o.mate) d += k > 0 ? -Math.PI / 2 : Math.PI / 2 }   // 约好的两人在喷泉边面对面说话   // 靠右/靠左走，有身份的走街心
      let bow = 0;
      if (mer && mer.vis && g && !g.center) { const dx = x - mer.x, dz = z - mer.z, px = Math.hypot(dx, dz) || 1e-3, dm = px * MPP;
        if (dm < 3.2) { bow = Math.min(1, (3.2 - dm) / 1.2); x += dx / px * bow * .9 * M; z += dz / px * bow * .9 * M } }   // 商人走过：让到一边、躬身
      o.x = x; o.z = z; o.dir = d; o.y = ground(x, z); act++;
      o.seg = g ? (g === o.go ? 'out' : 'back') : 'far'; o.load = load; o.bowing = bow > .2;   // 给信息层读：此刻在路上的哪一段
      SPH.center.set(x, o.y, z); SPH.radius = 2 * M; if (!frus.intersectsSphere(SPH)) continue;
      o.seen = frame;
      const dx = x - cx, dz = z - cz;
      if (view.full && dx * dx + dz * dz < fullR2 && nf < view.maxFull) {
        nf++; NEARN.push(o); const Pp = blank();
        if (g) walk(Pp, g, o.ph0 + (s / M) / g.stride * Math.PI); else stay(Pp, a, t + o.i * 1.7, o.k);
        carry(Pp, load);
        if (dx * dx + dz * dz < gestR2) {                                    // 叠加手势只给镜头 25 米内的人：远一点本来也看不清
          ng++; if (bow) { OVER.bow(Pp, bow); nbow++ }
          if (g === o.go && o.role === 'laborer') OVER.wipe(Pp, env(c, .2, 2.5));               // 出门前抹一把汗
          if (o.rel && !bow) for (const q of NEARP) { const l = o.rel.get(q); if (!l || q === o.lead || q.lead === o || q.lead === o.lead && o.lead || q === o.mate) continue;   // 路上碰见有关系的人
            const ex = q.x - x, ez = q.z - z, dm = Math.hypot(ex, ez) * MPP; if (dm > 6) continue;
            const e = Math.min(1, (6 - dm) / 2), ang = Math.atan2(ex, ez) - d, yaw = Math.atan2(Math.sin(ang), Math.cos(ang));
            if (l.includes('不来往') || l === '债主') OVER.avert(Pp, e, yaw); else OVER.greet(Pp, e, yaw);
            o.met = [q, l, frame]; ngr++; break }
        }
        drawFull(o, Pp, load);
      } else if (SPR && view.sprite) {                                      // 中景/远景：帧图小人 + 缩远时的色带
        const v = g ? (g === o.go ? o.vOut : o.vBack) : o.vFar;
        const f = g ? Math.floor((((o.ph0 + (s / M) / g.stride * Math.PI) / (Math.PI * 2)) % 1 + 1) % 1 * (NF - 1)) : NF - 1;
        drawSprite(o, boost, {v, f});
        if (boost > 1.3) { const walking = !!g, sc = M * boost; Vp.set(o.x, o.y + .4, o.z); E3.set(0, o.dir, 0); Qn.setFromEuler(E3);
          Vs.set(walking ? 2.4 * sc : 4.5 * sc, 1, walking ? 8 * sc : 4.5 * sc); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1); put('trail', Mroot, o.act) }
      } else drawFar(o, load, boost);
    }
    NEARP = NEARN; stat.greet = ngr;
    if (SPR) { SPR.fa.needsUpdate = true; SPR.mesh.material.uniforms.ink.value = view.spriteInk ? 1 : 0 }   // 小人默认不描墨：太小，描了就只剩一团黑
    for (const k in parts) { const m = parts[k]; m.count = cnt[k]; m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true }
    stat.active = act; stat.full = nf; stat.far = cnt.far + (cnt.spr || 0); stat.spr = cnt.spr || 0; stat.ms = performance.now() - t0; stat.gest = ng; stat.bow = nbow; stat.trail = cnt.trail; stat.k = boost;
    return stat;
  }
  // 信息层：指到才算，不指不花钱。只在这一帧视野里的人当中找
  const ROLE = {woman: '妇人', laborer: '搬运工', trader: '商贩', rich: '富商', old: '老人', child: '孩子', commoner: '街坊'};
  const DOING = {
    water: {out: '拿着空罐去喷泉打水', far: '在喷泉边排队等水', back: '顶着满罐回家'},
    market: {out: '去市场', far: '在市场上做买卖', back: '抱着货回铺子'},
    haul: {out: '去栈桥扛货', far: '在栈桥边歇口气', back: '扛着麻袋往回走'},
    forum: {out: '往广场去', far: '在广场上谈事', back: '从广场回铺子'},
    errand: {out: '出门办事', far: '在市场转转', back: '办完事回家'},
  };
  const FROM = {homes: '住在民居', shops: '开铺子的人家', market: '市场边的人家', dock: '码头上的人家', horrea: '粮仓边的人家'};
  const NOW = {
    water: ['拿着空罐去喷泉打水', '在喷泉边排队等水', '顶着满罐回家'], visit: ['回娘家看看，去%家', '在娘家门口说话', '从娘家回来'],
    haul: ['去%家的码头扛活', '在%家码头上卸货', '扛着麻袋往回走'], debt: ['去%家，想求他宽限几天', '在%家门口赔着笑说话', '从债主家出来'],
  };
  function describe(o) {
    if (!o.F) { const d = DOING[o.r.why] || DOING.errand; let s = (o.role === 'child' ? '跟着家里人' : '') + d[o.seg];
      if (o.role === 'child' && o.seg !== 'out') s = d[o.seg]; if (o.bowing) s = '给商人让路'; return {who: ROLE[o.role] || '街坊', what: s, from: FROM[o.r.fn] || ''} }
    const F = o.F, si = {out: 0, far: 1, back: 2}[o.seg] || 0, L = o.lead || o, why = L.F[7], tg = L.F[8];
    let s = NOW[why] ? NOW[why][si].replace('%', tg) : (DOING[why] || DOING.errand)[o.seg];
    if (o.lead) s = '跟着' + (o.rel.get(o.lead) || '家里人') + (o.seg === 'far' ? '，在一边等着' : s.replace(/^(拿着空罐|顶着满罐|扛着麻袋)/, ''));
    else if (o.mate && why === 'water') s = o.seg === 'far' ? '在喷泉边跟' + (o.rel.get(o.mate) || '邻居') + o.mate.F[5].split('，')[0] + '说话' : o.seg === 'out' ? '约了' + (o.rel.get(o.mate) || '邻居') + o.mate.F[5].split('，')[0] + '一道去打水' : s;
    if (o.met && frame - o.met[2] < 90) s = (o.met[1].includes('不来往') ? '碰见' + o.met[1].replace('不来往的', '') + o.met[0].F[5].split('，')[0] + '，把头扭开了' : o.met[1] === '债主' ? '碰见债主，低着头快步走过' : '碰见' + o.met[1].replace('娘家·', '娘家') + o.met[0].F[5].split('，')[0] + '，打了个招呼');
    if (o.bowing) s = '给商人让路';
    const ties = o.ties.filter(t => t[0].seen === frame).slice(0, 6);
    return {who: F[5], what: s, from: F[6], ties};
  }
  const pickable = () => P.filter(o => o.seen === frame);
  return {MPP, setInk: on => { NOINK.value = on ? 0 : 1 }, get inkOn() { return NOINK.value < .5 }, tick, stat, people: P, pickable, describe, parts, buildAtlas, atlasInfo: () => SPR && {V: SPR.V, W: SPR.W, H: SPR.H}, atlas: () => SPR};
}
