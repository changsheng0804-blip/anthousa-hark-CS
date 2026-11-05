# 南港全图：一台固定的全局正交等轴相机（方位 45°、俯角 35.264°、1.969 px/单位，和单格试验同比例），
# 用 setViewOffset 分 1024² 块渲染（几何天然连续），再用同一台相机把底账投影成全幅遮罩。
import functools,http.server,socketserver,threading,base64,time,sys,json,os
from playwright.sync_api import sync_playwright
ROOT='/workspace/work/ah/docs';OUT=sys.argv[1] if len(sys.argv)>1 else '.';YEAR=65
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
srv=socketserver.ThreadingTCPServer(('127.0.0.1',0),functools.partial(Q,directory=ROOT));threading.Thread(target=srv.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{srv.server_address[1]}/living/nodes/nangang/3d.html?clean=1&still=1'
SETUP='''()=>{const c=window.__ctx,T=c.THREE,MW=1820,MH=2048,K=1024/520;
const cam=new T.OrthographicCamera(-1,1,1,-1,1,20000);const el=35.264*Math.PI/180,a=45*Math.PI/180,D=6000,cx=MW/2,cz=MH/2;
cam.position.set(cx+D*Math.cos(el)*Math.sin(a),D*Math.sin(el),cz+D*Math.cos(el)*Math.cos(a));cam.lookAt(cx,0,cz);cam.updateMatrixWorld();
let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;for(const[x,z]of[[0,0],[MW,0],[0,MH],[MW,MH]])for(const y of[-5,90]){const v=new T.Vector3(x,y,z).applyMatrix4(cam.matrixWorldInverse);x0=Math.min(x0,v.x);x1=Math.max(x1,v.x);y0=Math.min(y0,v.y);y1=Math.max(y1,v.y)}
const FW=Math.ceil((x1-x0)*K/1024)*1024,FH=Math.ceil((y1-y0)*K/1024)*1024;const mx=(x0+x1)/2,my=(y0+y1)/2;
cam.left=mx-FW/K/2;cam.right=mx+FW/K/2;cam.top=my+FH/K/2;cam.bottom=my-FH/K/2;cam.updateProjectionMatrix();window.__gcam=cam;window.__FW=FW;window.__FH=FH;return [FW,FH]}'''
BLOCK='''([i,j])=>{const c=window.__ctx,r=c.renderer,cam=window.__gcam;r.setPixelRatio(1);r.setSize(1024,1024);
cam.setViewOffset(window.__FW,window.__FH,i*1024,j*1024,1024,1024);cam.updateProjectionMatrix();const fog=c.scene.fog;c.scene.fog=null;
r.render(c.scene,cam);const o=r.domElement.toDataURL('image/png');c.scene.fog=fog;cam.clearViewOffset();return o}'''
MASKS='''()=>{const c=window.__ctx,T=c.THREE,cam=window.__gcam,W=window.__FW,H=window.__FH,MW=1820,MH=2048;cam.clearViewOffset();cam.updateProjectionMatrix();
const P=(x,y,z)=>{const v=new T.Vector3(x,y,z).project(cam);return [(v.x+1)/2*W,(1-v.y)/2*H]};
const mk=()=>{const cv=document.createElement('canvas');cv.width=W;cv.height=H;const g=cv.getContext('2d');g.fillStyle='#000';g.fillRect(0,0,W,H);return [cv,g]};
const fillG=(g,G,col)=>{g.beginPath();for(const Pp of G)for(const r of Pp){r.forEach((p,i)=>{const q=P(p[0],0,p[1]);i?g.lineTo(q[0],q[1]):g.moveTo(q[0],q[1])});g.closePath()}g.fillStyle=col;g.fill('evenodd')};
// map footprint (ground heights along the edge)
const [mc,mg]=mk();mg.beginPath();const ed=[];for(let t=0;t<=MW;t+=20)ed.push([t,0]);for(let t=0;t<=MH;t+=20)ed.push([MW,t]);for(let t=MW;t>=0;t-=20)ed.push([t,MH]);for(let t=MH;t>=0;t-=20)ed.push([0,t]);
ed.forEach(([x,z],i)=>{const q=P(x,c.groundMesh(Math.min(x,MW-1),Math.min(z,MH-1)),z);i?mg.lineTo(q[0],q[1]):mg.moveTo(q[0],q[1])});mg.closePath();mg.fillStyle='#fff';mg.fill();
const [wc,wg]=mk();wg.fillStyle='#fff';wg.fillRect(0,0,W,H);
fillG(wg,c.by.land[0].g,'#000');for(const f of c.by.mole||[])if(c.live(f))fillG(wg,f.g,'#000');for(const f of c.by.water||[])if(f.k==='harbor'&&c.live(f))fillG(wg,f.g,'#fff');
const [hc,hg]=mk();hg.fillStyle='#fff';let n=0;
const hull=pts=>{pts.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);const lo=[],up=[];for(const p of pts){while(lo.length>=2&&cr(lo[lo.length-2],lo[lo.length-1],p)<=0)lo.pop();lo.push(p)}for(const p of pts.slice().reverse()){while(up.length>=2&&cr(up[up.length-2],up[up.length-1],p)<=0)up.pop();up.push(p)}return lo.slice(0,-1).concat(up.slice(0,-1))};
const cen=[];
for(const f of c.by.house){if(!c.live(f))continue;const p=f.p,pts=[];let b=-1e9;for(let i=0;i<p.length;i+=2)b=Math.max(b,c.groundMesh(p[i],p[i+1]));const top=b+(f.ht||5)*1.15+3;
 for(let i=0;i<p.length;i+=2){pts.push(P(p[i],b,p[i+1]));pts.push(P(p[i],top,p[i+1]))}
 const h=hull(pts);n++;hg.beginPath();h.forEach((q,i)=>i?hg.lineTo(q[0],q[1]):hg.moveTo(q[0],q[1]));hg.closePath();hg.fill();
 let sx=0,sz=0;for(let i=0;i<p.length;i+=2){sx+=p[i];sz+=p[i+1]}const k=p.length/2;cen.push(P(sx/k,top,sz/k))}
const [sc,sg]=mk();sg.strokeStyle='#fff';sg.lineCap='round';const K=W/(cam.right-cam.left);
for(const f of c.by.street){if(!c.live(f))continue;const g=f.g;sg.lineWidth=Math.max(1,(f.w||6)*K*0.9);sg.beginPath();for(let i=0;i<g.length;i+=2){const q=P(g[i],c.groundMesh(g[i],g[i+1]),g[i+1]);i?sg.lineTo(q[0],q[1]):sg.moveTo(q[0],q[1])}sg.stroke()}
return {map:mc.toDataURL(),water:wc.toDataURL(),houses:hc.toDataURL(),streets:sc.toDataURL(),n,cen}}'''
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    pg=b.new_page(viewport={'width':1024,'height':1024});errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    t=time.time();pg.goto(url,wait_until='commit',timeout=60000);pg.wait_for_function('window.__ready',timeout=300000)
    pg.evaluate(f'window.__setYear({YEAR})');time.sleep(3);pg.wait_for_function('window.__ready',timeout=120000);pg.evaluate('()=>window.__still()')
    FW,FH=pg.evaluate(SETUP);print('full',FW,FH,round(time.time()-t),'s',flush=True)
    os.makedirs(f'{OUT}/blocks',exist_ok=True)
    m=pg.evaluate(MASKS)
    for k in ('map','water','houses','streets'):open(f'{OUT}/ledger_{k}.png','wb').write(base64.b64decode(m[k].split(',')[1]))
    json.dump({'FW':FW,'FH':FH,'year':YEAR,'houses':m['n'],'cen':m['cen']},open(f'{OUT}/ledger.json','w'))
    print('masks',m['n'],round(time.time()-t),'s',flush=True)
    for j in range(FH//1024):
        for i in range(FW//1024):
            fn=f'{OUT}/blocks/r_{i}_{j}.png'
            if os.path.exists(fn):continue
            o=pg.evaluate(BLOCK,[i,j]);open(fn,'wb').write(base64.b64decode(o.split(',')[1]))
        print('row',j,round(time.time()-t),'s',flush=True)
    print('errs',errs[:3]);b.close()
