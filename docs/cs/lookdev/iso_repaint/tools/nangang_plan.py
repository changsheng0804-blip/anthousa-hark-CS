# 半窗滑动的贪心排序（Isopolis 做法）：象限 512²，窗口 2×2 象限；每个窗口至少有 1 个已画好的象限做上下文，只生成没画的陆地象限。
import numpy as np,json,sys
from PIL import Image
L=np.asarray(Image.open('mask_land.png').convert('L'))>127
QY,QX=L.shape[0]//512,L.shape[1]//512
q=L.reshape(QY,512,QX,512).mean(axis=(1,3));land={(x,y) for y in range(QY) for x in range(QX) if q[y,x]>0.03}
seed=(5,2);painted=set();plan=[]
def win(i,j):return [(i,j),(i+1,j),(i,j+1),(i+1,j+1)]
plan.append({'win':seed,'new':[c for c in win(*seed) if c in land],'ctx':[]});painted|=set(plan[0]['new'])
while land-painted:
    best=None
    for j in range(QY-1):
        for i in range(QX-1):
            w=win(i,j);new=[c for c in w if c in land and c not in painted];ctx=[c for c in w if c in painted]
            if not new or not ctx:continue
            # 先要 ≥2 个上下文象限，再要一次多出 2 个，再按离种子近
            d=abs(i-seed[0])+abs(j-seed[1])
            s=(min(len(ctx),2),min(len(new),2),sum(q[y,x] for x,y in new),-d)
            if best is None or s>best[0]:best=(s,(i,j),new,ctx)
    _,w,new,ctx=best;plan.append({'win':w,'new':new,'ctx':ctx});painted|=set(new)
json.dump({'q':q.round(3).tolist(),'land':sorted(land),'plan':plan},open('plan.json','w'))
print(len(land),'land quadrants;',len(plan),'windows')
for k,p in enumerate(plan):print(k,p['win'],'new',p['new'],'ctx',len(p['ctx']))
