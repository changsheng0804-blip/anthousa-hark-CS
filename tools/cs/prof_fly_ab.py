# CS 线 · 飞行 A/B（有/无史诗叠层）+ CDP 累计时间占比；依赖 prof_tiles.py 的服务器部分
import json,os,sys,collections
sys.argv=['x']
__file__='/workspace/work/ah/tools/cs/prof_tiles.py'
exec(open('tools/cs/prof_tiles.py').read().split("out = {}")[0])
P=json.load(open(os.path.join(ROOT,'docs/living/tiles/places.json')));QC={c['q']:c for c in P['quarters']}
FLY="""async([x,y,z])=>{const T=__TILES;let n=0,w=0,l=performance.now();const t0=l;let run=true;const f=t=>{if(!run)return;n++;w=Math.max(w,t-l);l=t;requestAnimationFrame(f)};requestAnimationFrame(f);await T.flyTo(x,y,z,{year:60});run=false;return {fps:+(n*1000/(performance.now()-t0)).toFixed(1),worst:+w.toFixed(0)}}"""
res=collections.defaultdict(list)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for rep in range(2):
      for tag in ('有','无'):
        pg=b.new_page(viewport={'width':1440,'height':900})
        if tag=='无': pg.route('**/ep.json',lambda r:r.fulfill(status=404,body=''))
        pg.goto(url,wait_until='networkidle');pg.evaluate("()=>__TILES.setYear(60)");pg.wait_for_timeout(1500)
        cdp=pg.context.new_cdp_session(pg);cdp.send('Profiler.enable');cdp.send('Profiler.start')
        a=pg.evaluate(FLY,[QC['nangang']['x'],QC['nangang']['y'],4.5]);pg.wait_for_timeout(800)
        c=pg.evaluate(FLY,[QC['siqiu']['x'],QC['siqiu']['y'],4.5])
        prof=cdp.send('Profiler.stop')['profile']
        cnt=collections.Counter(prof['samples']);tot=sum(cnt.values());byid={n['id']:n for n in prof['nodes']};parent={}
        for n in prof['nodes']:
            for ch in n.get('children',[]):parent[ch]=n['id']
        incl=collections.Counter()
        for i,k in cnt.items():
            seen=set();j=i
            while j is not None:
                nm=byid[j]['callFrame']['functionName']
                if nm and nm not in seen:incl[nm]+=k;seen.add(nm)
                j=parent.get(j)
        res[tag].append((a,c,[(k,round(100*v/tot,1)) for k,v in incl.most_common(18)]))
        print(tag,a,c,[(k,round(100*v/tot,1)) for k,v in incl.most_common(18)],flush=True);pg.close()
