// /goal 4 项 7（G6）：敲门卡的户籍一行（刘线 reg 旁车，懒取）。从 tiles/index.html 剪出 REG 段，用磁盘上的真旁车喂它，查：
// ① 页面载入时一个 reg/ 请求都不发（不预载）；点开卡才取，且一次只取这块这一年的一个文件；
// ② 有旁车的房子 → 卡里多一行「门牌 · 区·坊 · 教区」，全是中文，没有 d_/church_ 代号；只一行；
// ③ 没有旁车的房子（地标 id ≥ 900001、旁车里没有这户、那一年不在世）→ 不加这一行；
// ④ 同一块同一年只取一次（缓存）；卡换房子后旧请求回来不乱插。
const fs = require('fs'), path = require('path'); const AH = process.env.AH || '/workspace/work/ah';
const T = path.join(AH, 'docs/living/tiles'); const html = fs.readFileSync(path.join(T, 'index.html'), 'utf8');
const a = html.indexOf('/* /goal 4 项 7（G6）'), b = html.indexOf('function heartTap(');
if (a < 0 || b < 0 || b < a) { console.log('❌ 页面里没有 REG 段'); process.exit(1) }
const code = html.slice(a, b); let bad = []; const need = (c, m) => { if (!c) bad.push(m) };
need(!/reg\//.test(html.slice(0, a)) && !/reg\//.test(html.slice(b)), '页面别处出现了 reg/ 请求（只许在敲门卡的 REG 段里取）');
const M = JSON.parse(fs.readFileSync(path.join(T, 'meta.json'), 'utf8')); const TP = M.tile_px;
const reqs = []; const fakeFetch = u => { reqs.push(u); const f = path.join(T, u); return Promise.resolve(fs.existsSync(f) ? { ok: true, json: () => Promise.resolve(JSON.parse(fs.readFileSync(f, 'utf8'))) } : { ok: false }) };
function mk() { const cardBody = { innerHTML: '', insertAdjacentHTML(w, h) { this.innerHTML += h } }; const st = { CARDQ: 'nangang' };
  const env = new Function('fetch', 'M', 'cardBody', 'st', 'var CARDQ=st.CARDQ;var YEAR=50;' + code + ';return {regFill,get q(){return CARDQ},set q(v){CARDQ=v}}')(fakeFetch, M, cardBody, st); return { env, cardBody } }
// 挑几栋真房子：vec 里带底账 id、50 年站着的
const picks = []; for (const f of fs.readdirSync(path.join(T, 'vec')).filter(n => n.endsWith('.json')).slice(10, 130)) { const d = JSON.parse(fs.readFileSync(path.join(T, 'vec', f), 'utf8')); const [tx, ty] = f.slice(0, -5).split('_').map(Number);
  for (const h of d.h) { if (/^h\d+$/.test(h[5] || '') && h[0] <= 50 && h[1] > 50 && h[3] && picks.length < 60 && picks.filter(q => q.tx === tx && q.ty === ty).length < 3) { const xs = h[3].filter((_, i) => i % 2 == 0).slice(0, 4), ys = h[3].filter((_, i) => i % 2 == 1).slice(0, 4), cx = xs.reduce((s, v) => s + v, 0) / 4, cy = ys.reduce((s, v) => s + v, 0) / 4; picks.push({ id: +h[5].slice(1), cx, cy, tx: Math.floor(cx / TP), ty: Math.floor(cy / TP) }) } } }
need(picks.length >= 20, '没挑到足够的房子');
(async () => {
  const { env, cardBody } = mk(); need(reqs.length === 0, '载入时就取了 reg'); let shown = 0, miss = 0;
  const run = async (p, Y) => { cardBody.innerHTML = '<div>卡</div>'; await env.regFill({ q: 'nangang', ox: 0, oy: 0, yo: Y, m: { sel: { kind: 'house', hh: { h: { id: p.id, cx: p.cx, cy: p.cy } } } } }); return cardBody.innerHTML };
  const before = reqs.length;
  for (const p of picks) { const s = await run(p, 50); const n = (s.match(/obj reg/g) || []).length; need(n <= 1, p.id + ' 不止一行'); const has = [50, 40, 60].some(y => { try { return JSON.parse(fs.readFileSync(path.join(T, 'reg', String(y), p.tx + '_' + p.ty + '.json'), 'utf8')).h.some(r => r && r.length > 1 && r[0] === 'h' + p.id) } catch (e) { return false } }); need(has === (n === 1), p.id + (has ? ' 旁车里有这户却没出行' : ' 旁车里没有这户却出了行')); if (n === 1) { shown++; need(/门牌 *\d+/.test(s) && !/d_|church_|arian_/.test(s), p.id + ' 行里有代号或没门牌：' + s); need(/区/.test(s) && /教/.test(s) || /会堂/.test(s), p.id + ' 行里没有区或教区：' + s) } else miss++ }
  need(shown >= picks.length * .5, '有旁车的房子大多没出一行：' + shown + '/' + picks.length);
  const tiles = new Set(picks.map(p => p.tx + '_' + p.ty)); need(reqs.length - before <= tiles.size * 3, '一块不止取一次：' + (reqs.length - before) + ' 次，' + tiles.size + ' 块');
  need(reqs.every(u => /^reg\/(40|50|60)\/-?\d+_-?\d+\.json$/.test(u)), '请求路径不对：' + reqs.find(u => !/^reg\/(40|50|60)\//.test(u)));
  // 年份取最近一档
  const r2 = reqs.length; await run(picks[0], 41); need(reqs.slice(r2).every(u => u.startsWith('reg/40/')) || reqs.length === r2, '41 年该取 40 档');
  // ③ 没有旁车
  need((await run({ id: 900123, cx: picks[0].cx, cy: picks[0].cy }, 50)).indexOf('obj reg') < 0, '新立地标（id≥900001）不该有户籍行');
  need((await run({ id: 99999999, cx: picks[0].cx, cy: picks[0].cy }, 50)).indexOf('obj reg') < 0, '旁车里没有的 id 不该有户籍行');
  need((await run({ id: picks[0].id, cx: 99999999, cy: 99999999 }, 50)).indexOf('obj reg') < 0, '没有旁车文件的位置不该有户籍行');
  // 非房子（人）不加
  cardBody.innerHTML = '<div>卡</div>'; await env.regFill({ q: 'nangang', ox: 0, oy: 0, yo: 50, m: { sel: { kind: 'person', hid: picks[0].id } } }); need(cardBody.innerHTML.indexOf('obj reg') < 0, '点人时不该加户籍行');
  // ④ 卡已换掉：旧请求回来不插
  const { env: e2, cardBody: cb2 } = mk(); cb2.innerHTML = '<div>卡</div>'; const pr = e2.regFill({ q: 'nangang', ox: 0, oy: 0, yo: 60, m: { sel: { kind: 'house', hh: { h: { id: picks[1].id, cx: picks[1].cx, cy: picks[1].cy } } } } }); e2.q = null; await pr; need(cb2.innerHTML.indexOf('obj reg') < 0, '卡关了旧请求还插了行');
  console.log(`户籍一行：${picks.length} 栋里 ${shown} 栋有行、${miss} 栋无；取 reg ${reqs.length} 次（${tiles.size} 块）`);
  console.log(bad.join('\n') || '✅ 全过'); process.exit(bad.length ? 1 : 0)
})();
