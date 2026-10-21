# city_system v7（街道网络版）· 数据结构

运行：`python3 city_system.py incr | rt_street | rt_fac | compare | junctions`，各段写 `.part_*.json`；
`python3 city_system.py assemble` 合并进 `results.json`（每段 ≤2 分钟，分段跑）。
依赖：numpy、scipy；复用 `../city_system_v6/city_system.py`（按文件路径载入，未改动）。

## 输入
| 文件 | 用到的字段 |
|---|---|
| world.json `houses` | id、d、p（质心=顶点均值）、built、destroyed |
| world.json `structures` | road（折线，built/destroyed）→ 街；cistern/church/granary/gate/wall → 设施（与 v6 同一套标签） |
| facts_upstream/houses.json | 第 0 栏 id、第 4 栏地块多边形 → 与账本房屋按 id 配对，拟合上游→账本仿射；第 9 栏街区功能 → 行会（沿用 v6） |
| facts_upstream/streetnames.json | `n` 街名、`p` 折线（上游坐标）、`y` 开街年 → 仿射到账本坐标，只留上游房屋凸包（外扩 2%）内的段 |
| facts_upstream/junctions.json | 只做核对（见 results.json `junctions`），不进图 |
| addr / junctions_named / blocks / landmarks | 看过格式；本版未用（街名改名只影响名字，不影响拓扑；街区功能已由 v6 行会接入） |

## 街道图（逐年）
- 街 = 账本 road 一条，或上游街名在覆盖范围内的一段连续折线（`u:街名#k`）。当年站着：`built ≤ Y < destroyed`（上游街无拆毁年）。
- 节点 = 坐标量化到 0.01 单位的点 `(round(x·100), round(y·100))`：折线顶点、两街段交点、端点吸附点、设施门口。
- 边 = 同一街段上相邻两节点，权 = 两节点量化坐标的欧氏距离；另加吸附边：街端点到最近「别的街」垂足距离 ∈ (0, 6] 时连一段。
- 平面面 = 半边遍历（每个节点按方位角排序邻居，下一条半边取顺时针下一个邻居）。

## 归属
- 房屋门口 = 最近站着街段上的垂足（同距按街段号）；门口垂距 `acc`。
- 设施门口 = 设施点（城墙：v6 每 50 单位一段内的采样点取最近者）到最近站着街段的垂足；该点进图为节点，种子距离 = 垂距。
- 每类设施（water / parish / church_all / watch / grain）一次多源 Dijkstra，节点键 = (距离, 设施标签号) 字典序最小。
- 房屋键 = min over 门口两侧节点 x 的 ((dist[x] + |门口−x|) + acc, lab[x])。
- 节点职务、一户一职、口粮：与 v6 相同（区长 > 坊长 > 长老 > 阿里乌长老 > 水役头 > 哨长 > 行会头；年资 = 最早建成，同年按 id）。

## 坊
- 面 → 临街长度 < 20 的面并入共边最长的邻面（并查集）→ 每组按半边序列切成 ≤100 单位临街长度的段（长街段本身按 ≤100 切小段）。
- 房屋的坊 = 其门口所在半边（街段 A→B 方向，房在左取 a→b，在右取 b→a）上那一小段的名字；
  离街垂距每 20 单位另起一层（`|深n`）；垂足落在街段端点的人家按方位 4 扇区分（`|角n`）。
- 坊名 `坊@x1,y1>x2,y2.j[|深n][|角n]`：组内该段最小半边的两端坐标 + 小段号——只由当年街网几何决定，不看房屋，因此新房 O(1) 落坊、不会用到未来房屋。

## 增量事件 `apply(st, ev)`
| 事件 | 做法 |
|---|---|
| `("build",[h])` | 查静态 topK 取最近站着街段（O(K)）→ 二分找门口两侧节点 → 读各类节点键 → 半边查坊 → 入节点、结算一户一职 |
| `("destroy",[h..])` | 出节点、结算 |
| `("street_add"/"street_remove", i)` | 只改该街段及与之相交/吸附街段的分割点与边；设施门口与端点吸附按同一规则重算（数百个点）；每类设施做动态最短路：删边/删源 → 重置其最短路子树，再从边界做递减松弛；只重描邻接变了的节点上的面并重算受影响的合并组；只重评门口街段/节点标签变了的房屋 |
| `("struct_add"/"struct_remove", k)` | 设施：同上（加源/删源）；非设施结构只记入 sset |

## materialize → (records, nodes)
records：`hid → (d, fang, water, parish, arian, watch, grain, ration, guild, street, dist_water, dist_parish, dist_grain, dist_watch)`
（street = 门口所在街 id；dist_* = 步行距离，账本单位，按需由门口与节点键算出，不常驻）。
nodes：`"标签:节点" → (职名, 担任户 id 或 None, 成员户数)`。

## results.json
| 键 | 内容 |
|---|---|
| params | 全部模型阈值 |
| compare.affine_upstream_to_ledger / upstream_clip | 仿射残差、上游街段保留数 |
| compare.vs_v6.{41,55,70} | 与 v6 直线版对比：改归属户数与比例（分字段、去掉哨）、差异最大的 3 个坊、门口来源（账本/上游）、门口垂距、图规模、坊规模、一户一职、只用账本道路时的门口垂距 |
| compare.perf | prepare、全城生成耗时、内存、每户字节 |
| incr | AF41–70 逐年增量==重建、各事件耗时（中位/p90/最慢）、每个拓扑事件的耗时与改归属户数、逐年对账 |
| rt_street / rt_fac | AF70 合成往返（拆→比对不含它的重建，建回→比对原年重建） |
| junctions | 上游路口点离街网节点的距离（核对仿射与图） |
