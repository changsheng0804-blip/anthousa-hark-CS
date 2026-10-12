"""把同一处改动同步到 fleet_day.js、nangang/index.html、xerolophos/index.html 三处（旧串必须各出现恰好一次）"""
import sys
P=['tools/cs/factory/fleet_day.js','docs/living/nangang/index.html','docs/living/xerolophos/index.html']
def apply(old,new,paths=P,html_only=False):
    for p in paths:
        s=open(p).read()
        if s.count(old)!=1: sys.exit('%s: 旧串出现 %d 次'%(p,s.count(old)))
        open(p,'w').write(s.replace(old,new))
