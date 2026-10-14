# gov_frame_v8 · 数据结构

运行：`python3 cast.py`（约 60 s；依赖 numpy、scipy；按路径载入 `../city_system_v7_streets/city_system.py`，未改动）。
产出：`results.json`、`graph_AF{40,50,60,70}.json.gz`。

## 输入
| 来源 | 用到的 |
|---|---|
| world.json（v7 经 v6 读入） | 房屋 id、d、built、destroyed；设施结构 |
| v7 `build(40)` + 逐年 `events_for_year`/`apply` + `materialize` | 每户记录 d、fang、water、parish、arian、watch、grain、guild、street |
| v7 状态 `st.inter`、`st.hdoor`、`st.sset`、`C.fac` | 只用于关系图：街段交点（路口）、门口所在街段、设施点 |
| persons/、world.json `persons` | 有则按 `address == 房屋 id` 绑定人物；当前仓库两者都没有 → 0 人 |

## offices.json（规则表，不含人）
顶层：`powers`（7 种职权词表）、`selection_modes`（appoint / elect / hereditary / seniority 的选法定义）、`household_head`（人物 id 与户主更替规则）、`proxies`（信仰、居住年数、户主、房主的代理定义）、`offices[]`。

每个 office：
| 字段 | 含义 |
|---|---|
| id, name, order, level | order = 出缺填补顺序；level 0 城市、1 城市级专官/主教、2 区/行会、3 坊/堂区/哨/仓/水 |
| superior | 上级职位 id；null = 上级在城外（皇帝、牧首），见 superior_note |
| scope | city / arian_city / district / guild / fang / parish / arian_parish / watch / grain / water |
| jurisdiction_from | 辖区如何由 v7 结构推出（文字） |
| powers | 职权子集 |
| eligibility | 每条 `{value, scope, status}`；status：`enforced`（直接字段）、`enforced_proxy`（经代理执行）、`no_field`（账本无字段，只登记不执行） |
| selection | 默认产生方式；运行时可整体覆盖 |
| term_years | 任期年数；null = 终身；世袭方式下忽略 |
| vacancy | 出缺与递补规则（文字） |
| basis.reference / basis.assumption | 拜占庭参照 / 模型假设，分开列 |

## procedures.json
`procedures[]`：`{id, name, steps:[{office, power}]}`。每步实例由发起户的辖区解析（城市级全城一个）。

## 填职引擎（cast.py `Caster`）
- 每栋在册房屋 = 一户 = 一位户主；人物 id = `hh_<房屋id>_g<代>`，代 = ⌊(Y − 建成年 + crc32(id) mod 25) / 25⌋。
- 每年：①在任校验（户毁、迁出辖区、辖区消失、不再合格、任满、户主更替[世袭除外，世袭则改为新户主]）→ ②出缺按 (order, 辖区键) 顺序递补：候选 = 辖区内合格且未任他职、且不是本年任满卸任者。
- 从头版（规范）：每年重建辖区成员并校验全部在任者。增量版：只按变动户（户籍记录变化、新建、拆毁、户主换代）更新成员，只校验这些户持有的职位 + 当年任满的职位。逐年比对全部 (职位, 辖区) → (户, 人物, 起始年, 任满年) 与空职清单。

## results.json
| 键 | 内容 |
|---|---|
| rules_check | 静态校验错误（应为空）；自检：去掉区长「批建」后应报出的不可达 |
| persons_from_ledger | 从账本人物绑定的户数 |
| households_by_year | AF40/50/60/70 在册户 |
| default | 默认产生方式（各职 selection）下：空职率、任期、集中度、离任原因、违规计数、流程覆盖、增量验证、逐年空职清单 `empty_by_year[Y] = [{office, key, members, why}]`、`empty_summary_office_mainreason_size` |
| modes.{appoint,elect,hereditary,seniority} | 全部职位强制同一产生方式时的同一组指标 |
| graphs.AFY | 关系图节点/边数、每户平均边数、按类型与来源分的边数、原始与 gzip 字节 |
| roster_AF70_city_level | AF70 城市级职位：[户, 人物 id, 起始年, 任满年] |

指标定义：空职率 = 空职-年 / 职位-年；平均任期（已结束）= 已结束任期的年数均值；含截尾 = 再加 AF70 仍在任者到 AF71 的年数；街道前 5 占比 / HHI = 职位-年按持有户门口街道的分布；户前 10 占比 = 持职-年最多的 10 户所占份额。

## graph_AFY.json.gz（gzip 的 JSON）
```
{"year":Y, "nodes":[[id, 类型, 属性]], "edges":[[源下标, 目标下标, 类型, 细类, 来源]]}
```
- 节点类型：`户`、`职位户`（属性含 person、d、street、faith、office、jurisdiction）、`井/水池`、`教堂`、`粮仓`、`城门`、`城墙段`（设施标签 id，属性 struct、xy）、`路口`（`j:x,y`，当年两街段交点）。
- 边类型 / 细类 / 来源：
  - `隶属`：户 → 本户各辖区职位持有户（细类 = 职位名，规则）；职位户 → 上级职位户（细类 = 本职→上级，规则）
  - `辖区覆盖`：堂区长老/阿里乌长老/哨长/粮仓主管/水役头 → 本辖区设施；坊长 → 本坊各户门口路口（硬件推出）
  - `流程上下游`：五条流程中相邻两步的持有户（细类 = 流程名，规则，去重）
  - `共享设施`：户 → 用水/领粮/守哨设施、礼拜教堂、门口路口（硬件推出；阿里乌户 → 阿里乌教堂为信仰代理，来源 = 假设）。两户共享 = 经同一设施节点相连。
- 自环（职位户隶属自己）不写。
