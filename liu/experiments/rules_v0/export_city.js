// 规模测试用：用页面同一个 household() 推演，给 world.json 全城 18943 栋房子生成「合成人家」。
// 坐标先用仿射（world→干山页像素，由 8 个同名地标拟合，残差 <25px）换到页面尺度，地标换成全城建筑（让港口/宫殿/竞技场附近有各自行当）。
// 这些人家不是账本人家，只做数量/时间测试，不写故事。
// usage: node experiments/rules_v0/export_city.js > ../city_hh.json
const fs=require('fs'),path=require('path');
const dir='docs/living/xerolophos';
const src=fs.readFileSync(path.join(dir,'index.html'),'utf8');
const cut=(a,b)=>{const i=src.indexOf(a),j=src.indexOf(b,i);return src.slice(i,j)};
const utils=cut('/* ---------- utils ---------- */','/* ---------- base image');
const hhs=cut('/* ---------- households','function famAt');
const W=JSON.parse(fs.readFileSync('world.json'));
const M=JSON.parse(fs.readFileSync(path.join(__dirname,'affine.json')));
const T=(x,y)=>[x*M[0][0]+y*M[1][0]+M[2][0], x*M[0][1]+y*M[1][1]+M[2][1]];
const city=JSON.parse(fs.readFileSync(path.join(dir,'city.json')));
const cen=g=>{let c=g.coords;if(g.type==='polygon'&&Array.isArray(c[0][0]))c=c[0];let x=0,y=0;c.forEach(p=>{x+=p[0];y+=p[1]});return [x/c.length,y/c.length]};
city.landmarks=W.structures.filter(s=>s.geom&&s.geom.coords&&s.geom.coords.length&&!/^r_|wall|^d_|aq_/.test(s.id)).map(s=>({id:s.id,xy:T(...cen(s.geom)),name:s.name,now:{},story:''}));
const HD={houses:W.houses.map(h=>{const p=[];h.p.forEach(q=>{const t=T(q[0],q[1]);p.push(t[0],t[1])});return [h.id,h.d,h.built,h.destroyed==null?9999:h.destroyed,p]}),late:[]};
const SCENE={};
const fn=new Function('city','HD','SCENE',utils+'\n'+hhs+'\nreturn {houses,household,nearestLM};');
const {houses,household,nearestLM}=fn(city,HD,SCENE);
const out=houses.filter(h=>h.built<=60).map(h=>{const hh=household(h);return {id:h.id,d:h.d,cx:Math.round(h.cx),cy:Math.round(h.cy),built:h.built,destroyed:h.destroyed,
  fams:hh.fams.map(f=>({B:f.B,out:f.out,origin:f.origin,faith:f.faith,trade:f.trade,people:f.people.map(p=>({n:p.n,s:p.s,b:p.b,d:p.d,g:p.g,bride:!!p.bride,married:p.married||null,left:p.left||null,to:p.to||null}))})),
  ev:hh.ev.filter(e=>/当了兵|南港大火烧了他们/.test(e[1]))}});
process.stdout.write(JSON.stringify(out));
