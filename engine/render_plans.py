"""Architectural plans drawn inside a structure's footprint, by motif (PR-B1).

Pure rendering: reads the footprint, never changes it. Plans are drawn in the
footprint's own frame (long axis u, short axis v) so they follow its orientation.
"""
import math
from shapely.geometry import Polygon

INK = "#3b2a1a"
PAPER = "#f3e7c9"


def frame(g):
    """Centre, unit long axis u, unit short axis v, long and short extent of a polygon.

    The axis follows the footprint's longest edge (not its minimum-area rectangle,
    which turns cruciform plans 45 degrees)."""
    c = list(g.exterior.coords)
    best, u = 0, (1.0, 0.0)
    for (x0, y0), (x1, y1) in zip(c, c[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        if d > best + 1e-6:
            best, u = d, ((x1 - x0) / d, (y1 - y0) / d)
    v = (-u[1], u[0])
    pa = [x * u[0] + y * u[1] for x, y in c]
    pb = [x * v[0] + y * v[1] for x, y in c]
    L, S = max(pa) - min(pa), max(pb) - min(pb)
    if L < S:
        u, v, L, S, pa, pb = v, (-v[1], v[0]), S, L, pb, [-q for q in pa]
    ma, mb = (max(pa) + min(pa)) / 2, (max(pb) + min(pb)) / 2
    cx, cy = ma * u[0] + mb * v[0], ma * u[1] + mb * v[1]
    return (cx, cy), u, v, L, S


def _p(F, a, b):
    """Point at a (along u) and b (along v), both in footprint units from the centre."""
    (cx, cy), u, v, L, S = F
    return cx + a * u[0] + b * v[0], cy + a * u[1] + b * v[1]


def _poly(F, pts, **kw):
    return _el("polygon", points=" ".join(f"{x:.2f},{y:.2f}" for x, y in (_p(F, a, b) for a, b in pts)), **kw)


def _line(F, a1, b1, a2, b2, **kw):
    x1, y1 = _p(F, a1, b1)
    x2, y2 = _p(F, a2, b2)
    return _el("line", x1=f"{x1:.2f}", y1=f"{y1:.2f}", x2=f"{x2:.2f}", y2=f"{y2:.2f}", **kw)


def _circle(F, a, b, r, **kw):
    x, y = _p(F, a, b)
    return _el("circle", cx=f"{x:.2f}", cy=f"{y:.2f}", r=f"{max(r, 0.15):.2f}", **kw)


def _el(tag, **kw):
    return "<" + tag + " " + " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items()) + "/>"


THIN = dict(fill="none", stroke=INK, stroke_width="0.25")
HAIR = dict(fill="none", stroke=INK, stroke_width="0.15", stroke_opacity="0.8")


def basilica(F):
    _, _, _, L, S = F
    n = S * 0.2
    out = [_line(F, -L * 0.42, -n, L * 0.30, -n, **HAIR), _line(F, -L * 0.42, n, L * 0.30, n, **HAIR)]
    k = max(3, int(L / 3))
    for i in range(k + 1):  # arcade columns
        a = -L * 0.42 + i * (L * 0.72) / k
        out += [_circle(F, a, -n, 0.18, fill=INK), _circle(F, a, n, 0.18, fill=INK)]
    r = S * 0.28  # apse at the east end (+u)
    pts = [(L * 0.32 + r * math.sin(t), r * math.cos(t)) for t in [i * math.pi / 12 for i in range(13)]]
    out.append(_poly(F, pts, fill=PAPER, fill_opacity="0.6", stroke=INK, stroke_width="0.25"))
    return out


def cross_in_square(F):
    _, _, _, L, S = F
    a, b = L * 0.46, S * 0.46
    w = min(L, S) * 0.18
    cross = [(-a, -w), (-w, -w), (-w, -b), (w, -b), (w, -w), (a, -w), (a, w), (w, w), (w, b), (-w, b), (-w, w), (-a, w)]
    out = [_poly(F, cross, fill=PAPER, fill_opacity="0.55", stroke=INK, stroke_width="0.25")]
    d = min(L, S) * 0.17
    out.append(_circle(F, 0, 0, d, fill="none", stroke=INK, stroke_width="0.35"))
    out.append(_circle(F, 0, 0, d * 0.55, **HAIR))
    for sa in (-1, 1):
        for sb in (-1, 1):
            out.append(_circle(F, sa * L * 0.3, sb * S * 0.3, min(L, S) * 0.07, **HAIR))
    return out


def domed_basilica(F):
    _, _, _, L, S = F
    out = basilica(F)
    out.append(_circle(F, 0, 0, S * 0.4, fill="none", stroke=INK, stroke_width="0.4"))
    return out


def rotunda(F):
    _, _, _, L, S = F
    r = min(L, S) * 0.45
    return [_circle(F, 0, 0, r, fill=PAPER, fill_opacity="0.5", stroke=INK, stroke_width="0.3"),
            _circle(F, 0, 0, r * 0.25, **HAIR)]


def peristyle(F, g, court=False):
    _, _, _, L, S = F
    inset = min(L, S) * 0.14
    inner = g.buffer(-inset, join_style=2)
    out = []
    if inner.is_empty or inner.geom_type != "Polygon":
        return out
    ring = inner.exterior
    n = max(8, int(ring.length / 1.5))  # a column every ~18 m
    for i in range(n):
        p = ring.interpolate(i / n, normalized=True)
        out.append(_el("circle", cx=f"{p.x:.2f}", cy=f"{p.y:.2f}", r="0.2", fill=INK))
    out.append(_el("polygon", points=" ".join(f"{x:.2f},{y:.2f}" for x, y in ring.coords), **HAIR))
    if court:  # a palace: inner court and a throne hall on the axis
        core = g.buffer(-min(L, S) * 0.32, join_style=2)
        if not core.is_empty and core.geom_type == "Polygon":
            out.append(_el("polygon", points=" ".join(f"{x:.2f},{y:.2f}" for x, y in core.exterior.coords),
                           fill=PAPER, fill_opacity="0.7", stroke=INK, stroke_width="0.25"))
    return out


def hippodrome(F):
    _, _, _, L, S = F
    st = S * 0.18
    a, b = L / 2 - st, S / 2 - st
    # track: straight carceres end (-u), semicircular sphendone (+u)
    r = b
    pts = [(-a, -b), (a - r, -b)] + [(a - r + r * math.sin(t), -r * math.cos(t)) for t in [i * math.pi / 16 for i in range(17)]] + [(-a, b)]
    out = [_poly(F, pts, fill=PAPER, fill_opacity="0.8", stroke=INK, stroke_width="0.3")]
    sp = L * 0.3
    out.append(_line(F, -sp, 0, sp * 0.8, 0, stroke=INK, stroke_width="0.7"))  # spina
    for t in (-sp, sp * 0.8):
        out.append(_circle(F, t, 0, 0.45, fill=INK))  # metae
    out.append(_circle(F, -sp * 0.1, 0, 0.3, fill=PAPER, stroke=INK, stroke_width="0.2"))  # obelisk
    return out


def tower(F):
    _, _, _, L, S = F
    c = min(L, S) * 0.22
    out = []
    for sa in (-1, 1):
        for sb in (-1, 1):
            a, b = sa * (L / 2 - c / 2), sb * (S / 2 - c / 2)
            out.append(_poly(F, [(a - c / 2, b - c / 2), (a + c / 2, b - c / 2), (a + c / 2, b + c / 2), (a - c / 2, b + c / 2)],
                             fill=INK, fill_opacity="0.75"))
    return out


def gatehouse(F):
    _, _, _, L, S = F
    t, p = L * 0.34, L * 0.14
    out = []
    for s in (-1, 1):
        a0 = s * p
        a1 = s * (L / 2)
        out.append(_poly(F, [(a0, -S / 2), (a1, -S / 2), (a1, S / 2), (a0, S / 2)], fill=INK, fill_opacity="0.6"))
    out.append(_line(F, 0, -S / 2, 0, S / 2, stroke=PAPER, stroke_width="0.5"))
    return out


def column_monument(F):
    _, _, _, L, S = F
    r = min(L, S) * 0.25
    return [_circle(F, 0, 0, r, fill=PAPER, stroke=INK, stroke_width="0.3"), _circle(F, 0, 0, r * 0.35, fill=INK)]


def cistern(F):
    _, _, _, L, S = F
    out = []
    n, m = max(3, int(L / 3)), max(2, int(S / 3))
    for i in range(n):
        for j in range(m):
            out.append(_circle(F, -L / 2 + (i + 0.5) * L / n, -S / 2 + (j + 0.5) * S / m, 0.2, fill=PAPER))
    return out


def insula(F):
    _, _, _, L, S = F
    out = [_line(F, -L / 2, 0, L / 2, 0, **HAIR)]
    k = max(3, int(L / 4))
    for i in range(1, k):
        a = -L / 2 + i * L / k
        out.append(_line(F, a, -S / 2, a, S / 2, **HAIR))
    return out


def market_row(F):
    _, _, _, L, S = F
    out = [_line(F, -L / 2, S * 0.15, L / 2, S * 0.15, **HAIR)]
    k = max(4, int(L / 2.5))
    for i in range(k + 1):
        out.append(_circle(F, -L / 2 + i * L / k, S * 0.15, 0.18, fill=INK))
    return out


def courtyard_house(F, g):
    inner = g.buffer(-min(F[3], F[4]) * 0.3, join_style=2)
    if inner.is_empty or inner.geom_type != "Polygon":
        return []
    return [_el("polygon", points=" ".join(f"{x:.2f},{y:.2f}" for x, y in inner.exterior.coords), fill=PAPER, stroke=INK, stroke_width="0.15")]


def monastery(F, g):
    return courtyard_house(F, g) + [_circle(F, F[3] * 0.32, 0, min(F[3], F[4]) * 0.1, **THIN)]


def arcade(g):
    """Aqueduct bridge (exempt from motifs): piers along its long axis."""
    F = frame(g)
    _, _, _, L, S = F
    n = max(4, int(L / 1.5))  # a pier every ~18 m
    out = [_line(F, -L / 2, 0, L / 2, 0, stroke=INK, stroke_width="0.25")]
    for i in range(n + 1):
        a = -L / 2 + i * L / n
        out.append(_line(F, a, -S / 2, a, S / 2, stroke=INK, stroke_width="0.35"))
    return out


def plan(s, g, motif):
    """SVG elements for a structure's plan, or [] when its motif has no plan."""
    if g.geom_type != "Polygon" or g.area < 1:
        return []
    if s["type"] == "aqueduct_bridge":
        return arcade(g)
    F = frame(g)
    f = {"basilica": basilica, "cross_in_square": cross_in_square, "domed_basilica": domed_basilica,
         "rotunda": rotunda, "hippodrome": hippodrome, "tower": tower, "gatehouse": gatehouse,
         "column_monument": column_monument, "cistern": cistern, "insula": insula, "market_row": market_row}.get(motif)
    if f:
        return f(F)
    if motif == "peristyle":
        return peristyle(F, g, court=s["type"] == "palace")
    if motif == "courtyard_house":
        return courtyard_house(F, g)
    if motif == "monastery":
        return monastery(F, g)
    return []
