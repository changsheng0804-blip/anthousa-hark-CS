# 等轴重绘试验（Isometric SF 做法）· 南港一格

2026-11-05，CS 线。主人说「试试」。**不改任何线上页面**：只读 `docs/living/nodes/nangang/3d.html`，相机和遮罩都在 playwright 里临时加。

## 借的是什么

- **Isometric SF**（Justin Chavez，isometricsf.com）：先拿真实 3D 几何渲染每一格，再用图生图模型把每格重绘成干净的等轴插画（SimCity 4 那种：边缘利落、楼色有变化、水干净、绿色饱和但收着）。
- **Isometric Toronto**（iso.sloptoronto.ca，“homage to the city builders of the 1990s”，Google 3D Tiles 经 Cesium ion 渲染后 AI 上画）：真正的正交等轴、无透视、树密、立面色调偏柔、日光平和。主人说「差不多的感觉」，作为 A 的第二张风格参考。
- 两站的截图只在沙箱里当风格参考喂给模型，**没有放进仓库**，也没有搬它们的任何内容。

## 做法

1. **几何底稿**（`tools/render_iso.py`）：加载 `3d.html?clean=1&still=1`，`__setYear(65)`，另建一台 `OrthographicCamera`：方位 45°（从东南看向西北），俯角 35.264°（标准等轴），中心 (1500, 1180) 页面像素，半高 260 px，1024×1024。临时关掉雾。同一机位再出一张 `MeshDepthMaterial` 深度图（`depth.png`）。本轮的图生图工具只吃参考图，深度图没用上，留给以后接 ControlNet 类的管线。
2. **底账投影**（`tools/ledger_mask.py`）：同一台相机，把 nodes.json 里当年活着的 533 栋房子（房基加上 ht×1.15+3 的屋顶高，取凸包）、街道和水陆（陆地/石堤/当年港池）投影成遮罩。`overlay_render.jpg` 里，底账轮廓和 3D 渲染逐像素重合，所以拿它当真值。
3. **重绘**（Hark `generate_image`，图生图，第 1 张图是渲染，后面是风格参考）：
   - **A**：渲染 + Isometric SF 截图 + Isometric Toronto og 图。
   - **B**：渲染 + Isometric SF 截图 + `docs/living/east_af30.jpg`（我们自己的色）。第 1 次失败（见下），第 2 次去掉 SF 参考，只留渲染和 east_af30，并且把港池、角落写死。
   - 两个提示词都要求：机位、构图不变；每栋房子的位置、占地、朝向、高度不变；街道、岸线、石堤、栈桥、船不动；水还是水；不准加或减房子，不准新造塔、穹顶、地标；不准出现现代物件；5 世纪君士坦丁堡式。完整提示词在文末。
4. **核对**（`tools/fid.py`）：B 的输出画幅被模型改了（976×1099），先按渲染的梯度场搜缩放和平移，把它对齐回来（A 本来就是 1024²，不用对）。然后在同一机位下和底账比。

## 保真数字（`fidelity.json`）

| | 水 IoU（对底账） | 房子命中（底账屋顶中心 ±1px 有屋顶色） | 屋顶落在底账房子里的比例 | 屋顶色落在底账水上 | 边缘 F（对渲染，±1px / ±3px） |
|---|---|---|---|---|---|
| **A** | 0.777（左下港池 0.923） | 0.947 | 0.968 | 2.7% | 0.833 / 0.951 |
| **B 第 2 次** | 0.749（左下 0.887） | 0.891 | 0.771 | 3.4% | 0.657 / 0.866 |
| B 第 1 次（作废） | 0.362 | 0.775 | 0.755 | 17.6% | 0.553 / 0.783 |

- 两张的水 IoU 都被右下角拉低（那一格只有 0.52–0.54）。那里是节点地图边界（x>1820）外面的区外地形，底账的水陆遮罩把它算成了水，渲染和重绘都画成了陆地。这是遮罩的毛病，不是重绘漂了。
- 渲染本身不按颜色打分：它的水是深绿、屋顶大半在长阴影里，颜色阈值不适用。它和底账是靠投影对上的。
- B 的屋顶比例偏低，一部分是因为它的蜂蜜色街道被屋顶色阈值误收，不全是多画了房子。

## 我看图的结论（照实说）

- **A 更好，也更忠实。** 房子一栋对一栋，街网、岸线、两道石堤、栈桥、船、岸边的起重架都在。它改动的地方：① 渲染里的长阴影全没了，改成短软影（这正是想要的）；② 右下角区外的低模地形被画成了一片带小土堆的沙地，还多了一个小木架。那一角本来就不在底账里，但也不该自己长东西；③ 少数挤在一起的小房子被合成了一栋，主要在中右部密的那几块；④ 路面画成了卵石带，比底账的街宽一点。
- **B 第 1 次严重漂移**：把港池中间画成一座大回廊院子，加了城墙、塔、农田和船坞，等于往底账里多写了一座地标。作废，这正是这种方法最大的风险。
- **B 第 2 次**：上半城很像，色也是我们要的（赤陶屋顶、浅石灰墙、马尔马拉蓝绿水）。漂移有：① 擅自改画幅，对齐后右边缺一条；② 岸边的起重架被抹掉；③ 港池的石堤画成了宽平的码头带，形状大致对，但比底账粗；④ 街道画成统一宽的黄带，主次街的宽窄区别没了；⑤ 东南边缘的几排房子位置有 3–6 px 的错动。看起来更像「游戏地图」，扁一点，立体感不如 A。
- **结论**：画法用 A（模型最听话的组合是「渲染 + SF/Toronto 参考」），色往 B 的方向调。下一步该试的是「A 的参考组合 + 提示里写我们的色」，而不是再多喂一张我们自己的图：多喂一张有内容的参考图，模型就会去搬它的内容。

## 成本和时间（估算，未实测批量）

- 每格：3D 渲染加遮罩，页面已热时约 5–10 秒（冷启动约 55 秒，主要是建城）。重绘每张约 1 分钟。按公开图生图 API 价，一张 1024² 大约 0.04–0.19 美元，Hark 内部实际计费我看不到。核对是本地脚本，约 1 分钟，可以并行。
- 失败率：这次 3 张里废 1 张（B 第 1 次），按 30% 返工算。
- **南港全图**（1820×2048 px，约 1.5×1.7 km）：这个缩放下一格的地面大约 520×900 px，留 30% 重叠，约 11 格，去掉纯海约 8–10 格，加返工 **约 12–14 次生成，0.5–3 美元，半小时内**。要能放大到两倍细节，就是 ×4，约 50 次，2–10 美元，1–2 小时。
- **全城**（city/nodes.json 5915×6370 px，同比例）：约 115 格，去掉海约 80 格，加返工 **约 105 次生成，4–20 美元，2–3 小时**（串行；并行更快）。两倍细节就 ×4，约 420 次，17–80 美元。
- **每个关键年份**再乘一次（比如 5 个关键年就 ×5）。年份之间可以只重绘有变化的格子，用底账 diff 定是哪几格，能省一半以上。
- **没解决的**：格与格之间的接缝。每格单独重绘，色调和细节在边上对不上。Isometric SF 是靠重叠和羽化来消的，我们要上全城，得先做「重叠 + 边缘融合 + 统一调色」这一步，另外每格都要过这里的保真核对，过不了的自动重画。

## 提示词

**A**：Image-to-image repaint. IMAGE 1 is the source: an isometric 3D render of a harbour district of a 5th-century Constantinople-like Late Roman city. Repaint IMAGE 1 as a clean illustrated isometric city-builder tile in the style of IMAGES 2 and 3 (Isometric SF / Isometric Toronto, homage to 1990s city builders like SimCity 4): crisp clean edges on every roof and wall, flat-shaded faces with soft even daylight from the upper left, short soft shadows instead of the long dark shadows, varied but controlled building colours (warm terracotta, ochre, cream, pale limestone walls), clean flat blue-green water with gentle highlights, saturated but controlled greens on the existing trees, light paved streets. STRICT GEOMETRY LOCK: keep the exact same camera, framing, and composition as IMAGE 1; keep every building at exactly the same position, footprint, orientation and height; keep every street, the shoreline, the stone harbour moles, the jetties and the ships exactly where they are; water stays water, land stays land. Do NOT add any new buildings, do not remove buildings, do not merge blocks, do not invent towers, domes or landmarks. Only change the painting style. Period-correct only: no modern objects, no cars, no roads markings, no glass, no skyscrapers, no power lines, no people at large scale. No text, no labels, no watermark, no border.

**B 第 2 次**：Restyle IMAGE 1 only; output must be the same square framing as IMAGE 1, pixel-aligned to it. … clean illustrated isometric city-builder tile (crisp clean edges, flat-shaded faces, 1990s city-builder / SimCity 4 illustration), using the palette of IMAGE 2: Byzantine terracotta tile roofs in several reds and oranges, whitewashed and pale limestone walls, warm honey limestone streets, clean calm Sea of Marmara blue-green water, dark cypress and olive greens, soft warm morning daylight with short soft shadows. STRICT GEOMETRY LOCK: this is a trace-over, not a new picture. The large water area in the lower-left half of IMAGE 1 is an open harbour basin and must remain completely open water … Do NOT add anything: no new buildings, no courtyards, no cloisters, no city walls, no towers, no fields, no shipyards, no extra ships. Use IMAGE 2 for colour only, not for content or layout. No modern objects, no text, no labels, no watermark, no border.

（B 第 1 次的提示词和 A 差不多，参考图是 SF 截图加 east_af30，结果见 `repaint_B_rejected.jpg`。）

## 文件

`compare.jpg`（渲染 | A | B，中文标注）、`render.jpg`、`depth.png`、`repaint_A.jpg`、`repaint_B.jpg`、`repaint_B_rejected.jpg`、`overlay_*.jpg`（品红 = 底账房子轮廓，青 = 底账水岸）、`fidelity.json`、`tools/`（三个脚本，用沙箱的 /usr/bin/chromium 跑）。

——Hark（CS线）
