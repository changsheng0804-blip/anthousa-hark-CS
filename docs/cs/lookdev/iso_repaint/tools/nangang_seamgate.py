# 接缝闸门（自动）：在全幅 canvas 上给每条「两侧都画过的象限边界」打分，再加上修缝补丁自己的四条边；
# 对照组是象限中线（同一次生成的内部，不是边界），被补丁边压到的中线不算对照。
#  edge_ratio = 跨线相邻两列像素的 Lab 差 ÷ 线两侧 8–40px 内部相邻列差的中位数（≈1 看不出线）
#  colour_dE  = 线两侧 24px 条带（只取陆地像素）的 Lab 均值差 − 同侧往里两条带之差的平均（扣掉内容本身的渐变）
# 判失败：edge_ratio > 1.6，或 colour_dE > 对照组 colour_dE 的 p90（同一张图上现算，下限 6.0）。
# 用法（工作目录 = 原始件目录）：python3 nangang_seamgate.py [canvas.png] [out.json]
#   有任何一条失败 → 退出码 1。补丁清单读 seamfix_patches.json（nangang_seamfix.py 写），没有就当没有补丁。
import numpy as np,json,cv2,sys,os
from PIL import Image
EDGE_MAX=1.6;DE_FLOOR=6.0
f=sys.argv[1] if len(sys.argv)>1 else 'canvas.png';outf=sys.argv[2] if len(sys.argv)>2 else 'nangang_seams.json'
A0=cv2.cvtColor(np.asarray(Image.open(f).convert('RGB')),cv2.COLOR_RGB2LAB).astype(float)
L0=np.asarray(Image.open('mask_land.png').convert('L'))>127
S=json.load(open('state_pre_seamfix.json' if os.path.exists('state_pre_seamfix.json') else 'state.json'));P={tuple(c) for c in S['painted']}
PATCH=json.load(open('seamfix_patches.json')) if os.path.exists('seamfix_patches.json') and 'nopatch' not in sys.argv else []
def meas(A,L,X,ys):
    """竖线 X（列 X-1|X），行范围 ys；横线用转置数组调用"""
    m=L[ys,X-1]&L[ys,X]
    if m.sum()<150:return None
    e=np.linalg.norm(A[ys,X-1]-A[ys,X],axis=-1)[m].mean()
    inner=[np.linalg.norm(A[ys,X+k-1]-A[ys,X+k],axis=-1)[m].mean() for k in list(range(-40,-8,4))+list(range(8,40,4))]
    def band(a,b):
        mm=L[ys,a:b];return A[ys,a:b][mm].mean(0) if mm.sum()>500 else None
    ca,cb,ca2,cb2=band(X-24,X),band(X,X+24),band(X-48,X-24),band(X+24,X+48)
    col=None if any(v is None for v in (ca,cb,ca2,cb2)) else max(0,np.linalg.norm(ca-cb)-0.5*(np.linalg.norm(ca-ca2)+np.linalg.norm(cb-cb2)))
    return int(m.sum()),float(e/np.median(inner)),col
AT=A0.transpose(1,0,2).copy();LT=L0.T.copy()
def line(d,c,a,b):
    """d='V'：x=c，y∈[a,b)；d='H'：y=c，x∈[a,b)"""
    return meas(A0,L0,c,slice(a,b)) if d=='V' else meas(AT,LT,c,slice(a,b))
# 补丁边（会落在中线上，要从对照里剔除）
pedges=[]
for p in PATCH:
    x0,y0,x1,y1=p['box'];x0+=24;y0+=24;x1-=24;y1-=24   # 渐变带正中
    pedges+= [('V',x0,y0,y1),('V',x1,y0,y1),('H',y0,x0,x1),('H',y1,x0,x1)]
def on_patch_edge(d,c,a,b):
    return any(d==e[0] and abs(c-e[1])<=8 and min(b,e[3])-max(a,e[2])>64 for e in pedges)
seams=[];ctl=[];pe=[]
for (x,y) in P:
    for dx,dy in ((1,0),(0,1)):
        n=(x+dx,y+dy);d='V' if dx else 'H'
        for kind,off in (('seam',512),('control',256)):
            if kind=='seam' and n not in P:continue
            c=(x*512+off) if dx else (y*512+off);a=(y if dx else x)*512
            if kind=='control' and on_patch_edge(d,c,a,a+512):continue
            r=line(d,c,a,a+512)
            if r is None:continue
            rec={'a':[x,y],'b':list(n),'dir':d,'land_px':r[0],'edge_ratio':round(r[1],2),'colour_dE':None if r[2] is None else round(float(r[2]),1)}
            (seams if kind=='seam' else ctl).append(rec)
for i,p in enumerate(PATCH):
    x0,y0,x1,y1=p['box'];x0+=24;y0+=24;x1-=24;y1-=24
    for d,c,a,b,side in (('V',x0,y0,y1,'left'),('V',x1,y0,y1,'right'),('H',y0,x0,x1,'top'),('H',y1,x0,x1,'bottom')):
        r=line(d,c,a,b)
        if r is None:continue
        pe.append({'patch':i,'seam':p['seam'],'side':side,'dir':d,'at':c,'span':[a,b],'land_px':r[0],'edge_ratio':round(r[1],2),'colour_dE':None if r[2] is None else round(float(r[2]),1)})
def summ(rs):
    if not rs:return {'n':0}
    er=[r['edge_ratio'] for r in rs];ce=[r['colour_dE'] for r in rs if r['colour_dE'] is not None]
    return {'n':len(rs),'edge_ratio_median':round(float(np.median(er)),2),'edge_ratio_p90':round(float(np.percentile(er,90)),2),'edge_ratio_max':max(er),'colour_dE_median':round(float(np.median(ce)),1),'colour_dE_p90':round(float(np.percentile(ce,90)),1),'colour_dE_max':max(ce)}
cs=summ(ctl);DE_MAX=max(DE_FLOOR,cs['colour_dE_p90'])
def fails(r):
    why=[]
    if r['edge_ratio']>EDGE_MAX:why.append(f"edge {r['edge_ratio']}>{EDGE_MAX}")
    if r['colour_dE'] is not None and r['colour_dE']>DE_MAX:why.append(f"dE {r['colour_dE']}>{DE_MAX}")
    return why
for r in seams+pe:
    w=fails(r);r['fail']=w or None
key=lambda r:-((r['edge_ratio']-1)*10+(r['colour_dE'] or 0))
seams.sort(key=key);pe.sort(key=key)
bad=[r for r in seams if r['fail']];badp=[r for r in pe if r['fail']]
res={'file':f,'rule':{'edge_ratio_max':EDGE_MAX,'colour_dE_max':DE_MAX,'colour_dE_max_is':'control p90 on this image, floor 6.0'},
     'seams':summ(seams),'controls_mid_quadrant':cs,'patch_edges':summ(pe),
     'failing_seams':len(bad),'failing_patch_edges':len(badp),'pass':not(bad or badp),
     'failing':bad,'failing_patch_edge_list':badp,'all':seams,'all_patch_edges':pe}
json.dump(res,open(outf,'w'),indent=1)
print(json.dumps({k:res[k] for k in ('file','rule','seams','controls_mid_quadrant','patch_edges','failing_seams','failing_patch_edges','pass')},ensure_ascii=False))
for r in bad:print('FAIL',r['a'],r['b'],r['dir'],r['fail'])
for r in badp:print('FAIL patch',r['patch'],r['seam'],r['side'],r['fail'])
sys.exit(0 if res['pass'] else 1)
