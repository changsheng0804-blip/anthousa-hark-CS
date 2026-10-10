"""Architectural grammar (docs/arch-grammar-draft.md v0.2) — PR-B1 skeleton.

Render-side only: nothing here is an input to rules.py or check.py rulings.
A structure may carry an optional `dna` {motif, materials, ornament, scale};
when it doesn't, the motif is inferred from its type (first entry of type_map).
"""
import json, os, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_R = lambda n: json.load(open(os.path.join(ROOT, "rules", n), encoding="utf-8"))
MOTIFS = _R("motifs.json")
ERAS = _R("style_eras.json")
FACTIONS = _R("faction_styles.json")
SCALES = ["domestic", "civic", "monumental", "wonder"]


def style_era(af_year):
    """Style era id for an AF year. Engine years <= 0 are pre-foundation labels (see style_eras.json)."""
    if af_year <= 0:
        return ERAS["pre_foundation"]
    for e in ERAS["eras"]:
        if e["af"][0] <= af_year <= e["af"][1]:
            return e["id"]
    return ERAS["eras"][-1]["id"]


def era(eid):
    return next(e for e in ERAS["eras"] if e["id"] == eid)


def motif_of(s):
    """Declared motif, else the type's default motif, else None (exempt type)."""
    m = (s.get("dna") or {}).get("motif")
    if m:
        return m
    allowed = MOTIFS["type_map"].get(s["type"], [])
    if not allowed:
        return None
    g = s.get("geom", {})
    if "cross_in_square" in allowed and g.get("type") == "polygon" and len(g["coords"]) >= 12:
        return "cross_in_square"  # a cruciform footprint reads as a cross-in-square plan
    return allowed[0]


def motif_for(faction, style_era_id, rng=None, allowed=None):
    """Draw a motif by faction preference (soft weights). For proposal writers, not for rulings."""
    rng = rng or random.Random(0)
    prefs = FACTIONS["factions"].get(faction, {}).get("motifs", {})
    pool = [m for m in (allowed or MOTIFS["motifs"]) if m in MOTIFS["motifs"]]
    weights = [prefs.get(m, 0.3) for m in pool]
    return rng.choices(pool, weights)[0]


def materials_for(motif, faction, style_era_id):
    """Default materials: faction taste intersected with the era palette, else the era palette."""
    pal = era(style_era_id)["palette"]
    fav = [m for m in FACTIONS["factions"].get(faction, {}).get("materials", []) if m in pal]
    return fav or pal[:1]


def validate_dna(s):
    """Returns (ok, messages). PR-B1: advisory only; enforcement arrives in PR-C1."""
    d, msgs = s.get("dna"), []
    if not d:
        return True, []
    allowed = MOTIFS["type_map"].get(s["type"], [])
    if d.get("motif") and d["motif"] not in MOTIFS["motifs"]:
        msgs.append(f"{s['id']}: unknown motif {d['motif']}")
    elif allowed and d.get("motif") not in allowed:
        msgs.append(f"{s['id']}: motif {d.get('motif')} not allowed for type {s['type']} ({', '.join(allowed)})")
    if d.get("scale") and d["scale"] not in SCALES:
        msgs.append(f"{s['id']}: unknown scale {d['scale']}")
    if "ornament" in d and not 0 <= d["ornament"] <= 3:
        msgs.append(f"{s['id']}: ornament must be 0-3")
    return not msgs, msgs


def wonder_score(s, world=None):
    """0-5. PR-B1 placeholder: from scale and ornament only (sacredness arrives in PR-C3)."""
    m = motif_of(s)
    d = s.get("dna") or {}
    scale = d.get("scale") or (MOTIFS["motifs"][m]["scale"] if m else "domestic")
    base = {"domestic": 0, "civic": 1, "monumental": 2, "wonder": 4}[scale]
    return min(5, base + (1 if d.get("ornament", 0) >= 3 else 0))


def drift_style(world, af_year):
    """Style parameters for a year. PR-B1: the era's own values, no drift yet."""
    e = era(style_era(af_year))
    return {"era": e["id"], "palette": e["palette"], "ornament_max": e["ornament_max"], "tint": e["tint"]}
