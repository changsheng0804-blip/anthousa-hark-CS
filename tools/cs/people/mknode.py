"""把南港的长卷页（nangang/scroll.html，唯一的源）复制成别的节点的页，只换标题、去掉南港才有的 2D/3D 链接。
用法：python3 tools/cs/people/mknode.py gucheng 古城
数据要先生成：NH=2800 folk.py <节点> 60 → signs.py <节点>"""
import sys,os,re
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
q,name=sys.argv[1],sys.argv[2]
s=open(os.path.join(ROOT,'docs/living/nodes/nangang/scroll.html'),encoding='utf-8').read()
s=s.replace('南港 · 长卷',name+' · 长卷')
s=re.sub(r'<a href="\./">2D</a>\s*·\s*<a href="3d\.html">3D</a>','',s)
open(os.path.join(ROOT,'docs/living/nodes',q,'scroll.html'),'w',encoding='utf-8').write(s)
print('wrote',q,'scroll.html')
