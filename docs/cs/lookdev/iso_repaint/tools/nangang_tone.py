# 东半空地色调：只动空地像素（底账遮罩），把东半偏暗、偏黄绿的空地往全图空地的中位色拉。
# 做法：严格空地（陆地、离房子 >8px、离街 >5px、不是树、不是水色）上取 Lab，按 σ=160px 做归一化高斯平均得「当地空地色」场；
#   目标 = 全图严格空地中位色。L 用乘法增益（影子按比例一起提亮，明暗关系不变），a/b 用平移；只往目标拉、不越过；
#   作用像素 = 陆地 − 房子(外扩 1px) − 街道，再按「色相像不像当地空地」（a,b 距离，σ=14）给权重，屋顶红、树绿、街灰基本不动；
#   东西向权重：x<3300 为 0，x>3900 为 1（主人只说了东半）。
# 用法（工作目录 = 原始件目录）：python3 nangang_tone.py in.png out.png
import numpy as np,cv2,sys,json
from PIL import Image
from scipy import ndimage as nd
fi,fo=sys.argv[1],sys.argv[2]
C=np.asarray(Image.open(fi).convert('RGB'));H,W=C.shape[:2]
ld=lambda f:np.asarray(Image.open(f).convert('L'))>127
Lm=ld('mask_land.png');Hs=ld('ledger_houses.png');St=ld('ledger_streets.png')
dist=lambda m:cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,5)
a=C.astype(int);veg=a[...,1]>a[...,0]+8;wat=a[...,2]>a[...,0]+12
gr=Lm&(dist(Hs)>8)&(dist(St)>5)&~veg&~wat
lab=cv2.cvtColor(C,cv2.COLOR_RGB2LAB).astype(np.float32)
tgt=np.median(lab[gr],0)
# 当地空地色场（在 1/8 分辨率上算，再放大）
s=8;g8=cv2.resize(gr.astype(np.float32),(W//s,H//s),interpolation=cv2.INTER_AREA)
l8=cv2.resize(lab*gr[...,None],(W//s,H//s),interpolation=cv2.INTER_AREA)
sig=160/s;den=cv2.GaussianBlur(g8,(0,0),sig)+1e-4;loc8=cv2.GaussianBlur(l8,(0,0),sig)/den[...,None]
loc=cv2.resize(loc8,(W,H),interpolation=cv2.INTER_CUBIC)
xw=np.clip((np.arange(W)-3300)/600,0,1)[None,:]
gain=np.where(loc[...,0]<tgt[0],tgt[0]/np.maximum(loc[...,0],1),1.0)
gain=np.minimum(gain,1.35)
dab=np.zeros((H,W,2),np.float32)
for c in (1,2):
    d=tgt[c]-loc[...,c];dab[...,c-1]=np.where(np.sign(d)==np.sign(tgt[c]-loc[...,c]),d,0)
hue=np.exp(-((lab[...,1]-loc[...,1])**2+(lab[...,2]-loc[...,2])**2)/(2*14**2))
hue*=np.exp(-np.maximum(0,lab[...,0]-loc[...,0]-15)**2/(2*10**2))   # 比当地空地亮很多的（广场铺面、白墙）不动
act=Lm&~nd.binary_dilation(Hs,iterations=1)&~St&~veg&~wat
w=cv2.GaussianBlur((act*hue).astype(np.float32),(0,0),1.0)*xw
out=lab.copy()
out[...,0]=lab[...,0]*(1+(gain-1)*w)
out[...,1]=lab[...,1]+dab[...,0]*w;out[...,2]=lab[...,2]+dab[...,1]*w
rgb=cv2.cvtColor(np.clip(out,0,255).astype(np.uint8),cv2.COLOR_LAB2RGB)
Image.fromarray(rgb).save(fo)
east=gr&(xw>0.99)
print(json.dumps({'target_Lab':tgt.round(1).tolist(),'east_ground_before':np.median(lab[east],0).round(1).tolist(),
  'east_ground_after':np.median(cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).astype(float)[east],0).round(1).tolist(),
  'px_changed':int((w>0.05).sum())}))
