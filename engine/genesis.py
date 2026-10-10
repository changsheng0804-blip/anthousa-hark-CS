"""Create the empty world (meta only). History starts with proposals/era_0000_byzas.json."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from world import save
save({"meta": {"name": "Anthousa", "name_zh": "安托萨", "seed": 330, "start_year": -657, "year": -657,
               "calendar": "AF = Anno Fundationis, years since the refounding"},
      "structures": [], "houses": [], "eras": []})
print("world.json created")
