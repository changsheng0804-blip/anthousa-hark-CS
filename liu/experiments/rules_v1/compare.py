"""等价性核对：v1 compat 的交叉点集合 vs v0 调参版（仓库外 ../rules_v0_cross_SCOPE.json）。
逐条比：(甲, 乙) 对、模式集合、命中年份、分数；再比前 8（picks）。差异逐条列出。"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); C = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
def load(p): return {(r['a'], r['b']): r for r in json.load(open(p))}
def main(scope, quiet=False):
    v0 = load(os.path.join(C, f'rules_v0_cross_{scope}.json')); v1 = load(os.path.join(C, f'rules_v1_cross_{scope}_compat.json'))
    only0 = sorted(set(v0) - set(v1)); only1 = sorted(set(v1) - set(v0)); both = set(v0) & set(v1)
    dpat = [k for k in both if v0[k]['patterns'] != v1[k]['patterns']]
    dyrs = [k for k in both if v0[k]['patterns'] == v1[k]['patterns'] and v0[k]['years'] != v1[k]['years']]
    dsc = [k for k in both if v0[k]['patterns'] == v1[k]['patterns'] and v0[k]['years'] == v1[k]['years'] and abs(v0[k]['score'] - v1[k]['score']) > 1e-6]
    o0 = json.load(open(os.path.join(HERE, '..', 'rules_v0', 'out', f'{scope}.json'))); o1 = json.load(open(os.path.join(HERE, 'out', f'{scope}_compat.json')))
    p0 = [(p['a'], p['b'], p['score']) for p in o0['picks']]; p1 = [(p['a'], p['b'], p['score']) for p in o1['picks']]
    res = dict(scope=scope, v0=len(v0), v1=len(v1), identical_pairs=len(both), only_v0=len(only0), only_v1=len(only1),
               pattern_diff=len(dpat), years_diff=len(dyrs), score_diff=len(dsc), exact_match=len(both) - len(dpat) - len(dyrs) - len(dsc),
               top8_same=(p0 == p1), top60_same=[(r['a'], r['b'], r['score']) for r in o0['top']] == [(r['a'], r['b'], r['score']) for r in o1['top']])
    ex = dict(only_v0=[v0[k] for k in only0[:10]], only_v1=[v1[k] for k in only1[:10]],
              pattern_diff=[(v0[k]['patterns'], v1[k]['patterns'], k) for k in dpat[:10]],
              years_diff=[(k, v0[k]['years'], v1[k]['years'], v0[k]['patterns']) for k in dyrs[:10]],
              score_diff=[(k, v0[k]['score'], v1[k]['score'], v0[k]['rules'], v1[k]['rules']) for k in dsc[:10]])
    json.dump(dict(res, examples=ex), open(os.path.join(HERE, 'out', f'equiv_{scope}.json'), 'w'), ensure_ascii=False, indent=1)
    if not quiet: print(json.dumps(res, ensure_ascii=False)); print(json.dumps(ex, ensure_ascii=False)[:3000])
    return res
if __name__ == '__main__': main(sys.argv[1])
