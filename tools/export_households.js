// Run the page's own household() derivation in node so generated stories start from the exact same families the page shows.
// usage: node tools/export_households.js docs/living/xerolophos > work.json
const fs=require('fs'),path=require('path');
const dir=process.argv[2]||'docs/living/xerolophos';
const src=fs.readFileSync(path.join(dir,'index.html'),'utf8');
const cut=(a,b)=>{const i=src.indexOf(a),j=src.indexOf(b,i);if(i<0||j<0)throw new Error('marker '+a);return src.slice(i,j)};
const utils=cut('/* ---------- utils ---------- */','/* ---------- base image');
const hhs=cut('/* ---------- households','function famAt');
const city=JSON.parse(fs.readFileSync(path.join(dir,'city.json')));
const HD=JSON.parse(fs.readFileSync(path.join(dir,'houses.json')));
const SCENE=JSON.parse(fs.readFileSync(path.join(dir,'scene.json')));
const fn=new Function('city','HD','SCENE',utils+'\n'+hhs+'\nreturn {houses,household,nearestLM};');
const {houses,household,nearestLM}=fn(city,HD,SCENE);
const out=houses.map(h=>{const hh=household(h);const [lm,ld]=nearestLM(h.cx,h.cy);
  return {id:h.id,cx:Math.round(h.cx),cy:Math.round(h.cy),built:h.built,destroyed:h.destroyed,lm:lm.id,lmd:Math.round(ld),obj:hh.obj,
    fams:hh.fams.map(f=>({B:f.B,out:f.out,origin:f.origin,faith:f.faith,trade:f.trade,people:f.people.map(p=>({n:p.n,s:p.s,b:p.b,d:p.d,g:p.g,bride:!!p.bride,married:p.married||null,left:p.left||null,to:p.to||null}))})),
    ev:hh.ev}});
process.stdout.write(JSON.stringify(out));
