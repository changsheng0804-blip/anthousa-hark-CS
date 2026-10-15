# yamen_v13 · 数据结构

运行（分段，每段 < 2 分钟）：
```
python3 yamen.py incr      # v7 逐年增量 + 门牌增量 + v8 填职 + 户籍增量（≈21 s，写 .cache_incr.pkl，不入库）
python3 yamen.py rebuild   # v7 逐年从头建 + 门牌按街批量重放 + 户籍从头生成，逐年比对（≈25 s，写 .part_rebuild.json）
python3 yamen.py emit      # 写下列产出（≈8 s）
```
依赖 numpy、scipy；按路径载入 `../city_system_v7_streets/city_system.py`、`../gov_frame_v8/cast.py`（含其 offices.json、procedures.json），均未改动。
v8 核对读 `../gov_frame_v8/graph_AF{40,50,60,70}.json.gz`。上游事实读 `docs/living/xerolophos/facts_upstream/{streetnames,addr}.json`；3,168 复现读 `git show 04c3bec^:…/addr.json`。

## 门牌
- 实体：房屋（id `hNNN`）、v7 设施门（`f:<设施标签>`：教堂、蓄水池、粮仓、城门、城墙段）、兵营（`s:barracks_gate`）。设施与兵营占门牌，但辖区门牌段只按户计。
- 街键 K：账本道路 = 道路 id（`r_mese`）；上游街 = `u:<上游街名 n>`，同名各段共用一条门牌序列。
- 街名：上游街取 streetnames.json `r`（按年改名）；账本道路无中文街名，用 `路·<id 去掉 r_>` 作稳定名（假设）。
- 门口：v7 `st.hdoor`（房屋）/ `st.doors`（设施）/ 自算最近站着街段垂足（兵营）。沿街位置 = 本街起点起的折线累计长度（上游街按整条上游折线经仿射后累计）。
- 单双：沿街方向，账本坐标叉积 < 0 一侧为单号（`ODD_LEFT=False`，与 tools/facts_from_upstream.py 同式；仿射行列式 > 0，方向不翻）。
- 编号（每年：先注销/迁出，再按「有上游号者先、街、侧、位置、id」逐个编号）：
  1. 本户在上游 addr.json 当年就在这条街、上游号单双与本侧相符、且该号没发给过别的实体 → 用上游号；
  2. 本侧没有在册者或位置在本侧最后一户之后 → 新号 = max(本侧发过的整数号, 上游本侧最大号) + 2；
  3. 有前一户 → 前一户基号 + 大写附号（`12A`、`12B`…`12Z`、`12AA`…），附号按基号顺序发放、永不复用；
  4. 在本侧首户之前 → 首户基号 + 小写附号（`5a` = 位于 5 号之前）。
  已发的号注销后不复用，不重排。门口在同一街同一侧内挪动不改号。
- 本侧门牌序 `num_key`：基号，小写附号 < 无附号 < 大写附号，附号按长度再按字母。

## registry_AF{40,50,60,70}.json.gz
```
{"year":Y, "fields":[…], "ration_per_household":口粮, "rows":{"<当年街名> <号>号": [
  房屋id, 户主人物id(hh_<房屋>_g<代>，v8 规则), 坊, 区, 教区(尼西亚堂区或阿里乌会众标签), 信仰代理(nicene/arian),
  供水组, 配给点(粮仓标签), 哨, 行会(区×街区功能，无则 null), 所任职位("职位id|辖区键" 或 null), 门口街段id(v7)]}}
```
口粮在 v7 是全城均分值，放表头。

## addr_history.json.gz
`rows[] = [年, 实体id, 类型, 旧门牌, 新门牌, 原因/编号方式, 当时坊长户, 当时区长户]`
- 类型：新编（编号方式：上游门牌/新号/插号/插号(街头前)）、改址（新街开通/道路拆除/换侧/门口改街）、改名（`旧名→新名`，号不变）、注销（拆毁/设施撤除/无街可归）。
- 旧门牌按上一年街名显示；坊长/区长户 = 事件年该户所在坊、区的在任者（注销者按上一年户籍）。

## offices_seated.json
`years["AF{Y}"][] = {office, name, jurisdiction, holder_house, holder_person, holder_address, seat_entity, seat_address, seat_basis, members, members_without_address, ranges_decode_ok, range_count, ranges[]}`
- 衙署：城市长官 = 中心性代理（AF40 全城街网路口调和中心性最高者旁最近房屋，户毁才重选）；粮政官 = 最早在立粮仓；水政官 = 最早在立蓄水池；夜巡长 = 兵营；主教 = 面积最大的在立尼西亚 / 阿里乌教堂；堂区长老、会众长老、水役头、粮仓主管、哨长 = 本辖区设施本身；区长、坊长、行会头 = 任职户门牌（空缺则无衙署）。
- 辖区门牌段：`"<街名> a–b、c 号单"`；区间 = 本侧在册户门牌按门牌序连续的一段（含首尾）。`ranges_decode_ok` = 把区间解回门牌集合后与 v8 辖区成员完全相同。城市级职位写「全城」。

## 路由（yamen.py `build_index` / `route`）
每年预建 `门牌 → (户籍行, 七条线, 全部 14 类职位归属)`、`(职位, 辖区) → (任职户, 人物, 衙署门牌)`；查询 = 字典查找。
七条线：民政（坊长→区长→城市长官）、教会尼西亚（堂区长老→主教）、教会阿里乌（会众长老→主教）、粮（粮仓主管→粮政官→城市长官）、水（水役头→水政官→城市长官）、哨（哨长→夜巡长→城市长官）、行会（行会头→城市长官）。
流程：procedures.json 五条，每步按发起户辖区解出职位实例 → 衙署门牌。
归属口径与 v8 相同：每类职位按 `cast.jkey(scope, 户籍)` 取实例（主教（尼西亚）scope=city，阿里乌户也在其下）。

## results.json
| 键 | 内容 |
|---|---|
| params | 单双约定、仿射行列式、附号说明、账本街名规则 |
| addresses | 每年实体/户数、无门牌户、有门牌的街数、附号户数、AF41–70 事件按类型与原因、编号方式、改名年表、与上游 addr.json 一致率 |
| upstream_3168 | 3,168 复现及与本模型的比较 |
| addr_history | 行数、gzip 字节 |
| registry | 每年行数、JSON / gzip 字节、每户字节、门牌键唯一 |
| offices_seated | 每年实例数、空缺、衙署依据分布、区间解码校验、区间段数 |
| routing | 每年索引构建耗时、单次查询平均微秒、1,000 户与 v8 关系图核对 |
| rebuild | AF40–70 增量 == 重建（门口表、v7 记录、门牌、事件、户籍）、从头建耗时、合成 AF71 拆路+改名 |
| incremental | 各步每年耗时（中位/p90/最大/合计）、户籍每年改动行数 |
| eparch_seat | 城市长官中心性代理的路口与房屋 |
| samples_text | 3 个 AF70 门牌的完整查询（同 samples_AF70.txt） |
