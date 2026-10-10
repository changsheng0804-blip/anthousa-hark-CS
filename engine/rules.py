"""The rules engine: physical / civic constraints every proposal must satisfy.
The AI proposes; this code decides. Nothing here is written to flatter the AI."""
from shapely.geometry import Point
from shapely.ops import unary_union
from terrain import land
from world import geom, standing, BUILDING_TYPES, LINE_TYPES, WATER_TYPES, AREA_TYPES

import json, os
CAL = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules", "calibration.json")))
PEOPLE_PER_HOUSE = CAL["people_per_house"]["value"]


def capacities(w, year):
    s = standing(w, year)
    t = [x["type"] for x in s]
    F, Wt = CAL["food"], CAL["water"]
    # a structure may carry its own "capacity" (e.g. a small early aqueduct); otherwise the calibrated default
    food = F["base"] + sum(x.get("capacity", F[x["type"]]) for x in s if x["type"] in ("harbor", "granary", "market", "warehouse"))
    water = Wt["base"] + sum(x.get("capacity", Wt[x["type"]]) for x in s if x["type"] in ("cistern", "aqueduct"))
    return {"food": food, "water": water}


def population(w, year):
    from world import houses_standing
    return len(houses_standing(w, year)) * PEOPLE_PER_HOUSE


def check_structure(w, s, year):
    """Return a list of reasons the structure cannot exist; empty list = accepted."""
    errs = []
    L = land()
    g = geom(s)
    t = s["type"]
    if not g.is_valid:
        return [f"{s['id']}: invalid geometry"]
    if any(x["id"] == s["id"] for x in w["structures"]):
        errs.append(f"{s['id']}: id already used")
    if t in BUILDING_TYPES | AREA_TYPES:
        if not g.within(L.buffer(0.5)):
            errs.append(f"{s['id']}: footprint leaves dry land ({g.difference(L).area:.0f} sq units in water)")
    if t in WATER_TYPES:
        if g.intersection(L).area < 0.05 * g.area or g.difference(L).area < 0.3 * g.area:
            errs.append(f"{s['id']}: a harbor must sit on the shore, mostly in the water")
    if t in ("road", "wall", "aqueduct"):
        on = g.intersection(L).length / max(g.length, 1e-6)
        if on < 0.97:
            errs.append(f"{s['id']}: {t} runs {100*(1-on):.0f}% over water")
    # collisions with standing solid structures
    if t in BUILDING_TYPES | WATER_TYPES:
        for o in standing(w, year, BUILDING_TYPES | WATER_TYPES):
            if geom(o).intersection(g).area > 1.0:
                errs.append(f"{s['id']}: overlaps standing {o['id']} ({o['name']})")
        for o in standing(w, year, {"road", "wall"}):
            if t not in ("gate", "forum", "column", "monument") and geom(o).intersects(g.buffer(-1.5)):
                errs.append(f"{s['id']}: blocks the {o['type']} {o['id']} ({o['name']})")
                break
    # roads must join the existing network
    if t == "road":
        roads = standing(w, year, {"road"})
        if roads:
            net = unary_union([geom(r) for r in roads])
            ends = [Point(g.coords[0]), Point(g.coords[-1])]
            if min(net.distance(e) for e in ends) > 4 and net.distance(g) > 4:
                errs.append(f"{s['id']}: road does not connect to the existing street network")
    # a road or wall that crosses a standing wall/road needs a gate there
    if t in ("road", "wall"):
        other = "wall" if t == "road" else "road"
        gates = [geom(x) for x in standing(w, year, {"gate"})]
        pending = [geom(x) for x in w.get("_pending_gates", [])]
        for o in standing(w, year, {other}):
            cross = geom(o).intersection(g)
            if cross.is_empty:
                continue
            pts = list(cross.geoms) if hasattr(cross, "geoms") else [cross]
            for pt in pts:
                c = pt.centroid
                if not any(gt.buffer(3).contains(c) for gt in gates + pending):
                    errs.append(f"{s['id']}: crosses {o['type']} {o['id']} at ({c.x:.0f},{c.y:.0f}) with no gate")
    # buildings must be reachable
    if t in BUILDING_TYPES and t not in ("column", "monument", "aqueduct_bridge", "gate"):
        roads = standing(w, year, {"road"})
        if roads and min(geom(r).distance(g) for r in roads) > 25:
            errs.append(f"{s['id']}: no road within 25 units; nobody could reach it")
    if t in AREA_TYPES:
        roads = standing(w, year, {"road"})
        if not roads or min(geom(r).distance(g) for r in roads) > 10:
            errs.append(f"{s['id']}: a district needs a road running into it")
    # an aqueduct must start on high ground outside town and end lower
    if t == "aqueduct":
        from terrain import elevation
        a, b = g.coords[0], g.coords[-1]
        if elevation(*a) <= elevation(*b):
            errs.append(f"{s['id']}: aqueduct would have to run uphill")
        # the channel falls evenly from source to end; wherever the ground drops more than
        # SAG m below it, the channel needs an arcade (a standing aqueduct_bridge) under it
        R = CAL.get("aqueduct_arcade_rule", {})
        if year >= R.get("from_year", 10**9):
            e0, e1, n = elevation(*a), elevation(*b), max(2, int(g.length // 2))
            br = [geom(x).buffer(1.5) for x in standing(w, year, {"aqueduct_bridge"})]
            bad = 0
            for i in range(n + 1):
                f = i / n; p = g.interpolate(f, normalized=True)
                if elevation(p.x, p.y) < e0 + (e1 - e0) * f - R["sag_m"] and not any(b.contains(p) for b in br):
                    bad += 1
            if bad:
                errs.append(f"{s['id']}: {bad * g.length / n * 12:.0f} m of channel would hang in the air with no arcade under it")
    return errs


def check_world(w, year):
    """Global consistency checks run at the end of every era."""
    errs = []
    cap = capacities(w, year)
    pop = population(w, year)
    if pop > cap["food"] * 1.05:
        errs.append(f"population {pop} exceeds food capacity {cap['food']}")
    if pop > cap["water"] * 1.05:
        errs.append(f"population {pop} exceeds water capacity {cap['water']}")
    ids = [s["id"] for s in w["structures"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate structure ids")
    for s in w["structures"]:
        if s.get("destroyed") is not None and s["destroyed"] < s["built"]:
            errs.append(f"{s['id']} destroyed before it was built")
    return errs
