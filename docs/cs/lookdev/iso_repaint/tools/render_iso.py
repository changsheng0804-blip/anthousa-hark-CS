import functools,http.server,socketserver,threading,base64,time,sys,json
from playwright.sync_api import sync_playwright
ROOT='/workspace/work/ah/docs'
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
srv=socketserver.ThreadingTCPServer(('127.0.0.1',0),functools.partial(Q,directory=ROOT));threading.Thread(target=srv.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{srv.server_address[1]}/living/nodes/nangang/3d.html?clean=1&still=1'
CX,CZ,HALF,YEAR,W,H=[float(v) for v in sys.argv[1:7]]; W=int(W);H=int(H)
AZ=float(sys.argv[7]) if len(sys.argv)>7 else 45
JS='''([cx,cz,half,W,H,az])=>{const c=window.__ctx,T=c.THREE,r=c.renderer;r.setPixelRatio(1);r.setSize(W,H);
const asp=W/H,cam=new T.OrthographicCamera(-half*asp,half*asp,half,-half,1,20000);
const el=35.264*Math.PI/180,a=az*Math.PI/180,D=6000,gy=c.groundMesh(cx,cz);
cam.position.set(cx+D*Math.cos(el)*Math.sin(a),gy+D*Math.sin(el),cz+D*Math.cos(el)*Math.cos(a));cam.lookAt(cx,gy,cz);cam.updateProjectionMatrix();
const fog=c.scene.fog;c.scene.fog=null;const out={};
r.render(c.scene,cam);out.rgb=r.domElement.toDataURL('image/png');
const dm=new T.MeshDepthMaterial();cam.near=D-1500;cam.far=D+1500;cam.updateProjectionMatrix();
const bg=c.scene.background;c.scene.background=new T.Color(0xffffff);c.scene.overrideMaterial=dm;r.render(c.scene,cam);out.depth=r.domElement.toDataURL('image/png');
c.scene.overrideMaterial=null;c.scene.background=bg;c.scene.fog=fog;return out}'''
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    pg=b.new_page(viewport={'width':W,'height':H});errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    t=time.time();pg.goto(url,wait_until='commit',timeout=60000);pg.wait_for_function('window.__ready',timeout=240000)
    pg.evaluate(f'window.__setYear({int(YEAR)})');time.sleep(3);pg.wait_for_function('window.__ready',timeout=120000)
    pg.evaluate('()=>window.__still()')
    o=pg.evaluate(JS,[CX,CZ,HALF,W,H,AZ])
    for k in o: open(f'{k}.png','wb').write(base64.b64decode(o[k].split(',')[1]))
    print('ok',round(time.time()-t,1),'s',errs[:3]);b.close()
