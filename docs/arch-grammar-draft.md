# 安托萨建筑语法设计草案 v0.1

- 状态：草案 PR，待评审讨论，讨论通过后合并
- 日期：2026-10-10
- 对应仓库：tanxinhao2026-netizen/anthousa
- 目标读者：项目规划者与实现 agent
- 起草：Muse（2026-10-10）

> 本文档是设计草案，不是实现。评审重点见 §15。讨论请直接在 PR review comments 里进行。

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

母题是受控词表，存在 `rules/motifs.json`。v1 共 13 个：

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
| cistern | 蓄水池 | 地下矩形+柱列（地面只渲染图标） | civic | emperor | 人口超 10 万后刚需 |
| hippodrome | 竞技场 | U 形长条 | monumental | emperor, people | 仅限 1 座，重建需大事件 |
| market_row | 市场廊 | 连续拱廊临街 | civic | merchants | 商业区 |
| monastery | 修道院群 | 围合院落+小教堂 | civic | church | 中期后权重上升 |

几何参数（如长宽比、穹顶直径占比）写入 `motifs.json`，供 `render.py` 与将来的 3D 化使用。

## 4. 年代风格层 style_era（含风格漂移）

`style_era` 是时间的美学切片，存在 `rules/style_eras.json`：

| era id | 对应年代 | 材料调色板 | ornament 上限 | 尺度上限 | 备注 |
|---|---|---|---|---|---|
| archaic | 前657–前330 | 毛石 rubble | 1 | monumental | 希腊殖民城 |
| hellenistic | 前330–前196 | 方石 ashlar、灰泥 | 2 | monumental | |
| severan | 196–324 | 砖石混合 | 2 | monumental | |
| constantinian | 324–395 | 大理石贴面初现 | 3 | wonder | wonder 尺度开放 |
| theodosian | 395–527 | 砖石+马赛克 | 3 | wonder | |
| justinianic | 527–565 | 金底马赛克、大穹顶 | 3 | wonder | wonder 提案加权 |
| middle | 565– | 砖石混砌 | 2 | monumental | "节俭的辉煌" |

`style_era` 由建筑的建造年代自动推导（可覆写，需理由）。渲染色板按 `style_era × materials` 查表。

**风格漂移（style drift）**：年代之间不是硬切换。`style_eras.json` 增加 `transition` 规则：材料、穹顶技术、装饰密度三个参数随年代、灾变次数、国库水平缓慢漂移（如连续两次大火后木构权重下降、砖石上升）。漂移由 `grammar.py: drift_style()` 计算，提案与渲染都读漂移后的参数——换代不用人工干预。

## 5. 派系美学方言

每个派系一个偏好向量（写入 `rules/faction_styles.json`，软约束，权重制）：

- **emperor（皇帝）**：对称、轴线；偏好 domed_basilica、hippodrome、gatehouse、rotunda；材料偏大理石；ornament 倾向 3。
- **church（教会）**：垂直性、向天；偏好 cross_in_square、domed_basilica、monastery；金底马赛克；ornament 倾向 3。
- **merchants（商人）**：实用、临街、密集；偏好 market_row、insula、peristyle；砖石；ornament ≤1。
- **people（平民）**：courtyard_house；材料本地化；ornament 倾向 0–1；偶发捐建小教堂（声望动机）。
- **army（军队）**：tower、barracks（母题库 v2 增补）、城墙；功能优先；ornament 倾向 0。

提案 prompt 要求：每个 `build` 必须声明 `motif` + `faction`；材料默认按"派系×年代"推导，覆写需在 `why` 中说明。

**混血规则**：当两个派系合建（如皇帝出资、教会主持），dna 取双方偏好的加权混合，并在 `biography` 中注明。这是"风格杂交"的故事来源。

## 6. 声望经济（让宏伟从激励里长出来）

每个派系维护一个 `prestige`（声望）账本，存在世界状态中：

- 建筑落成时，按 `scale`/`wonder`/`sacred` 给建造派系加声望（wonder 级一次加 5 点，monumental 加 2 点）。
- 声望影响提案权重：声望落后的派系在下一个十年获得"野心加成"——规则引擎对其 monumental+ 提案放宽一条 warning（不是 reject），模拟"不甘人后"的内卷。
- 教会与皇帝的声望差超过阈值时，触发"辉煌竞赛"事件倾向：双方提案自动偏向更大尺度（在 prompt 中注入）。
- 声望随时间缓慢衰减（"前人栽树"会被遗忘），但 wonder 建筑的声望衰减减半——奇观是不朽的。

效果：宏伟不再是被安排的剧本，而是五个账本在激励下"不得不"卷出来的结果。

## 7. 建筑传记：引擎状态机 × 叙事八阶段

**引擎状态机**（`step.py` ops，直接影响世界状态）：

`planned → construction → standing → damaged → ruin → {restored → standing, rebuilt → standing, quarried → gone}`

| op | 含义 | 状态变迁 |
|---|---|---|
| build | 新建 | → construction（v1 可简化为直接 standing） |
| damage | 灾难/战争损毁 | standing → damaged |
| demolish | 拆除 | standing/damaged → gone（材料不回收） |
| quarry | 拆料 | ruin → gone，产出 spolia 库存 |
| restore | 修复 | ruin/damaged → standing |
| rebuild | 原址重建 | ruin → standing（保留 id，`biography` 追加） |

**叙事八阶段**（chronicle 层标签，不影响引擎，只影响故事写法）：

`proposed（倡议） → rising（兴建） → glory（鼎盛） → worn（斑驳） → wounded（创伤） → transformed（转身） → ruin（废墟） → myth（传说）`

- 每个 structure 的 `biography[]` 记录引擎事件；叙事阶段由实现 agent 在写编年史时根据 `biography` + 年代推导。
- 进入 `myth` 阶段的建筑：编年史允许失真重述（见传说机制），`{{id}}` 引用仍须指向真实 id。

## 8. 废墟层与 spolia（旧料新用）

- 废墟层是独立渲染层：灰色虚线 footprint + 年代标注。城市从此有了"地层"。
- 新建筑可声明 `spolia_from: [ids]`，表示使用了哪些废墟的旧料。
- `check.py` 验证：`spolia_from` 引用的 id 必须存在且 `state` 为 `ruin`/`quarried`。
- 叙事红利示例：编年史写"新教堂的十二根柱子取自老竞技场的看台"——零成本的真故事，拜占庭人真这么干。

## 9. 地形神圣度 sacred（可流动、可残留）

- `terrain.py` 标注 sacred 点：七丘顶点、岬角尖端、金角湾内凹处，`sacred: 0–3`。
- 规则：`sacred ≥ 2` 地块上的 civic 以上建筑，`wonder` 评分 +1；若该点已有 wonder，新提案必须在 `why` 中说明与既有建筑的关系（对景/扩建/取代），不能无视。
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
  "sacred": 2,
  "wonder": 3
}
```

- 旧数据无 `dna` 字段时视为 `vernacular`（乡土/未分类），`render.py` 用中性样式，保证向后兼容。
- `wonder` 为 0–5 评分，由规则引擎按 scale/materials/ornament/sacred 自动计算，提案不可自填。

## 11. 规则引擎新增检查（含无聊检测）

`rules.py` / `check.py` 新增（reject = 驳回，warning = 警告后允许修订）：

1. `build` 必须声明 `motif` 且在母题库中；否则 reject（附可选母题列表）。
2. `materials` 必须在该 `style_era` 调色板内；否则 warning（给 AI 在 dry-run 两轮修订内纠错的机会）。
3. `spolia_from` 引用的 id 必须存在且状态为 `ruin`/`quarried`；否则 reject。
4. `scale=wonder` 的建筑：footprint 面积 ≤ `calibration.json` 新增 `wonder_max_area`；同一 era 内处于 construction 的 wonder ≤ 1（防奇观通胀）。
5. `sacred ≥ 2` 地块上的 monumental+ 建筑：`why` 必须提及既有建筑关系（关键词检查）；缺失则 warning。
6. `demolish`/`quarry` wonder≥3 的建筑：需要 `why` ≥ 50 字（拆奇观是大事，要有交代）。
7. **无聊检测**（防闷不防错）：同一派系连续 3 个十年提案母题重复 → warning，建议换母题或加"处置旧建筑"项；全城近 5 个十年 ornament 分布熵低于阈值 → warning，提示注入变化。

## 12. grammar.py 接口（engine 新增模块）

```python
# engine/grammar.py
def motif_for(faction, style_era, rng) -> str
    """按派系偏好 × 年代权重抽取母题。"""

def materials_for(motif, faction, style_era) -> list[str]
    """推导默认材料，可被提案覆写。"""

def validate_dna(structure) -> tuple[bool, list[str]]
    """校验 dna 合法性；返回 (是否通过, warnings/errors)。"""

def wonder_score(structure, world) -> int
    """0–5 自动评分：scale/materials/ornament/sacred 加权。"""

def drift_style(world, era) -> dict
    """计算风格漂移后的参数（材料/穹顶技术/装饰密度）。"""
```

`step.py` 在 dry-run 与正式推进时调用 `validate_dna`；`render.py` 调用 `drift_style` 取色。

## 13. 渲染映射（render.py）

- 色板：`rules/styles.json`，按 `style_era × materials` 查 RGB（漂移后参数）。
- 图标：`motif → SVG glyph`（穹顶=圆+十字，塔楼=方形齿状，蓄水池=水波纹……）。
- 状态样式：construction=橙色斜线填充，damaged=红色裂纹标记，ruin=灰色虚线，wonder=金色描边。
- `docs/index.html`：图例增加"年代 / 派系"筛选器（复用现有 i18n 机制）。

## 14. 提案 prompt 与 HEARTBEAT 增补

- 提案 JSON 的 `structure` 增加 `dna` 字段要求；`proposals/make_eras_*.py` 模板同步更新。
- HEARTBEAT runbook 增补两条：
  - **每个十年至少包含一项"对既有建筑的处置"**（修缮/扩建/改建/拆除），培养城市的地层感。
  - 声望落后派系的提案自动获得"野心加成"提示词注入。
- 验收：`check.py` 新增 `dna_consistency` 检查；编年史 `{{id}}` 引用规则不变。

## 15. 分步实施计划

每步独立可验收，建议每步一个 commit（沿用现有习惯直接进 main）：

- **Step 1：数据模型 + 母题库 + styles.json + grammar.py 骨架**（不碰引擎）。验收：旧数据渲染像素级不变；新字段可读写；五个接口可 import。
- **Step 2：render 风格化**（色板/图标/废墟层/状态样式/风格漂移）。验收：同一地图肉眼可分辨年代差异；输出前后对比截图。
- **Step 3：rules 新增检查 + ops 扩展 + 声望经济 + 无聊检测**（restore/rebuild/quarry/damage）。验收：`step.py --dry-run` 能正确驳回非法提案（含测试用例）；声望账本可读写。
- **Step 4：prompt 增补 + 历史回填**（给现有建筑补 `dna`，如 wall_founder、forum_founder）。验收：`check.py` 全过；编年史无断裂；`docs` 时间轴正常。

## 16. 待决策问题（评审重点）

1. 年代划分用几段？草案 7 段，可并可分（建议先按草案跑，漂移感出来后再调）。
2. 是否允许"异域母题"（如波斯式穹顶、拉丁巴西利卡）作为贸易/战俘带来的外来风格？建议允许、低权重——是故事的种子。
3. wonder 并发上限：同一 era 只允许 1 个在建，是否太严？（备选：按国库/人口动态上限）
4. 派系美学用软约束（偏好权重）还是硬约束（禁忌）？建议先软后硬，跑 20 个十年看效果再收紧。
5. 声望经济的数值（加分/衰减率/阈值）先按草案估计值跑，第一个百年后按实际数据校准——是否接受"先拍脑袋后校准"？
6. 词汇表 v1 的 13 个母题是否过多/过少？评审时请逐个过。

## 附：术语表（中英对照，供 i18n 扩展）

- 母题 motif / 材料 materials / 装饰等级 ornament / 尺度 scale
- 废墟层 ruin layer / 旧料新用 spolia / 地形神圣度 sacredness / 奇观 wonder
- 建筑传记 building biography / 风格漂移 style drift / 派系方言 faction dialect
- 声望 prestige / 无聊检测 boredom detection / 混血 hybrid
