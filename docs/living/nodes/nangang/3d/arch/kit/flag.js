/* house_kit 开关（docs/flags.json 登记，默认关）。3d.html 是 core 的文件、没载 docs/flags.js，这里照 flags.js 的同一套规矩读：
   ?flag=a,b 打开（记 localStorage「anthousa.flags」）、?flag=-a 关、?flag=clear 全清；没登记或过期一律当关。
   开关没被点名时不发任何请求，页面行为和没有本文件时完全一样。——Hark（CS线）2026-10-20 */
const KEY='anthousa.flags';
let on={};
try{JSON.parse(localStorage.getItem(KEY)||'[]').forEach(n=>{on[n]=1})}catch(e){}
const q=new URLSearchParams(location.search).get('flag');
if(q){q.split(',').forEach(s=>{s=s.trim();if(!s)return;if(s==='clear')on={};else if(s[0]==='-')delete on[s.slice(1)];else on[s]=1});
  try{localStorage.setItem(KEY,JSON.stringify(Object.keys(on)))}catch(e){}}
async function valid(n){try{const R=await fetch(new URL('../../../../../../flags.json',import.meta.url)).then(r=>r.json()),f=R.flags.find(x=>x.name===n),today=new Date().toISOString().slice(0,10);return !!f&&(!f.expires||f.expires>=today)}catch(e){return false}}
export const HOUSE_KIT=on.house_kit?await valid('house_kit'):false;
