/* 人群渲染（压力试作，2026-10-19）。人一多，不能再一人一套 mesh：
   - 每个身体部件一张 InstancedMesh（躯干、头、袍、短裙、大腿×2、小腿×2、上臂×2、前臂×2、各种负重），
     不管多少人，绘制调用数都固定（约 20 次）。每帧在 CPU 上按姿势通道算每个部件的矩阵。
   - 三档：近（关节人，跟主角同一套姿势引擎）→ 远（一根着色小柱 + 负重的颜色块）→ 视野外不算。
   - 每个人的位置是时间的纯函数（路线 × 速度 × 出发时刻），不存状态：看不见的人一点不花钱。
   - 别人对你的反应：商人走过时，身边的人躬身让到一边。
   ——Hark（CS线） */
import {hash, rng, pickTemper, gaitOf, blank, walk, stay, carry, OVER, env} from './pose.js';

const PAL = {   // 衣色：染过的贵、素的便宜。都是按意图给的范围，人人从里面抽
  rich: ['#5a2f4a', '#3f3a6a', '#7a2a2a', '#2f4a3a'], trader: ['#4f6a3a', '#7a5a2a', '#5a6a7a', '#8a6a3a'],
  woman: ['#a85a3c', '#6a4a7a', '#3c6a8a', '#9a7a3a', '#8a3c3c'], laborer: ['#6e5038', '#7a6a50', '#5a4a38'],
  commoner: ['#b8a788', '#a89a7a', '#c9b48a', '#9a8a6a', '#8a7a5a'], child: ['#c9b48a', '#b8a080', '#d0c09a'],
  old: ['#9a8e74', '#8a826a', '#a89a80'],
};
const SKIN = ['#c89a74', '#b98c6a', '#d0a07a', '#a87a58'];
const LOADC = {sack: '#d2c3a0', jar_full: '#b5683e', jar_empty: '#b5683e', crate: '#8a6a48', basket: '#a8864e'};

export function initCrowd(E) {
  const {THREE, scene, elevPx, isLand, MPP, EX, data, T, getMerchant} = E;
  const M = 1 / MPP, N = E.n;
  const R = data.routes.map(r => { const P = r.path; let L = 0; const cum = [0]; for (let i = 1; i < P.length; i++) { L += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]); cum.push(L) } return {...r, L, cum} });

  // ---------- 铺人：第 i 个人分到第 i % 路线数 条路；意图来自路线（底账推出），长相和步态由种子抽 ----------
  const P = [], lastOn = new Map();
  for (let i = 0; i < N; i++) {
    const ri = i % R.length, r = R[ri], seed = hash(r.h + ':' + i), U = rng(seed);
    let role = r.intent;
    if (role === 'commoner') { const x = U(); role = x < .16 ? 'child' : x < .3 ? 'old' : x < .65 ? 'woman' : 'commoner' }
    const out = {child: 'child_walk', old: 'old', woman: 'woman', rich: 'rich', trader: 'trader', laborer: 'porter', commoner: 'walker'}[role];
    const back = {woman: r.why === 'water' ? 'woman_full' : 'woman', laborer: 'porter_load', trader: 'trader_load', old: 'old', child: 'child_walk', rich: 'rich', commoner: 'walker'}[role];
    const loadOut = r.why === 'water' ? 'jar_empty' : null;
    const loadBack = r.why === 'water' ? 'jar_full' : role === 'laborer' ? 'sack' : role === 'trader' ? (U() < .6 ? 'crate' : 'basket') : r.why === 'errand' && U() < .4 ? 'basket' : null;
    if (r.why === 'water' && role !== 'woman') role = 'woman';
    const h = role === 'child' ? 1.0 + U() * .3 : role === 'woman' ? 1.5 + U() * .14 : role === 'old' ? 1.55 + U() * .14 : 1.6 + U() * .18;
    const b = role === 'laborer' ? 1.1 + U() * .15 : role === 'rich' ? 1.05 + U() * .15 : role === 'child' ? .78 + U() * .08 : .88 + U() * .16;
    const nb = lastOn.get(ri) || [];
    const u = pickTemper(seed, [out, back], {h}, nb.slice(-4)); nb.push(u); lastOn.set(ri, nb);   // 同一条路上的人尽量不像
    const go = gaitOf(out, u), gb = gaitOf(back, u);
    const pal = PAL[role] || PAL.commoner, col = pal[Math.floor(U() * pal.length)];
    const long = role === 'rich' || role === 'woman' || (role === 'old' && U() < .4);
    const pauseFar = r.why === 'water' ? 18 + U() * 20 : r.why === 'market' ? 40 + U() * 60 : r.why === 'forum' ? 80 + U() * 80 : r.why === 'haul' ? 6 + U() * 8 : 20 + U() * 30;
    const pauseHome = 30 + U() * 120;
    const L = r.L / M, tOut = L / go.speed, tBack = L / gb.speed, cyc = tOut + pauseFar + tBack + pauseHome;
    P.push({i, r, role, go, gb, h, b, k: h / 1.7, col: new THREE.Color(col), skin: new THREE.Color(SKIN[Math.floor(U() * SKIN.length)]),
      leg: new THREE.Color(long ? col : role === 'laborer' || role === 'child' ? SKIN[0] : '#7a6a50'), long, veil: role === 'woman', hat: role === 'rich' && U() < .5,
      loadOut, loadBack, pauseFar, pauseHome, tOut, tBack, cyc, off: U() * cyc, dens: U(), ph0: U() * 6.28,
      farPose: r.why === 'water' ? 'queue' : r.why === 'haul' ? 'rest' : r.why === 'market' ? 'sell' : r.why === 'forum' ? 'talk' : 'stand',
      x: 0, z: 0, dir: 0, vis: false});
  }

  // ---------- 部件：每样一张 InstancedMesh。几何按 k=1、b=1 建，个子和胖瘦放在根矩阵的缩放里 ----------
  const MAT = new THREE.MeshLambertMaterial({color: '#ffffff'});
  const cyl = (r0, r1, h, seg = 6) => new THREE.CylinderGeometry(r1, r0, h, seg).translate(0, -h / 2, 0);
  const parts = {};
  const mk = (name, geo, cap) => { const m = new THREE.InstancedMesh(geo, MAT, cap); m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); m.count = 0; m.frustumCulled = false;
    m.setColorAt(0, new THREE.Color()); scene.add(m); parts[name] = m; return m };
  const capN = Math.max(64, N);
  mk('chest', new THREE.CylinderGeometry(.17, .15, .55, 7).translate(0, .3, 0), capN);
  mk('skirt', new THREE.CylinderGeometry(.16, .23, .3, 7).translate(0, -.1, 0), capN);
  mk('robe', new THREE.CylinderGeometry(.17, .3, .82, 8).translate(0, -.41 + .05, 0), capN);
  mk('head', new THREE.SphereGeometry(.11, 7, 5).translate(0, .14, 0), capN);
  mk('cap', new THREE.SphereGeometry(.115, 7, 4, 0, Math.PI * 2, 0, Math.PI * .5).translate(0, .15, -.01), capN);
  mk('veil', new THREE.CylinderGeometry(.12, .2, .32, 7, 1, true).translate(0, .02, -.02), capN); parts.veil.material = MAT.clone(); parts.veil.material.side = THREE.DoubleSide;
  mk('hat', new THREE.CylinderGeometry(.1, .12, .1, 7).translate(0, .27, 0), capN);
  for (const s of ['L', 'R']) { mk('th' + s, cyl(.075, .06, .46), capN); mk('sh' + s, cyl(.055, .045, .44), capN); mk('ft' + s, new THREE.BoxGeometry(.09, .06, .22).translate(0, -.03, .05), capN);
    mk('up' + s, cyl(.05, .045, .3), capN); mk('lo' + s, cyl(.042, .035, .28), capN) }
  const jarPts = [[0, 0], [.07, .02], [.13, .12], [.14, .26], [.09, .38], [.05, .44], [.07, .5], [0, .5]].map(q => new THREE.Vector2(q[0], q[1]));
  mk('sack', new THREE.SphereGeometry(.3, 7, 5).scale(1.25, .7, .9), capN);
  mk('jar', new THREE.LatheGeometry(jarPts, 7), capN);
  mk('crate', new THREE.BoxGeometry(.42, .3, .32), capN);
  mk('far', new THREE.CylinderGeometry(.2, .24, 1.6, 5).translate(0, .8, 0), capN);           // 远处：一根着色小柱
  mk('farLoad', new THREE.BoxGeometry(.5, .4, .5).translate(0, 1.75, 0), capN);              // 远处：负重的色块（顶在头上那一块）

  // ---------- 矩阵链 ----------
  const m4 = () => new THREE.Matrix4();
  const Mroot = m4(), Mhip = m4(), Mtor = m4(), Mneck = m4(), Mj = m4(), Mk = m4(), Mt = m4(), Mtmp = m4();
  const E3 = new THREE.Euler(), Qn = new THREE.Quaternion(), Vp = new THREE.Vector3(), Vs = new THREE.Vector3(1, 1, 1);
  function local(out, x, y, z, rx, ry, rz) { E3.set(rx, ry, rz, 'XYZ'); Qn.setFromEuler(E3); Vp.set(x, y, z); return out.compose(Vp, Qn, Vs) }
  const cnt = {}; for (const k in parts) cnt[k] = 0;
  function put(name, mat, col) { const m = parts[name], c = cnt[name]++; m.setMatrixAt(c, mat); if (col) m.setColorAt(c, col) }
  const C_INK = new THREE.Color('#3a2e22'), C_VEIL = new THREE.Color('#e8dfcb'), C_HAIR = new THREE.Color('#2a1e16'), C_GOLD = new THREE.Color('#c9a34a'), C_GREY = new THREE.Color('#d9d4c8');
  const LC = {}; for (const k in LOADC) LC[k] = new THREE.Color(LOADC[k]);

  function drawFull(o, Pp, load) {
    Vp.set(o.x, o.y, o.z); E3.set(0, o.dir, 0); Qn.setFromEuler(E3); Vs.set(M * o.b, M * EX * o.k, M * o.b); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
    Mhip.multiplyMatrices(Mroot, local(Mt, 0, .92 * (1 + Pp.bob) + Pp.lift / o.k, 0, 0, 0, Pp.hip));
    Mtor.multiplyMatrices(Mhip, local(Mt, 0, 0, 0, Pp.stoop, Pp.twist, Pp.side));
    put('chest', Mtor, o.col);
    if (o.long) { Mtmp.multiplyMatrices(Mhip, local(Mt, 0, 0, 0, (Pp.legs[0][0] - Pp.legs[1][0]) * .08, 0, 0)); put('robe', Mtmp, o.col) } else put('skirt', Mtor, o.col);
    Mneck.multiplyMatrices(Mtor, local(Mt, 0, .6, 0, Pp.neck, Pp.headYaw, 0));
    put('head', Mneck, o.skin); put(o.veil ? 'veil' : 'cap', Mneck, o.veil ? C_VEIL : o.role === 'old' ? C_GREY : C_HAIR);
    if (o.hat) put('hat', Mneck, C_GOLD);
    for (let i = 0; i < 2; i++) {
      const s = i ? 1 : -1, S = i ? 'R' : 'L';
      Mj.multiplyMatrices(Mhip, local(Mt, s * .1, 0, 0, -Pp.legs[i][0], 0, 0)); put('th' + S, Mj, o.leg);
      Mk.multiplyMatrices(Mj, local(Mt, 0, -.46, 0, Pp.legs[i][1], 0, 0)); put('sh' + S, Mk, o.long ? o.col : o.skin);
      Mtmp.multiplyMatrices(Mk, local(Mt, 0, -.44, 0, 0, 0, 0)); put('ft' + S, Mtmp, C_INK);
      const A = Pp.arms[i];
      Mj.multiplyMatrices(Mtor, local(Mt, s * .22, .56, 0, -A[0], 0, (i ? -1 : 1) * (.08 + A[2]))); put('up' + S, Mj, o.role === 'laborer' ? o.skin : o.col);
      Mk.multiplyMatrices(Mj, local(Mt, 0, -.3, 0, -A[1], 0, 0)); put('lo' + S, Mk, o.skin);
      if (i === 0 && load === 'basket') { Mtmp.multiplyMatrices(Mk, local(Mt, 0, -.3, 0, 0, 0, 0)); Mtmp.scale(Vp.set(.6, .6, .6)); put('crate', Mtmp, LC.basket) }
    }
    if (load === 'sack') { Mtmp.multiplyMatrices(Mtor, local(Mt, 0, .66, -.16, 0, 0, 0)); put('sack', Mtmp, LC.sack) }
    else if (load === 'crate') { Mtmp.multiplyMatrices(Mtor, local(Mt, 0, .28, .3, 0, 0, 0)); put('crate', Mtmp, LC.crate) }
    else if (load === 'jar_full') { Mtmp.multiplyMatrices(Mneck, local(Mt, 0, .28, -.02, 0, 0, 0)); put('jar', Mtmp, LC.jar_full) }
    else if (load === 'jar_empty') { Mtmp.multiplyMatrices(Mtor, local(Mt, .2, .05, .08, 0, 0, -.5)); put('jar', Mtmp, LC.jar_empty) }
  }
  function drawFar(o, load) {
    Vp.set(o.x, o.y, o.z); E3.set(0, o.dir, 0); Qn.setFromEuler(E3); Vs.set(M * o.b, M * EX * o.k, M * o.b); Mroot.compose(Vp, Qn, Vs); Vs.set(1, 1, 1);
    put('far', Mroot, o.col); if (load) put('farLoad', Mroot, LC[load]);
  }

  // ---------- 时间 → 位置（纯函数） ----------
  const pathAt = (r, s) => { const P = r.path, C = r.cum; let lo = 0, hi = C.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (C[m] <= s) lo = m; else hi = m }
    const l = C[hi] - C[lo] || 1, u = Math.min(1, Math.max(0, (s - C[lo]) / l)); return [P[lo][0] + (P[hi][0] - P[lo][0]) * u, P[lo][1] + (P[hi][1] - P[lo][1]) * u, Math.atan2(P[hi][0] - P[lo][0], P[hi][1] - P[lo][1])] };
  const DENS = [[0, .15], [.12, .5], [.3, .95], [.5, 1], [.7, .85], [.85, .45], [1, .15]];   // 一天里街上有几成人
  const dens = f => { for (let i = 1; i < DENS.length; i++) if (f <= DENS[i][0]) { const a = DENS[i - 1], b = DENS[i], u = (f - a[0]) / (b[0] - a[0]); return a[1] + (b[1] - a[1]) * u } return .15 };
  const ground = (x, z) => isLand(x, z) ? elevPx(x, z) + 1.5 : 1.6;
  const frus = new THREE.Frustum(), PV = new THREE.Matrix4(), SPH = new THREE.Sphere(new THREE.Vector3(), 2);
  const stat = {active: 0, full: 0, far: 0, ms: 0};

  function tick(t, view) {
    const t0 = performance.now();
    for (const k in cnt) cnt[k] = 0;
    const cam = view.cam; PV.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); frus.setFromProjectionMatrix(PV);
    const cx = cam.position.x, cz = cam.position.z, fullR2 = (view.fullM / MPP) ** 2, D = dens((t % T) / T);
    const mer = getMerchant && getMerchant();
    let act = 0, nf = 0;
    for (const o of P) {
      if (o.dens > D) continue;
      const r = o.r; let c = (t + o.off) % o.cyc, x, z, d, a, load = null, g = null, s = 0;
      if (c < o.tOut) { s = c * o.go.speed * M; [x, z, d] = pathAt(r, s); g = o.go; load = o.loadOut }
      else if ((c -= o.tOut) < o.pauseFar) { [x, z, d] = pathAt(r, r.L); a = o.farPose; load = o.loadOut; d += Math.PI }
      else if ((c -= o.pauseFar) < o.tBack) { s = c * o.gb.speed * M; [x, z, d] = pathAt(r, r.L - s); d += Math.PI; g = o.gb; load = o.loadBack }
      else continue;                                                        // 在家里
      if (g) { const side = (g.center ? 0 : (o.i & 1 ? .8 : -.8)) * M; x += Math.cos(d) * side; z -= Math.sin(d) * side }   // 靠右/靠左走，有身份的走街心
      let bow = 0;
      if (mer && mer.vis && g && !g.center) { const dx = x - mer.x, dz = z - mer.z, px = Math.hypot(dx, dz) || 1e-3, dm = px * MPP;
        if (dm < 3.2) { bow = Math.min(1, (3.2 - dm) / 1.2); x += dx / px * bow * .9 * M; z += dz / px * bow * .9 * M } }   // 商人走过：让到一边、躬身
      o.x = x; o.z = z; o.dir = d; o.y = ground(x, z); act++;
      SPH.center.set(x, o.y, z); SPH.radius = 2 * M; if (!frus.intersectsSphere(SPH)) continue;
      const dx = x - cx, dz = z - cz;
      if (view.full && dx * dx + dz * dz < fullR2 && nf < view.maxFull) {
        nf++; const Pp = blank();
        if (g) walk(Pp, g, o.ph0 + (s / M) / g.stride * Math.PI); else stay(Pp, a, t + o.i * 1.7, o.k);
        carry(Pp, load);
        if (bow) OVER.bow(Pp, bow);
        if (g === o.go && o.role === 'laborer') OVER.wipe(Pp, env(c, .2, 2.5));               // 出门前抹一把汗
        drawFull(o, Pp, load);
      } else drawFar(o, load);
    }
    for (const k in parts) { const m = parts[k]; m.count = cnt[k]; m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true }
    stat.active = act; stat.full = nf; stat.far = cnt.far; stat.ms = performance.now() - t0;
    return stat;
  }
  return {tick, stat, people: P};
}
