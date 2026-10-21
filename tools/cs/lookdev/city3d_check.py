#!/usr/bin/env python3
"""全城 3D 验收（CS 线，2026-10-20）：docs/living/nodes/city/3d.html

  python3 tools/cs/lookdev/city3d_check.py shots  [--out DIR] [--shot all|1,2]   固定机位出图 + 每机位三角形/分块统计
  python3 tools/cs/lookdev/city3d_check.py fly    [--out DIR] [--steps 60]       沿一条穿城路线飞，逐帧记三角形（最大值要 ≤ 3 M）
  python3 tools/cs/lookdev/city3d_check.py load   [--out DIR] [--shot mid]       首屏：时间、请求数、字节（原始 + gzip 估计，Pages 走 gzip）
沙箱是软件渲染（swiftshader），帧率和毫秒只作相对参考，不代表 Mac。
"""
import argparse, base64, functools, gzip, http.server, json, os, socketserver, sys, threading, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = 'living/nodes/city/3d.html'
SHOTS = os.path.join(ROOT, 'docs', 'living', 'nodes', 'city', '3d', 'shots.json')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=os.path.join(ROOT, 'docs')))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{srv.server_address[1]}/'


def browser(p):
    return p.chromium.launch(executable_path=os.environ.get('LOOKDEV_CHROME', '/usr/bin/chromium'),
                             args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])


def open_page(p, url, size, log):
    b = browser(p)
    pg = b.new_page(viewport={'width': size[0], 'height': size[1]})
    pg.on('pageerror', lambda e: log.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: log.append(m.type + ': ' + m.text) if m.type in ('error', 'warning') else None)
    t0 = time.time()
    pg.goto(url, wait_until='commit', timeout=60000)
    pg.wait_for_function('window.__ready', timeout=300000)
    return b, pg, time.time() - t0


def cmd_shots(a):
    S = json.load(open(SHOTS, encoding='utf-8'))
    todo = S['shots'] if a.shot == 'all' else [s for s in S['shots'] if str(s['id']) in a.shot.split(',') or s['name'] in a.shot.split(',')]
    os.makedirs(a.out, exist_ok=True)
    log, rep = [], {'shots': []}
    with sync_playwright() as p:
        b, pg, ld = open_page(p, serve() + PAGE + '?clean=1&still=1&shot=' + str(todo[0]['id']) + a.param, S['size'], log)
        rep['load_s'] = round(ld, 1)
        for s in todo:
            t1 = time.time()
            pg.evaluate('s=>window.__applyShot(s)', s)
            data = pg.evaluate('()=>window.__still()')
            fn = os.path.join(a.out, f"city_shot{s['id']}.png")
            open(fn, 'wb').write(base64.b64decode(data.split(',', 1)[1]))
            st = pg.evaluate('()=>({tris: window.__trisTotal, per: window.__trisPer, cs: window.__chunkStats, mod: window.__modStats})')
            rep['shots'].append({'id': s['id'], 'name': s['name'], 'png': fn, 's': round(time.time() - t1, 1), **st})
            print(s['id'], s['name'], f"{st['tris']:,}", st['per'], 'win', (st['cs'] or {}).get('window'), f"{time.time() - t1:.1f}s")
        b.close()
    rep['console'] = log[:30]
    json.dump(rep, open(os.path.join(a.out, 'shots.json'), 'w'), ensure_ascii=False, indent=1)
    if log:
        print('console:', *log[:10], sep='\n  ')


def cmd_fly(a):
    """路线：南港港口低空 → 沿梅塞大道往东过古城 → 老城（竞技场）→ 金角湾 → 拉高到航拍 → 西北城墙外再落下。全城坐标。"""
    W = [(1700, 260, 4700, 1650, 0, 4250), (2300, 220, 4100, 2500, 0, 3800), (2800, 160, 3900, 3000, 0, 3740),
         (3200, 200, 4050, 3450, 0, 3850), (3700, 300, 3600, 3700, 0, 3300), (3300, 400, 3000, 3100, 0, 2600),
         (2600, 1600, 3800, 2600, 0, 2900), (2400, 4200, 6400, 2500, 0, 3300), (1200, 900, 3600, 900, 0, 2900),
         (700, 120, 3300, 650, 0, 2700), (500, 300, 2300, 700, 0, 1800)]
    os.makedirs(a.out, exist_ok=True)
    log, rows = [], []
    with sync_playwright() as p:
        b, pg, ld = open_page(p, serve() + PAGE + '?clean=1&still=1&shot=2' + a.param, (1376, 768), log)
        n = a.steps
        k0, k1 = (int(v) for v in a.range.split(':')) if a.range else (0, n)
        prev = json.load(open(os.path.join(a.out, 'fly.json')))['rows'] if a.range and k0 > 0 and os.path.exists(os.path.join(a.out, 'fly.json')) else []
        rows = [r for r in prev if r['k'] < k0]
        for k in range(k0, min(n, k1) + 1):
            u = k / n * (len(W) - 1); i = min(len(W) - 2, int(u)); f = u - i
            q = [W[i][m] * (1 - f) + W[i + 1][m] * f for m in range(6)]
            t1 = time.time()
            pg.evaluate('q=>window.__view(...q)', q)
            tris = pg.evaluate('()=>window.__frame()')
            cs = pg.evaluate('()=>({w: window.__chunkStats && window.__chunkStats.window, per: window.__trisPer, reb: window.__chunkStats && window.__chunkStats.rebuilds})')
            pg.evaluate('()=>window.__frame()')
            cs2 = pg.evaluate('()=>({per: window.__trisPer, all: window.__trisAll, cst: (()=>{const c=window.__chunkStats;return c})()})')
            row = {'k': k, 'cam': [round(v) for v in q], 'tris': tris, 'trisAllInScene': cs2['all'], 'window': cs['w'] and [cs['w']['i'], cs['w']['j']], 'rebuilds': cs['reb'], 'per': cs2['per'], 's': round(time.time() - t1, 2)}
            rows.append(row)
            if a.png and k % a.png == 0:
                data = pg.evaluate('()=>window.__still()')
                open(os.path.join(a.out, f'fly_{k:03d}.png'), 'wb').write(base64.b64decode(data.split(',', 1)[1]))
            print(k, row['cam'], f"{tris:,}", row['window'], row['s'], flush=True)
            json.dump({'rows': rows}, open(os.path.join(a.out, 'fly.json'), 'w'))
        b.close()
    mx = max(rows, key=lambda r: r['tris'])
    rep = {'frames': len(rows), 'tris_max': mx['tris'], 'tris_max_at': mx['cam'], 'tris_min': min(r['tris'] for r in rows),
           'rebuilds': rows[-1]['rebuilds'], 'budget': 3000000, 'pass': mx['tris'] <= 3000000, 'rows': rows, 'console': log[:30]}
    json.dump(rep, open(os.path.join(a.out, 'fly.json'), 'w'), ensure_ascii=False, indent=1)
    print('max', f"{mx['tris']:,}", mx['cam'], 'pass', rep['pass'])


def cmd_load(a):
    S = json.load(open(SHOTS, encoding='utf-8'))
    out = {}
    with sync_playwright() as p:
        for shot in a.shot.split(','):
            log, req = [], []
            b = browser(p)
            pg = b.new_page(viewport={'width': 1376, 'height': 768})
            pg.on('requestfinished', lambda r: req.append(r.url))
            pg.on('pageerror', lambda e: log.append(str(e)))
            t0 = time.time()
            pg.goto(serve() + PAGE + '?shot=' + shot, wait_until='commit', timeout=60000)
            pg.wait_for_function('window.__ready', timeout=300000)
            first = time.time() - t0
            info = pg.evaluate('()=>({first: window.__firstMs, cs: window.__chunkStats, tris: window.__trisTotal})')
            n0 = len(req)
            raw = gz = 0; per = {}
            for u in req:
                path = u.split('://', 1)[1].split('/', 1)[1].split('?')[0]
                fp = os.path.join(ROOT, 'docs', path)
                if not os.path.isfile(fp):
                    continue
                d = open(fp, 'rb').read(); g = len(gzip.compress(d, 6)) if not fp.endswith(('.png', '.jpg', '.bin')) else len(d)
                raw += len(d); gz += g
                key = 'chunks_full' if '/chunks/f_' in fp else 'chunks_low' if '/chunks/l_' in fp else 'three' if '/lib/three/' in fp else 'modules' if fp.endswith('.js') else 'base' if fp.endswith('base.json') else 'other'
                per.setdefault(key, [0, 0, 0]); per[key][0] += 1; per[key][1] += len(d); per[key][2] += g
            out[shot] = {'first_screen_s_sandbox': round(first, 1), 'firstMs_page': info['first'], 'requests': n0, 'raw_bytes': raw, 'gzip_bytes_est': gz,
                         'by_kind[n,raw,gzip]': per, 'tris': info['tris'], 'window': info['cs']['window'], 'errors': log[:10]}
            print(shot, json.dumps(out[shot], ensure_ascii=False))
            b.close()
    # 全部数据（所有块 + base）
    d3 = os.path.join(ROOT, 'docs', 'living', 'nodes', 'city', '3d')
    tot_raw = tot_gz = 0
    for dp, _, fs in os.walk(d3):
        for fn in fs:
            if fn.endswith('.json'):
                b_ = open(os.path.join(dp, fn), 'rb').read(); tot_raw += len(b_); tot_gz += len(gzip.compress(b_, 6))
    out['all_city3d_data'] = {'raw': tot_raw, 'gzip_est': tot_gz}
    json.dump(out, open(os.path.join(a.out, 'load.json'), 'w'), ensure_ascii=False, indent=1)
    print(out['all_city3d_data'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['shots', 'fly', 'load'])
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'cs', 'lookdev', 'city3d', 'out'))
    ap.add_argument('--shot', default='all')
    ap.add_argument('--steps', type=int, default=60)
    ap.add_argument('--png', type=int, default=0)
    ap.add_argument('--param', default='')
    ap.add_argument('--range', default='', help='k0:k1，分几次跑（沙箱单条命令 120 s 上限）')
    a = ap.parse_args()
    {'shots': cmd_shots, 'fly': cmd_fly, 'load': cmd_load}[a.cmd](a)


if __name__ == '__main__':
    main()
