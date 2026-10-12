import sys,re
p,bp=sys.argv[1],sys.argv[2]
def blocks(t):
    out={};order=[];cur=None
    for line in t.split('\n'):
        if line.startswith('#'): cur=line[1:].strip(); order.append(cur); out[cur]=[line]
        elif cur: out[cur].append(line)
    return out,order
A,oa=blocks(open(p).read()); B,_=blocks(open(bp).read())
for k,v in B.items():
    assert k in A,k; A[k]=[l for l in v if l.strip()]
open(p,'w').write('\n'.join('\n'.join(l for l in A[k] if l.strip()) for k in oa)+'\n')
print('replaced',len(B))
