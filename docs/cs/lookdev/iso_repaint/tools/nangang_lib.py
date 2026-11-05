# 南港全图重绘：共用的遮罩、水面盖章、窗口输入拼图、对齐、保真核对、回填。工作目录 = 原始件目录（仓库外）。
import numpy as np,json,os,cv2
from PIL import Image
from scipy import ndimage as nd
WATER=np.array([86,150,152],float)   # 平的马尔马拉蓝绿（输入里的水）
PAPER=np.array([238,231,214],float)  # 区外底色
def load(f):return np.asarray(Image.open(f).convert('L'))>127
def prep():
    M=load('ledger_mapx.png');W0=load('ledger_water.png')&M;H,Wd=M.shape
    lab,n=nd.label(W0);keep=np.zeros(n+1,bool)
    for k,sl in enumerate(nd.find_objects(lab),1):
        sz=(lab[sl]==k).sum();cy=(sl[0].start+sl[0].stop)/2
        keep[k]=sz>100000 and cy>H*0.45          # 去掉地图北/东边缘那条被误算成水的窄带
    W=keep[lab];R=np.asarray(Image.open('render_full.png').convert('RGB')).astype(int)
    obj=W&(R[...,0]>R[...,1]+4)                     # 水上的东西（栈桥、船、起重架）：渲染里不是蓝绿
    obj=nd.binary_opening(obj,iterations=1);lab2,n2=nd.label(obj);sz=nd.sum(obj,lab2,range(1,n2+1))
    obj=np.isin(lab2,1+np.where(sz>25)[0]);obj=nd.binary_dilation(obj,iterations=3)&W
    Wf=W&~obj;L=M&~W
    for k,a in (('water',W),('waterfill',Wf),('obj',obj),('land',L)):Image.fromarray((a*255).astype(np.uint8)).save(f'mask_{k}.png')
    # 一种统一的水面：底色 + 全局坐标里的轻波纹 + 近岸浅色带 + 一像素岸线
    yy,xx=np.mgrid[0:H,0:Wd].astype(np.float32)
    rip=np.sin(xx*0.11+yy*0.19)*np.sin(xx*0.023-yy*0.041)*0.5+np.sin(xx*0.052+yy*0.091+1.3)*0.3
    rng=np.random.default_rng(65);nz=cv2.GaussianBlur(rng.standard_normal((H,Wd)).astype(np.float32),(0,0),6)*6
    d=cv2.distanceTransform(W.astype(np.uint8),cv2.DIST_L2,5)
    shallow=np.clip(1-d/40,0,1)**1.5
    base=WATER[None,None,:]*(1+0.035*rip[...,None])+nz[...,None]*np.array([.4,.8,.8])
    base=base*(1-0.35*shallow[...,None])+np.array([150,196,188])*(0.35*shallow[...,None])
    edge=(d>0)&(d<2.2);base[edge]=base[edge]*0.4+np.array([236,240,226])*0.6
    np.save('water_stamp.npy',np.clip(base,0,255).astype(np.uint8))
    print('water',W.mean(),'obj px',obj.sum())
def stamp(img,x0,y0,S):
    """把水和区外按底账盖章到 img（S×S，全局左上 x0,y0）"""
    st=np.load('water_stamp.npy',mmap_mode='r')[y0:y0+S,x0:x0+S];Wf=G('waterfill')[y0:y0+S,x0:x0+S];M=G('map')[y0:y0+S,x0:x0+S]
    out=img.copy();out[Wf]=st[Wf];out[~M]=PAPER;return out
_c={}
def G(k):
    if k not in _c:_c[k]=load('ledger_mapx.png') if k=='map' else load(f'ledger_{k}.png') if k in ('houses','streets') else load(f'mask_{k}.png')
    return _c[k]
def render():
    if 'R' not in _c:_c['R']=np.asarray(Image.open('render_full.png').convert('RGB'))
    return _c['R']
def make_input(win,new,canvas,painted_ctx):
    """拼输入：已画好的象限原样贴进去，要生成的象限放原始渲染；水填一种平色，区外填纸色。"""
    i,j=win;x0,y0=i*512,j*512;inp=render()[y0:y0+1024,x0:x0+1024].copy().astype(float)
    Wf=G('waterfill')[y0:y0+1024,x0:x0+1024];M=G('map')[y0:y0+1024,x0:x0+1024]
    inp[Wf]=WATER;inp[~M]=PAPER
    for (qx,qy) in painted_ctx:
        ox,oy=(qx-i)*512,(qy-j)*512;inp[oy:oy+512,ox:ox+512]=canvas[qy*512:qy*512+512,qx*512:qx*512+512]
    return inp.astype(np.uint8)
def align(out,inp,ctxmask):
    """把模型输出对回输入的像素格：ECC 仿射，只看上下文象限里陆地的梯度（那部分应当原样保留）。"""
    o=cv2.resize(out,(1024,1024),interpolation=cv2.INTER_AREA) if out.shape[:2]!=(1024,1024) else out
    g1=cv2.GaussianBlur(cv2.cvtColor(inp,cv2.COLOR_RGB2GRAY).astype(np.float32),(0,0),1.5)
    g2=cv2.GaussianBlur(cv2.cvtColor(o,cv2.COLOR_RGB2GRAY).astype(np.float32),(0,0),1.5)
    Wm=np.eye(2,3,dtype=np.float32);mk=(ctxmask*255).astype(np.uint8)
    try:
        cc,Wm=cv2.findTransformECC(g1,g2,Wm,cv2.MOTION_AFFINE,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,200,1e-5),mk if mk.any() else None,5)
    except cv2.error as e:cc=None
    a=cv2.warpAffine(o,Wm,(1024,1024),flags=cv2.INTER_CUBIC+cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REFLECT)
    return a,Wm,cc
def masks_col(a):
    a=a.astype(int);r,g,b=a[...,0],a[...,1],a[...,2]
    return (r-b>55)&(r>100)&(g<r*0.82)
def grad(a):
    g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(float);gx=np.abs(np.diff(g,axis=1,append=g[:,-1:]));gy=np.abs(np.diff(g,axis=0,append=g[-1:]));return gx+gy
def fidelity(a,win,region):
    """region：本窗新生成象限的布尔遮罩（窗口坐标）。房子命中＝底账屋顶中心 ±3px 内有屋顶色；边缘 F＝对原始渲染（独立基线），只算陆地。"""
    i,j=win;x0,y0=i*512,j*512;J=json.load(open('ledger.json'))
    cen=[(int(x-x0),int(y-y0)) for x,y in J['cen'] if 0<=x-x0<1024 and 0<=y-y0<1024]
    L=G('land')[y0:y0+1024,x0:x0+1024]&region
    roof=nd.binary_dilation(masks_col(a),iterations=3)
    cs=[(x,y) for x,y in cen if region[y,x] and L[y,x]]
    hit=sum(roof[y,x] for x,y in cs)/max(1,len(cs))
    R=render()[y0:y0+1024,x0:x0+1024]
    def E(img):g=grad(img);g[~L]=0;return g>np.percentile(g[L],85) if L.sum()>500 else np.zeros_like(L)
    e,er=E(a),E(R)
    if e.sum()==0:return {'houses':len(cs),'house_hit':None,'edgeF3':None}
    p=(e&nd.binary_dilation(er,iterations=3)).sum()/e.sum();r=(er&nd.binary_dilation(e,iterations=3)).sum()/max(1,er.sum())
    return {'houses':len(cs),'house_hit':round(float(hit),3),'edgeF3':round(float(2*p*r/max(1e-6,p+r)),3)}
