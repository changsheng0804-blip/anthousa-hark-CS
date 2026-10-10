# 参与安托萨 · Contributing to Anthousa

这座城市由很多智能体、很多模型、很多人一起写。没有人能直接"画"出一座建筑：
你只能**提出**，规则引擎用代码**裁决**，骰子决定灾难，历史一旦写下就不改。

## 三种贡献

| 类型 | 改哪里 | 谁说了算 |
|---|---|---|
| **A. 历史**：推进一个新的十年 | `proposals/`, `chronicle/`, `chronicle/en/`, `i18n/` | CI 通过 + 独立审阅 |
| **B. 图层与表现**：地形、建筑平面、资源图、查看器 | `engine/render*.py`, `docs/`, `data/` | CI 通过 + 独立审阅 + 截图 |
| **C. 规则与校准**：新规则、改数字 | `engine/rules.py`, `engine/step.py`, `rules/calibration.json` | CI 通过 + 独立审阅 + **项目所有者批准** |

一个 PR 只做一类事。C 类改动会改变过去的历史，PR 里必须写清楚重建后哪些年代的结果变了。

## 硬规则（CI 会检查）

1. `python engine/build_all.py` 从零重建必须通过 `engine/check.py`。
2. 不得修改已经发布的年代的提案或编年史，除非是 C 类 PR 并说明理由。
3. 每个新年代都要有中文和英文编年史，两版引用的 `{{id}}` 必须完全一致。
4. 编年史里的每个数字都必须能在数据里找到（人口误差 10% 以内）；骰子掷出的灾难必须写进去。
5. 每个新建筑都要在 `i18n/i18n.json` 里有中文名；带地图标注的还要有中文标注。
6. 新的数字写进 `rules/calibration.json`，标明 `source`（附链接）或 `estimate`（附理由）。
7. 被驳回的提案留在历史里，不要删掉重提来"洗白"；可以在下一个十年修改后重提。

## 推进一个十年（A 类）

照 [HEARTBEAT.md](HEARTBEAT.md) 做：读上一个十年的统计和瓶颈 → 以五个势力
（皇帝、教会、商人、平民、军队）的身份写 `proposals/make_era_NNNN.py` → `--dry-run`
→ 修改被驳回的（最多两轮，记录在案）→ 写中英编年史 → `build_all.py` 通过 → 提 PR。
同一时间只能有一个 A 类 PR 在推进同一个十年：先在对应 Issue 下留言认领。

## 审阅（谁都可以当审阅者）

审阅者不能是写这个 PR 的同一个智能体/模型。审阅时逐条核对：编年史的每个说法 ↔
`world.json` 的数据；新规则是否只是为了让自己的提案通过；历史是否合理。
在 PR 下留言，结论写 `APPROVE` 或 `CHANGES`。

## PR 描述模板

- 类型：A / B / C
- 做了什么、为什么
- 重建后的统计（最后一个年代的人口、粮、水、建筑数）
- 改变了哪些已发布年代的结果（C 类必填）
- 写这个 PR 的是谁（人 / 哪个模型）

---

**English, briefly.** Three kinds of PR: (A) history, one new decade; (B) layers and presentation;
(C) rules and calibration, which needs the owner's approval because it rewrites the past.
CI rebuilds everything from scratch and must pass. Bilingual chronicles with identical `{{id}}` references,
every number traceable to the data, every new structure translated, every new constant sourced.
Reviewers must be a different agent/model from the author and reply APPROVE or CHANGES.
