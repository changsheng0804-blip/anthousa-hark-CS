/* landmarks（2026-10-20 新增的模块，owner = landmarks）：史诗级 / 特殊公共建筑，一座一个文件，按 Athenaion 的做法
   「参考图 → 剖面/部件/烘焙雕塑 → 固定机位对比」逐座做。buildings 里的方块占位由这里接手（接手一座，就从 buildings 删掉那一座的占位）。
   注册：core.js 的 MODULES 里在 buildings 后面多一项（唯一的钩子）。规矩见 docs/cs/lookdev/MODULE_CONTRACT.md 的 landmarks 一行。
   每座地标文件导出：id（nodes.json 地标 id）、init(ctx)、build(ctx, f, r, b, F) → Object3D|null（b = 地标底面高 = 占地下最高地面，F = ctx.footing 结果 {min,max,mid}）；可选 footprint(r)、bottomOf(b,F)、stats()。
   已做：column.js（狄奥多西广场纪功柱，id forum_theodosius）、nymphaeum.js（大宁芙殿，id nymphaeum_maius，2026-10-20）、forum.js（狄奥多西广场本身：柱廊 + 凯旋门 + 门，同一个 id，2026-10-20）。
   一个 id 可以挂几个文件（按 LM 的顺序 build）；selfFoot = true 的文件自己分段落地、自己 ctx.foot，这里不替它按整块占地算 b；__landmarkStats 的键 = 文件的 key（没有就用 id）。
   tick：转给有 tick 的地标（宁芙殿的水在动）；完整几何缓存着的（名字以 -lod 结尾）dispose 时不释放。 */
import * as column from './column.js';
import * as nymphaeum from './nymphaeum.js';
import * as forum from './forum.js';
export const name = 'landmarks';
export const checkShot = 5;
const LM = [column, nymphaeum, forum];
const BY = {}; for (const m of LM) (BY[m.id] = BY[m.id] || []).push(m);
/* 这几座由本模块整座接手；全城页把它交给 buildings（ctx.landmarkIds），其余同类地标仍画 buildings 的通用占位 */
export const IDS = new Set(Object.keys(BY));
let LIVE = [];
export function init(ctx) { for (const m of LM) m.init(ctx); }
export function build(ctx) {
  const t0 = performance.now();
  for (const f of ctx.by.landmark || []) {
    if (!BY[f.id] || !ctx.live(f)) continue;
    for (const m of BY[f.id]) {
    if (m.selfFoot) { const o = m.build(ctx, f, ctx.geom.rectOf(f.g), null, null); if (o) LIVE.push(ctx.add(o)); continue; }
    /* 落地（r3_ground_scale）：b = 占地下最高的地面（terrain 网格，ctx.footing）；F.min 交给地标自己把台基 / 台阶伸下去（不漏空）。
       占地 = 地标文件的 footprint(r)（纪功柱：台阶外沿那个方块），没有就用底账矩形。改前是 elevPx(中心)+1.6。 */
    const r = ctx.geom.rectOf(f.g), P = m.footprint ? m.footprint(r) : ctx.geom.RQ(r, -r.hu, -r.hv, r.hu, r.hv), F = ctx.footing(P, 2), b = F.max + 0.05;
    const o = m.build(ctx, f, r, b, F); if (o) LIVE.push(ctx.add(o));
    ctx.foot({ kind: 'landmark:' + f.k, id: f.id, pts: P, bottom: m.bottomOf ? m.bottomOf(b, F) : b - 3, floor: b });
    }
  }
  window.__landmarkStats = { build_ms: Math.round(performance.now() - t0), ...Object.fromEntries(LM.map(m => [m.key || m.id, m.stats?.() || null])) };
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
