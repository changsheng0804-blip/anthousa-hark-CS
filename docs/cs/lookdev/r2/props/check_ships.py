#!/usr/bin/env python3
"""props 自查：当年在用的每座栈桥恰好一条大船（CS 线，lookdev 第 2 轮，props+flora 代理）。

独立于 props.js 的自报：栈桥在不在用由本脚本直接从 nodes.json 算（y0 <= 年 < y1），
再到页面里数场景里真实的船实例（round0/round1/galley 三个 InstancedMesh 的 count 与每个实例的位置），
逐座栈桥配对：每座在用栈桥 1 条船、船中心离栈桥中线 <= 栈桥半宽 + 船宽 + 2 像素、没有多余的船。
小艇 / 驳船（skiff / lighter）另算，不计入。
用法（仓库根目录）：python3 docs/cs/lookdev/r2/props/check_ships.py --years 20,40,60 --out docs/cs/lookdev/r2/props/numbers_ships.json
环境变量同 tools/cs/lookdev/render.py（LOOKDEV_CHROME / LOOKDEV_LIBS / LOOKDEV_PYLIB）。
"""
import argparse, functools, http.server, json, math, os, socketserver, sys, threading
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
if os.environ.get('LOOKDEV_PYLIB'):
    sys.path.insert(0, os.environ['LOOKDEV_PYLIB'])
from playwright.sync_api import sync_playwright  # noqa: E402

JS = """Y=>{window.__setYear(Y);const c=window.__ctx,M=new c.THREE.Matrix4(),V=new c.THREE.Vector3(),out=[];
 for(const o of c.scene.children){if(!o.isInstancedMesh||o.userData.mod!=='props')continue;const k=o.userData.kind;if(!['round0','round1','galley'].includes(k))continue;
  for(let i=0;i<o.count;i++){o.getMatrixAt(i,M);V.setFromMatrixPosition(M);const s=new c.THREE.Vector3().setFromMatrixScale(M).x;out.push({kind:k,x:V.x,z:V.z,s})}}
 return {ships:out,self:window.__propsCheck}}"""
BEAM = {'round0': 10, 'round1': 10, 'galley': 5.6 + 11}


def seg_dist(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dz * dz or 1
    t = max(0, min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / L2))
    return math.hypot(x - a[0] - t * dx, z - a[1] - t * dz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', default='60')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    W = json.load(open(os.path.join(ROOT, 'docs/living/nodes/nangang/nodes.json'), encoding='utf-8'))
    piers = [f for f in W['features'] if f['t'] == 'pier']
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(type('Q', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *x: None}), directory=os.path.join(ROOT, 'docs')))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ)
    if os.environ.get('LOOKDEV_LIBS'):
        env['LD_LIBRARY_PATH'] = os.environ['LOOKDEV_LIBS'] + ':' + env.get('LD_LIBRARY_PATH', '')
    launch = dict(args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'], env=env)
    if os.environ.get('LOOKDEV_CHROME'):
        launch['executable_path'] = os.environ['LOOKDEV_CHROME']
    res, ok_all = [], True
    with sync_playwright() as p:
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={'width': 1376, 'height': 768})
        pg.goto(f'http://127.0.0.1:{srv.server_address[1]}/living/nodes/nangang/3d.html?clean=1&still=1', wait_until='commit', timeout=60000)
        pg.wait_for_function('window.__ready', timeout=180000)
        for Y in [int(y) for y in a.years.split(',')]:
            live = [f for f in piers if f['y0'] <= Y and (f.get('y1') is None or f['y1'] > Y)]
            r = pg.evaluate(JS, Y)
            ships = r['ships']
            # 贪心配对：每条船配给离它最近、且在容差内的在用栈桥
            used, per = set(), []
            pairs = sorted(((seg_dist(s['x'], s['z'], f['g'][0], f['g'][1]), i, j) for i, s in enumerate(ships) for j, f in enumerate(live)))
            ship_of = {}
            for d, i, j in pairs:
                if i in used or j in ship_of:
                    continue
                f, s = live[j], ships[i]
                if d <= f['w'] / 2 + BEAM[s['kind']] * s['s'] + 2:
                    used.add(i); ship_of[j] = (i, round(d, 1))
            for j, f in enumerate(live):
                per.append({'harbor': f['harbor'], 'y0': f['y0'], 'a': f['g'][0], 'b': f['g'][1], 'ship': ships[ship_of[j][0]]['kind'] if j in ship_of else None,
                            'dist_to_pier': ship_of[j][1] if j in ship_of else None})
            ok = len(ships) == len(live) and len(ship_of) == len(live)
            ok_all &= ok
            row = {'year': Y, 'piers_in_use_nodes_json': len(live), 'ships_in_scene': len(ships), 'piers_with_ship': len(ship_of),
                   'unmatched_ships': len(ships) - len(used), 'ok': ok, 'self_report': {k: r['self'].get(k) for k in ('piers_in_use', 'ships_at_piers', 'fallbacks', 'shore_boats', 'cranes', 'clusters')}, 'per_pier': per}
            res.append(row)
            print(f"year {Y}: piers in use (nodes.json) {len(live)}  ships {len(ships)}  piers with a ship {len(ship_of)}  unmatched {row['unmatched_ships']}  {'OK' if ok else 'FAIL'}")
        b.close()
    if a.out:
        json.dump(res, open(a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
