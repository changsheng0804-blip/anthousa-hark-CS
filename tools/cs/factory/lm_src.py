"""CS 线 · /goal 3 项 3：地标只有一个来源——上游规格。
tools/landmark_registry.py + tools/landmarks/*.json（tanxinhao 线）里的固定地标，名字、故事、此刻、位置、建成年、到期年一律从这里读；
本线不再另存一份。规格的坐标是干山页的像素（页面框是世界格 (400,356)），这里换成瓦片像素 / 街区像素。
规格卡没有的地标（底账里有的）才用底账 + names_zh.json 兜底；那些就是「待上游收录」的候选。
用法（模块）：from lm_src import spec; spec()[key] → dict(name, story, now, built, until, tile_xy, poly_tile)；spec_xy(key, qbox) → 街区像素。 ——Hark（CS线）"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import landmark_registry as R
XB = (400, 356)   # 干山页的世界框左上角（格）；校验见 tools/cs/check_landmark_src.py
def _meta(): return json.load(open(os.path.join(ROOT, 'docs', 'living', 'tiles', 'meta.json')))
def spec():
    M = _meta(); S = M['scale']; OX, OY = M['origin']; ax, ay = (XB[0] - OX) * S, (XB[1] - OY) * S; out = {}
    for sid, sp, it in R.fixed('xerolophos'):
        d = dict(key=it['key'], spec=sid, name=it['name_zh'], story=it['story'], now=it.get('now', {}), built=it.get('built'), until=it.get('until'),
                 tile_xy=[it['xy'][0] + ax, it['xy'][1] + ay])
        if 'poly' in it: d['poly_tile'] = [[x + ax, y + ay] for x, y in it['poly']]
        out[it['key']] = d
    return out
