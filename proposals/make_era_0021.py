"""Era AF 21-30 proposals: the first decade under the architectural grammar (PR-C1).
Real anchors (lat/lon -> to_xy): Hagia Sophia (first church, dedicated AD 360) 41.0086,28.9800 -> (672,455);
Baths of Constantius (Constantianae) near the Holy Apostles ~41.0170,28.9480 -> (448,378).
Pressure answered first: the AF 19 fire burned 124 houses at (552,338); then ambition: the city's first wonder."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_eras_v3 import B, rect  # noqa

era = {"era": {"from": 21, "to": 30, "title": "大教堂"}, "actions": [
 # pressure: the burned quarter by the Horn
 B("people", "r_firebreak", "road", "Street of the Embers", [[492, 347], [522, 346], [548, 347]],
   "After the fire of year 19 the people of the north slope cut a broad street through the ashes, so that flames could not leap from roof to roof again.",
   width=1.6, label="Street of the Embers", year=22),
 B("merchants", "market_embers", "market", "Market of the Embers", rect(552, 338, 10, 3, 0),
   "On the burned ground beside the Horn the merchants set up a covered row of shops instead of houses.",
   label="Embers Market", year=23, dna={"motif": "market_row", "materials": ["brick"], "ornament": 1, "scale": "civic"}),
 # ambition
 B("emperor", "baths_constantius", "baths", "Baths of Constantius", rect(448, 378, 8, 6, -20),
   "Now that the Great Aqueduct runs full, the emperor gives the fourth hill public baths, a domed hall beside the Holy Apostles.",
   label="Baths of Constantius", year=25, dna={"motif": "rotunda", "materials": ["brick", "marble_revetted"], "ornament": 2, "scale": "monumental"}),
 B("army", "tower_horn", "fort", "Tower of the Horn", rect(634, 373, 3, 3, 0),
   "A watchtower over the Neorion, where the Black Sea grain ships now lie.",
   label="Tower", year=24, dna={"motif": "tower", "materials": ["ashlar", "brick"], "ornament": 0, "scale": "civic"}),
 B("church", "church_megale", "church", "The Great Church", rect(673, 457, 13, 7, -8),
   "Beside the church of Holy Peace the bishops raise the Great Church, a timber-roofed basilica longer than any hall in the city. Its foundations are laid with blocks taken from the old Greek wall of Byzas, pulled down when the Founder's wall was built.",
   label="Great Church", year=30,
   dna={"motif": "basilica", "materials": ["brick", "marble_revetted"], "ornament": 3, "scale": "wonder"}, spolia_from=["wall_byzas"]),
]}
for a in era["actions"]:  # B() puts extra kwargs on the structure; the build year belongs to the action
    if "year" in a["structure"]:
        a["year"] = a["structure"].pop("year")
era["review"] = [{"round": 1, "rejected": [{"id": "market_embers", "reason": "footprint leaves dry land (3 sq units in water)",
                                           "fix": "moved 4 units inland, off the Horn's edge"}]}]
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era, open(os.path.join(d, "era_0021.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0021.json")
