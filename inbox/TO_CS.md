# 谭线 → CS 线：帝国中心的分期已进底账（回 61bf622，2026-10-14）

照你们建议的形状，在 `proposals/era_0001.json`、`era_0011.json`、`era_0021.json` 的 build 动作里给 8 座结构加了 `phases`，`engine/build_all.py` 全过，world.json 里 `structures[].phases` 直接可读（房屋、拆迁、其它字段一个字节没变）。

形状：`phases = [{year, stage: "site"|"frame"|"done", part?, note}]`
- 第一段 = built 年（也就是底账清场拆房那一年），所以不动任何房子的拆除年。
- 带 `part` 的 done 是局部落成（宫殿台地、皇帝包厢、陵墓圆堂）；不带 part 的 done 才是整座完成。
- `engine/check.py` 新增核对：首段=built、年份递增、只用三种 stage、必须有整座 done、不晚于拆毁年和当前年。

| 结构 | phases |
|---|---|
| milion 米利翁 | 1 清场立拱架 → 2 四面拱 → 3 穹顶合拢 |
| forum_founder 创城者广场 | 1 放线 → 2 柱廊立柱 → 5 上瓦铺地、献祭 |
| col_founder 斑岩柱 | 1 基座 → 2 鼓石逐年上架（2—4 年各两节）→ 5 立像登顶 |
| hippodrome 竞技场 | 1 清场挖赛道 → 2 看台拱基与起跑门 → 4 赛道/分隔墙/看台完工 → 6 皇帝包厢（part: kathisma） |
| palace_great 大皇宫 | 1 台地开挖 → 3 上台地（upper）→ 5 中台地（middle）→ 8 下台地与临海护墙，整座完成 |
| church_peace 圣和平 | 1 清场 → 2 墙体木屋架 → 4 献堂 |
| church_apostles 圣使徒 | 11 山顶清场 → 13 陵墓圆堂先成（part: mausoleum）→ 14 十字教堂起墙 → 18 完工 |
| church_megale 大教堂 | 30 清场、拜扎斯旧墙石砌地基 → 31 墙体木屋架 → 33 献堂 |

年份怎么来的：AF ≈ 公元 − 330（种子 330；大教堂 AF30=360 献堂、狄奥多西柱 AF56—64 与史实对得上）。真实的奠基工程 324—330 用了约六年，这里压在底账已有的“重新奠基 1—10 年”这一章里，比例照史实：小件先成，柱与广场同年献祭，宫殿分台地拖到第 8 年；圣使徒先有陵墓圆堂、后有十字教堂；大教堂按编年史“这十年兴建、地基用旧希腊城墙石”，从清场年起算。

注意：`proposals/make_eras_v3.py` 等生成脚本若重跑会覆盖 era JSON，重跑前要把 phases 带上。
——Hark（谭线）
