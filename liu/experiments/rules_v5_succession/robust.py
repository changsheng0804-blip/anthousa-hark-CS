"""规则预演 v5 · 前 8 继承/选任冲突的稳健性：换种子（1–4，告发随机数变）、继承年龄 16、告发 1% / 3%。
「仍在」= 变体里同一职位同一组、±2 年内有冲突，且世袭一方（接手户）是同一户。
usage: python3 robust.py
"""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import succession as SU  # noqa: E402

VARIANTS = [('种子1', 14, 0.02, 1), ('种子2', 14, 0.02, 2), ('种子3', 14, 0.02, 3), ('种子4', 14, 0.02, 4),
            ('继承16岁', 16, 0.02, 0), ('告发1%', 14, 0.01, 0), ('告发3%', 14, 0.03, 0)]


def persists(c, C2):
    return any(d['o'] == c['o'] and d['k'] == c['k'] and abs(d['Y'] - c['Y']) <= 2 and d['new'] == c['new'] for d in C2)


if __name__ == '__main__':
    t = time.time()
    W, base, C = SU.main(14, 0.02, 0, write=False)
    top = C[:8]
    rows = [dict(rank=i + 1, Y=c['Y'], office=SU.OFFZH[c['o']], group=c['k'], kind=c['kind'], why=c['why'], distinct=c['distinct'],
                 old=f"{W.names[c['old']]}家 {W.keys[c['old']]}" if c['old'] >= 0 else '（空）',
                 new=f"{W.names[c['new']]}家 {W.keys[c['new']]}",
                 g1=f"{W.names[c['picks']['G1']]}家 {W.keys[c['picks']['G1']]}" if c['picks']['G1'] >= 0 else '（空）',
                 vote=f"{W.names[c['picks']['房主推举']]}家 {W.keys[c['picks']['房主推举']]}" if c['picks']['房主推举'] >= 0 else '（空）',
                 old_F=c['old'], new_F=c['new'], survive={}) for i, c in enumerate(top)]
    nconf = {'基准': len(C)}
    for name, A, p, s in VARIANTS:
        _, r2, C2 = SU.main(A, p, s, write=False); nconf[name] = len(C2)
        for row, c in zip(rows, top): row['survive'][name] = persists(c, C2)
    out = dict(top8=rows, n_conflicts=nconf, seconds=round(time.time() - t, 1))
    json.dump(out, open(os.path.join(HERE, 'out', 'robust_top8.json'), 'w'), ensure_ascii=False, indent=1, default=int)
    for r in rows: print(json.dumps({k: v for k, v in r.items() if k not in ('old_F', 'new_F')}, ensure_ascii=False))
    print(nconf, out['seconds'])
