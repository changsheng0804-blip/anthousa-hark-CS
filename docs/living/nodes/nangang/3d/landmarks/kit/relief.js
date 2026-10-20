/* landmarks 部件 · 程序化浮雕贴图：高度图（画布里画灰度形状）→ 模糊 → 法线贴图 + 带凹缝暗部的反照率贴图。——Hark（CS线）2026-10-20
   不贴照片、不下载：所有人物、花环、框都是代码画的形状。确定性：随机一律用 rng(seed)（mulberry32）。
   不用 ctx.filter（Safari 不支持），模糊自己做（可分离盒式模糊，两遍 ≈ 高斯）。
     const R = relief(T, W, H, (g, rng) => {...画高度：黑 = 最深，白 = 最高...}, {seed, blur, strength, base, ao})
     → {map, normalMap}（CanvasTexture；map 是 sRGB，normalMap 是线性）
   画人物的小函数（figure / captive / victory / garland / frame）在这里，凯旋门、方尖碑底座等以后照样用。 */
export function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function boxBlur(src, W, H, r, wrapX, wrapY) {
  if (r < 1) return src;
  const tmp = new Float32Array(W * H), out = new Float32Array(W * H), n = 2 * r + 1;
  const ix = (x) => wrapX ? (x % W + W) % W : Math.max(0, Math.min(W - 1, x));
  const iy = (y) => wrapY ? (y % H + H) % H : Math.max(0, Math.min(H - 1, y));
  for (let y = 0; y < H; y++) {
    let s = 0; const row = y * W;
    for (let k = -r; k <= r; k++) s += src[row + ix(k)];
    for (let x = 0; x < W; x++) { tmp[row + x] = s / n; s += src[row + ix(x + r + 1)] - src[row + ix(x - r)]; }
  }
  for (let x = 0; x < W; x++) {
    let s = 0;
    for (let k = -r; k <= r; k++) s += tmp[iy(k) * W + x];
    for (let y = 0; y < H; y++) { out[y * W + x] = s / n; s += tmp[iy(y + r + 1) * W + x] - tmp[iy(y - r) * W + x]; }
  }
  return out;
}

export function relief(T, W, H, paint, opt = {}) {
  const seed = opt.seed ?? 1, R = rng(seed), wrapX = !!opt.wrapX, wrapY = !!opt.wrapY;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const g = cv.getContext('2d', { willReadFrequently: true });
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  paint(g, R, W, H);
  const src = g.getImageData(0, 0, W, H).data;
  let h = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++) h[i] = src[i * 4] / 255;
  h = boxBlur(boxBlur(h, W, H, opt.blur ?? 1, wrapX, wrapY), W, H, opt.blur ?? 1, wrapX, wrapY);
  const big = boxBlur(boxBlur(h, W, H, opt.aoR ?? 6, wrapX, wrapY), W, H, opt.aoR ?? 6, wrapX, wrapY);
  const s = opt.strength ?? 6, base = opt.base ?? [236, 227, 210], aoK = opt.ao ?? 2.2, dirt = opt.dirt ?? 0.06;
  const nimg = g.createImageData(W, H), aimg = g.createImageData(W, H), N = nimg.data, A = aimg.data;
  const at = (x, y) => h[(wrapY ? (y % H + H) % H : Math.max(0, Math.min(H - 1, y))) * W + (wrapX ? (x % W + W) % W : Math.max(0, Math.min(W - 1, x)))];
  // 低频斑驳（风化）：几层不同尺度的确定性正弦和，避免再开一个噪声库
  const ph = Array.from({ length: 6 }, () => R() * 6.283), fr = Array.from({ length: 6 }, (_, k) => (k + 1) * 2.1 + R());
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    let nx = (at(x - 1, y) - at(x + 1, y)) * s, ny = (at(x, y + 1) - at(x, y - 1)) * s, nz = 1;
    const L = Math.hypot(nx, ny, nz); nx /= L; ny /= L; nz /= L;
    N[i * 4] = (nx * .5 + .5) * 255; N[i * 4 + 1] = (ny * .5 + .5) * 255; N[i * 4 + 2] = (nz * .5 + .5) * 255; N[i * 4 + 3] = 255;
    const cav = Math.max(0, big[i] - h[i]);
    const ao = Math.max(0.42, 1 - aoK * cav) * (0.9 + 0.1 * h[i]);
    let m = 0; for (let k = 0; k < 6; k++) m += Math.sin((x / W) * fr[k] * 6.283 * (wrapX ? 1 : 1.3) + ph[k]) * Math.sin((y / H) * fr[(k + 2) % 6] * 6.283 + ph[(k + 3) % 6]);
    const w = 1 - dirt * (0.5 + 0.5 * Math.tanh(m)) - (opt.streak ? opt.streak * Math.max(0, Math.sin(x * 0.37 + ph[1]) * Math.sin(x * 0.11 + ph[2])) : 0);
    A[i * 4] = Math.min(255, base[0] * ao * w); A[i * 4 + 1] = Math.min(255, base[1] * ao * w); A[i * 4 + 2] = Math.min(255, base[2] * ao * w * 0.985); A[i * 4 + 3] = 255;
  }
  const mk = (img, srgb) => {
    const c = document.createElement('canvas'); c.width = W; c.height = H; c.getContext('2d').putImageData(img, 0, 0);
    const t = new T.CanvasTexture(c); if (srgb) t.colorSpace = T.SRGBColorSpace;
    t.wrapS = wrapX ? T.RepeatWrapping : T.ClampToEdgeWrapping; t.wrapT = wrapY ? T.RepeatWrapping : T.ClampToEdgeWrapping;
    t.anisotropy = opt.aniso ?? 4; t.generateMipmaps = true; t.minFilter = T.LinearMipmapLinearFilter;
    return t;
  };
  return { map: mk(aimg, true), normalMap: mk(nimg, false) };
}

/* ---- 画高度的小形状（画布坐标：x 向右、y 向下；v = 0..1 高度灰度） ---- */
const grey = v => { const c = Math.round(Math.max(0, Math.min(1, v)) * 255); return `rgb(${c},${c},${c})`; };
export function ell(g, x, y, rx, ry, v, rot = 0) { g.fillStyle = grey(v); g.beginPath(); g.ellipse(x, y, Math.max(.5, rx), Math.max(.5, ry), rot, 0, Math.PI * 2); g.fill(); }
export function poly(g, pts, v) { g.fillStyle = grey(v); g.beginPath(); g.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) g.lineTo(p[0], p[1]); g.closePath(); g.fill(); }
export function line(g, x0, y0, x1, y1, w, v) { g.strokeStyle = grey(v); g.lineWidth = w; g.lineCap = 'round'; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); }
export function rect(g, x, y, w, h, v) { g.fillStyle = grey(v); g.fillRect(x, y, w, h); }

/* 站立的士兵：脚底在 (x, y)，高 h（像素），朝向 dir=±1；盾、矛、头盔 */
export function soldier(g, R, x, y, h, dir = 1, v = 0.85) {
  const u = h / 10, lean = (R() - .5) * u * .6;
  line(g, x - u * .7, y, x - u * .4 + lean, y - u * 4.6, u * 1.1, v * .92);           // 后腿
  line(g, x + u * .7 * dir, y, x + u * .3 + lean, y - u * 4.6, u * 1.1, v * .95);     // 前腿
  poly(g, [[x - u * 1.6 + lean, y - u * 4.2], [x + u * 1.6 + lean, y - u * 4.2], [x + u * 1.2 + lean, y - u * 7.6], [x - u * 1.2 + lean, y - u * 7.6]], v); // 身（短袍）
  ell(g, x + lean, y - u * 8.5, u * 0.95, u * 1.05, v);                                  // 头
  ell(g, x + lean, y - u * 8.9, u * 1.05, u * .6, Math.min(1, v + .08));                 // 盔
  if (R() < .75) ell(g, x + dir * u * 1.6 + lean, y - u * 5.6, u * 1.25, u * 2.3, Math.min(1, v + .12)); // 圆盾
  if (R() < .7) line(g, x - dir * u * 1.4 + lean, y - u * 1.2, x - dir * u * .8 + lean, y - u * 10.6, u * .32, v * .9); // 矛
}
/* 跪着的俘虏（披头、长袍、举手献礼） */
export function captive(g, R, x, y, h, dir = 1, v = 0.82) {
  const u = h / 10;
  poly(g, [[x - u * 2.4, y], [x + u * 2.2, y], [x + u * 1.2, y - u * 3.2], [x - u * 1.6, y - u * 3]], v * .95);   // 跪着的腿和袍摆
  poly(g, [[x - u * 1.3, y - u * 3], [x + u * 1.1, y - u * 3], [x + u * .9 * dir, y - u * 6], [x - u * .9, y - u * 6]], v); // 身
  ell(g, x + u * .5 * dir, y - u * 6.9, u * .9, u * 1, v);
  line(g, x + u * .4 * dir, y - u * 5.4, x + u * 2.4 * dir, y - u * 6.6, u * .7, v * .95);                     // 伸出的手
  if (R() < .5) ell(g, x + u * 2.8 * dir, y - u * 6.9, u * .8, u * .6, Math.min(1, v + .1));                     // 贡品
}
/* 有翼胜利女神（持花环） */
export function victory(g, R, x, y, h, dir = 1, v = 0.88) {
  const u = h / 10;
  poly(g, [[x - u * 1.8, y], [x + u * 1.8, y], [x + u * .9, y - u * 6.8], [x - u * .9, y - u * 6.8]], v);       // 长袍
  ell(g, x, y - u * 7.7, u * .85, u * .95, v);
  poly(g, [[x - dir * u * .5, y - u * 6.5], [x - dir * u * 4.2, y - u * 9.8], [x - dir * u * 3.4, y - u * 6.2], [x - dir * u * 2.2, y - u * 4.4]], v * .8); // 翅
  ell(g, x + dir * u * 2.4, y - u * 8.6, u * 1.3, u * 1.3, Math.min(1, v + .1));                                  // 花环外圈
  ell(g, x + dir * u * 2.4, y - u * 8.6, u * .7, u * .7, v * .5);                                                 // 花环内孔
}
/* 花环垂饰（swag）：x0→x1 之间挂几段弧 */
export function garland(g, R, x0, x1, y, depth, n, v = 0.8) {
  const w = (x1 - x0) / n;
  for (let i = 0; i < n; i++) for (let k = 0; k <= 14; k++) {
    const t = k / 14, x = x0 + (i + t) * w, yy = y + Math.sin(t * Math.PI) * depth;
    ell(g, x, yy, w * .07 + depth * .14, w * .07 + depth * .12, v * (0.85 + 0.15 * R()));
  }
  for (let i = 0; i <= n; i++) ell(g, x0 + i * w, y, depth * .18, depth * .18, Math.min(1, v + .1)); // 结（rosette）
}
/* 线脚框：外框亮、内凹场暗 */
export function frame(g, x, y, w, h, b, vOuter = 0.95, vField = 0.12) {
  rect(g, x, y, w, h, vOuter);
  rect(g, x + b * .45, y + b * .45, w - b * .9, h - b * .9, vOuter * .78);
  rect(g, x + b, y + b, w - 2 * b, h - 2 * b, vField);
}
