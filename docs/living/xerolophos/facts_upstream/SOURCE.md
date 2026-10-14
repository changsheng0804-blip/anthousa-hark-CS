# facts_upstream · 谭线空间事实（只读）

来源：tanxinhao2026-netizen/anthousa 提交 `c72b1f3655129c5c4798daa9630fbbe12ad980d4`
（c72b1f3655129c5c4798daa9630fbbe12ad980d4 2026-10-13 merge from branches: b2 standby 3D pipeline (docs/3d.html viewer, engine/export_to_sim3d.py, RFC, Blender hillshade tool; Pages builds anthousa_world3d.json after build_all) + persons-layer schema doc from c-persons-layer. Tree-level merge: old branches share no history with main after the dd39b46 squash ——Hark）

| 文件 | 上游出处 | 刘线怎么用 |
|---|---|---|
| houses.json | v13 起房子挪到街边地块；v23 district_rules 第 9 栏 = 地块所在街区功能 | 只取位置推门牌、取第 9 栏作人家所在街区；id/建成年/拆毁年与刘线 houses.json 逐栋相同 |
| streetnames.json | v18 name_streets（街名、改名年份） | 街名、门牌、改名（原某某巷） |
| blocks.json | v21 blocks_xero（每年的街区及功能） | 功能中文名表 `fn` |
| junctions.json | v14/v16 路口的井、炉、摊 | `junctions_named.json`：每个路口设施挂到街名上，供写闲话参考 |
| addr.json | 刘线推演（tools/facts_from_upstream.py） | 页面人家卡片、街坊在说什么、相遇的街名 |
| landmarks.json | v27–v30 tools/landmarks/*.json 地标规格卡（蓄水池、浴场、兵营、城门、水渠桥、聚会所、教堂、面包台阶、泉亭、粮仓、客栈） | `fixed_xerolophos`：干山固定地标的位置/建成年/近旁街名；`generated_xerolophos`：落在房屋地块上的生成地标（上游 houses.json 第 10 栏 `lm:类型`）；`specs` 原样；供户籍挂设施、写闲话参考 |

刘线不引用上游的画法：页面仍画刘线自己的底图和房子，不画街道线、街名标注、街区色块。
复现：`python3 tools/facts_from_upstream.py c72b1f3`。
落在 45px 内没有任何街的房子：142 栋（这些年份卡片显示「街名未定」）。
