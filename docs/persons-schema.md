# 人物层数据模型（persons schema）

起草：Muse（按 Hark 2026-10-10 CHANGES 审阅修订）

人物数据写入 `persons/` 源文件（每十年一个，如 `persons/af_0031.json`）；`world.json` 是派生文件（.gitignore），由 build_all.py 合并生成，不直接写。人物层从 AF 31 起试运行；AF 21–30 不做回填。

## Schema（persons/af_NNNN.json）

```json
{
  "persons": [
    {
      "id": "p_petros",
      "name": "佩特罗斯",
      "name_en": "Petros",
      "born": -38,
      "died": null,
      "trade": "mason",
      "faction": "people",
      "address": "fourth_hill",
      "address_note": "第四山丘脚下的棚屋",
      "status": "alive",
      "last_mentioned": 20,
      "bio": "色雷斯山里来的石匠……（约200字，必须引用真实 {{id}}）",
      "linked": ["aqb_valley", "nymphaeum_great"]
    }
  ]
}
```

字段说明：
- `id`：`p_` 前缀，全局唯一。
- `born` / `died`：AF 年份整数；`died: null` 表示在世；死亡按年龄与事件/骰子推定。
- `trade`：职业自由文本，建议复用已有词。
- `faction`：所属派系；表现层可用。
- `address`：引用真实存在的街区或地标 id；`address_note` 补充文字描述（如棚屋、阁楼）。
- `status`：alive | dead | faded。
- `last_mentioned`：最后被提起的十年（AF 年份）；用于半衰期判定。
- `bio`：约 200 字，必须引用真实存在的建筑或事件 `{{id}}`；不许编造地点。
- `linked`：关联的建筑/事件 id 数组。

## 编年史引用语法

编年史中引用人物使用 `{{p_xxx}}`（如 `{{p_petros}}`），与建筑 `{{id}}` 区分。check.py 的人物引用校验分支**下一 PR 实现**（当前 check.py 会把未知 `{{id}}` 当未建成建筑报错，在人物校验分支落地前，人物引用暂不受校验）。

## 生命周期

1. **析出**：每十年 heartbeat 从本十年事件与建筑里析出 3–5 人，优先重大事件相关者。
2. **变老**：每十年 +10 岁。
3. **死亡**：按年龄与事件/骰子推定。
4. **淡出**：`last_mentioned` 距今超过两个十年、且未被编年史引用 → `status: faded`（保留记录）。
5. **永存**：被编年史引用过的人物永不删除、永不淡出。

## 实现状态

- 本 PR：机制文档 + schema（本文件）。
- 下一 PR：build_all.py 合并 `persons/` 进 world.json；check.py 人物引用校验；"bio 必须引用真实 `{{id}}`" 的代码执行。

## 示例

**佩特罗斯**，58 岁，石匠（AF 20 年析出）：
色雷斯山里来的石匠，跟着水渠进的城。在 `{{aqb_valley}}` 那段 560 米的谷地拱廊干了六年，专管拱顶合龙——第 14 年一次塌方压断了他左手两根手指，皇帝的工程师赔了三个月工钱。现在住第四山丘脚下的棚屋，手指使不上劲，只能带学徒。小儿子在 `{{nymphaeum_great}}` 当守水人，是他托工头求来的差事。他常说：这水渠里有一段拱，是他儿子将来要守的水流过的。
