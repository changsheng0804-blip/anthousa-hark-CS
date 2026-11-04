import functools,http.server,socketserver,threading,base64,time,sys
from playwright.sync_api import sync_playwright
ROOT='/workspace/work/ah/docs'
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
srv=socketserver.ThreadingTCPServer(('127.0.0.1',0),functools.partial(Q,directory=ROOT));threading.Thread(target=srv.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{srv.server_address[1]}/living/nodes/nangang/3d.html?clean=1&still=1'
CX,CZ,HALF,YEAR,W,H,AZ=1500,1180,260,65,1024,1024,45
JS='''([cx,cz,half,W,H,az])=>{const c=window.__ctx,T=c.THREE;
const cam=new T.OrthographicCamera(-half*W/H,half*W/H,half,-half,1,20000);
const el=35.264*Math.PI/180,a=az*Math.PI/180,D=6000,gy=c.groundMesh(cx,cz);
cam.position.set(cx+D*Math.cos(el)*Math.sin(a),gy+D*Math.sin(el),cz+D*Math.cos(el)*Math.cos(a));cam.lookAt(cx,gy,cz);cam.updateProjectionMatrix();cam.updateMatrixWorld();
const P=(x,y,z)=>{const v=new T.Vector3(x,y,z).project(cam);return [(v.x+1)/2*W,(1-v.y)/2*H]};
const mk=()=>{const cv=document.createElement('canvas');cv.width=W;cv.height=H;const g=cv.getContext('2d');g.fillStyle='#000';g.fillRect(0,0,W,H);return [cv,g]};
// water: whole plane white, land+live moles black, live harbours white again (projected at y=0)
const [wc,wg]=mk();wg.fillStyle='#fff';wg.fillRect(0,0,W,H);
const fillG=(g,G,col)=>{g.beginPath();for(const Pp of G)for(const r of Pp){r.forEach((p,i)=>{const q=P(p[0],0,p[1]);i?g.lineTo(q[0],q[1]):g.moveTo(q[0],q[1])});g.closePath()}g.fillStyle=col;g.fill('evenodd')};
fillG(wg,c.by.land[0].g,'#000');for(const f of c.by.mole||[])if(c.live(f))fillG(wg,f.g,'#000');for(const f of c.by.water||[])if(f.k==='harbor'&&c.live(f))fillG(wg,f.g,'#fff');
// houses: hull of base+top corners
const [hc,hg]=mk();hg.fillStyle='#fff';let n=0;
const hull=pts=>{pts.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);const lo=[],up=[];for(const p of pts){while(lo.length>=2&&cr(lo[lo.length-2],lo[lo.length-1],p)<=0)lo.pop();lo.push(p)}for(const p of pts.slice().reverse()){while(up.length>=2&&cr(up[up.length-2],up[up.length-1],p)<=0)up.pop();up.push(p)}return lo.slice(0,-1).concat(up.slice(0,-1))};
const cen=[];
for(const f of c.by.house){if(!c.live(f))continue;const p=f.p,pts=[];let b=-1e9;for(let i=0;i<p.length;i+=2)b=Math.max(b,c.groundMesh(p[i],p[i+1]));const top=b+(f.ht||5)*1.15+3;
 for(let i=0;i<p.length;i+=2){pts.push(P(p[i],b,p[i+1]));pts.push(P(p[i],top,p[i+1]))}
 const h=hull(pts);if(h.every(q=>q[0]<0||q[0]>W||q[1]<0||q[1]>H))continue;n++;hg.beginPath();h.forEach((q,i)=>i?hg.lineTo(q[0],q[1]):hg.moveTo(q[0],q[1]));hg.closePath();hg.fill();
 let sx=0,sz=0;for(let i=0;i<p.length;i+=2){sx+=p[i];sz+=p[i+1]}const k=p.length/2;cen.push(P(sx/k,top,sz/k))}
// streets
const [sc,sg]=mk();sg.strokeStyle='#fff';sg.lineCap='round';
for(const f of c.by.street){if(!c.live(f))continue;const g=f.g;sg.lineWidth=Math.max(1,(f.w||6)*W/(2*half)*0.9);sg.beginPath();for(let i=0;i<g.length;i+=2){const q=P(g[i],c.groundMesh(g[i],g[i+1]),g[i+1]);i?sg.lineTo(q[0],q[1]):sg.moveTo(q[0],q[1])}sg.stroke()}
return {water:wc.toDataURL(),houses:hc.toDataURL(),streets:sc.toDataURL(),n,cen:cen.filter(q=>q[0]>=0&&q[0]<W&&q[1]>=0&&q[1]<H)}}'''
import json
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    pg=b.new_page(viewport={'width':W,'height':H})
    pg.goto(url,wait_until='commit',timeout=60000);pg.wait_for_function('window.__ready',timeout=240000)
    pg.evaluate(f'window.__setYear({YEAR})');time.sleep(3)
    o=pg.evaluate(JS,[CX,CZ,HALF,W,H,AZ])
    for k in ('water','houses','streets'): open(f'ledger_{k}.png','wb').write(base64.b64decode(o[k].split(',')[1]))
    json.dump(o['cen'],open('ledger_cen.json','w'));print('houses',o['n'],'in-frame centres',len(o['cen']));b.close()
