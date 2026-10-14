# Landmark system (open typology for all of Constantinople) — 2026-10-13
User: make special buildings an OPEN type system so every special building of the whole city can plug in later.

## Principle
A landmark = data spec (JSON, gen/landmarks/*.json) + a small shape vocabulary in gen/landmark_shapes.py.
Adding a new building type = add one JSON file (and only rarely a new shape primitive). No per-building code paths in render/JS:
landmarks export into houses_geom.json format (parts + stage table), so page/render/audit already draw them.

## Spec fields
- id, name_zh, name_la, category (civic|religious|water|food|trade|military|burial|imperial|entertainment)
- era: earliest/latest year (city years), historic: true + source note when a real building (e.g. Cistern of Modestus 369, Forum of Arcadius 403)
- quarters: where it may appear (any | list of quarter ids) ; instances: fixed [{quarter,x,y,year}] for historic ones, or generic count rules
- siting: needs (on street kind m/s, near water/aqueduct/wall/gate/market, outside walls), avoid, lot size min/max, orientation (face street | east for churches)
- footprint: shape primitive + params (rect, hall, basilica(nave,aisles,apse,atrium), rotunda, court(colonnade), steps, cistern(roofed/open), granary(long bays), kiln, column, arch, cemetery(stelae))
- materials/palette: wall, roof, accents (marble, brick bands, lead dome)
- stages: list of {from: rel year, shape/params override} e.g. room → room+atrium → basilica; construction scaffold; ageing; damage/fire; demolition/spolia
- function: block function it imposes/needs (h[8]), people/scenes hooks (queue at bread steps), street name hook (name_streets landmark list)
- size class: small (1 lot) | medium (merge lots) | large (own block, roads route around)

## Pipeline
streets_xero (reserve lots/blocks for large landmarks first) → landmarks.py place (siting rules, fixed instances) → houses on the rest → audit (landmark bodies included, strict 0) → blocks/name_streets/place_scenes → render/export.

## First types
1. bread_steps (panes gradiles): small, food, on a main street near market, steps + small bakery store; daily queue scene.
2. church: small→medium, religious, east-facing; stages oratory room → +atrium → small basilica (nave, aisles, apse).
Existing hard-coded landmarks (cisterns, baths, barracks, gate, aqueduct, arian church) migrate into specs later.
