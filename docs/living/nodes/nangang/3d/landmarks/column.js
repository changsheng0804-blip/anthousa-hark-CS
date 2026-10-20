/* landmark 试点 · 狄奥多西广场的纪功柱（Column of Theodosius）。——Hark（CS线）2026-10-20
   底账（只照用）：
   - nodes.json 地标 forum_theodosius（k=forum，y0=57，g = 广场四角）；ART_BIBLE §1「狄奥多西广场（第 57 年，中间一根纪念柱）」→ 柱子立在广场正中，基座顺广场的轴。
   - proposals/era_0051.json 的 phases：57 划地、59 铺地起柱廊、60 西侧凯旋门、64「纪功柱立到顶，广场完工」→ 第 64 年起才是完整的柱子；
     58–63 年画施工中（基座 + 按年份长高的柱身鼓石 + 木脚手架），57 年只有广场没有柱子。
   史料（形制，底账没写的部分；来源见 docs/cs/lookdev/landmarks/column/notes.md）：白色大理石、螺旋浮雕带（自左向右上升）、仿图拉真柱，
   总高约 40–50 m；顶上是狄奥多西的巨像（镀银青铜）。假设：柱头做科林斯式（主人要茛苕叶；图拉真柱其实是多立克式）、基座四面浮雕、像的姿势。
   尺寸（米，自台阶底起）：台阶 3 级 1.8 → 基座（线脚 + 浮雕身 + 檐口）到 9.5 → 阿提卡柱础到 11.35 → 柱身 27 m（17 节鼓石、18 圈浮雕、收分 1.95→1.70）
   → 柱头 2.2 → 像座 1.65 → 像 5.3，总高 ≈ 47.9 m ≈ 57 页面像素（1 像素 ≈ 0.84 米）。
   结构：近档（细节、法线贴图、烘焙雕像）/ 远档（几十个面的旋转体 + 低模像）用 THREE.LOD 按到相机的距离切（450 像素）。
   确定性：贴图和叶片的变化只用底账的 seed。?lmmask=1 把所有地标材质换成纯品红（silhouette.py 用来抠轮廓）。 */
import { lathe, squareLathe, merge, box } from './kit/lathe.js';
import { relief, soldier, captive, victory, garland, frame, line, rect, ell } from './kit/relief.js';
import { corinthian } from './kit/acanthus.js';
import { loadBaked, geoOf } from './kit/baked.js';

const STATUE_HI = await loadBaked(new URL('./column/statue_hi.bin', import.meta.url));
const STATUE_LO = await loadBaked(new URL('./column/statue_lo.bin', import.meta.url));

export const id = 'forum_theodosius';
export const PHASE = { pedestal: 58, top: 64 };          // proposals/era_0051.json：64 年立到顶；58 年起基座（假设：开工第二年）
const K = 1 / 0.84;                                        // 米 → 页面像素
export const DIM = { steps: 1.35, pedTop: 8.75, shaft0: 10.6, shaft1: 37.6, cap0: 37.95, cap1: 40.55, drum1: 43.55, statue: 7.5 };
const WIND = 18, DRUMS = 17, LOD_FAR = 450;

let T = null, M = null, CACHE = null;

function shaftR(y) { const t = (y - DIM.shaft0) / (DIM.shaft1 - DIM.shaft0); return 1.95 - 0.25 * Math.pow(t, 1.35) + 0.02 * Math.sin(Math.PI * t); }

/* ---- 贴图（init 里做一次） ---- */
function shaftTex(seed) {
  const W = 2048, H = 256;                                   // 一圈浮雕：u = 绕一圈，v = 一个螺旋节距（1.5 m）
  return relief(T, W, H, (g, R) => {
    const items = [];
    // 边带：螺旋线 y = H - x/W*H（画布 y 向下，所以往右是往上 → 自左向右上升）
    for (let x = 0; x <= W; x += 8) items.push(['b', x]);
    // 人物：一圈 ≈ 44 个，行军、骑马、扛旗、搭营，按 seed 变
    let x = 10;
    while (x < W - 20) {
      const kind = R(), h = 150 + R() * 30, gap = 38 + R() * 30;   // 留出暗的「地」，远看才读得出浮雕
      items.push(['f', x, h, kind, R() < .8 ? 1 : -1, R() * 1e9 | 0]); x += gap;
    }
    const offs = [];
    for (const dx of [-W, 0, W]) for (const dy of [-H, 0, H]) offs.push([dx, dy - dx / W * H]);
    // 底子（浮雕的地）：中灰；人物从地上凸出来
    rect(g, 0, 0, W, H, 0.08);
    for (const [ox, oy] of offs) {
      g.save(); g.translate(ox, oy);
      for (const it of items) {
        if (it[0] === 'f') {
          const [, fx, fh, kind, dir, s] = it, base = H - fx / W * H - 12;
          const r2 = (() => { let a = s >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; })();
          if (kind < 0.62) soldier(g, r2, fx, base, fh, dir, 0.86);
          else if (kind < 0.78) { // 骑兵：马身 + 骑手
            const u = fh / 10; ell(g, fx, base - u * 3.4, u * 3.2, u * 1.4, 0.82); line(g, fx - u * 2.2, base, fx - u * 2, base - u * 3, u * .6, .78); line(g, fx + u * 2.2, base, fx + u * 2, base - u * 3, u * .6, .78);
            ell(g, fx + dir * u * 3.3, base - u * 4.6, u * .8, u * 1.3, .84); soldier(g, r2, fx, base - u * 4.2, fh * .62, dir, .9);
          } else if (kind < 0.88) { soldier(g, r2, fx, base, fh, dir, 0.86); line(g, fx + 8, base - fh * .2, fx + 8, base - fh * 1.08, 4, .9); rect(g, fx + 8, base - fh * 1.08, 26, 22, .9); } // 旗手
          else captive(g, r2, fx, base, fh * .9, -dir, 0.8);
        }
      }
      // 边带（略凸的窄条），画在人物之后，压住脚
      g.strokeStyle = 'rgb(245,245,245)'; g.lineWidth = 18; g.beginPath(); g.moveTo(-40, H + 40 / W * H - 2); g.lineTo(W + 40, H - (W + 40) / W * H - 2); g.stroke();
      g.strokeStyle = 'rgb(0,0,0)'; g.lineWidth = 22; g.beginPath(); g.moveTo(-40, H + 40 / W * H + 20); g.lineTo(W + 40, H - (W + 40) / W * H + 20); g.stroke();
      g.restore();
    }
  }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 9, aoR: 8, ao: 4.0, base: [186, 174, 152], dirt: 0.1 });
}

function pedestalTex(seed) {
  const W = 1024, S = 512;                                    // 2×2 图集：0 南（正面）1 东 2 北 3 西
  return relief(T, W, W, (g, R) => {
    for (let k = 0; k < 4; k++) {
      const ox = (k % 2) * S, oy = (k >> 1) * S;
      g.save(); g.translate(ox, oy);
      rect(g, 0, 0, S, S, 0.62);                              // 浮雕身的平面
      // 顶上花环带
      rect(g, 0, 0, S, 70, 0.5); garland(g, R, 30, S - 30, 18, 30, 5, 0.85);
      // 主画框
      frame(g, 22, 84, S - 44, S - 130, 16, 0.92, 0.18);
      const y0 = S - 62, fh = 300;
      g.save(); g.beginPath(); g.rect(38, 100, S - 76, S - 162); g.clip();   // 人物不出框
      if (k === 0 || k === 2) {                               // 南、北：中间皇帝（较高）+ 两边士兵，角上胜利女神
        victory(g, R, 70, y0, fh * .95, 1, .9); victory(g, R, S - 70, y0, fh * .95, -1, .9);
        soldier(g, R, S / 2, y0, fh * 1.08, 1, .95);
        for (const dx of [-1, 1]) for (let i = 1; i <= 2; i++) soldier(g, R, S / 2 + dx * (52 + i * 48), y0, fh * (.92 - i * .03), -dx, .82 - i * .05);
      } else {                                                // 东、西：跪着献礼的俘虏 + 押送的士兵
        for (let i = 0; i < 5; i++) captive(g, R, 80 + i * 78, y0, fh * (.78 + .08 * R()), k === 1 ? 1 : -1, .8 + .08 * R());
        soldier(g, R, S - 64, y0, fh, k === 1 ? -1 : 1, .9); soldier(g, R, 52, y0, fh * .96, k === 1 ? 1 : -1, .88);
      }
      g.restore();
      // 底带
      rect(g, 0, S - 40, S, 40, 0.55); for (let x = 8; x < S; x += 22) rect(g, x, S - 30, 12, 20, 0.7);
      g.restore();
    }
  }, { seed, blur: 1, strength: 7, aoR: 7, ao: 3.0, base: [188, 174, 150], dirt: 0.1, streak: 0.05 });
}

function marbleTex(seed) {
  return relief(T, 256, 256, (g) => { rect(g, 0, 0, 256, 256, 0.5); for (let y = 0; y < 256; y += 64) rect(g, 0, y, 256, 2, 0.35); }, { seed, wrapX: true, wrapY: true, blur: 1, strength: 2, aoR: 3, ao: 1.2, base: [190, 178, 156], dirt: 0.12 });
}

export function init(ctx) {
  T = ctx.THREE;
  const f = (ctx.by.landmark || []).find(x => x.id === id), seed = f ? f.seed : 1;
  const sh = shaftTex(seed), pd = pedestalTex(seed + 1), mb = marbleTex(seed + 2);
  const ns = new T.Vector2(1, 1);
  M = {
    shaft: new T.MeshLambertMaterial({ map: sh.map, normalMap: sh.normalMap, normalScale: ns }),
    ped: new T.MeshLambertMaterial({ map: pd.map, normalMap: pd.normalMap, normalScale: ns }),
    marble: new T.MeshLambertMaterial({ map: mb.map, normalMap: mb.normalMap }),
    cap: new T.MeshLambertMaterial({ map: mb.map, side: T.DoubleSide }),
    statue: new T.MeshPhongMaterial({ color: 0x968c7c, specular: 0x8a7e6a, shininess: 34 }),     // 镀银青铜（史料），按风化后的暗银处理；假设：不鎏金
    far: new T.MeshLambertMaterial({ color: 0xbcae94 }),
    timber: new T.MeshLambertMaterial({ color: 0x7b5b3c }),
  };
  if (ctx.QS.has('lmmask')) { const mk = new T.MeshBasicMaterial({ color: 0xff00ff, fog: false, toneMapped: false, side: T.DoubleSide }); for (const k in M) M[k] = mk; }
}

/* ---- 几何（局部坐标：原点 = 台阶底面中心，y 向上，单位 = 页面像素；基座顺 (ax, az)） ---- */
function pedestalGeos(ax, az) {
  const s = (h, y) => [h * K, y * K];
  const steps = squareLathe(T, [s(3.95, -3), s(3.95, 0.45), s(3.75, 0.45), s(3.75, 0.9), s(3.55, 0.9), s(3.55, 1.35)], { ax, az, uv: 4 });
  const plinth = squareLathe(T, [s(3.5, 1.35), s(3.5, 1.7), s(3.36, 1.84), s(3.36, 1.96), s(3.22, 2.04), s(3.1, 2.1), s(3.05, 2.14)], { ax, az, uv: 4, top: false });
  const cornice = squareLathe(T, [s(3.05, 7.75), s(3.18, 7.83), s(3.24, 7.94), s(3.24, 8.05), s(3.42, 8.18), s(3.5, 8.36), s(3.55, 8.55), s(3.55, 8.75)], { ax, az, uv: 4 });
  // 浮雕身：四个面，图集四格
  const P = [], U = [], h = 3.05 * K, y0 = 2.14 * K, y1 = 7.75 * K, C = (u, v) => [ax * u - az * v, az * u + ax * v];
  const k = [C(-h, h), C(h, h), C(h, -h), C(-h, -h)]; // 南面（+v）、东、北、西：逆时针从外看
  const cells = [[0, 1], [1, 1], [0, 0], [1, 0]];        // 画布 2×2：左上=南 右上=东 左下=北 右下=西（v 向上 → 画布上半 = v 0.5..1）
  for (let i = 0; i < 4; i++) {
    const a = k[i], b = k[(i + 1) % 4], [cu, cv] = cells[i], u0 = cu * .5, v0 = cv * .5;
    const q = [[a[0], y0, a[1]], [b[0], y0, b[1]], [b[0], y1, b[1]], [a[0], y1, a[1]]], uq = [[u0, v0], [u0 + .5, v0], [u0 + .5, v0 + .5], [u0, v0 + .5]];
    for (const j of [0, 1, 2, 0, 2, 3]) { P.push(...q[j]); U.push(...uq[j]); }
  }
  const die = new T.BufferGeometry(); die.setAttribute('position', new T.Float32BufferAttribute(P, 3)); die.setAttribute('uv', new T.Float32BufferAttribute(U, 2)); die.computeVertexNormals();
  return { stone: [steps, plinth, cornice], die };
}

function baseAndShaft(segs, yTop = DIM.shaft1) {
  const s = (r, y) => [r * K, y * K];
  const plinth = squareLathe(T, [s(2.5, 8.75), s(2.5, 9.2)], { uv: 4 });
  const base = lathe(T, [s(2.3, 9.2), s(2.42, 9.29), s(2.48, 9.43), s(2.45, 9.57), s(2.3, 9.67), s(2.12, 9.71), s(2.02, 9.81), s(1.99, 9.93), s(2.08, 10.03), s(2.2, 10.07), s(2.25, 10.19), s(2.2, 10.31), s(2.06, 10.37), s(2.0, 10.39), s(2.0, 10.47), s(1.95, 10.6)], segs, { v: y => y / K / 1.5 });
  const prof = [];
  const top = Math.min(yTop, DIM.shaft1), dz = (DIM.shaft1 - DIM.shaft0) / DRUMS;
  for (let i = 0; i < DRUMS; i++) {
    const y0 = DIM.shaft0 + i * dz; if (y0 >= top - 1e-6) break;
    const y1 = Math.min(top, y0 + dz);
    prof.push(s(shaftR(y0), y0));   // 鼓石接缝不做成几何棱（会和螺旋带抢，读成一圈圈横纹）；接缝藏在浮雕里，和图拉真柱一样       // 鼓石接缝：一圈细缝
    for (let k = 1; k < 4; k++) { const y = y0 + (y1 - y0) * k / 4; prof.push(s(shaftR(y), y)); }
    if (y1 >= top - 1e-6) prof.push(s(shaftR(y1), y1));
  }
  const shaft = lathe(T, prof, segs, { v: y => (y / K - DIM.shaft0) / ((DIM.shaft1 - DIM.shaft0) / WIND), crease: 60 });
  return { stone: [plinth, base], shaft };
}

function topGeos(segs, far) {
  const s = (r, y) => [r * K, y * K];
  const astr = lathe(T, [s(1.72, 37.6), s(1.8, 37.67), s(1.8, 37.8), s(1.72, 37.87), s(1.7, 37.95)], segs);
  const drum = lathe(T, [s(1.5, 40.55), s(1.5, 40.75), s(1.36, 40.92), s(1.3, 41.0), s(1.3, 43.15), s(1.4, 43.28), s(1.5, 43.46), s(1.5, 43.55), s(0, 43.56)], segs, { v: y => y / K / 1.5 });
  const cap = corinthian(T, { r: 1.7 * K, h: 2.6 * K, a: 2.85 * K, seed: 11, lod: far ? 'far' : 'near' });
  cap.translate(0, DIM.cap0 * K, 0);
  return { stone: [astr, drum], cap };
}

function statueMesh(buf, mat, rotY) {
  const g = geoOf(T, buf, 1); g.computeBoundingBox(); const sc = K * DIM.statue / g.boundingBox.max.y; g.scale(sc, sc, sc); g.rotateY(rotY); g.translate(0, DIM.drum1 * K, 0);  // 烘焙的像按 DIM.statue 放大
  const m = new T.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true; return m;
}
const meshOf = (g, mat, cast = true) => { const m = new T.Mesh(g, mat); m.castShadow = cast; m.receiveShadow = true; return m; };

function nearGroup(ax, az, rotY) {
  const G = new T.Group(); G.name = 'column-near';
  const pd = pedestalGeos(ax, az), bs = baseAndShaft(48), tp = topGeos(40, false);
  G.add(meshOf(merge(T, [...pd.stone, ...bs.stone, ...tp.stone]), M.marble));
  G.add(meshOf(pd.die, M.ped));
  G.add(meshOf(bs.shaft, M.shaft));
  G.add(meshOf(tp.cap, M.cap));
  G.add(statueMesh(STATUE_HI, M.statue, rotY));
  return G;
}
function farGroup(ax, az, rotY) {
  const G = new T.Group(); G.name = 'column-far';
  const s = (h, y) => [h * K, y * K];
  const ped = squareLathe(T, [s(3.95, -3), s(3.95, 1.35), s(3.5, 1.35), s(3.5, 2.1), s(3.05, 2.14), s(3.05, 7.8), s(3.55, 8.3), s(3.55, 8.75)], { ax, az, uv: 4 });
  const col = lathe(T, [s(2.4, 8.75), s(2.4, 9.75), s(1.95, 10.6), s(1.7, 37.6), s(1.8, 37.75), s(1.7, 37.95)], 10);
  const drum = lathe(T, [s(1.5, 40.55), s(1.3, 41.0), s(1.3, 43.2), s(1.5, 43.55), s(0, 43.56)], 8);
  const cap = corinthian(T, { r: 1.7 * K, h: 2.6 * K, a: 2.85 * K, lod: 'far' }); cap.translate(0, DIM.cap0 * K, 0);
  G.add(meshOf(merge(T, [ped, col, drum, cap]), M.far));
  G.add(statueMesh(STATUE_LO, M.statue, rotY));
  return G;
}

/* 施工中（58–63 年）：台阶 + 基座 + 按年份长到第 n 节鼓石的柱身 + 木脚手架 */
function construction(ax, az, year) {
  const G = new T.Group(); G.name = 'column-construction';
  const frac = Math.max(0, Math.min(1, (year - PHASE.pedestal) / (PHASE.top - PHASE.pedestal)));
  const pd = pedestalGeos(ax, az), nd = Math.floor(frac * DRUMS), top = DIM.shaft0 + nd * (DIM.shaft1 - DIM.shaft0) / DRUMS;
  const parts = [...pd.stone];
  let shaft = null;
  if (nd > 0) { const bs = baseAndShaft(32, top); parts.push(...bs.stone); shaft = bs.shaft; }
  G.add(meshOf(merge(T, parts), M.marble)); G.add(meshOf(pd.die, M.ped)); if (shaft) G.add(meshOf(shaft, M.shaft));
  // 脚手架：8 根立杆绕柱身，每 2 m 一圈横杆，顶上一层平台
  const yA = DIM.pedTop * K, yB = (Math.max(top, DIM.pedTop + 2) + 2.5) * K, R0 = 3.0 * K, sc = [];
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; sc.push(box(T, .09 * K, (yB - yA) / 2, .09 * K, Math.cos(a) * R0, (yA + yB) / 2, Math.sin(a) * R0)); }
  for (let y = yA + 2 * K; y <= yB; y += 2 * K) for (let i = 0; i < 8; i++) {
    const a0 = i / 8 * Math.PI * 2, a1 = (i + 1) / 8 * Math.PI * 2, x0 = Math.cos(a0) * R0, z0 = Math.sin(a0) * R0, x1 = Math.cos(a1) * R0, z1 = Math.sin(a1) * R0, L = Math.hypot(x1 - x0, z1 - z0);
    sc.push(box(T, L / 2, .06 * K, .06 * K, (x0 + x1) / 2, y, (z0 + z1) / 2, -Math.atan2(z1 - z0, x1 - x0)));
  }
  sc.push(box(T, R0 * .95, .1 * K, R0 * .95, 0, yB, 0));
  G.add(meshOf(merge(T, sc), M.timber));
  return G;
}

export function build(ctx, f, r, b) {
  const Y = ctx.year;
  if (Y < PHASE.pedestal) return null;
  const rotY = -Math.PI / 2 + Math.atan2(r.az, r.ax);      // 像面朝西（西侧凯旋门，底账 60 年）；假设
  let obj;
  if (Y >= PHASE.top) {
    if (!CACHE) {                                           // 完整柱子的几何不随年份变：建一次，以后重用
      const t0 = performance.now();
      const lod = new T.LOD(); lod.name = 'column-lod';
      lod.addLevel(nearGroup(r.ax, r.az, rotY), 0); lod.addLevel(farGroup(r.ax, r.az, rotY), LOD_FAR);
      CACHE = { lod, ms: Math.round(performance.now() - t0) };
    }
    obj = CACHE.lod;
  } else obj = construction(r.ax, r.az, Y);
  obj.position.set(r.cx, b, r.cz);
  return obj;
}

/* 给 silhouette.py / numbers.json 的数：近/远两档的三角形、几何建造毫秒 */
export function stats() {
  const tri = o => { let n = 0; o.traverse(c => { if (c.isMesh) { const g = c.geometry; n += (g.index ? g.index.count : g.attributes.position.count) / 3; } }); return Math.round(n); };
  if (!CACHE) return null;
  const [near, far] = CACHE.lod.levels.map(l => tri(l.object));
  return { near_tris: near, far_tris: far, geom_build_ms: CACHE.ms, height_px: +((DIM.drum1 + DIM.statue) * K).toFixed(1), height_m: DIM.drum1 + DIM.statue };
}
export function dispose() { /* 完整柱子的几何是缓存的（不随年份变）；施工中的组每次新建，由 index.js 释放 */ }
