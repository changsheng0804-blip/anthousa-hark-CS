"""街网图：把 nodes_net.json 里某一年活着的街段连成一张可寻路的图。
街段的端点常常落在别的街段中间（丁字口），所以先把每个端点投到 2.5 像素内的街段上、在那里切开，再按 0.5 像素吸附端点。——Hark（CS线）"""
import heapq, math, collections

def live(f, Y):
    return f.get('y0', 0) <= Y and (f.get('y1') is None or f['y1'] > Y)

class StreetGraph:
    def __init__(self, D, Y, snap=2.5):
        segs = []
        for f in D['features']:
            if f['t'] == 'street' and live(f, Y):
                g = f['g']; segs.append((g[0], g[1], g[2], g[3], f['k'], f['w']))
        self.segs = segs
        cell = 16; grid = collections.defaultdict(list)
        for i, (x1, y1, x2, y2, *_ ) in enumerate(segs):
            for gx in range(int(min(x1, x2) // cell) - 1, int(max(x1, x2) // cell) + 2):
                for gy in range(int(min(y1, y2) // cell) - 1, int(max(y1, y2) // cell) + 2):
                    grid[(gx, gy)].append(i)
        self.grid, self.cell = grid, cell
        cuts = collections.defaultdict(set)
        for i, (x1, y1, x2, y2, *_ ) in enumerate(segs):
            for (px, py) in ((x1, y1), (x2, y2)):
                for j in set(grid[(int(px // cell), int(py // cell))]):
                    if j == i: continue
                    t, d, _, _ = self._proj(j, px, py)
                    if d <= snap and 0.02 < t < 0.98: cuts[j].add(round(t, 4))
        # 十字口：两段互相穿过、谁的端点都不在对方身上，也要切开
        for cellsegs in grid.values():
            for ii in range(len(cellsegs)):
                for jj in range(ii + 1, len(cellsegs)):
                    i, j = cellsegs[ii], cellsegs[jj]
                    if i == j: continue
                    r = self._cross(i, j)
                    if r: cuts[i].add(round(r[0], 4)); cuts[j].add(round(r[1], 4))
        key = lambda x, y: (round(x * 2), round(y * 2))
        self.adj = collections.defaultdict(dict); self.pos = {}; self.kind = {}
        for i, (x1, y1, x2, y2, k, w) in enumerate(segs):
            ts = [0.0] + sorted(cuts[i]) + [1.0]
            pts = [(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t) for t in ts]
            for a, b in zip(pts, pts[1:]):
                A, B = key(*a), key(*b)
                if A == B: continue
                L = math.dist(a, b)
                self.pos[A] = a; self.pos[B] = b
                self.adj[A][B] = min(L, self.adj[A].get(B, 1e9)); self.adj[B][A] = self.adj[A][B]
                self.kind[(A, B)] = self.kind[(B, A)] = (k, w)
        # 端点挨得很近（< snap）但没连上的，补一条短边
        ng = collections.defaultdict(list)
        for n, p in self.pos.items(): ng[(int(p[0] // 4), int(p[1] // 4))].append(n)
        for n, p in self.pos.items():
            if len(self.adj[n]) > 1: continue
            gx, gy = int(p[0] // 4), int(p[1] // 4)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for m in ng[(gx + dx, gy + dy)]:
                        if m != n and m not in self.adj[n]:
                            L = math.dist(p, self.pos[m])
                            if L <= snap:
                                self.adj[n][m] = self.adj[m][n] = L
                                self.kind[(n, m)] = self.kind[(m, n)] = ('s', 4)

    def _cross(self, i, j):
        x1, y1, x2, y2, *_ = self.segs[i]; x3, y3, x4, y4, *_ = self.segs[j]
        d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
        if abs(d) < 1e-9: return None
        t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
        u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
        if 0.001 < t < 0.999 and 0.001 < u < 0.999: return (t, u)
        return None

    def _proj(self, j, px, py):
        x1, y1, x2, y2, *_ = self.segs[j]
        dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy or 1
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
        qx, qy = x1 + dx * t, y1 + dy * t
        return t, math.hypot(px - qx, py - qy), qx, qy

    def nearest(self, px, py, rad=90):
        """离 (px,py) 最近的街面点，以及它所在小段的两个图节点。"""
        best = None
        for (A, nb) in self._near_nodes(px, py, rad):
            for B in nb:
                a, b = self.pos[A], self.pos[B]
                dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy or 1
                t = max(0, min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / L2))
                q = (a[0] + dx * t, a[1] + dy * t); d = math.dist(q, (px, py))
                if best is None or d < best[0]: best = (d, q, A, B)
        return best

    def _near_nodes(self, px, py, rad):
        for n, p in self.pos.items():
            if abs(p[0] - px) < rad and abs(p[1] - py) < rad: yield n, self.adj[n]

    def route(self, a, b):
        """从街面点 a 走到街面点 b 的折线（像素）。"""
        na, nb = self.nearest(*a), self.nearest(*b)
        if not na or not nb: return None
        src = {na[2]: math.dist(na[1], self.pos[na[2]]), na[3]: math.dist(na[1], self.pos[na[3]])}
        dst = {nb[2]: math.dist(nb[1], self.pos[nb[2]]), nb[3]: math.dist(nb[1], self.pos[nb[3]])}
        dist = dict(src); prev = {}; pq = [(d, n) for n, d in src.items()]; heapq.heapify(pq); done = set(); best = (1e18, None)
        while pq:
            d, u = heapq.heappop(pq)
            if u in done: continue
            done.add(u)
            if u in dst and d + dst[u] < best[0]: best = (d + dst[u], u)
            if d > best[0]: break
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
        if best[1] is None: return None
        path = []; u = best[1]
        while u is not None: path.append(self.pos[u]); u = prev.get(u)
        path.reverse()
        pts = [a, na[1]] + path + [nb[1], b]
        out = []
        for p in pts:
            p = (round(p[0], 1), round(p[1], 1))
            if not out or math.dist(out[-1], p) > 0.3: out.append(p)
        return out

def plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
