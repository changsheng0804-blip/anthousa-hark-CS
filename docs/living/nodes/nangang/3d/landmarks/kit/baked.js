/* landmarks 部件 · 读离线烘焙的网格（SDF 雕塑 → marching cubes，tools/cs/landmarks/bake_*.py 写的 .bin）。——Hark（CS线）2026-10-20
   格式：uint32 nv, uint32 nt, float32 bmin[3], bmax[3]；uint16 位置 nv*3（按包围盒量化）；int8 法线 nv*3（补齐到 4 字节）；索引 nt*3（nv<65536 用 uint16，否则 uint32）。
   loadBaked(url) 在模块顶层 await（core 载入模块时就等它，build 里不再等），geoOf(T, buf, scale) 每次给一个新的 BufferGeometry。 */
export async function loadBaked(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error('baked mesh ' + url + ' ' + r.status);
  return r.arrayBuffer();
}
export function geoOf(T, buf, scale = 1) {
  const dv = new DataView(buf), nv = dv.getUint32(0, true), nt = dv.getUint32(4, true);
  const bmin = [0, 1, 2].map(i => dv.getFloat32(8 + i * 4, true)), bmax = [0, 1, 2].map(i => dv.getFloat32(20 + i * 4, true));
  let o = 32;
  const q = new Uint16Array(buf, o, nv * 3); o += nv * 6;
  const n8 = new Int8Array(buf, o, nv * 3); o += nv * 3; o += (4 - o % 4) % 4;
  const idx = nv < 65536 ? new Uint16Array(buf, o, nt * 3) : new Uint32Array(buf, o, nt * 3);
  const P = new Float32Array(nv * 3), N = new Float32Array(nv * 3);
  for (let i = 0; i < nv * 3; i++) { const k = i % 3; P[i] = (bmin[k] + q[i] / 65535 * (bmax[k] - bmin[k])) * scale; N[i] = n8[i] / 127; }
  const g = new T.BufferGeometry();
  g.setAttribute('position', new T.BufferAttribute(P, 3));
  g.setAttribute('normal', new T.BufferAttribute(N, 3));
  g.setIndex(new T.BufferAttribute(nv < 65536 ? new Uint16Array(idx) : new Uint32Array(idx), 1));
  return g;
}
