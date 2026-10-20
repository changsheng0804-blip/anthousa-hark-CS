# NOW · CS 线现在到哪了

> 只覆盖不追加。接手的智能体先读这页，再读 AGENTS.md。历史看 git log、CS_LINE.md、tools/cs/factory/verdicts.json。
> 最后更新：2026-10-20 04:30 PDT ——Hark（CS线）

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
| 3D lookdev 第 2 轮（8 模块合并：低太阳 + 调色、立面/柱廊/粮仓、石板街、港水倒影、区外陆地和远岸、船吊车货堆、树、5966 口人） | docs/living/nodes/nangang/3d.html（`?shot=1..4` 看固定机位） | `docs/cs/lookdev/r2/report.md`、`docs/cs/lookdev/r2/overview.jpg`；沙箱：模块验收 9/12 条过，三角形 1.58–1.60 M | 待评（帧率待 Mac 实测） |

灰度入口：docs/living/next/（主页加 ?flag=nodes-nangang 才露入口），第 2 轮总览和报告的链接在那页。

## 进行中
- **南港 3D lookdev 第 2 轮：合并完成（10-20）**。7 个模块代理 + 导演合并都已推到 main。现状：
  - 4 个机位从「白模 + 正午平光」变成有光、有材质、有船有人的画面；机位 1、3、4 的光和调色过 sky 验收，机位 2 没过（顺光照亮整条街，参考是逆光）。
  - 导演改了：相机 far 9000→16000；机位 3 抬头左转（地平线 ≈0.14，看得到东岸和远岸），机位 3 旧基线数字不再可比，已在新机位重拍；sky 加冷灰天光补光，粮仓山墙不再是黑的；`__modStats` 改在出图后数三角形。
  - 剩下的差距（排名和归属见报告）：机位 2 太亮太平；粮仓码头没人（要 folk.py 加搬运工路线）；码头岸是沙坡不是石墙；机位 3 远处没细节；区外的城是空的。
  - 怎么看：打开 `docs/living/nodes/nangang/3d.html`，加 `?shot=1`（港）、`?shot=2`（主街）、`?shot=3`（高空）、`?shot=4`（粮仓）；加 `&quality=preview` 看低档；`&only=buildings,streets` 只开几个模块。
- 古城（gucheng）：另一个会话在做，别碰它的文件。

## 等主人（Mac 上实测，沙箱的数字不算）
- **帧率**：4 个机位在 `quality=high` 和 `quality=preview`、全部模块打开时的 fps 和最差一帧（预算 ≥60 fps、≤25 ms）。控制台 `window.__modStats` / `window.__trisTotal` 给三角形，`window.__crowdStats` 给人群 CPU 毫秒。
- **三角形预算**：现在每个机位约 1.6 M（契约上限 3 M）；若 Mac 吃紧，先砍 props 港区货堆、terrain 远档。
- **倒影开销**：water 的半分辨率平面倒影每帧多渲一遍场景，机位 1 开/关倒影各测一次帧率，决定要不要只在近水时开。
- 看总览 `docs/cs/lookdev/r2/overview.jpg`：留 / 再来；机位 2 要不要改成逆光（像参考图）。

## 下一步（主人点头后，第 3 轮提案，详见报告末节）
1. 机位 2 光向 + 粮仓搬运工路线（people 管线 → crowd）。
2. 硬码头：港池蒙版锐化 + 竖直码头石墙 + 水线湿痕。
3. 区外远景城 + 机位 3 远海细节，同一轮先在 Mac 上过帧率预算。
