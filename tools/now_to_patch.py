import sys
K=['morning','day','evening','night']
for line in open(sys.argv[1],encoding='utf-8'):
    line=line.strip()
    if not line: continue
    p=line.split('|')
    assert len(p)==5,line[:40]
    for k,t in zip(K,p[1:]): print(f'{p[0]}\tnow.{k}\t{t}')
