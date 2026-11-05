# 只有色差、没有错位的缝：不重画，做「缝两侧低频色平移」。
#   两侧各取缝边 96px 带里的严格空地（离房子 >8px、离街 >5px、非树非水）求 Lab 中位，差值 d 一半加给一侧、一半减给另一侧，
#   权重从缝上 1 线性降到 192px 外 0，沿缝两端各 64px 收口；只动陆地、不动盖章的水和纸。改完重新量这条缝，变好才留。
# 补丁边（seamfix 补丁块的四条边，渐变带正中）也照此处理。
# 用法（工作目录 = 原始件目录）：python3 nangang_seamlevel.py canvas.png gate.json → 覆盖 canvas.png，打印每条缝前后
import numpy as np,cv2,json,sys,os
from PIL import Image
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from nangang_seamfix import meas,DE_MAX
f,gj=sys.argv[1],sys.argv[2]
C=np.asarray(Image.open(f).convert('RGB')).copy()
ld=lambda p:np.asarray(Image.open(p).convert('L'))>127
L=ld('mask_land.png');Hs=ld('ledger_houses.png');St=ld('ledger_streets.png');Wf=ld('mask_waterfill.png');M=ld('ledger_mapx.png')
dist=lambda m:cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,5)
G0=L&(dist(Hs)>8)&(dist(St)>5)
R=192;B=96;TAP=64
def geom(r):
    """接缝 → (方向, 线位置, 起, 止)；补丁边直接用 at/span"""
    if 'at' in r:return r['dir'],r['at'],r['span'][0],r['span'][1]
    x,y=r['a']
    return ('V',512*(x+1),512*y,512*y+512) if r['dir']=='V' else ('H',512*(y+1),512*x,512*x+512)
def one(C,r):
    d,c,s0,s1=geom(r)
    if d=='V':ys=slice(s0,s1);xs=slice(c-R,c+R)
    else:xs=slice(s0,s1);ys=slice(c-R,c+R)
    sub=C[ys,xs];g=G0[ys,xs];l=L[ys,xs]&~Wf[ys,xs]&M[ys,xs]
    if d=='H':sub=sub.transpose(1,0,2);g=g.T;l=l.T
    lab=cv2.cvtColor(np.ascontiguousarray(sub),cv2.COLOR_RGB2LAB).astype(np.float32)
    a=sub.astype(int);gg=g&~(a[...,1]>a[...,0]+8)&~(a[...,2]>a[...,0]+12)
    A=gg[:,R-B:R];Bm=gg[:,R:R+B]
    if A.sum()<1500 or Bm.sum()<1500:return C,None
    dlt=np.median(lab[:,R-B:R][A],0)-np.median(lab[:,R:R+B][Bm],0)
    n=sub.shape[0];prof=np.clip(1-np.abs(np.arange(2*R)-R+0.5)/R,0,1);sgn=np.where(np.arange(2*R)<R,-0.5,0.5)
    along=np.clip(np.minimum(np.arange(n),n-1-np.arange(n))/TAP,0,1)
    w=(along[:,None]*prof[None,:]*sgn[None,:])[...,None]*l[...,None]
    out=cv2.cvtColor(np.clip(lab+w*dlt[None,None,:],0,255).astype(np.uint8),cv2.COLOR_LAB2RGB)
    out=np.where(l[...,None],out,sub)
    if d=='H':out=out.transpose(1,0,2)
    C2=C.copy();C2[ys,xs]=out;return C2,dlt
def score(C,r):
    d,c,s0,s1=geom(r)
    if d=='V':sl=C[s0:s1,c-64:c+64];Ls=L[s0:s1,c-64:c+64]
    else:sl=C[c-64:c+64,s0:s1].transpose(1,0,2).copy();Ls=L[c-64:c+64,s0:s1].T.copy()
    return meas(cv2.cvtColor(sl,cv2.COLOR_RGB2LAB).astype(float),Ls,64,slice(0,s1-s0))
J=json.load(open(gj));log=[]
for r in J['failing']+J['failing_patch_edge_list']:
    if r['colour_dE'] is None or r['colour_dE']<=DE_MAX or r['edge_ratio']>1.6:continue
    b=score(C,r);C2,dlt=one(C,r)
    if dlt is None:continue
    a=score(C2,r);keep=a is not None and (a['colour_dE'] or 0)<(b['colour_dE'] or 0) and a['edge_ratio']<=max(b['edge_ratio'],1.6)
    if keep:C=C2
    log.append({'line':(r['dir'],r['a']) if 'a' in r else (r['dir'],r['at'],r['span'],'patch '+r['seam']+' '+r['side']),'delta_Lab':np.round(dlt,1).tolist(),'before':b,'after':a,'kept':bool(keep)});print(log[-1])
Image.fromarray(C).save(f);json.dump(log,open('seamlevel_log.json','w'),indent=1)
