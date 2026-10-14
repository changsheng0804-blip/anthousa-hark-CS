// /goal 4 项 3：面包台阶清晨排队只在有粮仓供着的时候。从 tiles/index.html 剪出 breadQueue，喂假画布/假镜头/net_water.json 的粮网，查：
//  ① 供粮年之前、台阶拆毁年之后：一个人也不画；② 供粮年起，只在清晨 5–8:30 画；中午、夜里不画；③ 镜头没对着台阶、没放大到街巷级：不画。——Hark（CS线）
const fs = require('fs'), path = require('path'), AH = process.env.AH || '/workspace/work/ah';
const html = fs.readFileSync(path.join(AH, 'docs/living/tiles/index.html'), 'utf8');
const a = html.indexOf('function breadQueue('), b = html.indexOf('function heartPer(');
if (a < 0 || b < 0) { console.log('❌ 页面里没有 breadQueue'); process.exit(1) }
const J = JSON.parse(fs.readFileSync(path.join(AH, 'docs/living/tiles/net_water.json'), 'utf8')), G = J.grain.nodes.filter(n => n.kind === 'steps');
let bad = []; const need = (c, m) => { if (!c) bad.push(m) };
function run(n, Y, hour, z = 3, far = false) {
  let arcs = 0; const ctx = new Proxy({}, { get: (t, k) => k === 'arc' ? () => { arcs++ } : () => { }, set: () => true });
  const env = new Function('ctx', 'cam', 'W', 'H', 'streetAlpha', 'netWater', 'NETGR', 'HCLK', 'YEAR', html.slice(a, b) + ';return breadQueue');
  const cam = { x: n.fx + (far ? 5000 : 0), y: n.fy, z };
  env(ctx, cam, 1000, 700, () => z > 1.2 ? 1 : 0, () => { }, G, { h: hour }, Y)(1000); return arcs;
}
let n0 = 0;
for (const n of G) {
  need(run(n, n.supply - 1, 6) === 0, `${n.id} 供粮年 ${n.supply} 之前有人排队`);
  need(run(n, n.supply, 6) > 0, `${n.id} 供粮年 ${n.supply} 清晨没人排队`);
  need(run(n, n.supply, 12) === 0 && run(n, n.supply, 23) === 0 && run(n, n.supply, 4.5) === 0 && run(n, n.supply, 9) === 0, `${n.id} 非清晨也在排队`);
  need(run(n, n.supply, 6, 0.5) === 0, `${n.id} 没放大到街巷级也画人`);
  need(run(n, n.supply, 6, 3, true) === 0, `${n.id} 镜头不在也画人`);
  if (n.end != null) need(run(n, n.end, 6) === 0, `${n.id} 拆毁年 ${n.end} 还在排队`);
  if (n.supply > n.built + 2) { n0++; need(run(n, n.built + 2, 6) === 0, `${n.id} 落成但粮仓未建就排队`) }
}
console.log(`台阶 ${G.length} 座，其中先光秃再排队 ${n0} 座`);
console.log(bad.join('\n') || '✅ 全过'); process.exit(bad.length ? 1 : 0);
