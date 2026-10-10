"""Deterministic terrain for Anthousa: a peninsula between a long inlet (the Horn),
an inland sea (south) and a strait (east). Everything derives from SEED."""
import math
from functools import lru_cache
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

W, H = 1200, 800
SEED = 330


def _hash(ix, iy, s):
    h = (ix * 374761393 + iy * 668265263 + s * 2147483647) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def vnoise(x, y, s=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, s), _hash(ix + 1, iy, s)
    c, d = _hash(ix, iy + 1, s), _hash(ix + 1, iy + 1, s)
    return (a + (b - a) * ux) * (1 - uy) + (c + (d - c) * ux) * uy


def fbm(x, y, s=0, octaves=5):
    v, amp, f, tot = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        v += amp * vnoise(x * f, y * f, s + o * 17)
        tot += amp
        amp *= 0.5
        f *= 2.0
    return v / tot - 0.5


def _rough(poly, amp, scale, s):
    """Displace each boundary vertex along its normal with fractal noise."""
    ring = list(LineString(poly.exterior.coords).segmentize(3).coords)[:-1]
    n = len(ring)
    out = []
    for i, (x, y) in enumerate(ring):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        d = amp * fbm(x / scale, y / scale, s)
        out.append((x + nx * d, y + ny * d))
    p = Polygon(out).buffer(0)
    return p.buffer(1.5).buffer(-1.5)


@lru_cache(maxsize=1)
def land():
    west = Polygon([(-20, -20), (905, -20), (912, 90), (930, 200), (946, 300), (958, 360),
                    (975, 420), (955, 470), (905, 530), (820, 568), (700, 590), (560, 600),
                    (400, 612), (240, 622), (-20, 640)])
    horn = Polygon([(1000, 262), (930, 248), (860, 236), (790, 222), (720, 214), (650, 214),
                    (600, 222), (565, 236), (552, 246), (566, 252), (610, 252), (660, 256),
                    (720, 262), (790, 276), (860, 292), (930, 306), (1000, 318)])
    east = Polygon([(1035, -20), (1220, -20), (1220, 650), (1150, 662), (1085, 640), (1060, 590),
                    (1050, 520), (1042, 430), (1030, 330), (1040, 220), (1032, 100)])
    isl = [Point(1010, 735).buffer(16), Point(1068, 760).buffer(11), Point(1115, 722).buffer(7)]
    west = _rough(west, 70, 55, SEED)
    horn = _rough(horn, 22, 30, SEED + 1).buffer(3)
    east = _rough(east, 70, 55, SEED + 2)
    isl = [_rough(i, 14, 14, SEED + 3 + k) for k, i in enumerate(isl)]
    L = unary_union([west.difference(horn), east] + isl)
    return L.intersection(Polygon([(0, 0), (W, 0), (W, H), (0, H)]))


HILLS = [  # (x, y, height, radius)  -- the seven hills of the peninsula + others
    (905, 400, 34, 45), (835, 360, 40, 55), (760, 330, 44, 55), (690, 320, 48, 60),
    (620, 330, 52, 60), (720, 470, 46, 70), (560, 430, 58, 80),
    (760, 120, 50, 90), (880, 60, 45, 70), (1120, 300, 60, 120), (1110, 520, 40, 80),
    (250, 300, 60, 160), (420, 160, 55, 130),
]


def elevation(x, y):
    e = sum(h * math.exp(-((x - hx) ** 2 + (y - hy) ** 2) / (2 * r * r)) for hx, hy, h, r in HILLS)
    return e + 14 * fbm(x / 60, y / 60, SEED + 9) + 6 * fbm(x / 18, y / 18, SEED + 10)


def is_land(x, y):
    return land().contains(Point(x, y))
