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

## 分级：哪里直推，哪里要所有者过目（2026-10-18 所有者同意）
不看 diff，看三样东西：**意图、独立证据、分级**。

| 级别 | 范围 | 怎么上线 |
|---|---|---|
| 承重墙 | `world.json`、`proposals/`、`rules/`、`chronicle/`、`engine/`、节点生成器 | 先在开关后面跑，所有者看过成品说「留」才转正。 |
| 主体 | `docs/living/` 的页面逻辑、生成管线、渲染器 | 直推 `main`，但新行为必须先放在开关后面（见下）。 |
| 外围 | 画面、文案、样式、脚手架、文档 | 直推 `main`，坏了回退快照。 |

### 每次提交写三行意图
提交说明第一行照旧（镜头 + 署名），正文写三行：
- **为什么**：这次要解决什么。
- **动了什么不变量**：底账、坐标、种子、接口，没动就写「无」。
- **怎么证明**：跑了什么、在哪看（截图链接、帧率数字、`build_all.py` 结果）。

### 证据不能只由作者自己出
- 验收标准在动手前写进 `STORYBOARD.md` 或 INBOX，动手后不改。
- 渲染、帧率、截图一律在所有者的 Mac 上实测，沙箱软件渲染的数字不算。
- 承重墙改动另请一条线或另一个智能体按验收标准复查，找反例，不看作者自测。
- 自动循环（/goal 之类）连续 3 轮没有产出就停下报告，不准在自己的守卫后面空转。

### 灰度和开关（静态页面版）
- **开关**：`docs/flags.json` 登记每个开关 `{名字, 负责人, 说明, 到期日}`；页面读 URL 参数 `?flag=名字`（或 localStorage）打开。默认全关，线上访客看不到。
- **灰度**：大改先发到 `docs/living/next/`（或 `vN-next/`），只把链接给所有者；说「留」再把线上指针切过去，旧版照旧留快照。
- **到期**：开关过了到期日还在，要么转正删开关，要么删代码。不留僵尸开关，组合态不准超过 5 个同时开。

### 交接：每条线一页 NOW.md
- 每条线根目录放一个 `NOW.md`，**只覆盖不追加**：当前方向、已有成品（链接 + 证据 + 主人评语）、进行中、等主人的事、下一步。
- 每次推送成品、或主人说了「留/再来」，同一次提交里更新它。
- 接手的智能体先读 `NOW.md`，再读本协议；日志（CS_LINE.md、nightlog、verdicts.json）照旧只往后长，用来查历史，不用来判断现状。

### 定期修剪：长 5 刀，剪 1 刀
- 每推出 5 个纵向切片（`verdicts.json` 里新增 5 条版本），下一轮只修剪不长：去重、合并相似的生成器、删死代码、清过期开关、重划一遍承重墙。不加任何新行为。
- 修剪算成功要同时满足：代码行数或文件数下降；所有机器报告的关键数字前后一致（例如 `net_report.json`）；主人看成品觉得没变。
- 修剪轮也记进 `verdicts.json`，`what` 以「修剪：」开头，好数到下一个 5。

### 地图要对得上地形
- 改了任何 `AGENTS.md` 或 `NOW.md`，推之前跑 `python3 tools/check_docs.py`：里面用反引号写的路径必须还存在，不为 0 就不推。
- 规矩写在 `AGENTS.md`，现状写在 `NOW.md`，不混着写。子目录可以有自己的 `AGENTS.md`，同样受这条检查。
- CS 线已有这个脚本；别的线直接拷过去即可，不依赖别的文件。

## 目录
- `docs/` → GitHub Pages。`docs/living/` 是「活着的安托萨」体验，`docs/living/STORYBOARD.md` 是当前分镜。
- `world.json`、`proposals/`、`rules/`、`chronicle/` → 底账和正史。

---
**English, briefly.** Anthousa is built like an art studio, not a software project: generate, look at the result yourself, regenerate. No PRs or cross-review (owner decision, 2026-10-11). Three hard rules: never contradict the engine ledger (`world.json`, checked by `engine/build_all.py`); published history only grows forward (ask the owner before changing the past); never lose work (keep a snapshot of each version). Commit directly to `main`, sign the commit message, check the live Pages after pushing, and ask the owner before any change of direction. Since 2026-10-18 changes are tiered: load-bearing paths (ledger, engine, node generators) ship behind a flag and need the owner's keep; everything else pushes to main. Every commit body states why, which invariants it touched, and the evidence. Evidence is independent of the author (acceptance criteria fixed beforehand, rendering measured on the owner's Mac). Each line keeps an overwrite-only `NOW.md` (direction, what exists with evidence and owner verdict, in progress, waiting on owner, next); update it with every shipped change and read it first. After every 5 vertical slices, run one merge-only consolidation round (fewer lines, identical report numbers, no new behavior). Run `python3 tools/check_docs.py` before pushing changes to any AGENTS.md or NOW.md. Flags live in `docs/flags.json` with an expiry, toggled by `?flag=`; big changes go to `docs/living/next/` first.
