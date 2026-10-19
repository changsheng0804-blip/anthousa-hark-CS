/* 姿势引擎（2026-10-19，借鉴 oyasumi Name Gacha 的做法，只学方法，代码自写）。
   1) 统一姿势通道：任何动作都只输出同一组数 → 渲染器只认这一组。
      stoop 前倾 / side 侧弯 / twist 扭身 / hip 胯摆 / bob 起伏 / lift 升降 / neck 低头 / headYaw 转头 /
      legs[左,右]=[大腿, 膝] / arms[左,右]=[前举, 屈肘, 外展]
   2) 意图 → 参数分布：底账推出的意图（老、孩子、富、搬运、挑水……）给的是一个范围，不是一个值；
      每个人用自己的种子在范围里抽，同一个人永远一样，满城不重样。
   3) 抽 4 个候选，按「像不像真人」打分（步频、步长/身高、负重时的重心）留最好的；
      同一条路线上的人再挑跟前面的人最不像的那个。
   4) 叠加手势：在基础动作上加一层短动作（回头、擦汗、躬身让路），这一层负责「三秒读出他是谁」。
   ——Hark（CS线） */

// ---------- 种子 ----------
export function hash(s) { let h = 2166136261 >>> 0; s = String(s); for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) } return h >>> 0 }
export function rng(seed) { let a = seed >>> 0 || 1; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296 } }

// ---------- 意图 → 步态分布：[低, 高]。speed 米/秒，stride 每步米，stoop 前倾弧度，bob 起伏，swing 摆臂，limp 跛，out 两臂外张 ----------
export const GAITS = {
  old:         {speed: [.62, .8],  stride: [.42, .52], stoop: [.24, .38], bob: [.015, .03], swing: [.15, .32], limp: [.06, .26], out: [.02, .12]},
  old_load:    {speed: [.55, .7],  stride: [.38, .46], stoop: [.32, .44], bob: [.012, .025], swing: [.05, .15], limp: [.12, .3], out: [0, .08]},
  child:       {speed: [1.6, 2.1], stride: [.55, .7],  stoop: [.08, .16], bob: [.05, .08], swing: [.7, 1.0], limp: [0, 0], out: [.1, .3], skip: 1},
  child_walk:  {speed: [.8, 1.0],  stride: [.36, .44], stoop: [.02, .08], bob: [.025, .04], swing: [.35, .55], limp: [0, 0], out: [.05, .2]},
  rich:        {speed: [.85, 1.0], stride: [.58, .68], stoop: [-.09, -.03], bob: [.008, .015], swing: [.1, .22], limp: [0, 0], out: [.1, .22], center: 1},
  servant:     {speed: [.9, 1.0],  stride: [.5, .58],  stoop: [.1, .18], bob: [.02, .035], swing: [0, .05], limp: [0, 0], out: [0, .05]},
  woman:       {speed: [1.05, 1.25], stride: [.5, .6], stoop: [.0, .07], bob: [.02, .035], swing: [.35, .55], limp: [0, 0], out: [0, .1]},
  woman_full:  {speed: [.7, .85], stride: [.42, .5],  stoop: [-.05, -.01], bob: [.005, .01], swing: [.12, .25], limp: [0, 0], out: [0, .06]},
  porter_load: {speed: [.82, .98], stride: [.5, .6],  stoop: [.48, .62], bob: [.015, .025], swing: [0, .04], limp: [0, .05], out: [0, .05]},
  porter:      {speed: [1.3, 1.55], stride: [.68, .8], stoop: [.06, .14], bob: [.035, .055], swing: [.5, .7], limp: [0, 0], out: [.08, .2]},
  tired:       {speed: [.9, 1.1], stride: [.54, .62], stoop: [.18, .28], bob: [.025, .035], swing: [.2, .35], limp: [0, .06], out: [0, .1]},
  walker:      {speed: [1.1, 1.4], stride: [.6, .74], stoop: [.03, .12], bob: [.025, .045], swing: [.35, .6], limp: [0, .04], out: [0, .12]},
  trader:      {speed: [1.15, 1.45], stride: [.6, .72], stoop: [.04, .12], bob: [.025, .04], swing: [.3, .5], limp: [0, 0], out: [.05, .15]},
  trader_load: {speed: [.95, 1.15], stride: [.54, .62], stoop: [.12, .2], bob: [.02, .03], swing: [0, .05], limp: [0, 0], out: [0, .05]},
};
const KEYS = ['speed', 'stride', 'stoop', 'bob', 'swing', 'limp', 'out'];

// 打分：像不像真人。步频 = 速度 / 步长（步/秒）；步长不能超过身高的 0.47；扛重的人重心要压低（前倾够）
function score(g, name, body) {
  let s = 100;
  const cad = g.speed / g.stride, lo = name.startsWith('child') ? 1.8 : 1.25, hi = name.startsWith('child') ? 3.2 : 2.3;
  if (cad < lo) s -= 120 * (lo - cad); if (cad > hi) s -= 120 * (cad - hi);
  const r = g.stride / body.h; if (r > .47) s -= 400 * (r - .47);
  if (name.endsWith('_load') && g.stoop < .3 && name.startsWith('porter')) s -= 60;
  if (g.limp > .15 && g.speed > .9) s -= 40;          // 跛得厉害的人走不快
  return s;
}
// 一个人的「脾性」：每个参数一个 0–1 的位置，所有步态共用——快性子的人扛着货也比别人快一点
export function temper(seed, n = 4) {
  const R = rng(seed), out = [];
  for (let c = 0; c < n; c++) { const u = {}; for (const k of KEYS) u[k] = R(); out.push(u) }
  return out;
}
const lerp = (a, b, u) => a + (b - a) * u;
export function gaitOf(name, u) { const G = GAITS[name] || GAITS.walker, g = {}; for (const k of KEYS) g[k] = lerp(G[k][0], G[k][1], u[k]); g.skip = G.skip || 0; g.center = G.center || 0; return g }
const dist = (a, b) => { let s = 0; for (const k of KEYS) s += (a[k] - b[k]) ** 2; return Math.sqrt(s) };
// 抽人：4 个候选里留分高的；分差不大时，挑跟「邻居们」（同一条路上的人）最不像的
export function pickTemper(seed, names, body, neighbours = []) {
  const C = temper(seed);
  let best = null, bs = -1e9;
  for (const u of C) {
    let s = 0; for (const n of names) s += score(gaitOf(n, u), n, body); s /= names.length;
    if (neighbours.length) s += 6 * Math.min(...neighbours.map(v => dist(u, v)));
    if (s > bs) { bs = s; best = u }
  }
  return best;
}

// ---------- 基础动作：走 ----------
export function blank() { return {stoop: 0, side: 0, twist: 0, hip: 0, bob: 0, lift: 0, neck: 0, headYaw: 0, legs: [[0, 0], [0, 0]], arms: [[0, 0, 0], [0, 0, 0]]} }
export function walk(P, g, ph) {
  const w = ph + g.limp * Math.sin(ph) * .6, s = Math.sin(w);
  const amp = Math.min(.75, g.stride * 1.05);
  P.legs[0][0] = amp * s; P.legs[0][1] = Math.max(0, -Math.cos(w)) * amp * 1.3 + .05;
  P.legs[1][0] = -amp * s; P.legs[1][1] = Math.max(0, Math.cos(w)) * amp * 1.3 + .05;
  P.bob = g.bob * Math.abs(Math.sin(w)) * (g.skip ? 2.2 : 1); P.stoop = g.stoop; P.neck = -g.stoop * .6;
  P.hip = .04 * s * (1 + g.limp * 3); P.twist = -.08 * s * g.swing;          // 胯和肩反着拧，跛的人胯摆得大
  P.arms[0][0] = -g.swing * s; P.arms[0][1] = .25; P.arms[0][2] = g.out;
  P.arms[1][0] = g.swing * s; P.arms[1][1] = .25; P.arms[1][2] = g.out;
  if (g.skip) P.lift = Math.max(0, Math.sin(w * 2)) * .06;
  return P;
}
// ---------- 基础动作：停下来干活 ----------
export function stay(P, ps, tt, k) {
  if (ps === 'sit' || ps === 'rest') { P.lift = -.42 * k; P.legs = [[1.45, 1.5], [1.35, 1.5]]; P.stoop = ps === 'rest' ? .3 : .22; P.arms = [[.5, 1.0, 0], [.5, 1.0, 0]]; P.neck = Math.sin(tt * .3) * .15 }
  else if (ps === 'mend') { P.lift = -.5 * k; P.legs = [[1.5, 1.7], [1.4, 1.6]]; P.stoop = .55; P.neck = .3; const h = Math.sin(tt * 2.6); P.arms = [[.9 + .15 * h, 1.2, 0], [.9 - .15 * h, 1.3, 0]] }
  else if (ps === 'sell' || ps === 'talk') { const g = Math.max(0, Math.sin(tt * (ps === 'talk' ? .9 : .5))); P.stoop = -.05; P.arms = [[.2 + 1.1 * g, .8 * g, 0], [.15, .3, 0]]; P.neck = Math.sin(tt * .4) * .2; P.headYaw = Math.sin(tt * .21) * .5 }
  else if (ps === 'queue') { P.hip = Math.sin(tt * .5) * .04; P.neck = Math.sin(tt * .23) > .6 ? .6 : 0; P.arms = [[.1, .3, 0], [.05, .2, 0]]; P.headYaw = Math.sin(tt * .13) * .6 }
  else if (ps === 'spin') { const h = Math.sin(tt * 3); P.arms = [[.6, 1.2 + .2 * h, 0], [.9 + .1 * h, 1.4, 0]]; P.neck = .25 }
  else if (ps === 'wait') { P.neck = -.1; P.lift = Math.max(0, Math.sin(tt * 4)) * .05; P.arms = [[0, .2, 0], [0, .2, 0]]; P.headYaw = Math.sin(tt * .7) * .8 }
  else if (ps === 'play') { const h = tt * 6; P.legs = [[.6 * Math.sin(h), .6 + .4 * Math.sin(h)], [-.6 * Math.sin(h), .6 - .4 * Math.sin(h)]]; P.lift = Math.abs(Math.sin(h)) * .1; P.arms = [[.8 * Math.sin(h), .4, .4], [-.8 * Math.sin(h), .4, .4]] }
  else { P.hip = Math.sin(tt * .4) * .03; P.neck = Math.sin(tt * .17) * .25; P.headYaw = Math.sin(tt * .11) * .5; P.arms = [[.05, .15, 0], [.05, .15, 0]] }
  return P;
}
// ---------- 负重改姿势 ----------
export function carry(P, load) {
  if (load === 'crate' || load === 'basket') { P.arms = [[1.2, 1.1, -.3], [1.2, 1.1, .3]]; P.stoop -= .05 }
  else if (load === 'jar_full') { P.arms[1] = [Math.PI - .25, .2, .25]; P.stoop = Math.min(P.stoop, -.02); P.neck = 0; P.headYaw *= .2 }   // 顶罐的人脖子不敢动
  else if (load === 'jar_empty') P.arms[1] = [.1, 1.1, .5];
  else if (load === 'sack') { P.arms = [[-2.6, 1.6, 0], [-2.6, 1.6, 0]]; P.neck = Math.min(P.neck, -.05) }
  else if (load === 'net') P.arms[1] = [-2.4, 1.9, 0];
  else if (load === 'catch') P.arms[0] = [.05, .1, -.15];
  return P;
}
// ---------- 叠加手势：e 是 0→1→0 的包络 ----------
export const OVER = {
  lookback: (P, e) => { P.headYaw += 1.7 * e; P.twist += .35 * e; P.neck -= .1 * e },                       // 回头看身后跟着的孩子
  wipe:     (P, e) => { P.arms[1] = mix(P.arms[1], [2.6, 2.4, .25], e); P.neck -= .25 * e; P.stoop -= .1 * e },   // 卸完货抬手擦汗
  bow:      (P, e) => { P.stoop += .5 * e; P.neck += .4 * e; P.arms[0] = mix(P.arms[0], [.15, .3, -.05], e); P.arms[1] = mix(P.arms[1], [.6, 1.4, -.2], e) },  // 躬身让路
  reach:    (P, e) => { P.arms[1] = mix(P.arms[1], [1.3, .2, -.2], e); P.headYaw += .4 * e },             // 孩子伸手去够大人
  shift:    (P, e) => { P.side += .12 * e; P.hip -= .08 * e; P.arms[0] = mix(P.arms[0], [.4, 1.6, .5], e) },  // 顶罐的人一手叉腰歇口气
};
const mix = (a, b, e) => a.map((v, i) => v + (b[i] - v) * e);
export const env = (t, t0, d) => { const u = (t - t0) / d; return u <= 0 || u >= 1 ? 0 : Math.sin(Math.PI * u) ** 2 };
