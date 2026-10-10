"""World state: load/save and geometry helpers. world.json is the single source of truth."""
import json, os
from shapely.geometry import Polygon, LineString, Point, shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "world.json")

BUILDING_TYPES = {"palace", "forum", "church", "market", "fort", "granary", "cistern", "temple",
                  "hippodrome", "baths", "monument", "column", "monastery", "barracks", "warehouse",
                  "ruin_marker", "gate", "aqueduct_bridge"}
LINE_TYPES = {"road", "wall", "aqueduct", "seawall"}
WATER_TYPES = {"harbor"}            # polygons that must reach into the water
AREA_TYPES = {"district"}           # zones that houses grow into


def load():
    with open(WORLD) as f:
        return json.load(f)


def save(w):
    with open(WORLD, "w") as f:
        json.dump(w, f, ensure_ascii=False, indent=1)


def geom(s):
    g = s["geom"]
    if g["type"] == "polygon":
        return Polygon(g["coords"])
    if g["type"] == "line":
        return LineString(g["coords"])
    return Point(g["coords"])


def standing(w, year, types=None):
    """Structures that exist in `year`."""
    out = []
    for s in w["structures"]:
        if s["built"] > year:
            continue
        if s.get("destroyed") is not None and s["destroyed"] <= year:
            continue
        if types and s["type"] not in types:
            continue
        out.append(s)
    return out


def by_id(w, sid):
    for s in w["structures"]:
        if s["id"] == sid:
            return s
    return None


def houses_standing(w, year):
    return [h for h in w["houses"] if h["built"] <= year and (h.get("destroyed") is None or h["destroyed"] > year)]
