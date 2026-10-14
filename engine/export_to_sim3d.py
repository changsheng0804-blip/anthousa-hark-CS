#!/usr/bin/env python3
"""Export Anthousa world data to 3D pipeline format.
Outputs:
- Terrain elevation grid + water mask on the Bosporus peninsula (SRTM 30m + OSM coastline)
- Monumental structures, walls, roads, and houses across all eras (-657 .. AF 20)
- Bounding geometry and elevations for real-time WebGL instancing and Blender CLI
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import terrain
from world import load

# Bounds around the historic peninsula
X0, X1 = 80.0, 760.0
Z0, Z1 = 160.0, 580.0
STEP = 4.0  # 4 units = 48 meters per grid cell

NX = int((X1 - X0) / STEP) + 1
NZ = int((Z1 - Z0) / STEP) + 1

heights = []
water_mask = []

for j in range(NZ):
    z = Z0 + j * STEP
    for i in range(NX):
        x = X0 + i * STEP
        is_l = terrain.is_land(x, z)
        elev = terrain.elevation(x, z) if is_l else -3.0
        heights.append(round(elev, 1))
        water_mask.append(0 if is_l else 1)

# Load i18n
i18n_path = os.path.join(ROOT, "i18n", "i18n.json")
names_zh = {}
if os.path.exists(i18n_path):
    with open(i18n_path, "r", encoding="utf-8") as f:
        i18n = json.load(f)
        names_zh = i18n.get("names_zh", {})

# Load world
w = load()

structures_3d = []
for s in w.get("structures", []):
    geom = s.get("geom", {})
    gtype = geom.get("type")
    coords = geom.get("coords", [])
    sid = s.get("id")
    stype = s.get("type")
    name = s.get("name")
    name_zh = names_zh.get(sid, s.get("name_zh", name))
    
    if gtype == "point":
        bx, bz = coords[0], coords[1]
        base_h = terrain.elevation(bx, bz) if terrain.is_land(bx, bz) else 0.0
    elif coords:
        bx = sum(p[0] for p in coords) / len(coords)
        bz = sum(p[1] for p in coords) / len(coords)
        base_h = terrain.elevation(bx, bz) if terrain.is_land(bx, bz) else 0.0
    else:
        bx, bz, base_h = 0, 0, 0
    
    structures_3d.append({
        "id": sid,
        "type": stype,
        "name": name,
        "name_zh": name_zh,
        "faction": s.get("faction", "emperor"),
        "built": s.get("built", 0),
        "destroyed": s.get("destroyed"),
        "geom_type": gtype,
        "coords": coords,
        "cx": round(bx, 1),
        "cz": round(bz, 1),
        "base_h": round(base_h, 1),
        "history": s.get("history", [])
    })

houses_3d = []
for h in w.get("houses", []):
    p = h.get("p", [])
    if len(p) >= 3:
        cx = sum(pt[0] for pt in p) / len(p)
        cz = sum(pt[1] for pt in p) / len(p)
        base_h = terrain.elevation(cx, cz) if terrain.is_land(cx, cz) else 0.0
        houses_3d.append({
            "id": h.get("id"),
            "built": h.get("built", 0),
            "destroyed": h.get("destroyed"),
            "cx": round(cx, 1),
            "cz": round(cz, 1),
            "base_h": round(base_h, 1),
            "poly": p
        })

eras = []
for era in w.get("eras", []):
    eras.append({
        "from": era.get("from"),
        "to": era.get("to"),
        "title": era.get("title"),
        "title_en": era.get("title_en"),
        "stats": era.get("stats", {})
    })

export_data = {
    "grid": {
        "x0": X0, "x1": X1,
        "z0": Z0, "z1": Z1,
        "step": STEP,
        "nx": NX, "nz": NZ,
        "heights": heights,
        "water": water_mask
    },
    "eras": eras,
    "years": w.get("meta", {}).get("years", [-657, 0, 10, 20]),
    "structures": structures_3d,
    "houses": houses_3d
}

# Output to docs/
docs_out = os.path.join(ROOT, "docs", "anthousa_world3d.json")
with open(docs_out, "w", encoding="utf-8") as f:
    json.dump(export_data, f, ensure_ascii=False)
print(f"Exported 3D data to {docs_out} ({len(structures_3d)} structures, {len(houses_3d)} houses).")

# Also copy to sibling castle-town-sim if present
sibling_sim = os.path.abspath(os.path.join(ROOT, "..", "castle-town-sim"))
if os.path.isdir(sibling_sim):
    sim_out = os.path.join(sibling_sim, "anthousa_world3d.json")
    with open(sim_out, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False)
    print(f"Synchronized with sibling castle-town-sim: {sim_out}")
