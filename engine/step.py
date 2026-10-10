"""Advance the world one era from a proposals file.

    python engine/step.py proposals/era_0001.json

1. every proposed action is checked by rules.py; failures are recorded, never silently fixed
2. houses grow into districts as far as food and water allow, aligned to the streets
3. the dice roll for fire, earthquake and plague (seeded, the AI does not choose)
4. the era record (accepted, rejected, events, stats) is appended to world.json
"""
import json, math, random, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
from shapely import affinity
from terrain import land, SEED
from world import load, save, geom, standing, houses_standing, by_id, BUILDING_TYPES, WATER_TYPES
import rules

GROWTH_PER_ERA = rules.CAL["growth_cap_per_decade"]["value"]
GROWTH_FLOOR = rules.CAL["growth_floor_houses"]["value"]
HS = rules.CAL["house_size_units"]["value"]
SPACING = rules.CAL["house_spacing_units"]["value"]


def demolish_houses_under(w, g, year, cause):
    n = 0
    for h in houses_standing(w, year):
        if Polygon(h["p"]).intersects(g):
            h["destroyed"] = year
            h["cause"] = cause
            n += 1
    return n


def apply_actions(w, prop, era):
    y0 = era["from"]
    acc, rej = [], []
    w["_pending_gates"] = []
    acts = prop["actions"]
    # gates first so that walls/roads proposed in the same era can pass through them
    acts = sorted(acts, key=lambda a: 0 if a.get("structure", {}).get("type") == "gate" else 1)
    for a in acts:
        year = a.get("year", y0)
        if a["op"] == "build":
            s = dict(a["structure"])
            s["built"] = year
            s["destroyed"] = None
            s["faction"] = a.get("faction")
            if s["type"] == "district":   # a district is a zone: clip it to dry land
                g = Polygon(s["geom"]["coords"]).intersection(land().buffer(-2))
                if g.geom_type == "MultiPolygon":
                    g = max(g.geoms, key=lambda q: q.area)
                s["geom"] = {"type": "polygon", "coords": [[round(x, 1), round(y, 1)] for x, y in g.exterior.coords]}
            s["history"] = [{"year": year, "text": a.get("why", "")}]
            errs = rules.check_structure(w, s, year)
            if errs:
                rej.append({"faction": a.get("faction"), "id": s["id"], "name": s.get("name"), "reasons": errs})
                continue
            w["structures"].append(s)
            if s["type"] == "gate":
                w["_pending_gates"].append(s)
            if s["type"] not in ("district",):
                g = geom(s)
                width = {"road": s.get("width", 2) / 2 + 0.4, "wall": 1.0, "aqueduct": 0.8}.get(s["type"], 0.3)
                n = demolish_houses_under(w, g.buffer(width), year, f"cleared for {s['name']}")
                if n:
                    s["history"].append({"year": year, "text": f"{n} houses were pulled down to make room."})
            acc.append({"faction": a.get("faction"), "op": "build", "id": s["id"], "name": s.get("name")})
        elif a["op"] == "demolish":
            s = by_id(w, a["id"])
            if not s or (s.get("destroyed") is not None and s["destroyed"] <= year):
                rej.append({"faction": a.get("faction"), "id": a["id"], "reasons": ["nothing standing to demolish"]})
                continue
            s["destroyed"] = year
            s["cause"] = a.get("why", "demolished")
            s["history"].append({"year": year, "text": "Demolished: " + a.get("why", "")})
            acc.append({"faction": a.get("faction"), "op": "demolish", "id": s["id"], "name": s.get("name")})
        elif a["op"] == "rename":
            s = by_id(w, a["id"])
            s["history"].append({"year": year, "text": f"Renamed from {s['name']} to {a['name']}. " + a.get("why", "")})
            s["name"] = a["name"]
            acc.append({"faction": a.get("faction"), "op": "rename", "id": s["id"], "name": a["name"]})
    w.pop("_pending_gates", None)
    return acc, rej


def placed_add(idx, hp):
    x, y = hp.centroid.x, hp.centroid.y
    idx.setdefault((int(x // 4), int(y // 4)), []).append(hp)


def tree_new_hit(idx, hp):
    x, y = hp.centroid.x, hp.centroid.y
    cx, cy = int(x // 4), int(y // 4)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for q in idx.get((cx + i, cy + j), ()):
                if q.intersects(hp):
                    return True
    return False


def grow(w, era, rnd, floor=GROWTH_FLOOR):
    y0, y1 = era["from"], era["to"]
    cap = rules.capacities(w, y1)
    limit = int(min(cap["food"], cap["water"]) * 0.97 / rules.PEOPLE_PER_HOUSE)
    have = len(houses_standing(w, y1))
    target = min(limit, max(have + floor, int(have * (1 + GROWTH_PER_ERA))))
    need = target - have
    if need <= 0:
        return 0
    L = land()
    roads = standing(w, y1, {"road"})
    road_geoms = [geom(r) for r in roads]
    block = [geom(r).buffer(r.get("width", 2) / 2 + 0.4) for r in roads]
    block += [geom(s).buffer(1.0) for s in standing(w, y1, {"wall", "aqueduct"})]
    block += [geom(s).buffer(0.4) for s in standing(w, y1, BUILDING_TYPES | WATER_TYPES)]
    existing = [Polygon(h["p"]) for h in houses_standing(w, y1)]
    tree_block = STRtree(block) if block else None
    districts = standing(w, y1, {"district"})
    if not districts or not road_geoms:
        return 0
    road_tree = STRtree(road_geoms)
    cands = []
    for d in districts:
        dg = geom(d).intersection(L.buffer(-2))
        minx, miny, maxx, maxy = dg.bounds
        sp = d.get("spacing", SPACING)
        yy = miny
        while yy < maxy:
            xx = minx
            while xx < maxx:
                x, y = xx + rnd.uniform(-0.3, 0.3) * sp, yy + rnd.uniform(-0.3, 0.3) * sp
                p = Point(x, y)
                if dg.contains(p):
                    ri = road_tree.nearest(p)
                    rg = road_geoms[ri]
                    dist = rg.distance(p)
                    cands.append((dist + rnd.uniform(0, 30), x, y, rg, d["id"]))
                xx += sp
            yy += sp
    cands.sort(key=lambda c: c[0])           # houses cling to streets first
    placed_idx = {}
    tree_exist = STRtree(existing) if existing else None
    added = 0
    for _, x, y, rg, did in cands:
        if added >= need:
            break
        t = rg.project(Point(x, y))
        a = rg.interpolate(max(0, t - 1)), rg.interpolate(min(rg.length, t + 1))
        ang = math.degrees(math.atan2(a[1].y - a[0].y, a[1].x - a[0].x))
        wdt, dep = rnd.uniform(*HS), rnd.uniform(HS[0] * 0.85, HS[1] * 0.85)
        hp = Polygon([(-wdt / 2, -dep / 2), (wdt / 2, -dep / 2), (wdt / 2, dep / 2), (-wdt / 2, dep / 2)])
        hp = affinity.translate(affinity.rotate(hp, ang + rnd.uniform(-6, 6)), x, y)
        if tree_block is not None and any(block[i].intersects(hp) for i in tree_block.query(hp)):
            continue
        if tree_exist is not None and any(existing[i].intersects(hp) for i in tree_exist.query(hp)):
            continue
        if tree_new_hit(placed_idx, hp):
            continue
        placed_add(placed_idx, hp)
        w["houses"].append({"id": f"h{len(w['houses'])+1}", "d": did,
                            "p": [[round(px, 1), round(py, 1)] for px, py in list(hp.exterior.coords)[:4]],
                            "built": rnd.randint(y0, y1), "destroyed": None})
        added += 1
    return added


def roll_events(w, era, rnd):
    y0, y1 = era["from"], era["to"]
    ev = []
    hs = houses_standing(w, y1)
    if hs and rnd.random() < 0.28:
        year = rnd.randint(y0, y1)
        c = Polygon(rnd.choice(hs)["p"]).centroid
        r = rnd.uniform(8, 14 + min(40, len(hs) / 300))
        area = c.buffer(r)
        n = 0
        for h in houses_standing(w, year):
            if area.contains(Polygon(h["p"]).centroid) and rnd.random() < 0.9:
                h["destroyed"] = year; h["cause"] = "fire"; n += 1
        burned = []
        for s in standing(w, year, {"market", "warehouse", "church", "baths", "monastery"}):
            if area.contains(geom(s).centroid) and rnd.random() < 0.5:
                s["destroyed"] = year; s["cause"] = "fire"
                s["history"].append({"year": year, "text": "Burned in the great fire."})
                burned.append(s["id"])
        ev.append({"type": "fire", "year": year, "x": round(c.x), "y": round(c.y), "r": round(r),
                   "houses": n, "structures": burned})
    if rnd.random() < 0.08:
        year = rnd.randint(y0, y1)
        fallen = []
        for s in standing(w, year, {"church", "column", "monument", "baths", "wall", "aqueduct_bridge"}):
            if rnd.random() < 0.12:
                s["destroyed"] = year; s["cause"] = "earthquake"
                s["history"].append({"year": year, "text": "Thrown down by the earthquake."})
                fallen.append(s["id"])
        ev.append({"type": "earthquake", "year": year, "structures": fallen})
    if hs and rnd.random() < 0.06:
        year = rnd.randint(y0, y1)
        n = 0
        for h in houses_standing(w, year):
            if rnd.random() < 0.25:
                h["destroyed"] = year; h["cause"] = "plague (abandoned)"; n += 1
        ev.append({"type": "plague", "year": year, "houses": n})
    return ev


def main(path):
    w = load()
    prop = json.load(open(path))
    if prop.get("review"):
        prop_review = prop["review"]
    era = prop["era"]
    if w["eras"] and era["from"] != w["eras"][-1]["to"] + 1:
        sys.exit(f"era must start at year {w['eras'][-1]['to'] + 1}")
    rnd = random.Random(SEED * 100003 + era["from"])
    acc, rej = apply_actions(w, prop, era)
    added = grow(w, era, rnd, prop.get("growth_floor", GROWTH_FLOOR))
    events = roll_events(w, era, rnd) if not prop.get("no_events") else []
    y1 = era["to"]
    stats = {"population": rules.population(w, y1), **rules.capacities(w, y1),
             "houses": len(houses_standing(w, y1)), "houses_added": added,
             "structures": len(standing(w, y1)) - len(standing(w, y1, {"district"}))}
    problems = rules.check_world(w, y1)
    w["eras"].append({"from": era["from"], "to": y1, "title": era.get("title", ""),
                      "review_rounds": prop.get("review", []),
                      "accepted": acc, "rejected": rej, "events": events, "stats": stats,
                      "problems": problems, "chronicle": None})
    w["meta"]["year"] = y1
    if "--dry-run" not in sys.argv:
        save(w)
    print(json.dumps({"accepted": len(acc), "rejected": rej, "events": events, "stats": stats,
                      "problems": problems}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
