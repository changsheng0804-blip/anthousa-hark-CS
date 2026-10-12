"""apply a TSV patch (id<TAB>field<TAB>text) to voices.json; field = life0..2 | obj ('物件|说明') | now.morning etc."""
import json,sys
p=sys.argv[1]; V=json.load(open(p,encoding='utf-8')); n=0
for f in sys.argv[2:]:
    for line in open(f,encoding='utf-8'):
        line=line.rstrip('\n')
        if not line.strip(): continue
        k,fl,t=line.split('\t')
        e=V[k]
        if fl.startswith('life'): e['life'][int(fl[4:])][1]=t
        elif fl=='obj': e['obj']=t.split('|',1)
        elif fl.startswith('now.'):
            if not isinstance(e.get('now'),dict): e['now']={}
            e['now'][fl[4:]]=t
        else: raise SystemExit('bad field '+fl)
        n+=1
json.dump(V,open(p,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
print('applied',n)
