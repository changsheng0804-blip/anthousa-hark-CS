"""Era AF 61-70 (AD 390-399, Theodosius I). At AF 60 the city held 149,193 people against food 193,202 and water 188,000.
This decade is the people's: four petitions of the commoners (Xerolophos residents) of the dry hill, each written from a
pressure counted among the households of the painted quarter (docs/living/xerolophos/): crowded houses, the water queue,
the households left without a grown man, and the Arians who still pray in a timber yard beyond the wall.
Source: Liu-line residents' petitions; evidence in anthousa-liuzhijie drafts/proposals_af61_70
(https://github.com/liuzhijie820802-a11y/anthousa-liuzhijie/tree/main/drafts/proposals_af61_70 : pressures.json, README.md).
A fifth petition from the same drafts (a firebreak across the hill, 155 houses pulled down) was NOT submitted.
Real anchors: Theodosius' laws against heretics (380s-390s) kept Arian worship outside the walls; the Exokionion (the
quarter "outside the column", later the Exokionion beyond Constantine's wall) grew outside the Founder's wall before the
Theodosian Walls enclosed it (position approximate). The cistern, steps and widows' house are invented for Anthousa.
Helpers are copied from make_eras_v3 (importing it rewrites era_0000/era_0001 as a side effect).
Hand-written by Hark (Liu line)."""
import json, math, os, sys
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "engine"))
from shapely.geometry import LineString
from terrain import land

L = land()
def R(v): return [round(v[0], 1), round(v[1], 1)]
def clipline(c):
    g = LineString(c).intersection(L.buffer(-0.8))
    parts = list(getattr(g, "geoms", [g]))
    return [R(p) for p in max(parts, key=lambda p: p.length).coords]
def rect(cx, cy, w, h, ang=0):
    a = math.radians(ang); c, s = math.cos(a), math.sin(a)
    return [R((cx + x * c - y * s, cy + x * s + y * c)) for x, y in [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]]
LINE = {"road", "wall", "aqueduct"}
def B(f, id, t, name, coords, why, gt=None, label=None, **kw):
    if t in LINE: coords = clipline(coords)
    st = {"id": id, "type": t, "name": name, "geom": {"type": gt or ("line" if t in LINE else "polygon"), "coords": coords}}
    if label: st["label"] = label
    st.update(kw); return {"faction": f, "op": "build", "structure": st, "why": why}

SRC = "Liu-line residents' petition (commoners of the Xerolophos); evidence: anthousa-liuzhijie drafts/proposals_af61_70"
era = {"era": {"from": 61, "to": 70, "title": "干山上的请愿"}, "actions": [
 # petition 1: the new quarter outside the wall (crowding)
 B("people", "r_exo", "road", "Lane of the Newcomers", [[398, 473], [392, 450], [386, 430]],
   "A lane leaves the Mese just outside the Founder's gate and climbs north along the wall.", width=1.2, year=63),
 B("people", "d_exokionion", "district", "Exokionion", [[370, 425], [404, 425], [400, 500], [366, 505]],
   "Grown sons with nowhere to sleep and the families still coming off the grain ships build outside the Founder's wall, "
   "along the Mese and the new lane, where the Arians already walk on feast days.",
   label="EXOKIONION", year=63),
 # petition 2: the second cistern on the slope (water) - the steps must come first, or the cistern has no road
 B("people", "r_carriers", "road", "Carriers' Steps", [[440, 463], [440, 428]],
   "A stepped lane from the Mese straight up the middle of the hill, so a carrier no longer threads between houses with a full jar.",
   width=1.2, year=62),
 B("people", "cistern_slope", "cistern", "Second Cistern of the Water-Carriers", rect(440, 425, 6, 5, 0),
   "The water-carriers' first cistern (AF 54) sits at the foot of the hill and the queue there runs till dark; "
   "the families of the upper slope pool their coppers again for a second cistern at the head of the new steps.",
   label="Carriers II", year=62, dna={"motif": "cistern", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 # petition 3: the house of the widows and orphans
 B("people", "xenon_xerolophos", "monastery", "House of the Widows and Orphans", rect(444, 453, 5, 4, 0),
   "On the hill one household in seven has no grown man left and small children at home. Neighbours and the monks "
   "who took in their sons build a house where widows bake for the street and orphans learn a trade.",
   label="Widows' house", year=65, dna={"motif": "monastery", "materials": ["brick"], "ornament": 0, "scale": "domestic"}),
 # petition 4: the brick church outside the gate (faith)
 B("people", "church_arian_brick", "church", "Arian Church outside the Gate", rect(394, 466, 6, 4, 0),
   "For ten years the Arians of the hill have prayed in a timber yard beyond the wall, and their priests will not "
   "come into the city even to bless a sick child. They raise a small brick church outside the Founder's gate.",
   label="Arian church", year=64, dna={"motif": "basilica", "materials": ["brick"], "ornament": 1, "scale": "civic"}),
]}
for a in era["actions"]:
    a["proposer"] = "commoners (Xerolophos residents)"
    a["source"] = SRC
    if "year" in a["structure"]:
        a["year"] = a["structure"].pop("year")
era["review"] = [{"round": 1, "rejected": [
 {"id": "cistern_slope", "reason": "no road within 25 units; nobody could reach it",
  "fix": "the Carriers' Steps are listed before the cistern, so the lane exists when the cistern is judged"}]}]
json.dump(era, open(os.path.join(D, "era_0061.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0061.json")
