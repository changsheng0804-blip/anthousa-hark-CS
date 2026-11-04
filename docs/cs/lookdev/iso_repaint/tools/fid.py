import numpy as np,json
from PIL import Image,ImageFilter
S=1024
L=lambda f:np.asarray(Image.open(f).convert('L').resize((S,S)))>127
LW,LH,LS=L('ledger_water.png'),L('ledger_houses.png'),L('ledger_streets.png')
cen=np.array(json.load(open('ledger_cen.json'))).astype(int)
def grad(a):
    g=np.asarray(Image.fromarray(a).convert('L'),float);gx=np.abs(np.diff(g,axis=1))[:-1];gy=np.abs(np.diff(g,axis=0))[:,:-1];return gx+gy
def align(im):
    # search stretch/crop so the image best matches the render's gradient field (coarse, 256 px)
    R=np.asarray(Image.open('rgb_sq.png').convert('RGB').resize((256,256)));gr=grad(R);gr=(gr-gr.mean())/gr.std()
    w,h=im.size;best=None
    for sx in np.linspace(0.92,1.12,11):
      for sy in np.linspace(0.85,1.12,14):
        for dx in range(-10,11,2):
          for dy in range(-10,11,2):
            pass
    return best
def warp(im,sx,sy,dx,dy,S=S):
    # output pixel (u,v) samples input at ((u-dx)/sx*w/S, (v-dy)/sy*h/S)
    w,h=im.size;return im.transform((S,S),Image.AFFINE,(w/S/sx,0,-dx*w/S/sx,0,h/S/sy,-dy*h/S/sy),Image.BICUBIC)
def fit(im):
    def sc(Z,cands):
        R=np.asarray(Image.open('rgb_sq.png').convert('RGB').resize((Z,Z)).filter(ImageFilter.GaussianBlur(1)));gr=grad(R);gr=(gr-gr.mean())/gr.std()
        small=im.resize((int(im.size[0]*Z/S),int(im.size[1]*Z/S))).filter(ImageFilter.GaussianBlur(1));best=(-9,None)
        for (sx,sy,dx,dy) in cands:
            a=np.asarray(warp(small,sx,sy,dx*Z/S,dy*Z/S,Z));g=grad(a);g=(g-g.mean())/(g.std()+1e-6);c=(g*gr).mean()
            if c>best[0]:best=(c,(sx,sy,dx,dy))
        return best
    c1=[(sx,sy,dx,dy) for sx in np.arange(0.88,1.16,0.03) for sy in np.arange(0.82,1.16,0.03) for dx in range(-48,49,16) for dy in range(-48,49,16)]
    b=sc(128,c1)[1]
    c2=[(b[0]+i,b[1]+j,b[2]+x,b[3]+y) for i in np.arange(-.02,.021,.01) for j in np.arange(-.02,.021,.01) for x in range(-8,9,4) for y in range(-8,9,4)]
    return sc(256,c2)
def masks(a):
    a=a.astype(int);r,g,b=a[...,0],a[...,1],a[...,2]
    water=(b>r+12)&(g>r+5)
    roof=(r-b>55)&(r>100)&(g<r*0.82)
    return water,roof
def dil(m,k):return np.asarray(Image.fromarray((m*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k)))>0
def edges(a):
    g=grad(a);g=np.pad(g,((0,1),(0,1)));return g>np.percentile(g,85)
def run(name,f,aff=None):
    im=Image.open(f).convert('RGB')
    if aff is None and im.size!=(S,S): c,aff=fit(im)
    if aff: im=warp(im,*aff)
    else: im=im.resize((S,S))
    im.save(f'aligned_{name}.png');a=np.asarray(im)
    W,Rf=masks(a)
    iou=lambda x,y:(x&y).sum()/max(1,(x|y).sum())
    out={'aff':[round(float(v),3) for v in aff] if aff else None,'water_IoU_vs_ledger':round(float(iou(W,LW)),3)}
    LHd=dil(LH,5);Rd=dil(Rf,7)
    hit=sum(Rd[y,x] for x,y in cen);out['house_recall']=round(hit/len(cen),3)
    out['roof_precision']=round(float((Rf&LHd).sum()/max(1,Rf.sum())),3)
    out['roof_on_ledger_water']=round(float((Rf&LW&~dil(LH,9)).sum()/max(1,Rf.sum())),3)
    return out,a
res={};render_e=None
for n,f in [('render','rgb_sq.png'),('A','repaint_A.png'),('B1','repaint_B.png'),('B2','repaint_B2.png')]:
    o,a=run(n,f);e=edges(a)
    if n=='render':render_e=e
    else:
        p=(e&dil(render_e,7)).sum()/e.sum();r=(render_e&dil(e,7)).sum()/render_e.sum();o['edge_F_vs_render(3px)']=round(float(2*p*r/(p+r)),3)
    res[n]=o;print(n,o)
json.dump(res,open('fidelity.json','w'),indent=1,ensure_ascii=False)
