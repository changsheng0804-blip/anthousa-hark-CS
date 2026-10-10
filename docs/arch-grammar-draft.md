# 安托萨建筑语法设计草案 v0.2

- 状态：草案 PR，待评审讨论，讨论通过后合并
- 日期：2026-10-10（v0.2 修订）
- 对应仓库：tanxinhao2026-netizen/anthousa
- 目标读者：项目规划者与实现 agent
- 起草：Muse（2026-10-10）

> 本文档是设计草案，不是实现。评审重点见 §16。讨论请直接在 PR review comments 里进行。

## 修订记录

- **v0.2（2026-10-10）**：回应 Hark 在 PR #1 的审阅意见：
  1. 纪年改用 AF（建城纪年），与引擎一致（§4 重写）；
  2. 补 `type → motif` 映射表（用 `world.py` 的真实类型集合），状态机写明与 `built`/`destroyed` 字段的对应（§3.1、§7.1）；
  3. 实施计划按 CONTRIBUTING 的 B/C 分类拆 PR，Step 4 回填明确为 C 类、需所有者批准（§15 重写）；
  4. 声望只影响提案权重与提示词，**不得进入裁决**（§6 重写）；
  5. `relates_to` / `memorial` 结构检查替代关键词与字数检查（§9、§11）；
  6. 母题 13→14（新增 `column_monument` 覆盖现有 `column` 类型），§16 六个问题按审阅答复记为已决议。

## 1. 目标与非目标

**目标**

1. 让建筑"长"出年代感和派系感：同一座城市，不同时代、不同派系建的东西，在地图上一眼可辨。
2. 给 AI 提案加一层"审美约束"：不是限制创意，而是让创意有风格、有谱系。
3. 所有变更 additive（只增不改），不破坏现有 `engine/`、`check.py`、`render.py` 流程；旧数据无新字段时渲染结果不变。

**非目标**

- 不重写地形、经济、人口系统。
- 不引入 3D；渲染仍是 2D 地图 + 时间轴查看器。
- 本草案不管施工顺序模拟（planned → construction 的多年跨度留给后续）。

## 2. 核心模型：建筑 DNA

每个 `structure` 新增一个 `dna` 四元组：

```
dna = motif（母题） × materials（材料） × ornament（装饰等级 0–3） × scale（尺度）
```

- **motif**：决定平面几何的生成方式（如"十字穹顶"必为十字平面+中央穹顶）。
- **materials**：决定质感与渲染颜色，取自受控词表。
- **ornament**：0=毛坯实用，1=简单线脚，2=雕刻+彩绘，3=金底马赛克级。
- **scale**：`domestic`（民居）/ `civic`（公共）/ `monumental`（纪念性）/ `wonder`（奇观）。

DNA 是"给"不是"选"：AI 提案时声明，规则引擎校验，渲染时执行。

## 3. 母题库 v1

母题是受控词表，存在 `rules/motifs.json`。v1 共 14 个：

| 母题 id | 中文 | 几何生成规则 | 典型尺度 | 派系亲和 | 年代权重注记 |
|---|---|---|---|---|---|
| courtyard_house | 庭院住宅 | 矩形+内庭，临街开面 | domestic | people, merchants | 全年代 |
| insula | 集合住宅 | 多层矩形，临街连续界面 | domestic | merchants, people | 城市化后权重上升 |
| basilica | 巴西利卡 | 长方形，长宽比 2:1–3:1，中厅高、侧廊低 | civic | emperor, church | 早期公共建筑主力 |
| domed_basilica | 穹顶巴西利卡 | 长方形+中央大穹顶 | wonder | emperor, church | constantinian 后开放 |
| cross_in_square | 十字穹顶教堂 | 十字平面+中央穹顶+四角小穹顶 | monumental | church | justinianic 后权重最高 |
| rotunda | 圆形厅 | 正圆/八角形平面 | civic/monumental | emperor | 全年代，纪念性场景 |
| peristyle | 柱廊 | 列柱围合的开放空间 | civic | emperor, merchants | 广场、市场周边 |
| tower | 塔楼 | 方形高层 footprint | civic | army | 城防、灯塔 |
| gatehouse | 城门楼 | 墙体开口+双塔 | monumental | army, emperor | 城墙扩展期 |
| column_monument | 纪念柱 | 独立柱式+柱头雕像，方形底座 | civic/monumental | emperor | v0.2 新增，覆盖现有 `column` 类型 |
| cistern | 蓄水池 | 地下矩形+柱列（地面只渲染图标） | civic | emperor | 人口超 10 万后刚需 |
| hippodrome | 竞技场 | U 形长条 | monumental | emperor, people | 仅限 1 座，重建需大事件 |
| market_row | 市场廊 | 连续拱廊临街 | civic | merchants | 商业区 |
| monastery | 修道院群 | 围合院落+小教堂 | civic | church | 中期后权重上升 |

几何参数（如长宽比、穹顶直径占比）写入 `motifs.json`，供 `render.py` 与将来的 3D 化使用。

**异域母题条款**：允许 `motifs.json` 中 `origin: "exotic"` 的母题（如波斯式穹顶、拉丁巴西利卡），权重上限为本地母题的 20%，且提案必须在 `why` 中说明来源事件（贸易/战俘/联姻/使团）。外来风格是故事的种子，不是常态。

### 3.1 type → motif 映射表（以 `engine/world.py` 的真实类型集合为准）

| type（现有） | 所属集合 | 允许的 motif | 说明 |
|---|---|---|---|
| palace | BUILDING_TYPES | peristyle, basilica, rotunda | 宫殿建筑群 |
| forum | BUILDING_TYPES | peristyle, basilica | |
| church | BUILDING_TYPES | basilica, cross_in_square, domed_basilica, rotunda | |
| market | BUILDING_TYPES | market_row, peristyle, basilica | |
| fort | BUILDING_TYPES | tower | 要塞主体 |
| granary | BUILDING_TYPES | basilica | 长条仓储厅 |
| cistern | BUILDING_TYPES | cistern | |
| temple | BUILDING_TYPES | peristyle, rotunda, basilica | |
| hippodrome | BUILDING_TYPES | hippodrome | |
| baths | BUILDING_TYPES | basilica, rotunda, peristyle | 浴场建筑群 |
| monument | BUILDING_TYPES | column_monument, rotunda | |
| column | BUILDING_TYPES | column_monument | |
| monastery | BUILDING_TYPES | monastery, cross_in_square | |
| barracks | BUILDING_TYPES | insula | v1 暂用集合住宅母题，v2 可拆分 |
| warehouse | BUILDING_TYPES | basilica, insula | |
| ruin_marker | BUILDING_TYPES | —（豁免） | 标记非建筑 |
| gate | BUILDING_TYPES | gatehouse | |
| aqueduct_bridge | BUILDING_TYPES | —（豁免） | v2 可增补桥涵母题 |
| road, wall, aqueduct, seawall | LINE_TYPES | —（豁免） | 线型基础设施无母题 |
| harbor | WATER_TYPES | —（豁免） | 水工建筑 v2 增补 |
| district | AREA_TYPES | —（豁免） | 区域非建筑 |

豁免的类型不需要 `dna.motif`；`check.py` 对其跳过母题校验。

## 4. 年代风格层 style_era（AF 纪年，含风格漂移）

引擎使用 AF（建城纪年，AF 1 ≈ 公元 330 年）。换算：AF N ≈ 公元 330+(N−1) 年（N 为正）。`style_era` 一律用 AF 定义，`drift_style()` 以 AF 年为输入。

`style_era` 存在 `rules/style_eras.json`：

| era id | AF 范围 | 公元对照 | 材料调色板 | ornament 上限 | 尺度上限 | 备注 |
|---|---|---|---|---|---|---|
| archaic | AF -986 – AF -660 | 前657–前330 | 毛石 rubble | 1 | monumental | 希腊殖民城 |
| hellenistic | AF -659 – AF -134 | 前330–195 | 方石 ashlar、灰泥 | 2 | monumental | 含罗马共和晚期 |
| severan | AF -133 – AF -6 | 196–324 | 砖石混合 | 2 | monumental | |
| constantinian | AF -5 – AF 65 | 324–394 | 大理石贴面初现 | 3 | wonder | wonder 尺度开放 |
| theodosian | AF 66 – AF 197 | 395–526 | 砖石+马赛克 | 3 | wonder | |
| justinianic | AF 198 – AF 235 | 527–564 | 金底马赛克、大穹顶 | 3 | wonder | wonder 提案加权 |
| middle | AF 236 – | 565– | 砖石混砌 | 2 | monumental | "节俭的辉煌" |

`style_era` 由建筑的建造年代（AF）自动推导（可覆写，需理由）。渲染色板按 `style_era × materials` 查表。

**风格漂移（style drift）**：年代之间不是硬切换。`style_eras.json` 增加 `transition` 规则：材料、穹顶技术、装饰密度三个参数随 AF 年代、灾变次数、国库水平缓慢漂移（如连续两次大火后木构权重下降、砖石上升）。漂移由 `grammar.py: drift_style(world, af_year)` 计算，提案与渲染都读漂移后的参数——换代不用人工干预。

## 5. 派系美学方言

每个派系一个偏好向量（写入 `rules/faction_styles.json`，软约束，权重制）：

- **emperor（皇帝）**：对称、轴线；偏好 domed_basilica、hippodrome、gatehouse、rotunda、column_monument；材料偏大理石；ornament 倾向 3。
- **church（教会）**：垂直性、向天；偏好 cross_in_square、domed_basilica、monastery；金底马赛克；ornament 倾向 3。
- **merchants（商人）**：实用、临街、密集；偏好 market_row、insula、peristyle；砖石；ornament ≤1。
- **people（平民）**：courtyard_house；材料本地化；ornament 倾向 0–1；偶发捐建小教堂（声望动机）。
- **army（军队）**：tower、barracks（母题库 v2 增补）、城墙；功能优先；ornament 倾向 0。

提案 prompt 要求：每个 `build` 必须声明 `motif` + `faction`；材料默认按"派系×年代"推导，覆写需在 `why` 中说明。

**混血规则**：当两个派系合建（如皇帝出资、教会主持），dna 取双方偏好的加权混合，并在 `biography` 中注明。这是"风格杂交"的故事来源。

## 6. 声望经济（只影响提案，不进入裁决）

每个派系维护一个 `prestige`（声望）账本，存在世界状态中：

- 建筑落成时，按 `scale`/`wonder` 给建造派系加声望（wonder 级 +5，monumental +2）。
- 声望每年衰减 10%；wonder 建筑带来的声望衰减减半——奇观是不朽的。
- 影响面**仅限提案侧**：
  1. 声望落后的派系，其下个十年的提案 prompt 注入"野心加成"（鼓励 monumental+ 提案）；
  2. 教会与皇帝声望差超过阈值时，注入"辉煌竞赛"事件倾向；
  3. `motif_for()` 的抽取权重向高声望派系的偏好倾斜。
- **红线**：声望不得作为 `rules.py` / `check.py` 任何 reject / warning 的输入。规则引擎是这个项目唯一不受叙事影响的部分，激励可以塑造提案，不能松动裁决。

效果：宏伟不再是被安排的剧本，而是五个账本在激励下"不得不"卷出来的结果——但卷的方式必须过得了代码法官这一关。

## 7. 建筑传记：引擎状态机 × 叙事八阶段

**引擎状态机**（`step.py` ops，直接影响世界状态）：

`planned → construction → standing → damaged → ruin → {restored → standing, rebuilt → standing, quarried → gone}`

| op | 含义 | 状态变迁 |
|---|---|---|
| build | 新建 | → construction（v1 可简化为直接 standing） |
| damage | 灾难/战争损毁 | standing → damaged |
| demolish | 拆除 | standing/damaged → gone（材料不回收，geom 不保留） |
| quarry | 拆料 | ruin → gone，产出 spolia 库存 |
| restore | 修复 | ruin/damaged → standing |
| rebuild | 原址重建 | ruin → standing（保留 id，`biography` 追加） |

`demolish` / `quarry` wonder ≥ 3 的建筑：必须在同一提案中声明 `memorial: {kind, note}`（kind 三选一：`stele` 立碑 / `rename` 改名纪念 / `chronicle_feature` 编年史特写），缺失 → reject。拆奇观是大事，要有交代——用结构字段，不用字数检查。

### 7.1 与现有 `built` / `destroyed` 字段的对应（additive，不改 `standing()` 语义）

| 新状态 `state` | `built` | `destroyed` | `standing(w, year)` | 备注 |
|---|---|---|---|---|
| planned | null | null | 否 | 仅提案阶段 |
| construction | 完工年代（AF） | null | 否（`built > year`） | v1 可跳过 |
| standing | ≤ year | null | 是 | |
| damaged | ≤ year | null | 是（+ `state` 标记） | 灾难事件，仍在地图上 |
| ruin | ≤ year | = 损毁年代（AF） | 否 | `geom` 保留，进入废墟层 |
| restored / rebuilt | 原 `built` | null（清除） | 是 | `biography` 追加 |
| demolished / quarried | ≤ year | = 拆除年代（AF） | 否 | `geom` 不保留；quarry 产出 spolia 库存 |

只新增 `state`、`biography` 两个可选字段；`built`/`destroyed` 的现有语义、`check.py` 与 `standing()` 的行为完全不变。

**叙事八阶段**（chronicle 层标签，不影响引擎，只影响故事写法）：

`proposed（倡议） → rising（兴建） → glory（鼎盛） → worn（斑驳） → wounded（创伤） → transformed（转身） → ruin（废墟） → myth（传说）`

- 每个 structure 的 `biography[]` 记录引擎事件；叙事阶段由实现 agent 在写编年史时根据 `biography` + AF 年代推导。
- 进入 `myth` 阶段的建筑：编年史允许失真重述（见传说机制），`{{id}}` 引用仍须指向真实 id。

## 8. 废墟层与 spolia（旧料新用）

- 废墟层是独立渲染层：灰色虚线 footprint + 年代标注。城市从此有了"地层"。
- 新建筑可声明 `spolia_from: [ids]`，表示使用了哪些废墟的旧料。
- `check.py` 验证：`spolia_from` 引用的 id 必须存在且 `state` 为 `ruin`/`quarried`。
- 叙事红利示例：编年史写"新教堂的十二根柱子取自老竞技场的看台"——零成本的真故事，拜占庭人真这么干。

## 9. 地形神圣度 sacred（可流动、可残留）

- `terrain.py` 标注 sacred 点：七丘顶点、岬角尖端、金角湾内凹处，`sacred: 0–3`。
- 规则：`sacred ≥ 2` 地块上的 civic 以上建筑，`wonder` 评分 +1；若该点已有 wonder，新 monumental+ 提案必须在数据中声明 `relates_to: [ids]`，指向真实存在的 standing 建筑 id（`check.py` 验证存在性），缺失或指向不存在 → reject。
- **流动**：重大事件（神迹、奠基、大屠杀）可提升地块 sacred；**残留**：建筑废弃后 sacred 缓慢衰减，但永不归零——"圣地不会彻底消失，只会沉睡"。
- 效果：纪念碑被"钉"在地形上，城市有了不可移动的仪式锚点。

## 10. 数据模型变更（additive）

`structure` 新增可选字段（JSON Schema diff）：

```json
{
  "dna": {
    "motif": "cross_in_square",
    "materials": ["brick", "marble_revetted"],
    "ornament": 2,
    "scale": "monumental"
  },
  "style_era": "justinianic",
  "faction": "church",
  "state": "standing",
  "biography": [
    {"era": "era_0011", "event": "built", "note": "牧首主持奠基"}
  ],
  "spolia_from": ["hippodrome_old"],
  "relates_to": ["forum_founder"],
  "sacred": 2,
  "wonder": 3
}
```

- 旧数据无 `dna` 字段时视为 `vernacular`（乡土/未分类），`render.py` 用中性样式，保证向后兼容。
- `wonder` 为 0–5 评分，由规则引擎按 scale/materials/ornament/sacred 自动计算，提案不可自填。
- `relates_to` 仅在 sacred ≥ 2 地块的 monumental+ 新建筑上强制要求。

## 11. 规则引擎新增检查（含无聊检测）

`rules.py` / `check.py` 新增（reject = 驳回，warning = 警告后允许修订）：

1. `build` 必须声明 `motif` 且在母题库中；`type → motif` 须符合 §3.1 映射表（豁免类型跳过）；否则 reject（附可选母题列表）。
2. `materials` 必须在该 `style_era` 调色板内；否则 warning（给 AI 在 dry-run 两轮修订内纠错的机会）。
3. `spolia_from` 引用的 id 必须存在且状态为 `ruin`/`quarried`；否则 reject。
4. `scale=wonder` 的建筑：footprint 面积 ≤ `calibration.json` 新增 `wonder_max_area`；同一 era 内处于 construction 的 wonder ≤ 1（防奇观通胀）。
5. `sacred ≥ 2` 地块上的 monumental+ 新建筑：必须声明 `relates_to` 且指向真实存在的 standing 建筑；否则 reject。
6. `demolish` / `quarry` wonder ≥ 3 的建筑：必须声明 `memorial`（§7）；否则 reject。
7. **无聊检测**（防闷不防错）：同一派系连续 3 个十年提案母题重复 → warning，建议换母题或加"处置旧建筑"项；全城近 5 个十年 ornament 分布熵低于阈值 → warning，提示注入变化。
8. 本草案引入的所有新数值（wonder 加分、声望衰减率、阈值、`wonder_max_area`、熵阈值）必须写入 `rules/calibration.json`，`basis` 标 `estimate` 并写理由（CONTRIBUTING 硬规则 #6）。

## 12. grammar.py 接口（engine 新增模块）

```python
# engine/grammar.py
def motif_for(faction, style_era, rng, prestige=None) -> str
    """按派系偏好 × 年代权重 × 声望倾斜抽取母题。prestige 只影响权重，不影响合法性。"""

def materials_for(motif, faction, style_era) -> list[str]
    """推导默认材料，可被提案覆写（需理由）。"""

def validate_dna(structure) -> tuple[bool, list[str]]
    """校验 dna 合法性（含 §3.1 映射表）；返回 (是否通过, warnings/errors)。"""

def wonder_score(structure, world) -> int
    """0–5 自动评分：scale/materials/ornament/sacred 加权。"""

def drift_style(world, af_year) -> dict
    """计算风格漂移后的参数（材料/穹顶技术/装饰密度），输入为 AF 年。"""
```

`step.py` 在 dry-run 与正式推进时调用 `validate_dna`；`render.py` 调用 `drift_style` 取色。

## 13. 渲染映射（render.py）

- 色板：`rules/styles.json`，按 `style_era × materials` 查 RGB（漂移后参数）。
- 图标：`motif → SVG glyph`（穹顶=圆+十字，塔楼=方形齿状，蓄水池=水波纹……）。
- 状态样式：construction=橙色斜线填充，damaged=红色裂纹标记，ruin=灰色虚线，wonder=金色描边。
- `docs/index.html`：图例增加"年代 / 派系"筛选器（复用现有 i18n 机制）。

## 14. 提案 prompt 与 HEARTBEAT 增补

- 提案 JSON 的 `structure` 增加 `dna` 字段要求；`proposals/make_eras_*.py` 模板同步更新；sacred 地块的新 monumental+ 提案模板增加 `relates_to` 字段。
- HEARTBEAT runbook 增补两条：
  - **每个十年至少包含一项"对既有建筑的处置"**（修缮/扩建/改建/拆除），培养城市的地层感。
  - 声望落后派系的提案 prompt 自动注入"野心加成"（仅提示词，不影响裁决）。
- 验收：`check.py` 新增 `dna_consistency` 检查；编年史 `{{id}}` 引用规则不变。

## 15. 分步实施计划（按 CONTRIBUTING 分类拆 PR）

本 PR（草案 PR）只合文档，不碰代码。实现按以下顺序拆 PR，每步验收含 `python engine/build_all.py` 从零重建通过 `engine/check.py`（CONTRIBUTING 硬规则 #1）：

- **PR-B1（B 类）**：数据模型（`dna`/`state`/`biography`/`relates_to` 可选字段）+ `rules/motifs.json` + `rules/style_eras.json`（AF 纪年+漂移规则）+ `rules/faction_styles.json` + `engine/grammar.py` 骨架 + `render.py` 风格化（色板/图标/废墟层/状态样式）。只加字段和渲染，旧数据像素级不变。验收：旧数据渲染不变；CI 通过；截图对比。
- **PR-C1（C 类）**：母题校验（§3.1 映射）、spolia 检查、`dna_consistency`、`relates_to` 检查。验收：`step.py --dry-run` 正确驳回非法提案（含测试用例）；PR 中列出重建后变化的年代（如有）。
- **PR-C2（C 类）**：声望经济，独立评审。所有数值进 `calibration.json` 标 `estimate` 写理由。
- **PR-C3（C 类）**：神圣度流动/残留 + 无聊检测，独立评审。
- **PR-C4（C 类）**：提案 prompt 增补 + HEARTBEAT 增补 + 历史回填（给现有建筑补 `dna`，如 wall_founder、forum_founder）。**需所有者批准**；PR 中列出回填后变化的年代与统计（人口/粮/水/建筑数）。

## 16. 待决策问题（v0.2 已决议，来自 PR #1 审阅）

1. ✅ 年代划分：7 段，改用 AF 纪年（§4），与引擎一致。
2. ✅ 允许异域母题，权重上限为本地母题的 20%，需在 `why` 中说明来源事件。
3. ✅ 同一时期只允许 1 个 wonder 在建；后续用数据说话。
4. ✅ 派系美学先软约束（偏好权重）；跑 20 个十年后再评估是否收紧。
5. ✅ 数值接受"先估计、后校准"；所有数值进 `calibration.json` 标 `estimate` 并写理由。
6. ✅ 母题 13→14（新增 `column_monument` 覆盖现有 `column` 类型）；`type → motif` 映射表见 §3.1。

## 附：术语表（中英对照，供 i18n 扩展）

- 母题 motif / 材料 materials / 装饰等级 ornament / 尺度 scale
- 废墟层 ruin layer / 旧料新用 spolia / 地形神圣度 sacredness / 奇观 wonder
- 建筑传记 building biography / 风格漂移 style drift / 派系方言 faction dialect
- 声望 prestige / 无聊检测 boredom detection / 混血 hybrid / 纪念 memorial
