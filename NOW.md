# NOW · CS 线现在到哪了

> 只覆盖不追加。接手的智能体先读这页，再读 AGENTS.md。历史看 git log、CS_LINE.md、tools/cs/factory/verdicts.json。
> 最后更新：2026-10-20 01:10 PDT ——Hark（CS线）

## 方向（主人 2026-10-17 定）
底账 → 节点 → 渲染器（学 WorldGacha）：节点按顺序、可重抽，中间层是 OSM 形状 + 年份，近/远/地平线分层，一个渲染器。AI 写生成器和部件，不画内容。拆解见 tools/cs/nodes/README.md。
3D 的「样子」从 10-20 起按 athenaion 的做法追：参考图 → 美术圣经 + 模块契约 → 模块并行，对着固定机位比数字（见下「lookdev」）。

## 已有成品（南港一块，全链路跑通）
| 成品 | 地址 | 证据 | 主人 |
|---|---|---|---|
| 节点样板 nodes1 | docs/living/nodes/nangang/index.html | perf 基线见 tools/cs/nodes/README.md | 留（「效果好多了」）|
| 长卷 scroll1 | docs/living/nodes/nangang/scroll.html | 无机器验收 | 留（「确实好不少」）|
| 路网节点 net.py | scroll.html?n=net | net_report.json：5163/5163 户入街，pass | 待评 |
| 水系节点（水道桥/蓄水池/井） | scroll.html | water_report.json | 待评 |
| 长卷街区细化（街名路牌、招牌、坡地台基台阶、柱廊额枋） | scroll.html | 10-20 提交 b506e82、ff210df | 待评 |
| 居民：姿势引擎 + 人群 + 户籍关系 | scroll.html?n=net&crowd=N | tools/cs/people/README.md；Mac 实测一万人 100 fps | 模型不再细抠（10-19）；关系接入待评 |
| 3D 试作 | docs/living/nodes/nangang/3d.html | lookdev 基线：docs/cs/lookdev/baseline/report.md | 待评 |

灰度入口：docs/living/next/（主页加 ?flag=nodes-nangang 才露入口）。

## 进行中
- **南港 3D lookdev 第 1 轮（10-20 完成基线）**：4 张参考图 docs/cs/lookdev/refs/（按底账核过，南港无教堂）；ART_BIBLE.md、MODULE_CONTRACT.md；固定机位 docs/living/nodes/nangang/shots.json，3d.html 加了 ?shot=N&clean=1&still=1 钩子（不带参数行为不变）；工具 tools/cs/lookdev/render.py（无头出图）和 compare.py（Lab/反差/直方图/饱和/冷暖/边缘密度 + 并排图）。基线结论：骨架对，样子是白模 + 正午平光；前五差距 = 光和调色（sky-atmosphere）、房子白模（buildings）、街面平涂（streets）、水平色 + 区外空海（water/terrain）、没有船和人（props/crowd）。沙箱只看样子，帧率没测。
- 古城（gucheng）：户籍、街名、招牌、大地标部件已推（436984f），另一个会话在做。

## 等主人
- 看 lookdev 总览 docs/cs/lookdev/baseline/overview.jpg：参考图的样子对不对（定了就是第 2 轮的靶子），机位要不要改。
- 南港节点版「留」还是「再来」；2D 长卷还是 3D 继续走。

## 下一步（主人点头后）
- lookdev 第 2 轮：先由一个代理把 3d.html 拆成 docs/living/nodes/nangang/3d/ 下的模块（数字要和基线对上），再并行 7 个模块代理（sky-atmosphere、buildings、streets、water、terrain、props+flora、crowd），每个按 report.md 第 4 节的自查机位和验收数字跑；最后导演代理合并复测，主人 Mac 上看帧率。
- 节点链往外长一块街区，验证跨街区接缝从结构上消失。
