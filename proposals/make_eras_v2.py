"""Writes era_0000 and era_0001 proposals at the calibrated scale (1 unit = 12 m)."""
import json, math
def rect(cx,cy,w,h,ang=0):
    a=math.radians(ang);c,s=math.cos(a),math.sin(a)
    return [[round(cx+x*c-y*s,1),round(cy+x*s+y*c,1)] for x,y in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]
def oval(cx,cy,rx,ry,n=24):
    return [[round(cx+rx*math.cos(2*math.pi*i/n),1),round(cy+ry*math.sin(2*math.pi*i/n),1)] for i in range(n)]
LINE={"road","wall","aqueduct","seawall"}
def B(f,id,t,name,coords,why,gt=None,label=None,**kw):
    st={"id":id,"type":t,"name":name,"geom":{"type":gt or ("line" if t in LINE else "polygon"),"coords":coords}}
    if label: st["label"]=label
    st.update(kw); return {"faction":f,"op":"build","structure":st,"why":why}
era0={"era":{"from":-657,"to":0,"title":"拜扎斯的旧城"},"no_events":True,"growth_floor":2600,"actions":[
 B("settlers","fort_acropolis","fort","Acropolis of Byzas",[[905,330],[935,328],[940,352],[912,358]],"Megarian settlers under Byzas fortify the headland.",label="Acropolis"),
 B("settlers","r_old_harbor","road","Harbor Lane",[[903,313],[897,350],[892,384]],"A lane climbs from the landing to the market.",width=1.5),
 B("merchants","harbor_prosphorion","harbor","Prosphorion Harbor",[[884,309],[884,286],[920,286],[922,312]],"The sheltered Horn becomes the town's landing.",label="Prosphorion"),
 B("settlers","r_acropolis","road","Acropolis Way",[[892,384],[905,368],[915,359]],"A path to the citadel gate.",width=1.5),
 B("settlers","r_south","road","South Lane",[[892,384],[892,420],[890,455]],"A lane towards the southern shore.",width=1.5),
 B("settlers","r_shore_n","road","Horn Lane",[[897,350],[875,330],[862,312]],"A lane along the Horn shore.",width=1.2),
 B("settlers","r_east","road","Lane of the Fishermen",[[892,420],[925,425],[945,440]],"A lane to the fishing coves.",width=1.2),
 B("settlers","gate_old_thracian","gate","Thracian Gate",rect(857,395,4,4),"The single landward gate."),
 B("settlers","r_west","road","Thracian Road",[[892,388],[870,393],[857,395],[830,400],[780,410],[720,420]],"The road to Thrace leaves through the landward gate.",width=1.8),
 B("settlers","wall_byzas","wall","Wall of Byzas",[[863,298],[858,340],[857,395],[861,470],[872,532]],"A wall of rough stone seals the headland."),
 B("settlers","agora_tetrastoon","forum","Agora (Tetrastoon)",rect(880,390,6,5,-8),"The market square where four porticoes meet.",label="Agora"),
 B("priests","temple_apollo","temple","Temple of Apollo",rect(932,400,4,3),"A temple raised to the god of the oracle that sent them.",label="Temple of Apollo"),
 B("settlers","aq_hadrian","aqueduct","Old Aqueduct",[[560,430],[640,410],[740,395],[820,385],[870,378]],"A Roman governor brings water from the western hills in a channel.",label="Old Aqueduct",capacity=20000),
 B("settlers","d_byzas","district","Old Byzas",[[864,300],[960,312],[962,480],[915,530],[872,540],[860,470],[858,340]],"Houses crowd the slopes inside the wall.",label="BYZAS"),
]}
era1={"era":{"from":1,"to":10,"title":"重新奠基"},"actions":[
 {"faction":"emperor","op":"demolish","id":"wall_byzas","why":"The old wall is too small for an imperial city; its stones go into the new one."},
 {"faction":"emperor","op":"demolish","id":"gate_old_thracian","why":"The old gate falls with its wall."},
 B("emperor","gate_founder","gate","Gate of the Founder",rect(622,446,4,4),"Where the Mese passes the new wall."),
 B("emperor","wall_founder","wall","Wall of the Founder",[[628,256],[625,330],[621,420],[622,446],[621,500],[618,590]],"The Founder walks the line of the new wall with a spear, 'until he who walks before me stops.'"),
 B("emperor","r_mese","road","The Mese",[[870,394],[845,401],[818,414],[790,419],[760,425],[720,420],[700,430],[660,440],[622,446],[560,452]],"The Middle Street, 25 metres wide between porticoes, runs from the Milion to the land gate.",width=2.1,label="MESE",label_at=[690,427]),
 B("emperor","forum_founder","forum","Forum of the Founder",oval(818,414,7,6),"An oval forum of marble porticoes on the Mese, six hundred metres from the Milion.",label="Forum of the Founder"),
 B("emperor","col_founder","column","Column of the Founder",[818,414],"A porphyry column carries the Founder's statue.",gt="point"),
 B("emperor","milion","monument","Milion",rect(868,401,1.4,1.4),"The milestone from which every road of the empire is measured.",label="Milion"),
 B("emperor","palace_great","palace","Great Palace",[[880,468],[915,462],[920,494],[886,500]],"Terraces of the palace step down towards the sea.",label="Great Palace"),
 B("emperor","r_palace","road","Palace Approach",[[890,455],[892,462]],"The lane ends at the palace gate.",width=1.5),
 B("people","r_hippo","road","Street of the Charioteers",[[845,401],[842,440],[846,470]],"A street drops from the Mese towards the race course.",width=1.5),
 B("people","hippodrome","hippodrome","Hippodrome",rect(848,488,37.5,10.8,-18),"450 metres of race track beside the palace; the city will love and riot here.",label="Hippodrome"),
 B("church","church_peace","church","Church of Holy Peace",rect(878,350,8,4,-5),"The first great church rises beside the old citadel.",label="Holy Peace"),
 B("merchants","r_harbor_south","road","Harbor Street",[[760,425],[768,490],[788,552]],"A street drops from the Mese to the new southern harbor.",width=1.5),
 B("merchants","harbor_julian","harbor","Harbor of Julian",[[772,553],[805,551],[808,588],[770,590]],"Moles of rubble enclose a harbor on the inland sea.",label="Harbor of Julian"),
 B("emperor","granary_founder","granary","Granary of the Founder",rect(790,538,8,5,-4),"Egyptian grain needs a home.",label="Granary"),
 B("emperor","cistern_founder","cistern","Cistern of the Founder",rect(805,430,5.3,4.7,-6),"A covered cistern under brick vaults.",label="Cistern"),
 B("people","r_north1","road","Street of the Coppersmiths",[[812,409],[800,350],[790,284]],"A street runs north from the forum to the Horn.",width=1.2),
 B("people","r_north2","road","Street of the Lamps",[[845,401],[838,340],[846,302]],"Another street climbs north.",width=1.2),
 B("people","r_north3","road","Street of the Potters",[[720,420],[715,350],[722,272]],"A street through the new northern quarter.",width=1.2),
 B("people","r_west_n","road","Lane of the Wells",[[660,440],[650,380],[655,265]],"A lane along the inside of the new wall.",width=1.2),
 B("people","r_west_s","road","Lane of the Gardeners",[[660,440],[665,510],[660,585]],"Gardens give way to houses.",width=1.2),
 B("people","r_south2","road","Street of the Ropemakers",[[720,420],[715,500],[712,585]],"A street down to the southern shore.",width=1.2),
 B("people","d_forum","district","Region of the Forum",[[628,260],[860,300],[862,398],[628,440]],"Settlers from Asia and Thrace build north of the Mese.",label="REGIO FORI"),
 B("people","d_harbor","district","Region of the Harbor",[[628,450],[862,404],[870,470],[842,548],[625,590]],"Sailors and porters settle by the new harbor.",label="REGIO PORTUS"),
]}
json.dump(era0,open("proposals/era_0000_byzas.json","w"),ensure_ascii=False,indent=1)
json.dump(era1,open("proposals/era_0001.json","w"),ensure_ascii=False,indent=1)
