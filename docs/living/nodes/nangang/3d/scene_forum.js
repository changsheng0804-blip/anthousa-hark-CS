/* 狄奥多西广场一景（第 65 年，一个下午）——2026-11-05，CS 线。页面 nodes/nangang/forum.html。
   学 https://distant-rapids-j68a.here.now/（Forum Romanum AD 210）的「主意」：一座广场、一个下午、约 300 个人、指着什么就说出它的名字和一小段话、
   有几扇门能进去。样子用的是南港 3D 渲染器本身（core.js + 全部模块，原样），不改机位 1–7 的任何输出。
   人：forum/cast.json（tools/cs/scene/forum_cast.py 从 folk.py 第 65 年户籍里挑的人），演员用长卷人群引擎 people/crowd.js 原样（不改），
   这里只把每个人「派」到广场上的一个去处：站摊的不走、逛摊子的在两个摊子之间来回、穿过广场的从一个口进另一个口出。
   指：桌面悬停 / 手机点一下；人按屏幕上离头最近（≤26 / 36 px）、建筑按看不见的代理盒子射线。门：4 间柱廊铺面 + 纪功柱基座的小门。
   规矩（主人）：深的藏在门后，一次只露一件，不列长单子。——Hark（CS线） */
import {ctx} from './core.js';
import {initCrowd} from '../../people/crowd.js';

const {THREE, camera: cam, controls: ctl, renderer: rnd} = ctx;
const $ = id => document.getElementById(id);
const QS = ctx.QS, STILL = QS.has('still');
const CAST = await fetch(new URL('../forum/cast.json', import.meta.url)).then(r => r.json());
const MPP = CAST.mpp, M = 1 / MPP;
const CX = 1436, CZ = 313;
const BY = new Map(CAST.people.map(p => [p[0], p]));
const H = CAST.houses, LAB = CAST.labels;

/* ---------- 地坪：柱廊、凯旋门、门楼的台面（forum.js 用 ctx.foot 登记的那几块），其余是地形网格 ---------- */
const FEET = (ctx.reg.footings || []).filter(f => /^landmark:forum/.test(f.kind));
const inQuad = (P, x, z) => { let s = 0; for (let i = 0; i < P.length; i++) { const a = P[i], b = P[(i + 1) % P.length], c = (b[0] - a[0]) * (z - a[1]) - (b[1] - a[1]) * (x - a[0]); if (c !== 0) { if (s && Math.sign(c) !== s) return false; s = Math.sign(c) } } return true };
function floorAt(x, z) { let y = ctx.groundMesh(x, z); for (const f of FEET) if (f.pts.length >= 3 && inQuad(f.pts, x, z)) y = Math.max(y, f.floor); return y }

/* ---------- 太阳的影子框收到广场（全城框 3600 px 一张图，人和柱子的影子是糊的） ---------- */
const sun = ctx.scene.children.find(o => o.isDirectionalLight && o.castShadow);
if (sun) { const d = sun.position.clone().sub(sun.target.position).normalize(); sun.target.position.set(CX, 0, CZ); sun.position.set(CX + d.x * 1200, d.y * 1200, CZ + d.z * 1200);
  Object.assign(sun.shadow.camera, {left: -260, right: 260, top: 200, bottom: -200, near: 200, far: 2600}); sun.shadow.camera.updateProjectionMatrix(); sun.target.updateMatrixWorld(); sun.shadow.normalBias = .25 }

/* ---------- 演员：路线 + 引擎 ---------- */
const routes = [], rows = [];
CAST.cast.forEach((c, i) => {
  let path = c.path;
  if (!path && c.kind === 'follow') path = [[CX, CZ], [CX, CZ + 1]];   // 跟着的人走领头人的路线（下面 q[1]），这条用不上
  else if (!path) { const f = c.face || [0, 1]; path = [[c.spot[0] + f[0] * .4, c.spot[1] + f[1] * .4], c.spot] }   // 站定的人：最后一段的反方向 = 面朝 face（引擎在终点 d + π）
  routes.push({h: c.id, why: 'errand', len_m: 0, path});
});
const RI = new Map(CAST.cast.map((c, i) => [c.id, i]));
CAST.people.forEach((p, i) => { const q = p.slice(); const c = CAST.cast[i]; q[1] = c.kind === 'follow' ? RI.get(c.lead) : i; q[10] = -1; rows.push(q) });
const parts = [];
const sceneProxy = {add: o => { o.castShadow = true; o.receiveShadow = false; parts.push(o); ctx.scene.add(o); o.userData.mod = 'forum_people'; return o }};
const C = initCrowd({THREE, scene: sceneProxy, elevPx: (x, z) => floorAt(x, z) - 1.5 + .02, isLand: () => true, MPP, EX: 1,
  data: {routes, people: rows, labels: LAB, houses: H.map(h => [...h.slice(0, 7), []]), htie: CAST.htie}, n: rows.length, T: 2133});
const POSE = {stall: 'sell', scribe: 'sit', petition: 'queue', notable: 'talk', idler: 'talk', kid: 'play'};
const U = s => { let h = 2166136261; for (const ch of String(s)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return (h >>> 0) / 4294967296 };
for (const o of C.people) {
  const c = CAST.cast[o.i]; o.dens = 0; o.meta = c;
  if (c.kind === 'follow') continue;
  if (!c.path) { o.tOut = o.tBack = 0; o.pauseFar = o.cyc = 1e6; o.pauseHome = 0; o.off = U(c.id) * 5000; o.farPose = c.pose || POSE[c.kind] || 'stand'; o.loadOut = o.loadBack = null; continue }
  const u = U(c.id);
  if (c.kind === 'porter') { o.loadOut = o.loadBack = 'sack'; o.pauseFar = 3; o.pauseHome = 4 }
  else if (c.kind === 'carrier') { o.loadOut = o.loadBack = 'jar_full'; o.pauseFar = 3; o.pauseHome = 4 }
  else if (c.kind === 'water') { o.loadOut = 'jar_empty'; o.loadBack = 'jar_full'; o.pauseFar = 6; o.pauseHome = 3 }
  else if (c.kind === 'shopper') { o.loadOut = null; o.loadBack = u < .4 ? 'basket' : null; o.pauseFar = 25 + u * 40; o.pauseHome = 0; o.farPose = 'stand' }
  else { o.loadOut = o.loadBack = u < .25 ? 'basket' : null; o.pauseFar = 2; o.pauseHome = 3 + u * 6 }
  o.cyc = o.tOut + o.pauseFar + o.tBack + o.pauseHome; o.off = u * o.cyc;
}
for (const o of C.people) if (o.lead) { for (const k of ['off', 'cyc', 'tOut', 'tBack', 'pauseFar', 'pauseHome', 'dens', 'so', 'sb']) o[k] = o.lead[k]; o.farPose = o.role === 'child' ? 'stand' : o.lead.farPose;
  if (o.meta.kind === 'follow' && o.lead.meta.kind === 'stall') o.farPose = 'stand' }

/* ---------- 摊子、桌子（实例化的小盒子：一种一次绘制） ---------- */
const GOODC = {银钱商: '#c8a860', 丝绸商: '#b03a6a', 香料商: '#d0802a', 金匠: '#e8c050', 卖油的: '#b8a84a', 卖果子的: '#7a4a6a', 小贩: '#b0a080', 卖鱼的: '#9ab0b0', 裁缝: '#8a9ac8', 鞋匠: '#8a5a3a', 织工: '#e0d0b0', 面包师: '#e0b070'};
const props = new THREE.Group(); props.userData.mod = 'forum_props';
{ const wood = new THREE.MeshLambertMaterial({color: '#a5825c', emissive: '#2a1e12'}), cloth = new THREE.MeshLambertMaterial({color: '#ffffff', emissive: '#1e1a14'});
  const tb = new THREE.BoxGeometry(1, 1, 1).translate(0, .5, 0);
  const T = [], G = [], m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  for (const s of CAST.stalls) { const x = s.x + s.fx * 1.15, z = s.z + s.fz * 1.15, y = floorAt(x, z), a = Math.atan2(s.fx, s.fz); T.push([x, y, z, a, 1.9 * M, .78 * M, .75 * M]); G.push([x, y + .78 * M, z, a, 1.6 * M, .16 * M, .55 * M, GOODC[s.trade] || '#8a7a6a']) }
  for (const d of CAST.desks) { const y = floorAt(d.x, d.z); T.push([d.x, y, d.z, Math.PI / 2, 1.0 * M, .7 * M, .6 * M]); T.push([d.x - 1.05, y, d.z, 0, .4 * M, .42 * M, .4 * M]); G.push([d.x, y + .7 * M, d.z, Math.PI / 2, .5 * M, .03 * M, .4 * M, '#e8dfc8']) }
  for (const o of C.people) if (o.meta.kind === 'idler' && o.meta.pose === 'sit') {}   // 坐在纪功柱最下一级台阶上，不加凳子
  const mk = (L, mat, col) => { const im = new THREE.InstancedMesh(tb, mat, L.length); L.forEach((r, i) => { e.set(0, r[3], 0); q.setFromEuler(e); m4.compose(new THREE.Vector3(r[0], r[1], r[2]), q, new THREE.Vector3(r[4], r[5], r[6])); im.setMatrixAt(i, m4); if (col) im.setColorAt(i, new THREE.Color(r[7])) });
    im.castShadow = im.receiveShadow = true; props.add(im) };
  mk(T, wood); mk(G, cloth, true); ctx.scene.add(props) }

/* ---------- 地方：名字 + 一小段有出处的话；代理盒子只给射线用，不进场景 ---------- */
const SRC = {
  phases: '底账：proposals/era_0051.json（forum_theodosius 的 phases）',
  chron: '编年史 chronicle/51_60.md、61_70.md',
  wiki: 'Wikipedia「Forum of Theodosius」',
  byz: 'The Byzantine Legacy「Arch of Theodosius」',
  naumann: 'Naumann 1976, Istanbuler Mitteilungen 26',
  mcid: 'Columbia「Istanbul Documentation Project」',
  lsa: 'Last Statues of Antiquity LSA-2458',
  socr: 'Socrates《教会史》4.8；Istanbul-su（Radboud 大学）',
  ours: '我们自己的复原假设，见 docs/cs/lookdev/landmarks/forum/notes.md',
};
const g0 = floorAt(CX, CZ);
const PLACES = [];
const place = (o) => { PLACES.push(o); return o };
const boxMesh = (x0, x1, y0, y1, z0, z1) => { const m = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0), new THREE.MeshBasicMaterial()); m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2); m.updateMatrixWorld(true); return m };
const PH = 22.5, AH = 63;   // 柱廊外墙压顶 ≈ 18.3 m、凯旋门含像 ≈ 53.3 m（页面像素 = 米 / 0.84）
place({key: 'column', name: '狄奥多西纪功柱', sub: '第 58–64 年起造 · 64 年立到顶', text: '白大理石柱身绕着一圈圈往上爬的浮雕，顶上是面朝西的皇帝像。底账记第 64 年「纪功柱立到顶，广场完工」；史料说它仿罗马的图拉真柱，柱身里有一道螺旋梯。', src: [SRC.phases, SRC.mcid, SRC.lsa], meshes: [boxMesh(CX - 6, CX + 6, g0, g0 + 90, CZ - 6, CZ + 6)], door: 'column'});
place({key: 'arch', name: '狄奥多西凯旋门', sub: '西口 · 第 60 年落成', text: '三个门洞跨在梅塞大道上，中门最宽。四个墩子各是一束四根的柱子，雕成赫拉克勒斯的棍棒，有的柱头下有一只握着的拳头；顶上站着狄奥多西和两个儿子的像。', src: [SRC.phases, SRC.wiki, SRC.byz, SRC.naumann], meshes: [boxMesh(1364, 1373, g0 - 2, g0 + AH, 287, 335)]});
place({key: 'egate', name: '东门楼', sub: '梅塞大道从这里出广场', text: '底账只写了西边的凯旋门，所以东口只做了一座柱廊门楼：两个方墩、一个拱、两面三角山花。史料说东西两头各有一座凯旋门，东边那座底账里没有，没画。', src: [SRC.phases, SRC.mcid, SRC.ours], meshes: [boxMesh(1495, 1508, g0 - 2, g0 + PH + 2, 289, 305)]});
for (const [k, z0, z1, nm] of [['nlane', 254, 268, '北拱门'], ['slane', 358, 372, '南拱门']])
  place({key: k, name: nm, sub: '圣科斯马斯大街穿过广场的地方', text: '广场 57 年划地时把一条南北向的小街吃掉了，小街两头还在，所以南北两翼的外墙在这里各开一个 3.2 米的拱门，柱廊不断。去大泉宫打水的人多半从这里过。', src: [SRC.phases, SRC.ours], meshes: [boxMesh(1440, 1448, g0 - 1, g0 + 9, z0, z1)]});
const WINGS = {
  N: {name: '北柱廊', box: [1365, 1507, 256, 267], who: '丝绸商'}, S: {name: '南柱廊', box: [1365, 1507, 359, 370], who: '银钱商'},
  W: {name: '西柱廊', box: [1365, 1376, 267, 359], who: '香料商'}, E: {name: '东柱廊', box: [1496, 1507, 267, 359], who: '金匠'}};
const STREET_OF = {S: '南边隔两条街是钱商街', W: '西边出去就是香料街', N: '', E: ''};
for (const [k, w] of Object.entries(WINGS)) {
  const [x0, x1, z0, z1] = w.box, n = CAST.stalls.filter(s => s.wing === k).length;
  place({key: 'wing' + k, name: w.name, sub: `两层柱廊 · 此刻 ${n} 个摊子`, text: `底账第 59 年「铺地，四面柱廊起墙」。下层科林斯柱，上层矮柱加栏板，外墙砖带石、里墙刷赭色灰泥。这个下午摆摊的多是${w.who}家的人${STREET_OF[k] ? '——' + STREET_OF[k] : ''}。`, src: [SRC.phases, SRC.ours, 'forum/cast.json'], meshes: [boxMesh(x0, x1, g0 - 2, g0 + PH, z0, z1)]});
}
place({key: 'mese', name: '梅塞大道', sub: '南港的主街 · 从凯旋门进、东门出', text: '城里最宽的一条街，宽 15 个格子。广场 57 年把它在框里的那一段吃掉了，人和货就从凯旋门进来、斜穿过石板地，从东门出去，往东通到大泉宫大道。', src: ['底账 nodes.json 街线（k=m）', 'signs.json 街名'], meshes: [boxMesh(1250, 1364, g0 - 6, g0 + .4, 304, 320), boxMesh(1508, 1620, g0 - 6, g0 + .4, 284, 300)], flat: true});
place({key: 'court', name: '狄奥多西广场', sub: '第 57 年划地 · 64 年完工 · 约 119 × 96 米', text: '狄奥多西在陶里广场、瓦伦斯大喷泉的旁边划出这块地，拆了 29 座房子。按底账是 119 × 96 米（史料的复原小得多，照底账）。新皇帝信尼西亚派，广场周围的人家一多半是阿里乌派。', src: [SRC.chron, 'world.json（forum_theodosius 的 history）', SRC.wiki], meshes: [boxMesh(1376, 1496, g0 - 8, g0 + .3, 267, 359)], flat: true});
place({key: 'nymph', name: '大宁芙殿（大泉宫）', sub: '广场东北 · 第 44 年', text: '瓦伦斯的水道在这里露面，全城看得见水是从哪里来的。史书说城守克利阿库斯在「现在叫狄奥多西广场的地方」修了一座最大的水殿；形制没有记载，眼前这座是我们按两层壁龛式假设的。', src: ['底账 proposals/era_0041.json', SRC.socr], meshes: [boxMesh(1538, 1620, g0 - 4, g0 + 40, 170, 228)]});
const PROXY = PLACES.flatMap(p => p.meshes.map(m => (m.userData.place = p, m)));

/* ---------- 门：4 间柱廊铺面（每翼挑一个摊子：那一开间就是铺子） + 纪功柱基座的小门 ---------- */
const DOORS = {};
for (const k of ['N', 'S', 'E', 'W']) {
  const L = CAST.stalls.filter(s => s.wing === k); if (!L.length) continue;
  const s = L[Math.floor(L.length / 2)], who = CAST.cast.filter(c => c.kind === 'stall' && (c.id === s.id || c.helper === s.id)).map(c => c.id);
  const shoppers = CAST.cast.filter(c => c.kind === 'shopper' && c.stall === s.id).map(c => c.id).slice(0, 1);
  const p = BY.get(s.id), h = H[p[12]];
  DOORS['shop' + k] = {key: 'shop' + k, stall: s, name: `${h[0] || p[5].split('，')[0]}家的${s.trade}铺面`, sub: `${WINGS[k].name}里的一个开间`,
    text: `门洞开在柱廊外墙上，一开间就是一间铺子。这家人住在广场${dirOf(h[5] - CX, h[6] - CZ)}约 ${Math.round(Math.hypot(h[5] - CX, h[6] - CZ) * MPP / 10) * 10} 米的房子里，是从${h[2] === '本城生' ? '本城' : h[2]}来的${h[3]}人家，${h[4]}。`,
    src: ['forum/cast.json（folk.py 第 65 年户籍）', '铺面租在柱廊里是我们的假设'], who: [...who, ...shoppers]};
  place({key: 'shop' + k, name: DOORS['shop' + k].name, sub: DOORS['shop' + k].sub + ' · 可以进去', text: DOORS['shop' + k].text, src: DOORS['shop' + k].src, door: 'shop' + k,
    meshes: [boxMesh(s.x - 2.2, s.x + 2.2, floorAt(s.x, s.z) - .5, floorAt(s.x, s.z) + 8, s.z - 2.2, s.z + 2.2)], pri: 1});
}
DOORS.column = {key: 'column', name: '纪功柱基座的小门', sub: '柱身里的螺旋梯', text: '史料说柱子是空心的，里面一道螺旋梯一直绕到柱头上（同罗马的图拉真柱）。底账里没有守柱子的人，此刻门里没有人。', src: [SRC.mcid], who: [], card: true};
function dirOf(dx, dz) { const D8 = ['东', '东南', '南', '西南', '西', '西北', '北', '东北']; return D8[Math.floor(((Math.atan2(dz, dx) * 180 / Math.PI + 382.5) % 360) / 45)] }

/* ---------- 人的签：谁 / 此刻 / 家 + 一件事 ---------- */
const KINDZ = {stall: '摆摊', scribe: '代写状子', petition: '等着写状子', notable: '在凯旋门下说事', idler: '在纪功柱下', porter: '脚夫', carrier: '运水', water: '去打水', shopper: '逛摊子', crosser: '穿过广场', follow: '跟着家里人', kid: '玩'};
function personText(o) {
  const c = o.meta, p = BY.get(c.id), h = H[p[12]], who = p[5];
  const fam = /^一家人是/.test(p[6]) ? `${h[0] ? h[0] + '家' : '这家'}是${h[1]}，${h[3]}。`   // 「家里的事」本身就是籍贯 + 来历时不重复
    : `${h[0] ? h[0] + '家' : '这家'}是${h[1]}，${h[2] === '本城生' ? '本城人' : '从' + h[2] + '来的'}，${h[3]}，${h[4]}。`;
  let now = c.now;
  if (c.path && o.seg) { if (c.kind === 'water') now = o.seg === 'back' ? '顶着满罐从大宁芙殿回来，穿过广场回家。' : now;
    else if (c.kind === 'shopper' && o.seg === 'far') now = `站在${BY.get(c.stall)[5].split('，')[0]}的摊子前看货。` }
  return {name: who.split('，')[0], sub: `${who.split('，').slice(1).join('，')} · ${p[4]} 岁`, now, text: fam + p[6] + '。', src: ['forum/cast.json ← folk.py 第 65 年户籍（名字、户主、行当、籍贯、信仰、来历、家里的事）；「此刻」按派的去处拼']};
}

/* ---------- 界面 ---------- */
const info = $('info'), card = $('card'), tag = $('ptag');
const HINT = matchMedia('(pointer:coarse)').matches ? '单指转、双指缩放；点一下人或建筑看名字' : '拖动转视角、滚轮缩放、右键平移；指着人或建筑看名字';
let pinned = null, hover = null, inside = null;
function showInfo(it) {
  if (!it) { info.innerHTML = `<i>${HINT}</i>`; info.classList.remove('on'); tag.style.display = 'none'; return }
  const d = it.o ? personText(it.o) : it.p;
  info.innerHTML = `<b>${d.name}</b><i>${d.sub}</i>${d.now ? `<span class="now">此刻：${d.now}</span>` : ''}<span>${d.text}</span><small>出处：${d.src.join('；')}</small>` + (it.p && it.p.door ? `<button id="enter" type="button">进去看看 →</button>` : '');
  info.classList.add('on');
  const b = $('enter'); if (b) b.onclick = e => { e.stopPropagation(); enter(it.p.door) };
}
const V = new THREE.Vector3(), RC = new THREE.Raycaster(), NDC = new THREE.Vector2();
const scr = (x, y, z) => { V.set(x, y, z).project(cam); return [(V.x + 1) / 2 * innerWidth, (1 - V.y) / 2 * innerHeight, V.z] };
function pickAt(mx, my, touch) {
  const lim = (touch ? 36 : 26) ** 2; let best = null, bd = lim;
  for (const o of C.pickable()) { const [sx, sy, sz] = scr(o.x, o.y + 1.2 * M * o.k, o.z); if (sz > 1) continue; const d = (sx - mx) ** 2 + (sy - my) ** 2; if (d < bd) { bd = d; best = o } }
  NDC.set(mx / innerWidth * 2 - 1, -(my / innerHeight) * 2 + 1); RC.setFromCamera(NDC, cam);
  const hits = RC.intersectObjects(PROXY, false);
  let ph = hits.length ? {p: hits[0].object.userData.place, d: hits[0].distance} : null;   // 最近的那个；铺面（pri）在它后面 20 以内也算铺面
  const sh = hits.find(h => h.object.userData.place.pri); if (ph && sh && sh.distance < ph.d + 20) ph = {p: sh.object.userData.place, d: sh.distance};
  /* 遮挡：只有实心的（柱子、凯旋门、东门楼、宁芙殿）挡人；柱廊、院子、街是「软」的，人站在里面照样指得到 */
  if (best) { const dd = cam.position.distanceTo(V.set(best.x, best.y, best.z)); if (!ph || !HARD.has(ph.p.key) || dd < ph.d + 3) return {o: best} }
  return ph ? {p: ph.p} : null;
}
const HARD = new Set(['column', 'arch', 'egate', 'nymph']);
const same = (a, b) => a && b && (a.o ? a.o === b.o : a.p === b.p);
let down = null;
const cv = rnd.domElement;
cv.addEventListener('pointerdown', e => { down = {x: e.clientX, y: e.clientY, t: performance.now()} });
cv.addEventListener('pointermove', e => { if (down || pinned || e.pointerType === 'touch') return; hover = pickAt(e.clientX, e.clientY, false); showInfo(hover) });
cv.addEventListener('pointerup', e => { if (!down) return; const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 8; down = null; if (moved) return;
  const it = pickAt(e.clientX, e.clientY, e.pointerType === 'touch'); pinned = it && !same(it, pinned) ? it : null; showInfo(pinned || (e.pointerType === 'touch' ? null : it)) });
cv.addEventListener('pointerleave', () => { if (!pinned) { hover = null; showInfo(null) } });
function tagStep() { const it = pinned || hover; if (!it || !it.o) { tag.style.display = 'none'; return } const o = it.o;
  if (o.seen == null) { tag.style.display = 'none'; return } const [sx, sy, sz] = scr(o.x, o.y + 2.05 * M * o.k, o.z); if (sz > 1) { tag.style.display = 'none'; return }
  tag.textContent = BY.get(o.meta.id)[5].split('，')[0]; tag.style.left = sx + 'px'; tag.style.top = sy + 'px'; tag.style.display = 'block' }

/* ---------- 镜头：绕广场转、缩放；手机单指转、双指缩放平移 ---------- */
ctl.touches = {ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN};
ctl.mouseButtons = {LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN};
ctl.screenSpacePanning = false; ctl.minDistance = 6; ctl.maxDistance = 520; ctl.maxPolarAngle = 1.48; ctl.zoomToCursor = false;
const HOME = {pos: [1392, g0 + 70, 222], tgt: [1446, g0 + 4, 322]};   // 西北高处往东南看：低太阳在西北偏西，看得到受光的南、东柱廊和纪功柱，凯旋门在右
const clampT = () => { const t = ctl.target; t.x = Math.max(CX - 170, Math.min(CX + 170, t.x)); t.z = Math.max(CZ - 150, Math.min(CZ + 150, t.z)); t.y = Math.max(g0 - 5, Math.min(g0 + 60, t.y)) };
ctl.addEventListener('change', clampT);
let fly = null;
function flyTo(pos, tgt, ms = 900) { fly = {p0: cam.position.clone(), t0: ctl.target.clone(), p1: new THREE.Vector3(...pos), t1: new THREE.Vector3(...tgt), s: performance.now(), ms} }
function flyStep() { if (!fly) return; let u = Math.min(1, (performance.now() - fly.s) / fly.ms); const e = u * u * (3 - 2 * u);
  cam.position.lerpVectors(fly.p0, fly.p1, e); ctl.target.lerpVectors(fly.t0, fly.t1, e); if (u >= 1) fly = null }
cam.position.set(...HOME.pos); ctl.target.set(...HOME.tgt); cam.fov = 50; cam.updateProjectionMatrix(); ctl.update();
function turn(dir) { const t = ctl.target, p = cam.position.clone().sub(t), a = dir * Math.PI / 4, c = Math.cos(a), s = Math.sin(a); const np = [t.x + p.x * c - p.z * s, cam.position.y, t.z + p.x * s + p.z * c]; flyTo(np, [t.x, t.y, t.z], 600) }
function zoom(k) { const t = ctl.target, p = cam.position.clone().sub(t).multiplyScalar(k); if (p.length() < ctl.minDistance || p.length() > ctl.maxDistance) return; flyTo([t.x + p.x, t.y + p.y, t.z + p.z], [t.x, t.y, t.z], 350) }
$('turnL').onclick = () => turn(-1); $('turnR').onclick = () => turn(1); $('zin').onclick = () => zoom(.7); $('zout').onclick = () => zoom(1 / .7);

/* ---------- 进门：镜头进到那一开间的柱廊里（人眼高），旁边一张卡片，一次只露一个人 ---------- */
let saved = null;
function enter(key) {
  const D0 = DOORS[key]; if (!D0) return; pinned = null; showInfo(null);
  if (!D0.card) { const s = D0.stall, y = floorAt(s.x, s.z), along = [-s.fz, s.fx];   // 站在走道上、隔两开间回头看铺子
    const ex = s.x + s.fx * 4.2 + along[0] * 6.5, ez = s.z + s.fz * 4.2 + along[1] * 6.5;
    saved = {pos: cam.position.toArray(), tgt: ctl.target.toArray(), min: ctl.minDistance};
    ctl.minDistance = .5; flyTo([ex, y + 1.7 * M, ez], [s.x, y + 1.25 * M, s.z], 1100) }
  inside = D0; let i = 0;
  const one = () => { if (!D0.who.length) return `<p class="who"><i>此刻没有人在里面。</i></p>`;
    const o = C.people[RI.get(D0.who[i])], d = personText(o); return `<p class="who"><b>${d.name}</b> <i>${d.sub}</i><br>${d.now}<br><span>${d.text}</span></p>` + (D0.who.length > 1 ? `<button id="nx" type="button">下一位（${i + 1}/${D0.who.length}）</button>` : '') };
  const draw = () => { hover = D0.who.length ? {o: C.people[RI.get(D0.who[i])]} : null;   // 卡片上是谁，画面里就给谁头上挂签
    card.innerHTML = `<button id="back" type="button">← 回到广场</button><h2>${D0.name}</h2><i>${D0.sub}</i><p>${D0.text}</p><h3>里面是谁</h3>${one()}<small>出处：${D0.src.join('；')}</small>`;
    $('back').onclick = leave; const nx = $('nx'); if (nx) nx.onclick = () => { i = (i + 1) % D0.who.length; draw() } };
  draw(); card.hidden = false; document.body.classList.add('inside');
}
function leave() { hover = null; card.hidden = true; document.body.classList.remove('inside'); if (saved) { ctl.minDistance = saved.min; flyTo(saved.pos, saved.tgt, 900) } saved = null; inside = null }
addEventListener('keydown', e => { if (e.key === 'Escape' && inside) leave(); if (e.key === 'q') turn(-1); if (e.key === 'e') turn(1) });

/* ---------- 每帧：人 + 签 + 镜头飞 ---------- */
const CULL = new THREE.PerspectiveCamera();
const T0 = +(QS.get('crowdT') || 1300);   // 引擎一天 2133 s，1194–1788 是「下午」
let last = null;
function step(t) {
  cam.updateMatrixWorld(); CULL.position.copy(cam.position); CULL.quaternion.copy(cam.quaternion); CULL.fov = cam.fov; CULL.aspect = cam.aspect; CULL.near = cam.near; CULL.far = 900; CULL.updateProjectionMatrix(); CULL.updateMatrixWorld(); CULL.matrixWorldInverse.copy(CULL.matrixWorld).invert();
  last = C.tick(T0 + t, {cam: CULL, full: true, fullM: 320, maxFull: 340, sprite: false, farBoost: 1}); window.__forumCrowd = {...last, people: C.people.length}; return last }
const t00 = performance.now();
/* 挂在 core 的渲染循环上：主画面那一遍渲染开始前（renderTarget 为空，水面倒影那一遍不算）摆人、贴签、飞镜头 */
ctx.scene.onBeforeRender = (r, sc, c, rt) => { if (rt) return; flyStep(); cam.updateMatrixWorld(); step(STILL ? SHOT_T : (performance.now() - t00) / 1000); tagStep() };
showInfo(null);
/* 钩子（无头验收用）：__forum.view / pick / tap / enter / still */
const tris = () => { let n = 0; ctx.scene.traverseVisible(c => { if (!c.isMesh || !c.geometry) return; const g = c.geometry, k = (g.index ? g.index.count : g.attributes.position.count) / 3; n += k * (c.isInstancedMesh ? c.count : 1) }); return Math.round(n) };
window.__forum = {C, CAST, PLACES, DOORS, people: () => C.people.length, tris, last: () => last,
  view: (p, t, fov) => { fly = null; cam.position.set(...p); ctl.target.set(...t); if (fov) { cam.fov = fov; cam.updateProjectionMatrix() } ctl.update() },
  home: () => window.__forum.view(HOME.pos, HOME.tgt),
  screenOf: id => { const o = C.people[RI.get(id)]; if (o.seen == null) return null; const [sx, sy, sz] = scr(o.x, o.y + 1.2 * M * o.k, o.z); return sz > 1 ? null : [sx, sy] },
  pick: (x, y, touch) => { const it = pickAt(x, y, touch); pinned = it; showInfo(it); tagStep(); return it ? (it.o ? 'person:' + it.o.meta.id : 'place:' + it.p.key) : null },
  pin: id => { const o = C.people[RI.get(id)]; pinned = {o}; showInfo(pinned); tagStep(); return true },
  place: k => { const p = PLACES.find(q => q.key === k); pinned = {p}; showInfo(pinned); return !!p },
  enter, leave, finishFly: () => { if (fly) { fly.s = -1e9; flyStep() } ctl.update() },
  render: () => { ctl.update(); return window.__still ? window.__still() : null }};
const SHOT_T = 0;
window.__forumReady = 1;
