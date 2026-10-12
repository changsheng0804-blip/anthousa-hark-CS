"""居民请愿草案 · 建城 61–70 年（AD 390–399）· 刘线 liu3 —— 草案，不进 proposals/，不改正史。
Draft petitions of the Xerolophos residents for the era AF 61-70, written from the pressures counted by tools/petitions.py
(see pressures.json and README.md in this folder). Same format as proposals/era_NNNN.json (era / actions / review), built
with the same helpers as proposals/make_era_0051.py, so that the owner (or the next heartbeat) can paste any of them into
proposals/make_era_0061.py as the people's share of the decade. Every action is faction "people".
Each petition is written to its own file petition_N_<slug>.json; all five together to petitions_all.json.
i18n_additions.json holds the Chinese names/labels the ledger would need (i18n/ is not touched).
Run: python3 drafts/proposals_af61_70/make_petitions.py   (from the repo root)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "engine"))
import math
from shapely.geometry import LineString
from terrain import land
# same helpers as proposals/make_eras_v3.py (copied, because importing it rewrites era_0000/era_0001 as a side effect)
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

ERA = {"from": 61, "to": 70}
P = [
 ("water", "坡上的第二口池子", [
  B("people", "r_carriers", "road", "Carriers' Steps", [[440, 463], [440, 428]],
    "A stepped lane from the Mese straight up the middle of the hill, so a carrier no longer threads between houses with a full jar.",
    width=1.2, year=62),
  B("people", "cistern_slope", "cistern", "Second Cistern of the Water-Carriers", rect(440, 425, 6, 5, 0),
    "The water-carriers' first cistern (AF 54) sits at the foot of the hill and the queue there runs till dark; "
    "the families of the upper slope pool their coppers again for a second cistern at the head of the new steps.",
    label="Carriers II", year=62, dna={"motif": "cistern", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 ], [{"round": 1, "rejected": [{"id": "cistern_slope", "reason": "no road within 25 units; nobody could reach it",
      "fix": "the Carriers' Steps are listed first, so the lane exists when the cistern is judged"}]}]),
 ("crowd", "城墙外的新街坊", [
  B("people", "r_exo", "road", "Lane of the Newcomers", [[398, 473], [392, 450], [386, 430]],
    "A lane leaves the Mese just outside the Founder's gate and climbs north along the wall.", width=1.2, year=63),
  B("people", "d_exokionion", "district", "Exokionion", [[370, 425], [404, 425], [400, 500], [366, 505]],
    "Grown sons with nowhere to sleep and the families still coming off the grain ships build outside the Founder's wall, "
    "along the Mese and the new lane, where the Arians already walk on feast days.",
    label="EXOKIONION", year=63),
 ], []),
 ("fire", "横穿干山的防火巷", [
  B("people", "r_firebreak_hill", "road", "Firebreak of the Dry Hill", [[421, 464], [430, 430], [441, 404], [456, 388], [466, 369]],
    "The families burned out of the South Harbor in AF 48 rebuilt wall to wall on the hill. They ask for a lane cut "
    "from the Mese to the Modestus road, wide enough that a fire cannot jump it, and give up the houses in its way.",
    width=2.0, year=61),
 ], [{"round": 1, "rejected": [{"id": "r_firebreak", "reason": "r_firebreak: id already used (the Street of the Embers, AF 22)",
      "fix": "renamed r_firebreak_hill"}]}]),
 ("faith", "城外的砖礼拜堂", [
  B("people", "church_arian_brick", "church", "Arian Church outside the Gate", rect(394, 466, 6, 4, 0),
    "For ten years the Arians of the hill have prayed in a timber yard beyond the wall, and their priests will not "
    "come into the city even to bless a sick child. They raise a small brick church outside the Founder's gate.",
    label="Arian church", year=64, dna={"motif": "basilica", "materials": ["brick"], "ornament": 1, "scale": "civic"}),
 ], []),
 ("widow", "孤寡院", [
  B("people", "xenon_xerolophos", "monastery", "House of the Widows and Orphans", rect(444, 453, 5, 4, 0),
    "On the hill one household in seven has no grown man left and small children at home. Neighbours and the monks "
    "who took in their sons build a house where widows bake for the street and orphans learn a trade.",
    label="Widows' house", year=65, dna={"motif": "monastery", "materials": ["brick"], "ornament": 0, "scale": "domestic"}),
 ], []),
]
I18N = {"names_zh": {"cistern_slope": "运水人第二蓄水池", "r_carriers": "运水人石阶", "r_exo": "新来人巷",
                     "d_exokionion": "城墙外新区", "r_firebreak_hill": "干山防火巷", "church_arian_brick": "城门外阿里乌派礼拜堂",
                     "xenon_xerolophos": "干山孤寡院"},
        "labels_zh": {"cistern_slope": "运水人二池", "d_exokionion": "城墙外新区", "church_arian_brick": "阿里乌派礼拜堂",
                      "xenon_xerolophos": "孤寡院"}}


def era_file(title, actions, review=()):
    acts = json.loads(json.dumps(actions))
    for a in acts:
        if "year" in a["structure"]:
            a["year"] = a["structure"].pop("year")
    return {"era": {**ERA, "title": title}, "actions": acts, "review": list(review)}


if __name__ == "__main__":
    for i, (slug, title, acts, review) in enumerate(P, 1):
        json.dump(era_file(title, acts, review), open(os.path.join(HERE, f"petition_{i}_{slug}.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(era_file("干山上的请愿", [a for _, _, acts, _ in P for a in acts],
                       [{"round": 1, "rejected": [x for _, _, _, rv in P for r in rv for x in r["rejected"]]}]),
              open(os.path.join(HERE, "petitions_all.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(I18N, open(os.path.join(HERE, "i18n_additions.json"), "w"), ensure_ascii=False, indent=1)
    print("written", len(P), "petitions + petitions_all.json + i18n_additions.json")
