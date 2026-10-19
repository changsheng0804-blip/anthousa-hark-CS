/* 居民节点渲染（试作，2026-10-18）——只照 people.json 演，不自己编。
   一个人 = 一副关节骨架（髋、躯干、头、两臂两节、两腿两节）+ 按底账穿的衣服和手里的东西。
   怎么走（步速、步长、前倾、起伏、摆臂、跛）、扛什么、几点去哪、跟着谁，全来自 people.json；这里只把这些数变成动作。
   页面上不写一个字：认不认得出他是谁，就是验收。——Hark（CS线） */
import {hash, pickTemper, gaitOf, blank, walk, stay, carry, OVER, env} from './pose.js';
export function initPeople(E) {
  const {THREE, scene, elevPx, isLand, MPP, EX, data} = E;
  const M = 1 / MPP;                       // 1 米 = 多少像素（水平）
  const V = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);
  const mat = c => new THREE.MeshLambertMaterial({color: new THREE.Color(c)});
  const SKIN = mat('#c89a74'), SKIN_OLD = mat('#b98c6a'), INK = mat('#3a2e22');
  const cyl = (r0, r1, h, seg = 7) => new THREE.CylinderGeometry(r1, r0, h, seg).translate(0, -h / 2, 0); // 从关节往下长
  const people = [], byId = {};

  function limb(parent, r0, r1, len, m, x, y, z) {
    const j = new THREE.Group(); j.position.set(x, y, z); parent.add(j);
    const mesh = new THREE.Mesh(cyl(r0, r1, len), m); j.add(mesh); j.userData.len = len; return j;
  }
  function build(p) {
    const c = p.cast, h = c.h, b = c.build, k = h / 1.7;
    const cloth = mat(c.color), hair = mat(c.hair || '#2a1e16'), skin = c.beard && p.id === 'f' ? SKIN_OLD : SKIN;
    const root = new THREE.Group(); root.scale.set(M, M * EX, M);
    const hip = new THREE.Group(); hip.position.y = .92 * k; root.add(hip);
    // 腿：大腿 + 小腿；长衣的人腿藏在袍子里，但仍然在动（袍摆跟着摆）
    const legM = c.cloth === 'long' ? cloth : (c.bare ? skin : mat('#7a6a50'));
    const L = [], A = [];
    for (const s of [-1, 1]) {
      const th = limb(hip, .075 * b, .06 * b, .46 * k, legM, s * .1 * b, 0, 0);
      const sh = limb(th, .055 * b, .045 * b, .44 * k, c.cloth === 'long' ? cloth : skin, 0, -.46 * k, 0);
      const ft = new THREE.Mesh(new THREE.BoxGeometry(.09 * b, .06, .22 * k).translate(0, -.03, .05), INK); ft.position.y = -.44 * k; sh.add(ft);
      L.push({th, sh});
    }
    // 躯干：从髋往上，前倾角加在这里
    const torso = new THREE.Group(); hip.add(torso);
    const chest = new THREE.Mesh(new THREE.CylinderGeometry(.17 * b, .15 * b, .55 * k, 8).translate(0, .3 * k, 0), cloth); torso.add(chest);
    if (c.cloth === 'short') { const sk = new THREE.Mesh(new THREE.CylinderGeometry(.16 * b, .23 * b, .3 * k, 8).translate(0, -.1 * k, 0), cloth); torso.add(sk); }
    let robe = null;
    if (c.cloth === 'long') { robe = new THREE.Mesh(new THREE.CylinderGeometry(.17 * b, .3 * b, .82 * k, 9).translate(0, -.41 * k, 0), cloth); robe.position.y = .05 * k; hip.add(robe);
      if (c.trim) { const t = new THREE.Mesh(new THREE.CylinderGeometry(.305 * b, .305 * b, .05, 9), mat(c.trim)); t.position.y = -.8 * k; robe.add(t); } }
    const neck = new THREE.Group(); neck.position.y = .6 * k; torso.add(neck);
    const head = new THREE.Mesh(new THREE.SphereGeometry(.11 * k, 9, 7).translate(0, .14 * k, 0), skin); neck.add(head);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(.115 * k, 9, 5, 0, Math.PI * 2, 0, Math.PI * .5).translate(0, .15 * k, -.01), c.veil ? mat(c.veil) : hair); neck.add(cap);
    if (c.veil) { const v = new THREE.Mesh(new THREE.CylinderGeometry(.12 * k, .2 * k, .32 * k, 8, 1, true).translate(0, .02 * k, -.02), mat(c.veil)); v.material.side = THREE.DoubleSide; neck.add(v); }
    if (c.beard) { const bd = new THREE.Mesh(new THREE.SphereGeometry(.07 * k, 7, 5).translate(0, .06 * k, .07 * k), p.id === 'f' ? mat('#d9d4c8') : hair); bd.scale.set(1, 1.1, .7); neck.add(bd); }
    if (c.hat) { const ht = new THREE.Mesh(new THREE.CylinderGeometry(.1 * k, .12 * k, .1 * k, 9).translate(0, .27 * k, 0), mat(c.trim || '#c9a34a')); neck.add(ht); }
    for (const s of [-1, 1]) {
      const up = limb(torso, .05 * b, .045 * b, .3 * k, c.bare ? skin : cloth, s * .22 * b, .56 * k, 0);
      const lo = limb(up, .042 * b, .035 * b, .28 * k, skin, 0, -.3 * k, 0);
      A.push({up, lo});
    }
    // 手里的东西（负重）：都先建好，按 load 显隐
    const props = {};
    { const g = new THREE.Group(); const n = new THREE.Mesh(new THREE.SphereGeometry(.22, 8, 6), mat('#8f8a74')); n.scale.set(1.4, .7, .9); g.add(n);
      const d = new THREE.Mesh(new THREE.CylinderGeometry(.02, .25, .5, 7, 1, true).translate(0, -.25, 0), mat('#8f8a74')); d.material.side = THREE.DoubleSide; d.position.set(0, -.05, -.12); g.add(d);
      g.position.set(.16 * b, .66 * k, -.05); torso.add(g); props.net = g; }                                  // 渔网：搭在右肩，垂到背后
    { const g = new THREE.Mesh(new THREE.CylinderGeometry(.13, .1, .18, 8).translate(0, -.09, 0), mat('#a8864e')); g.position.y = -.3 * k; A[0].lo.add(g); props.catch = g; } // 鱼篓：提在左手
    { const g = new THREE.Mesh(new THREE.BoxGeometry(.42, .3, .32), mat('#8a6a48')); g.position.set(0, .28 * k, .3); torso.add(g); props.crate = g; }  // 货箱：抱在胸前
    { const pts = [[0, 0], [.07, .02], [.13, .12], [.14, .26], [.09, .38], [.05, .44], [.07, .5], [0, .5]].map(q => new THREE.Vector2(q[0], q[1]));
      const jar = () => new THREE.Mesh(new THREE.LatheGeometry(pts, 9), mat('#b5683e'));
      const e = jar(); e.position.set(.2 * b, .05 * k, .08); e.rotation.z = -.5; torso.add(e); props.jar_empty = e;      // 空罐：夹在腰侧
      const f = jar(); f.position.set(0, .28 * k, -.02); neck.add(f); props.jar_full = f; }                            // 满罐：顶在头上
    { const g = new THREE.Mesh(new THREE.SphereGeometry(.3, 8, 6), mat('#d2c3a0')); g.scale.set(1.25, .7, .9); g.position.set(0, .66 * k, -.16); torso.add(g); props.sack = g; } // 麻袋：压在肩背上
    for (const q of Object.values(props)) q.visible = false;
    scene.add(root);
    return {root, hip, torso, neck, L, A, robe, props, k};
  }

  for (const p of data.people) { const r = build(p); const o = {p, r, x: 0, z: 0, dir: 0, vis: false, ph: 0}; people.push(o); byId[p.id] = o; }
  const LEADER = {c: 'f', s: 'm'};
  const plen = path => { let s = 0; for (let i = 1; i < path.length; i++) s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]); return s };
  for (const o of people) for (const a of o.p.acts) if (a.a === 'walk') a.len = plen(a.path);
  function along(path, s) { // 折线上第 s 像素处的点和朝向
    for (let i = 1; i < path.length; i++) { const ax = path[i - 1][0], az = path[i - 1][1], bx = path[i][0], bz = path[i][1], l = Math.hypot(bx - ax, bz - az);
      if (s <= l || i === path.length - 1) { const u = l ? Math.min(1, Math.max(0, s / l)) : 0; return [ax + (bx - ax) * u, az + (bz - az) * u, Math.atan2(bx - ax, bz - az)] } s -= l }
    const q = path[path.length - 1]; return [q[0], q[1], 0];
  }
  const actAt = (o, t) => { const A = o.p.acts; for (const a of A) if (t >= a.t0 && t < a.t1) return a; return A[A.length - 1] };
  function ground(x, z) { return isLand(x, z) ? elevPx(x, z) + 1.5 : 1.6 }

  // 姿势：交给姿势引擎（pose.js）。步态参数不再逐人手写——按每个人的种子从「意图 → 参数分布」里抽，
  // 4 个候选按像不像真人打分留一个。叠加手势在最后一层：回头、擦汗、伸手、叉腰歇气。
  for (const o of people) { const names = [...new Set(o.p.acts.filter(a => a.gait).map(a => a.gait))];
    o.u = pickTemper(hash(o.p.id + ':' + (o.p.facts.house || '')), names.length ? names : ['walker'], {h: o.p.cast.h}); o.g = {} }
  const gait = (o, name) => o.g[name] || (o.g[name] = gaitOf(name, o.u));
  let prevAct = new Map();
  function pose(o, t, a) {
    const r = o.r, P = blank(), load = a.load || null;
    if (a.a === 'walk') walk(P, gait(o, a.gait), o.ph);
    else stay(P, a.pose || 'stand', t + o.p.n * 3.1, r.k);
    carry(P, load);
    // 叠加层：什么时候做哪个手势，全看他此刻在干什么
    const id = o.p.id, dt = t - a.t0;
    if (id === 'f' && a.a === 'walk' && load === 'net') OVER.lookback(P, env(dt % 7, 2.5, 1.8));                 // 带着孙子走：隔一会儿回头看一眼
    if (id === 'p' && a.a === 'walk' && !load && a.gait === 'porter') OVER.wipe(P, env(dt, .3, 2.8));            // 刚卸下麻袋：抬手擦汗
    if (id === 'c' && a.a === 'walk' && a.tag === 'follow') OVER.reach(P, env(dt % 6, 1, 2.2));                   // 跟着爷爷：时不时伸手去够
    if (id === 'w' && a.a === 'walk' && load === 'jar_full') OVER.shift(P, env(dt % 14, 6, 3));                  // 满罐上坡：一手叉腰歇口气
    return P;
  }
  function apply(o, P, a) {
    const r = o.r;
    r.hip.position.y = .92 * r.k * (1 + P.bob) + P.lift; r.hip.rotation.z = P.hip; r.torso.rotation.set(P.stoop, P.twist, P.side); r.neck.rotation.set(P.neck, P.headYaw, 0);
    for (let i = 0; i < 2; i++) { r.L[i].th.rotation.x = -P.legs[i][0]; r.L[i].sh.rotation.x = P.legs[i][1];
      r.A[i].up.rotation.x = -P.arms[i][0]; r.A[i].up.rotation.z = (i ? -1 : 1) * (.08 + P.arms[i][2]); r.A[i].lo.rotation.x = -P.arms[i][1] }
    if (r.robe) { r.robe.rotation.x = (P.legs[0][0] - P.legs[1][0]) * .08; r.robe.scale.z = 1 + Math.abs(P.legs[0][0] - P.legs[1][0]) * .25 }
    const load = a.load || null; for (const [k, m] of Object.entries(r.props)) m.visible = k === load;
  }

  let lastT = 0;
  function tick(t) {
    const dt = Math.min(1, Math.max(0, t - lastT)); lastT = t;
    for (const o of people) {
      let a = actAt(o, t), x, z, d = o.dir;
      const lead = LEADER[o.p.id] && byId[LEADER[o.p.id]];
      if (a.a === 'walk' && a.tag === 'follow' && lead) {             // 同伴：踩着带头人的脚印走，落后一两步
        const la = actAt(lead, t);
        if (la.a === 'walk') { const s = la.len * (t - la.t0) / (la.t1 - la.t0) - (o.p.id === 'c' ? 1.3 : 1.7) * M; const q = along(la.path, Math.max(0, s)); x = q[0]; z = q[1]; d = q[2];
          const side = (o.p.id === 'c' ? -.55 : .5) * M; x += Math.cos(d) * side; z -= Math.sin(d) * side; a = {...a, gait: o.p.id === 'c' ? 'child_walk' : a.gait} }
      }
      if (x == null) {
        if (a.a === 'walk') { const s = a.len * (t - a.t0) / Math.max(.01, a.t1 - a.t0); const q = along(a.path, s); x = q[0]; z = q[1]; d = q[2];
          if (!gait(o, a.gait).center) { const side = .7 * M; x += Math.cos(d) * side; z -= Math.sin(d) * side } }   // 有身份的走街心，其他人靠边
        else { [x, z] = a.at; if (a.face) d = Math.atan2(a.face[0] - x, a.face[1] - z);
          if (a.pose === 'play') { const tt = t * .7 + o.p.n; x += Math.sin(tt) * 2.2 * M; z += Math.sin(tt * 1.7) * 1.4 * M; d = Math.atan2(Math.cos(tt) * 2.2, Math.cos(tt * 1.7) * 2.4) } }
      }
      const step = Math.hypot(x - o.x, z - o.z);
      if (a.a === 'walk') { const g = gait(o, a.gait); o.ph += (step / M) / g.stride * Math.PI; }   // 相位跟着走过的米数走：步子不会滑
      o.x = x; o.z = z;
      let dd = d - o.dir; dd = Math.atan2(Math.sin(dd), Math.cos(dd)); o.dir += dd * Math.min(1, dt * 6 + .05);
      o.vis = a.a !== 'hide'; o.r.root.visible = o.vis;
      o.r.root.position.set(x, ground(x, z), z); o.r.root.rotation.y = o.dir;
      apply(o, pose(o, t, a), a);
    }
  }
  return {tick, people, byId, T: data.T, phases: data.phases, posOf: n => { const o = people.find(q => q.p.n === n); return o && {x: o.x, z: o.z, y: o.r.root.position.y, dir: o.dir, vis: o.vis} }};
}
