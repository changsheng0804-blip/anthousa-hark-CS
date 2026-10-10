"""Tests for the grammar rulings (PR-C1). Run: python engine/test_grammar_rules.py
Uses the real AF 20 world and asks the rules engine about hypothetical AF 21 proposals."""
import os, sys, copy
from shapely.geometry import Polygon
sys.path.insert(0, os.path.dirname(__file__))
from world import load
import rules

w = load()
Y = 21
sq = lambda x, y, a, b: {"type": "polygon", "coords": [[x, y], [x + a, y], [x + a, y + b], [x, y + b], [x, y]]}
church_old = next(s for s in w["structures"] if s["id"] == "church_apostles")
cx, cy = church_old["geom"]["coords"][0]
base = {"id": "t_church", "name": "Test", "type": "church", "geom": sq(cx + 14, cy + 8, 4, 2.5)}
fails = 0


def expect(label, s, want_reject, contains=None, year=Y, world=w):
    global fails
    errs = [e for e in rules.check_grammar(world, s, year)]
    ok = bool(errs) == want_reject and (contains is None or any(contains in e for e in errs))
    print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  -> {errs}"))
    fails += not ok


expect("no motif from AF 21 is rejected", dict(base), True, "must declare dna.motif")
expect("AF 20 is grandfathered", dict(base), False, year=20)
expect("allowed motif passes", dict(base, dna={"motif": "cross_in_square", "scale": "monumental", "ornament": 2}), False)
expect("motif not allowed for type", dict(base, dna={"motif": "hippodrome"}), True, "not allowed")
expect("unknown motif", dict(base, dna={"motif": "pagoda"}), True, "unknown motif")
expect("bad ornament", dict(base, dna={"motif": "basilica", "ornament": 7}), True, "ornament")
expect("road is exempt", {"id": "t_road", "type": "road", "geom": {"type": "line", "coords": [[0, 0], [5, 5]]}}, False)
expect("spolia from a standing building", dict(base, dna={"motif": "basilica"}, spolia_from=["hippodrome"]), True, "still standing")
expect("spolia from a missing id", dict(base, dna={"motif": "basilica"}, spolia_from=["nowhere"]), True, "no such structure")
expect("spolia from a ruin", dict(base, dna={"motif": "basilica"}, spolia_from=["gate_old_thracian"]), False)
big = dict(base, geom=sq(cx + 14, cy + 8, 15, 10), dna={"motif": "domed_basilica", "scale": "wonder"})
expect("oversized wonder", big, True, "wonder_max_area")
w2 = copy.deepcopy(w)
w2["structures"].append(dict(base, id="t_first", built=21, dna={"motif": "domed_basilica", "scale": "wonder"}))
expect("second wonder in a decade", dict(base, dna={"motif": "domed_basilica", "scale": "wonder"}), True, "already this decade", world=w2)
mats = dict(base, dna={"motif": "basilica", "materials": ["gold_mosaic"]})
ok = bool(rules.grammar_warnings(mats, Y)) and not rules.check_grammar(w, mats, Y)
print(("PASS " if ok else "FAIL ") + "materials off-palette warn but do not reject")
fails += not ok

# memorial on demolishing a wonder (step.apply_actions), asked for by review of PR #13 once a wonder exists
import step
w3 = copy.deepcopy(w)
w3["structures"].append(dict(base, id="t_wonder", built=21, destroyed=None, history=[], faction="church",
                             dna={"motif": "basilica", "scale": "wonder", "ornament": 3}))
era = {"from": 31, "to": 40}
acc, rej = step.apply_actions(copy.deepcopy(w3), {"actions": [{"op": "demolish", "id": "t_wonder", "faction": "emperor", "year": 32}]}, era)
ok = not acc and rej and "memorial" in rej[0]["reasons"][0]
print(("PASS " if ok else "FAIL ") + "demolishing a wonder without memorial is rejected"); fails += not ok
acc, rej = step.apply_actions(copy.deepcopy(w3), {"actions": [{"op": "demolish", "id": "t_wonder", "faction": "emperor", "year": 32,
                                                                "memorial": {"kind": "stele", "note": "a stone marks where it stood"}}]}, era)
ok = acc and not rej
print(("PASS " if ok else "FAIL ") + "demolishing a wonder with a memorial passes"); fails += not ok
acc, rej = step.apply_actions(copy.deepcopy(w3), {"actions": [{"op": "demolish", "id": "t_wonder", "faction": "emperor", "year": 32,
                                                                "memorial": {"kind": "plaque"}}]}, era)
ok = not acc and rej
print(("PASS " if ok else "FAIL ") + "memorial kind outside the enum is rejected"); fails += not ok

# disasters must not depend on the proposals (independent_dice, from AF 21)
import random, json as _json
def dice(world, frm):
    r = random.Random(f"anthousa-events-{step.SEED}-{frm}")
    return [(e["type"], e["year"]) for e in step.roll_events_fixed(copy.deepcopy(world), {"from": frm, "to": frm + 9}, r)]
w4 = copy.deepcopy(w); w4["houses"] = w4["houses"][: len(w4["houses"]) // 2]  # a very different city
seen = {frm: dice(w, frm) == dice(w3, frm) == dice(w4, frm) for frm in range(21, 2000, 10)}
print("   eras with a disaster in AF 21-2000:", sum(bool(dice(w, f)) for f in range(21, 2000, 10)), "of", len(seen))
ok = all(seen.values())
print(("PASS " if ok else "FAIL ") + "disaster type and year are the same whatever was built"); fails += not ok
src = open(os.path.join(os.path.dirname(__file__), "step.py")).read()
ok = "independent_dice" in src and rules.CAL["independent_dice"]["from_year"] == 21
print(("PASS " if ok else "FAIL ") + "step.py draws disasters from the independent stream from AF 21"); fails += not ok


# farmland (from AF 31): feeds ~1.5 people/ha, must be ploughable, reachable, and never built on
def farm(c, i="t_farm"):
    return {"id": i, "type": "farmland", "name": "T", "geom": {"type": "polygon", "coords": c}}
F_OK = [[260, 400], [380, 400], [380, 470], [260, 470]]  # gentle ground west of the Founder's wall, by the Mese
ok = not rules.check_structure(w, farm(F_OK), 31)
print(("PASS " if ok else "FAIL ") + "farmland on gentle ground by a road passes"); fails += not ok
ok = any("enters the rules" in e for e in rules.check_structure(w, farm(F_OK), 30))
print(("PASS " if ok else "FAIL ") + "farmland before AF 31 is rejected"); fails += not ok
ok = any("garden plot" in e for e in rules.check_structure(w, farm([[300, 420], [305, 420], [305, 425], [300, 425]]), 31))
print(("PASS " if ok else "FAIL ") + "tiny farmland is rejected"); fails += not ok
ok = any("no road" in e for e in rules.check_structure(w, farm([[300, 330], [390, 330], [390, 420], [300, 420]]), 31))
print(("PASS " if ok else "FAIL ") + "farmland far from any road is rejected"); fails += not ok
hippo = next(s for s in w["structures"] if s["id"] == "hippodrome")
hc = hippo["geom"]["coords"]; hx = sum(p[0] for p in hc) / len(hc); hy = sum(p[1] for p in hc) / len(hc)
ok = any("overlaps standing hippodrome" in e for e in rules.check_structure(w, farm([[hx - 10, hy - 6], [hx + 10, hy - 6], [hx + 10, hy + 6], [hx - 10, hy + 6]]), 31))
print(("PASS " if ok else "FAIL ") + "farmland over a building is rejected"); fails += not ok
w5 = copy.deepcopy(w); f5 = dict(farm(F_OK), built=31, destroyed=None); w5["structures"].append(f5)
from world import geom as _g
gain = rules.capacities(w5, 31)["food"] - rules.capacities(w, 31)["food"]
want = int(_g(f5).area * 144 / 10000 * rules.CAL["farmland"]["people_per_ha"])
ok = abs(gain - want) <= 1
print(("PASS " if ok else "FAIL ") + f"farmland feeds {gain} people ({_g(f5).area * 144 / 10000:.0f} ha x {rules.CAL['farmland']['people_per_ha']}/ha)"); fails += not ok
import random as _r
h0 = len(w5["houses"]); step.grow(w5, {"from": 31, "to": 40}, _r.Random(1))
ok = not any(_g(f5).contains(Polygon(h["p"]).centroid) for h in w5["houses"][h0:])
print(("PASS " if ok else "FAIL ") + "no house grows on farmland"); fails += not ok

print(f"{fails} failed" if fails else "all grammar rule tests passed")
sys.exit(1 if fails else 0)
