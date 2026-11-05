# 接缝分数：在每条两侧都画过的象限边界（512 网格）上量，并在象限中线（512k+256，同样两侧都画过、但不是边界）上量同样的数作对照。
#  edge_ratio = 跨线相邻两列像素的 Lab 差 ÷ 线两侧 8–40px 内部相邻列差的中位数（≈1 看不出线）
#  colour_dE  = 线两侧 24px 条带（只取陆地像素）的 Lab 均值差 − 同侧往里两条带之差的平均（扣掉内容本身的渐变）
import numpy as np,json,cv2,sys
from PIL import Image
f=sys.argv[1] if len(sys.argv)>1 else 'canvas.png'
A=cv2.cvtColor(np.asarray(Image.open(f).convert('RGB')),cv2.COLOR_RGB2LAB).astype(float)
L=np.asarray(Image.open('mask_land.png'))>127;S=json.load(open('state.json'));P={tuple(c) for c in S['painted']}
def meas(X,ys):
    """竖线 X（列 X-1|X），行范围 ys；横线用转置调用"""
    m=L[ys,X-1]&L[ys,X]
    if m.sum()<150:return None
    e=np.linalg.norm(A[ys,X-1]-A[ys,X],axis=-1)[m].mean()
    inner=[np.linalg.norm(A[ys,X+k-1]-A[ys,X+k],axis=-1)[m].mean() for k in list(range(-40,-8,4))+list(range(8,40,4))]
    def band(a,b):
        mm=L[ys,a:b];return A[ys,a:b][mm].mean(0) if mm.sum()>500 else None
    ca,cb,ca2,cb2=band(X-24,X),band(X,X+24),band(X-48,X-24),band(X+24,X+48)
    col=None if any(v is None for v in (ca,cb,ca2,cb2)) else max(0,np.linalg.norm(ca-cb)-0.5*(np.linalg.norm(ca-ca2)+np.linalg.norm(cb-cb2)))
    return int(m.sum()),float(e/np.median(inner)),col
out=[];ctl=[]
AT=A.transpose(1,0,2).copy();LT=L.T.copy()
for (x,y) in P:
    for dx,dy in ((1,0),(0,1)):
        n=(x+dx,y+dy)
        for kind,off,need in (('seam',512,n in P),('control',256,True)):
            if not need:continue
            if dx:r=meas(x*512+off,slice(y*512,y*512+512))
            else:
                A,AT=AT,A;L,LT=LT,L;r=meas(y*512+off,slice(x*512,x*512+512));A,AT=AT,A;L,LT=LT,L
            if r is None:continue
            rec={'a':[x,y],'b':list(n),'dir':'V' if dx else 'H','land_px':r[0],'edge_ratio':round(r[1],2),'colour_dE':None if r[2] is None else round(float(r[2]),1)}
            (out if kind=='seam' else ctl).append(rec)
def summ(rs):
    er=[r['edge_ratio'] for r in rs];ce=[r['colour_dE'] for r in rs if r['colour_dE'] is not None]
    return {'n':len(rs),'edge_ratio_median':round(float(np.median(er)),2),'edge_ratio_p90':round(float(np.percentile(er,90)),2),'edge_ratio_max':max(er),'colour_dE_median':round(float(np.median(ce)),1),'colour_dE_p90':round(float(np.percentile(ce,90)),1),'colour_dE_max':max(ce)}
out.sort(key=lambda r:-((r['edge_ratio']-1)*10+(r['colour_dE'] or 0)))
res={'file':f,'seams':summ(out),'controls_mid_quadrant':summ(ctl),'worst':out[:10],'all':out}
json.dump(res,open(f.replace('.png','')+'_seams.json','w'),indent=1)
print(json.dumps({k:res[k] for k in ('file','seams','controls_mid_quadrant')}))
for r in out[:6]:print(r)
