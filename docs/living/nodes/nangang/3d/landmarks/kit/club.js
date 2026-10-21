/* landmarks 部件 · 「赫拉克勒斯棍棒」柱 / 树干柱（狄奥多西凯旋门那种）。——Hark（CS线）2026-10-20
   史料：狄奥多西广场凯旋门的柱子雕成赫拉克勒斯的棍棒，柱头下有一只握着它的拳头（Naumann 1976 复原；Wikipedia「Forum of Theodosius」；
   unibo historica「columns decorated like Heracles' club with corinthian capitals and four of them have an hand under the capital」）；
   Byzantium 1200 说成「树干状的束柱」。同一种纹样在地下水宫（Basilica Cistern）的「孔雀眼 / 泪滴」柱上还在。
   clubColumn(T, {r, h, seed, far, fist, knobs}) → BufferGeometry（原点 = 柱础底面中心，y 向上，单位随调用者）
     r = 柱身中段半径，h = 柱础 + 柱身 + 柱头总高。棍棒形：下细上粗（0.86r → 1.08r，顶下再收一点），
     柱身上一圈圈斜着排的「砍掉的枝杈」短桩（knobs，每根 5 棱锥），fist = 柱头下一圈握拳（一道鼓出的箍 + 4 根指节）。
     柱头 = kit/acanthus.js 的科林斯（远档：钟形 + 顶板，几十个面）。泪滴 / 树皮纹交给调用者的法线贴图。
   确定性：枝杈的角度只用 seed。 */
import { lathe, merge } from './lathe.js';
import { corinthian } from './acanthus.js';
import { rng } from './relief.js';

export function clubColumn(T, o) {
  const { r, h } = o, far = !!o.far, R = rng(o.seed ?? 3), segs = far ? 8 : 14;
  const capH = r * 2.4, baseH = r * 0.9, sh = h - capH, shaftH = sh - baseH;
  const prof = [[r * 1.3, 0], [r * 1.3, baseH * .22], [r * 1.18, baseH * .3], [r * 1.24, baseH * .5], [r * 1.08, baseH * .64], [r * 1.0, baseH * .74], [r * 1.06, baseH * .88], [r * .9, baseH]];
  const N = far ? 4 : 10;
  for (let k = 0; k <= N; k++) {
    const t = k / N, y = baseH + shaftH * t;
    let rr = r * (0.86 + 0.24 * Math.pow(t, 1.2));            // 下细上粗
    if (t > 0.86) rr -= r * 0.3 * Math.pow((t - 0.86) / 0.14, 2); // 顶下收进柱颈
    if (!far && k > 0 && k < N) rr += r * 0.035 * Math.sin(k * 2.3 + R() * 2);   // 树干一样微微起伏
    prof.push([rr, y]);
  }
  const parts = [lathe(T, prof, segs, { v: y => y / (r * 4) })];
  if (o.fist !== false) {                                     // 握拳：柱头下 0.55r–1.25r 一道箍 + 4 根指节（四面）
    const y0 = sh - r * 1.35, y1 = sh - r * 0.45;
    parts.push(lathe(T, [[r * .82, y0], [r * 1.12, y0 + (y1 - y0) * .2], [r * 1.18, y0 + (y1 - y0) * .55], [r * 1.08, y1], [r * .8, y1 + r * .05]], segs));
    if (!far) for (let i = 0; i < 4; i++) {
      const a = i * Math.PI / 2 + Math.PI / 4;
      for (let j = 0; j < 4; j++) {                          // 一只拳头的四个指节：一排鼓包
        const g = new T.SphereGeometry(r * 0.17, 5, 4); g.scale(1, 1.25, .8);
        const aa = a + (j - 1.5) * 0.17, rr = r * 1.2;
        g.translate(rr * Math.cos(aa), y0 + (y1 - y0) * (0.35 + 0.08 * (j % 2)), -rr * Math.sin(aa));
        parts.push(g);
      }
    }
  }
  if (!far && o.knobs !== false) {                            // 砍掉的枝杈：5 圈、每圈 4 个，错开，朝外斜向上
    for (let ring = 0; ring < 5; ring++) for (let i = 0; i < 4; i++) {
      const t = 0.12 + ring * 0.16 + 0.03 * R(), a = (i + ring * 0.5) / 4 * Math.PI * 2 + 0.2 * R(), y = baseH + shaftH * t;
      const rr = r * (0.86 + 0.24 * Math.pow(t, 1.2));
      const g = new T.ConeGeometry(r * 0.16, r * 0.42, 5, 1, false); g.translate(0, r * 0.21, 0);
      g.rotateZ(-Math.PI * 0.28);                             // 往外斜上
      g.rotateY(a); g.translate(rr * 0.92 * Math.cos(a), y, -rr * 0.92 * Math.sin(a));
      parts.push(g);
    }
  }
  const cap = corinthian(T, { r: r * 0.8, h: capH, a: r * 1.4, seed: o.seed ?? 3, lod: 'far' });
  cap.translate(0, sh, 0);
  parts.push(cap);
  return merge(T, parts);
}
