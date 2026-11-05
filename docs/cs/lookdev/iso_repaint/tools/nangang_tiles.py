# 全幅 canvas → 看图页瓦片：按 mosaic_crop.json 裁掉四周纸边，三级（1/4、1/2、1），512px JPEG；写 meta.json（带版本号 v，页面拿它给瓦片加 ?v= 防缓存）。
# 用法（工作目录 = 原始件目录）：python3 nangang_tiles.py canvas.png OUTDIR VERSION
import sys,os,json,shutil
from PIL import Image
f,od,ver=sys.argv[1],sys.argv[2],sys.argv[3]
cx0,cy0,cx1,cy1=json.load(open('mosaic_crop.json'))['crop']
im=Image.open(f).convert('RGB').crop((cx0,cy0,cx1,cy1));im.save('mosaic_full.png')
W,H=im.size;T=512;levels=[]
for z,s in enumerate((0.25,0.5,1.0)):
    d=os.path.join(od,f'z{z}');shutil.rmtree(d,ignore_errors=True);os.makedirs(d)
    w,h=round(W*s),round(H*s);L=im.resize((w,h),Image.LANCZOS) if s!=1 else im
    nx,ny=(w+T-1)//T,(h+T-1)//T
    for x in range(nx):
        for y in range(ny):L.crop((x*T,y*T,min(w,x*T+T),min(h,y*T+T))).save(f'{d}/{x}_{y}.jpg',quality=82,optimize=True)
    levels.append({'z':z,'scale':s,'w':w,'h':h,'nx':nx,'ny':ny})
json.dump({'W':W,'H':H,'tile':T,'v':ver,'levels':levels},open(os.path.join(od,'meta.json'),'w'))
print(W,H,ver,[(l['nx'],l['ny']) for l in levels])
