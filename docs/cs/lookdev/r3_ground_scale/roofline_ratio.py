import json,math,statistics as st
import os;d=json.load(open(os.path.join(os.path.dirname(__file__),'../../../living/nodes/nangang/nodes.json')))
K=1/0.84
def roof(f):
    p=f['p'];cx=sum(p[0::2])/4;cz=sum(p[1::2])/4
    a=math.hypot(p[2]-p[0],p[3]-p[1])*.92;b=math.hypot(p[6]-p[0],p[7]-p[1])*.92
    H=max(3,(f.get('ht') or 5)*1.15);return cx,cz,H+min(a,b)/2*.42
LM={f['id']:f for f in d['features'] if f['t']=='landmark'}
def ctr(f):
    g=f['g'];return sum(q[0] for q in g)/len(g),sum(q[1] for q in g)/len(g)
def gran(scale):
    # tallest hall 18 + rise ~ bw/2*.46, bw ~ (2hu-4-(n-1)5)/n
    return 18*scale
cases={'forum_theodosius (column)':(65,61.8,61.8*1.4),'nymphaeum_maius':(60,22.2*K,(1.4+20.8*1.4)*K),
       'forum_theodosius (portico)':(65,8+1.8,8*1.2+1.8),'horrea_alexandrina':(60,18+3.8,18*1.2+3.8),'horrea_theodosius':(60,18+4.3,18*1.2+4.3)}
out={}
for name,(Y,h0,h1) in cases.items():
    f=LM[name.split(' ')[0]];cx,cz=ctr(f)
    R=[roof(h)[2] for h in d['features'] if h['t']=='house' and h['y0']<=Y and (h.get('y1') is None or h['y1']>Y) and math.hypot(roof(h)[0]-cx,roof(h)[1]-cz)<180]
    med=st.median(R);p90=sorted(R)[int(.9*len(R))]
    out[name]={'n_houses_180px':len(R),'roof_median_px':round(med,1),'roof_p90_px':round(p90,1),'before_px':round(h0,1),'after_px':round(h1,1),
      'before_m':round(h0*.84,1),'after_m':round(h1*.84,1),'ratio_median_before':round(h0/med,2),'ratio_median_after':round(h1/med,2),'ratio_p90_before':round(h0/p90,2),'ratio_p90_after':round(h1/p90,2)}
print(json.dumps(out,ensure_ascii=False,indent=1));json.dump(out,open(os.path.join(os.path.dirname(__file__),'ratio.json'),'w'),ensure_ascii=False,indent=1)
