# 地图边收口：原来的范围 = 地面 ∪ 房子凸包外扩，边上一圈房子各带一圈黄色地皮，纸色在房子之间切出锯齿和缺口，
#   模型还在边上留了一些「纸色洞」。做法：
#   1) 新范围 M2 = 对原范围做半径 28px 的闭运算（把房子之间的缺口连起来），再做半径 6px 的开运算去掉毛刺；
#   2) M2 里离边 60px 以内、颜色几乎就是纸色（每通道差 ≤10）、连片 ≥30px 的像素也算缺口；
#   3) 缺口一律用「当地空地色」填：严格空地像素按 σ=24px 归一化高斯求平均色场，加一点点全局坐标噪声；
#   4) M2 外面全是纸；M2 边做 1.5px 羽化。水（底账盖章）不动。
# 用法（工作目录 = 原始件目录）：python3 nangang_edge.py in.png out.png
import numpy as np,cv2,sys,json
from PIL import Image
from scipy import ndimage as nd
fi,fo=sys.argv[1],sys.argv[2]
C=np.asarray(Image.open(fi).convert('RGB')).astype(np.float32);H,W=C.shape[:2]
ld=lambda f:np.asarray(Image.open(f).convert('L'))>127
M=ld('ledger_mapx.png');Wt=ld('mask_water.png');Hs=ld('ledger_houses.png');St=ld('ledger_streets.png');L=ld('mask_land.png')
PAPER=np.array([238,231,214],np.float32)
k=lambda r:cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*r+1,2*r+1))
M2=cv2.morphologyEx(M.astype(np.uint8),cv2.MORPH_CLOSE,k(28))
M2=cv2.morphologyEx(M2,cv2.MORPH_OPEN,k(6)).astype(bool)|M
M2=nd.binary_fill_holes(M2)
dedge=cv2.distanceTransform(M2.astype(np.uint8),cv2.DIST_L2,5)
paperish=(np.abs(C-PAPER).max(-1)<=10)&M2&(dedge<60)&~Wt
lb,n=nd.label(paperish);sz=nd.sum(paperish,lb,range(1,n+1));paperish=np.isin(lb,1+np.where(sz>=30)[0])
gap=(M2&~M)|paperish
dist=lambda m:cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,5)
a=C.astype(int);gr=L&M&(dist(Hs)>6)&(dist(St)>4)&~(a[...,1]>a[...,0]+8)&~(a[...,2]>a[...,0]+12)&~paperish
gr&=np.abs(C-PAPER).max(-1)>14
den=cv2.GaussianBlur(gr.astype(np.float32),(0,0),24)+1e-4
fld=cv2.GaussianBlur(C*gr[...,None],(0,0),24)/den[...,None]
# 没有空地可参考的地方（离空地很远）退到全局空地中位色
glob=np.median(C[gr],0);wv=np.clip(den/0.05,0,1)[...,None];fld=fld*wv+glob*(1-wv)
rng=np.random.default_rng(65);nz=cv2.GaussianBlur(rng.standard_normal((H,W)).astype(np.float32),(0,0),2)*3
out=C.copy();out[gap]=fld[gap]+nz[gap][:,None]
alpha=cv2.GaussianBlur(M2.astype(np.float32),(0,0),1.5)[...,None]
out=out*alpha+PAPER*(1-alpha)
out[Wt&M]=C[Wt&M]
Image.fromarray(np.clip(out,0,255).astype(np.uint8)).save(fo)
Image.fromarray((M2*255).astype(np.uint8)).save('ledger_mapx2.png')
print(json.dumps({'map_px_before':int(M.sum()),'map_px_after':int(M2.sum()),'gap_filled_px':int(gap.sum()),'paper_holes_px':int(paperish.sum()),'ground_ref_Lab_rgb':glob.round(1).tolist()}))
