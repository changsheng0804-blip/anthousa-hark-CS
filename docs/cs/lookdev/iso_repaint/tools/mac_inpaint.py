# 在主人 Mac mini（M4，MPS）上跑的本地 inpaint：SD1.5-inpainting（fp16 权重，ModelScope 国内源下载）。
# 只重画缝上的窄带（mask 内），mask 外的像素在回到沙箱后按原图原样贴回，所以上下文逐像素不变。
# 用法（Mac 上，venv 在 ~/AI工作区/anthousa-local/inpaint/.venv）：python mac_inpaint.py jobs.json
#   jobs.json: [{"name":..,"img":"x.jpg","band":[x0,y0,x1,y1],"seeds":[1,2,3],"strength":0.6}]  band 是裁片里的 mask 矩形
import json,sys,time,torch,numpy as np
from PIL import Image,ImageFilter
from diffusers import StableDiffusionInpaintPipeline
t0=time.time()
pipe=StableDiffusionInpaintPipeline.from_pretrained('sd15inp',torch_dtype=torch.float16,variant='fp16',safety_checker=None,requires_safety_checker=False).to('mps')
pipe.set_progress_bar_config(disable=True)
P=("isometric city map illustration, 1990s city-builder game tile art, small late roman town, terracotta and brick-red tile roofs, cream walls, "
   "warm honey-yellow open ground, grey-beige stone lanes, dark cypress trees, crisp thin dark outlines, flat shading, soft short shadows, seamless")
NEG="blurry, photo, realistic, text, watermark, border, seam, line, modern, cars, glass, distorted"
log={'load_s':round(time.time()-t0,1),'jobs':[]}
for j in json.load(open(sys.argv[1])):
    im=Image.open(j['img']).convert('RGB');W,H=im.size
    m=Image.new('L',(W,H),0);x0,y0,x1,y1=j['band'];m.paste(255,(x0,y0,x1,y1))
    for s in j.get('seeds',[1]):
        t=time.time()
        out=pipe(prompt=P,negative_prompt=NEG,image=im,mask_image=m,width=W,height=H,num_inference_steps=j.get('steps',30),
                 strength=j.get('strength',0.6),guidance_scale=j.get('cfg',6.0),generator=torch.Generator('cpu').manual_seed(s)).images[0]
        a=np.asarray(out);ok=bool(np.isfinite(a).all() and a.mean()>5)
        out.crop((x0,y0,x1,y1)).save(f"{j['name']}_s{s}.png")
        log['jobs'].append({'name':j['name'],'seed':s,'sec':round(time.time()-t,1),'ok':ok})
        print(log['jobs'][-1],flush=True)
json.dump(log,open('mac_inpaint_log.json','w'))
print(log)
