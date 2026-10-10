"""Era AF 11-20 proposals. Real anchors (lat/lon -> to_xy): Holy Apostles 41.0195,28.9497;
Valens aqueduct bridge 41.0160,28.9555 -> 41.0151,28.9625; Neorion harbor 41.0170,28.9740; Philadelphion 41.0105,28.9560."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_eras_v3 import B, rect, R, to_xy  # noqa: reuses helpers (also rewrites era 0/1 identically)

def cross_shape(cx, cy, a, b, ang=0):
    pts = [(-b,-a),(b,-a),(b,-b),(a,-b),(a,b),(b,b),(b,a),(-b,a),(-b,b),(-a,b),(-a,-b),(-b,-b)]
    r = math.radians(ang); c, s = math.cos(r), math.sin(r)
    return [R((cx+x*c-y*s, cy+x*s+y*c)) for x, y in pts]

ax, ay = to_xy(41.0195, 28.9497)
from terrain import elevation
from shapely.geometry import LineString
from shapely.ops import substring
# route found by a search that minimises arcade length (see rules: aqueduct_arcade_rule)
AQ = [[140,250],[251,297],[384,296],[391,324],[519,389],[549,395],[575,405]]
def hanging(c, sag=6):
    g = LineString(c); e0, e1 = elevation(*c[0]), elevation(*c[-1]); n = int(g.length // 1); segs = []; cur = None
    for i in range(n + 1):
        f = i / n; p = g.interpolate(f, normalized=True)
        h = elevation(p.x, p.y) < e0 + (e1 - e0) * f - sag
        if h and cur is None: cur = f
        if not h and cur is not None: segs.append((cur, f)); cur = None
    if cur is not None: segs.append((cur, 1))
    return g, segs
_g, _segs = hanging(AQ)
_ARC = [("aqb_outer", "Arcade of the Springs", "Outer Arcade"), ("aqb_middle", "Arcade of the Wall", "Arcade"), ("aqb_valley", "Bridge of the Aqueduct", "Aqueduct Bridge")]
ARCADES = []
for (i, (a, b)) in enumerate(_segs):
    piece = substring(_g, max(0, a * _g.length - 2), min(_g.length, b * _g.length + 2))
    poly = [R(v) for v in list(piece.buffer(0.7, cap_style=2).simplify(0.3).exterior.coords)[:-1]]
    aid, name, lab = _ARC[i]
    ARCADES.append(B("emperor", aid, "aqueduct_bridge", name, poly,
        f"Where the ground falls away under the channel, an arcade of stone {round(piece.length*12, -1):.0f} m long carries it.", label=lab))

era = {"era": {"from": 11, "to": 20, "title": "引水入城"}, "actions": ARCADES + [
 B("emperor","aq_great","aqueduct","Great Aqueduct",AQ,
   "Water is the binding limit: the old channel and one cistern serve 43,000. A new channel from springs in the Thracian hills, 62 m above the sea, falls evenly to the third hill.",label="Great Aqueduct",label_at=[300,290]),
 B("emperor","nymphaeum_great","cistern","Great Nymphaeum",rect(579,409,6,4,10),
   "At the aqueduct's end a fountain house and reservoir feed the public fountains.",label="Nymphaeum"),
 B("people","r_mese_north","road","Northern Mese",[[504,447],[495,420],[480,390],[462,362]],
   "At the Philadelphion the Mese forks; the northern branch climbs to the fourth hill.",width=1.8,label="MESE BOREIA",label_at=[478,410]),
 B("church","church_apostles","church","Church of the Holy Apostles",cross_shape(ax, ay-4, 3.5, 1.1, 0),
   "A cross-shaped church on the fourth hill, raised as a mausoleum for the Founder.",label="Holy Apostles"),
 B("merchants","harbor_neorion","harbor","Neorion Harbor",[[610,352],[632,352],[632,370],[610,370]],
   "Ships from the Black Sea unload in the calm of the Horn, west of the old landing.",label="Neorion"),
 B("merchants","warehouse_horn","warehouse","Horrea of the Horn",rect(612,377,8,4,0),"Warehouses behind the new quay.",label="Horrea"),
 B("army","barracks_gate","barracks","Barracks of the Gate",rect(428,481,8,5,-10),"The guard of the land gate needs quarters.",label="Barracks"),
]}
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era, open(os.path.join(d, "era_0011.json"), "w"), ensure_ascii=False, indent=1)
print("written era_0011.json")
