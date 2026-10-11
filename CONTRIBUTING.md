# 参与安托萨 · Contributing to Anthousa

这座城市由很多智能体、很多模型、很多人一起写。没有人能直接"画"出一座建筑：
你只能**提出**，规则引擎用代码**裁决**，骰子决定灾难，历史一旦写下就不改。

## 怎么贡献

不走 PR，不做交叉审阅（所有者 2026-10-11 决定）。照 [AGENTS.md](AGENTS.md) 的工作室循环做：**生成 → 自己看 → 重画**，然后直接提交到 `main`，提交说明署名。
改规则、改引擎数字、动已发布的历史这类方向性的事，先问所有者。

## 硬规则（CI 会检查）

1. `python engine/build_all.py` 从零重建必须通过 `engine/check.py`。
2. 不得修改已经发布的年代的提案或编年史；要改过去，先问所有者。
3. 每个新年代都要有中文和英文编年史，两版引用的 `{{id}}` 必须完全一致。
4. 编年史里的每个数字都必须能在数据里找到（人口误差 10% 以内）；骰子掷出的灾难必须写进去。
5. 每个新建筑都要在 `i18n/i18n.json` 里有中文名；带地图标注的还要有中文标注。
6. 新的数字写进 `rules/calibration.json`，标明 `source`（附链接）或 `estimate`（附理由）。
7. 被驳回的提案留在历史里，不要删掉重提来"洗白"；可以在下一个十年修改后重提。

## 推进一个十年（A 类）

照 [HEARTBEAT.md](HEARTBEAT.md) 做：读上一个十年的统计和瓶颈 → 以五个势力
（皇帝、教会、商人、平民、军队）的身份写 `proposals/make_era_NNNN.py` → `--dry-run`
→ 修改被驳回的（最多两轮，记录在案）→ 写中英编年史 → `build_all.py` 通过 → 提交到 main，打开线上 Pages 看一眼。
同一时间只能有一个 A 类 PR 在推进同一个十年：先在对应 Issue 下留言认领。


**English, briefly.** No PRs or cross-review (owner decision, 2026-10-11). Follow the studio loop in AGENTS.md: generate, look at the result yourself, regenerate, then commit to main with a signed message. The hard rules above still hold: rebuild must pass `engine/check.py`, published history is never rewritten without asking the owner, chronicles in Chinese and English with matching ids, every number traceable to the data.
