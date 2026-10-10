"""Render the city in a given year as an engraved map (SVG), plus the viewer data.

    python engine/render.py            # every era end-year + docs/data.json
"""
import json, math, os, re, sys, html
sys.path.insert(0, os.path.dirname(__file__))
from shapely.geometry import Polygon
from world import load, geom, standing, houses_standing, ROOT
from render_terrain import render as render_terrain, path_of, INK
from terrain import W, H
from grammar import motif_of, style_era, wonder_score
from render_plans import plan

DOCS = os.path.join(ROOT, "docs")
FILL = {"palace": "#d9b45a", "church": "#9c3b2e", "forum": "#efe6cf", "market": "#c98f4e", "fort": "#7d6a55",
        "granary": "#c2a16a", "cistern": "#6f8fa0", "temple": "#e8dcc0", "hippodrome": "#e6d6ad",
        "baths": "#8fb0b5", "monument": "#efe6cf", "column": "#efe6cf", "monastery": "#a8553f",
        "barracks": "#8a7660", "warehouse": "#b48a5a", "gate": "#5a4632", "harbor": "#7f9aa6",
        "aqueduct_bridge": "#d8c8a0"}


# viewer layers (#5): every drawn entity carries classes the viewer's lenses key on
KIND = {"aqueduct": "water", "aqueduct_bridge": "water", "cistern": "water", "baths": "water",
        "harbor": "food", "granary": "food", "warehouse": "food", "market": "food", "farmland": "food"}


def cls(s, *extra):
    c = ["s", "k-" + KIND.get(s["type"], "other"), "f-" + str(s.get("faction") or "none"), *extra]
    return f'class="{" ".join(c)}" data-id="{s["id"]}"'


def pts(coords):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)


def line_d(coords):
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in coords)


def towers(coords, every=9):
    out = []
    from shapely.geometry import LineString
    ln = LineString(coords)
    n = max(2, int(ln.length / every))
    for i in range(n + 1):
        p = ln.interpolate(i / n, normalized=True)
        out.append(f'<rect x="{p.x-1.1:.1f}" y="{p.y-1.1:.1f}" width="2.2" height="2.2" fill="{INK}"/>')
    return "".join(out)


def svg_for(w, year, terrain_inner, lang="en"):
    P = []
    ruins_h, fire_h, plague_h, old_h, new_h, cur_h = [], [], [], [], [], []
    for h in w["houses"]:
        if h["built"] > year:
            continue
        d = h.get("destroyed")
        if d is not None and d <= year:
            if year - d > 60:
                old_h.append(h)
            else:
                c = h.get("cause") or ""
                (fire_h if c == "fire" else plague_h if c.startswith("plague") else ruins_h).append(h)
        elif year - h["built"] < 10:
            new_h.append(h)
        else:
            cur_h.append(h)
    # long-vanished foundations: the palimpsest
    if old_h:
        P.append(f'<path class="old" d="{"".join("M"+pts(h["p"]).replace(" ","L")+"Z" for h in old_h)}" fill="none" stroke="#8a6a4a" stroke-opacity="0.25" stroke-width="0.15"/>')
    for grp, c in ((ruins_h, "rz clr"), (fire_h, "rz fire"), (plague_h, "rz plg")):
        if not grp:
            continue
        P.append(f'<path class="{c}" d="{"".join("M"+pts(h["p"]).replace(" ","L")+"Z" for h in grp)}" fill="#6b4a32" fill-opacity="0.12" stroke="#6b4a32" stroke-opacity="0.5" stroke-width="0.15" stroke-dasharray="0.4 0.4"/>')
    for s in w["structures"]:  # vanished structures leave traces
        if s["built"] > year or s.get("destroyed") is None or s["destroyed"] > year or s["type"] == "district":
            continue
        g = s["geom"]
        if g["type"] == "line":
            P.append(f'<path {cls(s, "gone")} d="{line_d(g["coords"])}" fill="none" stroke="#6b4a32" stroke-opacity="0.45" stroke-width="{1.6 if s["type"]=="wall" else 0.8}" stroke-dasharray="2 2"/>')
        elif g["type"] == "polygon":
            P.append(f'<polygon {cls(s, "gone")} points="{pts(g["coords"])}" fill="none" stroke="#6b4a32" stroke-opacity="0.5" stroke-width="0.8" stroke-dasharray="2 2"/>')
    live = standing(w, year)
    for s in [x for x in live if x["type"] == "farmland"]:  # fields: pale green with furrows along the long side
        g = geom(s); mr = g.minimum_rotated_rectangle; c = list(mr.exterior.coords)
        e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda q: math.dist(*q))
        ang = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        cx, cy = g.centroid.x, g.centroid.y; R = max(math.dist(*q) for q in [(c[0], c[2])]) / 2 + 1
        fur = "".join(f"M{-R:.1f},{k:.1f}H{R:.1f}" for k in [i * 1.6 - R for i in range(int(2 * R / 1.6) + 1)])
        cid = "clip-" + s["id"]
        P.append(f'<g {cls(s, "fld")}><clipPath id="{cid}"><polygon points="{pts(s["geom"]["coords"])}"/></clipPath>'
                 f'<polygon points="{pts(s["geom"]["coords"])}" fill="#c9cf94" fill-opacity="0.55" stroke="#8a8a52" stroke-width="0.3" stroke-dasharray="1 0.6"/>'
                 f'<path clip-path="url(#{cid})" transform="translate({cx:.1f},{cy:.1f}) rotate({ang:.1f})" d="{fur}" stroke="#8a8a52" stroke-opacity="0.45" stroke-width="0.25" fill="none"/></g>')
    for s in [x for x in live if x["type"] == "harbor"]:
        P.append(f'<polygon {cls(s, "fp")} points="{pts(s["geom"]["coords"])}" fill="#7f9aa6" fill-opacity="0.35" stroke="{INK}" stroke-width="0.8"/>')
    for s in [x for x in live if x["type"] == "aqueduct"]:
        c = s["geom"]["coords"]
        P.append(f'<g {cls(s)}><path d="{line_d(c)}" fill="none" stroke="{INK}" stroke-width="1.4"/>'
                 f'<path class="ri" d="{line_d(c)}" fill="none" stroke="#e8dcc0" stroke-width="0.7" stroke-dasharray="1.2 0.8"/></g>')
    for s in sorted([x for x in live if x["type"] == "road"], key=lambda r: -r.get("width", 4)):
        c, wd = s["geom"]["coords"], s.get("width", 4)
        P.append(f'<path {cls(s, "rd")} d="{line_d(c)}" fill="none" stroke="{INK}" stroke-width="{wd+0.6}" stroke-linecap="round" stroke-linejoin="round"/>')
    for s in sorted([x for x in live if x["type"] == "road"], key=lambda r: -r.get("width", 4)):
        c, wd = s["geom"]["coords"], s.get("width", 4)
        P.append(f'<path {cls(s, "rd", "ri")} d="{line_d(c)}" fill="none" stroke="#f1e6c8" stroke-width="{wd}" stroke-linecap="round" stroke-linejoin="round"/>')
    if cur_h:
        P.append(f'<path class="hs" d="{"".join("M"+pts(h["p"]).replace(" ","L")+"Z" for h in cur_h)}" fill="#b0603f" stroke="{INK}" stroke-width="0.12"/>')
    if new_h:
        P.append(f'<path class="hs new" d="{"".join("M"+pts(h["p"]).replace(" ","L")+"Z" for h in new_h)}" fill="#d9774a" stroke="{INK}" stroke-width="0.12"/>')
    for s in [x for x in live if x["geom"]["type"] == "polygon" and x["type"] not in ("district", "harbor", "farmland")]:
        f = FILL.get(s["type"], "#ccc")
        P.append(f'<g {cls(s)}><polygon class="fp" points="{pts(s["geom"]["coords"])}" fill="{f}" stroke="{INK}" stroke-width="0.5"/>')
        g = geom(s)
        P.extend(plan(s, g, motif_of(s)))
        if wonder_score(s) >= 4:  # wonders get a gilt edge
            P.append(f'<polygon points="{pts(s["geom"]["coords"])}" fill="none" stroke="#b8862b" stroke-width="0.35"/>')
        P.append('</g>')
    for s in [x for x in live if x["type"] in ("wall", "seawall")]:
        c = s["geom"]["coords"]
        P.append(f'<g {cls(s)}><path class="ri" d="{line_d(c)}" fill="none" stroke="{INK}" stroke-width="{1.5 if s["type"]=="wall" else 1}" stroke-linejoin="round"/>')
        if s["type"] == "wall":
            P.append(towers(c))
        P.append('</g>')
    for s in [x for x in live if x["geom"]["type"] == "point"]:
        x, y = s["geom"]["coords"]
        P.append(f'<circle {cls(s, "fp")} cx="{x}" cy="{y}" r="1.2" fill="#efe6cf" stroke="{INK}" stroke-width="0.5"/>')
    # labels
    for s in live:
        if not s.get("label"):
            continue
        g = geom(s)
        c = g.centroid if s["geom"]["type"] != "line" else g.interpolate(0.5, normalized=True)
        lx, ly = s.get("label_at", [c.x, c.y])
        la = I18N.get("label_at", {})
        lx, ly = la.get(lang, {}).get(s["id"], la.get("both", {}).get(s["id"], [lx, ly]))
        lab = I18N["labels_zh"].get(s["id"], s["label"]) if lang == "zh" else s["label"]
        big = s["type"] == "district"
        FONT = "Georgia,'Songti SC','Noto Serif SC',serif"
        fst = "normal" if lang == "zh" else "italic"
        common = (f'x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" font-family="{FONT}" font-style="{fst}" '
                  f'font-size="{(6.5 if big else 3.6) if lang == "zh" else (9 if big else 4.5)}" letter-spacing="{(3 if big else 0.2) if lang == "zh" else (2.5 if big else 0.6)}"')
        if not big:
            P.append(f'<text class="lb" {common} fill="none" stroke="#f3e7c9" stroke-width="1.4" stroke-linejoin="round">{html.escape(lab)}</text>')
        P.append(f'<text class="lb" {common} fill="{INK}" fill-opacity="{0.55 if big else 0.95}">{html.escape(lab)}</text>')
    pop = len(houses_standing(w, year)) * 9
    if lang == "zh":
        yr = f"前 {-year} 年" if year < 0 else f"建城 {year} 年"
        sub, popl = yr, f"约 {pop:,} 人"
    else:
        sub, popl = (f"{-year} BC" if year < 0 else f"Anno Fundationis {year}"), f"c. {pop:,} souls"
    cart = (f'<g transform="translate(24,22)"><rect width="250" height="76" fill="#f3e7c9" fill-opacity="0.92" stroke="{INK}" stroke-width="1.2"/>'
            f'<rect x="4" y="4" width="242" height="68" fill="none" stroke="{INK}" stroke-width="0.5"/>'
            f'<text x="125" y="32" text-anchor="middle" font-family="Georgia,serif" font-size="22" letter-spacing="6" fill="{INK}">ANTHOUSA</text>'
            f'<text x="125" y="52" text-anchor="middle" font-family="Georgia,serif" font-size="11" font-style="italic" fill="{INK}">{sub}</text>'
            f'<text x="125" y="66" text-anchor="middle" font-family="Georgia,serif" font-size="9" fill="{INK}" fill-opacity="0.75">{popl}</text></g>')
    return terrain_inner + '<g id="city">' + "".join(P) + "</g>" + cart


def main():
    global I18N
    I18N = json.load(open(os.path.join(ROOT, "i18n", "i18n.json"), encoding="utf-8"))
    w = load()
    years = [w["meta"]["start_year"]] + [e["to"] for e in w["eras"]]
    for lang, sub in (("en", ""), ("zh", "zh")):
        t = render_terrain(lang)
        defs_end = t.index("</defs>") + 7
        head = t[:defs_end]
        inner = t[defs_end:-6]
        out = os.path.join(DOCS, "years", sub)
        os.makedirs(out, exist_ok=True)
        for y in years:
            svg = head + svg_for(w, y, inner, lang) + "</svg>"
            open(os.path.join(out, f"{y:05d}.svg".replace("-", "m")), "w", encoding="utf-8").write(svg)
    for e in w["eras"]:
        f = os.path.join(ROOT, "chronicle", f"{e['from']}_{e['to']}.md")
        e["chronicle"] = open(f, encoding="utf-8").read() if os.path.exists(f) else None
        f = os.path.join(ROOT, "chronicle", "en", f"{e['from']}_{e['to']}.md")
        e["chronicle_en"] = open(f, encoding="utf-8").read() if os.path.exists(f) else None
        e["title_en"] = I18N["titles_en"].get(str(e["from"]), "")
    data = {"meta": w["meta"], "years": years, "names_zh": I18N["names_zh"],
            "eras": [{k: e[k] for k in ("from", "to", "title", "title_en", "chronicle_en", "accepted", "rejected", "events", "stats", "chronicle", "review_rounds") if k in e}
                     for e in w["eras"]],
            "structures": [{k: s.get(k) for k in ("id", "name", "type", "built", "destroyed", "cause", "faction", "history")} | {"name_zh": I18N["names_zh"].get(s["id"]), "motif": motif_of(s), "style_era": style_era(s["built"])}
                           for s in w["structures"] if s["type"] != "district" or s.get("label")]}
    json.dump(data, open(os.path.join(DOCS, "data.json"), "w"), ensure_ascii=False)
    print("rendered", years)


if __name__ == "__main__":
    main()
