"""Acceptance checks run after every era (the 'CI' of the city). Exit 1 on any failure.
These checks are code, not opinions: they do not care how good the chronicle sounds."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from world import load, by_id, ROOT
import rules

w = load()
fails = []
year = w["meta"]["year"]
fails += [f"world: {p}" for p in rules.check_world(w, year)]
for e in w["eras"]:
    f = os.path.join(ROOT, "chronicle", f"{e['from']}_{e['to']}.md")
    if not os.path.exists(f):
        fails.append(f"era {e['from']}-{e['to']}: chronicle missing")
        continue
    text = open(f).read()
    for sid in re.findall(r"\{\{(\w+)\}\}", text):
        s = by_id(w, sid)
        if s is None:
            fails.append(f"chronicle {e['from']}-{e['to']}: mentions {sid}, which was never built")
        elif s["built"] > e["to"]:
            fails.append(f"chronicle {e['from']}-{e['to']}: mentions {sid} before it exists")
        elif s.get("destroyed") is not None and s["destroyed"] < e["from"] - 60:
            fails.append(f"chronicle {e['from']}-{e['to']}: mentions {sid}, gone since {s['destroyed']}")
    zh = {"fire": "火", "earthquake": "地震", "plague": "瘟疫"}
    for ev in e.get("events", []):
        if zh[ev["type"]] not in text:
            fails.append(f"chronicle {e['from']}-{e['to']}: the {ev['type']} of year {ev['year']} is not mentioned")
    pop = e["stats"]["population"]
    nums = [int(n.replace(",", "")) for n in re.findall(r"(\d[\d,]*)\s*人", text)]
    if "万" not in text and nums and all(abs(n - pop) / pop > 0.1 for n in nums):
        fails.append(f"chronicle {e['from']}-{e['to']}: no population figure within 10% of {pop}")
    if len(e.get("accepted", [])) == 0 and not e.get("events"):
        fails.append(f"era {e['from']}-{e['to']}: nothing happened (no-progress brake)")
print("\n".join(fails) if fails else f"all checks passed for {len(w['eras'])} eras, year {year}")
sys.exit(1 if fails else 0)
