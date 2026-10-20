# 南港 3D · 模块契约（lookdev 第 1 轮定稿）

> 读这页再动 `docs/living/nodes/nangang/3d.html`。美术目标见 `ART_BIBLE.md`，差距排名见 `baseline/report.md`。
> 方向不变：**底账 → 节点 → 渲染器**。模块是渲染器的零件：AI 写生成器和部件（代码），不画内容（图）。
> ——Hark（CS线）2026-10-20

## 1. 工具（每个模块代理都用同一套）

```bash
# 仓库根目录。沙箱里先设好 chrome（主人 Mac 上不用设，playwright 自带 chromium 即可）
export LOOKDEV_CHROME=…/chrome-headless-shell  LOOKDEV_LIBS=…  LOOKDEV_PYLIB=…   # 可选
python3 tools/cs/lookdev/render.py --out /tmp/me            # 4 个机位 → /tmp/me/shotN.png
python3 tools/cs/lookdev/render.py --shot 2 --out /tmp/me --param "only=buildings,streets"
python3 tools/cs/lookdev/compare.py --renders /tmp/me --out /tmp/me   # cmp_shotN.jpg + stats.json + 排名
```

- 页面钩子（不带参数时页面完全不变）：`3d.html?shot=N` 套用 `shots.json` 的机位；`&clean=1` 藏界面；`&still=1` 停掉动画循环，只在 `window.__still()` 时画一帧并返回 PNG（无头截图靠它，软件渲染一帧 1–4 秒）。`window.__applyShot(s)` 换机位不重载。
- 第 2 轮拆模块后加 `&only=a,b`（只建这些模块），供单模块自查。
- 沙箱是软件渲染（SwiftShader）：**只看样子，不报帧率**。帧率和卡顿在主人的 Mac 上测。
- 并行时每个代理用自己的 `--out` 目录，别互相覆盖。

## 2. 拆分方式（第 2 轮第一步，由 core 一人做完再开并行）

现在整个渲染器是一个 `3d.html`（约 150 行）。第 2 轮先把它拆成零构建的 ES 模块，放在 `docs/living/nodes/nangang/3d/`：

```
3d.html            壳：importmap、界面、读参数，调 core
3d/core.js         渲染器、相机、机位钩子、数据载入、年份重建循环、共享工具、注册表
3d/terrain.js  3d/water.js  3d/sky.js  3d/buildings.js  3d/streets.js  3d/props.js  3d/flora.js  3d/crowd.js
```

每个模块导出：

```js
export const name = 'water';
export function build(ctx) { … }          // 按 ctx.year 把自己那份东西加进 ctx.scene；年份变了会再调一次
export function dispose(ctx) { … }        // 年份重建前清掉自己加的东西
export const checkShot = 1;               // 自查用哪个机位（见下表）
```

`ctx` 由 core 提供：`scene, camera, renderer, WD`（nodes.json）、`year, live(f), elevPx(x,z), ground(x,z), hsh(n,k)`、
`reg`（共享注册表，生产者写、消费者读，如 `reg.frontage`、`reg.slots.fountain`）、`quality`（preview/high）。

**拆分验收（不变量）**：拆完用同一套工具重渲 4 个机位，`compare.py` 的数字和 `baseline/stats.json` 里 render 一侧对得上
（每个机位 |ΔL*| < 1，边缘密度相差 < 5%）。对不上就是拆坏了，不准开并行。

## 3. 模块表

| 模块 | 文件 | 从底账/节点读什么 | 可以动 | 不准动 | 自查机位 |
|---|---|---|---|---|---|
| core（导演） | `3d.html`、`3d/core.js`、`shots.json` | 全部（只载入，不解释） | 渲染循环、相机、钩子、注册表、`shots.json` | 任何模块的内容 | 全部 4 个 |
| terrain | `3d/terrain.js` | `WD.elev`、`land`、`bands`；城外地形（`data/elev_grid20.json`、`data/land.geojson`） | 高程网格、海岸、区外陆地和远岸（地平线不能是空的海）、地面底色 | 街面图层（归 streets）、水面 | 3（再看 1 的地平线） |
| water | `3d/water.js` | `water`（sea / harbor）、`mole` | 海面、港池水、岸线湿痕、倒影/高光、浪 | 石堤和栈桥的几何（归 props/buildings 见下）、地形 | 1 |
| sky-atmosphere | `3d/sky.js` | 无（只读机位里的时间设定） | 太阳方向/颜色、天光、天空穹、雾/空气透视、阴影参数、色调映射、调色 | 任何物体的反照率（材质归各自模块） | 全部 4 个的全局统计；主看 1 |
| buildings | `3d/buildings.js`（可再分 `3d/arch/`） | `house`（p、ht、fn、id、y0/y1）、`landmark`、`aqueduct`、`mole`、`pier` 的几何；`reg.frontage` | 墙、屋顶、门窗、砖带、柱廊（沿 `m`/`s` 街的铺面才有）、地标部件、水道桥、石堤和栈桥 | 房子的位置/占地/高度/年份（底账给的，只能照用）；街面 | 2、4（再看 1） |
| streets | `3d/streets.js` | `street`（k=m/s/c/l、w）、`landmark` 地皮、`nodes_net.json` | 街面铺装（石板、缝、车辙、路缘）、广场铺地、喷泉/井/路牌等街具、写 `reg.frontage`（哪户面向哪条街） | 房子、地形高程 | 2 |
| props | `3d/props.js` | `pier`、`landmark`（granary）、`house.fn`（market、dock） | 船（每个泊位）、吊车、麻袋/双耳罐堆、手推车、摊位、遮阳布 | 房子、街面、人 | 4（再看 1） |
| flora | `3d/flora.js` | `trees`（olive/cypress/garden、年份、大小） | 柏、橄榄、园子的树形和颜色 | 树的位置/种类/年份（底账给的） | 3 |
| crowd | `3d/crowd.js` | `crowd.json`、`folk_h.json`、`people.json`；复用 `docs/living/nodes/people/` 的 `crowd.js`、`pose.js` | 把长卷已有的人群接进 3D、按机位定近景关节人/远景柱的档 | 人的身份、路线、日程（由 `tools/cs/people/` 从底账推，模块只演） | 2、4 |

共享规则：
- 只改自己的文件。要别人的模块改东西，写在交付报告里，不要直接改。
- 共享文件（`3d/core.js`、`shots.json`）只有 core 能改；别的模块只能在注册表里加新键。
- 确定性：同一份代码 + 同一个年份 = 同一张图。随机数一律用 `ctx.hsh(id, k)` 或带种子的 RNG，不用 `Math.random`、不用时间。
- 不引外部资源：不用 CDN、不下载贴图/模型；画布贴图在代码里画（≤ 2048²）。全部相对路径。
- 底账优先：参考图里有而底账没有的（例如教堂），不画；底账有而参考图没拍到的，照样建。

## 4. 预算（全部模块加起来，在主人 Mac M4 上测，1376×768）

- 4 个机位都 ≥ 60 fps，最差一帧 ≤ 25 ms。
- draw call ≤ 1500，三角形 ≤ 3 M（`quality=high`）；重复物（窗、柱、瓦、船、人、树）一律 InstancedMesh 或合并几何。
- 年份重建 ≤ 1.5 s；每个模块在控制台打出自己的 build 毫秒和三角形数。
- 远处要便宜：近/中/远三档（同 WorldGacha 的 near/far/horizon），机位已知，按到机位的距离降级。

## 5. 每个模块代理的一轮怎么跑

1. 读 `ART_BIBLE.md` 里自己相关的段落，打开参考图和 `baseline/cmp_shotN.jpg` 看差距。
2. 动手前把本轮的验收数字写进提交说明（来自 `baseline/report.md` 第 4 节），动手后不改。
3. 改 → `render.py --shot <自查机位>` → `compare.py` → 看并排图 → 再改。先看图，再看数字。
4. 交付前跑全部 4 个机位，确认没有把别的机位弄坏（别的模块那几带的数字不能变差超过 5%）。
5. 提交：第一行写镜头 + 署名「——Hark（CS线）」；正文三行：为什么 / 动了什么不变量 / 怎么证明（贴 compare 的前后数字和并排图路径）。帧率留给主人 Mac 测，在 NOW.md 里写「待 Mac 实测」。
