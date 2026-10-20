/* crowd 的舞台转接（lookdev 第 2 轮，2026-10-20）：把长卷的人群引擎 docs/living/nodes/people/crowd.js（+ pose.js）原样接进 3D。
   引擎不改一个字（长卷也在用），这里只做转接：
   - 场景：引擎往 scene.add 的部件，改走 ctx.add（core 按模块数三角形）；每个部件投影。
   - 地面：引擎站人的高度 = elevPx + 1.5，这里把 elevPx 换成 ctx.ground − 1.5，人就踩在 3D 地形网格上（含港边软化）。
   - 尺度：3D 里房子不做竖向夸张，人也不夸张（EX=1），人眼高机位 1.7 m 才和人头一样高。
   - 时钟：引擎的一天长 T（people.json，2133 s）；still 模式 t 固定，这里把 3D 的 t 挂到「正午」段里的 930 s（930 + t），同机位同图。
     930 是在正午段里按机位 2 主街上的人数挑的（主街 400 m 内 72 人；T/2 = 1066 时 60 人），可用 ?crowdT= 改。
   - 档：近处关节人（同一套姿势引擎），远处着色小柱；视野外不算。帧图小人（长卷斜俯专用）不建。
   - 年份：人群是第 cd.year 年的户籍推出来的，别的年份不出人（不和底账打架）。
   - 指到才出签（主人定）：不指不算；指的时候只在这一帧视野里的人当中找最近的那个。
   ——Hark（CS线） */
import {initCrowd} from '../../../people/crowd.js';

export function stage(ctx, cd, pd) {
  const {THREE, camera} = ctx, MPP = cd.mpp, M = 1 / MPP;
  const QS = ctx.QS, preview = ctx.quality === 'preview', STILL = QS.has('still');
  const FULL_M = +(QS.get('crowdFull') || (preview ? 40 : 100));  // 关节人半径（米）：100 m 处一个人还有 ~9 像素高，关节人比柱子像人
  const MAXF = +(QS.get('crowdMaxFull') || (preview ? 60 : 200));  // 关节人上限
  const FAR_M = +(QS.get('crowdFar') || (preview ? 250 : 400));    // 远柱的最远距离（米）：再远一根柱子不到 3 像素，不算不画
  const CULL = new THREE.PerspectiveCamera();                      // 只给引擎做视锥裁剪的影子相机：同机位，远裁剪面收到 FAR_M
  const T = (pd && pd.T) || 2133, T0 = +(QS.get('crowdT') || 930);  // 人群时钟锚在 people.json 的「正午」段（853–1194 s）里：still 模式同图
  const N = Math.min(cd.people.length, +(QS.get('crowdN') || cd.people.length));
  const parts = [];
  const sceneProxy = {add: o => { o.castShadow = true; o.receiveShadow = false; parts.push(o); ctx.add(o); return o }};
  /* 街面抬高：streets 把车道铺高几厘米、主街人行道再高一道路缘（剖面见 3d/streets.js 的 PROF）。人脚要踩在铺面上，不然陷进人行道。
     每次重建按当年的街和 reg.frontage（streets 写）画一张 1 px 一格的「抬高图」，站人时查一格（读不到 frontage 就只有车道）。 */
  const LIFT = {m: [.11, .2], s: [.08, .13], c: [.06, 0], l: [.04, 0]}, LQ = 500;   // [车道抬高, 路缘再高]，页面像素
  let LR = null, LW = 0, LH = 0, liftMs = 0;
  function liftMap(ctx) {
    const W = Math.ceil(ctx.W), H = Math.ceil(ctx.H), cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    const X = cv.getContext('2d', {willReadFrequently: true}), t0 = performance.now(); X.fillStyle = '#000'; X.fillRect(0, 0, W, H); X.lineCap = 'round'; X.lineJoin = 'round';
    const g = v => { const q = Math.round(v * LQ); return `rgb(${q},${q},${q})` };
    const F = ctx.reg.frontage, S = F && F.sides || [];
    for (let i = 0; i + 1 < S.length; i++) { const a = S[i], b = S[i + 1];             // 主街人行道：同一条街、同一侧的相邻两个采样点连成一段
      if (a.k !== 'm' || b.chain !== a.chain || a.nx * b.nx + a.nz * b.nz < .7 || Math.hypot(a.x - b.x, a.z - b.z) > 12) continue;
      const o0 = a.kerb, w = Math.max(0, Math.min(a.edge, b.edge) - o0); if (w < .3) continue;
      const oa = o0 + w / 2; X.strokeStyle = g(LIFT.m[0] + LIFT.m[1]); X.lineWidth = w + .4;
      X.beginPath(); X.moveTo(a.x + a.nx * oa, a.z + a.nz * oa); X.lineTo(b.x + b.nx * oa, b.z + b.nz * oa); X.stroke() }
    for (const f of ctx.by.street || []) { if (!ctx.live(f)) continue; const L = LIFT[f.k] || LIFT.l, kb = f.k === 'm' ? 5.2 : f.k === 's' ? 3.62 : f.w / 2;
      X.strokeStyle = g(L[0]); X.lineWidth = 2 * kb; X.beginPath(); X.moveTo(f.g[0], f.g[1]); X.lineTo(f.g[2], f.g[3]); X.stroke() }
    const D = X.getImageData(0, 0, W, H).data; LR = new Uint8Array(W * H); for (let i = 0; i < W * H; i++) LR[i] = D[i * 4]; LW = W; LH = H; liftMs = Math.round(performance.now() - t0) }
  const liftAt = (x, z) => { if (!LR) return 0; const i = x | 0, j = z | 0; return i < 0 || j < 0 || i >= LW || j >= LH ? 0 : LR[j * LW + i] / LQ };
  const C = initCrowd({THREE, scene: sceneProxy, elevPx: (x, z) => ctx.ground(x, z) - 1.5 + .02 + liftAt(x, z), isLand: () => true,
    MPP, EX: 1, data: cd, n: N, T});
  let on = false, last = null;
  const triOf = m => { const g = m.geometry; return (g.index ? g.index.count : g.attributes.position.count) / 3 };

  function setOn(v) { on = v; for (const m of parts) m.visible = v; if (!v) for (const m of parts) m.count = 0 }
  function step(t) {
    camera.updateMatrixWorld(); camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    CULL.position.copy(camera.position); CULL.quaternion.copy(camera.quaternion); CULL.fov = camera.fov; CULL.aspect = camera.aspect;
    CULL.near = camera.near; CULL.far = Math.min(camera.far, FAR_M * M); CULL.updateProjectionMatrix(); CULL.updateMatrixWorld(); CULL.matrixWorldInverse.copy(CULL.matrixWorld).invert();
    const st = C.tick(T0 + t, {cam: CULL, full: true, fullM: FULL_M, maxFull: MAXF, sprite: false, farBoost: 1});
    let tris = 0, dc = 0; for (const m of parts) if (m.count) { tris += triOf(m) * m.count; dc++ }
    last = {active: st.active, full: st.full, far: st.far, ms: +st.ms.toFixed(2), greet: st.greet || 0, tris: Math.round(tris), drawCalls: dc, liftMs};
    window.__crowdStats = last; return last;
  }

  // ---- 指到才出签 ----
  let TIP = null, TIPO = null, MX = -1, MY = -1, PEND = false;
  const V = new THREE.Vector3(), headY = 1.55 * M;
  const scr = (x, y, z) => { V.set(x, y, z).project(camera); return [(V.x + 1) / 2 * innerWidth, (1 - V.y) / 2 * innerHeight, V.z] };
  const tipEl = () => { if (TIP) return TIP; TIP = document.createElement('div');
    TIP.style.cssText = 'position:fixed;pointer-events:none;background:rgba(250,244,230,.95);border:1px solid #b9a582;border-radius:9px;padding:4px 8px;font-size:13px;line-height:1.45;color:#3a2e22;transform:translate(-50%,-100%);white-space:nowrap;display:none;box-shadow:0 1px 4px rgba(0,0,0,.15);z-index:5';
    document.body.append(TIP); return TIP };
  function pick() { PEND = false; if (!on) return; let best = null, bd = 28 * 28;
    for (const o of C.pickable()) { const [sx, sy, sz] = scr(o.x, o.y + headY, o.z); if (sz > 1) continue; const d = (sx - MX) ** 2 + (sy - MY) ** 2; if (d < bd) { bd = d; best = o } }
    TIPO = best; if (!best && TIP) TIP.style.display = 'none' }
  function tipStep() { if (!TIPO) return; const o = TIPO, [px, py] = scr(o.x, o.y + headY, o.z);
    if (o.seen == null || Math.hypot(px - MX, py - MY) > 70) { TIPO = null; tipEl().style.display = 'none'; return }
    const d = C.describe(o), [sx, sy] = scr(o.x, o.y + 2.0 * M, o.z), el = tipEl();
    el.innerHTML = '<b>' + d.who + '</b><br>' + d.what + (d.from ? '<br><span style="color:#7a6a50;font-size:12px">' + d.from + '</span>' : '');
    el.style.left = sx + 'px'; el.style.top = (sy - 6) + 'px'; el.style.display = 'block' }
  if (!STILL) {
    const cv = ctx.renderer.domElement;
    cv.addEventListener('pointermove', e => { MX = e.clientX; MY = e.clientY; if (!PEND) { PEND = true; requestAnimationFrame(pick) } });
    cv.addEventListener('pointerleave', () => { TIPO = null; if (TIP) TIP.style.display = 'none' });
  }

  /* 测 CPU：连跑 n 帧 step（位置 + 姿势 + 实例矩阵 + 统计），给最小值 / p10 / 中位数。沙箱只有 2 核还常被别的渲染占着，最小值最接近不受干扰的真实开销 */
  window.__crowd = {C, get stats() { return last }, tipAt: (x, y) => { MX = x; MY = y; pick(); tipStep(); return TIPO && TIP ? TIP.innerText : null }, bench: n => { const a = []; for (let i = 0; i < n; i++) { const t0 = performance.now(); step(i * .25); a.push(performance.now() - t0) }
    a.sort((x, y) => x - y); const r = {min: a[0], p10: a[Math.floor(n * .1)], median: a[n >> 1], max: a[n - 1], stats: last}; step(0); return r }};
  return {
    build(ctx) { setOn(ctx.year === cd.year); if (on) { liftMap(ctx); step(0) } },   // 先摆一次，core 数得到三角形
    dispose() {},                                                 // 部件常驻（init 里建的），只按年份显隐
    /* still：同一刻摆两遍。引擎的「碰见熟人打招呼」读上一帧的近处名单，摆两遍后名单就是这一刻自己的，跟之前拍过哪个机位无关 → 同机位同图 */
    tick(ctx, t) { if (!on) return; if (STILL) step(t); step(t); tipStep() },
  };
}
