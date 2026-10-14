"""立面房子的前后次序：全城一次拓扑排序，写回 vec/*.json 每栋房的 h[2]（页面只按 h[2] 升序画，运行时零开销）。
原来 h[2] = 脚印最南端 y（单键 Y 排序）。长条地标（水道、柱廊、城墙段）、凹口里的小房、贴着大宅的邻居会被盖错。
现在：两栋房的立面贴图在屏幕上可能重叠、且年份有交集时，用脚印在共同 x 范围内谁更靠南来定谁在前，建一条边；
全城 Kahn 拓扑排序，同层按原 y 键先后；遇到环（几何本身互相穿插）就从环里挑 y 键最小的先画。
用法：python3 zsort.py [vec 目录] [--check]   --check 只数错序对，不写。——Hark（CS线）"""
import json, os, sys, glob, heapq, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
VD = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'docs', 'living', 'tiles', 'vec'))

def foot(sh):
    """vec 的 h[3] 是影子：前 4 点是脚印，后 4 点是脚印平移。地标的影子是脚印缩到 0.6 再平移 (3.0,1.8)，这里放回原大。"""
    P = [(sh[i], sh[i + 1]) for i in range(0, 8, 2)]
    if len(sh) >= 16:
        Q = [(sh[i], sh[i + 1]) for i in range(8, 16, 2)]
        if all(abs(q[0] - p[0] - 3.0) < 0.15 and abs(q[1] - p[1] - 1.8) < 0.15 for p, q in zip(P, Q)):
            cx = sum(p[0] for p in P) / 4; cy = sum(p[1] for p in P) / 4
            P = [(cx + (x - cx) / 0.6, cy + (y - cy) / 0.6) for x, y in P]
    return P

def span(P, x):
    """凸多边形在竖线 x 上的 [ymin, ymax]；不相交返回 None"""
    ys = []
    for i in range(len(P)):
        (x0, y0), (x1, y1) = P[i], P[(i + 1) % len(P)]
        if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
            ys.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
        elif x0 == x1 == x: ys += [y0, y1]
    return (min(ys), max(ys)) if ys else None

def front(A, B):
    """B 在 A 前面（更靠南、该后画）→ 1；A 在 B 前 → -1；分不出（左右并排）→ 0"""
    ax0, ax1 = min(p[0] for p in A), max(p[0] for p in A); bx0, bx1 = min(p[0] for p in B), max(p[0] for p in B)
    lo, hi = max(ax0, bx0), min(ax1, bx1)
    if hi - lo < 0.4: return 0
    vb = va = 0
    for k in range(5):
        x = lo + (hi - lo) * (k + 0.5) / 5; sa, sb = span(A, x), span(B, x)
        if not sa or not sb: continue
        if sb[0] >= sa[1] - 0.6: vb += 1
        elif sa[0] >= sb[1] - 0.6: va += 1
        else: vb += (sb[0] + sb[1]) > (sa[0] + sa[1]); va += (sb[0] + sb[1]) < (sa[0] + sa[1])
    return 1 if vb > va else -1 if va > vb else 0

def load(vd):
    H = []; files = {}
    for f in sorted(glob.glob(os.path.join(vd, '*.json'))):
        d = json.load(open(f)); files[f] = d
        for i, h in enumerate(d.get('h', [])):
            sh = h[3]
            if len(sh) < 8: continue
            xs = sh[0::2] + [c for q in h[4] for c in q[1][0::2]]; ys = sh[1::2] + [c for q in h[4] for c in q[1][1::2]]
            ay = max(sh[1::2]); y0 = min(ys); y0 -= 0.35 * (ay - y0)          # 倾斜时立面最多再拉长约三成
            H.append(dict(f=f, i=i, b=h[0], e=h[1], key=h[2], fp=foot(sh), box=(min(xs) - 1, y0 - 1, max(xs) + 1, max(ys) + 1)))
    return H, files

def edges(H):
    G = 24; grid = defaultdict(list)
    for n, h in enumerate(H):
        x0, y0, x1, y1 = h['box']
        for gx in range(int(x0 // G), int(x1 // G) + 1):
            for gy in range(int(y0 // G), int(y1 // G) + 1): grid[gx, gy].append(n)
    E = set()
    for cell in grid.values():
        for a in range(len(cell)):
            for b in range(a + 1, len(cell)):
                i, j = cell[a], cell[b]
                if (i, j) in E or (j, i) in E: continue
                A, B = H[i], H[j]
                if A['b'] >= B['e'] or B['b'] >= A['e']: continue
                p, q = A['box'], B['box']
                if p[0] >= q[2] or q[0] >= p[2] or p[1] >= q[3] or q[1] >= p[3]: continue
                s = front(A['fp'], B['fp'])
                if s > 0: E.add((i, j))
                elif s < 0: E.add((j, i))
    return E

def inversions(H, E, key):
    return sum(1 for i, j in E if key(H[i]) >= key(H[j]))

def topo(H, E):
    out = defaultdict(list); indeg = [0] * len(H)
    for i, j in E: out[i].append(j); indeg[j] += 1
    ready = [(H[n]['key'], n) for n in range(len(H)) if indeg[n] == 0]; heapq.heapify(ready)
    alive = sorted(range(len(H)), key=lambda n: H[n]['key']); ap = 0
    done = [False] * len(H); rank = [0] * len(H); r = 0; cyc = 0
    while r < len(H):
        if ready:
            _, n = heapq.heappop(ready)
            if done[n]: continue
        else:   # 环：剩下的里挑 y 键最小的先画
            while done[alive[ap]]: ap += 1
            n = alive[ap]; cyc += 1
        done[n] = True; rank[n] = r; r += 1
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0 and not done[m]: heapq.heappush(ready, (H[m]['key'], m))
    return rank, cyc

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; vd = args[0] if args else VD
    H, files = load(vd); E = edges(H)
    before = inversions(H, E, lambda h: h['key'])
    rank, cyc = topo(H, E)
    for n, h in enumerate(H): h['rank'] = rank[n]
    after = inversions(H, E, lambda h: h['rank'])
    print(json.dumps(dict(houses=len(H), overlap_pairs=len(E), wrong_before=before, wrong_after=after, cycles_broken=cyc), ensure_ascii=False))
    if '--check' in sys.argv: sys.exit(0)
    for n, h in enumerate(H): files[h['f']]['h'][h['i']][2] = rank[n]
    for f, d in files.items():
        d['h'].sort(key=lambda x: x[2]); open(f, 'wb').write(json.dumps(d, separators=(',', ':')).encode())
