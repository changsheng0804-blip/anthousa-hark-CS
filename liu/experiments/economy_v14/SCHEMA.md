# economy_v14 · 数据结构

——Hark（刘线）

## 运行
```
python3 economy.py run      # AF40–70 逐年全量；写 flows_AF{40,50,60,70}.json.gz、ledger_reconcile.csv、results.json、sample_household.txt（≈14 s）
python3 economy.py events   # 4 个账本事件：反事实 vs 事件、增量 == 重建、耗时；写入 results.json["events"]（≈8 s，需先 run）
```
依赖 numpy、scipy。只读、按路径载入：
- `../yamen_v13/yamen.py` 与它的 `.cache_incr.pkl`（不入库；缺时先在 yamen_v13 里跑 `python3 yamen.py incr`）：v7 逐年户籍字段、门牌、v8 填职；yamen 再按路径载入 `../city_system_v7_streets`、`../gov_frame_v8/cast.py`。
- `../rules_v4_fiscal/out/fiscal_city.json`：v4 参数、账本工程造价/出资方表、逐年层级账（对账用）。
- `../rules_v0/rules.json`：v2 所用房东（cap 6）、债（cap 4、4 年）参数。
- `docs/living/xerolophos/facts_upstream/houses.json`：第 9 栏（下标 8）= 地块所在街区功能。
- `world.json`：房屋形心、建成/拆毁年、设施（市场、广场、港口、港仓、粮仓、蓄水池、城门、兵营）。

`.cache_states.pkl`（不入库）= run 写出的事件年年初状态，供 events 用。

## 单位
- 粮：份 = 一人一年口粮（与 v4 同）。只出现在三类粮流里。
- 钱：份（折粮），与 v4 同。flows 里 `q` 是千分之一份的整数。

## 实体
- 户：一栋账本房屋一户（v13 户籍）。显示为当年门牌「街名 号号」；本年注销（拆毁）的户显示上年门牌加「（注销）」。
- 官：`官:城市长官@门牌`（v13 中心性代理房屋）、`官:粮政官@最早粮仓门牌`、`官:夜巡长@兵营门牌`、`官:主教(尼西亚)@大教堂门牌`、`官:主教(阿里乌)@阿里乌教堂门牌`、`官:堂区长老|教堂@教堂门牌`、`官:会众长老(阿里乌)|教堂@教堂门牌`。这些是「库」（有余额）。坊长、区长、行会头、粮仓主管、水役头、哨长不设库，钱直接进任职户门牌。
- 仓：`仓:粮仓id@粮仓门牌`（只经手粮）。
- 外：`外:皇库`、`外:皇家粮运`、`外:城外贸易`、`外:城外商人`、`外:迁入`、`外:迁出`（城外源/汇）。

## flows_AF{Y}.json.gz（列式）
```
{year, _doc,
 entities:[显示名…], entity_kind:["户"|"官"|"仓"|"外"…],
 types:[流类型…], rules:[规则来源…],
 flows:{t:[类型下标], a:[付方实体下标], b:[收方实体下标], q:[千分之一份], r:[规则下标]},
 households:{ent, house, livelihood(下标→livelihood_names), lh_src(下标→lh_src_names),
             income_m, expense_m, cash_m, networth_m, houses_owned, debt_m, landlord(实体下标或 -1),
             market(最近市场节点 id), dist_market, dist_grain}}
```
- 行按 (t, a, b) 排序。同一 (t,a,b) 可有多行（例如房东替多户租户交房税）。
- `income` 不含借入、迁入带钱；`expense` 不含还款、放贷、迁出带钱。`networth = 年末现钱 + 30 × 名下房屋数（自住 + 出租）+ 应收债 − 应付债`。
- 距离为账本单位（v4：1 单位 ≈ 12 m）的直线距离。

## 流类型（types）与链路
| 类型 | 付 → 收 | 规则来源 |
|---|---|---|
| 口粮调拨 / 口粮下仓 / 口粮配给 | 外:皇家粮运 → 官:粮政官 → 仓 → 户 | 账本 food_cap；v7 全城均分、配给点 = 最近粮仓（走街） |
| 房税 | 房主户（自住户；租户之房由房东交；无房东的租户自交）→ 坊长户（坊长空缺 → 区长户 → 城市长官） | v4 tau=0.5/栋 |
| 人头税 | 户 → 同上 | 新假设 0.2/户 |
| 税钱上缴(坊长→区长) | 坊长户 → 本坊多数户所在区的区长户（区长空缺 → 城市长官） | v4 alpha=10% 截留 |
| 税钱上缴(区长→城市长官) | 区长户 → 官:城市长官 | v4 beta=10% 截留 |
| 行会钱 / 行会钱上缴 | 行会户 → 区×行会 行会头户 → 城市长官 | v4 delta=0.3、gamma=10% |
| 上交皇库 | 城市长官 → 外:皇库 | v4 remit=50%（城市长官当年收到的税钱） |
| 奉献 / 奉献截留 / 奉献上缴 | 户 → 本堂区（或阿里乌会众）长老库 → 长老户 5% / 主教库 95% | v4 omega=0.3、eps=5% |
| 施舍 | 主教库 → 本派上年收入 < 贫困线的户 | v4 alms=1.0（预算 = 当年奉献 60% + 库存 50%，不足按比例） |
| 租金 | 租户 → 房东户 | v4 rho=1.0；v2 房东规则 |
| 买卖:面包 / 手工 / 港货 | 户 → 最近市场节点上该货卖方（本节点无此货 → 最近有此货的节点），按户编号散列固定一家（常客） | 户需求表 × 市场价（新假设） |
| 买卖:水 | 户 → 本供水组（v7 water）运水人（组里没有 → 本区） | 同上 |
| 进货/原料(付城外) | 卖方 → 外:城外贸易 | 面包 20%、手工 30%、港货 50% 营收（新假设） |
| 出口(城外付) / 宫廷采购(皇库付) | 外 → 作坊 / 港货商 / 营造 / 铺户 | 新假设定额 |
| 工钱 | 雇主户 → 雇工户 | 上年营收 50% ÷ 3.0 = 工位；同街同行优先 → 同街 → 同区同行 → 同区，门牌序 |
| 公役工钱 | 官:城市长官 → 无主雇工 | 库存超 20,000 部分的一半；按区无主人数分额，区内门牌序 |
| 俸给 | 外:皇库 → 城市长官/粮政官/水政官/夜巡长户；城市长官 → 粮仓主管/水役头/哨长户；主教库 → 主教户 | 新假设 |
| 兵饷 | 外:皇库 + 城市长官 → 官:夜巡长 → 兵户 | v4 sigma=1.0 + 新假设 |
| 借贷 / 还款 | 同区有房面包户/体面户 → 年末现钱 < 0 的户；4 年等额还 | v2 债规则（cap 4、4 年、无息） |
| 拆迁补偿 / 搬迁费 | 城市长官 → 房主（租户之房给房东）/ 被拆租户 | v4 comp=0.5×V_h=15、reloc=1.0 |
| 建设:新房 | 房东 → 同区最近营造户 | 新假设 10/栋 |
| 建设:公共工程 | 出资方（v4 WORK_PAYER）→ 离工地最近 20 户营造户 | v4 账本工程造价 |
| 修水摊派 | 新池供水组各户 → 城市长官 | v4 levy=1.0 |
| 迁入带钱 / 迁出带钱 | 外:迁入 → 新户；拆毁户年末现钱 → 外:迁出 | 假设 |

## ledger_reconcile.csv（每年一行，AF40–70）
`ledger_houses`（world.json 当年在立房屋）/`model_households`/`houses_ok`；`food_cap`/`grain_to_households`/`grain_ok`/`v4_grain_income`；
`house_tax_model`/`house_tax_rule`(= tau × 账本房屋)/`house_tax_ok`/`tenants_without_landlord`/`v4_house_tax`/`v4_houses`；
`money_stock`（户 + 各库现钱）/`dM`/`ext_in`/`ext_out`/`bad_debt_with_departing`（随户注销的负现钱）/`conservation_err` = |dM − (ext_in − ext_out) + bad_debt|；`max_type_err`（每类付总额 − 收总额）。

## results.json
`params`、`livelihood`（生计户数、来源、功能）、`years[Y]`（贫困、Gini、借贷、就业、各库、每类流总额）、`conservation`、`per_type_AF70`、`timing`、`files`、`sample`、`events[名]`（硬件变化、脏集、受影响户、收入/支出/距离/价格变化、每类流 事件−反事实、`incremental_equals_rebuild`、耗时）。
