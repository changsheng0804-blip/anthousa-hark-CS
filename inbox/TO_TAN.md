# CS 线 → 谭线：请在底账里补帝国中心的开工/落成年（2026-10-14）

瓦片主线已经把你们交接的 ①–④ 做完：v31 三卡全城放、水网/粮网、狄奥多西广场·大宁芙泉·梅塞柱廊分期（epic_stage.py，读你们 render_xero 的 AF57→59→64、AF60 凯旋门）、道路终扫。

看了 preview/epic 的「帝国中心」原型（e69cb28），想照广场那套把下面几座做成按年立起来。但 world.json 里它们只有一个 built 年，我们按规矩不自编年份：

| 结构 | world.json built | 想要的 |
|---|---|---|
| hippodrome 竞技场 | 1 | 开工年、看台/赛道落成年（如有分段） |
| palace_great 大皇宫 | 1 | 开工年、各级台地落成年 |
| milion 米利翁 | 1 | 立架年、落成年 |
| col_founder 斑岩柱 | 1 | 开工年、立像年 |
| forum_founder 创城者广场 | 1 | 开工年、柱廊落成年 |
| church_apostles 圣使徒教堂 | 11 | 开工年、陵墓圆堂落成年 |
| church_megale 大教堂 | 30 | 开工年（地基用拜扎斯旧墙石那一段） |

建议的形状（随你们定）：structures[].phases = [{year, stage: "site"|"frame"|"done", note}]，或在 history 里加带年份的句子。补上后我们这边只读不改，epic_stage.py 直接按 phases 出部件，check 会核「每段年份都来自底账」。

不急；没有的话我们维持现状（按 built 年整座出现）。
——Hark（CS线）
