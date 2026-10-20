#!/usr/bin/env python3
"""南港 lookdev 机位渲染器（CS 线，2026-10-20）。

打开 docs/living/nodes/nangang/3d.html?clean=1，按 shots.json 的固定机位逐个截图。
只用来看「样子」：沙箱是软件渲染，帧率不算数（帧率一律在主人的 Mac 上测）。

用法（仓库根目录）：
  python3 tools/cs/lookdev/render.py                     # 全部机位 → docs/cs/lookdev/out/shotN.png
  python3 tools/cs/lookdev/render.py --shot 2 --out /tmp/x
  python3 tools/cs/lookdev/render.py --page docs/living/nodes/nangang/3d.html --settle 4

环境变量（可选）：
  LOOKDEV_CHROME     chrome / chrome-headless-shell 可执行文件；不给就用 playwright 自带的 chromium
  LOOKDEV_LIBS       额外的 .so 目录（冒号分隔），沙箱里 chrome 缺库时用
  LOOKDEV_PYLIB      playwright 不在 sys.path 时，从这里 import
"""
import argparse, base64, functools, http.server, json, os, socketserver, sys, threading, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if os.environ.get('LOOKDEV_PYLIB'):
    sys.path.insert(0, os.environ['LOOKDEV_PYLIB'])
from playwright.sync_api import sync_playwright  # noqa: E402


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{srv.server_address[1]}/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default='docs/living/nodes/nangang/3d.html')
    ap.add_argument('--shots', default=None, help='默认：页面同目录的 shots.json')
    ap.add_argument('--shot', default='all')
    ap.add_argument('--out', default='docs/cs/lookdev/out')
    ap.add_argument('--settle', type=float, default=1.0, help='每个机位等几秒再截（软件渲染要慢一点）')
    ap.add_argument('--param', default='', help='附加 URL 参数，例如 flag=xxx&people=1')
    a = ap.parse_args()

    page = os.path.join(ROOT, a.page)
    shots_path = a.shots or os.path.join(os.path.dirname(page), 'shots.json')
    S = json.load(open(shots_path, encoding='utf-8'))
    W, H = S.get('size', [1376, 768])
    todo = S['shots'] if a.shot == 'all' else [s for s in S['shots'] if str(s['id']) == a.shot or s['name'] == a.shot]
    out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    os.makedirs(out, exist_ok=True)

    docs = os.path.join(ROOT, 'docs')
    url = serve(docs) + os.path.relpath(page, docs).replace(os.sep, '/') + '?clean=1&still=1' + ('&' + a.param if a.param else '')
    env = dict(os.environ)
    if os.environ.get('LOOKDEV_LIBS'):
        env['LD_LIBRARY_PATH'] = os.environ['LOOKDEV_LIBS'] + ':' + env.get('LD_LIBRARY_PATH', '')
    launch = dict(args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'], env=env)
    if os.environ.get('LOOKDEV_CHROME'):
        launch['executable_path'] = os.environ['LOOKDEV_CHROME']

    report = {'page': a.page, 'url_params': '?clean=1&still=1' + ('&' + a.param if a.param else ''), 'shots': []}
    with sync_playwright() as p:
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={'width': W, 'height': H})
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.type + ': ' + m.text) if m.type in ('error', 'warning') else None)
        t0 = time.time()
        pg.goto(url, wait_until='commit', timeout=60000)
        pg.wait_for_function('window.__ready', timeout=180000)
        report['load_s'] = round(time.time() - t0, 1)
        report['build_ms'] = pg.evaluate('window.__buildMs')
        for s in todo:
            pg.evaluate('s=>window.__applyShot(s)', s)
            time.sleep(a.settle)
            fn = os.path.join(out, f"shot{s['id']}.png")
            t1 = time.time()
            data = pg.evaluate('()=>window.__still()')  # 画一帧，直接从 canvas 取 PNG
            open(fn, 'wb').write(base64.b64decode(data.split(',', 1)[1]))
            print(f"  frame {time.time() - t1:.1f}s (软件渲染，不代表帧率)")
            report['shots'].append({'id': s['id'], 'name': s['name'], 'png': os.path.relpath(fn, ROOT)})
            print('shot', s['id'], s['name'], '->', os.path.relpath(fn, ROOT))
        report['console'] = errs[:20]
        b.close()
    json.dump(report, open(os.path.join(out, 'render.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if errs:
        print('console:', *errs[:8], sep='\n  ')


if __name__ == '__main__':
    main()
