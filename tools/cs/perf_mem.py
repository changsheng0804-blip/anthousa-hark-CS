"""CS 线 · 显存压力测（审核意见 2026-10-14）：街巷级三个年份来回拖、横穿 8 秒、退回全城，量层缓存（LAY）和瓦片位图占的字节。
在所有者 Mac 上跑：/usr/bin/python3 perf_mem.py live desk|mob 。线：桌面层缓存峰值 ≤ 480MB、手机 ≤ 256MB；退回全城 3.5 秒后层缓存 = 0；页面零报错。
old 模式给旧页面注入 window.__LAY 用来对比；new 模式用 ~/anthousa-perf/new_index.html 顶替线上页面。"""
import json,os,sys,base64
from playwright.sync_api import sync_playwright
URL='https://changsheng0804-blip.github.io/anthousa-hark-CS/living/tiles/'
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NEW=open(os.path.expanduser('~/anthousa-perf/new_index.html')).read() if sys.argv[1]=='new' else ''
MODE=sys.argv[1]  # old|new
MOB=sys.argv[2]=='mob'
FPS="""ms=>new Promise(r=>{let n=0,t0=performance.now(),worst=0,last=t0;function f(t){n++;worst=Math.max(worst,t-last);last=t;if(t-t0<ms)requestAnimationFrame(f);else r({fps:+(n*1000/(t-t0)).toFixed(1),worst:+worst.toFixed(0)})}requestAnimationFrame(f)})"""
SUM="""()=>{const LAY=window.__LAY||__TILES.LAY;let n=0,b=0;for(const L of LAY.values()){n++;b+=L.cv.width*L.cv.height*4}
let cb=0;for(const t of __TILES.cache.values())if(t&&t.im&&t.im.width)cb+=t.im.width*t.im.height*4;
return {lay_n:n,lay_mb:Math.round(b/1048576),tile_mb:Math.round(cb/1048576)}}"""
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=CH,headless=True,args=['--enable-precise-memory-info','--use-angle=metal','--ignore-gpu-blocklist'])
    ctx=b.new_context(viewport={'width':390,'height':844} if MOB else {'width':1440,'height':900},device_scale_factor=3 if MOB else 2,has_touch=MOB,is_mobile=MOB)
    pg=ctx.new_page();ER=[];pg.on('pageerror',lambda e:ER.append(str(e)[:300]))
    def rt(route):
        r=route.fetch();body=NEW if MODE=='new' else r.text() if MODE=='live' else r.text().replace('const LAY=new Map();','const LAY=window.__LAY=new Map();')
        route.fulfill(response=r,body=body,headers={**r.headers,'content-type':'text/html; charset=utf-8'})
    pg.route('**/living/tiles/',rt)
    pg.goto(URL,wait_until='networkidle');pg.wait_for_timeout(1500)
    M=pg.evaluate("()=>__TILES.M");tp=M['tile_px'];G=M['grid']
    def go(x,y,z): pg.evaluate("([x,y,z])=>{const T=__TILES;T.cam.x=x;T.cam.y=y;T.cam.z=z;T.zoomAt(innerWidth/2,innerHeight/2,1)}",[x,y,z])
    peak=0;out={}
    for yr in [60,40,70]:
        pg.evaluate("y=>__TILES.setYear(y)",yr)
        for z in [1.2,2.0]:
            for i in range(10):
                go(G[0]*tp*(0.2+0.06*i),G[1]*tp*(0.45+0.02*(i%3)),z);pg.wait_for_timeout(600);peak=max(peak,pg.evaluate(SUM)['lay_mb'])
    out['peak_lay_mb']=peak;out['street_end']=pg.evaluate(SUM)
    # pan fps at street level
    go(G[0]*tp*0.3,G[1]*tp*0.5,2.0);pg.wait_for_timeout(2500)
    pg.evaluate("([W])=>{const T=__TILES;window.__pan=1;const t0=performance.now(),x0=T.cam.x;(function f(){if(!window.__pan)return;const k=Math.min(1,(performance.now()-t0)/8000);T.cam.x=x0+W*0.4*k;T.zoomAt(innerWidth/2,innerHeight/2,1);requestAnimationFrame(f)})()}",[G[0]*tp])
    out['pan_fps']=pg.evaluate(FPS,7500);pg.evaluate("()=>window.__pan=0");out['after_pan']=pg.evaluate(SUM)
    go(G[0]*tp/2,G[1]*tp/2,0.08);pg.wait_for_timeout(3500);out['back_to_city']=pg.evaluate(SUM)
    out['errors']=ER;lim=256 if MOB else 480
    out['pass']=not ER and out['peak_lay_mb']<=lim and out['back_to_city']['lay_n']==0
    print(MODE,'mob' if MOB else 'desk',json.dumps(out,ensure_ascii=False),flush=True)
