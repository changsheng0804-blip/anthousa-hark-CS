# 修缝前后对照图：每行一条缝，左修前（canvas_pre_seamfix.png）右修后（canvas.png），100% 裁 560px 缩到 440px，红三角标缝的位置，标题写两边的分数。
# 用法（工作目录 = 原始件目录）：python3 nangang_seamfix_figure.py OUT.jpg
import sys,json
from PIL import Image,ImageDraw,ImageFont
B=Image.open('canvas_pre_seamfix.png');A=Image.open('canvas.png')
bj={(r['dir'],*r['a']):r for r in json.load(open('seams_before.json'))['all']}
aj={(r['dir'],*r['a']):r for r in json.load(open('nangang_seams_after.json'))['all']}
items=[('V',6,1,'北缘 (6,1)|(7,1)：半栋房子、两边描边画法不同'),('V',5,5,'岸线 (5,5)|(6,5)：一边沙岸一边石岸，直刀口'),('V',7,2,'(7,2)|(8,2)：两边空地色调不同'),('H',7,1,'(7,1)/(7,2) 横缝'),('V',2,4,'(2,4)|(3,4) 竖缝')]
F=ImageFont.truetype('/workspace/work/fonts/NotoSansCJKsc-Regular.otf',21)
S=560;D=440;rows=[]
for d,x,y,lab in items:
    cx,cy=(512*(x+1),512*y+256) if d=='V' else (512*x+256,512*(y+1))
    box=(cx-S//2,cy-S//2,cx+S//2,cy+S//2)
    row=Image.new('RGB',(2*D+30,D+40),'white');dr=ImageDraw.Draw(row)
    for i,(im,tag,j) in enumerate(((B,'修前',bj),(A,'修后',aj))):
        t=im.crop(box).resize((D,D),Image.LANCZOS);td=ImageDraw.Draw(t);m=D//2
        if d=='V':td.polygon([(m-9,0),(m+9,0),(m,14)],fill=(220,20,20));td.polygon([(m-9,D),(m+9,D),(m,D-14)],fill=(220,20,20))
        else:td.polygon([(0,m-9),(0,m+9),(14,m)],fill=(220,20,20));td.polygon([(D,m-9),(D,m+9),(D-14,m)],fill=(220,20,20))
        row.paste(t,(10+i*(D+10),36));r=j.get((d,x,y))
        dr.text((12+i*(D+10),4),f"{tag}　边缘比 {r['edge_ratio']}　色差 ΔE {r['colour_dE']}",fill=(40,30,20),font=F)
    rows.append((row,lab))
H=sum(r.height+34 for r,_ in rows)+10
out=Image.new('RGB',(2*D+30,H),'white');yy=0;dr=ImageDraw.Draw(out)
for r,lab in rows:
    dr.text((12,yy+2),lab,fill=(130,30,20),font=F);out.paste(r,(0,yy+30));yy+=r.height+34
out.save(sys.argv[1],quality=86);print(out.size)
