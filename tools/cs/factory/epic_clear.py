#!/usr/bin/env python3
"""/goal 4 G3 史诗地块清场（派生表）。world.json 的史诗建筑（多边形结构，不含港口/片区/农田/城墙/城门）存续期内，脚印下不许有房：
  · 房在建成年 eb 时已存在 → 拆于 eb（h[3]=eb）；建成年之后才开工的 → 不建（h[3]=h[2]）；
  · 记号：h[13:]=['epic', 原拆毁年, 史诗 id]（landmarks_city 对 len>13 的房不动；撤销见 undo）；
  · 清掉的房记进 tiles/epic_cleared.json（叠层「旧街坊」可读；id、年、史诗、街区）。
街：streets_ng 已让路给史诗（检查 check_epic_clear.py ② 全城 0 段）；此处只清房。底账 world.json 一字不动。
  python3 tools/cs/factory/epic_clear.py        # 幂等：先撤自己上一次的记号再重做
——Hark（CS线）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import landmarks_city as L
from shapely.geometry import Polygon
SKIP = {'district', 'farmland', 'wall', 'gate', 'harbor'}
TOL = 1e-3   # 相交面积占房面积 ≤ 千分之一不算压（同 check_epic_clear.py）
def undo(HS):
    for h in HS:
        if len(h) > 13 and h[13] == 'epic': h[3] = h[14]; del h[13:]
def main():
    EP = [(e, Polygon(e['geom']['coords']).buffer(0), e['built'], e['destroyed'] if e['destroyed'] is not None else 9999)
          for e in L.W['structures'] if e['geom']['type'] == 'polygon' and e['type'] not in SKIP]
    out = {}; skipped = []
    for q in L.QS:
        p = os.path.join(L.LIV, q, 'houses_street.json'); D = json.load(open(p)); HS = D['houses']; undo(HS)
        for h in HS:
            if h[3] <= h[2]: continue
            Q = L.wpoly(q, h[4]).buffer(0)
            for e, P, eb, ee in EP:
                if not (h[2] < ee and h[3] > eb and Q.intersects(P) and Q.intersection(P).area > TOL * max(Q.area, 1e-9)): continue
                if len(h) > 13: skipped.append(f'{q} h{h[0]} 已是地标/并入行，没清'); break
                old = h[3]; h += ['epic', old, e['id']]; h[3] = max(h[2], eb)
                out.setdefault(f'h{h[0]}', {'id': f'h{h[0]}', 'epic': e['id'], 'year': h[3], 'from': h[2], 'was': old, 'q': set()})['q'].add(q)
                break
        json.dump(D, open(p, 'w'), separators=(',', ':'))
    rows = sorted(({**v, 'q': sorted(v['q'])} for v in out.values()), key=lambda r: r['id'])
    json.dump({'src': 'tools/cs/factory/epic_clear.py（world.json 史诗多边形脚印）', 'cleared': rows}, open(os.path.join(L.OUT, 'epic_cleared.json'), 'w'), ensure_ascii=False, indent=0)
    print(f'清掉 {len(rows)} 栋', *[f"{r['id']} {r['epic']} {r['from']}→{r['year']}" for r in rows]); print('\n'.join(skipped))
if __name__ == '__main__': main()
