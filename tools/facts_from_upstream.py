"""刘线 · 只读引入谭线（上游）的空间事实。
上游产出的街名（v18 name_streets → streetnames.json）、街区功能（v21 blocks_xero → blocks.json，
v23 district_rules → houses.json 第 9 栏）、路口设施（junctions.json）原样复制到
docs/living/xerolophos/facts_upstream/，并推演出刘线页面要用的门牌表 addr.json。
刘线不搬上游的画法：页面不画街、不画街区，只在文字里引用这些事实。

usage: python3 tools/facts_from_upstream.py [UPSTREAM_REF]   (default upstream/main)

门牌的推法（刘线自己的，和上游页面的 streetAt 同一规则取街）：
  - 房子按上游 houses.json 里的新位置（v13 起房子挪到了街边地块）取形心；
  - 某一年，离形心 45px 以内、那年已经有名字的最近一条街，就是它的街（与上游卡片地址一致）；
  - 门牌：一条街上所有曾经挂在这条街的房子，按沿街方向排序，左手单号、右手双号，从街头起编；
    改名（如 48 年火后的新一街…、54 年运水人池街）不改门牌。
addr.json:
  {"src": 上游提交, "streets": [[现名, 起年, [[名, 起, 止], ...]], ...],
   "fn": {功能: 中文名}, "h": {房号: [功能, [[街序, 门牌, 起年, 止年], ...]]}}
  止年不含；没有落在任何街上的年份不写（页面显示「街名未定」）。
"""
import json, os, subprocess, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'docs', 'living', 'xerolophos')
OUT = os.path.join(XD, 'facts_upstream')
REF = sys.argv[1] if len(sys.argv) > 1 else 'upstream/main'
COPY = ['houses.json', 'streetnames.json', 'blocks.json', 'junctions.json']
MAXD = 45
YEARS = range(0, 61)


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, check=True).stdout


def main():
    sha = git('rev-parse', REF).decode().strip()
    os.makedirs(OUT, exist_ok=True)
    raw = {}
    for f in COPY:
        b = git('show', f'{sha}:docs/living/xerolophos/{f}')
        open(os.path.join(OUT, f), 'wb').write(b)
        raw[f] = json.loads(b)
    SN = raw['streetnames.json']
    HU = raw['houses.json']['houses']
    FN = {k: v[0] for k, v in raw['blocks.json']['fn'].items()}

    # segments of every named street
    segs = []  # (street index, seg index, ax, ay, bx, by, cumulative length at a)
    for si, st in enumerate(SN):
        p = st['p']; acc = 0.0
        for i in range(len(p) - 1):
            ax, ay = p[i]; bx, by = p[i + 1]
            segs.append((si, i, ax, ay, bx, by, acc)); acc += ((bx - ax) ** 2 + (by - ay) ** 2) ** .5
    S = np.array(segs, dtype=float)
    sidx = S[:, 0].astype(int)
    ax, ay, bx, by, acc = S[:, 2], S[:, 3], S[:, 4], S[:, 5], S[:, 6]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy + 1e-9

    def name_at(st, Y):
        for r in st['r']:
            if r[1] <= Y < r[2]: return r
        return None

    live = {Y: np.array([st['y'] <= Y and name_at(st, Y) is not None for st in SN]) for Y in YEARS}

    per_house = {}
    on_street = {}  # street index -> {house id: (arc position, side)}
    for h in HU:
        hid, built, dem, poly, dist = h[0], h[2], h[3], h[4], h[8]
        cx = sum(poly[0::2]) / (len(poly) // 2); cy = sum(poly[1::2]) / (len(poly) // 2)
        t = np.clip(((cx - ax) * dx + (cy - ay) * dy) / L2, 0, 1)
        ex, ey = cx - ax - t * dx, cy - ay - t * dy
        d2 = ex * ex + ey * ey
        cross = dx * (cy - ay) - dy * (cx - ax)
        yrs = []
        for Y in YEARS:
            if not (built <= Y < dem): yrs.append(None); continue
            m = live[Y][sidx] & (d2 < MAXD * MAXD)
            if not m.any(): yrs.append(None); continue
            j = int(np.argmin(np.where(m, d2, np.inf)))
            si = int(sidx[j])
            pos = float(acc[j] + t[j] * (L2[j] ** .5))
            on_street.setdefault(si, {}).setdefault(hid, (pos, 1 if cross[j] < 0 else 0))
            yrs.append(si)
        per_house[hid] = (dist, yrs)

    # house numbers: along the street, odd on the left hand, even on the right
    number = {}
    for si, hs in on_street.items():
        odd = sorted((v[0], k) for k, v in hs.items() if v[1] == 1)
        even = sorted((v[0], k) for k, v in hs.items() if v[1] == 0)
        for i, (_, k) in enumerate(odd): number[(si, k)] = 2 * i + 1
        for i, (_, k) in enumerate(even): number[(si, k)] = 2 * i + 2

    H = {}
    nostreet = 0
    for hid, (dist, yrs) in per_house.items():
        runs = []
        for Y, si in zip(YEARS, yrs):
            if si is None: continue
            if runs and runs[-1][0] == si and runs[-1][3] == Y: runs[-1][3] = Y + 1
            else: runs.append([si, number[(si, hid)], Y, Y + 1])
        for r in runs:
            if r[3] == 61: r[3] = 999  # still there at the end of the ledger
        if not runs: nostreet += 1
        H[str(hid)] = [dist, runs]
    streets = [[st['n'], st['y'], st['r']] for st in SN]
    out = {'_doc': '刘线 · tools/facts_from_upstream.py 由上游 streetnames/houses(第9栏 district)/blocks 推演的门牌表；只读事实，不含画法。',
           'src': sha, 'streets': streets, 'fn': FN, 'h': H}
    json.dump(out, open(os.path.join(OUT, 'addr.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    # junction facts named by street (well / oven / stall at a corner, with the year it appeared)
    J = []
    for x, y, yr, kind in raw['junctions.json']:
        t = np.clip(((x - ax) * dx + (y - ay) * dy) / L2, 0, 1)
        d2 = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
        Y = max(yr, 0)
        m = live[min(Y, 60)][sidx] & (d2 < MAXD * MAXD)
        nm = [SN[int(sidx[j])]['n'] for j in np.argsort(np.where(m, d2, np.inf))[:6] if m[j]]
        J.append([x, y, yr, kind, list(dict.fromkeys(nm))[:2]])
    json.dump({'src': sha, 'junctions': J}, open(os.path.join(OUT, 'junctions_named.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    # landmark spec cards (upstream v27–v30: tools/landmarks/*.json is the single source for special buildings);
    # copied whole, read-only; each fixed instance also gets its nearest named streets (year 60)
    LM = {}
    names = git('ls-tree', '--name-only', sha, 'tools/landmarks/').decode().split()
    for f in names:
        if f.endswith('.json'):
            sp = json.loads(git('show', f'{sha}:{f}'))
            LM[sp.get('id', os.path.basename(f)[:-5])] = sp
    FX = []
    for sid, sp in sorted(LM.items()):
        for it in sp.get('instances', {}).get('fixed', []):
            if it.get('quarter', 'xerolophos') != 'xerolophos' or 'xy' not in it: continue
            x, y = it['xy']
            t = np.clip(((x - ax) * dx + (y - ay) * dy) / L2, 0, 1)
            d2 = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            m = live[60][sidx] & (d2 < (MAXD * 3) ** 2)
            nm = [SN[int(sidx[j])]['n'] for j in np.argsort(np.where(m, d2, np.inf))[:12] if m[j]]
            FX.append({'spec': sid, 'key': it['key'], 'name': it.get('name_zh', sp.get('name_zh')), 'category': sp.get('category'),
                       'xy': it['xy'], 'built': it.get('built', sp.get('era', [0])[0]), 'until': it.get('until'),
                       'historic': sp.get('historic', False), 'streets_60': list(dict.fromkeys(nm))[:3]})
    # generated instances (church, bread steps, fountain, horrea, inn …) sit on house lots: column 10 = 'lm:<spec>'
    GX = []
    for h in HU:
        if len(h) > 9 and isinstance(h[9], str) and h[9].startswith('lm:'):
            poly = h[4]; x = sum(poly[0::2]) / (len(poly) // 2); y = sum(poly[1::2]) / (len(poly) // 2)
            sp = LM.get(h[9][3:], {})
            t = np.clip(((x - ax) * dx + (y - ay) * dy) / L2, 0, 1)
            d2 = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            m = live[60][sidx] & (d2 < MAXD * MAXD)
            nm = [SN[int(sidx[j])]['n'] for j in np.argsort(np.where(m, d2, np.inf))[:6] if m[j]]
            GX.append({'house': h[0], 'spec': h[9][3:], 'name': sp.get('name_zh'), 'category': sp.get('category'),
                       'xy': [round(x, 1), round(y, 1)], 'built': h[2], 'destroyed': h[3], 'district': h[8], 'streets_60': list(dict.fromkeys(nm))[:2]})
    json.dump({'src': sha, 'fixed_xerolophos': FX, 'generated_xerolophos': GX, 'specs': LM}, open(os.path.join(OUT, 'landmarks.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    log = git('log', '-1', '--format=%H %ad %s', '--date=short', sha).decode().strip()
    open(os.path.join(OUT, 'SOURCE.md'), 'w', encoding='utf-8').write(f"""# facts_upstream · 谭线空间事实（只读）

来源：tanxinhao2026-netizen/anthousa 提交 `{sha}`
（{log}）

| 文件 | 上游出处 | 刘线怎么用 |
|---|---|---|
| houses.json | v13 起房子挪到街边地块；v23 district_rules 第 9 栏 = 地块所在街区功能 | 只取位置推门牌、取第 9 栏作人家所在街区；id/建成年/拆毁年与刘线 houses.json 逐栋相同 |
| streetnames.json | v18 name_streets（街名、改名年份） | 街名、门牌、改名（原某某巷） |
| blocks.json | v21 blocks_xero（每年的街区及功能） | 功能中文名表 `fn` |
| junctions.json | v14/v16 路口的井、炉、摊 | `junctions_named.json`：每个路口设施挂到街名上，供写闲话参考 |
| addr.json | 刘线推演（tools/facts_from_upstream.py） | 页面人家卡片、街坊在说什么、相遇的街名 |
| landmarks.json | v27–v30 tools/landmarks/*.json 地标规格卡（蓄水池、浴场、兵营、城门、水渠桥、聚会所、教堂、面包台阶、泉亭、粮仓、客栈） | `fixed_xerolophos`：干山固定地标的位置/建成年/近旁街名；`generated_xerolophos`：落在房屋地块上的生成地标（上游 houses.json 第 10 栏 `lm:类型`）；`specs` 原样；供户籍挂设施、写闲话参考 |

刘线不引用上游的画法：页面仍画刘线自己的底图和房子，不画街道线、街名标注、街区色块。
复现：`python3 tools/facts_from_upstream.py {sha[:7]}`。
落在 45px 内没有任何街的房子：{nostreet} 栋（这些年份卡片显示「街名未定」）。
""")
    print('src', sha, 'houses', len(H), 'never on a street', nostreet)


if __name__ == '__main__':
    main()
