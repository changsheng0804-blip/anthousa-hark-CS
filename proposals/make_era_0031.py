"""Era AF 31-40 proposals: the grain decade. Pop 66,420 against a food ceiling of 108,000 at AF 30.
Real anchors (lat/lon -> to_xy): Harbor of Theodosius / Eleutherios (Yenikapi) 41.0045,28.9500 -> (462,493), but that
site now lies under modern landfill, so the harbor sits on today's shore ~200 m east-south-east at (480,524);
St Mocius 41.0105,28.9380 -> (378,438). The extramural Mese continues west as the Via Egnatia.
Farmland (rules from AF 31) is fields outside the Founder's wall; at ~1.5 people/ha it adds only a margin."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_eras_v3 import B, rect  # noqa

era = {"era": {"from": 31, "to": 40, "title": "粮道"}, "actions": [
 B("people", "r_egnatia", "road", "Via Egnatia", [[360, 480], [300, 486], [250, 492]],
   "Beyond the Founder's gate the Mese becomes the old road west to Thessalonica; carts from the farms come in along it.",
   width=1.6, label="VIA EGNATIA", year=31),
 B("merchants", "harbor_theodosius", "harbor", "Harbor of Theodosius", rect(480, 524, 22, 14, 0),
   "The Egyptian grain fleet needs a harbor on the Marmara shore big enough for the whole convoy; the merchants dig one west of the Julian harbor.",
   label="Harbor of Theodosius", year=33),
 B("emperor", "horrea_theodosius", "granary", "Horrea of Theodosius", rect(478, 505, 10, 5, 0),
   "Behind the new harbor the emperor builds state granaries for the annona, the free bread of the city.",
   label="Horrea", year=34, dna={"motif": "basilica", "materials": ["brick"], "ornament": 1, "scale": "civic"}),
 B("church", "r_mocius", "road", "Lane of St Mocius", [[372, 479], [377, 442]],
   "A lane from the Mese up to the martyr's grave.", width=1.0, year=35),
 B("church", "church_mocius", "church", "Church of St Mocius", rect(378, 438, 5, 3, -5),
   "Among the fields outside the wall the church raises a basilica over the grave of the martyr Mocius.",
   label="St Mocius", year=35, dna={"motif": "basilica", "materials": ["brick"], "ornament": 2, "scale": "civic"}),
 B("people", "field_north", "farmland", "Fields of the Lycus", [[268, 404], [300, 398], [338, 401], [362, 408], [362, 461], [330, 463], [296, 466], [266, 458], [261, 430]],
   "Farmers clear the gentle ground north of the Egnatia for wheat and barley.",
   label="Fields", year=32),
 B("people", "field_south", "farmland", "Fields of the Egnatia", [[300, 470], [340, 468], [384, 467], [386, 488], [378, 506], [345, 511], [312, 507], [294, 492]],
   "South of the road the slope is gentler still; market gardens and grain strips run down toward the sea.",
   year=32),
]}
for a in era["actions"]:  # B() puts extra kwargs on the structure; the build year belongs to the action
    if "year" in a["structure"]:
        a["year"] = a["structure"].pop("year")
era["review"] = [{"round": 1, "rejected": [{"id": "church_mocius", "reason": "no road within 25 units; nobody could reach it",
                                           "fix": "the church adds a lane from the Mese to the grave; the northern fields leave a strip for it"}]}]
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era, open(os.path.join(d, "era_0031.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0031.json")
