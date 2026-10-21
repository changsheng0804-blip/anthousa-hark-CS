/* CS 线 · 全城 3D 导演 citycore（2026-10-20，主人「可以」：把南港 3D 渲染器推到全城，分块流式加载）。——Hark（CS线）
   页面：docs/living/nodes/city/3d.html（设 globalThis.CS3D = {base:'3d/', crowd:null} 后载入本文件）。南港页仍走 core.js，一行没动。
   模块（sky terrain water streets buildings landmarks props flora crowd）一个都没复制：和南港同一份文件，只多认 ctx 上三个可选参数
   （ctx.noOuter：terrain 不画南港区外烘焙；ctx.landmarkIds：buildings 给没被 landmarks 接手的同类地标画旧通用占位；ctx.ox/oz：flora 按全城坐标定树样）。

   做法（为什么这样，见 docs/cs/lookdev/city3d/report.md）：
   - 数据：tools/cs/nodes/city3d_chunks.py 把 nodes/city/nodes_net.json 按瓦片格（455 px，13×14）切成 116 块：f_i_j（近景整块，nodes.json 同 schema，全城坐标）
     + l_i_j（远景简块）；base.json = 高程、等高带、陆地/海/港池/石堤、29 座地标、水道桥、分块索引。
   - 近景 = 一个 4×4 块（1820 px ≈ 1.5 km，和南港一个页面框差不多大）的「窗口」，跟着镜头的看点走（滞后一块，免得来回重建）。
     窗口里的要素平移成窗口局部坐标（0..1820），交给原封不动的模块按南港那套 init/paint/build 建——模块眼里窗口就是一个「街区框」。
   - 浮动原点：场景原点 = 窗口左上角。窗口挪了，相机、看点、远景组一起反向平移同一个量，画面不跳。
   - 远景 = citylod.js：每块一张粗地形（带裙边）+ 一块房子体块网格；29 座地标剪影。窗口里的块藏远景、窗口外的块藏近景（近景本来就只建窗口）。
   - 高度：全城一个 ground(x,z)（同 core 的公式：高程格 × 1.3 + 水陆蒙版过渡），近景 4 px 网格、远景 16 px 网格都从它取，所以接缝只差插值，裙边盖住。
   - 镜头很高（> ALT_FULL）时不要近景窗口，整城只画远景（航拍首屏不用下近景块）。
   钩子：window.__ready、__trisTotal（当前画面里可见的三角形）、__chunkStats、__bytes()、__applyShot(s)、__setYear(Y)、__view(...)（全城坐标）。 */
import * as THREE from 'three';
import {MapControls} from 'three/addons/controls/MapControls.js';
import * as sky from './sky.js';
import * as terrain from './terrain.js';
import * as water from './water.js';
import * as streets from './streets.js';
import * as buildings from './buildings.js';
import * as landmarks from './landmarks/index.js';
import * as props from './props.js';
import * as flora from './flora.js';
import * as crowd from './crowd.js';
import * as LOD from './citylod.js';

const CFG = globalThis.CS3D || {};
const BASE = new URL(CFG.base || '3d/', location.href).href;
const QS = new URLSearchParams(location.search);
const $ = id => document.getElementById(id);
const MODULES = [sky, terrain, water, streets, buildings, landmarks, props, flora, crowd];
const ONLY = QS.get('only') ? new Set(['sky', 'terrain', 'water', ...QS.get('only').split(',').map(s => s.trim())]) : null;
const ACTIVE = MODULES.filter(m => !ONLY || ONLY.has(m.name));
const T_START = performance.now();
const BD = await fetch(BASE + 'base.json').then(r => r.json());
const CW = BD.W, CH = BD.H, E = BD.elev, MPP = E.mpp, CK = BD.chunk, CS = CK.size, NI = CK.n[0], NJ = CK.n[1];
const WN = +(QS.get('win') || 4), WIN = CS * WN;                 // 近景窗口：WN×WN 块
const ALT_FULL = +(QS.get('altFull') || 2600);                  // 镜头高于这个（px）不要近景窗口
const LO_FAR = +(QS.get('loFar') || 11000);                     // 远景房子块的可见距离（px）；地形块一直在
const hsh = (n, k = 0) => { let x = (Math.imul(n | 0, 2654435761) + Math.imul(k, 40503)) >>> 0; x ^= x >>> 15; x = Math.imul(x, 2246822519) >>> 0; x ^= x >>> 13; return (x >>> 0) / 4294967296 };
const EX = 1.3;

/* ---- 全城高度（同 core.js 的 elevPx / 蒙版 / ground 公式，坐标 = 全城像素） ---- */
function elevG(x, y) { const s = E.st, gx = Math.max(0, Math.min(E.w - 1.001, x / s)), gy = Math.max(0, Math.min(E.h - 1.001, y / s)), i = gx | 0, j = gy | 0, fx = gx - i, fy = gy - j, g = (a, b) => E.dm[b * E.w + a] / 10;
  const m = (g(i, j) * (1 - fx) + g(i + 1, j) * fx) * (1 - fy) + (g(i, j + 1) * (1 - fx) + g(i + 1, j + 1) * fx) * fy; return m / MPP * EX }
const byG = {}; for (const f of BD.features) (byG[f.t] = byG[f.t] || []).push(f);
let YEAR = +(QS.get('year') || $('yr').value);
const liveY = f => f.y0 <= YEAR && (f.y1 == null || f.y1 > YEAR);
const mask = document.createElement('canvas'); mask.width = Math.ceil(CW / 4); mask.height = Math.ceil(CH / 4); const MX = mask.getContext('2d'); let MD = null;
function buildMask() { MX.setTransform(.25, 0, 0, .25, 0, 0); MX.fillStyle = '#000'; MX.fillRect(0, 0, CW, CH);
  const fillRings = (g, col) => { MX.beginPath(); for (const P of g) for (const r of P) { MX.moveTo(r[0][0], r[0][1]); for (const p of r) MX.lineTo(p[0], p[1]); MX.closePath() } MX.fillStyle = col; MX.fill('evenodd') };
  fillRings(byG.land[0].g, '#fff');
  for (const f of byG.mole || []) if (liveY(f)) fillRings(f.g, '#fff');
  for (const f of byG.water || []) if (f.k === 'harbor' && liveY(f)) fillRings(f.g, '#000');
  const M2 = document.createElement('canvas'); M2.width = mask.width; M2.height = mask.height; const m2 = M2.getContext('2d', {willReadFrequently: true}); m2.filter = 'blur(1.5px)'; m2.drawImage(mask, 0, 0);
  MD = m2.getImageData(0, 0, mask.width, mask.height).data }
function cover(x, y) { const fx = Math.max(0, Math.min(mask.width - 1.001, x / 4 - .5)), fy = Math.max(0, Math.min(mask.height - 1.001, y / 4 - .5)), i = fx | 0, j = fy | 0, a = fx - i, b = fy - j, g = (u, v) => MD[(v * mask.width + u) * 4] / 255; return (g(i, j) * (1 - a) + g(i + 1, j) * a) * (1 - b) + (g(i, j + 1) * (1 - a) + g(i + 1, j + 1) * a) * b }
const groundG = (x, y) => { const c = cover(x, y), t = Math.min(1, Math.max(0, (c - .3) / .4)), s = t * t * (3 - 2 * t); return -6 + (elevG(x, y) + 7.5) * s };

/* ---- 几何小工具（同 core.js；core 是南港页的入口模块，载入它就会起南港，所以这里抄一份） ---- */
function quadAxes(P) { const cx = (P[0][0] + P[1][0] + P[2][0] + P[3][0]) / 4, cz = (P[0][1] + P[1][1] + P[2][1] + P[3][1]) / 4;
  const ux = P[1][0] - P[0][0], uz = P[1][1] - P[0][1], vx = P[3][0] - P[0][0], vz = P[3][1] - P[0][1], Lu = Math.hypot(ux, uz), Lv = Math.hypot(vx, vz);
  return Lu >= Lv ? {cx, cz, ax: ux / Lu, az: uz / Lu, hu: Lu / 2, hv: Lv / 2} : {cx, cz, ax: vx / Lv, az: vz / Lv, hu: Lv / 2, hv: Lu / 2} }
function rectOf(G) { let cx = 0, cz = 0; for (const q of G) { cx += q[0]; cz += q[1] } cx /= G.length; cz /= G.length; let best = null; for (let i = 0; i < G.length; i++) { const a = G[i], b = G[(i + 1) % G.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (!best || L > best.L) best = {L, ax: (b[0] - a[0]) / L, az: (b[1] - a[1]) / L} }
  let hu = 0, hv = 0; for (const q of G) { const dx = q[0] - cx, dz = q[1] - cz; hu = Math.max(hu, Math.abs(dx * best.ax + dz * best.az)); hv = Math.max(hv, Math.abs(-dx * best.az + dz * best.ax)) } return {cx, cz, ax: best.ax, az: best.az, hu, hv} }
const RQ = (r, u0, v0, u1, v1) => { const c = (u, v) => [r.cx + r.ax * u - r.az * v, r.cz + r.az * u + r.ax * v]; return [c(u0, v0), c(u1, v0), c(u1, v1), c(u0, v1)] };
const pathRings = (X, g) => { for (const P of g) for (const ring of P) { X.moveTo(ring[0][0], ring[0][1]); for (let i = 1; i < ring.length; i++) X.lineTo(ring[i][0], ring[i][1]); X.closePath() } };

/* ---- three ---- */
const rnd = new THREE.WebGLRenderer({antialias: true}); rnd.setPixelRatio(Math.min(1.5, devicePixelRatio)); rnd.setSize(innerWidth, innerHeight); rnd.shadowMap.enabled = true; rnd.shadowMap.type = THREE.PCFSoftShadowMap; document.body.prepend(rnd.domElement);
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 2, 16000);
const ctl = new MapControls(cam, rnd.domElement); ctl.maxPolarAngle = 1.42; ctl.minDistance = 40; ctl.maxDistance = 12000; ctl.enableDamping = true; ctl.dampingFactor = .12;
const CITY = new THREE.Group(); CITY.name = 'city-lod'; scene.add(CITY);   // 远景：全城坐标，position = −窗口原点

/* ---- 近景窗口的状态（窗口局部坐标 = 全城坐标 − (OX, OZ)） ---- */
let OX = 0, OZ = 0, WI = -99, WJ = -99, WIN_ON = false;
const TS = Math.min(2, 4096 / WIN), tex = document.createElement('canvas'); tex.width = Math.round(WIN * TS); tex.height = Math.round(WIN * TS); const X = tex.getContext('2d');
const gtex = new THREE.CanvasTexture(tex); gtex.colorSpace = THREE.SRGBColorSpace; gtex.anisotropy = rnd.capabilities.getMaxAnisotropy();
const GM_S = 4, GM_N = Math.ceil(WIN / GM_S) + 1; let GM = null;
function groundMesh(x, z) { if (x < 0 || z < 0 || x > WIN || z > WIN) return groundG(x + OX, z + OZ);   // 窗口外：全城光滑地面
  if (!GM) GM = new Float32Array(GM_N * GM_N).fill(NaN);
  const g = (i, j) => { i = Math.max(0, Math.min(GM_N - 1, i)); j = Math.max(0, Math.min(GM_N - 1, j)); const k = j * GM_N + i; let v = GM[k]; if (v !== v) v = GM[k] = groundG(Math.min(WIN, i * GM_S) + OX, Math.min(WIN, j * GM_S) + OZ); return v };
  const fx0 = x / GM_S, fz0 = z / GM_S, i = Math.floor(fx0), j = Math.floor(fz0), fx = fx0 - i, fz = fz0 - j;
  if (fx + fz <= 1) return g(i, j) + (g(i + 1, j) - g(i, j)) * fx + (g(i, j + 1) - g(i, j)) * fz; return g(i + 1, j + 1) + (g(i, j + 1) - g(i + 1, j + 1)) * (1 - fx) + (g(i + 1, j) - g(i + 1, j + 1)) * (1 - fz) }
function footing(P, step = 2) { let mn = 1e9, mx = -1e9; const add = (x, z) => { const h = groundMesh(x, z); mx = Math.max(mx, h); mn = Math.min(mn, Math.max(h, 0)) };
  if (P.length === 4) { const n = Math.max(1, Math.ceil(Math.max(Math.hypot(P[1][0] - P[0][0], P[1][1] - P[0][1]), Math.hypot(P[3][0] - P[0][0], P[3][1] - P[0][1])) / step));
    for (let a = 0; a <= n; a++) for (let b = 0; b <= n; b++) { const s = a / n, t = b / n; add((P[0][0] * (1 - s) + P[1][0] * s) * (1 - t) + (P[3][0] * (1 - s) + P[2][0] * s) * t, (P[0][1] * (1 - s) + P[1][1] * s) * (1 - t) + (P[3][1] * (1 - s) + P[2][1] * s) * t) } }
  else for (const p of P) add(p[0], p[1]);
  const cx = P.reduce((a, p) => a + p[0], 0) / P.length, cz = P.reduce((a, p) => a + p[1], 0) / P.length; return {min: mn, max: mx, mid: groundMesh(cx, cz), inMap: true} }
const foot = q => { (ctx.reg.footings = ctx.reg.footings || []).push(q) };
let CUR = null;
const ctx = {THREE, scene, camera: cam, renderer: rnd, controls: ctl, WD: null, by: {}, W: WIN, H: WIN, year: YEAR,
  live: f => f.y0 <= ctx.year && (f.y1 == null || f.y1 > ctx.year),
  elevPx: (x, y) => elevG(x + OX, y + OZ), ground: (x, z) => groundG(x + OX, z + OZ), groundMesh, footing, foot, hsh,
  geom: {quadAxes, rectOf, RQ, pathRings}, groundCanvas: tex, groundTex: gtex, groundScale: TS, reg: {},
  quality: QS.get('quality') || 'high', QS, time: 0, add(o) { o.userData.mod = CUR; scene.add(o); return o },
  only: ONLY ? [...ONLY] : null, modules: ACTIVE.map(m => m.name),
  noOuter: true, landmarkIds: landmarks.IDS, ox: 0, oz: 0, city: {W: CW, H: CH, chunk: CS}};
for (const m of ACTIVE) { CUR = m.name; m.init?.(ctx) } CUR = null;

/* ---- 分块数据（流式） ---- */
const IDX = CK.index, KEY = (i, j) => i + '_' + j, FULL = new Map(), LOW = new Map(), PEND = new Map();
const BYTES = {base: 0, low: 0, full: 0, fullN: 0, lowN: 0};
async function getJSON(u) { const r = await fetch(u); const t = await r.text(); return [JSON.parse(t), t.length] }
function loadFull(k) { if (FULL.has(k)) return Promise.resolve(FULL.get(k)); if (!IDX[k]) return Promise.resolve(null); if (PEND.has(k)) return PEND.get(k);
  const p = getJSON(BASE + 'chunks/f_' + k + '.json').then(([d, n]) => { FULL.set(k, d); BYTES.full += n; BYTES.fullN++; PEND.delete(k); return d }); PEND.set(k, p); return p }
async function loadLow(k) { if (LOW.has(k) || !IDX[k]) return LOW.get(k); const [d, n] = await getJSON(BASE + 'chunks/l_' + k + '.json'); LOW.set(k, d); BYTES.low += n; BYTES.lowN++; return d }

/* ---- 远景 ---- */
const lodTerrMat = new THREE.MeshLambertMaterial({map: null});
const lodHouseMat = new THREE.MeshLambertMaterial({vertexColors: true, side: THREE.DoubleSide});
const LC = {};  // key → {terr, houses, i, j}
const LM_SIL = new Map();  // landmark id → mesh
const CTS = Math.min(1, 4096 / Math.max(CW, CH)), ctex = document.createElement('canvas'); ctex.width = Math.round(CW * CTS); ctex.height = Math.round(CH * CTS); const CX = ctex.getContext('2d');
const cityTex = new THREE.CanvasTexture(ctex); cityTex.colorSpace = THREE.SRGBColorSpace; cityTex.anisotropy = rnd.capabilities.getMaxAnisotropy(); lodTerrMat.map = cityTex;
/* 全城地面贴图：直接调 terrain / water / streets 三个模块自己的 paint（同一套颜色），ctx 换成全城的（街来自远景简块） */
function paintCity() { const t0 = performance.now(); const street = []; for (const L of LOW.values()) for (const s of L.s) street.push({t: 'street', k: CK.ks[s[0]], w: s[1], g: [s[2], s[3], s[4], s[5]], y0: s[6], y1: s[7] < 0 ? null : s[7]});
  const cc = {W: CW, H: CH, WD: {bands: BD.bands}, by: {...byG, street}, year: YEAR, live: liveY, geom: {pathRings}};
  for (const m of [terrain, water, streets]) { CX.save(); CX.setTransform(CTS, 0, 0, CTS, 0, 0); m.paint(cc, CX); CX.restore() }
  CX.save(); CX.setTransform(CTS, 0, 0, CTS, 0, 0); for (const L of LOW.values()) LOD.paintRoofs(CX, L, YEAR, hsh); CX.restore();
  cityTex.needsUpdate = true; return Math.round(performance.now() - t0) }
function buildLodTerrain() { for (let j = 0; j < NJ; j++) for (let i = 0; i < NI; i++) { const k = KEY(i, j);
    if (!IDX[k]) { let land = false; for (let a = 0; a <= 8 && !land; a++) for (let b = 0; b <= 8; b++) if (groundG(i * CS + a * CS / 8, j * CS + b * CS / 8) > -3) { land = true; break } if (!land) continue }
    const o = LC[k] || (LC[k] = {i, j}); if (o.terr) { CITY.remove(o.terr); o.terr.geometry.dispose() }
    o.terr = LOD.terrainChunk(THREE, i, j, CS, groundG, CW, CH, lodTerrMat); CITY.add(o.terr) } }
function buildLodHouses() { let n = 0; for (const [k, L] of LOW) { const o = LC[k] || (LC[k] = {i: L.i, j: L.j}); if (o.houses) { CITY.remove(o.houses); o.houses.geometry.dispose(); o.houses = null }
    const m = LOD.housesChunk(THREE, L, CK.fn, YEAR, groundG, hsh, lodHouseMat); if (m) { o.houses = m; CITY.add(m); n += m.userData.n } } return n }
function buildLodLandmarks() { for (const m of LM_SIL.values()) { CITY.remove(m); m.geometry.dispose() } LM_SIL.clear();
  for (const f of byG.landmark || []) if (liveY(f)) { const m = LOD.landmarkMass(THREE, f, groundG, lodHouseMat); if (m) { m.userData.f = f; LM_SIL.set(f.id, m); CITY.add(m) } } }
let RIM = null;
function rebuildRim() { if (RIM) { CITY.remove(RIM); RIM.geometry.dispose(); RIM = null } if (!WIN_ON) return; RIM = LOD.rimSkirt(THREE, OX, OZ, WIN, (x, z) => groundMesh(x - OX, z - OZ), CW, CH, lodTerrMat); CITY.add(RIM) }
const inWin = (i, j) => WIN_ON && i >= WI && i < WI + WN && j >= WJ && j < WJ + WN;
const lmInWin = f => { if (!WIN_ON || !buildings.PART_KINDS.has(f.k)) return false; const r = rectOf(f.g); return r.cx >= OX && r.cx < OX + WIN && r.cz >= OZ && r.cz < OZ + WIN };
function lodVisibility() { const cp = cam.position, gx = cp.x + OX, gz = cp.z + OZ;
  for (const k in LC) { const o = LC[k], w = inWin(o.i, o.j), d = Math.hypot((o.i + .5) * CS - gx, (o.j + .5) * CS - gz, cp.y);
    if (o.terr) o.terr.visible = !w; if (o.houses) o.houses.visible = !w && d < LO_FAR }
  for (const m of LM_SIL.values()) m.visible = !lmInWin(m.userData.f) }

/* ---- 近景窗口：要素平移进窗口局部坐标 ---- */
const mvP = (p, dx, dz) => [p[0] - dx, p[1] - dz, ...p.slice(2)];
const mvMP = (g, dx, dz) => g.map(P => P.map(r => r.map(p => mvP(p, dx, dz))));
function shift(f, dx, dz) { const o = {...f};
  switch (f.t) {
    case 'house': o.p = f.p.map((v, i) => i % 2 ? v - dz : v - dx); break;
    case 'street': o.g = [f.g[0] - dx, f.g[1] - dz, f.g[2] - dx, f.g[3] - dz]; break;
    case 'fountain': o.x = f.x - dx; o.y = f.y - dz; break;
    case 'pier': case 'cistern': case 'landmark': case 'aqueduct': o.g = f.g.map(p => mvP(p, dx, dz)); break;
    case 'land': case 'water': case 'mole': o.g = mvMP(f.g, dx, dz); break;
  } return o }
const BANDS_CACHE = new Map();
function windowWD(dx, dz) { const feats = [], trees = [];
  for (const f of BD.features) { if (f.t === 'landmark') { const r = rectOf(f.g); if (!(r.cx >= dx && r.cx < dx + WIN && r.cz >= dz && r.cz < dz + WIN)) continue }
    if (f.t === 'water' && f.k === 'harbor' || f.t === 'mole') { let x0 = 1e9, x1 = -1e9, z0 = 1e9, z1 = -1e9; for (const P of f.g) for (const p of P[0]) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); z0 = Math.min(z0, p[1]); z1 = Math.max(z1, p[1]) }
      if (x1 < dx - 50 || x0 > dx + WIN + 50 || z1 < dz - 50 || z0 > dz + WIN + 50) continue }
    feats.push(shift(f, dx, dz)) }
  for (let j = WJ; j < WJ + WN; j++) for (let i = WI; i < WI + WN; i++) { const F = FULL.get(KEY(i, j)); if (!F) continue;
    for (const f of F.features) feats.push(shift(f, dx, dz)); for (const t of F.trees) trees.push([t[0] - dx, t[1] - dz, ...t.slice(2)]) }
  const bk = dx + ',' + dz; let bands = BANDS_CACHE.get(bk); if (!bands) { bands = BD.bands.map(b => ({lv: b.lv, g: mvMP(b.g, dx, dz)})); BANDS_CACHE.clear(); BANDS_CACHE.set(bk, bands) }
  return {q: 'city-window', W: WIN, H: WIN, elev: E, years: BD.years, nodes: BD.nodes, bands, features: feats, trees, pal: []} }

let built = false, REB = 0, LAST_MS = 0;
function rebuildWindow() { const t0 = performance.now(); const stats = {};
  if (built) for (const m of ACTIVE) { CUR = m.name; m.dispose?.(ctx) }
  ctx.reg = {}; GM = null; ctx.year = YEAR; ctx.ox = OX; ctx.oz = OZ;
  const WD = windowWD(OX, OZ); ctx.WD = WD; const by = {}; for (const f of WD.features) (by[f.t] = by[f.t] || []).push(f); ctx.by = by;
  X.setTransform(TS, 0, 0, TS, 0, 0);
  for (const m of ACTIVE) if (m.paint) { X.save(); X.setTransform(TS, 0, 0, TS, 0, 0); const t = performance.now(); m.paint(ctx, X); X.restore(); stats[m.name] = {paint_ms: Math.round(performance.now() - t)} }
  for (const m of ACTIVE) { CUR = m.name; const t = performance.now(); m.build?.(ctx); (stats[m.name] = stats[m.name] || {}).build_ms = Math.round(performance.now() - t) }
  CUR = null; gtex.needsUpdate = true; built = true; REB++; LAST_MS = Math.round(performance.now() - t0);
  window.__modStats = stats; window.__buildMs = LAST_MS }
function setWinVisible(on) { for (const o of scene.children) { const k = o.userData.mod; if (!k || k === 'sky' || k === 'water') continue; o.visible = on } }

/* 把窗口挪到左上角块 (ci, cj)：取块 → 浮动原点平移 → 重建 */
let BUSY = null;
async function placeWindow(ci, cj) {
  ci = Math.max(0, Math.min(NI - WN, ci)); cj = Math.max(0, Math.min(NJ - WN, cj));
  if (WIN_ON && ci === WI && cj === WJ) return;
  const ks = []; for (let j = cj; j < cj + WN; j++) for (let i = ci; i < ci + WN; i++) ks.push(KEY(i, j));
  await Promise.all(ks.map(loadFull));
  const nx = ci * CS, nz = cj * CS, dx = nx - OX, dz = nz - OZ;
  cam.position.x -= dx; cam.position.z -= dz; ctl.target.x -= dx; ctl.target.z -= dz; ctl.update();
  OX = nx; OZ = nz; WI = ci; WJ = cj; WIN_ON = true; CITY.position.set(-OX, 0, -OZ);
  rebuildWindow(); setWinVisible(true); rebuildRim(); lodVisibility();
  /* 预取外面一圈；窗口外两圈以外的近景块丢掉（远景简块常驻） */
  for (let j = cj - 1; j <= cj + WN; j++) for (let i = ci - 1; i <= ci + WN; i++) if (IDX[KEY(i, j)]) loadFull(KEY(i, j)).catch(() => {});
  for (const k of [...FULL.keys()]) { const [i, j] = k.split('_').map(Number); if (i < ci - 2 || i > ci + WN + 1 || j < cj - 2 || j > cj + WN + 1) FULL.delete(k) } }
function dropWindow() { if (!WIN_ON) return; WIN_ON = false; setWinVisible(false); rebuildRim(); lodVisibility() }
/* 每帧看一眼：看点离窗口中心超过一块就挪（滞后一块），镜头太高就收掉近景 */
function wantWindow() { const gx = ctl.target.x + OX, gz = ctl.target.z + OZ, alt = cam.position.y;
  if (alt > ALT_FULL) return null;
  if (WIN_ON) { const cx = OX + WIN / 2, cz = OZ + WIN / 2; if (Math.abs(gx - cx) <= CS && Math.abs(gz - cz) <= CS) return [WI, WJ] }
  return [Math.round(gx / CS - WN / 2), Math.round(gz / CS - WN / 2)] }
async function stream() { if (BUSY) return BUSY; const w = wantWindow();
  if (!w) { if (WIN_ON) dropWindow(); return }
  const ci = Math.max(0, Math.min(NI - WN, w[0])), cj = Math.max(0, Math.min(NJ - WN, w[1]));
  if (WIN_ON && ci === WI && cj === WJ) return;
  BUSY = placeWindow(ci, cj).finally(() => { BUSY = null }); return BUSY }

/* ---- 首屏：base → 全城远景简块 → 全城贴图/远景 → 近景窗口 ---- */
setWinVisible(false);   // 没放窗口前，模块 init 建的常驻网格（terrain 平面等）先藏着
buildMask();
await Promise.all(Object.keys(IDX).map(loadLow));
const T_LOW = Math.round(performance.now() - T_START);
let paintMs = paintCity(); buildLodTerrain(); let lodHouses = buildLodHouses(); buildLodLandmarks();
function fullYear(Y) { YEAR = Y; ctx.year = Y; $('yr').value = Y; $('yl').textContent = '建城 ' + Y + ' 年'; buildMask(); paintMs = paintCity(); buildLodTerrain(); lodHouses = buildLodHouses(); buildLodLandmarks(); if (WIN_ON) { rebuildWindow(); rebuildRim() } lodVisibility() }
let pend = 0; $('yr').oninput = e => { const Y = +e.target.value; $('yl').textContent = '建城 ' + Y + ' 年'; clearTimeout(pend); pend = setTimeout(() => fullYear(Y), 80) };
$('yr').value = YEAR; $('yl').textContent = '建城 ' + YEAR + ' 年';
addEventListener('resize', () => { cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); rnd.setSize(innerWidth, innerHeight) });

/* ---- 三角形：只数画面里看得见的（可见链 + 视锥），THREE.LOD 按当前档 ---- */
const FR = new THREE.Frustum(), PM = new THREE.Matrix4(), SPH = new THREE.Sphere();
function trisVisible() { cam.updateMatrixWorld(); PM.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); FR.setFromProjectionMatrix(PM); let n = 0, all = 0; const per = {};
  const walk = (o, vis, mk) => { vis = vis && o.visible; mk = o.userData.mod || mk; if (o.isLOD) { /* 只走当前档 */ const lv = o.levels; let cur = null; for (const l of lv) if (l.object.visible) cur = l.object; for (const l of lv) walk(l.object, vis && l.object === cur, mk); return }
    if (o.isMesh && o.geometry) { const g = o.geometry, t = (g.index ? g.index.count : (g.attributes.position ? g.attributes.position.count : 0)) / 3 * (o.isInstancedMesh ? o.count : 1); all += t;
      if (vis) { let inF = true; if (o.frustumCulled && !o.isInstancedMesh) { if (!g.boundingSphere) g.computeBoundingSphere(); SPH.copy(g.boundingSphere).applyMatrix4(o.matrixWorld); inF = FR.intersectsSphere(SPH) } if (inF) { n += t; const k = mk || (o.name.startsWith('lod-') ? o.name.split(':')[0] : 'other'); per[k] = (per[k] || 0) + t } } }
    for (const c of o.children) walk(c, vis, mk) };
  walk(scene, true); window.__trisTotal = Math.round(n); window.__trisAll = Math.round(all); window.__trisPer = Object.fromEntries(Object.entries(per).map(([k, v]) => [k, Math.round(v)])); return window.__trisTotal }
function chunkStats() { let lowVis = 0, lowHidden = 0; for (const k in LC) { const o = LC[k]; if (o.houses) (o.houses.visible ? lowVis++ : lowHidden++) }
  return window.__chunkStats = {grid: [NI, NJ], size: CS, chunks: Object.keys(IDX).length, window: WIN_ON ? {i: WI, j: WJ, n: WN, origin: [OX, OZ], px: WIN} : null,
    fullLoaded: FULL.size, fullFetched: BYTES.fullN, lowLoaded: LOW.size, lodHouseChunksVisible: lowVis, lodHouseChunksHidden: lowHidden, lodHouses, landmarksSil: [...LM_SIL.values()].filter(m => m.visible).length,
    rebuilds: REB, lastRebuildMs: LAST_MS, bytesJSON: {...BYTES}, firstLowMs: T_LOW, paintCityMs: paintMs, tris: window.__trisTotal} }
window.__bytes = () => { const R = performance.getEntriesByType('resource'); let enc = 0, dec = 0, tr = 0; for (const r of R) { enc += r.encodedBodySize || 0; dec += r.decodedBodySize || 0; tr += r.transferSize || 0 } return {n: R.length, encoded: enc, decoded: dec, transfer: tr} };

/* ---- 机位（全城坐标）：?shot=N 读 3d/shots.json ---- */
if (QS.has('clean')) for (const id of ['tag', 'bar', 'fps', 'cst']) if ($(id)) $(id).style.display = 'none';
let SHOT_T = 0;
window.__applyShot = async s => { if (s.year != null && s.year !== YEAR) fullYear(s.year);
  const gy = (x, z) => s.eye ? Math.max(0, groundG(x, z)) : 0, p = s.pos, t = s.target; ctl.maxPolarAngle = Math.PI / 2 + .15; ctl.minDistance = 1; SHOT_T = s.t || 0;
  cam.fov = s.fov || 40; cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix();
  const P = [p[0], p[1] + gy(p[0], p[2]), p[2]], Tg = [t[0], t[1] + gy(t[0], t[2]), t[2]];
  cam.position.set(P[0] - OX, P[1], P[2] - OZ); ctl.target.set(Tg[0] - OX, Tg[1], Tg[2] - OZ); ctl.update(); farFor();
  await stream(); cam.position.set(P[0] - OX, P[1], P[2] - OZ); ctl.target.set(Tg[0] - OX, Tg[1], Tg[2] - OZ); ctl.update(); lodVisibility(); window.__shot = s.id };
window.__view = async (px, py, pz, tx, ty, tz) => { cam.position.set(px - OX, py, pz - OZ); ctl.target.set(tx - OX, ty, tz - OZ); ctl.update(); farFor(); await stream(); lodVisibility() };
window.__setYear = Y => fullYear(Y);
window.__ctx = ctx; window.__origin = () => [OX, OZ];
window.__ground = (x, z) => groundG(x, z);
/* 镜头高时把 far 拉远（雾跟着 far 走，sky.tick），整城才不会全埋在霾里 */
function farFor() { const f = Math.max(16000, Math.min(40000, cam.position.y * 6)); if (Math.abs(cam.far - f) > 1) { cam.far = f; cam.updateProjectionMatrix() } }

const TICK = ACTIVE.filter(m => m.tick);
let fN = 0, fT = performance.now(), T0 = performance.now(), lastS = 0; window.__fps = 0;
const frame = () => { ctl.update(); farFor(); const now = performance.now();
  if (now - lastS > 250) { lastS = now; stream(); lodVisibility() }
  if (TICK.length) { ctx.time = (now - T0) / 1000; for (const m of TICK) m.tick(ctx, ctx.time) } rnd.render(scene, cam); fN++;
  if (now - fT > 1000) { window.__fps = fN * 1000 / (now - fT); trisVisible(); const c = chunkStats(); $('fps').textContent = window.__fps.toFixed(0) + ' fps · ' + (window.__trisTotal / 1e6).toFixed(2) + ' M △'; if ($('cst')) $('cst').textContent = c.window ? `近景窗口 ${c.window.i},${c.window.j}（${WN}×${WN} 块）· 已载 ${c.fullLoaded} 近景块 / ${c.lowLoaded} 远景块` : `航拍：全城远景 ${c.lowLoaded} 块`; fN = 0; fT = now } };
const STILL = QS.has('still');
window.__still = () => { ctl.update(); farFor(); lodVisibility(); ctx.time = SHOT_T; for (const m of TICK) m.tick(ctx, SHOT_T); rnd.render(scene, cam); trisVisible(); chunkStats(); return rnd.domElement.toDataURL('image/png') };
window.__frame = () => { ctl.update(); farFor(); lodVisibility(); for (const m of TICK) m.tick(ctx, ctx.time); rnd.render(scene, cam); const n = trisVisible(); chunkStats(); return n };

/* 起始机位：?shot= 或默认（全城中部偏南的中景） */
let S0 = null; try { S0 = await fetch(BASE + 'shots.json').then(r => r.json()) } catch (e) { console.warn('shots.json', e) }
window.__shots = S0;
const s0 = S0 && (QS.has('shot') ? S0.shots.find(x => String(x.id) === QS.get('shot') || x.name === QS.get('shot')) : S0.shots.find(x => x.name === (S0.start || 'mid')));
if (s0) await window.__applyShot(s0); else { cam.position.set(3000, 1400, 5600); ctl.target.set(3000, 0, 3800); ctl.update(); await stream() }
if (!STILL) rnd.setAnimationLoop(frame);
rnd.render(scene, cam); trisVisible(); chunkStats();
window.__firstMs = Math.round(performance.now() - T_START);
window.__ready = 1;
