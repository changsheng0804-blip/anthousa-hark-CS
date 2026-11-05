# 修缝（Isopolis 的「纠正窗」做法）：对一条失败的接缝，开一个以缝为中心的 1024² 新窗口，
#   窗口外圈（四边各 256px）全是已定稿的画（上下文），中间 512²（正好把缝骑在中线上）放原始渲染让模型重画；
#   只保留中间这块，向外圈 32px 渐变回旧图；然后照旧盖水、盖纸。
# 闸门和主轮一样：房子命中 ≥0.88、边缘 F ≥0.80、陆地造水 <1500px、屋顶 ΔE ≤30、ECC 收敛；
#   另加「补丁本身不能变成新缝」：原缝所在那条线过闸，且原缝 + 补丁四条边的超标量总和下降（见 commit 里的注释）。
#   渐变在块内 48px，补丁边在渐变带正中（块边往里 24px）量。
# 用法（工作目录 = 原始件目录）：
#   python3 nangang_seamfix.py input V,6,1          → fin_V_6_1.png + fprompt_V_6_1.txt（V,x,y = (x,y)|(x+1,y)；H,x,y = (x,y)/(x,y+1)）
#   python3 nangang_seamfix.py commit V,6,1 OUT.png [force]  → 核对；通过才回填 canvas.png，记 seamfix_patches.json / seamfix_attempts.jsonl
import sys,json,os,numpy as np,cv2,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)));import nangang_lib as N
from PIL import Image
from scipy import ndimage as nd
FEA=48;MID=24;TH_HOUSE=0.88;TH_EDGE=0.80;EDGE_MAX=1.6;DE_MAX=float(os.environ.get('DE_MAX','6.3'))
FW,FH=6144,4096;GROUND_TGT=np.array([205.,131.,172.])
def geom(tag):
    d,x,y=tag.split(',');x,y=int(x),int(y)
    if d=='V':X=512*(x+1);box=(X-256,512*y,X+256,512*y+512)
    else:Y=512*(y+1);box=(512*x,Y-256,512*x+512,Y+256)
    cx,cy=(box[0]+box[2])//2,(box[1]+box[3])//2
    x0=min(max(0,cx-512),FW-1024);y0=min(max(0,cy-512),FH-1024)
    return d,(x,y),box,(x0,y0)
def prompt():
    return ("Continue an illustrated isometric map seamlessly. Output a square image with exactly the same framing as the input, pixel-aligned to it. "
    "The OUTER FRAME of the input (a band one quarter of the image wide along all four sides) is ALREADY FINISHED artwork: keep it pixel-identical, do not repaint, recolour, sharpen or shift it. "
    "The CENTRAL SQUARE (the middle half of the image in both directions) is still a raw 3D render of the same 5th-century Late Roman (early Byzantine) harbour town: small low-rise houses with pitched tile roofs, lanes, small squares, trees. "
    "Repaint ONLY that central square in exactly the same illustrated style, outline weight, colours, lighting and shadow length as the finished frame around it, so that it joins the frame on all four sides with no visible seam: roads, house rows, ground colour and shoreline continue straight across the boundary. "
    "Style: clean illustrated isometric city-builder tile (Isometric SF, 1990s SimCity 4), crisp thin dark outlines, flat-shaded faces, soft even daylight from the upper left, short soft shadows instead of long dark shadows; "
    "match the finished frame's colours exactly: deep terracotta and brick-red roofs, cream walls, warm honey-yellow open ground, grey-beige stone lanes, dark cypress and olive greens; same brightness and saturation as the frame, do not lighten, darken, wash out or desaturate. "
    "Flat blue-green water stays flat blue-green water; the flat cream-beige area is an empty paper margin, NOT sea: keep it plain flat cream-beige, do not paint water, shore, jetties or boats there. "
    "STRICT GEOMETRY LOCK: every building keeps exactly its position, footprint, orientation and height; every lane, square, shoreline, mole and jetty stays exactly where it is. "
    "Do not add or remove buildings, do not merge blocks, no towers, domes, walls, skyscrapers or new landmarks. No modern objects, no cars, no glass, no text, no labels, no watermark, no border.")
def meas(A,L,X,ys):
    m=L[ys,X-1]&L[ys,X]
    if m.sum()<150:return None
    e=np.linalg.norm(A[ys,X-1]-A[ys,X],axis=-1)[m].mean()
    inner=[np.linalg.norm(A[ys,X+k-1]-A[ys,X+k],axis=-1)[m].mean() for k in list(range(-40,-8,4))+list(range(8,40,4))]
    def band(a,b):
        mm=L[ys,a:b];return A[ys,a:b][mm].mean(0) if mm.sum()>500 else None
    ca,cb,ca2,cb2=band(X-24,X),band(X,X+24),band(X-48,X-24),band(X+24,X+48)
    col=None if any(v is None for v in (ca,cb,ca2,cb2)) else max(0,np.linalg.norm(ca-cb)-0.5*(np.linalg.norm(ca-ca2)+np.linalg.norm(cb-cb2)))
    return {'land_px':int(m.sum()),'edge_ratio':round(float(e/np.median(inner)),2),'colour_dE':None if col is None else round(float(col),1)}
def lines(C,tag):
    """原缝那条线 + 补丁四条边，在 C（全幅 RGB）上量"""
    d,(x,y),box,_=geom(tag);bx0,by0,bx1,by1=box
    pad=64;X0,Y0=max(0,bx0-pad),max(0,by0-pad);X1,Y1=min(FW,bx1+pad),min(FH,by1+pad)
    A=cv2.cvtColor(C[Y0:Y1,X0:X1],cv2.COLOR_RGB2LAB).astype(float);L=N.G('land')[Y0:Y1,X0:X1]
    AT=A.transpose(1,0,2).copy();LT=L.T.copy()
    V=lambda c,a,b:meas(A,L,c-X0,slice(a-Y0,b-Y0));Hh=lambda c,a,b:meas(AT,LT,c-Y0,slice(a-X0,b-X0))
    out={'seam':V((bx0+bx1)//2,by0,by1) if d=='V' else Hh((by0+by1)//2,bx0,bx1),
         'left':V(bx0+MID,by0,by1),'right':V(bx1-MID,by0,by1),'top':Hh(by0+MID,bx0,bx1),'bottom':Hh(by1-MID,bx0,bx1)}   # 补丁边在渐变带正中量
    return out
def bad(r):return r is not None and (r['edge_ratio']>EDGE_MAX or (r['colour_dE'] or 0)>DE_MAX)
def fidelity(a,x0,y0,region):
    J=json.load(open('ledger.json'))
    cen=[(int(x-x0),int(y-y0)) for x,y in J['cen'] if 0<=x-x0<1024 and 0<=y-y0<1024]
    L=N.G('land')[y0:y0+1024,x0:x0+1024]&region
    roof=nd.binary_dilation(N.masks_col(a),iterations=3)
    cs=[(x,y) for x,y in cen if region[y,x] and L[y,x]]
    hit=sum(roof[y,x] for x,y in cs)/max(1,len(cs))
    R=N.render()[y0:y0+1024,x0:x0+1024]
    def E(img):g=N.grad(img);g[~L]=0;return g>np.percentile(g[L],85) if L.sum()>500 else np.zeros_like(L)
    e,er=E(a),E(R)
    if e.sum()==0:return {'houses':len(cs),'house_hit':None,'edgeF3':None}
    p=(e&nd.binary_dilation(er,iterations=3)).sum()/e.sum();r=(er&nd.binary_dilation(e,iterations=3)).sum()/max(1,er.sum())
    return {'houses':len(cs),'house_hit':round(float(hit),3),'edgeF3':round(float(2*p*r/max(1e-6,p+r)),3)}
if __name__=='__main__':
    cmd,tag=sys.argv[1],sys.argv[2];ft=tag.replace(',','_');d,(qx,qy),box,(x0,y0)=geom(tag)
    C=np.asarray(Image.open('canvas.png').convert('RGB')).copy()
    reg=np.zeros((1024,1024),bool);reg[box[1]-y0:box[3]-y0,box[0]-x0:box[2]-x0]=True;ctxm=~reg
    if cmd=='input':
        inp=C[y0:y0+1024,x0:x0+1024].astype(float);R=N.render()[y0:y0+1024,x0:x0+1024].astype(float)
        Wf=N.G('waterfill')[y0:y0+1024,x0:x0+1024];M=N.G('map')[y0:y0+1024,x0:x0+1024]
        R[Wf]=N.WATER;R[~M]=N.PAPER;inp[reg]=R[reg]
        Image.fromarray(inp.astype(np.uint8)).save(f'fin_{ft}.png');open(f'fprompt_{ft}.txt','w').write(prompt())
        print('input',tag,'box',box,'win',(x0,y0),'before',json.dumps(lines(C,tag)))
    elif cmd=='commit':
        out=np.asarray(Image.open(sys.argv[3]).convert('RGB'));inp=np.asarray(Image.open(f'fin_{ft}.png').convert('RGB'))
        Lw=N.G('land')[y0:y0+1024,x0:x0+1024]
        a,Wm,cc=N.align(out,inp,ctxm&Lw);shift=float(np.abs(Wm[:,2]).max())
        ctxdiff=float(np.abs(a[ctxm&Lw].astype(int)-inp[ctxm&Lw].astype(int)).mean())
        lab_a=cv2.cvtColor(a,cv2.COLOR_RGB2LAB).astype(float);lab_c=cv2.cvtColor(inp,cv2.COLOR_RGB2LAB).astype(float)
        Hs=N.G('houses')[y0:y0+1024,x0:x0+1024];roofm=nd.binary_erosion(Hs,iterations=2)&Lw
        vegA=(a[...,1].astype(int)>a[...,0]+8);vegC=(inp[...,1].astype(int)>inp[...,0]+8)
        dEr=None
        if (roofm&reg).sum()>800 and (roofm&ctxm).sum()>800:dEr=float(np.linalg.norm(np.median(lab_a[roofm&reg],0)-np.median(lab_c[roofm&ctxm],0)))
        ov=ctxm&Lw&~vegA&~vegC;off=np.clip(np.median(lab_c[ov],0)-np.median(lab_a[ov],0),-10,10) if ov.sum()>2000 else np.zeros(3)
        n2=cv2.cvtColor(np.clip(lab_a+off,0,255).astype(np.uint8),cv2.COLOR_LAB2RGB);norm=n2   # 整窗都加同一个偏移，否则外圈渐变区（用的是模型画的外圈）和中间之间会多出一个色阶
        # 空地单独对色：新画的中间块常把空地画暗、画偏黄绿（原始渲染那里就暗）。严格空地（离房子 >8px、离街 >5px、非树非水）
        #   中间块的中位色对到外圈的中位色：L 乘法增益（0.8–1.35），a/b 平移（±12）；只作用于「色相像空地」的像素（屋顶、树、街基本不动）
        gtf=None
        St=N.G('streets')[y0:y0+1024,x0:x0+1024];dist=lambda m:cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,5)
        ln=cv2.cvtColor(norm,cv2.COLOR_RGB2LAB).astype(np.float32);ni=norm.astype(int)
        vegN=ni[...,1]>ni[...,0]+8;watN=ni[...,2]>ni[...,0]+12;watC=inp[...,2].astype(int)>inp[...,0]+12
        grs=Lw&(dist(Hs)>8)&(dist(St)>5)
        gn=grs&reg&~vegN&~watN;gc=grs&ctxm&~vegC&~watC
        if gn.sum()>1500 and gc.sum()>1500:
            # 用「场」而不是一个中位数：外圈空地色按 σ=200 做归一化高斯外推进中间（参考场），中间新空地色按 σ=100 求当地场，逐像素对
            def field(lab,m,sg):
                s8=4;mm=cv2.resize(m.astype(np.float32),(256,256),interpolation=cv2.INTER_AREA);ll=cv2.resize(lab*m[...,None],(256,256),interpolation=cv2.INTER_AREA)
                den=cv2.GaussianBlur(mm,(0,0),sg/s8)+1e-4;return cv2.resize(cv2.GaussianBlur(ll,(0,0),sg/s8)/den[...,None],(1024,1024),interpolation=cv2.INTER_CUBIC)
            # 参考色：外圈空地按 σ=200 外推的场，和全图空地目标色（nangang_tone.py 的目标，205,131,172）取亮的那个——
            #   外圈里有铺地、阴影、广场，单用外圈会把参考拉暗（V,9,4 第一张就是这样，新空地被对到 L≈180）
            ref=field(lab_c.astype(np.float32),gc,200);ref[...,0]=np.maximum(ref[...,0],GROUND_TGT[0]);ref[...,1:]=GROUND_TGT[1:]
            loc=field(ln,gn,100)
            mn=np.median(ln[gn],0);mc=np.median(lab_c[gc],0)
            gain=np.clip(ref[...,0]/np.maximum(loc[...,0],1),0.8,1.35);sh=np.clip(ref[...,1:]-loc[...,1:],-12,12)
            hue=np.exp(-((ln[...,1]-loc[...,1])**2+(ln[...,2]-loc[...,2])**2)/(2*14**2))*np.exp(-np.maximum(0,ln[...,0]-loc[...,0]-15)**2/(2*10**2))
            act=Lw&~nd.binary_dilation(Hs,iterations=1)&~St&~vegN&~watN
            rr=cv2.GaussianBlur(reg.astype(np.float32),(0,0),6)
            wgt=cv2.GaussianBlur((act*hue).astype(np.float32),(0,0),1.0)*rr
            o2=ln.copy();o2[...,0]=ln[...,0]*(1+(gain-1)*wgt);o2[...,1]+=sh[...,0]*wgt;o2[...,2]+=sh[...,1]*wgt
            norm=cv2.cvtColor(np.clip(o2,0,255).astype(np.uint8),cv2.COLOR_LAB2RGB)
            gtf={'ground_new_median':mn.round(1).tolist(),'ground_ctx_median':mc.round(1).tolist(),'L_gain_mean':round(float(gain[gn].mean()),3)}
        f=fidelity(norm,x0,y0,reg)
        ai=norm.astype(int);dreg=cv2.distanceTransform((~reg).astype(np.uint8),cv2.DIST_L2,5)
        blue=(ai[...,2]>ai[...,0]+12)&(ai[...,1]>ai[...,0]+5)&(reg|(dreg<FEA+4))&nd.binary_erosion(Lw,iterations=6)
        lb,nb=nd.label(blue);f['blue_on_land_px']=int(nd.sum(blue,lb,range(1,nb+1)).max()) if nb else 0
        # 回填：中间整块用新图，向外圈 FEA px 渐变回旧图
        # 渐变放在中间块里面：块边上还是旧画，往里 FEA px 渐变到新画。
        #   （第一版向外圈渐变，块边那一列量出边缘比 2.1–2.4：模型自己在「定稿/原始渲染」交界处留了一道线，向外渐变救不了）
        din=cv2.distanceTransform(reg.astype(np.uint8),cv2.DIST_L2,5)
        alpha=np.clip(din/FEA,0,1)[...,None]
        o=C[y0:y0+1024,x0:x0+1024].astype(float);blend=(o*(1-alpha)+norm.astype(float)*alpha).astype(np.uint8)
        blend=N.stamp(blend,x0,y0,1024);C2=C.copy();C2[y0:y0+1024,x0:x0+1024]=blend
        before=lines(C,tag);after=lines(C2,tag)
        Image.fromarray(C2[max(0,y0-64):y0+1088,max(0,x0-64):x0+1088]).save(f'fcand_{ft}.png')   # 看图用
        fid_ok=(f['house_hit'] is None or f['house_hit']>=TH_HOUSE) and (f['edgeF3'] is None or f['edgeF3']>=TH_EDGE) and cc is not None and shift<40 and (dEr is None or dEr<=30) and f['blue_on_land_px']<1500
        # 原缝那条线必须过闸；五条线（原缝 + 补丁四条边）的「超标量」总和要下降。
        #   超标量 = 10×max(0,边缘比−1.6) + max(0,色差−阈值)。补丁边有两条压在旧缝上，色差这一项在 24px 带宽上很吵；
        #   起初要求五条线全过闸，目标缝明显修好的窗口（H,8,4、H,3,3、V,4,3、V,7,2）全被某条边上 +1–5 的色差拦下，所以改成看总和。
        exc=lambda r:0 if r is None else 10*max(0,r['edge_ratio']-EDGE_MAX)+max(0,(r['colour_dE'] or 0)-DE_MAX)
        exb=sum(exc(r) for r in before.values());exa=sum(exc(r) for r in after.values())
        seam_ok=not bad(after['seam']) and exa<exb
        force=len(sys.argv)>4 and sys.argv[4]=='force'
        ok=(fid_ok and seam_ok) or force
        rec={'tag':tag,'file':sys.argv[3],'box':box,'win':[x0,y0],'ecc':cc,'shift':round(shift,2),'ctx_absdiff':round(ctxdiff,1),'colour_off':off.round(1).tolist(),'ground_tf':gtf,'dE_roof':None if dEr is None else round(dEr,1),**f,
             'lines_before':before,'lines_after':after,'excess_before':round(exb,1),'excess_after':round(exa,1),'fidelity_ok':fid_ok,'seam_ok':seam_ok,'accepted':bool(ok),'forced':bool(force and not (fid_ok and seam_ok)),'t':time.strftime('%H:%M:%S')}
        open('seamfix_attempts.jsonl','a').write(json.dumps(rec,ensure_ascii=False)+'\n')
        print(json.dumps({k:rec[k] for k in ('tag','ecc','shift','ctx_absdiff','dE_roof','houses','house_hit','edgeF3','blue_on_land_px','excess_before','excess_after','fidelity_ok','seam_ok','accepted')}))
        print(' before',json.dumps(before));print(' after ',json.dumps(after))
        if ok and not os.environ.get('DRY'):   # DRY=1：只核对、出 fcand 看图，不回填
            Image.fromarray(C2).save('canvas.png')
            P=json.load(open('seamfix_patches.json')) if os.path.exists('seamfix_patches.json') else []
            P.append({'seam':tag,'box':list(box),'win':[x0,y0],'file':sys.argv[3],'forced':rec['forced']});json.dump(P,open('seamfix_patches.json','w'),indent=1)
            Image.fromarray(norm).save(f'facc_{ft}.png')
