"""记一条所有者评语：python tools/cs/factory/verdict.py <版本> 留|再来 ["哪里不对"] ["补上的检查名"]
再来 + 机器当时判过 = 假成功；没写补上的检查，accept.py 会一直标红，直到补上。"""
import json, os, sys
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verdicts.json')
d = json.load(open(F)); v, o = sys.argv[1], sys.argv[2]
e = next((x for x in d['verdicts'] if x['v'] == v), None)
if not e: sys.exit(f'没有 {v}')
e['owner'] = o
if len(sys.argv) > 3: e['issue'] = sys.argv[3]
if len(sys.argv) > 4: e['check'] = sys.argv[4]
json.dump(d, open(F, 'w'), ensure_ascii=False, indent=1); print(e)
