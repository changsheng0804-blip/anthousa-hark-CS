"""Era AF 41-50 proposals (AD 370-379, Valens). At AF 40 the city held 96,417 people against food 153,202 and water 158,000;
both ceilings bind within the decade. Real anchors (lat/lon -> to_xy): Cistern of Modestus (AD 369, near the Holy Apostles,
approx. 41.0195,28.9455) -> (430,355), which falls just outside our approximate Founder's wall, so the cistern sits ~200 m east at (447,363); Nymphaeum Maius of Valens at the Forum Tauri (AD 373, 41.0106,28.9640) -> (560,437);
Horrea Troadensia on the Golden Horn (approx. 41.0150,28.9720) -> (616,396); Anastasia, Gregory of Nazianzus' house chapel
(AD 379, approx. 41.0075,28.9700) -> (602,465). Positions of Modestus and the Troadensia are scholarly estimates.
Drafts that informed this era: draft/exp-growth-* (growth-cap forecast) and draft/historical; this file is hand-written."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_eras_v3 import B, rect  # noqa

era = {"era": {"from": 41, "to": 50, "title": "瓦伦斯的水"}, "actions": [
 B("emperor", "cistern_modestus", "cistern", "Cistern of Modestus", rect(447, 363, 9, 7, 0),
   "The prefect Modestus digs an open reservoir beside the Holy Apostles, fed from the Great Aqueduct before it enters the city.",
   label="Modestus", year=41, dna={"motif": "cistern", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 B("people", "d_xerolophos", "district", "Xerolophos quarter", [[437, 370], [452, 370], [452, 462], [416, 466]],
   "Between the Founder's wall and the old forum quarter the dry seventh hill fills with houses.", year=42),
 B("emperor", "nymphaeum_maius", "monument", "Nymphaeum Maius", rect(556, 432, 5, 3, -10),
   "Valens finishes the aqueduct's showpiece: a great fountain on the Forum Tauri where the water is seen to arrive.",
   label="Nymphaeum Maius", year=44, dna={"motif": "rotunda", "materials": ["brick", "marble_revetted"], "ornament": 3, "scale": "monumental"}),
 B("merchants", "horrea_troadensia", "granary", "Horrea Troadensia", rect(618, 392, 9, 4, -5),
   "Granaries on the Golden Horn for the grain ships from the Troad, behind the Neorion quays.",
   label="Troadensia", year=46, dna={"motif": "basilica", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 B("church", "church_anastasia", "church", "Anastasia", rect(603, 466, 4, 3, 0),
   "In a house chapel south of the Mese, Gregory of Nazianzus preaches to the Nicene remnant; the chapel is called Anastasia, the resurrection.",
   label="Anastasia", year=49, dna={"motif": "basilica", "materials": ["brick"], "ornament": 1, "scale": "domestic"}),
]}
for a in era["actions"]:
    if "year" in a["structure"]:
        a["year"] = a["structure"].pop("year")
era["review"] = [{"round": 1, "rejected": [{"id": "cistern_modestus", "reason": "no road within 25 units; nobody could reach it",
                                           "fix": "a lane was tried next, but it crossed the Founder's wall with no gate: the site was outside the wall. Moved inside, beside the end of the northern Mese"}]}]
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era, open(os.path.join(d, "era_0041.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0041.json")
