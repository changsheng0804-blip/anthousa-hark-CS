"""俯视对比图：左 = 现在的路和房（nodes.json），右 = 路网节点长出来的（nodes_net.json），同一年。
用法: python3 tools/cs/nodes/net_cmp.py nangang 60 [x0 y0 x1 y1] → tools/cs/nodes/out/<q>_net_<Y>.jpg"""
import json, os, sys
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
q = sys.argv[1]; Y = int(sys.argv[2]); win = [int(v) for v in sys.argv[3:7]] if len(sys.argv) > 6 else None
O = os.path.join(ROOT, 'docs', 'living', 'nodes', q)
def live(f): return f['y0'] <= Y and (f.get('y1') is None or f['y1'] > Y)
def draw(D, sc):
    W, H = D['W'], D['H']; im = np.full((int(H * sc), int(W * sc), 3), (190, 205, 214), np.uint8)
    P = lambda pts: np.int32(np.array(pts) * sc)
    for f in D['features']:
        if f['t'] == 'land':
            for g in f['g']: cv2.fillPoly(im, [P(g[0])], (196, 222, 236))
    for f in D['features']:
        if f['t'] == 'water' and f.get('k') == 'harbor' and live(f):
            for g in f['g']: cv2.fillPoly(im, [P(g[0])], (190, 205, 214))
    for f in D['features']:
        if f['t'] == 'landmark' and live(f): cv2.fillPoly(im, [P(f['g'])], (150, 170, 196))
    for f in D['features']:
        if f['t'] == 'street' and live(f):
            g = f['g']; cv2.line(im, tuple(P([g[0], g[1]])), tuple(P([g[2], g[3]])), (236, 244, 248) if f['k'] != 'm' else (220, 236, 246), max(1, int(f['w'] * sc)), cv2.LINE_AA)
    col = {'casa': (86, 110, 186), 'row': (60, 84, 170), 'insula': (70, 70, 140), 'hall': (90, 120, 140), 'std': (120, 120, 170), 'flat': (130, 150, 190)}
    for f in D['features']:
        if f['t'] == 'house' and live(f):
            p = f['p']; cv2.fillPoly(im, [P([[p[i], p[i + 1]] for i in range(0, 8, 2)])], col.get(f.get('ty'), (86, 110, 186)))
    for a in D.get('net', {}).get('anchors', []):
        cv2.circle(im, (int(a[0] * sc), int(a[1] * sc)), 4, {'gate': (40, 40, 200), 'lm': (40, 150, 40), 'pier': (160, 60, 20)}[a[2]], -1)
    if win: im = im[int(win[1] * sc):int(win[3] * sc), int(win[0] * sc):int(win[2] * sc)]
    return im
A = json.load(open(os.path.join(O, 'nodes.json'))); B = json.load(open(os.path.join(O, 'nodes_net.json')))
sc = 0.45 if not win else min(1.6, 900 / (win[2] - win[0]))
a, b = draw(A, sc), draw(B, sc)
out = np.concatenate([a, np.full((a.shape[0], 12, 3), 255, np.uint8), b], 1)
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
fn = os.path.join(HERE, 'out', '%s_net_%d%s.jpg' % (q, Y, '_win' if win else ''))
cv2.imwrite(fn, out, [cv2.IMWRITE_JPEG_QUALITY, 85]); print(fn)
