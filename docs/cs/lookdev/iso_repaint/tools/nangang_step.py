# 用法：python3 nangang_step.py input K      → 写 in_K.png（窗口 K 的拼图输入）
#       python3 nangang_step.py commit K OUT.png [force] → 对齐、核对、（通过才）回填 canvas，记日志 attempts.jsonl
import sys,json,os,numpy as np,cv2,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)));import nangang_lib as N
from PIL import Image
from scipy import ndimage as nd
P=json.load(open('plan.json'));plan=P['plan'];FEA=28;TH_HOUSE=0.88;TH_EDGE=0.80;TH_DE=20
def canvas():
    if os.path.exists('canvas.png'):return np.asarray(Image.open('canvas.png').convert('RGB')).copy()
    c=N.render().copy();c=N.stamp(c,0,0,c.shape[0]) if False else c
    st=np.load('water_stamp.npy');Wf=N.G('waterfill');M=N.G('map');c[Wf]=st[Wf];c[~M]=N.PAPER.astype(np.uint8);return c
def state():return json.load(open('state.json')) if os.path.exists('state.json') else {'painted':[],'done':[]}
cmd,k=sys.argv[1],int(sys.argv[2]);p=plan[k];win=tuple(p['win']);new=[tuple(c) for c in p['new']];S=state()
ctx=[tuple(c) for c in p['ctx']];assert all(list(c) in S['painted'] for c in ctx),'context not painted yet'
C=canvas()
if cmd=='input':
    inp=N.make_input(win,new,C,ctx);Image.fromarray(inp).save(f'in_{k}.png');print('in',k,win,'new',new,'ctx',ctx)
elif cmd=='commit':
    out=np.asarray(Image.open(sys.argv[3]).convert('RGB'));inp=np.asarray(Image.open(f'in_{k}.png').convert('RGB'))
    i,j=win;x0,y0=i*512,j*512;reg=np.zeros((1024,1024),bool);ctxm=np.zeros((1024,1024),bool)
    for qx,qy in new:reg[(qy-j)*512:(qy-j)*512+512,(qx-i)*512:(qx-i)*512+512]=True
    for qx,qy in ctx:ctxm[(qy-j)*512:(qy-j)*512+512,(qx-i)*512:(qx-i)*512+512]=True
    Lw=N.G('land')[y0:y0+1024,x0:x0+1024]
    # 对齐：有上下文就用上下文，没有（种子）就用整张陆地对渲染
    a,Wm,cc=N.align(out,inp,(ctxm if ctx else np.ones_like(ctxm))&Lw)
    shift=float(np.abs(Wm[:,2]).max());scl=float(abs(Wm[0,0]-1)+abs(Wm[1,1]-1))
    # 模型对上下文改了多少（应接近 0）
    ctxdiff=float(np.abs(a[ctxm&Lw].astype(int)-inp[ctxm&Lw].astype(int)).mean()) if ctx else None
    # 颜色归一（按类）：底账分出「屋顶」（房子遮罩内缩）和「空地」（陆地减房子、街道、植被），
    # 新象限两类的 Lab 中位数各对到上下文象限里已定稿像素的两类中位数；每通道解一条 gain+offset（gain 限 0.8–1.25）。
    # 只比整体均值会把「房子密/空地多」的内容差当成色差，所以按类比。
    raw=a.copy();norm=a.copy();tf=None;dE=None
    if ctx:
        Hs=N.G('houses')[y0:y0+1024,x0:x0+1024];St=N.G('streets')[y0:y0+1024,x0:x0+1024]
        roofm=nd.binary_erosion(Hs,iterations=2)&Lw
        # 空地只取离房子 >10px、离街 >6px、离水 >15px 的开阔地（避开影子、街边、岸坡）
        dist=lambda m:cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,5)
        gr=Lw&(dist(Hs)>10)&(dist(St)>6)
        lab_a=cv2.cvtColor(a,cv2.COLOR_RGB2LAB).astype(float);lab_c=cv2.cvtColor(inp,cv2.COLOR_RGB2LAB).astype(float)
        vegA=(a[...,1].astype(int)>a[...,0]+8);vegC=(inp[...,1].astype(int)>inp[...,0]+8)
        sets=[(roofm&reg,roofm&ctxm),(gr&reg&~vegA,gr&ctxm&~vegC)]
        if all(x.sum()>800 and y.sum()>800 for x,y in sets):
            pn=[np.median(lab_a[x],0) for x,_ in sets];pc=[np.median(lab_c[y],0) for _,y in sets]
            dEs=[float(np.linalg.norm(pn[t]-pc[t])) for t in range(2)];dE=dEs   # 自动闸门只用屋顶 ≤30（拦得住 g_1_a 那种整体洗白）；空地中位数受内容影响太大（同一张好图能差 30–70），只记录，空地色偏靠每批看图人工拦
            # 校正只用重叠区：模型把上下文重画了一遍，「真上下文 − 模型画的上下文」就是它这次整体的色偏（和内容无关），限幅 ±10，反加到新象限
            ov=ctxm&Lw&~vegA&~vegC;off=np.clip(np.median(lab_c[ov],0)-np.median(lab_a[ov],0),-10,10);gain=np.ones(3)
            tf={'roof_new':pn[0].round(1).tolist(),'roof_ctx':pc[0].round(1).tolist(),'ground_new':pn[1].round(1).tolist(),'ground_ctx':pc[1].round(1).tolist(),'gain':gain.round(3).tolist(),'off':off.round(1).tolist(),'dE_roof':round(dEs[0],1),'dE_ground':round(dEs[1],1)}
            n2=cv2.cvtColor(np.clip(lab_a*gain+off,0,255).astype(np.uint8),cv2.COLOR_LAB2RGB);norm=np.where(reg[...,None],n2,a)
    f=N.fidelity(norm,win,reg)
    # 陆地上被画成水的最大连片（模型自己造水塘/海）
    ai=norm.astype(int);blue=(ai[...,2]>ai[...,0]+12)&(ai[...,1]>ai[...,0]+5)&(reg|(ctxm&(cv2.distanceTransform((~reg).astype(np.uint8),cv2.DIST_L2,5)<FEA+4)))&nd.binary_erosion(Lw,iterations=6)
    lb,nb=nd.label(blue);f['blue_on_land_px']=int(nd.sum(blue,lb,range(1,nb+1)).max()) if nb else 0
    ok=(f['house_hit'] is None or f['house_hit']>=TH_HOUSE) and (f['edgeF3'] is None or f['edgeF3']>=TH_EDGE) and (cc is not None) and shift<40 and (dE is None or dE[0]<=30) and f['blue_on_land_px']<1500
    force=len(sys.argv)>4 and sys.argv[4]=='force'
    rec={'k':k,'win':win,'new':new,'file':sys.argv[3],'out_size':out.shape[:2],'ecc':cc,'affine':np.round(Wm,4).tolist(),'ctx_absdiff':ctxdiff,'colour_tf':tf,'dE_raw_vs_ctx':None if dE is None else [round(x,1) for x in dE],**f,'accepted':bool(ok or force),'forced':force and not ok,'t':time.strftime('%H:%M:%S')}
    if not (os.environ.get('REPLAY') or os.environ.get('DRY')):open('attempts.jsonl','a').write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(json.dumps(rec,ensure_ascii=False))
    if (ok or force) and not os.environ.get('DRY'):
        # 回填：新象限整块用；在上下文一侧 FEA px 的窄带里从新图渐变回旧图
        d=cv2.distanceTransform((~reg).astype(np.uint8),cv2.DIST_L2,5)   # 到新区域的距离（上下文里）
        alpha=np.where(reg,1.0,np.clip(1-d/FEA,0,1))[...,None]
        alpha[~(reg|ctxm)]=0
        old=C[y0:y0+1024,x0:x0+1024].astype(float)
        for tag,src in (('norm',norm),('raw',raw)):
            base=C if tag=='norm' else (np.asarray(Image.open('canvas_raw.png').convert('RGB')).copy() if os.path.exists('canvas_raw.png') else C.copy())
            o=base[y0:y0+1024,x0:x0+1024].astype(float);blend=(o*(1-alpha)+src.astype(float)*alpha).astype(np.uint8)
            blend=N.stamp(blend,x0,y0,1024)
            base[y0:y0+1024,x0:x0+1024]=blend;Image.fromarray(base).save('canvas.png' if tag=='norm' else 'canvas_raw.png')
            if tag=='norm':C=base
        S['painted']+= [list(c) for c in new];S['done'].append(k);json.dump(S,open('state.json','w'))
        Image.fromarray(norm).save(f'acc_{k}.png');json.dump(S,open('state.json','w'))
        if not os.environ.get('REPLAY'):open('accepted.txt','a').write(f'{k} {sys.argv[3]}\n')
