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

## 追加（同晚）：港口与码头也进了 phases

| 结构 | phases |
|---|---|
| harbor_julian 尤利安港 | 1 抛石筑堤 → 3 防波堤合拢、码头岸线 → 5 堤头灯塔、码头齐备 |
| granary_founder 创城者粮仓 | 1 清场 → 2 起墙 → 4 上瓦入库 |
| harbor_neorion 新港 | 11 打桩抛石 → 13 码头岸线与船坡 → 15 完工 |
| warehouse_horn 金角湾仓库 | 11 清场 → 12 起墙 → 14 上瓦 |
| harbor_theodosius 狄奥多西港 | 31 疏浚港池、抛石（水上作业）→ 32 防波堤合拢 → 33 完工 |

- 狄奥多西港是唯一早于 built 年开工的：编年史写死“第 33 年完工”，所以 done=33，前两段在水上。`check.py` 只给 harbor 这个例外：可以早开工，但必须恰好在 built 年 done，岸上拆房仍在 built 年。
- 编年史写了具体年份的粮仓（狄奥多西粮仓 34、特罗阿德粮仓 46“完工”、亚历山大粮仓 55）不加分期：它们在陆上，提前开工就得改拆房年，那是改正史，没动。按 built 年整座出现。
- 拜扎斯旧港 prosphorion（-657）不加。
- 底账统计（粮食上限等）仍按 built 年算，phases 只管画面。

## 再追加（10-14 夜）：城墙、城门、水道等 11 座也有 phases

| 结构 | phases |
|---|---|
| wall_founder | 1 基槽 → 3 墙身半高 → 5 雉堞方塔完工 |
| gate_founder | 1 清场 → 2 双塔起墙 → 4 门楼完工 |
| cistern_founder | 1 挖池 → 2 砖拱封顶 → 3 存水 |
| aq_great | 11 测坡开沟 → 13 渠道与石拱 → 16 通水 |
| aqb_outer / aqb_middle / aqb_valley | 11 拱基 → 13 拱券起架 → 15 渠槽合龙 |
| nymphaeum_great | 11 挖蓄水池 → 14 起墙 → 16 随通水开放 |
| barracks_gate | 11 清场 → 12 起墙 → 13 驻军入营 |
| tower_horn | 24 塔基 → 25 塔身 → 26 雉堞 |
| forum_theodosius | 57 划出（编年史）→ 59 铺地、柱廊起墙 → 60 凯旋门（part=arch）→ 64 纪功柱到顶、整座完工 |

- 都在各自 built 年开工、在同一个十年的编年史段内完工，编年史和拆房年不动。
- 写死落成年的（浴场 25、各座有年份的教堂/蓄水池/粮仓）和 -657 拜扎斯时期的不加。
- 统计（水、粮上限）照旧按 built 年算。

