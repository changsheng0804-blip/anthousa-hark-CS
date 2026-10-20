# NOW · CS 线现在到哪了

> 只覆盖不追加。接手的智能体先读这页，再读 AGENTS.md。历史看 git log、CS_LINE.md、tools/cs/factory/verdicts.json。
> 最后更新：2026-10-20 09:40 PDT ——Hark（CS线）

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
| 3D 地标试点：狄奥多西广场纪功柱（landmarks 模块第一座） | docs/living/nodes/nangang/3d.html?shot=5（第 65 年；第 60 年是施工中） | `docs/cs/lookdev/landmarks/column/notes.md`、`docs/cs/lookdev/landmarks/column/overview.jpg`；10-20 第二遍修订后轮廓 IoU 0.83（框对齐）/ 0.86（按高）、高宽比 5.0（参考 5.35）；机位 1–4 match 全过 | 待评（帧率待 Mac 实测） |
| 3D 地标第 2 座：大宁芙殿 Nymphaeum Maius | docs/living/nodes/nangang/3d.html?shot=6（第 60 年） | `docs/cs/lookdev/landmarks/nymphaeum/notes.md`、`overview.jpg`；轮廓 IoU 0.59（占位）→ 0.83（框对齐）、高宽比 0.77（参考 0.65）；机位 1–5 match 全过，2–4 逐像素不变 | 待评（帧率待 Mac 实测） |

| 3D r3：地面穿模 + 史诗夸张（主人 10-20 两条） | docs/living/nodes/nangang/3d.html（`?shot=1..6`；机位 5、6 重新对准） | `docs/cs/lookdev/r3_ground_scale/notes.md`、`docs/cs/lookdev/r3_ground_scale/overview.jpg`、`docs/cs/lookdev/r3_ground_scale/numbers.json`；`tools/cs/lookdev/ground_check.py`：第 65 年漏空 26→14、埋墙脚 1671→2；纪功柱 51.9→72.7 m（周边屋顶中位数的 8.2→11.5 倍）、宁芙殿 22.2→30.5 m（3.1→4.2 倍）；每机位 1.62–1.68 M 三角形 | 待评（帧率待 Mac 实测） |

灰度入口：docs/living/next/（主页加 ?flag=nodes-nangang 才露入口），第 2 轮总览和报告的链接在那页。

## 进行中
- **r3 地面穿模 + 史诗夸张（10-20，主人：「地面穿模明显，要调整」「史诗城市里地标放大一些，尤其大的」）**：
  - 落地规矩进了 `docs/cs/lookdev/MODULE_CONTRACT.md` §6 第 13 条：站在地上的一律用 `ctx.groundMesh`（terrain 网格的三角插值，框外读 terrain/outer.js 的 `heightAt`）；有占地的用 `ctx.footing` → 地坪 = 最高地面（民居 max(mid, max−0.45)），台基 / 墙基伸到最低地面 −0.6，`ctx.foot` 登记；验收 `ground_check.py`。
  - 史诗夸张进了 §7：每座地标 `HERO_SCALE`（纪功柱、宁芙殿 1.4，只放大高，占地照底账）；buildings 里的广场柱廊、粮仓 `LM_SCALE` 1.2。纪功柱、宁芙殿原来的轮廓 IoU 数字不再是目标。
  - 剩下：14 户在页面框角（区内 / 区外地形接缝高差 20–80 px，要 terrain 缝合）；2 座框外栈桥埋在区外地形里；港池岸仍是沙坡，码头户现在立在高墙基上；陡街上临街铺面墙基最高 ≈2.5 px（主人嫌高可改回中心地坪）。
- **南港 3D 地标（landmarks，10-20 开）**：主人 10-20 说 Mac 帧率够（60–90）、3D 样子可以接受，史诗/特殊公共建筑按 athenaion 的做法一座座做。已推两座：纪功柱（机位 5）、大宁芙殿（机位 6）。
  - **大宁芙殿（10-20 第二座）**：`docs/living/nodes/nangang/3d/landmarks/nymphaeum.js` + 烘焙像 `tools/cs/landmarks/bake_nymph_statues.py`；`shots.json` 加机位 6；buildings 的半圈柱子 + 水池占位删了（留 15 个零高度空实例保住广场柱廊的色差序号）。
    底账：`nymphaeum_maius` y0=44、`proposals/era_0041.json` dna rotunda/砖/大理石贴面、无 phases（不画施工）；水道桥 aq_hadrian 贴北边过。形制史料无载 → 按两层壁龛式宁芙殿假设（7 折面弧形立面、两端塔、18 尊宁芙像、吐水 + 4 道水瀑 + 鼓出的大池），全在 notes.md。
    立面整片背光（太阳西北偏西）：在地标材质里加了按法线的西南天光补光、塔面反照率 ×0.7，sky 没动。机位 6：IoU 0.59→0.83、高宽比 0.34→0.77（0.65）、蒙版 L* 41.9（43.1）、边缘 0.134（0.125）、饱和 0.31（0.27）、受光 p90 94.4（87.8）。近档 58,099 / 远档 24,159 三角形，几何 ≈0.1 s，贴图 init ≈0.7 s（沙箱）。
    剩下的差：参考立面更高、正面受光；人眼高看不到池水面；柱头只有钟形 + 顶板；远档可以再省。
  - 纪功柱（第一座），当天按主人三条又修了一遍：
  - 一座一个文件 `docs/living/nodes/nangang/3d/landmarks/`（`index.js` 模块壳 + `column.js` + `kit/` 部件），core 的 MODULES 里只多了 `landmarks` 一项；buildings 里的占位圆柱删了。规矩和配方见 `docs/cs/lookdev/MODULE_CONTRACT.md` 第 7 节。
  - 底账：`forum_theodosius` 中心；`proposals/era_0051.json` 写 64 年立到顶 → 58–63 年画施工中（基座 + 长高的柱身 + 脚手架）。假设（科林斯柱头、51.95 m、像 9.3 m 面朝西、镀银不鎏金）都写在 notes.md。
  - 修订（主人：浮雕浅、受光面亮、像和柱头小）：螺旋边带做成真几何凸棱、基座画框的场真凹 0.12 m、凹缝 AO 烘进贴图；反照率在地标材质里压（sky / 全局光没动）；柱头 2.6→4.0 m、像 7.5→9.3 m、基座矮瘦。机位 5 数字：IoU 0.75→0.83、高宽比 4.37→5.00（5.35）、像/柱头占比 0.16/0.05→0.20/0.07（0.22/0.07）、蒙版 L* 54→42（40）、受光面 p90 95.5→88.8（84.5）、边缘 0.22→0.33（0.30）。近档 41,288 / 远档 3,920 三角形。
  - 工具：`tools/cs/lookdev/silhouette.py`（比形）；雕像烘焙 `tools/cs/landmarks/bake_statue.py`（这次没重烘，按尺寸放大）。
  - 剩下的差：阴面太黑（全局补光的事，地标里不抬）；受光面 p90 比目标高 0.8；饱和和边缘比参考高约 10–20%；像是暗银灰，参考画成深色青铜。
- **南港 3D lookdev 第 2 轮：合并完成（10-20）**。7 个模块代理 + 导演合并都已推到 main。现状：
  - 4 个机位从「白模 + 正午平光」变成有光、有材质、有船有人的画面；机位 1、3、4 的光和调色过 sky 验收，机位 2 没过（顺光照亮整条街，参考是逆光）。
  - 导演改了：相机 far 9000→16000；机位 3 抬头左转（地平线 ≈0.14，看得到东岸和远岸），机位 3 旧基线数字不再可比，已在新机位重拍；sky 加冷灰天光补光，粮仓山墙不再是黑的；`__modStats` 改在出图后数三角形。
  - 剩下的差距（排名和归属见报告）：机位 2 太亮太平；粮仓码头没人（要 folk.py 加搬运工路线）；码头岸是沙坡不是石墙；机位 3 远处没细节；区外的城是空的。
  - 怎么看：打开 `docs/living/nodes/nangang/3d.html`，加 `?shot=1`（港）、`?shot=2`（主街）、`?shot=3`（高空）、`?shot=4`（粮仓）；加 `&quality=preview` 看低档；`&only=buildings,streets` 只开几个模块。
- 古城（gucheng）：另一个会话在做，别碰它的文件。

## 等主人（Mac 上实测，沙箱的数字不算）
- **r3**：看 `docs/cs/lookdev/r3_ground_scale/overview.jpg`：穿模修得算不算数、放大 1.4 够不够（要更夸张就改各地标文件的 `HERO_SCALE`）、陡街铺面墙基高不高；Mac 上机位 1–6 帧率。
- **纪功柱**：`3d.html?shot=5` 看一眼「留 / 再来」；Mac 上机位 5 的帧率（近档 41,288 三角形、远档 3,920）；像要不要更大 / 鎏金、柱头要不要改回史实更可能的多立克式。
- **大宁芙殿**：`3d.html?shot=6` 看一眼「留 / 再来」；Mac 上机位 6、5 的帧率（宁芙殿近档 58,099、远档 24,159）；立面形制（弧形两层壁龛 + 两端塔）和朝向（朝南偏东、背靠水道桥）认不认。下一座做哪个（候选：粮仓立面、广场凯旋门、蓄水池）。
- **帧率**：4 个机位在 `quality=high` 和 `quality=preview`、全部模块打开时的 fps 和最差一帧（预算 ≥60 fps、≤25 ms）。控制台 `window.__modStats` / `window.__trisTotal` 给三角形，`window.__crowdStats` 给人群 CPU 毫秒。
- **三角形预算**：现在每个机位约 1.6 M（契约上限 3 M）；若 Mac 吃紧，先砍 props 港区货堆、terrain 远档。
- **倒影开销**：water 的半分辨率平面倒影每帧多渲一遍场景，机位 1 开/关倒影各测一次帧率，决定要不要只在近水时开。
- 看总览 `docs/cs/lookdev/r2/overview.jpg`：留 / 再来；机位 2 要不要改成逆光（像参考图）。

## 下一步（主人点头后，第 3 轮提案，详见报告末节）
1. 机位 2 光向 + 粮仓搬运工路线（people 管线 → crowd）。
2. 硬码头：港池蒙版锐化 + 竖直码头石墙 + 水线湿痕。
3. 区外远景城 + 机位 3 远海细节，同一轮先在 Mac 上过帧率预算。
