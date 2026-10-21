/* 全城 3D 远景档（citylod，2026-10-20，全城页 nodes/city/3d.html 的导演 citycore.js 用；南港页不载入）。——Hark（CS线）
   近景窗口外的每个分块画三样，全部全城坐标、挂在 citycore 的 CITY 组（浮动原点：组跟着窗口原点平移）：
   - 地形：每块 28×28 格（455/28 ≈ 16.25 px 一格）+ 四边裙边往下 12 px（和近景窗口、相邻块的接缝不露天）；高度 = citycore 的全城 ground()，
     和近景 terrain 网格同一个函数，只是格子粗；披全城地面贴图（terrain/water/streets 三个模块自己的 paint 画的，同一套颜色）。
   - 房子：一户一个体块 + 四坡/平顶，占地、高度、墙色/瓦色/平顶与否都按 arch/house.js 同一套房号哈希（WALLS/ROOFS/OPUS_P/FLAT），远近切换颜色不跳。
     约 14 个三角形一户；一块一个网格（顶点色，无贴图）。
   - 地标剪影：29 座都画（年份内），近景窗口里的那几座藏起来交给 buildings/landmarks。按 kind 给体块和高度，纪功柱、大宁芙殿、狄奥多西广场照模块里的尺寸给轮廓。 */
import {linC,mul} from './arch/geo.js';
import {WALLS,ROOFS,OPUS_P,FLAT} from './arch/house.js';

export const NS = 28;          // 每块地形的格数
const SKIRT = 12;

/* 一块地形：i,j 块号，CS 块边长，G(x,z) 全城地面高，CW/CH 全城宽高（贴图 uv） */
export function terrainChunk(T, i, j, CS, G, CW, CH, mat) {
  const x0 = i * CS, z0 = j * CS, st = CS / NS, n = NS + 1, pos = [], uv = [], idx = [];
  const v = (x, y, z) => { pos.push(x, y, z); uv.push(x / CW, 1 - z / CH); return pos.length / 3 - 1 };
  for (let b = 0; b < n; b++) for (let a = 0; a < n; a++) { const x = x0 + a * st, z = z0 + b * st; v(x, G(x, z), z) }
  for (let b = 0; b < NS; b++) for (let a = 0; a < NS; a++) { const p = b * n + a, q = p + 1, r = p + n, s = r + 1; idx.push(p, r, q, q, r, s) }
  /* 裙边：沿四边，每个边点往下 SKIRT */
  const ring = []; for (let a = 0; a < NS; a++) ring.push(a); for (let b = 0; b < NS; b++) ring.push(b * n + NS); for (let a = NS; a > 0; a--) ring.push(NS * n + a); for (let b = NS; b > 0; b--) ring.push(b * n);
  const low = ring.map(k => v(pos[k * 3], pos[k * 3 + 1] - SKIRT, pos[k * 3 + 2]));
  for (let m = 0; m < ring.length; m++) { const a = ring[m], b = ring[(m + 1) % ring.length], c = low[m], d = low[(m + 1) % ring.length]; idx.push(a, c, b, b, c, d) }
  /* 法线按地面函数的差分算（裙边点抄顶上那点的），块边不出暗线 */
  const nor = new Float32Array(pos.length), e = 24;
  for (let k = 0; k < pos.length / 3; k++) { const x = pos[k * 3], z = pos[k * 3 + 2], dx = G(x + e, z) - G(x - e, z), dz = G(x, z + e) - G(x, z - e), L = Math.hypot(dx, 2 * e, dz); nor[k * 3] = -dx / L; nor[k * 3 + 1] = 2 * e / L; nor[k * 3 + 2] = -dz / L }
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new T.Float32BufferAttribute(nor, 3)); g.setAttribute('uv', new T.Float32BufferAttribute(uv, 2)); g.setIndex(idx);
  const m = new T.Mesh(g, mat); m.receiveShadow = true; m.name = 'lod-terrain'; return m;
}

/* 近景窗口的裙边：窗口 [ox,oz]–[ox+w,oz+w] 四条边，每 4 px 一点，从 Y(x,z)（窗口网格的高，全城坐标）往下 SKIRT */
export function rimSkirt(T, ox, oz, w, Y, CW, CH, mat) {
  const pos = [], uv = [], idx = []; const S = 4, n = Math.round(w / S);
  const edge = (fx, fz) => { const base = pos.length / 3; for (let k = 0; k <= n; k++) { const [x, z] = fx(k * S), y = Y(x, z); pos.push(x, y + .05, z, x, y - SKIRT, z); uv.push(x / CW, 1 - z / CH, x / CW, 1 - z / CH) }
    for (let k = 0; k < n; k++) { const a = base + k * 2; idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3) } };
  edge(t => [ox + t, oz]); edge(t => [ox + w, oz + t]); edge(t => [ox + w - t, oz + w]); edge(t => [ox, oz + w - t]);
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new T.Float32BufferAttribute(uv, 2)); g.setIndex(idx); g.computeVertexNormals();
  const m = new T.Mesh(g, mat); m.name = 'lod-rim'; return m;
}

/* 顶点色三角桶 */
function bucket() { return {p: [], c: []} }
function tri(B, a, b, c, col) { B.p.push(...a, ...b, ...c); for (let i = 0; i < 3; i++) B.c.push(col[0], col[1], col[2]) }
function quad(B, a, b, c, d, col) { tri(B, a, b, c, col); tri(B, a, c, d, col) }
function meshOf(T, B, mat, name) { if (!B.p.length) return null; const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(B.p, 3)); g.setAttribute('color', new T.Float32BufferAttribute(B.c, 3)); g.computeVertexNormals(); const m = new T.Mesh(g, mat); m.name = name; m.receiveShadow = true; return m }

function axes(P) { const cx = (P[0][0] + P[1][0] + P[2][0] + P[3][0]) / 4, cz = (P[0][1] + P[1][1] + P[2][1] + P[3][1]) / 4;
  const ux = P[1][0] - P[0][0], uz = P[1][1] - P[0][1], vx = P[3][0] - P[0][0], vz = P[3][1] - P[0][1], Lu = Math.hypot(ux, uz) || 1, Lv = Math.hypot(vx, vz) || 1;
  return Lu >= Lv ? {cx, cz, ax: ux / Lu, az: uz / Lu, hu: Lu / 2, hv: Lv / 2} : {cx, cz, ax: vx / Lv, az: vz / Lv, hu: Lv / 2, hv: Lu / 2} }

/* 一个体块：r = 轴向矩形，y0 墙底，y1 檐高，wc/rc 线性色；roof: 'hip' | 'flat' | 'gable'；pitch 屋面坡度（半宽的倍数） */
export function mass(B, r, y0, y1, wc, rc, roof = 'hip', pitch = .42, O = .5) {
  const C = (u, v) => [r.cx + r.ax * u - r.az * v, r.cz + r.az * u + r.ax * v];
  const k = [C(-r.hu, -r.hv), C(r.hu, -r.hv), C(r.hu, r.hv), C(-r.hu, r.hv)];
  for (let i = 0; i < 4; i++) { const a = k[i], b = k[(i + 1) % 4]; quad(B, [a[0], y0, a[1]], [b[0], y0, b[1]], [b[0], y1, b[1]], [a[0], y1, a[1]], mul(wc, i % 2 ? .86 : 1)) }
  if (roof === 'flat') { quad(B, [k[0][0], y1, k[0][1]], [k[3][0], y1, k[3][1]], [k[2][0], y1, k[2][1]], [k[1][0], y1, k[1][1]], rc); return }
  const rh = Math.min(r.hv * pitch, 10), rr = roof === 'gable' ? r.hu + O : Math.max(0, r.hu - r.hv), e = (u, v) => { const q = C(u, v); return [q[0], y1 - .2, q[1]] }, t = u => { const q = C(u, 0); return [q[0], y1 + rh, q[1]] };
  const e00 = e(-r.hu - O, -r.hv - O), e10 = e(r.hu + O, -r.hv - O), e11 = e(r.hu + O, r.hv + O), e01 = e(-r.hu - O, r.hv + O), A = t(-rr), Bq = t(rr);
  quad(B, e00, e10, Bq, A, rc); quad(B, e11, e01, A, Bq, rc);
  if (roof === 'gable') { const g0 = C(-r.hu, -r.hv), g1 = C(-r.hu, r.hv), g2 = C(r.hu, r.hv), g3 = C(r.hu, -r.hv), a = t(-r.hu), b = t(r.hu);
    tri(B, [g0[0], y1, g0[1]], [g1[0], y1, g1[1]], a, wc); tri(B, [g2[0], y1, g2[1]], [g3[0], y1, g3[1]], b, wc) }
  else { tri(B, e01, e00, A, mul(rc, .92)); tri(B, e10, e11, Bq, mul(rc, .92)) }
}

/* 一块的房子：L = 远景简块 {h:[[id,y0,y1,p8,ht,fn]]}，FN = fn 名表，Y 年份，G 地面（全城坐标），hsh 同 core */
export function housesChunk(T, L, FN, Y, G, hsh, mat) {
  const B = bucket(); let n = 0;
  for (const h of L.h) {
    const id = h[0], y0 = h[1], y1 = h[2]; if (!(y0 <= Y && (y1 < 0 || y1 > Y))) continue;
    const p = h.slice(3, 11), ht = h[11], fn = FN[h[12]] || 'homes';
    const cx = (p[0] + p[2] + p[4] + p[6]) / 4, cz = (p[1] + p[3] + p[5] + p[7]) / 4;
    const P = [0, 1, 2, 3].map(i => [cx + (p[i * 2] - cx) * .92, cz + (p[i * 2 + 1] - cz) * .92]), r = axes(P);
    let mn = 1e9, mx = -1e9; for (const q of P) { const g = G(q[0], q[1]); mn = Math.min(mn, Math.max(g, 0)); mx = Math.max(mx, g) } const mid = G(cx, cz);
    const base = Math.max(mid, mx - .45) + .05, H = Math.max(3, (ht || 5) * 1.15);
    const kind = hsh(id, 21) < (OPUS_P[fn] ?? .25) ? 'opus' : 'stucco', WP = WALLS[kind], wc = WP[Math.floor(hsh(id, 3) * WP.length)];
    const wcol = linC(mul(wc, (.96 + .08 * hsh(id, 4)) * .9)), rc = ROOFS[Math.floor(hsh(id, 14) * ROOFS.length)], rcol = linC(mul(rc, (.92 + .16 * hsh(id, 15)) * 1.1));
    const flat = hsh(id, 17) < (FLAT[fn] ?? .1);
    mass(B, r, Math.min(mn - 1.5, base - 1), base + H, wcol, flat ? mul(wcol, .82) : rcol, flat ? 'flat' : 'hip');
    n++;
  }
  const m = meshOf(T, B, mat, 'lod-houses'); if (m) m.userData.n = n; return m;
}

/* 地标剪影：f = 底账地标（全城坐标），G 地面，返回一个网格（或 null）。尺寸 px（1 px ≈ 0.84 m）。 */
const MARBLE = linC([238, 232, 218]), STONE = linC([222, 212, 190]), ROOF = linC([186, 98, 62]), LEAD = linC([150, 146, 140]), BRICK = linC([196, 150, 112]);
export function landmarkMass(T, f, G, mat) {
  const g = f.g; let cx = 0, cz = 0; for (const q of g) { cx += q[0]; cz += q[1] } cx /= g.length; cz /= g.length;
  /* 最长边定轴 */
  let best = null; for (let i = 0; i < g.length; i++) { const a = g[i], b = g[(i + 1) % g.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (!best || L > best.L) best = {L, ax: (b[0] - a[0]) / L, az: (b[1] - a[1]) / L} }
  let hu = 0, hv = 0; for (const q of g) { const dx = q[0] - cx, dz = q[1] - cz; hu = Math.max(hu, Math.abs(dx * best.ax + dz * best.az)); hv = Math.max(hv, Math.abs(-dx * best.az + dz * best.ax)) }
  const r = {cx, cz, ax: best.ax, az: best.az, hu, hv}, sub = (u0, v0, u1, v1) => ({cx: cx + r.ax * (u0 + u1) / 2 - r.az * (v0 + v1) / 2, cz: cz + r.az * (u0 + u1) / 2 + r.ax * (v0 + v1) / 2, ax: r.ax, az: r.az, hu: Math.abs(u1 - u0) / 2, hv: Math.abs(v1 - v0) / 2});
  let mn = 1e9, mx = -1e9; for (let a = -1; a <= 1; a += .5) for (let b = -1; b <= 1; b += .5) { const x = cx + r.ax * a * hu - r.az * b * hv, z = cz + r.az * a * hu + r.ax * b * hv, h = G(x, z); mn = Math.min(mn, Math.max(h, 0)); mx = Math.max(mx, h) }
  const B0 = bucket(), y0 = mn - 2, b = mx + .1, k = f.k;
  /* 大体块按 ≤ 40 px 的格子拆开、每格按自己脚下的地面落（坡上成台地），不然坡地上的皇宫一面墙几十米高 */
  const B = {p: B0.p, c: B0.c};
  const fit = rr => { let lo = 1e9, hi = -1e9; for (let a = -1; a <= 1; a++) for (let c = -1; c <= 1; c++) { const x = rr.cx + rr.ax * a * rr.hu - rr.az * c * rr.hv, z = rr.cz + rr.az * a * rr.hu + rr.ax * c * rr.hv, h = G(x, z); lo = Math.min(lo, Math.max(h, 0)); hi = Math.max(hi, h) } return [lo - 2, hi + .1] };
  const massT = (B_, rr, _y0, top, wc, rc, roof = 'hip', pitch = .42) => { const h = top - b; const nu = Math.max(1, Math.ceil(rr.hu * 2 / 40)), nv = Math.max(1, Math.ceil(rr.hv * 2 / 40));
    if (nu * nv === 1) { const [lo, hi] = fit(rr); return mass(B_, rr, lo, hi + h, wc, rc, roof, pitch) }
    for (let a = 0; a < nu; a++) for (let c = 0; c < nv; c++) { const u0 = -rr.hu + a * rr.hu * 2 / nu, u1 = u0 + rr.hu * 2 / nu, v0 = -rr.hv + c * rr.hv * 2 / nv, v1 = v0 + rr.hv * 2 / nv;
      const q = {cx: rr.cx + rr.ax * (u0 + u1) / 2 - rr.az * (v0 + v1) / 2, cz: rr.cz + rr.az * (u0 + u1) / 2 + rr.ax * (v0 + v1) / 2, ax: rr.ax, az: rr.az, hu: (u1 - u0) / 2, hv: (v1 - v0) / 2}, [lo, hi] = fit(q);
      mass(B_, q, lo, hi + h, wc, rc, 'flat') } };
  const ring = (d, h, wc, rc) => { massT(B, sub(-hu, -hv, hu, -hv + d), y0, b + h, wc, rc); massT(B, sub(-hu, hv - d, hu, hv), y0, b + h, wc, rc); massT(B, sub(-hu, -hv + d, -hu + d, hv - d), y0, b + h, wc, rc); massT(B, sub(hu - d, -hv + d, hu, hv - d), y0, b + h, wc, rc) };
  const tower = (x, z, w, h, c) => massT(B, {cx: x, cz: z, ax: 1, az: 0, hu: w, hv: w}, y0, b + h, c, c, 'flat');
  if (k === 'forum') {
    ring(Math.min(10, hv * .3), f.id === 'forum_theodosius' ? 22 : 9.6, MARBLE, ROOF);
    if (f.id === 'forum_theodosius') { tower(cx, cz, 2.6, 86, MARBLE); massT(B, sub(-hu - 4, -18, -hu + 4, 18), y0, b + 52, MARBLE, MARBLE, 'flat') }
  } else if (k === 'nymphaeum') massT(B, r, y0, b + (f.id === 'nymphaeum_maius' ? 36 : 18), MARBLE, MARBLE, 'flat');
  else if (k === 'church') { const h = Math.min(24, 8 + hv * .35); massT(B, r, y0, b + h, STONE, LEAD, 'gable', .5); if (hu > 60) tower(cx, cz, Math.min(hv, 20) * .7, h + 14, LEAD) }
  else if (k === 'hippodrome') { const d = Math.min(18, hv * .35); massT(B, sub(-hu, -hv, hu, -hv + d), y0, b + 12, STONE, STONE, 'flat'); massT(B, sub(-hu, hv - d, hu, hv), y0, b + 12, STONE, STONE, 'flat'); massT(B, sub(-hu, -hv + d, -hu + d, hv - d), y0, b + 12, STONE, STONE, 'flat'); massT(B, sub(-hu * .8, -2, hu * .8, 2), y0, b + 3, MARBLE, MARBLE, 'flat') }
  else if (k === 'palace') { massT(B, sub(-hu, -hv, hu * .1, hv * .2), y0, b + 16, BRICK, ROOF); massT(B, sub(hu * .2, -hv * .1, hu, hv), y0, b + 12, BRICK, ROOF) }
  else if (k === 'fort' || k === 'gate') { massT(B, r, y0, b + (k === 'gate' ? 16 : 14), STONE, STONE, 'flat'); tower(r.cx + r.ax * hu * .7, r.cz + r.az * hu * .7, 5, 24, STONE); tower(r.cx - r.ax * hu * .7, r.cz - r.az * hu * .7, 5, 24, STONE) }
  else if (k === 'cistern') massT(B, r, y0, b + 2, STONE, linC([130, 120, 104]), 'flat');
  else if (k === 'baths') { massT(B, r, y0, b + 16, BRICK, LEAD, 'hip', .3); tower(cx, cz, Math.min(hu, hv) * .4, 26, LEAD) }
  else if (k === 'market') ring(Math.min(9, hv * .3), 8, STONE, ROOF);
  else if (k === 'monument') massT(B, r, y0, b + 12, MARBLE, MARBLE, 'flat');
  else if (k === 'xenon') ring(9, 9, STONE, ROOF);
  else massT(B, r, y0, b + 12 * 1.2, STONE, ROOF, 'gable', .4);   // granary / warehouse：长仓
  return meshOf(T, B0, mat, 'lod-landmark:' + f.id);
}

/* 远景地面贴图上画屋顶色的房基（航拍时一户只有一两个屏幕像素，体块读不出来；贴图上的屋顶色让全城读得出街廓）。颜色同 housesChunk 的哈希。 */
export function paintRoofs(X, L, Y, hsh) {
  for (const h of L.h) { const id = h[0]; if (!(h[1] <= Y && (h[2] < 0 || h[2] > Y))) continue;
    const fn = h[12], rc = ROOFS[Math.floor(hsh(id, 14) * ROOFS.length)], k = .92 + .16 * hsh(id, 15), flat = false;
    X.fillStyle = `rgb(${rc[0] * k | 0},${rc[1] * k | 0},${rc[2] * k | 0})`;
    X.beginPath(); X.moveTo(h[3], h[4]); X.lineTo(h[5], h[6]); X.lineTo(h[7], h[8]); X.lineTo(h[9], h[10]); X.closePath(); X.fill() } }
