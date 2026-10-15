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
    text = open(f, encoding="utf-8").read()
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
    # English edition: must exist, mention exactly the same structures, every event, and a population figure within 10%
    fe = os.path.join(ROOT, "chronicle", "en", f"{e['from']}_{e['to']}.md")
    if not os.path.exists(fe):
        fails.append(f"era {e['from']}-{e['to']}: English chronicle missing")
    else:
        en = open(fe, encoding="utf-8").read()
        if set(re.findall(r"\{\{(\w+)\}\}", en)) != set(re.findall(r"\{\{(\w+)\}\}", text)):
            fails.append(f"chronicle {e['from']}-{e['to']}: English and Chinese editions mention different structures")
        for ev in e.get("events", []):
            if ev["type"] not in en.lower():
                fails.append(f"chronicle/en {e['from']}-{e['to']}: the {ev['type']} of year {ev['year']} is not mentioned")
        nums = [int(n.replace(",", "")) for n in re.findall(r"\b\d{1,3}(?:,\d{3})+\b", en)]
        if not any(abs(n - pop) / pop <= 0.1 for n in nums):
            fails.append(f"chronicle/en {e['from']}-{e['to']}: no population figure within 10% of {pop}")
    if len(e.get("accepted", [])) == 0 and not e.get("events"):
        fails.append(f"era {e['from']}-{e['to']}: nothing happened (no-progress brake)")
import json as _json
_i = _json.load(open(os.path.join(ROOT, "i18n", "i18n.json"), encoding="utf-8"))
for s in w["structures"]:
    if s.get("label") and s["id"] not in _i["labels_zh"]:
        fails.append(f"i18n: map label of {s['id']} has no Chinese translation")
    if s["type"] != "district" and s["id"] not in _i["names_zh"]:
        fails.append(f"i18n: {s['id']} has no Chinese name")
# dna_consistency (grammar v0.2, PR-C1): whatever dna a structure carries must be valid, and spolia must come from ruins
import grammar
for s in w["structures"]:
    ok, msgs = grammar.validate_dna(s)
    fails += [f"dna: {m}" for m in msgs]
    for src in s.get("spolia_from", []):
        o = by_id(w, src)
        if o is None or o.get("destroyed") is None or o["destroyed"] > s["built"]:
            fails.append(f"dna: {s['id']} reuses spolia from {src}, which was not a ruin in AF {s['built']}")
# phases (2026-10-14): staged construction inside the ledger; first phase is the built (clearing) year,
# years ascend, a 'done' without part closes it, and nothing outlives the structure
for s in w["structures"]:
    ph = s.get("phases")
    if not ph: continue
    ys = [p["year"] for p in ph]
    if ys[0] != s["built"]: fails.append(f"phases: {s['id']} starts in {ys[0]}, built {s['built']}")
    if ys != sorted(ys): fails.append(f"phases: {s['id']} years not ascending")
    if any(p["stage"] not in ("site", "frame", "done") for p in ph): fails.append(f"phases: {s['id']} unknown stage")
    if not any(p["stage"] == "done" and "part" not in p for p in ph): fails.append(f"phases: {s['id']} never done")
    if s.get("destroyed") is not None and ys[-1] >= s["destroyed"]: fails.append(f"phases: {s['id']} phase after destruction")
    if ys[-1] > year: fails.append(f"phases: {s['id']} phase beyond the present year {year}")
print("\n".join(fails) if fails else f"all checks passed for {len(w['eras'])} eras, year {year}")
sys.exit(1 if fails else 0)
