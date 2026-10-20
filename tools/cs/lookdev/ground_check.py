#!/usr/bin/env python3
"""南港 3D · 地面穿模数字检查（CS 线，2026-10-20 r3_ground_scale）。

打开 3d.html，在页面里对每个房子 / 地标部件 / 水道桥采样 / 树的占地，按 terrain 网格同样的三角插值（4 px 格，a,c,b / b,c,d）
独立算出地面高，和模块实际用的「底」（墙或台基最低点）、「地坪」（墙/柱起点）比：
  gap    = 有一处地面（含海面 y=0）比「底」低 0.5 px 以上 → 底下漏空（飘）
  buried = 有一处地面比「地坪」高 0.5 px 以上 → 墙脚 / 门被埋
模块在 ctx.reg.footings 里登记 [{kind, id, pts:[[x,z],…], bottom, floor}]；没登记（旧代码）时按旧公式复算
（房子：地坪 = elevPx(中心)+1.5、底 = 地坪 −3；地标：地坪 = elevPx(中心)+1.6、底 = 地坪 −3，占地 = rectOf）。

用法（仓库根目录）：python3 tools/cs/lookdev/ground_check.py --year 65 --out x.json
环境变量同 render.py（LOOKDEV_CHROME / LOOKDEV_LIBS / LOOKDEV_PYLIB）。
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
if os.environ.get('LOOKDEV_PYLIB'):
    sys.path.insert(0, os.environ['LOOKDEV_PYLIB'])
from render import serve, ROOT  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

JS = r"""
(Y)=>{const ctx=window.__ctx;window.__setYear(Y);
const S=4,W=ctx.W,H=ctx.H,nx=Math.ceil(W/S)+1,G=new Map();
const g=(i,j)=>{i=Math.max(0,Math.min(nx-1,i));j=Math.max(0,Math.min(Math.ceil(H/S),j));const k=j*nx+i;if(!G.has(k))G.set(k,ctx.ground(Math.min(W,i*S),Math.min(H,j*S)));return G.get(k)};
/* 框外：从场景里的 terrain-outer 网格自己重建（规则格，同三角切法），不靠模块登记 */
let OG=null;ctx.scene.traverse(o=>{if(o.name==='terrain-outer'){const p=o.geometry.attributes.position.array;let nx=0;while(p[nx*3+2]===p[2])nx++;const nz=p.length/3/nx;
  OG={nx,nz,xs:Array.from({length:nx},(_,i)=>p[i*3]),zs:Array.from({length:nz},(_,j)=>p[j*nx*3+2]),p}}});
const bs=(A,v)=>{if(v<A[0]||v>A[A.length-1])return -1;let lo=0,hi=A.length-2;while(lo<hi){const m=(lo+hi+1)>>1;if(A[m]<=v)lo=m;else hi=m-1}return lo};
const om=(x,z)=>{if(!OG)return null;const i=bs(OG.xs,x),j=bs(OG.zs,z);if(i<0||j<0)return null;const h=(a,b)=>OG.p[((j+b)*OG.nx+i+a)*3+1],fx=(x-OG.xs[i])/(OG.xs[i+1]-OG.xs[i]),fz=(z-OG.zs[j])/(OG.zs[j+1]-OG.zs[j]);
  return fx+fz<=1?h(0,0)+(h(1,0)-h(0,0))*fx+(h(0,1)-h(0,0))*fz:h(1,1)+(h(0,1)-h(1,1))*(1-fx)+(h(1,0)-h(1,1))*(1-fz)};
const tm=(x,z)=>{if(x<0||z<0||x>W||z>H){const v=om(x,z);if(v!=null)return v}const fx0=x/S,fz0=z/S,i=Math.floor(fx0),j=Math.floor(fz0),fx=fx0-i,fz=fz0-j;
  if(fx+fz<=1)return g(i,j)+(g(i+1,j)-g(i,j))*fx+(g(i,j+1)-g(i,j))*fz;return g(i+1,j+1)+(g(i,j+1)-g(i+1,j+1))*(1-fx)+(g(i+1,j)-g(i+1,j+1))*(1-fz)};
const samp=P=>{const out=[];if(P.length===4){const n=Math.max(2,Math.ceil(Math.max(Math.hypot(P[1][0]-P[0][0],P[1][1]-P[0][1]),Math.hypot(P[3][0]-P[0][0],P[3][1]-P[0][1]))/2));
  for(let a=0;a<=n;a++)for(let b=0;b<=n;b++){const s=a/n,t=b/n,x=(P[0][0]*(1-s)+P[1][0]*s)*(1-t)+(P[3][0]*(1-s)+P[2][0]*s)*t,z=(P[0][1]*(1-s)+P[1][1]*s)*(1-t)+(P[3][1]*(1-s)+P[2][1]*s)*t;out.push([x,z])}}else for(const p of P)out.push(p);return out};
let F=ctx.reg.footings,mode='registered';
if(!F){mode='replicated-old-formula';F=[];const live=ctx.live;
  for(const f of ctx.by.house){if(!live(f))continue;const p=f.p,cx=(p[0]+p[2]+p[4]+p[6])/4,cz=(p[1]+p[3]+p[5]+p[7])/4,P=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]].map(q=>[cx+(q[0]-cx)*.92,cz+(q[1]-cz)*.92]),fl=ctx.elevPx(cx,cz)+1.5;F.push({kind:'house',id:f.id,pts:P,bottom:fl-3,floor:fl})}
  for(const f of ctx.by.landmark||[]){if(!live(f))continue;const r=ctx.geom.rectOf(f.g),fl=ctx.elevPx(r.cx,r.cz)+1.6;F.push({kind:'landmark:'+f.k,id:f.id,pts:ctx.geom.RQ(r,-r.hu,-r.hv,r.hu,r.hv),bottom:fl-3,floor:fl})}
  for(const f of ctx.by.pier||[]){if(!live(f))continue;const [a,b]=f.g,dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz),nx=-dz/L*f.w/2,nz=dx/L*f.w/2;F.push({kind:'pier',id:f.id,pts:[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]],bottom:-4,floor:2.6})}
  for(const f of ctx.by.aqueduct||[]){if(!live(f))continue;const P=f.g,S=[];for(let i=0;i<P.length-1;i++){const [ax,az]=P[i],[bx,bz]=P[i+1],L=Math.hypot(bx-ax,bz-az),n=Math.max(1,Math.ceil(L/6));for(let j=0;j<n;j++){const t=j/n;S.push([ax+(bx-ax)*t,az+(bz-az)*t,(bx-ax)/L,(bz-az)/L])}}
    for(let i=0;i<S.length-1;i++){const a=S[i],b=S[i+1];if(a[0]<0||a[1]<0||a[0]>ctx.W||a[1]>ctx.H)continue;const nx=-a[3]*2.6,nz=a[2]*2.6;F.push({kind:'aqueduct',id:f.id+':'+i,pts:[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]],bottom:Math.min(ctx.ground(a[0],a[1]),ctx.ground(b[0],b[1]))-4,floor:1e9})}}}
const R={mode,year:Y,by:{}},worst=[];
for(const q of F){const pts=samp(q.pts);let mn=1e9,mx=-1e9,mnv=1e9;for(const [x,z] of pts){const h=tm(x,z);mn=Math.min(mn,h);mx=Math.max(mx,h);mnv=Math.min(mnv,Math.max(h,0))}
  const gap=q.bottom-mnv,bur=mx-q.floor,k=q.kind;const b=R.by[k]=R.by[k]||{n:0,gap:0,buried:0,max_gap:0,max_buried:0,relief_max:0};
  b.n++;if(gap>.5)b.gap++;if(bur>.5)b.buried++;b.max_gap=Math.max(b.max_gap,+gap.toFixed(2));b.max_buried=Math.max(b.max_buried,+bur.toFixed(2));b.relief_max=Math.max(b.relief_max,+(mx-mn).toFixed(2));
  if(gap>.5||bur>.5)worst.push({kind:k,id:q.id,at:[Math.round(q.pts.reduce((a,p)=>a+p[0],0)/q.pts.length),Math.round(q.pts.reduce((a,p)=>a+p[1],0)/q.pts.length)],gap:+gap.toFixed(2),buried:+bur.toFixed(2),gmin:+mn.toFixed(2),gmax:+mx.toFixed(2),bottom:+q.bottom.toFixed(2),floor:+q.floor.toFixed(2)})}
/* 树：flora 的落点 vs 网格 */
const T={n:0,off:0,max:0};const tf=ctx.reg.treeY;for(const t of ctx.WD.trees){if(!(t[3]<=Y&&(t[4]==null||t[4]>Y)))continue;const y=tf?tf(t[0],t[1]):ctx.elevPx(t[0],t[1])+1.5,d=Math.abs(y-tm(t[0],t[1]));T.n++;if(d>.5)T.off++;T.max=Math.max(T.max,+d.toFixed(2))}
R.by.tree=T;const tot={n:0,gap:0,buried:0};for(const k in R.by){if(k==='tree')continue;tot.n+=R.by[k].n;tot.gap+=R.by[k].gap;tot.buried+=R.by[k].buried}R.total=tot;worst.sort((a,b)=>Math.max(b.gap,b.buried)-Math.max(a.gap,a.buried));R.worst=worst.slice(0,60);
/* 坡度最大的地方（给诊断机位挑点）：4 px 格上相邻差 */
const sl=[];for(let j=2;j<Math.ceil(H/S)-2;j+=3)for(let i=2;i<nx-2;i+=3){const a=g(i,j);if(a<1)continue;const s=Math.hypot(g(i+1,j)-g(i-1,j),g(i,j+1)-g(i,j-1))/(2*S);sl.push([+s.toFixed(3),i*S,j*S,+a.toFixed(1)])}
sl.sort((a,b)=>b[0]-a[0]);R.steepest=sl.slice(0,30);return R}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default='docs/living/nodes/nangang/3d.html')
    ap.add_argument('--year', type=int, default=65)
    ap.add_argument('--out', default=None)
    ap.add_argument('--param', default='')
    a = ap.parse_args()
    docs = os.path.join(ROOT, 'docs')
    url = serve(docs) + os.path.relpath(os.path.join(ROOT, a.page), docs).replace(os.sep, '/') + '?clean=1&still=1&only=buildings,landmarks,flora' + ('&' + a.param if a.param else '')
    env = dict(os.environ)
    if os.environ.get('LOOKDEV_LIBS'):
        env['LD_LIBRARY_PATH'] = os.environ['LOOKDEV_LIBS'] + ':' + env.get('LD_LIBRARY_PATH', '')
    launch = dict(args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'], env=env)
    if os.environ.get('LOOKDEV_CHROME'):
        launch['executable_path'] = os.environ['LOOKDEV_CHROME']
    with sync_playwright() as p:
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={'width': 640, 'height': 360})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url, wait_until='commit', timeout=60000)
        pg.wait_for_function('window.__ready', timeout=180000)
        R = pg.evaluate(JS, a.year)
        R['errors'] = errs[:10]
        b.close()
    s = json.dumps(R, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(s)
    print(json.dumps({k: R[k] for k in ('mode', 'year', 'total')}, ensure_ascii=False)); [print(' ', k, v) for k, v in R['by'].items()]
    print('worst:', *R['worst'][:12], sep='\n ')
    print('steepest:', R['steepest'][:10])


if __name__ == '__main__':
    main()
