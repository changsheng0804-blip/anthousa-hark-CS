#!/usr/bin/env python3
"""check_econ：刘线生计/房况旁车（docs/living/xerolophos/econ/）进 CS 干山页敲门卡的自检。python3 liu/tools/check_econ.py
 ① 旁车每户的 id（'h数字'）都在 world.json 的 houses 里；
 ② 年份覆盖：每个文件 y0=40、y1=70，每户 31 档；40…70 每一年都有户；
 ③ 无空值：非 null 的一档 28 个字段全是数，下标都在各自的表里（term/liv/maint/facade/types/lsrc）；每户至少一档非 null；
 ④ CS 干山页 houses.json 的每栋房，它所在分组文件都在（页面不会取到 404）；SOURCE.md 写明刘线来源与破败偏高；
 ⑤ 页面：econ/ 只在敲门卡的 ECON 段里取（不预载）；用 node 跑这一段：页面拼出的「为什么」短句与刘线 surfWhy（Python 端）抽样逐字一致；
    有旁车的房子出一段「生计/房况」、只一段、没有 undefined/NaN；40 年前 / 没有旁车的 id / 点人 → 不出；卡换房子后旧请求不插；同组只取一次；
 ⑥ 体积：旁车总量 ≤ 15 MB、单文件 ≤ 0.25 MB。
——Hark（刘线）"""
import json, os, sys, glob, subprocess, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
X = os.path.join(ROOT, 'docs', 'living', 'xerolophos'); E = os.path.join(X, 'econ'); bad = []
def need(c, m):
    if not c: bad.append(m)
W = {h['id'] for h in json.load(open(os.path.join(ROOT, 'world.json')))['houses']}
fs = sorted(glob.glob(os.path.join(E, 'g*.json'))); need(len(fs) > 50, f'econ 只有 {len(fs)} 个文件')
nh = 0; years = {y: 0 for y in range(40, 71)}; tot = 0; mx = 0; groups = set(); notw = []
for f in fs:
    b = os.path.getsize(f); tot += b; mx = max(mx, b); J = json.load(open(f)); groups.add(J['g'])
    need(os.path.basename(f) == 'g%d.json' % J['g'], f'{f} 文件名与 g 不符')
    need(J['y0'] == 40 and J['y1'] == 70, f'{f} 年份段不是 40–70')
    L = {'term': len(J['term']), 'liv': len(J['liv']), 'maint': len(J['maint']), 'facade': len(J['facade']), 'types': len(J['types'])}
    need(all(str(y) in J['path'] for y in range(40, 71)), f'{f} path 缺年份')
    for lid, rows in J['h'].items():
        nh += 1
        if lid not in W: notw.append(lid)
        need(re.fullmatch(r'h\d+', lid) and int(lid[1:]) // 64 == J['g'], f'{f} {lid} 分错组')
        need(len(rows) == 31, f'{lid} 不是 31 档'); need(any(r is not None for r in rows), f'{lid} 全是空档')
        for k, r in enumerate(rows):
            if r is None: continue
            years[40 + k] += 1
            ok = isinstance(r, list) and len(r) == 28 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in r)
            if not ok: need(False, f'{lid} AF{40+k} 有空值/形状不对：{r}'); continue
            need(-1 <= r[0] < L['term'] and 0 <= r[1] < L['liv'] and 0 <= r[2] < L['maint'] and 0 <= r[4] < L['facade'] and -1 <= r[13] < L['types'] and -1 <= r[15] < L['types']
                 and -1 <= r[21] < L['maint'] and -1 <= r[27] < len(J['lsrc']) and 0 <= r[3] <= 100, f'{lid} AF{40+k} 下标越界：{r}')
need(not notw, f'{len(notw)} 户 id 不在 world.json：{notw[:5]}')
need(all(v > 0 for v in years.values()), '有年份没有一户：' + str([y for y, v in years.items() if v == 0]))
page = [h[0] for h in json.load(open(os.path.join(X, 'houses.json')))['houses']]
miss = sorted({i // 64 for i in page} - groups); need(not miss, f'CS 页面房屋所在分组缺文件：{miss[:5]}')
src = open(os.path.join(E, 'SOURCE.md'), encoding='utf8').read() if os.path.exists(os.path.join(E, 'SOURCE.md')) else ''
need('刘线' in src and '36' in src and 'v24' in src, 'SOURCE.md 没写刘线来源 / 破败偏高待 v24')
need(tot <= 15e6, f'旁车总量 {tot/1e6:.1f} MB > 15 MB'); need(mx <= 0.25e6, f'单文件 {mx/1e6:.2f} MB > 0.25 MB')
# ⑤ 页面行为（node）
js = r'''
const fs=require('fs'),path=require('path');const X=process.argv[2],S=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const html=fs.readFileSync(path.join(X,'index.html'),'utf8');const a=html.indexOf('/* 刘线 · 生计/房况'),b=html.indexOf('{const _econShow=showCard');
const bad=[];const need=(c,m)=>{if(!c)bad.push(m)};if(a<0||b<a){console.log(JSON.stringify(['页面里没有 ECON 段']));process.exit(1)}
need(!/econ\//.test(html.slice(0,a))&&!/econ\//.test(html.slice(b+40)),'页面别处出现了 econ/ 请求');
const code=html.slice(a,b);const reqs=[];
const fakeFetch=u=>{reqs.push(u);const f=path.join(X,u);return Promise.resolve(fs.existsSync(f)?{ok:true,json:()=>Promise.resolve(JSON.parse(fs.readFileSync(f,'utf8')))}:{ok:false})};
function mk(){const el={cardbody:{innerHTML:'',insertAdjacentHTML(w,h){this.innerHTML+=h}},card:{style:{display:'block'}}};const st={sel:null,YEAR:50};
  const env=new Function('fetch','$','st','var sel,YEAR;'+code+';return {econFill,econLoad,econWhy,econText,set sel(v){sel=v},set YEAR(v){YEAR=v}}')(fakeFetch,k=>el[k],st);return {env,el}}
(async()=>{const {env,el}=mk();need(reqs.length===0,'载入时就取了 econ');
  // 短句逐字一致
  let n=0,diff=0;const groups={};for(const [k,want] of Object.entries(S)){const [lid,y]=k.split('|');const id=+lid.slice(1);const J=await env.econLoad(id);const r=J.h[lid][+y-40];const got=env.econWhy(J,r,+y);n++;if(got!==want){diff++;if(diff<4)bad.push('短句不一致 '+k+'\n  页面：'+got+'\n  刘线：'+want)}}
  const r0=reqs.length;await env.econLoad(Number(Object.keys(S)[0].split('|')[0].slice(1)));need(reqs.length===r0,'同组取了两次');
  // 卡片
  const files=fs.readdirSync(path.join(X,'econ')).filter(f=>/^g\d+\.json$/.test(f)).slice(0,40);let shown=0,tried=0;
  for(const f of files){const J=JSON.parse(fs.readFileSync(path.join(X,'econ',f),'utf8'));for(const [lid,rows] of Object.entries(J.h).slice(0,3)){for(const Y of [40,50,60,65,70]){tried++;
    el.cardbody.innerHTML='<h2>卡</h2>';el.card.style.display='block';env.sel={kind:'house',hh:{h:{id:+lid.slice(1)}}};env.YEAR=Y;await env.econFill();const s=el.cardbody.innerHTML,c=(s.match(/obj econ/g)||[]).length;
    need(c<=1,lid+' 不止一段');need(c===(rows[Y-40]?1:0),lid+' AF'+Y+(rows[Y-40]?' 有旁车却没出段':' 没旁车却出了段'));if(c){shown++;need(!/undefined|NaN|null|\{\w+\}/.test(s),lid+' AF'+Y+' 段里有 undefined/NaN/未填模板：'+s)}}}}
  need(shown>20,'出段太少 '+shown+'/'+tried);
  el.cardbody.innerHTML='<h2>卡</h2>';env.sel={kind:'house',hh:{h:{id:2604}}};env.YEAR=30;await env.econFill();need(!/obj econ/.test(el.cardbody.innerHTML),'40 年前不该出段');
  el.cardbody.innerHTML='<h2>卡</h2>';env.sel={kind:'house',hh:{h:{id:99999999}}};env.YEAR=50;await env.econFill();need(!/obj econ/.test(el.cardbody.innerHTML),'没有旁车的 id 不该出段');
  el.cardbody.innerHTML='<h2>卡</h2>';env.sel={kind:'named',P:{}};env.YEAR=50;await env.econFill();need(!/obj econ/.test(el.cardbody.innerHTML),'点人不该出段');
  const {env:e2,el:l2}=mk();l2.cardbody.innerHTML='<h2>卡</h2>';const s0={kind:'house',hh:{h:{id:2604}}};e2.sel=s0;e2.YEAR=50;const pr=e2.econFill();e2.sel={kind:'house',hh:{h:{id:2611}}};await pr;need(!/obj econ/.test(l2.cardbody.innerHTML),'卡换了房子旧请求还插了段');
  console.log(JSON.stringify(bad));console.error(`短句比对 ${n} 条、不一致 ${diff}；卡片 ${tried} 次里出段 ${shown}；取 econ ${reqs.length} 次`);process.exit(bad.length?1:0)})();
'''
open('/tmp/check_econ_page.js', 'w').write(js)
p = subprocess.run(['node', '/tmp/check_econ_page.js', X, os.path.join(ROOT, 'liu', 'tools', 'econ_why_sample.json')], capture_output=True, text=True)
try: bad += json.loads(p.stdout.strip().splitlines()[-1])
except Exception: bad.append('页面检查没跑起来：' + p.stdout[-500:] + p.stderr[-500:])
print(f'econ：{len(fs)} 个文件、{nh} 户、{tot/1e6:.2f} MB（单文件最大 {mx/1e3:.0f} KB）；每年户数 AF40 {years[40]} / AF60 {years[60]} / AF70 {years[70]}；' + p.stderr.strip())
print('\n'.join(bad) or '✅ 全过'); sys.exit(1 if bad else 0)
