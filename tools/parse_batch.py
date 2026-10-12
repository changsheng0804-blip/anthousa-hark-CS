"""compact batch text -> json.  Format per household:
#id
L year text        (2-3 lines)
O object|what neighbours say about it
N morning|day|evening|night
"""
import json,sys
K=['morning','day','evening','night']
out={};cur=None
for line in open(sys.argv[1],encoding='utf-8'):
    line=line.rstrip('\n').strip()
    if not line: continue
    if line.startswith('#'):
        cur=line[1:].strip(); out[cur]={'life':[]}; continue
    tag,rest=line[0],line[1:].strip()
    e=out[cur]
    if tag=='L':
        y,t=rest.split(' ',1); e['life'].append([int(y),t.strip()])
    elif tag=='O': e['obj']=rest.split('|',1)
    elif tag=='N':
        p=rest.split('|'); assert len(p)==4,(cur,rest); e['now']=dict(zip(K,p))
    else: raise SystemExit('bad tag '+line)
json.dump(out,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=0)
print(len(out),'households ->',sys.argv[2])
