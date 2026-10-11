# 智能体协作协议 · Agent protocol

安托萨不按传统软件工程的方式做。它像一间画师工作室：**先生成，再自己看，然后重画**。
AI 的长处是能大量、快速、反复地生成；这份协议的目的，是让这个长处放开，同时不丢东西、不和史实打架。

（2026-10-11 所有者决定：本项目不再走 PR / 交叉审阅流程。旧协议见 git 历史。）

## 一个循环：生成 → 看 → 重来
1. **生成**：一次做一个「镜头」——一条街、一家人、一个年代、一种声音、一张画——而不是一个「功能」。同一个镜头可以一次生成几种，挑最活的一个。
2. **自己看**：做完必须打开成品看（截图、实际走一遍体验），用一个问题来评：**陌生人三分钟内能不能看懂、愿不愿意继续追下去？** 不好就重画、重写，不必等任何人。
3. **给所有者一眼**：只给成品链接和一句话的变化。所有者说「留」就留，说「再来」就再来。

## 谁管什么
| 谁 | 管什么 |
|---|---|
| 所有者（人） | 品味和方向。可以否决任何东西。 |
| 引擎（底账） | 只管事实：房子何时建、何时拆，哪场火烧了哪里，人口多少。生成的东西不能和底账矛盾，这一步由脚本自动核对。 |
| AI（任何智能体） | 画、人、故事、声音、体验。可以大胆生成，也可以随时推倒重来。 |

## 只有三条硬规矩
1. **不和底账打架**：画里、故事里、家庭里出现的年份、建筑、灾害，必须和 `world.json` 一致。推进新年代后跑 `python engine/build_all.py`，要能通过。
2. **正史只往前长**：已经发生的年代不改写。要改过去，先问所有者。
3. **不丢东西**：每一版成品留一个快照（如 `docs/living/v3/`），线上只指向最新的；旧版随时能打开对比。

## 怎么提交
- 直接提交到 `main`，推送后 Pages 自动发布。提交说明第一行写清楚改了哪个镜头，并署名（`——Hark`、`——Muse` 等）。
- 推送后打开线上页面确认能用。坏了就立刻修，或者回退到上一个快照。
- 大的方向变化（换路线、改规则、动正史）先问所有者，再动手。

## 目录
- `docs/` → GitHub Pages。`docs/living/` 是「活着的安托萨」体验，`docs/living/STORYBOARD.md` 是当前分镜。
- `world.json`、`proposals/`、`rules/`、`chronicle/` → 底账和正史。

---
**English, briefly.** Anthousa is built like an art studio, not a software project: generate, look at the result yourself, regenerate. No PRs or cross-review (owner decision, 2026-10-11). Three hard rules: never contradict the engine ledger (`world.json`, checked by `engine/build_all.py`); published history only grows forward (ask the owner before changing the past); never lose work (keep a snapshot of each version). Commit directly to `main`, sign the commit message, check the live Pages after pushing, and ask the owner before any change of direction.
