"""Tests for the grammar rulings (PR-C1). Run: python engine/test_grammar_rules.py
Uses the real AF 20 world and asks the rules engine about hypothetical AF 21 proposals."""
import os, sys, copy
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
print(f"{fails} failed" if fails else "all grammar rule tests passed")
sys.exit(1 if fails else 0)
