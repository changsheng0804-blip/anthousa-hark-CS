"""CS 线 · /goal 3 项 6：瓦片页的年份轴（一处定）。-657 到 70：0 年以前每隔 ~200 年一个（-657 建城、-400、-200），0 年起每 10 年一套。
关键年（各街区 scene.json 的 keys：40/50/60）的地面在 docs/living/<q>/ground_<年>.jpg；其余年份的地面在 out/ground_y/<q>/（不进 docs，tile_bake 缺了会自己叫 ground_ng 补）。"""
import os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
TILE_YEARS = [-657, -400, -200, 0, 10, 20, 30, 40, 50, 60, 70]
def ground_file(q, Y, write=False):
    """某街区某年的地面图路径：docs 里有就用 docs 的（关键年和 0 年），否则 out/ground_y/。write=True 时给「该写到哪」。"""
    import json
    keys = [k[0] for k in json.load(open(os.path.join(ROOT, 'docs', 'living', q, 'scene.json')))['keys']]
    if Y == 0 or Y in keys: return os.path.join(ROOT, 'docs', 'living', q, f'ground_{Y}.jpg')
    d = os.path.join(HERE, 'out', 'ground_y', q)
    if write: os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'ground_{Y}.jpg')
def ground_year(q, Y):
    """这一年用哪一张地面：年份轴上的年份用自己的，其余按「第一个 ≥Y 的关键年」（街区页老规则）。"""
    import json
    keys = [k[0] for k in json.load(open(os.path.join(ROOT, 'docs', 'living', q, 'scene.json')))['keys']]
    if Y in TILE_YEARS: return Y
    return min([k for k in keys if Y <= k] or [keys[-1]])
