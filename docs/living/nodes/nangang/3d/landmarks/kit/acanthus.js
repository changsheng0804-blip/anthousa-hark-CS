/* landmarks 部件 · 科林斯柱头：钟形芯 + 两圈茛苕叶（程序化曲面叶片，锯齿叶缘、中脉、叶尖外卷）+ 四角涡卷 + 凹边方顶板 + 顶板花饰。——Hark（CS线）2026-10-20
   corinthian(T, {r, h, a, seed, rows, leaves, lod}) → BufferGeometry（原点 = 柱头底面中心，y 向上，单位随调用者）
     r = 柱颈半径，h = 柱头总高，a = 顶板半宽
   以后柱廊柱子、凯旋门壁柱、宁芙殿柱子都能用同一个：lod='far' 时只出钟形 + 顶板（几十个三角形）。
   确定性：叶片的微小变化用 seed 推。 */
import { lathe, merge } from './lathe.js';
import { rng } from './relief.js';

function leaf(T, R, { th, y0, len, rBase, out, w, curl, segS = 7, segT = 11 }) {
  // 叶片参数面：s 横向 0..1，t 纵向 0..1。中脉沿钟面向上，越往上越外翻，叶尖下卷。
  const P = [], U = [], I = [];
  const jit = 0.9 + 0.2 * R();
  for (let i = 0; i <= segT; i++) {
    const t = i / segT;
    // 中脉（径向 r、高 y）
    let r = rBase + out * Math.pow(t, 2.0) * jit, y = y0 + len * t;
    if (t > 0.72) { const k = (t - 0.72) / 0.28; r += curl * Math.sin(k * 1.4); y -= curl * 0.9 * k * k; }
    // 半宽：中段最宽，锯齿叶缘（5 个裂片）
    const hw = w * Math.pow(Math.sin(Math.PI * Math.min(t * 0.92 + 0.04, 0.999)), 0.7) * (0.82 + 0.18 * Math.cos(t * Math.PI * 10));
    for (let j = 0; j <= segS; j++) {
      const s = j / segS * 2 - 1;
      const cup = -0.28 * hw * (1 - s * s);              // 叶面内凹
      const rib = 0.1 * w * Math.exp(-((s / 0.16) ** 2)) * (1 - t); // 中脉鼓起
      const lobe = 0.06 * w * Math.cos(s * Math.PI * 2.5);  // 横向起伏
      const rr = r + cup + rib + lobe;
      const a = th + s * hw / Math.max(rr, 1e-3);
      P.push(rr * Math.cos(a), y, -rr * Math.sin(a)); U.push(j / segS, t);
    }
  }
  const C = segS + 1;
  for (let i = 0; i < segT; i++) for (let j = 0; j < segS; j++) { const a = i * C + j, b = a + 1, c = a + C, d = c + 1; I.push(a, b, d, a, d, c); }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.Float32BufferAttribute(P, 3)); g.setAttribute('uv', new T.Float32BufferAttribute(U, 2)); g.setIndex(I); g.computeVertexNormals();
  return g;
}

function volute(T, th, r0, y0, r1, y1, size) {
  // 从钟面伸向顶板角的卷须，末端卷成一个平面螺旋（在包含柱轴和该角的竖平面里）
  const pts = [], n = 26, c = Math.cos(th), s = -Math.sin(th);
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    let r, y;
    if (t < 0.5) { const k = t / 0.5; r = r0 + (r1 - r0) * k; y = y0 + (y1 - y0) * Math.sin(k * Math.PI / 2); }
    else { const k = (t - 0.5) / 0.5, ang = k * Math.PI * 2.2, rad = size * (1 - 0.75 * k); r = r1 + Math.sin(ang) * rad; y = y1 - size + Math.cos(ang) * rad; }
    pts.push(new T.Vector3(r * c, y, r * s));
  }
  const curve = new T.CatmullRomCurve3(pts);
  return new T.TubeGeometry(curve, 30, size * 0.28, 5, false);
}

export function corinthian(T, o) {
  const { r, h, a } = o, R = rng(o.seed ?? 7), far = o.lod === 'far';
  const segs = far ? 10 : 40;
  // 钟形芯（kalathos）+ 柱颈环；顶板单独做
  const ab = h * 0.14, bellTop = h - ab;
  const bell = lathe(T, [[r * 0.98, 0], [r * 1.04, h * 0.03], [r * 1.04, h * 0.06], [r * 0.97, h * 0.08], [r * 1.0, bellTop * 0.5], [r * 1.22, bellTop * 0.92], [r * 1.3, bellTop]], segs);
  const parts = [bell];
  // 顶板：凹边方板（四边各向内凹一段弧，四角切掉一点）
  const sh = new T.Shape(), k = a * 0.18, cut = a * 0.12;
  const C = [[-a, -a], [a, -a], [a, a], [-a, a]]; // 逆时针
  const ST = [], EN = [], CT = [];
  for (let i = 0; i < 4; i++) {
    const p = C[i], q = C[(i + 1) % 4], L = Math.hypot(q[0] - p[0], q[1] - p[1]), dx = (q[0] - p[0]) / L, dy = (q[1] - p[1]) / L;
    ST.push([p[0] + dx * cut, p[1] + dy * cut]); EN.push([q[0] - dx * cut, q[1] - dy * cut]);
    CT.push([(p[0] + q[0]) / 2 - dy * k, (p[1] + q[1]) / 2 + dx * k]); // 向内凹
  }
  sh.moveTo(ST[0][0], ST[0][1]);
  for (let i = 0; i < 4; i++) { sh.quadraticCurveTo(CT[i][0], CT[i][1], EN[i][0], EN[i][1]); if (i < 3) sh.lineTo(ST[i + 1][0], ST[i + 1][1]); }
  sh.closePath();
  const abacus = new T.ExtrudeGeometry(sh, { depth: ab, bevelEnabled: !far, bevelThickness: ab * 0.12, bevelSize: ab * 0.12, bevelSegments: 1, curveSegments: far ? 2 : 6 });
  abacus.rotateX(-Math.PI / 2); abacus.translate(0, bellTop, 0);
  parts.push(abacus);
  if (!far) {
    const nLeaf = o.leaves ?? 8;
    // 下圈 8 片矮叶、上圈 8 片高叶（错开半格），叶尖外卷
    for (let i = 0; i < nLeaf; i++) parts.push(leaf(T, R, { th: i / nLeaf * Math.PI * 2, y0: h * 0.06, len: bellTop * 0.42, rBase: r * 1.0, out: r * 0.3, w: r * 0.42, curl: r * 0.16 }));
    for (let i = 0; i < nLeaf; i++) parts.push(leaf(T, R, { th: (i + 0.5) / nLeaf * Math.PI * 2, y0: h * 0.1, len: bellTop * 0.68, rBase: r * 1.04, out: r * 0.36, w: r * 0.46, curl: r * 0.2 }));
    // 四角涡卷（helix）：从上圈叶后面伸到顶板角下；四边中间各一对小卷
    for (let i = 0; i < 4; i++) {
      const th = Math.PI / 4 + i * Math.PI / 2;
      parts.push(volute(T, th, r * 1.1, bellTop * 0.6, a * 1.25, bellTop - h * 0.02, h * 0.11));
      parts.push(volute(T, th + Math.PI / 4 - 0.18, r * 1.1, bellTop * 0.62, r * 1.36, bellTop - h * 0.04, h * 0.06));
      parts.push(volute(T, th + Math.PI / 4 + 0.18, r * 1.1, bellTop * 0.62, r * 1.36, bellTop - h * 0.04, h * 0.06));
      // 顶板正中的花饰（fleuron）
      const fa = th + Math.PI / 4, fr = a - k * 0.6;
      const fl = new T.SphereGeometry(h * 0.075, 8, 6); fl.scale(1, 1, 0.6); fl.rotateY(fa); fl.translate(fr * Math.cos(fa), bellTop + ab * 0.5, -fr * Math.sin(fa));
      parts.push(fl);
    }
  }
  return merge(T, parts);
}
