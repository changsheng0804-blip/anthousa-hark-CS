#!/usr/bin/env python3
"""crowd 自查探针（lookdev 第 2 轮）：按 shots.json 的机位打开 3d.html?still=1，拍一帧，读 window.__crowdStats（这一帧在场/关节人/远柱/三角形/绘制调用），
再数「画面里看得见的人」：把每个被摆进画面的人（引擎 pickable = 视锥内）投到屏幕，头或脚在画面内、且不被房子挡（深度缓冲读回比较）才算。
最后把 crowd 的 tick 连跑 60 次取中位数（毫秒，CPU 端：位置 + 姿势 + 实例矩阵）。沙箱数字只作上限估计，不代表主人 Mac。
用法（仓库根）：python3 docs/cs/lookdev/r2/crowd/probe.py --shot 2 [--param ...]"""
import argparse, base64, json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'cs', 'lookdev'))
if os.environ.get('LOOKDEV_PYLIB'): sys.path.insert(0, os.environ['LOOKDEV_PYLIB'])
from playwright.sync_api import sync_playwright
from render import serve

JS_PTS = r"""()=>{const C=window.__crowd.C,cam=window.__ctx.camera,T=window.__ctx.THREE,V=new T.Vector3(),M=1/C.MPP,W=innerWidth,H=innerHeight,out=[];
 for(const o of C.pickable()){const q=[];for(const hy of [0,1.2,1.55]){V.set(o.x,o.y+hy*M,o.z).project(cam);q.push([(V.x+1)/2*W,(1-V.y)/2*H,V.z])}
  out.push({id:o.F?o.F[0]:-1,d:Math.round(Math.hypot(o.x-cam.position.x,o.z-cam.position.z)*C.MPP),foot:q[0],torso:q[1],head:q[2]})}return out}"""

ap = argparse.ArgumentParser(); ap.add_argument('--shot', default='2'); ap.add_argument('--param', default=''); ap.add_argument('--out', default='/tmp/crowd_probe'); ap.add_argument('--bench', type=int, default=60)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
S = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/shots.json')))
env = dict(os.environ)
if os.environ.get('LOOKDEV_LIBS'): env['LD_LIBRARY_PATH'] = os.environ['LOOKDEV_LIBS'] + ':' + env.get('LD_LIBRARY_PATH', '')
launch = dict(args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'], env=env)
if os.environ.get('LOOKDEV_CHROME'): launch['executable_path'] = os.environ['LOOKDEV_CHROME']
url = serve(os.path.join(ROOT, 'docs')) + 'living/nodes/nangang/3d.html?clean=1&still=1' + ('&' + a.param if a.param else '')
res = {}
import io
import numpy as np
from PIL import Image
def count(on, off, pts):
    A = np.asarray(Image.open(io.BytesIO(base64.b64decode(on.split(',', 1)[1]))).convert('RGB')).astype(int)
    B = np.asarray(Image.open(io.BytesIO(base64.b64decode(off.split(',', 1)[1]))).convert('RGB')).astype(int)
    D = np.abs(A - B).sum(2) > 12; H, W = D.shape
    vis = []; inframe = 0
    for q in pts:
        hpx = abs(q['foot'][1] - q['head'][1])
        if q['head'][2] > 1 or not any(0 <= p[0] < W and 0 <= p[1] < H for p in (q['torso'], q['head'])): continue
        inframe += 1
        hit = False
        for p in (q['torso'], q['head']):
            x, y = int(p[0]), int(p[1])
            if 0 <= x < W and 0 <= y < H and D[max(0, y-1):y+2, max(0, x-1):x+2].any(): hit = True
        if hit: vis.append((q['id'], q['d'], round(hpx, 1)))
    v6 = [v for v in vis if v[2] >= 6]
    return {'in_frame': inframe, 'visible_any': len(vis), 'visible_ge3px': sum(v[2] >= 3 for v in vis), 'visible_ge6px': len(v6), 'visible_ge20px': sum(v[2] >= 20 for v in vis),
            'all_from_crowd_json': all(v[0] >= 0 for v in vis), 'nearest': sorted(vis, key=lambda v: v[1])[:8]}
with sync_playwright() as p:
    b = p.chromium.launch(**launch); pg = b.new_page(viewport={'width': 1376, 'height': 768}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(url, wait_until='commit', timeout=60000); pg.wait_for_function('window.__ready', timeout=180000)
    res['modStats_crowd_at_build'] = pg.evaluate('window.__modStats.crowd')
    for sid in a.shot.split(','):
        s = [x for x in S['shots'] if str(x['id']) == sid][0]
        pg.evaluate('s=>window.__applyShot(s)', s); time.sleep(.5)
        png = pg.evaluate('()=>window.__still()'); open(os.path.join(a.out, f'shot{sid}.png'), 'wb').write(base64.b64decode(png.split(',', 1)[1]))
        r = {'stats': pg.evaluate('window.__crowdStats')}
        pts = pg.evaluate(JS_PTS)
        off = pg.evaluate('()=>{const C=window.__crowd.C;for(const k in C.parts)C.parts[k].visible=false;return 1}')
        png0 = pg.evaluate('()=>window.__still()')
        pg.evaluate('()=>{const C=window.__crowd.C;for(const k in C.parts)C.parts[k].visible=true}')
        r['count'] = count(png, png0, pts)
        if a.bench: r['bench_ms'] = pg.evaluate(f'window.__crowd.bench({a.bench})')
        pg.evaluate('()=>window.__still()')
        res[f'shot{sid}'] = r
    res['errors'] = errs[:10]; b.close()
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(a.out, 'probe.json'), 'w'), ensure_ascii=False, indent=1)
