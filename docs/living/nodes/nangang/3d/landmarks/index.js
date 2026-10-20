/* landmarks（2026-10-20 新增的模块，owner = landmarks）：史诗级 / 特殊公共建筑，一座一个文件，按 Athenaion 的做法
   「参考图 → 剖面/部件/烘焙雕塑 → 固定机位对比」逐座做。buildings 里的方块占位由这里接手（接手一座，就从 buildings 删掉那一座的占位）。
   注册：core.js 的 MODULES 里在 buildings 后面多一项（唯一的钩子）。规矩见 docs/cs/lookdev/MODULE_CONTRACT.md 的 landmarks 一行。
   每座地标文件导出：id（nodes.json 地标 id）、init(ctx)、build(ctx, f, r, b) → Object3D|null（b = 地标底面高，和 buildings 同一个算法）、stats()。
   已做：column.js（狄奥多西广场纪功柱，id forum_theodosius）、nymphaeum.js（大宁芙殿，id nymphaeum_maius，2026-10-20）。
   tick：转给有 tick 的地标（宁芙殿的水在动）；完整几何缓存着的（名字以 -lod 结尾）dispose 时不释放。 */
import * as column from './column.js';
import * as nymphaeum from './nymphaeum.js';
export const name = 'landmarks';
export const checkShot = 5;
const LM = [column, nymphaeum];
const BY = Object.fromEntries(LM.map(m => [m.id, m]));
let LIVE = [];
export function init(ctx) { for (const m of LM) m.init(ctx); }
export function build(ctx) {
  const t0 = performance.now();
  for (const f of ctx.by.landmark || []) {
    const m = BY[f.id]; if (!m || !ctx.live(f)) continue;
    const r = ctx.geom.rectOf(f.g), b = ctx.elevPx(r.cx, r.cz) + 1.6;
    const o = m.build(ctx, f, r, b); if (o) LIVE.push(ctx.add(o));
  }
  window.__landmarkStats = { build_ms: Math.round(performance.now() - t0), ...Object.fromEntries(LM.map(m => [m.id, m.stats?.() || null])) };
}
export function dispose(ctx) {
  for (const o of LIVE) {
    ctx.scene.remove(o);
    if (o.name && o.name.endsWith('-lod')) continue;    // 完整的地标（纪功柱、宁芙殿）缓存着，不释放
    o.traverse(c => { if (c.isMesh) c.geometry.dispose(); });
  }
  LIVE = [];
}
export function tick(ctx, t) { for (const m of LM) if (m.tick) m.tick(ctx, t); }
