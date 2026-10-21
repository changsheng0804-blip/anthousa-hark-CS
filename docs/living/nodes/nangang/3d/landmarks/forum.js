/* landmark 第 3 座 · 狄奥多西广场（Forum of Theodosius / Forum Tauri）：铺地广场 + 四面两层柱廊 + 西侧凯旋门 + 东门 + 南北小门 + 施工阶段。——Hark（CS线）2026-10-20
   中间的纪功柱归 column.js（同一个地标 id forum_theodosius，index.js 现在允许一个 id 挂几个文件），这里不画柱子。
   底账（只照用）：
   - nodes.json 地标 forum_theodosius：k=forum，y0=57，四角 [1365,256]–[1507,370]（142×114 px ≈ 119×96 m）；
     主街 Mese（k=m，w 15）从西边 z≈311 进、东边 z≈297 出，广场里那几段 y1=57（被广场吃掉）；南北向小街 c 在 x=1444，也是 y1=57。
   - proposals/era_0051.json 的 phases：57「划出广场」· 59「铺地，四面柱廊起墙」· 60「西侧凯旋门落成」· 64「纪功柱立到顶，广场完工」。
     dna：motif peristyle（四面柱廊围院）、marble_revetted、ornament 3、monumental。
   史料（形制；出处见 docs/cs/lookdev/landmarks/forum/notes.md）：狄奥多西 393 年仿罗马图拉真广场重建陶里广场；西侧（Mese 进城方向）一座普罗科奈索斯大理石三门凯旋门，
   中门约 7 m 宽、比两侧门高，四个墩子每个是 4 根束柱，柱子雕成赫拉克勒斯的棍棒（树干状，有「泪滴 / 孔雀眼」纹），其中几根柱头下有握拳；
   顶上中间狄奥多西像、两边阿卡狄乌斯和霍诺留像。东西两个主入口（Columbia 的 Istanbul Documentation Project 说两头各一座凯旋门；底账只写西门 → 东边只做一座柱廊门楼）。
   假设（都写在 notes.md，可推翻）：柱廊两层（下层科林斯柱 + 上层矮柱和栏板），进深 11 px ≈ 9.2 m，柱距 3.2 m；外墙砖带石，下层每两开间一个铺面门洞、上层拱窗；
   单坡瓦顶朝院子；南北两侧在小街 c 的位置各开一个拱门；凯旋门总宽 28.2 m（侧门 4.2 m，第 2 轮按参考的宽高比放宽）、深 4 m、到女儿墙顶 23.4 m、雕像 4.2 / 3.6 m（复用纪功柱的烘焙像）。
   史诗夸张（MODULE_CONTRACT §7）：凯旋门整座 ×HERO_SCALE 1.4（同纪功柱，占地是这里假设的，不是底账）；柱廊只放大高 ×PORTICO_SCALE 1.2（同改前 buildings 的 LM_SCALE.forum），占地照底账。
   落地（§6 第 13 条）：每翼按 ≤ 30 px 分段，每段 ctx.footing → 地坪 = max、台基伸到 min − 0.6，ctx.foot 登记；凯旋门、东门、角墩各自落地。
   结构：完工（≥ 64 年）的几何不随年份变，建一次缓存成 THREE.LOD（近 / 远，LOD_FAR 像素）；57–63 年每次按年份新建（施工中，只一档）。?lmmask=1 全换品红。
   确定性：随机只用 ctx.hsh / 底账 seed。 */
import { lathe, merge } from './kit/lathe.js';
import { relief, rng, rect, line, ell, garland } from './kit/relief.js';
import { corinthian } from './kit/acanthus.js';
import { loadBaked, geoOf } from './kit/baked.js';
import { clubColumn } from './kit/club.js';
import { makeFill } from './kit/fill.js';

const STATUE_LO = await loadBaked(new URL('./column/statue_lo.bin', import.meta.url));

export const id = 'forum_theodosius';
export const key = 'forum_theodosius:forum';                 // __landmarkStats 里的键（纪功柱占着 forum_theodosius）
export const selfFoot = true;                                 // 落地自己分段登记，index.js 不替它算整块占地
export const PHASE = { site: 57, frame: 59, arch: 60, done: 64 };   // proposals/era_0051.json
export const HERO_SCALE = 1.4, PORTICO_SCALE = 1.2;
const K = 1 / 0.84, LOD_FAR = 600;
/* 平面（页面像素）：柱廊进深 D、外墙厚 WT、柱心离院边 DC、柱距 BAY；入口位置（沿各翼的 s） */
const D = 11, WT = 0.9 * K, DC = 1.25, BAY = 3.2 * K, SEG = 30;
const MESE_W = 311 - 313, MESE_E = 297 - 313, LANE_C = 1444 - 1436;   // 相对广场中心 (1436, 313)：西口 v、东口 v、小街 c 的 u（底账街线）
/* 柱廊高（米，实际比例 × PORTICO_SCALE → 像素） */
const PM = m => m * PORTICO_SCALE * K;
const Y = { c1: PM(6.0), e1: PM(6.9), par: PM(8.0), c2: PM(11.3), e2: PM(12.0), roof: PM(13.8), wall: PM(14.1) };
const R1 = 0.5 * K, R2 = 0.4 * K;                            // 下 / 上层柱半径（不放大：只放大高）
/* 凯旋门（米，局部：x 横跨 = 沿西翼，z = 进深，y 向上；整组 × K × HERO_SCALE） */
const AR = { inner: 5.1, outer: 12.5, half: 14.1, depth: 2.0, ped: 2.2, col: 9.6, imp: 13.0, attic0: 19.0, attic1: 22.0, top: 22.5, mid: 23.4, cr: 3.5, sr: 2.1, colR: 0.42, colGap: 0.75 };
const ARCH_HALF_PX = AR.half * K * HERO_SCALE + 0.6;

let T = null, M = null, CACHE = null, FILL = null, LAST = { near: 0, far: 0, ms: 0 };

/* ---------------- 几何小工具 ---------------- */
/* 自动定向的三角形收集器：每个面给一个「朝外」方向，绕序按它定（不怕坐标系左右手） */
class GB {
  constructor() { this.p = []; }
  tri(a, b, c, out) {
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    if (nx * out[0] + ny * out[1] + nz * out[2] < 0) this.p.push(...a, ...c, ...b); else this.p.push(...a, ...b, ...c);
  }
  quad(a, b, c, d, out) { this.tri(a, b, c, out); this.tri(a, c, d, out); }
  geo() { const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(this.p, 3)); g.computeVertexNormals(); return g; }
}
/* 世界 UV：按法线主轴投影（米制贴图：一张 = tile 像素） */
function worldUV(g, tile) {
  const p = g.attributes.position, n = g.attributes.normal, U = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
    let u, v; if (ay >= ax && ay >= az) { u = x; v = z; } else if (ax >= az) { u = z; v = y; } else { u = x; v = y; }
    U[i * 2] = u / tile; U[i * 2 + 1] = v / tile;
  }
  g.setAttribute('uv', new T.BufferAttribute(U, 2)); return g;
}
/* 翼的坐标架：P(s,d) = O + t·s + n·d（n 指离开院子；d=0 是院边，d=D 是外墙外皮） */
const frame = (O, t, n) => ({ O, t, n, P: (s, d) => [O[0] + t[0] * s + n[0] * d, O[1] + t[1] * s + n[1] * d] });
const V3 = (F, s, d, y) => { const q = F.P(s, d); return [q[0], y, q[1]]; };
const OUT = (F, ts, nd, y = 0) => [F.t[0] * ts + F.n[0] * nd, y, F.t[1] * ts + F.n[1] * nd];
function boxF(gb, F, s0, s1, d0, d1, y0, y1, faces = 'all') {
  const c = (s, d, y) => V3(F, s, d, y);
  const A = c(s0, d0, y0), B = c(s1, d0, y0), C = c(s1, d1, y0), Dd = c(s0, d1, y0), A2 = c(s0, d0, y1), B2 = c(s1, d0, y1), C2 = c(s1, d1, y1), D2 = c(s0, d1, y1);
  gb.quad(A2, B2, C2, D2, [0, 1, 0]);
  if (faces === 'all') gb.quad(A, B, C, Dd, [0, -1, 0]);
  gb.quad(A, B, B2, A2, OUT(F, 0, -1)); gb.quad(Dd, C, C2, D2, OUT(F, 0, 1));
  gb.quad(A, Dd, D2, A2, OUT(F, -1, 0)); gb.quad(B, C, C2, B2, OUT(F, 1, 0));
}
/* 剖面（[[a, y], …] 闭合多边形，a 沿方向 A）沿方向 E 从 e0 拉到 e1：线脚、檐部、山花 */
function prism(gb, O, A, E, prof, e0, e1, y0 = 0, caps = true) {
  const W = (a, e, y) => [O[0] + A[0] * a + E[0] * e, y0 + y, O[1] + A[1] * a + E[1] * e];
  let ar = 0; for (let i = 0; i < prof.length; i++) { const p = prof[i], q = prof[(i + 1) % prof.length]; ar += p[0] * q[1] - q[0] * p[1]; }
  const sg = ar > 0 ? 1 : -1;
  for (let i = 0; i < prof.length; i++) {
    const p = prof[i], q = prof[(i + 1) % prof.length], na = (q[1] - p[1]) * sg, ny = -(q[0] - p[0]) * sg;
    gb.quad(W(p[0], e0, p[1]), W(q[0], e0, q[1]), W(q[0], e1, q[1]), W(p[0], e1, p[1]), [A[0] * na, ny, A[1] * na]);
  }
  if (caps) {
    const tris = T.ShapeUtils.triangulateShape(prof.map(p => new T.Vector2(p[0], p[1])), []);
    for (const [i, j, k] of tris) for (const [e, s] of [[e0, -1], [e1, 1]]) gb.tri(W(prof[i][0], e, prof[i][1]), W(prof[j][0], e, prof[j][1]), W(prof[k][0], e, prof[k][1]), [E[0] * s * Math.sign(e1 - e0), 0, E[1] * s * Math.sign(e1 - e0)]);
  }
}
/* 墙片：Shape（s, y）带洞 → 拉厚 thick（沿 n，从 d0 起）。ExtrudeGeometry 出来后搬进世界坐标，按左右手翻绕序 */
function wallShape(F, sh, d0, thick, curve = 5) {
  const g = new T.ExtrudeGeometry(sh, { depth: thick, bevelEnabled: false, curveSegments: curve });
  if (g.index) { const g2 = g.toNonIndexed(); g.dispose(); return wallShapeNI(F, g2, d0); }
  return wallShapeNI(F, g, d0);
}
function wallShapeNI(F, g, d0) {
  const p = g.attributes.position, det = F.t[0] * F.n[1] - F.t[1] * F.n[0];   // (t, up, n) 的手性
  for (let i = 0; i < p.count; i++) { const s = p.getX(i), y = p.getY(i), d = d0 + p.getZ(i), q = F.P(s, d); p.setXYZ(i, q[0], y, q[1]); }
  if (det < 0) { const a = p.array; for (let i = 0; i < a.length; i += 9) for (let k = 0; k < 3; k++) { const t = a[i + 3 + k]; a[i + 3 + k] = a[i + 6 + k]; a[i + 6 + k] = t; } }
  g.deleteAttribute('normal'); g.deleteAttribute('uv'); g.clearGroups(); g.computeVertexNormals();
  return g;
}
/* 墙片拆成两份：朝院子的那面（法线 · (−n) > 0.7）单独给内墙灰泥，其余（外皮、洞口侧壁、顶）留给外墙材质 */
function splitInner(F, g) {
  const p = g.attributes.position.array, n = g.attributes.normal.array, A = [], Bq = [];
  for (let i = 0; i < p.length; i += 9) { const dn = -(n[i] * F.n[0] + n[i + 2] * F.n[1]); (dn > 0.7 ? A : Bq).push(...p.slice(i, i + 9)); }
  const mk = P => { const q = new T.BufferGeometry(); q.setAttribute('position', new T.Float32BufferAttribute(P, 3)); q.computeVertexNormals(); return q; };
  g.dispose(); return [mk(A), mk(Bq)];
}
const archHole = (cx, w, y0, ys) => { const p = new T.Path(), r = w / 2; p.moveTo(cx - r, y0); p.lineTo(cx + r, y0); p.lineTo(cx + r, ys); p.absarc(cx, ys, r, 0, Math.PI, false); p.lineTo(cx - r, y0); return p; };
const rectHole = (cx, w, y0, y1) => { const p = new T.Path(); p.moveTo(cx - w / 2, y0); p.lineTo(cx + w / 2, y0); p.lineTo(cx + w / 2, y1); p.lineTo(cx - w / 2, y1); p.lineTo(cx - w / 2, y0); return p; };

/* 柱子（局部原点 = 柱础底面中心）：阿提卡柱础 + 收分柱身 + 科林斯柱头（钟形 + 顶板） */
function colGeo(r, h, segs, far) {
  const capH = r * 2.3, b = r * 0.8, sh = h - capH;
  const prof = far ? [[r * 1.25, 0], [r * 1.25, b * .5], [r, b]] : [[r * 1.28, 0], [r * 1.28, b * .25], [r * 1.18, b * .32], [r * 1.24, b * .5], [r * 1.1, b * .62], [r * 1.05, b * .72], [r * 1.12, b * .86], [r * 1.0, b]];
  const nk = far ? 1 : 4;
  for (let k = 0; k <= nk; k++) { const t = k / nk; prof.push([r * (1 - 0.13 * Math.pow(t, 1.3)), b + (sh - b) * t]); }
  if (!far) prof.push([r * 0.95, sh + r * .06], [r * 0.95, sh + r * .14], [r * 0.87, sh + r * .16]);
  const shaft = lathe(T, prof, segs, { v: y => y / 2 });
  const parts = [shaft];
  if (far) { const g = new T.BoxGeometry(r * 2.6, capH * .5, r * 2.6); g.translate(0, sh + capH * .75, 0); parts.push(g); }
  else { const cap = corinthian(T, { r: r * 0.87, h: capH - r * .16, a: r * 1.45, seed: 9, lod: 'far' }); cap.translate(0, sh + r * .16, 0); parts.push(cap); }
  return merge(T, parts);
}

/* ---------------- 贴图 ---------------- */
function marbleTex(seed) {     // 普罗科奈索斯大理石：灰白、带淡灰纹，砌块 1.2 m 一皮（一张 = 4.8 m）
  return relief(T, 512, 512, (g, R) => {
    rect(g, 0, 0, 512, 512, .6);
    for (let r = 0; r < 4; r++) { const y = r * 128; rect(g, 0, y, 512, 2, .32); for (let x = (r % 2) * 96; x < 512 + 192; x += 192) rect(g, x % 512, y, 2, 128, .32); }
    for (let k = 0; k < 14; k++) { let x = R() * 512, y = R() * 512; const a = R() * 6.28; for (let j = 0; j < 20; j++) { const nx = x + Math.cos(a + Math.sin(j * .6) * .6) * 9, ny = y + Math.sin(a + Math.sin(j * .6) * .6) * 9; line(g, x, y, nx, ny, 1, .55); x = nx; y = ny; } }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: .8, aoR: 3, ao: 1.0, aoMin: .5, low: .04, base: [178, 175, 168], dirt: .08, streak: .05, patina: .25 });
}
function wallTex(seed) {       // 外墙：砖带石（opus listatum）+ 白灰缝，一张 = 4.8 m
  const W = 512, cv = document.createElement('canvas'); cv.width = cv.height = W; const g = cv.getContext('2d'), R = rng(seed);
  g.fillStyle = 'rgb(176,166,146)'; g.fillRect(0, 0, W, W);
  let y = 0, row = 0;
  while (y < W) {
    const stone = (row % 7) >= 5, h = stone ? 22 : 9;
    for (let x = -(row % 2) * 26; x < W; x += stone ? 64 : 46) {
      const c = stone ? [188 + R() * 18, 178 + R() * 16, 154 + R() * 14] : [150 + R() * 30, 80 + R() * 22, 58 + R() * 14], k = .86 + R() * .18;
      g.fillStyle = `rgb(${c[0] * k | 0},${c[1] * k | 0},${c[2] * k | 0})`; g.fillRect(x + 1, y + 1, (stone ? 64 : 46) - 3, h - 1);
    }
    y += h + 3; row++;
  }
  const map = new T.CanvasTexture(cv); map.colorSpace = T.SRGBColorSpace; map.wrapS = map.wrapT = T.RepeatWrapping; map.anisotropy = 4;
  const nrm = relief(T, W, W, (h) => { h.drawImage(cv, 0, 0); }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 2.2 }).normalMap;
  return { map, normalMap: nrm };
}
function roofTex(seed) {       // 筒瓦：竖向的盖瓦脊 + 横向的搭接缝（一张 = 4.8 m）
  return relief(T, 256, 256, (g, R) => {
    rect(g, 0, 0, 256, 256, .35);
    for (let x = 0; x < 256; x += 16) { rect(g, x + 4, 0, 8, 256, .85); }
    for (let y = 0; y < 256; y += 32) rect(g, 0, y, 256, 3, .15);
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 3, aoR: 3, ao: 2, aoMin: .5, base: [176, 92, 60], dirt: .15, patina: .2 });
}
function colTex(seed) {        // 柱身：白大理石竖纹
  return relief(T, 256, 256, (g, R) => {
    rect(g, 0, 0, 256, 256, .5);
    for (let k = 0; k < 6; k++) { const x0 = R() * 256, ph = R() * 6.28, w = 1 + R() * 2; for (let y = 0; y < 256; y += 4) line(g, x0 + Math.sin(y / 40 + ph) * 8, y, x0 + Math.sin((y + 4) / 40 + ph) * 8, y + 4, w, .4); }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 1.2, aoR: 4, ao: 2, aoMin: .55, base: [206, 201, 190], dirt: .07, patina: .2 });
}
function clubTex(seed) {       // 棍棒柱：错开排的泪滴（孔雀眼）+ 树皮竖纹（u 绕一圈，v = y / 4r）
  return relief(T, 256, 256, (g, R) => {
    rect(g, 0, 0, 256, 256, .45);
    for (let k = 0; k < 18; k++) { const x0 = R() * 256; for (let y = 0; y < 256; y += 6) line(g, x0 + Math.sin(y / 30 + k) * 4, y, x0 + Math.sin((y + 6) / 30 + k) * 4, y + 6, 1.5, .35); }
    for (let r = 0; r < 4; r++) for (let i = 0; i < 6; i++) {
      const x = (i + (r % 2) * .5) * 256 / 6, y = r * 64 + 32;
      for (const dx of [-256, 0, 256]) { ell(g, x + dx, y, 11, 17, .9); ell(g, x + dx, y - 15, 5, 7, .85); ell(g, x + dx, y + 2, 5, 7, .3); }
    }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 5, aoR: 4, ao: 3, aoMin: .42, low: .1, base: [190, 184, 172], dirt: .1, patina: .3 });
}
function atticTex(seed) {      // 凯旋门女儿墙：中间一块题额 + 两边胜利女神 + 花环（一张 = 整个女儿墙正面）
  return relief(T, 1024, 256, (g, R) => {
    rect(g, 0, 0, 1024, 256, .55);
    rect(g, 330, 40, 364, 176, .8); rect(g, 346, 56, 332, 144, .45);
    for (let i = 0; i < 4; i++) rect(g, 372, 78 + i * 30, 280 - (i % 2) * 40, 12, .7);    // 题字的行（不写字，只是凸起的条）
    for (const cx of [180, 844]) {                            // 月桂花环 + 飘带（不用胜利女神：这个尺度上读成怪符号）
      for (let k = 0; k < 28; k++) { const a = k / 28 * Math.PI * 2; ell(g, cx + Math.cos(a) * 62, 128 + Math.sin(a) * 62, 13, 7, .85); }
      line(g, cx - 20, 190, cx - 60, 240, 7, .75); line(g, cx + 20, 190, cx + 60, 240, 7, .75);
    }
    garland(g, R, 30, 300, 14, 26, 4, .8); garland(g, R, 724, 994, 14, 26, 4, .8);
  }, { seed, blur: 1, strength: 8, aoR: 6, ao: 3.5, aoMin: .38, low: .15, base: [170, 166, 158], dirt: .1, streak: .06, patina: .3 });
}

export function init(ctx) {
  T = ctx.THREE;
  const f = (ctx.by.landmark || []).find(x => x.id === id), seed = (f ? f.seed : 1) + 101;
  const t0 = performance.now();
  FILL = makeFill(T, { tag: 'forum' });
  const mb = marbleTex(seed), wl = wallTex(seed + 1), rf = roofTex(seed + 2), cl = colTex(seed + 3), cb = clubTex(seed + 4), at = atticTex(seed + 5);
  const L = (o, k) => FILL(new T.MeshLambertMaterial(o), k);
  M = {
    marble: L({ map: mb.map, normalMap: mb.normalMap, color: 0xb3b0a8, side: T.DoubleSide }, 'marble'),
    wall: L({ map: wl.map, normalMap: wl.normalMap, color: 0xb4a894, side: T.DoubleSide }, 'wall'),
    roof: L({ map: rf.map, normalMap: rf.normalMap, side: T.DoubleSide }, 'roof'),
    col: L({ map: cl.map, normalMap: cl.normalMap, color: 0xe2dccf }, 'col'),
    club: L({ map: cb.map, normalMap: cb.normalMap, color: 0xbcb9b0 }, 'club'),
    attic: L({ map: at.map, normalMap: at.normalMap, color: 0xb9b6ae }, 'attic'),
    ceil: new T.MeshLambertMaterial({ color: 0x8a7f6e, side: T.DoubleSide }),
    inner: L({ map: mb.map, color: 0xb88e6c, side: T.DoubleSide }, 'inner'),   // 柱廊里的内墙：赭色灰泥（假设），好让白柱子跳出来
    statue: new T.MeshPhongMaterial({ color: 0x6f6658, specular: 0x4a443a, shininess: 22 }),   // 青铜，风化暗色（假设）
    timber: new T.MeshLambertMaterial({ color: 0x7b5b3c }),
    rope: new T.MeshLambertMaterial({ color: 0xc9b48a }),
    stone: new T.MeshLambertMaterial({ color: 0xcfc6b2 }),
    dirt: new T.MeshLambertMaterial({ color: 0x9c8462, side: T.DoubleSide, polygonOffset: true, polygonOffsetFactor: -8, polygonOffsetUnits: -16 }),
    far: L({ map: mb.map, color: 0xb3b0a8, side: T.DoubleSide }, 'far'),
    farWall: L({ map: wl.map, color: 0xb4a894, side: T.DoubleSide }, 'farWall'),
  };
  for (const k of ['marble', 'wall', 'roof', 'far', 'farWall']) { for (const t of [M[k].map, M[k].normalMap]) if (t) t.repeat.set(1, 1); }
  if (ctx.QS.has('lmmask')) { const mk = new T.MeshBasicMaterial({ color: 0xff00ff, fog: false, toneMapped: false, side: T.DoubleSide }); for (const k in M) M[k] = mk; }
  M._tex_ms = Math.round(performance.now() - t0);
}

/* ---------------- 平面：四翼、入口、分段落地 ---------------- */
function wings(r) {
  const C = (u, v) => [r.cx + r.ax * u - r.az * v, r.cz + r.az * u + r.ax * v], U = [r.ax, r.az], Vv = [-r.az, r.ax], neg = a => [-a[0], -a[1]];
  const hu = r.hu, hv = r.hv;
  /* N/S 翼占满长边（含两个角），两端封山墙；E/W 翼夹在中间 */
  return [
    { k: 'N', F: frame(C(0, -hv + D), U, neg(Vv)), s0: -hu, s1: hu, ends: true, court: [-hu + D, hu - D], gaps: [], doors: [LANE_C] },
    { k: 'S', F: frame(C(0, hv - D), U, Vv), s0: -hu, s1: hu, ends: true, court: [-hu + D, hu - D], gaps: [], doors: [LANE_C] },
    { k: 'W', F: frame(C(-hu + D, 0), Vv, neg(U)), s0: -hv + D, s1: hv - D, ends: false, court: [-hv + D, hv - D], gaps: [[MESE_W - ARCH_HALF_PX, MESE_W + ARCH_HALF_PX, 'arch']], doors: [] },
    { k: 'E', F: frame(C(hu - D, 0), Vv, U), s0: -hv + D, s1: hv - D, ends: false, court: [-hv + D, hv - D], gaps: [[MESE_E - 7, MESE_E + 7, 'gate']], doors: [] },
  ];
}
function colPositions(w) {
  const a = w.court[0] - DC, b = w.court[1] + DC, n = Math.max(2, Math.round((b - a) / BAY)), out = [];
  for (let k = 1; k < n; k++) { const s = a + (b - a) * k / n; if (w.gaps.some(([g0, g1]) => s > g0 - .9 && s < g1 + .9)) continue; out.push(s); }
  return out;
}
function pieces(w) {             // 一翼去掉门洞后的几段 [s0, s1, 左端封墙?, 右端封墙?]
  const out = []; let a = w.s0, capA = w.ends;
  for (const [g0, g1] of w.gaps) { out.push([a, g0, capA, true]); a = g1; capA = true; }
  out.push([a, w.s1, capA, w.ends]); return out.filter(p => p[1] - p[0] > 2);
}

/* 一段柱廊（地坪 y、台基底 bot）。stage：0 = 59 年（台基 + 墙起 45%）… 5 = 完工；far = 远档 */
function porticoSeg(B, w, s0, s1, y, bot, capA, capB, stage, far, cols, scaff) {
  const F = w.F, done = stage >= 5;
  /* 台基：院子一侧两级台阶，外侧竖直墙基 */
  boxF(B.marble, F, s0, s1, 0, D, bot, y);
  boxF(B.marble, F, s0, s1, -0.55, 0, bot, y - 0.32); boxF(B.marble, F, s0, s1, -1.1, -0.55, bot, y - 0.64);
  /* 外墙：下层铺面门洞（每两开间）、上层拱窗；南北翼在小街 c 处开拱门 */
  const wallTop = [Y.e1 * .45, Y.e1, (Y.e1 + Y.wall) / 2, Y.wall - PM(1.2), Y.wall, Y.wall][Math.min(stage, 5)];
  const sh = new T.Shape(); sh.moveTo(s0, 0); sh.lineTo(s1, 0); sh.lineTo(s1, wallTop); sh.lineTo(s0, wallTop); sh.lineTo(s0, 0);
  if (!far) {
    const n = Math.floor((s1 - s0) / BAY);
    for (let i = 0; i < n; i++) {
      const cx = s0 + (s1 - s0) * (i + .5) / n;
      if (w.doors.some(dc => Math.abs(cx - dc) < BAY * 1.2)) continue;
      if (i % 2 === 0 && wallTop > PM(3.6) + .3) sh.holes.push(archHole(cx, 1.7 * K, PM(0.25), PM(2.6)));     // 铺面门洞（每两开间）
      else if (wallTop > PM(4.6) + .3) sh.holes.push(rectHole(cx, 1.0 * K, PM(2.6), PM(4.0)));               // 高窗
      if (wallTop > PM(11.6) + .3) sh.holes.push(archHole(cx, 1.6 * K, PM(8.3), PM(10.2)));                   // 上层拱窗（每开间）
    }
    for (const dc of w.doors) if (dc - 2.2 * K > s0 && dc + 2.2 * K < s1 && wallTop > PM(5.2)) sh.holes.push(archHole(dc, 3.2 * K, .05, PM(3.6)));
  }
  const wg = wallShape(F, sh, D - WT, WT, far ? 2 : 5); wg.translate(0, y, 0); const [wi, wo] = splitInner(F, wg); B.wallG.push(wo); B.innerG.push(wi);
  if (wallTop > Y.e1 + .5) { boxF(B.marble, F, s0, s1, D - .02, D + .28, y + Y.e1 - .45, y + Y.e1 - .05); boxF(B.marble, F, s0, s1, D - .02, D + .2, y - .02, y + .55); }   // 外墙腰线、墙脚石
  /* 端墙（门洞旁、N/S 两头）：从院边到外墙，整高 */
  for (const [cap, s, dir] of [[capA, s0, 1], [capB, s1, -1]]) if (cap) {
    const e0 = dir > 0 ? s : s - WT, e1 = dir > 0 ? s + WT : s;
    if (done) prism(B.wall, F.P(0, 0), F.n, F.t, [[0, 0], [D - WT, 0], [D - WT, Y.wall], [0, Y.e2 + .4]], e0, e1, y);   // 完工：顶顺着单坡屋面
    else boxF(B.wall, F, e0, e1, 0, D - WT, y, y + wallTop);
  }
  /* 柱子：只在院子那一段（court）里，角上让给角墩 */
  /* 柱位按整翼统一排（院子两角之间等分，角上让给角墩），这一段只取落在 [s0, s1) 里、离端墙 ≥ 0.9 px 的 */
  if (stage >= 1) for (const s of w.colS) {
    if (s < s0 || s >= s1) continue;
    if ((capA && s - s0 < 0.9) || (capB && s1 - s < 0.9)) continue;
    const q = F.P(s, DC); cols.c1.push([q[0], y, q[1]]); if (stage >= 3) cols.c2.push([q[0], y + Y.e1, q[1]]);
  }
  /* 下层檐部 + 二层楼板 */
  if (stage >= 2) {
    const ent = [[DC - .62, Y.c1], [DC + .62, Y.c1], [DC + .62, Y.e1 - .35], [DC + .8, Y.e1 - .2], [DC + .8, Y.e1], [DC - .85, Y.e1], [DC - .85, Y.e1 - .18], [DC - .7, Y.e1 - .32], [DC - .7, Y.c1 + (Y.e1 - Y.c1) * .55], [DC - .66, Y.c1 + (Y.e1 - Y.c1) * .55], [DC - .66, Y.c1 + (Y.e1 - Y.c1) * .25], [DC - .62, Y.c1 + (Y.e1 - Y.c1) * .25]];
    prism(B.marble, F.P(0, 0), F.n, F.t, ent, s0, s1, y);
    boxF(B.ceil, F, s0, s1, DC + .62, D - WT, y + Y.e1 - .7, y + Y.e1 - .05, 'all');
    /* 上层栏板（柱间矮墙） */
    if (stage >= 3) boxF(B.marble, F, s0, s1, DC - .18, DC + .18, y + Y.e1, y + Y.par);
  }
  /* 上层檐部 + 单坡屋顶（朝院子） */
  if (stage >= 4) {
    const e2 = [[DC - .5, Y.c2], [DC + .5, Y.c2], [DC + .5, Y.e2], [DC - .72, Y.e2], [DC - .72, Y.e2 - .2], [DC - .56, Y.e2 - .32], [DC - .56, Y.c2 + .2], [DC - .5, Y.c2 + .2]];
    prism(B.marble, F.P(0, 0), F.n, F.t, e2, s0, s1, y);
    const a = DC - .95, b = D + .35, ya = y + Y.e2 + .05, yb = y + Y.roof;
    if (stage >= 5) {
      const g = new GB(), p = (s, d, yy) => V3(F, s, d, yy), up = OUT(F, 0, -(yb - ya) / (b - a), 1);
      g.quad(p(s0, a, ya), p(s1, a, ya), p(s1, b, yb), p(s0, b, yb), up);
      g.quad(p(s0, a, ya - .3), p(s1, a, ya - .3), p(s1, b, yb - .3), p(s0, b, yb - .3), [-up[0], -up[1], -up[2]]);
      g.quad(p(s0, a, ya - .3), p(s1, a, ya - .3), p(s1, a, ya), p(s0, a, ya), OUT(F, 0, -1));
      for (const [s, dir] of [[s0, -1], [s1, 1]]) g.tri(p(s, a, ya), p(s, b, yb), p(s, b, yb - .3), OUT(F, dir, 0)), g.tri(p(s, a, ya), p(s, b, yb - .3), p(s, a, ya - .3), OUT(F, dir, 0));
      const rg = g.geo(); B.roofG.push(rg);
      boxF(B.marble, F, s0, s1, D - WT - .15, D + .15, y + Y.wall - .05, y + Y.wall + .35);   // 外墙压顶
    } else {                                                  // 63 年：椽子架好，还没铺瓦
      const n = Math.max(2, Math.round((s1 - s0) / 1.6));
      for (let i = 0; i <= n; i++) { const s = s0 + (s1 - s0) * i / n, g = new GB(), p = (d, yy, o) => V3(F, s + o, d, yy); g.quad(p(a, ya, -.12), p(b, yb, -.12), p(b, yb + .25, -.12), p(a, ya + .25, -.12), OUT(F, -1, 0)); g.quad(p(a, ya, .12), p(b, yb, .12), p(b, yb + .25, .12), p(a, ya + .25, .12), OUT(F, 1, 0)); g.quad(p(a, ya + .25, -.12), p(b, yb + .25, -.12), p(b, yb + .25, .12), p(a, ya + .25, .12), [0, 1, 0]); B.timberG.push(g.geo()); }
    }
  }
  /* 脚手架（施工中）：外墙院子一侧，立杆每 2.4 m，横杆每 2 m（米 × K） */
  if (!done && scaff) {
    const top = y + wallTop + 1.6, n = Math.max(1, Math.round((s1 - s0) / (2.4 * K))), g = new GB();
    for (const d of [D - WT - 1.4, D + 1.2]) for (let i = 0; i <= n; i++) { const s = s0 + (s1 - s0) * i / n; boxF(g, F, s - .07, s + .07, d - .07, d + .07, y - .4, top, 'side'); }
    for (const d of [D - WT - 1.4, D + 1.2]) for (let yy = y + 2 * K; yy < top; yy += 2 * K) boxF(g, F, s0, s1, d - .05, d + .05, yy, yy + .1, 'side');
    B.timberG.push(g.geo());
  }
}

/* 角墩（院子四角柱列的交点）：方墩到下层檐、上层到上层檐 */
function cornerPier(B, ctx, P, stage, foots, idk) {
  const S = [[P[0] - .8, P[1] - .8], [P[0] + .8, P[1] - .8], [P[0] + .8, P[1] + .8], [P[0] - .8, P[1] + .8]], F0 = ctx.footing(S, 1), y = F0.max + .08;
  foots.push({ kind: 'landmark:forum', id: idk, pts: S, bottom: F0.min - .6, floor: y });
  const F = frame(P, [1, 0], [0, 1]), top = stage >= 4 ? Y.e2 : stage >= 2 ? Y.e1 : stage >= 1 ? Y.c1 : 0;
  boxF(B.marble, F, -.85, .85, -.85, .85, F0.min - .6, y + 0.3);
  if (top > 0) boxF(B.marble, F, -.7, .7, -.7, .7, y, y + top);
}

/* ---------------- 凯旋门（米，局部；整组 × K × HERO_SCALE） ---------------- */
function archGroup(far, part = 1) {
  const G = new T.Group(), gb = new GB(), O = [0, 0], X = [1, 0], Z = [0, 1];
  const box = (x0, x1, z0, z1, y0, y1) => boxF(gb, frame(O, X, Z), x0, x1, z0, z1, y0, y1);
  const piers = [-AR.outer, -AR.inner, AR.inner, AR.outer];
  const colY = AR.ped, colTop = AR.ped + AR.col, built = part >= 1;
  /* 基座：每个墩子一个台座（3.4 × 3.6 m，带线脚），中间门道铺石 */
  for (const px of piers) {
    box(px - 1.75, px + 1.75, -1.85, 1.85, -1.2, 0.35); box(px - 1.6, px + 1.6, -1.7, 1.7, 0.35, AR.ped - 0.3); box(px - 1.72, px + 1.72, -1.82, 1.82, AR.ped - 0.3, AR.ped);
  }
  /* 束柱：每墩 2×2 根棍棒柱，柱心距 1.5 m；内墩朝中门那两根的柱头下有握拳（史料「四根有手」→ 假设是中门两侧 4 根） */
  const clubs = [], colH = AR.col;
  /* 59 年：内墩的束柱先立起来，外墩还只有台座 */
  for (const px of piers) if (built || Math.abs(px) === AR.inner) for (const dx of [-AR.colGap, AR.colGap]) for (const dz of [-AR.colGap, AR.colGap]) clubs.push([px + dx, dz, Math.abs(px) === AR.inner && Math.sign(dx) === -Math.sign(px)]);
  if (clubs.length) {
    const gFist = clubColumn(T, { r: AR.colR, h: AR.col, seed: 21, far, fist: true }), gPlain = clubColumn(T, { r: AR.colR, h: AR.col, seed: 22, far, fist: false });
    for (const fist of [true, false]) {
      const L = clubs.filter(c => c[2] === fist); if (!L.length) continue;
      const im = new T.InstancedMesh(fist ? gFist : gPlain, M.club, L.length), m4 = new T.Matrix4();
      L.forEach((c, i) => { m4.makeTranslation(c[0], colY, c[1]); im.setMatrixAt(i, m4); });
      im.castShadow = im.receiveShadow = true; G.add(im);
    }
  }
  if (built) {
    /* 墩顶的檐块（柱头上的额枋，向前凸出） */
    for (const px of piers) { box(px - 1.55, px + 1.55, -1.75, 1.75, colTop, colTop + .55); box(px - 1.7, px + 1.7, -1.9, 1.9, colTop + .55, colTop + .8); box(px - 1.8, px + 1.8, -2.0, 2.0, colTop + .8, AR.imp); }
    /* 拱身：一整片墙，三个半圆拱（中门 7 m、侧门 3.6 m）在 imp 起拱，拉深 4 m → 筒拱 */
    const sh = new T.Shape(), arcs = [[-(AR.outer + AR.inner) / 2, AR.sr], [0, AR.cr], [(AR.outer + AR.inner) / 2, AR.sr]];
    sh.moveTo(-AR.half, AR.imp);
    for (const [cx, rr] of arcs) { sh.lineTo(cx - rr, AR.imp); sh.absarc(cx, AR.imp, rr, Math.PI, 0, true); }
    sh.lineTo(AR.half, AR.imp); sh.lineTo(AR.half, AR.attic0 - .8); sh.lineTo(-AR.half, AR.attic0 - .8); sh.lineTo(-AR.half, AR.imp);
    const body = new T.ExtrudeGeometry(sh, { depth: AR.depth * 2, bevelEnabled: false, curveSegments: far ? 5 : 12 }); body.translate(0, 0, -AR.depth);
    body.deleteAttribute('uv'); body.deleteAttribute('normal'); body.computeVertexNormals();
    /* 拱门洞以下、两墩之间的外侧墙（外墩外面那一截）：外墩外沿到 half */
    for (const s of [-1, 1]) box(s > 0 ? AR.outer + 1.6 : -AR.half, s > 0 ? AR.half : -AR.outer - 1.6, -AR.depth, AR.depth, 0.35, AR.imp);
    /* 拱圈线脚（两面）+ 拱心石 */
    const ring = [];
    for (const [cx, rr] of arcs) for (const zf of [-AR.depth - .18, AR.depth]) {
      const s2 = new T.Shape(); s2.absarc(cx, AR.imp, rr + .75, 0, Math.PI, false); s2.lineTo(cx - rr, AR.imp); s2.absarc(cx, AR.imp, rr, Math.PI, 0, true); s2.lineTo(cx + rr + .75, AR.imp);
      const g = new T.ExtrudeGeometry(s2, { depth: .18, bevelEnabled: false, curveSegments: far ? 5 : 12 }); g.translate(0, 0, zf); g.deleteAttribute('uv'); g.deleteAttribute('normal'); g.computeVertexNormals(); ring.push(g);
      if (!far) box(cx - .45, cx + .45, zf < 0 ? -AR.depth - .3 : AR.depth, zf < 0 ? -AR.depth : AR.depth + .3, AR.imp + rr - .1, AR.imp + rr + 1.1);
    }
    /* 檐口（两面出挑）+ 女儿墙 + 中段加高 + 顶檐 */
    const cor = [[-AR.depth - .55, 0], [-AR.depth, -.2], [-AR.depth, -.8], [AR.depth, -.8], [AR.depth, -.2], [AR.depth + .55, 0], [AR.depth + .55, .3], [-AR.depth - .55, .3]];
    prism(gb, [0, 0], [0, 1], [1, 0], cor, -AR.half - .5, AR.half + .5, AR.attic0 - .3);
    box(-AR.half + .3, AR.half - .3, -AR.depth + .2, AR.depth - .2, AR.attic0, AR.attic1);
    /* 女儿墙的壁柱（对着四个墩，两面）+ 中门上的拱肩板：参考图的女儿墙是分格的，平板读不出尺度 */
    if (!far) for (const px of piers) for (const zs of [-1, 1]) box(px - .7, px + .7, zs > 0 ? AR.depth - .2 : -AR.depth - .05, zs > 0 ? AR.depth + .05 : -AR.depth + .2, AR.attic0, AR.attic1);
    if (!far) for (const px of piers) for (const zs of [-1, 1]) box(px - .55, px + .55, zs > 0 ? AR.depth : -AR.depth - .12, zs > 0 ? AR.depth + .12 : -AR.depth, colTop + .8 + .05, AR.attic0 - .85);   // 墩上方的壁柱（拱肩之间）
    box(-AR.half + .1, AR.half - .1, -AR.depth, AR.depth, AR.attic1, AR.top);
    box(-AR.inner - 1.6, AR.inner + 1.6, -AR.depth + .2, AR.depth - .2, AR.top, AR.mid);
    box(-AR.inner - 1.75, AR.inner + 1.75, -AR.depth, AR.depth, AR.mid, AR.mid + .3);
    /* 女儿墙正面的浮雕板（两面）：贴图（题额 + 胜利女神 + 花环） */
    if (!far) {
      const ap = [];
      for (const [zf, nz] of [[AR.depth - .2 + .02, 1], [-AR.depth + .2 - .02, -1]]) {
        const g = new T.PlaneGeometry(2 * AR.half - .8, AR.attic1 - AR.attic0 - .3); if (nz < 0) g.rotateY(Math.PI); g.translate(0, (AR.attic0 + AR.attic1) / 2, zf); ap.push(g);
      }
      const am = new T.Mesh(merge(T, ap), M.attic); am.receiveShadow = true; G.add(am);
    }
    const bg = merge(T, [body, ...ring]); worldUV(bg, 4.8); const bm = new T.Mesh(bg, M.marble); bm.castShadow = bm.receiveShadow = true; G.add(bm);
    /* 顶上的像：中间狄奥多西（4.2 m），两侧墩上阿卡狄乌斯、霍诺留（3.6 m）；面朝西（城外来的人先看见）—— 复用纪功柱的烘焙低模像 */
    const st = [];
    for (const [x, h, y0] of [[0, 4.2, AR.mid + .3], [-AR.outer, 3.6, AR.top], [AR.outer, 3.6, AR.top]]) {
      const g = geoOf(T, STATUE_LO, 1); g.computeBoundingBox(); const sc = h / g.boundingBox.max.y; g.scale(sc, sc, sc); g.translate(x, y0, 0);   // 局部不转：整组转 −90° 后像朝西（同纪功柱的朝向）
      st.push(g);
      box(x - .8, x + .8, -.8, .8, y0 - .01, y0 + .35);
      st[st.length - 1].translate(0, .35, 0);
    }
    const sm = new T.Mesh(merge(T, st), M.statue); sm.castShadow = true; G.add(sm);
  } else {
    /* 59 年：墩座 + 半高的束柱 + 木脚手架和拱架（centering） */
    const tg = new GB(), F0 = frame(O, X, Z), top = colY + colH + 1.5;
    for (const px of piers) for (const dx of [-2.1, 2.1]) for (const dz of [-2.2, 2.2]) boxF(tg, F0, px + dx - .08, px + dx + .08, dz - .08, dz + .08, 0, top, 'side');
    for (const px of piers) for (let yy = 1.8; yy < top; yy += 1.8) { boxF(tg, F0, px - 2.2, px + 2.2, -2.25, -2.15, yy, yy + .1, 'side'); boxF(tg, F0, px - 2.2, px + 2.2, 2.15, 2.25, yy, yy + .1, 'side'); }
    const tm = new T.Mesh(tg.geo(), M.timber); tm.castShadow = true; G.add(tm);
  }
  const g = gb.geo(); worldUV(g, 4.8); const m = new T.Mesh(g, far ? M.far : M.marble); m.castShadow = m.receiveShadow = true; G.add(m);
  return G;
}

/* 东门（柱廊门楼）：两个方墩 + 一个拱，进深 = 柱廊进深，顶上两面三角山花（不是凯旋门：底账只写了西门） */
function eastGate(B, ctx, w, s0, s1, foots, stage) {
  const F = w.F, P = [F.P(s0, -1.1), F.P(s1, -1.1), F.P(s1, D + .5), F.P(s0, D + .5)], F0 = ctx.footing(P, 2), y = F0.max + .08;
  foots.push({ kind: 'landmark:forum', id: 'forum:eastgate', pts: P, bottom: F0.min - .6, floor: y });
  boxF(B.marble, F, s0, s1, -1.1, D + .5, F0.min - .6, y);
  if (stage < 1) return;
  const top = stage >= 4 ? Y.e2 + .6 : stage >= 2 ? Y.e1 + 1 : Y.c1, pw = 2.6, spring = Y.c1 + .4, rr = (s1 - s0 - 2 * pw) / 2;
  const sh = new T.Shape(); sh.moveTo(s0, 0); sh.lineTo(s0 + pw, 0); sh.lineTo(s0 + pw, spring); sh.absarc((s0 + s1) / 2, spring, rr, Math.PI, 0, true); sh.lineTo(s1 - pw, 0); sh.lineTo(s1, 0); sh.lineTo(s1, top); sh.lineTo(s0, top); sh.lineTo(s0, 0);
  if (top < spring + rr + .3) { sh.curves.length = 0; const h = Math.max(top, 1); sh.moveTo(s0, 0); for (const [a, b] of [[s0, s0 + pw], [s1 - pw, s1]]) { const p = new T.Shape(); p.moveTo(a, 0); p.lineTo(b, 0); p.lineTo(b, h); p.lineTo(a, h); p.lineTo(a, 0); const g = wallShape(F, p, -.6, D + 1.0); g.translate(0, y, 0); B.marbleG.push(g); } return; }
  const g = wallShape(F, sh, -.6, D + 1.0, 8); g.translate(0, y, 0); B.marbleG.push(g);
  if (stage >= 5) {
    const W2 = (s1 - s0) / 2 + .4, hgt = W2 * .38, pd = [[-W2, 0], [W2, 0], [0, hgt]], mid = (s0 + s1) / 2;
    prism(B.marble, F.P(mid, 0), F.t, F.n, pd, -.9, D + .7, y + top);
    const cor = [[s0 - .4, 0], [s1 + .4, 0], [s1 + .4, .35], [s0 - .4, .35]];
    prism(B.marble, F.P(0, 0), F.t, F.n, cor, -.9, D + .7, y + top - .35);
  }
}

/* 57–58 年：划地 —— 一圈木桩 + 拉绳，广场内是翻过的土（盖住 streets 的铺地，底账 59 年才铺地），几堆石料 */
function siteMarks(G, ctx, r) {
  const C = (u, v) => [r.cx + r.ax * u - r.az * v, r.cz + r.az * u + r.ax * v], tb = new GB(), rp = new GB(), st = new GB();
  const ring = (o) => [C(-r.hu + o, -r.hv + o), C(r.hu - o, -r.hv + o), C(r.hu - o, r.hv - o), C(-r.hu + o, r.hv - o)];
  for (const o of [0.5, D]) {
    const q = ring(o);
    for (let i = 0; i < 4; i++) {
      const a = q[i], b = q[(i + 1) % 4], L = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.round(L / 6);
      let prev = null;
      for (let k = 0; k <= n; k++) {
        const x = a[0] + (b[0] - a[0]) * k / n, z = a[1] + (b[1] - a[1]) * k / n, y = ctx.groundMesh(x, z), F = frame([x, z], [1, 0], [0, 1]);
        boxF(tb, F, -.1, .1, -.1, .1, y - .5, y + 1.6, 'side');
        if (prev) { const g = new GB(), p0 = [prev[0], prev[2] + 1.2, prev[1]], p1 = [x, y + 1.2, z]; rp.quad(p0, p1, [p1[0], p1[1] + .06, p1[2]], [p0[0], p0[1] + .06, p0[2]], [-(z - prev[1]), 0, x - prev[0]]); }
        prev = [x, z, y];
      }
    }
  }
  /* 翻过的土：按网格贴地 +0.3（streets 的广场铺地在 +0.14） */
  const n = 28, P = [], I = [];
  for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) { const u = -r.hu + 2 * r.hu * i / n, v = -r.hv + 2 * r.hv * j / n, q = C(u, v); P.push(q[0], ctx.groundMesh(q[0], q[1]) + .55, q[1]); }
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const a = j * (n + 1) + i, b = a + 1, c = a + n + 1, d = c + 1; I.push(a, c, b, b, c, d); }
  const dg = new T.BufferGeometry(); dg.setAttribute('position', new T.Float32BufferAttribute(P, 3)); dg.setIndex(I); dg.computeVertexNormals();
  if (dg.attributes.normal.getY(0) < 0) { const ix = dg.index.array; for (let i = 0; i < ix.length; i += 3) { const t = ix[i + 1]; ix[i + 1] = ix[i + 2]; ix[i + 2] = t; } dg.computeVertexNormals(); }
  const dm = new T.Mesh(dg, M.dirt); dm.receiveShadow = true; G.add(dm);
  /* 石料堆：6 堆，每堆 5–8 块（位置用底账 seed） */
  for (let k = 0; k < 6; k++) {
    const u = (ctx.hsh(id.length * 7 + k, 31) - .5) * (r.hu - 25) * 2, v = (ctx.hsh(k, 32) - .5) * (r.hv - 25) * 2, q = C(u, v), y = ctx.groundMesh(q[0], q[1]);
    if (Math.hypot(u, v) < 14) continue;                      // 别压在纪功柱的基座上
    const nb = 5 + Math.floor(ctx.hsh(k, 33) * 4);
    for (let i = 0; i < nb; i++) { const F = frame([q[0] + (i % 3) * 1.9 - 1.9, q[1] + Math.floor(i / 3) * 1.5], [1, 0], [0, 1]), lev = i >= 6 ? 1 : 0; boxF(st, F, -.85, .85, -.6, .6, y - .2 + lev * 1.2, y + 1.0 + lev * 1.2); }
  }
  for (const [g, m] of [[tb, M.timber], [rp, M.rope], [st, M.stone]]) if (g.p.length) { const mm = new T.Mesh(g.geo(), m); mm.castShadow = true; mm.receiveShadow = true; G.add(mm); }
}

/* ---------------- 组装 ---------------- */
function buildAll(ctx, r, Yr, far) {
  const G = new T.Group(), foots = [];
  const stage = Yr >= PHASE.done ? 5 : Yr < PHASE.frame ? -1 : Math.min(4, Yr - PHASE.frame);
  if (Yr < PHASE.frame) { siteMarks(G, ctx, r); return { G, foots }; }
  const B = { marble: new GB(), wall: new GB(), ceil: new GB(), wallG: [], innerG: [], roofG: [], timberG: [], marbleG: [] }, cols = { c1: [], c2: [] };
  const archOnly = ctx.QS.get && ctx.QS.get('lmonly') === 'arch';   // 比形用：?lmmask=1&lmonly=arch 只出凯旋门（柱廊、门、角墩都不建）
  for (const w of archOnly ? [] : wings(r)) {
    w.colS = colPositions(w);
    for (const [a, b, capA, capB] of pieces(w)) {
      const n = Math.max(1, Math.ceil((b - a) / SEG));
      for (let i = 0; i < n; i++) {
        const s0 = a + (b - a) * i / n, s1 = a + (b - a) * (i + 1) / n, P = [w.F.P(s0, -1.1), w.F.P(s1, -1.1), w.F.P(s1, D), w.F.P(s0, D)], Fo = ctx.footing(P, 2), y = Fo.max + .08, bot = Fo.min - .6;
        foots.push({ kind: 'landmark:forum', id: `forum:${w.k}${i}:${a.toFixed(0)}`, pts: P, bottom: bot, floor: y });
        porticoSeg(B, w, s0, s1, y, bot, capA && i === 0, capB && i === n - 1, stage, far, cols, !far);
      }
    }
    for (const [g0, g1, kind] of w.gaps) if (kind === 'gate') eastGate(B, ctx, w, g0, g1, foots, stage);
  }
  /* 角墩 */
  const C = (u, v) => [r.cx + r.ax * u - r.az * v, r.cz + r.az * u + r.ax * v], cu = r.hu - D + DC, cv = r.hv - D + DC;
  if (!archOnly) [[-cu, -cv], [cu, -cv], [cu, cv], [-cu, cv]].forEach(([u, v], i) => cornerPier(B, ctx, C(u, v), stage, foots, 'forum:corner' + i));
  /* 凯旋门：西翼门洞正中；外皮和外墙齐 */
  const W = wings(r)[2], ad = D - AR.depth * K * HERO_SCALE - .2, ac = W.F.P(MESE_W, ad), ah = ARCH_HALF_PX, adep = (AR.depth + .1) * K * HERO_SCALE;
  const AP = [W.F.P(MESE_W - ah, ad - adep), W.F.P(MESE_W + ah, ad - adep), W.F.P(MESE_W + ah, ad + adep), W.F.P(MESE_W - ah, ad + adep)], AF = ctx.footing(AP, 2), ab = AF.max + .05;
  foots.push({ kind: 'landmark:forum_arch', id: 'forum:arch', pts: AP, bottom: AF.min - .6, floor: ab });
  boxF(B.marble, W.F, MESE_W - ah, MESE_W + ah, ad - adep, ad + adep, AF.min - .6, ab);
  const archPart = Yr >= PHASE.arch ? 1 : 0.5;
  const A = archGroup(far, archPart); A.scale.setScalar(K * HERO_SCALE); A.position.set(ac[0], ab, ac[1]); A.rotation.y = Math.atan2(-W.F.t[1], W.F.t[0]); G.add(A);
  /* 柱子：两种（下 / 上层）各一个 InstancedMesh */
  const segs = far ? 6 : 10;
  for (const [L, rr, h] of [[cols.c1, R1, Y.c1], [cols.c2, R2, Y.c2 - Y.e1 - (Y.par - Y.e1) * 0]]) {
    if (!L.length) continue;
    const im = new T.InstancedMesh(colGeo(rr, h, segs, far), M.col, L.length), m4 = new T.Matrix4();
    L.forEach((q, i) => { m4.makeTranslation(q[0], q[1], q[2]); im.setMatrixAt(i, m4); });
    im.frustumCulled = false;                                  // 实例在世界坐标，网格本身在原点：默认的包围球会把整排柱子裁掉
    im.castShadow = true; im.receiveShadow = true; G.add(im);
  }
  /* 合并网格（一种材质一个） */
  const add = (geos, mat, tile, shadow = true) => { const L = geos.filter(g => g && g.attributes.position.count); if (!L.length) return; const g = merge(T, L); if (tile) worldUV(g, tile); const m = new T.Mesh(g, mat); m.castShadow = shadow; m.receiveShadow = true; G.add(m); };
  add([B.marble.geo(), ...B.marbleG], far ? M.far : M.marble, 4.8 * K);
  add([B.wall.geo(), ...B.wallG], far ? M.farWall : M.wall, 4.8 * K);
  add([B.ceil.geo()], M.ceil, 0);
  add(B.innerG, far ? M.ceil : M.inner, 4.8 * K);
  add(B.roofG, M.roof, 4.8 * K);
  add(B.timberG, M.timber, 0);
  return { G, foots, nCols: cols.c1.length + cols.c2.length };
}

export function build(ctx, f, r) {
  const Yr = ctx.year;
  if (Yr < f.y0) return null;
  let obj, foots;
  if (Yr >= PHASE.done) {
    if (!CACHE) {
      const t0 = performance.now(), near = buildAll(ctx, r, Yr, false), farB = buildAll(ctx, r, Yr, true);
      const lod = new T.LOD(); lod.name = 'forum-lod';
      /* LOD 按到广场中心的距离切；子组的坐标是世界坐标，LOD 本身放在中心（子组反向平移） */
      for (const [o, dist] of [[near.G, 0], [farB.G, LOD_FAR]]) { o.position.set(-r.cx, 0, -r.cz); const w = new T.Group(); w.add(o); lod.addLevel(w, dist); }
      lod.position.set(r.cx, 0, r.cz);
      CACHE = { lod, foots: near.foots, ms: Math.round(performance.now() - t0), nCols: near.nCols };
      LAST = { near: tri(near.G), far: tri(farB.G), ms: CACHE.ms };
    }
    obj = CACHE.lod; foots = CACHE.foots;
  } else {
    const t0 = performance.now(), b = buildAll(ctx, r, Yr, false); b.G.name = 'forum-construction'; obj = b.G; foots = b.foots;
    LAST = { near: tri(b.G), far: null, ms: Math.round(performance.now() - t0) };
  }
  for (const q of foots) ctx.foot(q);
  return obj;
}
const tri = (o) => { let n = 0; o.traverse(c => { if (c.isMesh) n += (c.geometry.index ? c.geometry.index.count : c.geometry.attributes.position.count) / 3 * (c.isInstancedMesh ? c.count : 1); }); return Math.round(n); };
export function stats() {
  return { near_tris: LAST.near, far_tris: LAST.far, geom_build_ms: LAST.ms, tex_ms: M && M._tex_ms, columns: CACHE ? CACHE.nCols : null,
    portico_height_m: +(Y.wall / K).toFixed(2), arch_height_m: +((AR.mid + .3 + .35 + 4.2) * HERO_SCALE).toFixed(2), arch_attic_m: +(AR.mid * HERO_SCALE).toFixed(2), arch_width_m: +(2 * AR.half * HERO_SCALE).toFixed(1), hero_scale: HERO_SCALE, portico_scale: PORTICO_SCALE };
}
export function dispose() { /* 完工的几何缓存着；施工中的组每次新建，由 index.js 释放 */ }
