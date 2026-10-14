// /goal 4 项 2：敲门卡水源一句。从 tiles/index.html 剪出 waterLine，喂假的房子/年份/net_water.json，查：
// 离泉近且已出水 → 一句「水从X来」；泉池已建未出水 → 一句「水还没来」；泉还没建 / 太远 / 无中文名 → 空串；只一句（一个 div）。
const fs = require('fs'), path = require('path'); const AH = process.env.AH || '/workspace/work/ah';
const html = fs.readFileSync(path.join(AH, 'docs/living/tiles/index.html'), 'utf8');
const a = html.indexOf('var NETW=null'), b = html.indexOf('function heartTap(');
if (a < 0 || b < 0) { console.log('❌ 页面里没有 waterLine'); process.exit(1) }
const N = JSON.parse(fs.readFileSync(path.join(AH, 'docs/living/tiles/net_water.json'), 'utf8')).nodes;
const code = 'var fetch=()=>new Promise(()=>{});' + html.slice(a, b);
let bad = []; const need = (c, m) => { if (!c) bad.push(m) };
function run(n, Y, dx, dy) { const env = new Function('NODES', 'YEAR', code + ';NETW=NODES;return waterLine')(N, Y); return env({ m: { sel: { kind: 'house', hh: { h: { cx: n.px[0] + dx, cy: n.px[1] + dy } } } }, ox: 0, oy: 0, yo: Y }) }
let dry = 0, wet = 0;
for (const n of N.filter(n => n.kind === 'fountain')) {
  if (n.wet > n.built) { const s = run(n, n.wet - 1, 20, 0); need(/水还没来/.test(s), n.id + ' 干着的年份没说水没来：' + s); dry++ }
  const s2 = run(n, Math.max(n.wet, n.built), 20, 0); need(/水从.+来/.test(s2) || /水还没来/.test(s2), n.id + ' 出水年没有水源一句：' + s2); if (/水从/.test(s2)) wet++;
  need((s2.match(/<div/g) || []).length <= 1, n.id + ' 不止一句');
  need(run(n, n.built - 1, 20, 0) === '' || N.some(m => m.kind === 'fountain' && m.id !== n.id && m.built < n.built), n.id + ' 泉没建就有水源句');
  need(run(n, n.wet, 5000, 5000) === '', n.id + ' 太远还有水源句');
}
console.log('水源一句：干着 ' + dry + '、有水 ' + wet); console.log(bad.join('\n') || '✅ 全过'); process.exit(bad.length ? 1 : 0)
