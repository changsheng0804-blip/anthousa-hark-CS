"""Render the static engraved-style base map (sea ripples, coast, hachured hills)."""
import math, random, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shapely.geometry import Point
from terrain import land, elevation, W, H, SEED

INK = "#3b2a1a"


def path_of(geom, prec=1):
    polys = geom.geoms if hasattr(geom, "geoms") else [geom]
    d = []
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            d.append("M" + "L".join(f"{x:.{prec}f},{y:.{prec}f}" for x, y in pts) + "Z")
    return "".join(d)


def lines_of(geom, prec=1):
    gs = geom.geoms if hasattr(geom, "geoms") else [geom]
    out = []
    for g in gs:
        if g.geom_type == "Polygon":
            out += [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
        elif g.geom_type in ("LineString", "LinearRing"):
            out.append(list(g.coords))
        elif hasattr(g, "geoms"):
            for h in g.geoms:
                out += [list(h.coords)] if h.geom_type != "Polygon" else [list(h.exterior.coords)]
    return "".join("M" + "L".join(f"{x:.{prec}f},{y:.{prec}f}" for x, y in pts) for pts in out)


def hachures(L):
    rnd = random.Random(SEED)
    segs = []
    step = 7
    for gy in range(0, H, step):
        for gx in range(0, W, step):
            x, y = gx + rnd.uniform(-2.5, 2.5), gy + rnd.uniform(-2.5, 2.5)
            if not L.contains(Point(x, y)):
                continue
            ex = elevation(x + 2, y) - elevation(x - 2, y)
            ey = elevation(x, y + 2) - elevation(x, y - 2)
            g = math.hypot(ex, ey) / 4
            if g < 0.45:
                continue
            ln = min(6.5, 2 + g * 3.2)
            ux, uy = ex / (g * 4), ey / (g * 4)
            # light from north-west: south-east facing slopes darker
            shade = 0.35 + 0.6 * max(0, (ux * 0.7 + uy * 0.7))
            segs.append((x - ux * ln / 2, y - uy * ln / 2, x + ux * ln / 2, y + uy * ln / 2, shade))
    groups = {}
    for x0, y0, x1, y1, s in segs:
        k = round(s, 1)
        groups.setdefault(k, []).append(f"M{x0:.1f},{y0:.1f}L{x1:.1f},{y1:.1f}")
    return "".join(f'<path d="{"".join(v)}" stroke="{INK}" stroke-opacity="{k:.2f}" stroke-width="0.9" fill="none"/>'
                   for k, v in sorted(groups.items()))


def compass(cx, cy, r):
    pts = []
    for i in range(16):
        a = math.pi / 8 * i - math.pi / 2
        rr = r if i % 4 == 0 else (r * 0.55 if i % 2 == 0 else r * 0.32)
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
        a2 = a + math.pi / 16
        pts.append(f"{cx + r * 0.12 * math.cos(a2):.1f},{cy + r * 0.12 * math.sin(a2):.1f}")
    return (f'<g class="compass"><circle cx="{cx}" cy="{cy}" r="{r*1.08:.1f}" fill="none" stroke="{INK}" stroke-width="0.8"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r*0.95:.1f}" fill="none" stroke="{INK}" stroke-width="0.4"/>'
            f'<polygon points="{" ".join(pts)}" fill="#e9dcc0" stroke="{INK}" stroke-width="0.8"/>'
            f'<text x="{cx}" y="{cy - r*1.2:.1f}" text-anchor="middle" font-size="13" fill="{INK}" font-family="serif">N</text></g>')


def render():
    L = land()
    parts = [f'<rect width="{W}" height="{H}" fill="url(#sea)"/>']
    # water ripple lines
    for i, d in enumerate([5, 10, 16, 23, 31, 41]):
        ring = L.buffer(d, quad_segs=4).boundary
        parts.append(f'<path d="{lines_of(ring.simplify(0.6))}" stroke="#4a6a7a" stroke-opacity="{0.42 - i*0.06:.2f}" stroke-width="0.6" fill="none"/>')
    parts.append(f'<path d="{path_of(L.buffer(2.5))}" fill="#c9b48a" opacity="0.55"/>')
    parts.append(f'<path d="{path_of(L)}" fill="url(#paper)" stroke="{INK}" stroke-width="1.3"/>')
    parts.append(hachures(L))
    labels = [("MARE ANTHOUSIUM · 安托萨内海", 520, 700, 22, 0), ("CORNU · 金角湾", 500, 268, 11, 38),
              ("FRETUM · 海峡", 930, 230, 13, -48), ("PONTUS · 北海", 1085, 40, 12, -50),
              ("ORIENS · 东岸", 1120, 420, 14, 70), ("SYCAE · 北岸", 650, 200, 13, -20),
              ("THRACIA · 西陆", 200, 400, 18, 0)]
    for t, x, y, s, rot in labels:
        parts.append(f'<text x="{x}" y="{y}" transform="rotate({rot} {x} {y})" text-anchor="middle" font-size="{s}" '
                     f'font-style="italic" letter-spacing="3" fill="{INK}" fill-opacity="0.7" font-family="Georgia,serif">{t}</text>')
    parts.append(compass(95, 700, 42))
    defs = ('<defs><radialGradient id="sea" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#d9d3bf"/>'
            '<stop offset="1" stop-color="#b8b29b"/></radialGradient>'
            '<radialGradient id="paper" cx="45%" cy="40%" r="80%"><stop offset="0" stop-color="#f3e7c9"/>'
            '<stop offset="1" stop-color="#e2cfa3"/></radialGradient></defs>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{defs}{"".join(parts)}</svg>'


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/terrain.svg"
    open(out, "w").write(render())
    print("wrote", out)
