/* landmarks 部件 · 旋转体（lathe）和方形线脚（square lathe）。——Hark（CS线）2026-10-20
   纪功柱试点里写的，给以后的地标（凯旋门、方尖碑底座、穹顶鼓座、柱廊柱子）共用：
   - lathe(T, prof, segs, {v})        剖面 [[r,y],…]（自下而上）绕 y 轴转一圈；转角 > 35° 处自动断法线（线脚的棱是硬的）。
                                       UV：u = 绕一圈 0→1；v = opt.v(y)（默认 = y），柱身用它把螺旋浮雕贴图按「一圈一个高度」铺。
   - squareLathe(T, prof, {ax,az})    同一种剖面沿正方形走一圈（台阶、基座线脚、柱础方板），棱是硬的，UV = 世界尺寸。
   - merge(T, geos)                   几个几何并成一个（非索引；位置 + 法线 + uv），一个材质一个 draw call。
   - box(T, hx, hy, hz, x, y, z)      小方块（脚手架、垫石）。
   全部确定性：只用传入的数，不用随机。 */
export function lathe(T, prof, segs, opt = {}) {
  const vf = opt.v || (y => y), crease = Math.cos((opt.crease ?? 35) * Math.PI / 180);
  // 每个剖面点按左右两段的法线决定：平滑（取平均）还是断开（复制一个点）
  const segN = [];
  for (let i = 0; i < prof.length - 1; i++) {
    const [r0, y0] = prof[i], [r1, y1] = prof[i + 1], dr = r1 - r0, dy = y1 - y0, L = Math.hypot(dr, dy) || 1;
    segN.push([dy / L, -dr / L]); // 剖面向上走时，外法线 = (dy, -dr)
  }
  const pts = []; // [r, y, nr, ny]
  for (let i = 0; i < prof.length; i++) {
    const a = segN[i - 1], b = segN[i], [r, y] = prof[i];
    if (a && b && a[0] * b[0] + a[1] * b[1] < crease) { pts.push([r, y, ...a]); pts.push([r, y, ...b]); }
    else { const n = a && b ? [a[0] + b[0], a[1] + b[1]] : (a || b), L = Math.hypot(n[0], n[1]) || 1; pts.push([r, y, n[0] / L, n[1] / L]); }
  }
  const P = [], N = [], U = [], I = [], cols = segs + 1;
  for (const [r, y, nr, ny] of pts) for (let j = 0; j <= segs; j++) {
    const t = j / segs * Math.PI * 2, c = Math.cos(t), s = Math.sin(t);
    P.push(r * c, y, -r * s); N.push(nr * c, ny, -nr * s); U.push(j / segs, vf(y));
  }
  for (let i = 0; i < pts.length - 1; i++) {
    if (pts[i][0] === pts[i + 1][0] && pts[i][1] === pts[i + 1][1]) continue; // 断法线复制出来的同一个点
    for (let j = 0; j < segs; j++) {
      const a = i * cols + j, b = a + 1, c = a + cols, d = c + 1;
      I.push(a, b, d, a, d, c);
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(P, 3));
  g.setAttribute('normal', new T.Float32BufferAttribute(N, 3));
  g.setAttribute('uv', new T.Float32BufferAttribute(U, 2));
  g.setIndex(I);
  return g;
}

export function squareLathe(T, prof, opt = {}) {
  const ax = opt.ax ?? 1, az = opt.az ?? 0, uvs = opt.uv ?? 1;
  const C = (u, v) => [ax * u - az * v, az * u + ax * v];
  const P = [], U = [];
  const corner = h => [C(-h, -h), C(h, -h), C(h, h), C(-h, h)];
  for (let i = 0; i < prof.length - 1; i++) {
    const [h0, y0] = prof[i], [h1, y1] = prof[i + 1];
    if (h0 === h1 && y0 === y1) continue;
    const k0 = corner(h0), k1 = corner(h1);
    for (let s = 0; s < 4; s++) {
      const a0 = k0[s], b0 = k0[(s + 1) % 4], a1 = k1[s], b1 = k1[(s + 1) % 4];
      // 外侧面：从外面看逆时针 = a0 b1 b0 / a0 a1 b1
      const q = [[a0[0], y0, a0[1]], [b0[0], y0, b0[1]], [b1[0], y1, b1[1]], [a1[0], y1, a1[1]]];
      const uq = [[-h0 / uvs, y0 / uvs], [h0 / uvs, y0 / uvs], [h1 / uvs, y1 / uvs], [-h1 / uvs, y1 / uvs]];
      for (const k of [0, 2, 1, 0, 3, 2]) { P.push(...q[k]); U.push(...uq[k]); }
    }
  }
  // 顶面（最后一个点）：一个正方形
  if (opt.top !== false) {
    const [h, y] = prof[prof.length - 1], k = corner(h);
    const q = [[k[0][0], y, k[0][1]], [k[3][0], y, k[3][1]], [k[2][0], y, k[2][1]], [k[1][0], y, k[1][1]]];
    for (const i of [0, 1, 2, 0, 2, 3]) { P.push(...q[i]); U.push(q[i][0] / uvs, q[i][2] / uvs); }
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(P, 3));
  g.setAttribute('uv', new T.Float32BufferAttribute(U, 2));
  g.computeVertexNormals();
  return g;
}

export function merge(T, geos) {
  const P = [], N = [], U = [];
  for (const g0 of geos) {
    const g = g0.index ? g0.toNonIndexed() : g0;
    if (!g.attributes.normal) g.computeVertexNormals();
    P.push(...g.attributes.position.array); N.push(...g.attributes.normal.array);
    if (g.attributes.uv) U.push(...g.attributes.uv.array); else for (let i = 0; i < g.attributes.position.count; i++) U.push(0, 0);
    if (g !== g0) g.dispose();
    g0.dispose();
  }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(P, 3));
  g.setAttribute('normal', new T.Float32BufferAttribute(N, 3));
  g.setAttribute('uv', new T.Float32BufferAttribute(U, 2));
  return g;
}

export function box(T, hx, hy, hz, x, y, z, ry = 0) {
  const g = new T.BoxGeometry(hx * 2, hy * 2, hz * 2);
  if (ry) g.rotateY(ry);
  g.translate(x, y, z);
  return g;
}
