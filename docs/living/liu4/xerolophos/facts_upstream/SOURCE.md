# facts_upstream · 谭线空间事实（只读）

来源：tanxinhao2026-netizen/anthousa 提交 `3cd473c8139d6f5afeb530d9c65cfba0e884c560`
（3cd473c8139d6f5afeb530d9c65cfba0e884c560 2026-10-13 living v23: districts decide how lots are cut (district_rules.py: market narrow deep party-wall shopfronts, fine wide court lots no back row, workshop lots with yards, planned standard grid lots); houses take their lot's district; fix K joins road islands per year ——Hark）

| 文件 | 上游出处 | 刘线怎么用 |
|---|---|---|
| houses.json | v13 起房子挪到街边地块；v23 district_rules 第 9 栏 = 地块所在街区功能 | 只取位置推门牌、取第 9 栏作人家所在街区；id/建成年/拆毁年与刘线 houses.json 逐栋相同 |
| streetnames.json | v18 name_streets（街名、改名年份） | 街名、门牌、改名（原某某巷） |
| blocks.json | v21 blocks_xero（每年的街区及功能） | 功能中文名表 `fn` |
| junctions.json | v14/v16 路口的井、炉、摊 | `junctions_named.json`：每个路口设施挂到街名上，供写闲话参考 |
| addr.json | 刘线推演（tools/facts_from_upstream.py） | 页面人家卡片、街坊在说什么、相遇的街名 |

刘线不引用上游的画法：页面仍画刘线自己的底图和房子，不画街道线、街名标注、街区色块。
复现：`python3 tools/facts_from_upstream.py 3cd473c`。
落在 45px 内没有任何街的房子：138 栋（这些年份卡片显示「街名未定」）。
