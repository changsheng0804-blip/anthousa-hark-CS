/* crowd（lookdev 第 2 轮）：把长卷已有的南港人群接进 3D。人是谁、住哪栋房子、去哪、跟谁，全来自 crowd.json
   （tools/cs/people/folk.py 从底账的房子推出户籍和关系、按街网推出路线）；本模块只演，不新写人。
   引擎复用 docs/living/nodes/people/crowd.js + pose.js（不改，长卷也在用），转接在 3d/crowd/stage.js。
   近处关节人、远处着色小柱，全部 InstancedMesh：不管多少人，绘制调用固定（约 30 次）。——Hark（CS线） */
import {stage} from './crowd/stage.js';
export const name = 'crowd';
export const checkShot = 2;

const QS = new URLSearchParams(location.search), ONLY = QS.get('only');
const WANT = !ONLY || ONLY.split(',').map(s => s.trim()).includes('crowd');
/* 数据在模块载入时取（core 的 init 是同步的）；不建 crowd 时不取，省 2 MB */
const [CD, PD] = WANT ? await Promise.all([
  fetch(new URL('../crowd.json', import.meta.url)).then(r => r.ok ? r.json() : null).catch(() => null),
  fetch(new URL('../people.json', import.meta.url)).then(r => r.ok ? r.json() : null).catch(() => null)]) : [null, null];

let S = null;
export function init(ctx) { if (CD) S = stage(ctx, CD, PD) }
export function build(ctx) { S?.build(ctx) }
export function dispose(ctx) { S?.dispose(ctx) }
export function tick(ctx, t) { S?.tick(ctx, t) }
