"""Era 0 and era 1 proposals on the real-geography terrain (v3). Coordinates come from real
landmark positions (lat/lon) projected with terrain.to_xy; lines and districts are clipped to land."""
import json, math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
from terrain import land, to_xy, elevation
from shapely.geometry import LineString, Polygon, Point
L = land()
def R(v): return [round(v[0], 1), round(v[1], 1)]
def clipline(c):
    g = LineString(c).intersection(L.buffer(-0.8))
    parts = list(getattr(g, "geoms", [g]))
    return [R(p) for p in max(parts, key=lambda p: p.length).coords]
def clippoly(c, inside):
    g = Polygon(c).intersection(L.buffer(-0.7))
    parts = list(getattr(g, "geoms", [g]))
    p = [q for q in parts if q.geom_type == "Polygon" and q.contains(Point(inside))][0]
    p = p.simplify(0.5)
    return [R(v) for v in list(p.exterior.coords)[:-1]]
def rect(cx,cy,w,h,ang=0):
    a=math.radians(ang);c,s=math.cos(a),math.sin(a)
    return [R((cx+x*c-y*s,cy+x*s+y*c)) for x,y in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]
def oval(cx,cy,rx,ry,n=24):
    return [R((cx+rx*math.cos(2*math.pi*i/n),cy+ry*math.sin(2*math.pi*i/n))) for i in range(n)]
LINE={"road","wall","aqueduct"}
def B(f,id,t,name,coords,why,gt=None,label=None,**kw):
    if t in LINE: coords = clipline(coords)
    st={"id":id,"type":t,"name":name,"geom":{"type":gt or ("line" if t in LINE else "polygon"),"coords":coords}}
    if label: st["label"]=label
    st.update(kw); return {"faction":f,"op":"build","structure":st,"why":why}
def cross(a, b):
    p = LineString(a).intersection(LineString(b)); return R((p.x, p.y))

SEVERAN = clipline([[624,370],[656,525]])
MESE = [[654,458],[640,456],[611,454],[585,447],[560,438],[530,441],[490,450],[450,460],[400,472],[360,480]]
FOUNDER_WALL = clipline([[462,250],[388,580]])
g_old = cross(SEVERAN, [[660,447],[654,452],[641,456],[620,456]])
g_new = cross(FOUNDER_WALL, MESE)
HIPPO_C, HIPPO_ANG = (641, 477.5), math.degrees(math.atan2(27, -20))

era0={"era":{"from":-657,"to":0,"title":"拜扎斯的旧城"},"no_events":True,"growth_floor":2600,"actions":[
 B("settlers","fort_acropolis","fort","Acropolis of Byzas",[[688,418],[710,416],[712,437],[690,441]],"Megarian settlers under Byzas fortify the headland.",label="Acropolis"),
 B("merchants","harbor_prosphorion","harbor","Prosphorion Harbor",[[640,389],[640,370],[668,370],[668,389]],"The sheltered Horn becomes the town's landing.",label="Prosphorion"),
 B("settlers","r_old_harbor","road","Harbor Lane",[[652,392],[655,420],[660,447]],"A lane climbs from the landing to the market.",width=1.5),
 B("settlers","r_acropolis","road","Acropolis Way",[[660,447],[675,441],[685,437]],"A path to the citadel gate.",width=1.5),
 B("settlers","r_south","road","South Lane",[[660,447],[662,470]],"A lane towards the southern slope.",width=1.5),
 B("settlers","r_east","road","Lane of the Fishermen",[[662,462],[690,465],[708,474]],"A lane to the fishing coves.",width=1.2),
 B("settlers","gate_old_thracian","gate","Thracian Gate",rect(*g_old,4,4),"The single landward gate."),
 B("settlers","r_west","road","Thracian Road",[[660,447],[654,452],[641,456],[620,456],[600,451],[560,439]],"The road to Thrace leaves through the landward gate.",width=1.8),
 B("settlers","wall_byzas","wall","Wall of Byzas",SEVERAN,"A wall of rough stone seals the headland."),
 B("settlers","agora_tetrastoon","forum","Agora (Tetrastoon)",rect(666,452,6,5,-8),"The market square where four porticoes meet.",label="Agora"),
 B("priests","temple_apollo","temple","Temple of Apollo",rect(716,442,4,3),"A temple raised to the god of the oracle that sent them.",label="Temple of Apollo"),
 B("settlers","aq_hadrian","aqueduct","Old Aqueduct",[[200,205],[300,290],[400,350],[480,395],[560,432],[636,450]],"A Roman governor brings water from the western hills in a channel.",label="Old Aqueduct",capacity=20000),
 B("settlers","d_byzas","district","Old Byzas",clippoly([[632,380],[700,365],[740,400],[740,470],[700,510],[660,525],[644,470]],(690,455)),"Houses crowd the slopes inside the wall.",label="BYZAS"),
]}
era1={"era":{"from":1,"to":10,"title":"重新奠基"},"actions":[
 {"faction":"emperor","op":"demolish","id":"wall_byzas","why":"The old wall is too small for an imperial city; its stones go into the new one."},
 {"faction":"emperor","op":"demolish","id":"gate_old_thracian","why":"The old gate falls with its wall."},
 B("emperor","gate_founder","gate","Gate of the Founder",rect(*g_new,4,4),"Where the Mese passes the new wall."),
 B("emperor","wall_founder","wall","Wall of the Founder",FOUNDER_WALL,"The Founder walks the line of the new wall with a spear, 'until he who walks before me stops.'"),
 B("emperor","r_mese","road","The Mese",MESE,"The Middle Street, 25 metres wide between porticoes, runs from the Milion to the land gate.",width=2.1,label="MESE",label_at=[515,436]),
 B("emperor","forum_founder","forum","Forum of the Founder",oval(611,454,7,6),"An oval forum of marble porticoes on the Mese, about six hundred metres from the Milion.",label="Forum of the Founder"),
 B("emperor","col_founder","column","Column of the Founder",[611,454],"A porphyry column carries the Founder's statue.",gt="point"),
 B("emperor","milion","monument","Milion",rect(654,459.5,1.4,1.4),"The milestone from which every road of the empire is measured.",label="Milion"),
 B("emperor","palace_great","palace","Great Palace",[[662,478],[684,473],[692,497],[666,505]],"Terraces of the palace step down towards the sea.",label="Great Palace"),
 B("people","r_hippo","road","Street of the Charioteers",[[645,456],[648,460]],"A short street from the Mese to the starting gates.",width=1.5),
 B("people","hippodrome","hippodrome","Hippodrome",rect(*HIPPO_C,37.5,10.8,HIPPO_ANG),"450 metres of race track beside the palace; the city will love and riot here.",label="Hippodrome"),
 B("church","church_peace","church","Church of Holy Peace",rect(681,451,8,4,-5),"The first great church rises beside the old citadel.",label="Holy Peace"),
 B("merchants","r_harbor_south","road","Harbor Street",[[585,447],[576,480],[569,505]],"A street drops from the Mese to the new southern harbor.",width=1.5),
 B("merchants","harbor_julian","harbor","Harbor of Julian",[[553,507],[586,507],[586,532],[553,532]],"Moles of rubble enclose a harbor on the inland sea.",label="Harbor of Julian"),
 B("emperor","granary_founder","granary","Granary of the Founder",rect(585,496,8,5,-4),"Egyptian grain needs a home.",label="Granary"),
 B("emperor","cistern_founder","cistern","Cistern of the Founder",rect(624,468,5.3,4.7,-6),"A covered cistern under brick vaults.",label="Cistern"),
 B("people","r_north1","road","Street of the Coppersmiths",[[608,449],[604,410],[600,360]],"A street runs north from the forum to the Horn.",width=1.2),
 B("people","r_north2","road","Street of the Lamps",[[560,438],[552,400],[548,340]],"Another street climbs north.",width=1.2),
 B("people","r_north3","road","Street of the Potters",[[490,450],[488,400],[492,320]],"A street through the new northern quarter.",width=1.2),
 B("people","r_west_s","road","Lane of the Gardeners",[[490,450],[495,500],[500,560]],"Gardens give way to houses.",width=1.2),
 B("people","r_south2","road","Street of the Ropemakers",[[530,441],[532,490],[535,540]],"A street down to the southern shore.",width=1.2),
 B("people","d_forum","district","Region of the Forum",clippoly([[455,240],[632,240],[632,452],[450,462]],(550,420)),"Settlers from Asia and Thrace build north of the Mese.",label="REGIO FORI"),
 B("people","d_harbor","district","Region of the Harbor",clippoly([[450,466],[632,458],[640,540],[420,580]],(550,480)),"Sailors and porters settle by the new harbor.",label="REGIO PORTUS"),
]}
print("aq elev", round(elevation(120,420)), round(elevation(636,450)), "gates", g_old, g_new, "founder wall", FOUNDER_WALL[0], FOUNDER_WALL[-1])
d = os.path.dirname(os.path.abspath(__file__))
json.dump(era0,open(os.path.join(d,"era_0000_byzas.json"),"w"),ensure_ascii=False,indent=1)
json.dump(era1,open(os.path.join(d,"era_0001.json"),"w"),ensure_ascii=False,indent=1)
