#!/usr/bin/env python3
"""只换 vec 里的史诗分期行（id 'epic:…'），不重烤栅格：epic_stage.json 改了以后跑这个，比 tile_bake 全量（Mac 上约 20 分钟）快。
放法与 tile_bake 第 167 行起那段相同（按影子前四点中心落瓦片），换完再跑 zsort.py 重排立面次序。
  python3 tools/cs/factory/epic_vec.py
——Hark（CS线）"""
import json, os, glob, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T = os.path.join(ROOT, 'docs', 'living', 'tiles'); V = os.path.join(T, 'vec'); M = json.load(open(os.path.join(T, 'meta.json'))); TP = M['tile_px']
D = json.load(open(os.path.join(T, 'epic_stage.json'))); add = {}
for r in D['rows']:
    sh = r['shadow']; cx = sum(sh[0:8:2]) / 4; cy = sum(sh[1:8:2]) / 4
    add.setdefault(f'{int(cx // TP)}_{int(cy // TP)}', []).append([r['built'], r['end'], r['by'], sh, r['parts'], r['id']])
rm = put = 0
for f in sorted(set(glob.glob(os.path.join(V, '*.json'))) | {os.path.join(V, k + '.json') for k in add}):
    k = os.path.basename(f)[:-5]; v = json.load(open(f)) if os.path.exists(f) else {'s': [], 'h': []}
    n0 = len(v['h']); v['h'] = [h for h in v['h'] if not str(h[5]).startswith('epic:')]; rm += n0 - len(v['h'])
    v['h'] += add.get(k, []); put += len(add.get(k, []))
    if n0 == len(v['h']) and not add.get(k) and n0 == len(v['h']): pass
    v['h'].sort(key=lambda x: x[2]); open(f, 'w').write(json.dumps(v, separators=(',', ':')))
subprocess.run([sys.executable, os.path.join(HERE, 'zsort.py'), V], check=True)
print('epic 行：拿掉', rm, '放进', put)
