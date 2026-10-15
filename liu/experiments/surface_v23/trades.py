# -*- coding: utf-8 -*-
"""surface_v23 · 行当统一后的文本冲突统计。——Hark（刘线）

统一行当 = 经济层生计（docs/living/xerolophos/trades.json，surface.py 产出），手工铺/作坊且原散列行当是手艺时用原行当做细分。
已有文本（stories.json 10 户深度故事、voices.json 385 户邻居讲述、talk.json 街坊议论）不改写，只检查：
  文本里提到「这一家自己的行当」（故事取 meta 里的行当词；邻居讲述/议论取该户被讲那一家的原散列行当）的关键词，
  且那一年统一行当与它不相容 → 记一条冲突。关键词表、相容表都写进 conflicts.json，页面用同一张表。
页面处理：此刻(now)与屋里物件(obj)冲突的那几年不显示、换回按统一行当的日常；故事段与邻居讲的段落照常显示、加 ⚠ 标记；
街坊议论的引语冲突则换下一条。房上标签/卡片副行改读统一行当（标签里与统一行当矛盾的行当词去掉、括注统一行当）。
输入：.path/fams.json（dump_fams.py 从页面导出的散列人家）、trades.json、stories/voices/talk/houses.json。输出：docs/living/xerolophos/conflicts.json、本目录 conflicts.json（明细）。
"""
import os, json, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PAGE = os.path.join(ROOT, "docs", "living", "xerolophos")

KW = {   # 文本里指向本户行当的词
    "织工": ["织机", "织布", "梭", "经线", "织工", "一匹布", "紫边"],
    "陶匠": ["窑", "拉坯", "坯", "陶匠", "烧裂", "转盘"],
    "鞋匠": ["鞋匠", "绱鞋", "鞋楦", "补鞋", "做鞋", "皮子", "锥子", "鞋跟"],
    "面包师": ["揉面", "面团", "出炉", "饼", "炉子", "面缸", "面粉", "面包"],
    "酒馆老板": ["酒馆", "酒客", "舀酒", "柜台", "醉汉", "酒罐", "兑了水", "倒酒", "酒碗"],
    "运水人": ["运水", "挑水", "卖水", "水罐", "水桶", "担水", "挑着水"],
    "石匠": ["石匠", "凿", "石料", "石头"],
    "铜匠": ["铜匠", "打铜", "铜锅", "铜器", "锤"],
    "兵": ["辅兵", "军营", "兵营", "当兵", "军饷"],
    "搬运工": ["搬运", "扛", "码头"],
    "教书先生": ["文法", "学生", "教书", "讲课", "学童"],
    "菜农": ["种菜", "菜园", "菜地", "卖菜"],
    "水手": ["粮船", "水手", "出海", "船上"],
}
COMPAT = {   # 文本行当 → 相容的经济层生计
    "织工": ["手工铺", "作坊"], "陶匠": ["手工铺", "作坊"], "鞋匠": ["手工铺", "作坊"], "铜匠": ["手工铺", "作坊"],
    "面包师": ["面包"], "酒馆老板": ["面包"], "运水人": ["运水人"], "石匠": ["营造"], "兵": ["兵户"],
    "搬运工": ["码头脚夫", "雇工", "装卸行"], "教书先生": ["体面户"], "菜农": ["菜农"], "水手": ["码头脚夫", "装卸行", "渔户", "船修", "港货商"],
}
STORY_TRADE = {   # 深度故事：meta 里的行当词 → 文本行当；标题里的行当词（去掉后括注统一行当）
    "13068": ("织布", "织工", "织布的"), "14251": ("皇家辅兵", "兵", ""), "16975": ("石匠", "石匠", "石匠"), "13821": ("面包铺", "面包师", "面包师"),
    "13654": ("铜匠", "铜匠", "铜匠"), "12482": ("搬运工", "搬运工", ""), "17158": ("搬运工", "搬运工", ""), "12250": ("文法教师", "教书先生", "教书先生"),
    "13196": ("种菜", "菜农", ""), "17084": ("粮船水手", "水手", "水手"),
}


def main():
    T = json.load(open(os.path.join(PAGE, "trades.json")))
    fams = json.load(open(os.path.join(HERE, ".path", "fams.json")))
    S = json.load(open(os.path.join(PAGE, "stories.json")))
    V = json.load(open(os.path.join(PAGE, "voices.json")))
    TK = json.load(open(os.path.join(PAGE, "talk.json")))["years"]
    PH = json.load(open(os.path.join(PAGE, "houses.json")))
    HB = {r[0]: (r[2], r[3]) for r in PH["houses"]}
    LN = T["liv"]; TERM = T["term"]; CRAFT = set(T["craft_liv"]); FINE = set(T["craft_fine"])

    def code(h, Y):
        s = T["h"].get(str(h))
        if not s:
            return None
        k = min(max(Y, 40), 70) - 40
        if s[k] != ".":
            return ord(s[k]) - 97
        for d in range(1, 31):
            for kk in (k - d, k + d):
                if 0 <= kk < len(s) and s[kk] != ".":
                    return ord(s[kk]) - 97
        return None

    def fam_at(h, Y):
        F = fams.get(str(h))
        if not F:
            return None
        f = F[0]
        for x in F:
            if x[0] <= Y:
                f = x
        return f

    def compat(text_trade, h, Y):
        c = code(h, Y)
        if c is None:
            return True, "（账本无户）"
        if LN[c] not in COMPAT.get(text_trade, []):
            return False, TERM[c]
        return True, TERM[c]

    def mentions(text, tr):
        return any(k in text for k in KW.get(tr, []))

    conf = {}     # 页面键 → 冲突年份列表（或 [0] 表示与年份无关）
    det = []
    cnt = collections.Counter(); items = collections.Counter()

    def add(key, kind, h, years, text, tr, uni):
        conf[key] = sorted(set(years))
        cnt[kind] += 1
        det.append(dict(key=key, kind=kind, house=h, years=[min(years), max(years)], text_trade=tr, unified=uni, text=text[:80]))

    # ---- 深度故事
    for sid, st in S.items():
        h = int(sid); b, d = HB.get(h, (0, 9999))
        tok, tr, _ = STORY_TRADE[sid]
        last = max(m["d"] for m in st["members"])
        shown = [Y for Y in range(max(b, 1), min(d, last, 71)) if Y <= 70]
        for i, (y, t) in enumerate(st["beats"]):
            items["故事段"] += 1
            if mentions(t, tr):
                ok, u = compat(tr, h, y)
                if not ok:
                    add(f"s:{sid}:beat:{i}", "故事段", h, [y], t, tr, u)
        for fld in ("quote", "want", "fear"):
            items["故事其他"] += 1
            t = st.get(fld, "")
            if mentions(t, tr):
                bad = [Y for Y in shown if not compat(tr, h, Y)[0]]
                if bad:
                    add(f"s:{sid}:{fld}", "故事其他", h, bad, t, tr, compat(tr, h, bad[0])[1])
        t = "".join(st.get("object", [])); items["故事其他"] += 1
        if mentions(t, tr):
            bad = [Y for Y in shown if not compat(tr, h, Y)[0]]
            if bad:
                add(f"s:{sid}:obj", "故事其他", h, bad, t, tr, compat(tr, h, bad[0])[1])
        for per, t in st["now"].items():
            items["此刻"] += 1
            if mentions(t, tr):
                bad = [Y for Y in shown if not compat(tr, h, Y)[0]]
                if bad:
                    add(f"s:{sid}:now:{per}", "此刻", h, bad, t, tr, compat(tr, h, bad[0])[1])
        # 标签/副行
        bad = [Y for Y in shown if not compat(tr, h, Y)[0]]
        if bad:
            cnt["故事标签/副行（改读统一行当）"] += 1
            det.append(dict(key=f"s:{sid}:label", kind="故事标签/副行", house=h, years=[min(bad), max(bad)], text_trade=tr, unified=compat(tr, h, bad[0])[1], text=st["title"] + " | " + st["meta"]))
    # ---- 邻居讲述（文本行当 = 被讲那一家的原散列行当）
    for vid, v in V.items():
        h = int(vid)
        F = [f for f in fams.get(vid, []) if f[0] == v["fam"]]
        if not F:
            continue
        tr = F[0][1]
        nh = v["nar"]["house"]
        for i, (y, t) in enumerate(v["life"]):
            items["邻居讲的段落"] += 1
            if mentions(t, tr):
                ok, u = compat(tr, h, y)
                if not ok:
                    add(f"v:{vid}:life:{i}", "邻居讲的段落", h, [y], t, tr, u)
            nf = fam_at(nh, y)                        # 讲述者自己的行当（「——X家的某某说」+ 第一人称提到自家活计）
            if nf and nf[1] != tr and mentions(t, nf[1]):
                ok, u = compat(nf[1], nh, y)
                if not ok:
                    add(f"v:{vid}:life:{i}:n", "邻居讲的段落（讲述者行当）", nh, [y], t, nf[1], u)
        ny = v.get("nowY") or []
        yrs = list(range(ny[0], ny[1] + 1)) if ny else []
        nows = v["now"] if isinstance(v["now"], dict) else {"day": v["now"]}
        for per, t in nows.items():
            items["此刻"] += 1
            if t and mentions(t, tr):
                bad = [Y for Y in yrs if not compat(tr, h, Y)[0]]
                if bad:
                    add(f"v:{vid}:now:{per}", "此刻", h, bad, t, tr, compat(tr, h, bad[0])[1])
        t = "".join(v.get("obj", [])); items["屋里物件"] += 1
        if mentions(t, tr):
            ys = yrs or [v["life"][-1][0]]
            bad = [Y for Y in range(min(ys + [v["life"][0][0]]), 71) if not compat(tr, h, Y)[0]]
            if bad:
                add(f"v:{vid}:obj", "屋里物件", h, bad, t, tr, compat(tr, h, bad[0])[1])
    # ---- 街坊议论引语
    for Y, rows in TK.items():
        Y = int(Y)
        for ti, t in enumerate(rows):
            for k, (h, q) in enumerate([[t["quote_house"], t["quote"]]] + [list(a) for a in t.get("alt", [])]):
                items["街坊议论引语"] += 1
                f = fam_at(h, Y)
                if str(h) in S:
                    tr = STORY_TRADE[str(h)][1]
                elif f:
                    tr = f[1]
                else:
                    continue
                if mentions(q, tr):
                    ok, u = compat(tr, h, Y)
                    if not ok:
                        add(f"t:{Y}:{ti}:{k}", "街坊议论引语", h, [Y], q, tr, u)
    # ---- 普通人家卡片副行：原散列行当 vs 统一行当（不是文本冲突，是替换了多少）
    rep = collections.Counter(); tot = 0
    for hs, F in fams.items():
        h = int(hs); b, d = HB.get(h, (0, 9999))
        for Y in range(max(b, 40), min(d, 71)):
            c = code(h, Y)
            if c is None:
                continue
            f = fam_at(h, Y); tot += 1
            uni = f[1] if (c in CRAFT and f[1] in FINE) else TERM[c]
            rep["同" if uni == f[1] else "改"] += 1
    out = dict(_doc="surface_v23 · 统一行当后与已有文本冲突的条目（文本不改写）。键：s:故事房id:段 / v:邻居讲述房id:段 / t:年:议题序:引语序；值 = 冲突年份。kw/compat/story 供页面判断标签与副行。——Hark（刘线）",
               kw=KW, compat=COMPAT, story={k: dict(token=v[0], trade=v[1], strip=v[2]) for k, v in STORY_TRADE.items()}, c=conf)
    json.dump(out, open(os.path.join(PAGE, "conflicts.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    summary = dict(conflicts_by_kind=dict(cnt), items_checked=dict(items), total_text_conflicts=sum(v for k, v in cnt.items() if "标签" not in k),
                   card_trade_house_years_40_70=dict(total=tot, **rep),
                   by_text_trade=dict(collections.Counter(x["text_trade"] for x in det if x["kind"] != "故事标签/副行")),
                   by_unified=dict(collections.Counter(x["unified"] for x in det if x["kind"] != "故事标签/副行")))
    json.dump(dict(summary=summary, detail=det), open(os.path.join(HERE, "conflicts.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for x in det:
        if x["kind"] == "故事标签/副行":
            print(x)


if __name__ == "__main__":
    main()
