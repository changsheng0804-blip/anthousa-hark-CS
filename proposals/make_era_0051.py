"""Era AF 51-60 (AD 380-389, Theodosius I). At AF 50 the city held 137,664 people against food 173,202 and water 173,000.
This era is the first written people-first: each structure answers a need of the people living in the painted quarters
(docs/living/): the burned lots of the AF 48 fire, the water-carriers of the Xerolophos, the Arians put out of the city's
churches in 380-381, the grain merchants. Real anchors: Edict of Thessalonica (380) and the Council of Constantinople (381)
hand the churches to the Nicenes and send the Arians to meet outside the walls; Horrea Alexandrina stood by the Harbor of Theodosius (position approximate); Forum of Theodosius laid out on the Forum Tauri from AD 386.
The Cistern of the Water-Carriers is invented for Anthousa. Hand-written by Hark."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_eras_v3 import B, rect  # noqa

era = {"era": {"from": 51, "to": 60, "title": "城外的礼拜"}, "actions": [
 B("people", "arian_meeting", "church", "Arian meeting house", rect(403, 476, 4, 3, 0),
   "Put out of the city's churches by the new emperor, the Arians walk out through the Founder's gate on feast days and pray in a yard beyond the wall.",
   label="Arians", year=52, dna={"motif": "basilica", "materials": ["timber"], "ornament": 0, "scale": "domestic"}),
 B("people", "cistern_carriers", "cistern", "Cistern of the Water-Carriers", rect(432, 452, 7, 5, 0),
   "The water-carriers of the dry hill pool their coppers for a cistern halfway up the slope, so they no longer climb from Modestus with every jar.",
   label="Carriers", year=54, dna={"motif": "cistern", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 B("merchants", "horrea_alexandrina", "granary", "Horrea Alexandrina", rect(492, 511, 9, 4, 0),
   "Grain merchants buy the burned lots by the Harbor of Theodosius and raise a granary for the Egyptian ships.",
   label="Alexandrina", year=55, dna={"motif": "basilica", "materials": ["brick"], "ornament": 0, "scale": "civic"}),
 B("emperor", "forum_theodosius", "forum", "Forum of Theodosius", rect(546, 440, 10, 8, 0),
   "Theodosius lays out a great forum on the Forum Tauri, beside the fountain where Valens' water arrives.",
   label="Forum of Theodosius", year=57, dna={"motif": "peristyle", "materials": ["marble_revetted"], "ornament": 3, "scale": "monumental"}),
]}
for a in era["actions"]:
    if "year" in a["structure"]:
        a["year"] = a["structure"].pop("year")
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era, open(os.path.join(d, "era_0051.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0051.json")
era["review"] = [{"round": 1, "rejected": [
 {"id": "cistern_carriers", "reason": "no road within 25 units; nobody could reach it", "fix": "moved down the slope beside the Mese, near the Founder's gate"},
 {"id": "horrea_alexandrina", "reason": "overlaps the standing Horrea of Theodosius (AF 34)", "fix": "moved east onto the burned lots"}]}]
json.dump(era, open(os.path.join(d, "era_0051.json"), "w"), ensure_ascii=False, indent=1)
