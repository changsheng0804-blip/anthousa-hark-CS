/* landmark 第 2 座 · 大宁芙殿（Nymphaeum Maius，「丰沛之水」）。——Hark（CS线）2026-10-20
   底账（只照用）：
   - nodes.json 地标 nymphaeum_maius（k=nymphaeum，y0=44，四角 [1540,185] [1610,172] [1617,213] [1547,226]，约 60×35 m）；
   - proposals/era_0041.json：第 44 年皇帝（瓦伦斯）建成，dna = rotunda / 砖 + 大理石贴面 / ornament 3 / monumental，「水道的门面，让全城看见水从哪里来」；
     没有 phases → 不画施工中，44 年起就是完整的（AF 44 ≈ AD 373，和史料 373 年 Clearchus 建成对得上）；
   - chronicle/41_50.md 第 44 年、51_60.md 第 57 年「陶里广场、瓦伦斯大喷泉的旁边」划出狄奥多西广场 → 广场在它西南；
   - nodes.json 的 aq_hadrian 水道桥贴着它的北边过（东北角离桥只有几米）→ 背墙让开桥，水从背后进来。
   史料（形制底账没写；来源见 docs/cs/lookdev/landmarks/nymphaeum/notes.md）：Socrates《教会史》4.8 叫它 hydreion megiston（最大的水殿）、
   「丰沛之水」δαψιλὲς ὕδωρ；Notitia（约 425 年）记在第十区；形制没有任何描述流传下来。
   假设（都可推翻）：照 2–4 世纪的大型宁芙殿（米利都、锡德、杰拉什）做两层壁龛式（aedicular）立面；dna 的 rotunda 读成「凹的半圆形平面」——
   这里是 7 个平面折出来的弧形立面（弦 46 m、矢高 11 m），两端各一座方塔；每层 7 个凸出的小神龛（两根柱子 + 断开的檐部），后面是半圆壁龛，
   每龛一尊像（共 14 尊，宁芙 / 披袍像，3 种姿势烘焙）；上层神龛三角 / 弧形山花交替；下层龛下兽头吐水进前面的长槽，上层 4 道水瀑落进槽，
   槽再溢进前面一个向外鼓的大水池。立面贴白 / 灰大理石，柱子下层灰绿 cipollino、上层白；背墙、女儿墙是砖带石（底账 materials = brick）。
   尺寸（米，自基面起）：台基 1.4 → 下层柱座到 3.2、柱到 10.2、檐到 11.6 → 上层柱座到 12.8、柱到 18.0、檐到 19.1 → 山花 / 顶檐到 21.0 → 砖女儿墙 22.2；塔 22.8。
   结构：所有尺寸按米写，内组整体乘 K（1 页面像素 ≈ 0.84 m）；近 / 远两档 THREE.LOD；几何不随年份变，建一次缓存。?lmmask=1 全换品红。
   确定性：贴图只用底账 seed，水的动画只吃 tick 的 t。 */
import { lathe, merge } from './kit/lathe.js';
import { relief, rng, rect, line, ell } from './kit/relief.js';
import { corinthian } from './kit/acanthus.js';
import { loadBaked, geoOf } from './kit/baked.js';

const SB = {};
for (const k of ['a', 'b', 'c']) for (const l of ['hi', 'lo']) SB[k + l] = await loadBaked(new URL(`./nymphaeum/statue_${k}_${l}.bin`, import.meta.url));

export const id = 'nymphaeum_maius';
const K = 1 / 0.84, LOD_FAR = 340;
/* 平面（米，局部：u 顺长边 = 底账 rectOf 的 (ax,az)，v 朝前 = 南偏东；原点 = 地标中心） */
const PYL = 0.7;                                                                      // 塔面反照率系数（见塔身）
export const PLAN = { u0: -0.25, front: 4, half: 23.3, sag: 11, bays: 7, pylonW: 6.4, pylonD: 6.0, back: 2.5 };
/* 史诗夸张（r3_ground_scale，主人 10-20「史诗城市里地标要放大一些，尤其大的」）：台基顶（1.4 m）以上的所有高 ×HERO_SCALE，
   神龛 / 壁龛 / 柱子的宽和粗 ×HERO_W（不然柱子变细长），雕像整体 ×HERO_SCALE；平面（弦长、矢高、塔的平面）照底账占地不动。
   台基、长槽、水池（贴地的部分）不放大。见 MODULE_CONTRACT §7「史诗夸张」。 */
export const HERO_SCALE = 1.4, HERO_W = 1.2;
const Y0 = { pod: 1.4, ped1: 3.3, col1: 10.6, ent1: 12.0, ped2: 13.2, col2: 18.6, ent2: 19.7, top: 21.6, attic: 22.2, tower: 22.0 };   // 改前（实际比例）的高
const SY = y => y <= Y0.pod ? y : Y0.pod + (y - Y0.pod) * HERO_SCALE;
export const Y = { ...Object.fromEntries(Object.entries(Y0).map(([k, v]) => [k, SY(v)])), water: -0.35, trough: 1.05 };   // 池水比台基低，池栏顶 +0.2
const N1 = { w: 2.4 * HERO_W, y0: SY(3.5), ys: SY(7.0) }, N2 = { w: 2.0 * HERO_W, y0: SY(13.4), ys: SY(16.1) };        // 壁龛：宽、龛底、起拱
const AE1 = { a: 2.9 * HERO_W, d: 1.5 * HERO_W, r: 0.38 * HERO_W }, AE2 = { a: 2.5 * HERO_W, d: 1.25 * HERO_W, r: 0.3 * HERO_W };         // 神龛：两柱间距、柱心离墙、柱下半径
/* 落地（r3）：基面 b = 占地下最高的地面（index.js 给）；所有往下伸的面（台基、背墙、塔基、长槽、池栏）伸到 −DEPTH 米 = 占地下最低地面 −0.6 像素；
   池栏外面做成台阶（每级高 0.38、宽 0.42 m），坡下那一侧成一圈石阶。DEPTH 在第一次 build 时按地形定（几何缓存，不随年份变）。 */
let DEPTH = 3;
function poolSteps() { const rise = 0.38, run = 0.42, n = Math.max(0, Math.ceil((DEPTH - 0.9) / rise)), out = [];
  out.push([.3 + n * run, -DEPTH]);
  for (let k = n; k >= 1; k--) { const top = -0.9 - (k - 1) * rise; out.push([.3 + k * run, top], [.3 + (k - 1) * run, top]); }
  return n ? out.slice(0, -1) : out; }
const CASCADES = [1, 3, 4, 6];                                                       // 上层水瀑从哪几个折角落下（Q_i）

let T = null, M = null, CACHE = null, WU = null, FALL_TEX = null;

/* ---------- 平面：弧上的 8 个折点 ---------- */
function plan() {
  const { u0, front, half, sag, bays } = PLAN, R = (half * half + sag * sag) / (2 * sag), C = [u0, front - sag + R], th = Math.asin(half / R);
  const Q = [];
  for (let i = 0; i <= bays; i++) { const p = -th + i * 2 * th / bays; Q.push([C[0] + R * Math.sin(p), C[1] - R * Math.cos(p)]); }
  const F = [];
  for (let i = 0; i < bays; i++) {
    const a = Q[i], b = Q[i + 1], L = Math.hypot(b[0] - a[0], b[1] - a[1]), t = [(b[0] - a[0]) / L, (b[1] - a[1]) / L], n = [-t[1], t[0]];
    const m = new T.Matrix4().set(t[0], 0, n[0], a[0], 0, 1, 0, 0, t[1], 0, n[1], a[1], 0, 0, 0, 1);   // 立面坐标 (s, y, d) → 局部 (u, y, v)
    F.push({ a, b, L, t, n, m });
  }
  return { Q, F, R, C };
}

/* ---------- 几何收集：一种材质一个桶，最后一个网格 ---------- */
class Bucket {
  constructor() { this.P = []; this.N = []; this.U = []; this.C = []; }
  add(g0, m = null, shade = 1, fix = false) {
    const g = g0.index ? g0.toNonIndexed() : g0;
    if (!g.attributes.normal) g.computeVertexNormals();
    if (fix) windByNormal(g);
    const p = g.attributes.position, n = g.attributes.normal, uv = g.attributes.uv, nm = m ? new T.Matrix3().getNormalMatrix(m) : null, v = new T.Vector3();
    const col = g.attributes.color;
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i); if (m) v.applyMatrix4(m); this.P.push(v.x, v.y, v.z);
      v.fromBufferAttribute(n, i); if (nm) v.applyMatrix3(nm).normalize(); this.N.push(v.x, v.y, v.z);
      if (uv) this.U.push(uv.getX(i), uv.getY(i)); else this.U.push(0, 0);
      const s = col ? col.getX(i) * shade : shade; this.C.push(s, s, s);
    }
    if (g !== g0) g.dispose(); g0.dispose();
  }
  mesh(mat, cast = true) {
    if (!this.P.length) return null;
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.Float32BufferAttribute(this.P, 3)); g.setAttribute('normal', new T.Float32BufferAttribute(this.N, 3));
    g.setAttribute('uv', new T.Float32BufferAttribute(this.U, 2)); g.setAttribute('color', new T.Float32BufferAttribute(this.C, 3));
    const o = new T.Mesh(g, mat); o.castShadow = cast; o.receiveShadow = true; return o;
  }
}
/* 三角形绕向按给定法线摆正（DoubleSide 材质背面会翻法线，绕向错了光就反了） */
function windByNormal(g) {
  const p = g.attributes.position, n = g.attributes.normal, u = g.attributes.uv, c = g.attributes.color, A = new T.Vector3(), B = new T.Vector3(), C = new T.Vector3(), N = new T.Vector3();
  const sw = (at, i, j) => { if (!at) return; for (let k = 0; k < at.itemSize; k++) { const t = at.array[i * at.itemSize + k]; at.array[i * at.itemSize + k] = at.array[j * at.itemSize + k]; at.array[j * at.itemSize + k] = t; } };
  for (let i = 0; i < p.count; i += 3) {
    A.fromBufferAttribute(p, i); B.fromBufferAttribute(p, i + 1).sub(A); C.fromBufferAttribute(p, i + 2).sub(A); B.cross(C);
    N.fromBufferAttribute(n, i).add(new T.Vector3().fromBufferAttribute(n, i + 1)).add(new T.Vector3().fromBufferAttribute(n, i + 2));
    if (B.dot(N) < 0) for (const at of [p, n, u, c]) sw(at, i + 1, i + 2);
  }
}
const tri = (o) => { let n = 0; o.traverse(c => { if (c.isMesh) n += (c.geometry.index ? c.geometry.index.count : c.geometry.attributes.position.count) / 3; }); return Math.round(n); };

/* 沿平面折线扫一个剖面（[[d, y], …]，d = 折线左手法线方向 = 朝前），折角斜接；平法线（线脚的棱是硬的）。UV：u = 沿线米数，v = 剖面米数。剖面的走向：实体永远在走向的左边（(d,y) 平面里），这样三角形朝外 */
function sweep(path, prof, closed = false) {
  const n = path.length, P = [], U = [], nrm = [];
  const seg = (i) => { const a = path[i], b = path[(i + 1) % n], L = Math.hypot(b[0] - a[0], b[1] - a[1]); return [(b[0] - a[0]) / L, (b[1] - a[1]) / L, L]; };
  const off = [], len = [0];
  for (let i = 0; i < n; i++) {
    const prev = (i > 0 || closed) ? seg((i - 1 + n) % n) : null, next = (i < n - 1 || closed) ? seg(i) : null;
    const l0 = prev ? [-prev[1], prev[0]] : null, l1 = next ? [-next[1], next[0]] : null;
    let m = l0 && l1 ? [l0[0] + l1[0], l0[1] + l1[1]] : (l0 || l1); const ml = Math.hypot(m[0], m[1]); m = [m[0] / ml, m[1] / ml];
    const c = l1 ? m[0] * l1[0] + m[1] * l1[1] : m[0] * l0[0] + m[1] * l0[1]; off.push([m[0] / c, m[1] / c]);
    if (i > 0) len.push(len[i - 1] + seg(i - 1)[2]);
  }
  if (closed) len.push(len[n - 1] + seg(n - 1)[2]);
  const pl = [0]; for (let k = 1; k < prof.length; k++) pl.push(pl[k - 1] + Math.hypot(prof[k][0] - prof[k - 1][0], prof[k][1] - prof[k - 1][1]));
  const at = (i, k) => { const ii = i % n, [d, y] = prof[k]; return [path[ii][0] + off[ii][0] * d, y, path[ii][1] + off[ii][1] * d]; };
  const ns = closed ? n : n - 1;
  for (let i = 0; i < ns; i++) for (let k = 0; k < prof.length - 1; k++) {
    const a = at(i, k), b = at(i + 1, k), c = at(i + 1, k + 1), d = at(i, k + 1);
    const ua = [len[i], pl[k]], ub = [len[i + 1], pl[k]], uc = [len[i + 1], pl[k + 1]], ud = [len[i], pl[k + 1]];
    for (const [q, uu] of [[a, ua], [b, ub], [c, uc], [a, ua], [c, uc], [d, ud]]) { P.push(...q); U.push(...uu); }
  }
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(P, 3)); g.setAttribute('uv', new T.Float32BufferAttribute(U, 2)); g.computeVertexNormals();
  return g;
}
/* 剖面（d 朝前，y 向上）：檐部（额枋三道 + 楣 + 檐口出挑）、台基线脚、顶檐 */
const ENT = (y0, y1, base = 0.32) => { const h = y1 - y0, k = h / 1.4; return [[0, y0 - .02], [base * .8, y0], [base * .8, y0 + .16 * k], [base * .9, y0 + .2 * k], [base * .9, y0 + .34 * k], [base, y0 + .38 * k], [base, y0 + .55 * k], [base * .95, y0 + .58 * k], [base * .95, y0 + .9 * k], [base + .1, y0 + .95 * k], [base + .14, y0 + 1.02 * k], [base + .42, y0 + 1.1 * k], [base + .45, y0 + 1.28 * k], [base + .5, y0 + 1.33 * k], [base + .5, y1], [0, y1]]; };
const PLINTH = () => [[0, -DEPTH], [2.6, -DEPTH], [2.6, .9], [2.55, 1.0], [2.55, 1.12], [2.43, 1.2], [2.43, 1.32], [2.35, 1.4], [0, 1.4]];   // 立面前的台基（伸到 2.6 m，神龛柱座站在上面）
const PYL_PLINTH = () => [[0, -DEPTH], [.45, -DEPTH], [.45, .9], [.4, 1.0], [.4, 1.12], [.28, 1.2], [.28, 1.32], [.2, 1.4], [0, 1.4]];

/* ---------- 部件（立面坐标 s, y, d：s 顺折面，d 朝前） ---------- */
function shapeGeo(sh, curve = 6) { return new T.ShapeGeometry(sh, curve); }
function archPath(p, cx, w, y0, ys) { const r = w / 2; p.moveTo(cx - r, y0); p.lineTo(cx + r, y0); p.lineTo(cx + r, ys); p.absarc(cx, ys, r, 0, Math.PI, false); p.lineTo(cx - r, y0); }
/* 一个折面的墙面：从台基顶到顶檐，挖两个拱形龛口（下层、上层） */
function wallFace(L, far) {
  const sh = new T.Shape(); sh.moveTo(0, Y.pod); sh.lineTo(L, Y.pod); sh.lineTo(L, Y.top); sh.lineTo(0, Y.top); sh.lineTo(0, Y.pod);
  if (!far) for (const N of [N1, N2]) { const h = new T.Path(); archPath(h, L / 2, N.w, N.y0, N.ys); sh.holes.push(h); }
  return shapeGeo(sh, far ? 2 : 8);
}
/* 半圆壁龛：半圆柱面 + 四分之一球顶 + 龛底；法线朝龛里（朝外能看见的一面）；颜色往里压暗（烘进去的 AO） */
function niche(cx, N, segs = 10) {
  const r = N.w / 2, P = [], Nn = [], C = [], U = [];
  const pt = (al, be, y0) => { const c = Math.cos(be), dx = Math.cos(al) * r * c, dd = -Math.sin(al) * r * c, y = y0 + Math.sin(be) * r; return [cx + dx, y, dd, -Math.cos(al) * c, -Math.sin(be), Math.sin(al) * c]; };
  const push = (q, sh) => { P.push(q[0], q[1], q[2]); Nn.push(q[3], q[4], q[5]); C.push(sh); U.push(q[0] / 2, q[1] / 2); };
  const shade = (q) => 0.18 + 0.62 * Math.min(1, Math.max(0, 1 + q[2] / r * 0.9));        // 越深越暗
  for (let i = 0; i < segs; i++) {
    const a0 = Math.PI * i / segs, a1 = Math.PI * (i + 1) / segs;
    const A = [cx + Math.cos(a0) * r, N.y0, -Math.sin(a0) * r, -Math.cos(a0), 0, Math.sin(a0)], B = [cx + Math.cos(a1) * r, N.y0, -Math.sin(a1) * r, -Math.cos(a1), 0, Math.sin(a1)];
    const A2 = [A[0], N.ys, A[2], A[3], 0, A[5]], B2 = [B[0], N.ys, B[2], B[3], 0, B[5]];
    for (const q of [A, A2, B, B, A2, B2]) push(q, shade(q));
    for (let j = 0; j < 4; j++) {                                                       // 龛顶
      const b0 = Math.PI / 2 * j / 4, b1 = Math.PI / 2 * (j + 1) / 4, p00 = pt(a0, b0, N.ys), p01 = pt(a0, b1, N.ys), p10 = pt(a1, b0, N.ys), p11 = pt(a1, b1, N.ys);
      for (const q of [p00, p01, p10, p10, p01, p11]) push(q, shade(q) * (0.92 - 0.1 * j / 4));
    }
    const F0 = [cx, N.y0, 0, 0, 1, 0];                                                  // 龛底（半圆盘）
    for (const q of [F0, [A[0], N.y0, A[2], 0, 1, 0], [B[0], N.y0, B[2], 0, 1, 0]]) push(q, 0.8);
  }
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new T.Float32BufferAttribute(Nn, 3));
  g.setAttribute('color', new T.Float32BufferAttribute(C, 1)); g.setAttribute('uv', new T.Float32BufferAttribute(U, 2));
  return g;
}
function boxAt(w, h, d, x, y, z) { const g = new T.BoxGeometry(w, h, d); g.translate(x, y + h / 2, z); return g; }
/* 柱子：阿提卡柱础 + 有收分的柱身 + 科林斯柱头（远档只出钟形 + 顶板）；局部原点 = 柱础底面中心 */
function columnGeo(r, h, segs, far) {
  const capH = r * 2.3, b = r * 0.8, sh = h - capH, prof = [[r * 1.28, 0], [r * 1.28, b * .25], [r * 1.18, b * .32], [r * 1.24, b * .5], [r * 1.1, b * .62], [r * 1.05, b * .72], [r * 1.12, b * .86], [r * 1.0, b]];
  for (let k = 0; k <= 6; k++) { const t = k / 6; prof.push([r * (1 - 0.13 * Math.pow(t, 1.3) + 0.015 * Math.sin(Math.PI * t)), b + (sh - b) * t]); }
  prof.push([r * 0.95, sh + r * .06], [r * 0.95, sh + r * .14], [r * 0.87, sh + r * .16]);
  const shaft = lathe(T, prof, segs, { v: y => y / 2 });
  const cap = corinthian(T, { r: r * 0.87, h: capH - r * .16, a: r * 1.45, seed: 5, lod: 'far' });   // 近档也用钟形 + 顶板：28 个茛苕叶柱头 ≈ 20 万三角形，60 m 外看不出来 cap.translate(0, sh + r * .16, 0);
  return { shaft, cap };
}
/* 山花：三角（tri）或弧形（seg），底宽 W、出挑 D（立面坐标，s 居中 cx） */
function pediment(kind, cx, W, y0, D) {
  const out = [], hgt = kind === 'tri' ? W * 0.24 : W * 0.2;
  const tymp = new T.Shape();
  if (kind === 'tri') { tymp.moveTo(cx - W / 2, y0); tymp.lineTo(cx + W / 2, y0); tymp.lineTo(cx, y0 + hgt); tymp.lineTo(cx - W / 2, y0); }
  else { const R = (W * W / 4 + hgt * hgt) / (2 * hgt), yc = y0 + hgt - R, a = Math.asin(W / 2 / R); tymp.moveTo(cx - W / 2, y0); tymp.lineTo(cx + W / 2, y0); tymp.absarc(cx, yc, R, Math.PI / 2 - a, Math.PI / 2 + a, false); tymp.lineTo(cx - W / 2, y0); }
  const tg = new T.ExtrudeGeometry(tymp, { depth: D - 0.25, bevelEnabled: false, curveSegments: 10 }); out.push(tg);
  // 斜檐：沿上沿的一条厚 0.32、出挑多 0.25 的檐板
  const pts = []; if (kind === 'tri') pts.push([cx - W / 2 - .25, y0 - .05], [cx, y0 + hgt + .12], [cx + W / 2 + .25, y0 - .05]);
  else { const R = (W * W / 4 + hgt * hgt) / (2 * hgt), yc = y0 + hgt - R, a = Math.asin((W / 2 + .25) / R); for (let k = 0; k <= 10; k++) { const t = Math.PI / 2 + a - 2 * a * k / 10; pts.push([cx + Math.cos(t) * R, yc + Math.sin(t) * R]); } }
  const cs = new T.Shape(); cs.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) cs.lineTo(p[0], p[1]);
  for (let k = pts.length - 1; k >= 0; k--) cs.lineTo(pts[k][0], pts[k][1] + .34); cs.lineTo(pts[0][0], pts[0][1]);
  const cg = new T.ExtrudeGeometry(cs, { depth: D, bevelEnabled: false }); out.push(cg);
  return out;
}
/* 水：抛物线水帘（从 (d0,y0) 出水、水平速度 v，落到 y1），宽 w；立面坐标 */
function fallGeo(cx, d0, y0, y1, v, w, n = 12) {
  const P = [], U = [], Nn = [];
  const at = (k) => { const y = y0 - (y0 - y1) * k / n, t = Math.sqrt(2 * (y0 - y) / 9.81); return [d0 + v * t, y]; };
  for (let k = 0; k < n; k++) {
    const [da, ya] = at(k), [db, yb] = at(k + 1), wa = w * (1 + 0.5 * k / n), wb = w * (1 + 0.5 * (k + 1) / n);
    const q = [[cx - wa / 2, ya, da, 0, k / n], [cx + wa / 2, ya, da, 1, k / n], [cx + wb / 2, yb, db, 1, (k + 1) / n], [cx - wb / 2, yb, db, 0, (k + 1) / n]];
    const nn = Math.hypot(yb - ya, db - da);
    for (const i of [0, 1, 2, 0, 2, 3]) { P.push(q[i][0], q[i][1], q[i][2]); U.push(q[i][3], q[i][4] * (y0 - y1) / 3); Nn.push(0, (db - da) / nn, (ya - yb) / nn); }
  }
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(P, 3)); g.setAttribute('uv', new T.Float32BufferAttribute(U, 2)); g.setAttribute('normal', new T.Float32BufferAttribute(Nn, 3));
  return g;
}
function statueGeo(key, lod, sc, cx, y0, d, rot) {
  const g = geoOf(T, SB[key + lod], 1); g.scale(sc, sc, sc); g.rotateY(rot); g.translate(cx, y0, d); return g;
}

/* ---------- 整座 ---------- */
function buildGroup(far) {
  const { Q, F } = plan(), B = { rev: new Bucket(), colA: new Bucket(), colB: new Bucket(), orn: new Bucket(), brick: new Bucket(), statue: new Bucket(), water: new Bucket(), fall: new Bucket() };
  const segs = far ? 6 : 12;
  const c1 = columnGeo(AE1.r, Y.col1 - Y.ped1, segs, far), c2 = columnGeo(AE2.r, Y.col2 - Y.ped2, segs, far);
  const POSE1 = ['b', 'a', 'c', 'b', 'c', 'a', 'b'], POSE2 = ['c', 'b', 'a', 'b', 'a', 'b', 'c'];
  F.forEach((f, i) => {
    const m = f.m, cx = f.L / 2, S = (g, b = B.rev, sh = 1) => b.add(g, m, sh);
    S(wallFace(f.L, far));
    if (!far) { B.rev.add(niche(cx, N1), m, 1, true); B.rev.add(niche(cx, N2), m, 1, true); }
    else for (const N of [N1, N2]) { const sh = new T.Shape(); archPath(sh, cx, N.w, N.y0, N.ys); const g = shapeGeo(sh, 4); g.translate(0, 0, 0.02); S(g, B.rev, 0.45); }
    // 神龛：柱座、柱、檐部凸块（下层、上层）
    for (const [AE, y0, y1, yE, c, bk, pedH, pedW] of [[AE1, Y.pod, Y.ped1, Y.ent1, c1, B.colA, Y.ped1 - Y.pod, 0.98 * HERO_W], [AE2, Y.ent1, Y.ped2, Y.ent2, c2, B.colB, Y.ped2 - Y.ent1, 0.78 * HERO_W]]) {
      const yc = AE === AE1 ? Y.col1 : Y.col2;
      for (const sx of [-1, 1]) {
        const x = cx + sx * AE.a / 2;
        S(boxAt(pedW, pedH, AE.d + pedW / 2, x, y0, (AE.d + pedW / 2) / 2), B.rev, 0.95);                          // 柱座连墙
        S(boxAt(pedW + .14, .14, pedW + .14, x, y0 + pedH - .14, AE.d), B.orn); S(boxAt(pedW + .12, .12, pedW + .12, x, y0, AE.d), B.orn);
        const mm = new T.Matrix4().makeTranslation(x, y1, AE.d);
        bk.add(c.shaft.clone(), m.clone().multiply(mm)); B.orn.add(c.cap.clone(), m.clone().multiply(mm));
      }
      // 檐部凸块：沿 U 形路径扫檐部剖面（立面坐标里画好再整体变换）
      const w = AE.a / 2 + .55, Dp = AE.d + AE.r * .8, path = [[cx - w, -.05], [cx - w, Dp], [cx + w, Dp], [cx + w, -.05]];
      S(sweep(path, ENT(yc, yE, 0)), B.orn);                // sweep 的平面 (x, z) 正好是立面坐标 (s, d)
      if (AE === AE2) for (const p of pediment(i % 2 ? 'seg' : 'tri', cx, 2 * w, Y.ent2, Dp + .45)) S(p, B.orn);
    }
    // 雕像（每龛一尊，站在小座上）
    {
      const lod = far ? 'lo' : 'hi', rot = (i - 3) * 0.08;
      S(boxAt(1.1 * HERO_W, .3, .8 * HERO_W, cx, N1.y0, -.55 * HERO_W), B.rev, 0.85); S(statueGeo(POSE1[i], lod, 1.3 * HERO_SCALE, cx, N1.y0 + .3, -.55 * HERO_W, rot), B.statue);
      S(boxAt(.95 * HERO_W, .26, .7 * HERO_W, cx, N2.y0, -.45 * HERO_W), B.rev, 0.85); S(statueGeo(POSE2[i], lod, 1.05 * HERO_SCALE, cx, N2.y0 + .26, -.45 * HERO_W, rot), B.statue);
    }
    // 下层龛下吐水：兽头（小椭球）+ 落进长槽的水帘
    if (!far) { const sp = new T.SphereGeometry(.22, 8, 6); sp.scale(1, .9, .8); sp.translate(cx, SY(2.8), .12); S(sp, B.orn); }
    B.fall.add(fallGeo(cx, .3, SY(2.75), Y.trough, 4.4, .26, far ? 4 : 10), m, 1, true);
  });
  // 连续的檐带（沿整条折线）：下层檐、上层檐、顶檐；台基；砖背墙、女儿墙
  const L = Q.map(q => [q[0], q[1]]);
  B.orn.add(sweep(L, ENT(Y.col1, Y.ent1, .32))); B.orn.add(sweep(L, ENT(Y.col2, Y.ent2, .28)));
  B.orn.add(sweep(L, [[0, Y.ent2], [.06, Y.ent2], [.06, Y.top - .7], [.12, Y.top - .64], [.18, Y.top - .5], [.5, Y.top - .38], [.55, Y.top - .2], [.6, Y.top - .16], [.6, Y.top], [-PLAN.back, Y.top]]));
  B.orn.add(sweep(L, PLINTH()));
  B.brick.add(sweep(L, [[-.8, Y.top], [-.8, Y.attic - .2], [-.7, Y.attic - .14], [-.7, Y.attic], [-PLAN.back - .05, Y.attic]]));
  B.brick.add(sweep(L.slice().reverse(), [[PLAN.back, -DEPTH], [PLAN.back, Y.top]]));                       // 背墙（反向走 → 左手法线朝后）
  // 长槽：台基前面一道（槽底 + 外沿），水面在槽里
  const off = (d) => sweepLine(L, d);
  B.orn.add(sweep(off(2.55), [[1.75, -DEPTH], [1.75, 1.32], [1.68, 1.4], [1.5, 1.4], [1.45, 1.32], [1.45, .4], [0, .4]]));
  waterPoly(B.water, off(2.55), off(4.0), Y.trough);
  // 两端方塔
  const { pylonW: pw, pylonD: pd } = PLAN, py = [[Q[0][0] - pw / 2 - .3, PLAN.front - pd / 2 + 1.75], [Q[PLAN.bays][0] + pw / 2 + .3, PLAN.front - pd / 2 + 1.75]];
  for (const [ux, vz] of py) {
    const rr = [[ux - pw / 2, vz + pd / 2], [ux + pw / 2, vz + pd / 2], [ux + pw / 2, vz - pd / 2], [ux - pw / 2, vz - pd / 2]];   // 逆时针（从上看 u 右、v 下）→ 左手法线朝外
    B.rev.add(sweep(rr, [[0, Y.pod], [0, Y.tower - 1.0]], true), null, PYL);          // 塔身：西塔的西面是全座唯一整片受光的面，反照率压到 0.7（局部，不动 sky）
    B.orn.add(sweep(rr, PYL_PLINTH(), true)); B.orn.add(sweep(rr, ENT(Y.col1, Y.ent1, .2), true)); B.orn.add(sweep(rr, ENT(Y.col2, Y.ent2, .2), true));
    B.orn.add(sweep(rr, [[0, Y.tower - 1.0], [.1, Y.tower - .9], [.1, Y.tower - .6], [.35, Y.tower - .45], [.4, Y.tower - .2], [.4, Y.tower], [0, Y.tower]], true)); B.orn.add(boxAt(pw + .7, .04, pd + .7, ux, Y.tower - .02, vz));
    // 塔面：四角壁柱（两层）、正面和外侧面每层一个凹框（四条细框）、正面每层一尊像站在托座上
    const outer = ux < 0 ? -1 : 1;
    for (const [ya, yb] of [[Y.pod, Y.ent1 - 1.4], [Y.ent1, Y.ent2 - 1.1]]) {
      if (!far) for (const [sx, sz] of [[-1, 1], [1, 1], [-1, -1], [1, -1]]) B.rev.add(boxAt(.7, yb - ya, .7, ux + sx * (pw / 2 - .25), ya, vz + sz * (pd / 2 - .25)), null, PYL * 1.08);
      const fh = yb - ya - 1.2, fy = ya + .6;
      if (!far) {
        for (const [cx0, cz0, ax0, w0] of [[ux, vz + pd / 2, 'x', pw - 2.0], [ux + outer * pw / 2, vz, 'z', pd - 2.0]]) {
          const fr = [];
          if (ax0 === 'x') fr.push(boxAt(w0, .16, .2, cx0, fy, cz0), boxAt(w0, .16, .2, cx0, fy + fh - .16, cz0), boxAt(.16, fh, .2, cx0 - w0 / 2, fy, cz0), boxAt(.16, fh, .2, cx0 + w0 / 2, fy, cz0));
          else fr.push(boxAt(.2, .16, w0, cx0, fy, cz0), boxAt(.2, .16, w0, cx0, fy + fh - .16, cz0), boxAt(.2, fh, .16, cx0, fy, cz0 - w0 / 2), boxAt(.2, fh, .16, cx0, fy, cz0 + w0 / 2));
          for (const g of fr) B.orn.add(g);
        }
      }
      const sc = (ya < 5 ? 1.25 : 1.0) * HERO_SCALE, key = ya < 5 ? 'b' : 'a';
      B.orn.add(boxAt(1.2, .35, .9, ux, fy + .4, vz + pd / 2 + .45));                                        // 托座
      B.statue.add(statueGeo(key, far ? 'lo' : 'hi', sc, ux, fy + .75, vz + pd / 2 + .45, 0));
    }
  }
  // 大水池：前沿向外鼓的弧（矮栏），后沿 = 立面墙线（台基和长槽压在上面）
  const W0 = [py[0][0] + pw / 2, PLAN.front + 1.75], W1 = [py[1][0] - pw / 2, PLAN.front + 1.75], arc = [];
  const bulge = 9.5, ch = (W1[0] - W0[0]) / 2, Rb = (ch * ch + bulge * bulge) / (2 * bulge), cxb = (W0[0] + W1[0]) / 2, cvb = W0[1] + bulge - Rb, ab = Math.asin(ch / Rb);
  for (let k = 0; k <= 24; k++) { const t = -ab + 2 * ab * k / 24; arc.push([cxb + Rb * Math.sin(t), cvb + Rb * Math.cos(t)]); }
  B.orn.add(sweep(arc, [...poolSteps(), [.3, -.9], [.38, -.82], [.38, -.72], [.3, -.64], [.3, .0], [.36, .07], [.3, .14], [0, .2], [-.3, .14], [-.3, -.6]]));
  waterPoly(B.water, arc, L.slice().reverse(), Y.water, true);
  // 上层水瀑：从折角处的面具吐出，越过下层檐，落进长槽
  for (const qi of CASCADES) {
    const a = F[Math.max(0, qi - 1)], b = F[Math.min(F.length - 1, qi)], n = [(a.n[0] + b.n[0]) / 2, (a.n[1] + b.n[1]) / 2], nl = Math.hypot(n[0], n[1]), nn = [n[0] / nl, n[1] / nl], t = [nn[1], -nn[0]];
    const m = new T.Matrix4().set(t[0], 0, nn[0], Q[qi][0], 0, 1, 0, 0, t[1], 0, nn[1], Q[qi][1], 0, 0, 0, 1);
    B.fall.add(fallGeo(0, .85, Y.ent1 + 2.0 * HERO_SCALE, Y.trough, 1.75, .55, far ? 5 : 14), m, 1, true);
    if (!far) { const mk = new T.SphereGeometry(.42, 10, 8); mk.scale(1, 1.1, .7); mk.translate(0, Y.ent1 + 2.2 * HERO_SCALE, .2); B.orn.add(mk, m); const sp = boxAt(.5, .16, 1.0, 0, Y.ent1 + 1.9 * HERO_SCALE, .45); B.orn.add(sp, m); }
  }
  const G = new T.Group();
  for (const [k, mat, cast] of [['rev', M.rev, true], ['colA', M.colA, true], ['colB', M.colB, true], ['orn', M.orn, true], ['brick', M.brick, true], ['statue', M.statue, true], ['water', M.water, false], ['fall', M.fall, false]]) {
    const o = B[k].mesh(mat, cast); if (o) { if (k === 'fall') o.renderOrder = 2; G.add(o); }
  }
  G.scale.setScalar(K);
  c1.shaft.dispose(); c1.cap.dispose(); c2.shaft.dispose(); c2.cap.dispose();
  return G;
}
/* 折线往前（左手法线）平移 d：用 sweep 同样的斜接 */
function sweepLine(path, d) {
  const n = path.length, out = [];
  for (let i = 0; i < n; i++) {
    const s = (a, b) => { const L = Math.hypot(b[0] - a[0], b[1] - a[1]); return [-(b[1] - a[1]) / L, (b[0] - a[0]) / L]; };
    const l0 = i > 0 ? s(path[i - 1], path[i]) : null, l1 = i < n - 1 ? s(path[i], path[i + 1]) : null;
    let m = l0 && l1 ? [l0[0] + l1[0], l0[1] + l1[1]] : (l0 || l1); const ml = Math.hypot(m[0], m[1]); m = [m[0] / ml, m[1] / ml];
    const c = m[0] * (l1 || l0)[0] + m[1] * (l1 || l0)[1]; out.push([path[i][0] + m[0] * d / c, path[i][1] + m[1] * d / c]);
  }
  return out;
}
/* 水面多边形：a 线 + b 线反过来（或 closedB 时 b 已经是回程），水平放在 y */
function waterPoly(bk, a, b, y, closedB = false) {
  const ring = closedB ? a.concat(b) : a.concat(b.slice().reverse());
  const sh = new T.Shape(ring.map(p => new T.Vector2(p[0], p[1])));
  const g = new T.ShapeGeometry(sh); const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getY(i); p.setXYZ(i, x, y, z); }
  const nn = []; for (let i = 0; i < p.count; i++) nn.push(0, 1, 0); g.setAttribute('normal', new T.Float32BufferAttribute(nn, 3));
  const idx = g.index.array; for (let i = 0; i < idx.length; i += 3) { const t = idx[i + 1]; idx[i + 1] = idx[i + 2]; idx[i + 2] = t; }   // shape 在 xz 里翻了面
  bk.add(g);
}

/* 地标材质里的天光补光（不是灯：sky 的灯和曝光都不动）。立面朝南偏东，太阳在西北偏西 14° → 整片立面背光，只吃均匀的环境光，
   柱子、线脚、壁龛全是平的。这里按世界法线加一项「西南边亮天和门前铺地的反光」：朝西南、朝上的面亮一些，朝东北的暗；
   乘反照率（壁龛的 AO 顶点色也乘进去），不吃阴影（天光本来就不吃）。uFill 的强度在对照循环里调。 */
const FILL = { uFill: { value: null }, uFillDir: { value: null } };
function withFill(mat, key) {
  mat.onBeforeCompile = s => {
    Object.assign(s.uniforms, FILL);
    s.fragmentShader = 'uniform vec3 uFill;uniform vec3 uFillDir;\n' + s.fragmentShader.replace('#include <opaque_fragment>',
      `{vec3 fd=normalize((viewMatrix*vec4(uFillDir,0.)).xyz);float k=.15+.85*max(dot(normal,fd),0.);outgoingLight+=diffuseColor.rgb*uFill*k;}
      #include <opaque_fragment>`);
  };
  mat.customProgramCacheKey = () => 'cs-nymph-fill-' + key;
  return mat;
}

/* ---------- 贴图（init 里做一次） ---------- */
function revTex(seed) {        // 大理石贴面：2.0×1.35 m 的板（4 m 一张贴图 = 2 列 3 行），细缝 + 淡纹
  return relief(T, 512, 512, (g, R) => {
    rect(g, 0, 0, 512, 512, .6);
    for (let r = 0; r < 3; r++) { const y = r * 171; rect(g, 0, y, 512, 2, .3); for (let x = (r % 2) * 128; x < 512 + 256; x += 256) rect(g, x % 512, y, 2, 171, .3); }
    for (let k = 0; k < 10; k++) { let x = R() * 512, y = R() * 512; const a = R() * 6.28; for (let j = 0; j < 18; j++) { const nx = x + Math.cos(a + Math.sin(j * .7) * .5) * 10, ny = y + Math.sin(a + Math.sin(j * .7) * .5) * 10; line(g, x, y, nx, ny, 1, .56); x = nx; y = ny; } }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: .6, aoR: 3, ao: 1.0, aoMin: .5, low: .04, base: [183, 183, 181], dirt: .07, streak: .03, patina: .2 });
}
function colTex(seed, base, veins) {   // 柱身：竖向波纹（cipollino 的灰绿条纹 / 白大理石）
  return relief(T, 256, 256, (g, R) => {
    rect(g, 0, 0, 256, 256, .5);
    for (let k = 0; k < veins; k++) { const x0 = R() * 256, ph = R() * 6.28, w = 1 + R() * 3; for (let y = 0; y < 256; y += 4) line(g, x0 + Math.sin(y / 40 + ph) * 10, y, x0 + Math.sin((y + 4) / 40 + ph) * 10, y + 4, w, .38); }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 1.5, aoR: 4, ao: 2.2, aoMin: .5, base, dirt: .08, patina: .2 });
}
function brickTex(seed) {      // 砖带石（opus listatum）：5 皮砖 + 一道石，砖色有深浅（4 m 一张）
  const W = 512, cv = document.createElement('canvas'); cv.width = cv.height = W; const g = cv.getContext('2d'), R = rng(seed);
  g.fillStyle = 'rgb(150,140,124)'; g.fillRect(0, 0, W, W);
  const bh = 9, mor = 3; let y = 0, row = 0;
  while (y < W) {
    const stone = row % 6 === 5, h = stone ? 26 : bh;
    for (let x = -(row % 2) * 24; x < W; x += stone ? 70 : 48) {
      const c = stone ? [196, 184, 160] : [150 + R() * 30, 82 + R() * 22, 58 + R() * 14], k = .85 + R() * .2;
      g.fillStyle = `rgb(${c[0] * k | 0},${c[1] * k | 0},${c[2] * k | 0})`; g.fillRect(x + 1, y + 1, (stone ? 70 : 48) - mor, h - 1);
    }
    y += h + mor; row++;
  }
  const map = new T.CanvasTexture(cv); map.colorSpace = T.SRGBColorSpace; map.wrapS = map.wrapT = T.RepeatWrapping; map.anisotropy = 4;
  const nrm = relief(T, W, W, (h) => { h.drawImage(cv, 0, 0); }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 2.5 }).normalMap;
  return { map, normalMap: nrm };
}
function fallTex() {           // 水帘：竖向亮条（alpha），tick 里往下滚
  const W = 64, H = 256, cv = document.createElement('canvas'); cv.width = W; cv.height = H; const g = cv.getContext('2d'), R = rng(7);
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  for (let k = 0; k < 40; k++) { const x = R() * W, w = 1 + R() * 4, a = .35 + R() * .6; g.fillStyle = `rgba(255,255,255,${a})`; g.fillRect(x, 0, w, H); }
  for (let k = 0; k < 60; k++) { g.fillStyle = `rgba(255,255,255,${.3 + R() * .5})`; g.fillRect(R() * W, R() * H, 2 + R() * 6, 6 + R() * 20); }
  const t = new T.CanvasTexture(cv); t.wrapS = t.wrapT = T.RepeatWrapping; return t;
}
/* 池水：MeshPhong + onBeforeCompile（同 water 模块的路子：灯、雾、色调映射都走 three），注入细浪法线、菲涅尔天光、太阳尖亮点；颜色取港池绿偏清 */
function waterMat(ctx) {
  const mat = new T.MeshPhongMaterial({ color: 0x3f6f68, specular: 0x8a8a80, shininess: 160 });
  WU = { uT: { value: 0 }, uSkyLo: { value: new T.Color(0xd6d2c4) }, uSkyHi: { value: new T.Color(0x8fb0c4) } };
  mat.onBeforeCompile = s => {
    Object.assign(s.uniforms, WU);
    s.vertexShader = 'varying vec3 vWP;\n' + s.vertexShader.replace('#include <project_vertex>', '#include <project_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;');
    s.fragmentShader = 'varying vec3 vWP;uniform float uT;uniform vec3 uSkyLo,uSkyHi;vec3 nW;\n' + s.fragmentShader
      .replace('#include <normal_fragment_maps>', `{vec2 p=vWP.xz;float a=sin(p.x*2.1+uT*1.7)+sin(p.y*2.7-uT*1.3)+.6*sin((p.x+p.y)*4.3+uT*2.3)+.4*sin((p.x-p.y)*7.1-uT*3.1);
        float b=cos(p.x*2.1+uT*1.7)*2.1+.6*cos((p.x+p.y)*4.3+uT*2.3)*4.3+.4*cos((p.x-p.y)*7.1-uT*3.1)*7.1, c=cos(p.y*2.7-uT*1.3)*2.7+.6*cos((p.x+p.y)*4.3+uT*2.3)*4.3-.4*cos((p.x-p.y)*7.1-uT*3.1)*7.1;
        nW=normalize(vec3(-b*.035,1.,-c*.035));normal=normalize((viewMatrix*vec4(nW,0.)).xyz);}`)
      .replace('#include <opaque_fragment>', `{vec3 V=normalize(cameraPosition-vWP);float F=.04+.96*pow(1.-max(dot(nW,V),0.),5.);vec3 R=reflect(-V,nW);
        outgoingLight=mix(outgoingLight,mix(uSkyLo,uSkyHi,smoothstep(0.,.5,R.y))*.8,clamp(F,0.,.6));}
        #include <opaque_fragment>`);
  };
  mat.customProgramCacheKey = () => 'cs-nymph-water-1';
  return mat;
}

export function init(ctx) {
  T = ctx.THREE;
  const f = (ctx.by.landmark || []).find(x => x.id === id), seed = f ? f.seed : 1;
  const t0 = performance.now();
  const rv = revTex(seed), ca = colTex(seed + 1, [198, 200, 190], 12), cb = colTex(seed + 2, [210, 205, 194], 5), bk = brickTex(seed + 3);
  for (const t of [rv.map, rv.normalMap]) t.repeat.set(.25, .25);
  FALL_TEX = fallTex();
  FILL.uFill.value = new T.Color(0.22, 0.235, 0.25); FILL.uFillDir.value = new T.Vector3(-0.55, 0.5, 0.67).normalize();   // 西南偏上（x 东、z 南）
  M = {
    rev: withFill(new T.MeshLambertMaterial({ map: rv.map, normalMap: rv.normalMap, vertexColors: true, side: T.DoubleSide }), 'rev'),
    colA: withFill(new T.MeshLambertMaterial({ map: ca.map, normalMap: ca.normalMap, vertexColors: true }), 'colA'),
    colB: withFill(new T.MeshLambertMaterial({ map: cb.map, normalMap: cb.normalMap, vertexColors: true }), 'colB'),
    orn: withFill(new T.MeshLambertMaterial({ map: rv.map, vertexColors: true, side: T.DoubleSide }), 'orn'),
    brick: withFill(new T.MeshLambertMaterial({ map: bk.map, normalMap: bk.normalMap, vertexColors: true, side: T.DoubleSide }), 'brick'),
    statue: withFill(new T.MeshLambertMaterial({ color: 0xdcd6ca, vertexColors: true }), 'statue'),
    water: waterMat(ctx),
    fall: new T.MeshLambertMaterial({ color: 0xf2f6f4, emissive: 0x56605e, alphaMap: FALL_TEX, transparent: true, opacity: .85, depthWrite: false, side: T.DoubleSide }),
  };
  if (ctx.QS.has('lmmask')) { const mk = new T.MeshBasicMaterial({ color: 0xff00ff, fog: false, toneMapped: false, side: T.DoubleSide }); for (const k in M) M[k] = mk; }
  M._tex_ms = Math.round(performance.now() - t0);
}

export function build(ctx, f, r, b, F) {
  if (ctx.year < f.y0) return null;
  if (!CACHE) {
    if (F) DEPTH = Math.max(3, (b - F.min + 0.6) / K);         // 像素 → 米（K = 1/0.84）
    const t0 = performance.now();
    const lod = new T.LOD(); lod.name = 'nymphaeum-lod';
    lod.addLevel(buildGroup(false), 0); lod.addLevel(buildGroup(true), LOD_FAR);
    lod.rotation.y = Math.atan2(-r.az, r.ax);                 // 局部 x → (ax, az)，局部 z → (−az, ax)
    CACHE = { lod, ms: Math.round(performance.now() - t0) };
  }
  CACHE.lod.position.set(r.cx, b, r.cz);
  return CACHE.lod;
}
/* ground_check：最低的面（台基、池栏台阶）到哪 */
export function bottomOf(b, F) { return Math.min(b - 3 * K, F.min - 0.6); }
export function tick(ctx, t) {
  if (WU) WU.uT.value = t;
  if (FALL_TEX) FALL_TEX.offset.y = (t * 1.6) % 1;
}
export function stats() {
  if (!CACHE) return null;
  const [near, far] = CACHE.lod.levels.map(l => tri(l.object));
  return { near_tris: near, far_tris: far, geom_build_ms: CACHE.ms, tex_ms: M._tex_ms, height_m: Y.attic, hero_scale: HERO_SCALE, depth_m: +DEPTH.toFixed(2), width_m: 2 * PLAN.half + 2 * PLAN.pylonW + .6 };
}
export function dispose() { /* 几何缓存着（不随年份变） */ }
