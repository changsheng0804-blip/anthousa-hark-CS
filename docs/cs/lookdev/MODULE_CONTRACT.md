# 南港 3D · 模块契约（lookdev 第 1 轮定稿，第 2 轮第 0 步拆分后更新）

> 读这页再动 `docs/living/nodes/nangang/3d.html` 和 `docs/living/nodes/nangang/3d/`。谁能改哪个文件见第 6 节。美术目标见 `ART_BIBLE.md`，差距排名见 `baseline/report.md`。
> 方向不变：**底账 → 节点 → 渲染器**。模块是渲染器的零件：AI 写生成器和部件（代码），不画内容（图）。
> ——Hark（CS线）2026-10-20

## 1. 工具（每个模块代理都用同一套）

```bash
# 仓库根目录。沙箱里先设好 chrome（主人 Mac 上不用设，playwright 自带 chromium 即可）
export LOOKDEV_CHROME=…/chrome-headless-shell  LOOKDEV_LIBS=…  LOOKDEV_PYLIB=…   # 可选
python3 tools/cs/lookdev/render.py --out /tmp/me            # 4 个机位 → /tmp/me/shotN.png
python3 tools/cs/lookdev/render.py --shot 2 --out /tmp/me --param "only=buildings,streets"
python3 tools/cs/lookdev/compare.py --renders /tmp/me --out /tmp/me   # cmp_shotN.jpg + stats.json + 排名
python3 tools/cs/lookdev/match.py --renders /tmp/me --skip water      # 别人的带没被我弄坏（|ΔL*|<1、边缘差<5%）
# 地标（2026-10-20 起）：比形。lmmask 渲染 = landmarks 模块的材质全换品红
python3 tools/cs/lookdev/render.py --shot 5 --out /tmp/lm_mask --param "only=landmarks&lmmask=1"
python3 tools/cs/lookdev/silhouette.py --ref-mask docs/cs/lookdev/landmarks/column/refs/ref1_mask.png --render /tmp/lm_mask/shot5.png --out /tmp/lm/sil \
    --ref-img docs/cs/lookdev/landmarks/column/refs/ref1_hero.jpg --render-img /tmp/me/shot5.png   # IoU、高宽比、四段高度占比、蒙版内颜色
```

- 页面钩子（不带参数时页面完全不变）：`3d.html?shot=N` 套用 `shots.json` 的机位；`&clean=1` 藏界面；`&still=1` 停掉动画循环，只在 `window.__still()` 时画一帧并返回 PNG（无头截图靠它，软件渲染一帧 1–4 秒）。`window.__applyShot(s)` 换机位不重载。
- `&only=a,b`：只建这些模块（单模块自查）。**sky 和 terrain 总是开着**（灯、地面贴图都在它们身上）；不带 water 就没有海面平面，背景色露出来，这是正常的。
- `&quality=preview|high`（默认 high）放进 `ctx.quality`，模块自己决定怎么降级。
- 控制台 `[3d] build …` 一行、`window.__modStats` 给每个模块的 paint/build 毫秒和三角形数（按 `ctx.add` 加进去的物体数）；`window.__ctx` 是 ctx。
- 沙箱是软件渲染（SwiftShader）：**只看样子，不报帧率**。帧率和卡顿在主人的 Mac 上测。
- 并行时每个代理用自己的 `--out` 目录，别互相覆盖。

## 2. 拆分方式（第 2 轮第 0 步已做完，2026-10-20）

`3d.html` 只剩壳（界面、importmap、`<script type="module" src="3d/core.js">`）。渲染器全部在 `docs/living/nodes/nangang/3d/`：

```
3d.html            壳：样式、年份滑条、importmap，载入 3d/core.js
3d/core.js         渲染器、相机、MapControls、数据载入（nodes.json）、高程 elevPx、水陆蒙版 + ground()、地面贴图画布、
                   年份重建循环、机位钩子（?shot ?clean ?still ?only、__applyShot、__still、__setYear、__view）、注册表、共享几何工具
3d/sky.js          天空底色、雾、天光、太阳 + 阴影
3d/terrain.js      地面贴图底层（海色底、陆地、沙岸、等高带）+ 高程网格（披 core 的地面贴图）
3d/water.js        海面平面；地面贴图上的港池水色、港池岸线、石堤地皮
3d/streets.js      地面贴图上的街（m/s/c/l）和地标地皮
3d/buildings.js    房子（合并网格）、地标部件（占位方块）、栈桥、石堤立体
3d/landmarks/      史诗/特殊公共建筑，一座一个文件（2026-10-20 起；index.js 是模块壳，column.js 第一座、nymphaeum.js 第二座，kit/ 是部件）
3d/props.js        空壳
3d/flora.js        树（柏 = 锥、橄榄 = 球，实例网格）
3d/crowd.js        空壳
```

每个模块导出（`init`、`paint`、`tick` 可选）：

```js
export const name = 'water';
export const checkShot = 1;               // 主自查机位（副机位见第 3 节表）
export function init(ctx) { … }           // 只调一次：建材质、常驻网格、灯
export function paint(ctx, X) { … }       // 每次重建：往共享地面贴图画自己那层（X 是 2D 画布，坐标 = 页面像素；core 每层前后 save/restore）
export function build(ctx) { … }          // 每次重建：按 ctx.year 加东西，一律 ctx.add(obj)
export function dispose(ctx) { … }        // 每次重建前：清掉上次 build 加的（scene.remove + geometry.dispose）
export function tick(ctx, t) { … }        // 每帧；still 模式只在 __still() 时调，t = 机位的 t（默认 0），保证同图
```

顺序（init / paint / build / tick 全按这个）：**sky → terrain → water → streets → buildings → landmarks → props → flora → crowd**。
重建一次 = 清空 `ctx.reg` → 各模块 dispose → 各模块 paint（地面贴图）→ core 算水陆蒙版 → 各模块 build → 贴图标脏。

`ctx`：`THREE, scene, camera, renderer, controls, WD`（nodes.json）、`by`（按 t 分好的要素）、`W, H, year, live(f), elevPx(x,z), ground(x,z), hsh(n,k)`、
`geom: {quadAxes, rectOf, RQ, pathRings}`、`groundCanvas, groundTex, groundScale`、`reg`（共享注册表）、`quality, QS, time`、`add(obj)`、`only, modules`。

**拆分验收（不变量，已过）**：同一套工具重渲 4 个机位，`tools/cs/lookdev/match.py` 对 `baseline/stats.json` 的 render 一侧：
4 个机位全局 + 12 条带 ΔL* 全是 +0.00、边缘密度差全是 +0.0%（和单文件版逐像素比，每通道平均差 ≤ 0.001（0–255 标度），只有零星几个像素不同）。
年份来回拨（60→20→60）再拍机位 4，和直接拍逐像素相同。证据：`r2/split_match.json`。

## 3. 模块表

| 模块 | 文件 | 从底账/节点读什么 | 可以动 | 不准动 | 自查机位 |
|---|---|---|---|---|---|
| core（导演） | `3d.html`、`3d/core.js`、`shots.json` | 全部（只载入，不解释） | 渲染循环、相机、钩子、注册表、水陆蒙版、地面贴图画布、`shots.json` | 任何模块的内容 | 全部 4 个 |
| terrain | `3d/terrain.js` | `WD.elev`、`land`、`bands`；城外地形（`data/elev_grid20.json`、`data/land.geojson`） | 高程网格、海岸、区外陆地和远岸（地平线不能是空的海）、地面底色 | 街面图层（归 streets）、水面 | 3（再看 1 的地平线） |
| water | `3d/water.js` | `water`（sea / harbor）、`mole` | 海面、港池水、岸线湿痕、倒影/高光、浪 | 石堤和栈桥的几何（归 props/buildings 见下）、地形 | 1 |
| sky-atmosphere | `3d/sky.js` | 无（只读机位里的时间设定） | 太阳方向/颜色、天光、天空穹、雾/空气透视、阴影参数、色调映射、调色 | 任何物体的反照率（材质归各自模块） | 全部 4 个的全局统计；主看 1 |
| buildings | `3d/buildings.js`（可再分 `3d/arch/`） | `house`（p、ht、fn、id、y0/y1）、`landmark`、`aqueduct`、`mole`、`pier` 的几何；`reg.frontage` | 墙、屋顶、门窗、砖带、柱廊（沿 `m`/`s` 街的铺面才有）、地标部件、水道桥、石堤和栈桥 | 房子的位置/占地/高度/年份（底账给的，只能照用）；街面 | 2、4（再看 1） |
| streets | `3d/streets.js` | `street`（k=m/s/c/l、w）、`landmark` 地皮、`nodes_net.json` | 街面铺装（石板、缝、车辙、路缘）、广场铺地、喷泉/井/路牌等街具、写 `reg.frontage`（哪户面向哪条街） | 房子、地形高程 | 2 |
| props | `3d/props.js` | `pier`、`landmark`（granary）、`house.fn`（market、dock） | 船（每个泊位）、吊车、麻袋/双耳罐堆、手推车、摊位、遮阳布 | 房子、街面、人 | 4（再看 1） |
| flora | `3d/flora.js` | `trees`（olive/cypress/garden、年份、大小） | 柏、橄榄、园子的树形和颜色 | 树的位置/种类/年份（底账给的） | 3 |
| landmarks | `3d/landmarks/index.js` + 一座一个文件（`3d/landmarks/column.js`…）+ `3d/landmarks/kit/` | `landmark`（id、g、y0/y1、seed）；底账的 phases（`proposals/`，按年份画施工中） | 自己接手的那几座地标的全部几何、材质、贴图、烘焙网格、LOD；`?lmmask=1` 蒙版 | 地标的位置/年份（底账给的）；没接手的地标（还归 buildings）；广场柱廊、地皮 | 5、6（再看 1） |
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

## 6. 第 1 波：谁能改哪个文件（2026-10-20 定，拆分后生效）

路径都相对 `docs/living/nodes/nangang/`。「新文件」= 可以在自己的子目录里新建任意 `.js`，由自己的模块文件 import（相对路径 `./xxx/…`）。

| 代理 | 只能改 / 新建 | 自查渲染（单机位） | 交付前全量 |
|---|---|---|---|
| sky-atmosphere | `3d/sky.js`、新文件放 `3d/sky/` | `render.py --shot 1 --out /tmp/sky` | 4 机位，`match.py --skip sky`（它管全局光，别的带 L* 必然变，只看边缘） |
| terrain | `3d/terrain.js`、`3d/terrain/` | `render.py --shot 3 --out /tmp/terrain --param only=terrain` | 4 机位，`match.py --skip terrain` |
| water | `3d/water.js`、`3d/water/` | `render.py --shot 1 --out /tmp/water --param only=water` | 4 机位，`match.py --skip water` |
| streets | `3d/streets.js`、`3d/streets/` | `render.py --shot 2 --out /tmp/streets --param only=streets` | 4 机位，`match.py --skip streets` |
| buildings | `3d/buildings.js`、`3d/arch/` | `render.py --shot 4 --out /tmp/bld --param only=buildings`（再 `--shot 1`） | 4 机位，`match.py --skip buildings` |
| props + flora | `3d/props.js`、`3d/flora.js`、`3d/props/` | `render.py --shot 4 --out /tmp/props --param only=props,flora,buildings,water`（船要有码头和水才看得懂） | 4 机位，`match.py --skip props,flora` |
| landmarks | `3d/landmarks/` 下全部；接手一座时可以删 `3d/buildings.js` 里那一座的占位（一行，注释写清）；烘焙脚本放 `tools/cs/landmarks/` | `render.py --shot 5 --out /tmp/lm` + `--param "only=landmarks&lmmask=1"` 出蒙版 | 4 机位 `match.py --against <改前渲染>`：只允许地标所在的像素变；机位 5 用 `silhouette.py` |
| crowd | `3d/crowd.js`、`3d/crowd/`；可以 import `docs/living/nodes/people/crowd.js`、`pose.js`（在 `3d/crowd.js` 里写 `../../people/crowd.js`），**不准改**（长卷也在用） | `render.py --shot 2 --out /tmp/crowd --param only=crowd,buildings,streets` | 4 机位，`match.py --skip crowd` |

只有 core（导演）能改：`3d.html`、`3d/core.js`、`shots.json`、`nodes.json` 及其他数据、`tools/cs/lookdev/` 下的工具、
`docs/cs/lookdev/` 下的 `ART_BIBLE.md`、本页、`baseline/`、根目录 `NOW.md`。

单机位自查之后，`compare.py --renders /tmp/xxx --out /tmp/xxx` 只比有图的机位（缺的跳过）。注意：自查时 `only=` 关掉了别的模块，
**数字只能拿来看自己那一带的边缘和饱和**；交付验收数字一律用不带 `only` 的全量渲染。

每个代理的证据放 `docs/cs/lookdev/r2/<模块名>/`（`cmp_shotN.jpg`、`stats.json`、`match.json`、一页 `README.md` 写本轮做了什么和数字）。
第 1 波代理不改 `NOW.md`（7 个代理同时覆盖会互相冲掉）；现状写进自己的 `r2/<模块名>/README.md`，导演合并时统一更新 `NOW.md`。

### 并行时的坑（第 0 步拆的时候看到的）

1. **地面贴图是一张共享画布**。terrain 先画底（会整张填海色），water 再画港池/石堤地皮，streets 最后画街和地标地皮，后画的盖前画的。
   除 terrain 外谁都不要整张清画布。画布 = 页面像素 × `ctx.groundScale`（现在 2，即 3640×4096）。街面要更细的纹理，streets 用自己的贴图/网格叠上去，不要改画布尺寸（core 的事）。
2. **水陆蒙版和 `ground()` 归 core**：陆地 + 当年石堤 = 地，当年港池 = 水。water 和 terrain 都不能各自改「哪里是水」，要改请 core。
3. **材质不共享**。每个模块自己建自己的材质。buildings 里有一个 `mats.water`（宁芙殿水池）和石堤的石头材质，它们归 buildings，不归 water。
4. **灯只在 sky 里**。别的模块要太阳方向读 `ctx.reg.sun`（DirectionalLight），不要再加灯。阴影相机现在只罩住区中心 ±1500 像素；terrain 把陆地铺到区外，远处不会有投影，要扩阴影范围请 sky。
5. **色调映射/曝光/雾归 sky**，改它们会让所有模块的 L* 一起动——所以只有 sky 追 L*，别的模块追边缘和饱和（见 `baseline/report.md` 第 4 节）。sky 合进来以后，别的模块的 L* 会整体移位，这不算谁弄坏了。
6. **相机近/远裁剪面归 core**（near 2、far 16000——r2 合并时由 9000 提上来，远岸环和雾都跟着 far 走）。terrain 要更远的远岸、雾更远，先在报告里提给 core。
7. **注册表每次重建前清空**，所以 `reg` 要在 build 里写，不要在 init 里写。streets 在 buildings 之前 build，`reg.frontage` 由 streets 写、buildings 读——**第 0 步还没写 frontage**，buildings 代理在它出现前要能照常跑（读不到就当没有铺面）。
8. **一律用 `ctx.add(obj)` 加东西**（core 靠它按模块数三角形），dispose 里自己 `scene.remove` 并 `geometry.dispose()`；常驻物（init 里加的）不用每次清。
9. **确定性**：随机用 `ctx.hsh(id,k)`；动的东西（浪、人走）放 `tick(ctx,t)`，still 模式下 t 固定，同代码同机位同图。
10. **模块只用相对路径 import**（`'three'` 走页面的 importmap，`three/addons/…` 也行）；不引 CDN、不下载贴图。
11. **git**：只 `git add` 自己的文件；推之前 `git pull --rebase`（古城线的另一个会话也在推这个仓库，别碰它的文件）。沙箱里 HTTPS fetch 常 502，重试即可。
12. **沙箱渲染慢**：软件渲染一帧 1–4 秒，`render.py` 全 4 机位约 20 秒（载入 ~2 秒 + 重建 ~1.6 秒）。沙箱 chrome 用 `LOOKDEV_CHROME`/`LOOKDEV_LIBS`/`LOOKDEV_PYLIB` 指路（见第 1 节）。
13. **落地（2026-10-20 r3_ground_scale，主人「地面穿模明显」）**：凡是站在地上的东西，一律按 `ctx.groundMesh(x,z)`（terrain 网格同样的 4 px 三角插值；页面框外用 terrain/outer.js 的 `heightAt`，经 `reg.outerY`）落地，不用 `elevPx`、不用光滑的 `ground()`。
    有占地的（房子、地标部件、粮仓长仓、柱廊段）用 `ctx.footing(四角)` → `{min,max,mid}`：**地坪 = max**（墙、柱从这里起，底账的 ht 从这里量；民居取 max(mid, max−0.45)），**台基 / 墙基伸到 min − 0.6**（地标是石色、顶下两级台阶，民居是素面墙基），再 `ctx.foot({kind,id,pts,bottom,floor})` 登记。
    验收：`python3 tools/cs/lookdev/ground_check.py --year 65`（独立按网格采样，报每类「漏空 > 0.5 px / 埋 > 0.5 px」的个数），不得比上一版多。

## 7. landmarks：史诗/特殊公共建筑，一座一座按 Athenaion 的做法（2026-10-20 试点：纪功柱）

主人 10-20：帧率 Mac 上够（60–90 fps），3D 样子可以接受；史诗级 / 特殊的公共建筑用这个方法逐座做。第一座 = 南港狄奥多西广场的纪功柱（机位 5），证据在 `docs/cs/lookdev/landmarks/column/`；第二座 = 大宁芙殿（机位 6），证据在 `docs/cs/lookdev/landmarks/nymphaeum/`（`notes.md` 都写了底账事实、假设、4 轮数字）。

**钩子（唯一的一处）**：`3d/core.js` 的 `MODULES` 在 buildings 后面多一项 `landmarks`（`3d/landmarks/index.js`）。index.js 按地标 id 把 `ctx.by.landmark` 分给各自的文件；没有文件的地标照旧由 buildings 画占位。接手一座 = 新文件 + `LM` 列表加一项 + 删 buildings 里那一座的占位（同一次提交）。

**一座地标的文件**（`3d/landmarks/<名字>.js`）导出 `id`、`init(ctx)`（材质、画布贴图，只一次）、`build(ctx, f, r, b, F)` → Object3D 或 null（`r = rectOf(f.g)`、`b = 占地下最高的网格地面`（r3 起；之前是 elevPx(中心)+1.6）、`F = ctx.footing(占地)` 给台基往下伸）、`stats()`（近/远三角形、建造毫秒）；可选 `footprint(r)`（占地，默认底账矩形）、`bottomOf(b,F)`（最低面，给 ground_check）、`HERO_SCALE`。
年份照底账：nodes.json 只有 y0/y1，细的阶段（施工、完工）读 `proposals/` 的 phases，写成文件里的常量并注明出处。

**配方（每座照走一遍）**
1. 底账：在 `nodes.json`、`proposals/`、`chronicle/` 里找这座的 id、位置、年份、阶段；史料补形制（尺寸、材料、装饰），每条写出处；底账没说的写成「假设」。
2. 参考图 3 张（`generate_image`）：主机位人眼高（把占位渲染图当构图参考喂进去，参考才和机位对得上）、3/4 近景细部、远景天际线；光照 ART_BIBLE（低暖太阳从左）；禁教堂/十字/现代物。存 `docs/cs/lookdev/landmarks/<名字>/refs/`。逐张看，有违规就重生成。
3. 参考蒙版：天空背景的部分按行估背景色自动抠，被背景压住的部分按放大网格量边、手写多边形；存 `refs/ref1_mask.png`，叠在参考上看一遍。
4. 机位：`shots.json` 加一个（core 允许的最小改动），用页面里的投影反算 fov/俯仰，让地标在画面里的上下边和参考一致；带 = 天空/地标/背景。
5. 建：剖面（`kit/lathe.js`）→ 线脚和旋转体；浮雕（`kit/relief.js`）→ 法线 + 反照率；装饰件（`kit/acanthus.js` 一类参数曲面）；雕像/不规则体 → SDF + marching cubes 离线烘焙（`tools/cs/landmarks/bake_*.py`，浏览器里现算 > 300 ms 就烘焙）；`THREE.LOD` 近/远两档；`?lmmask=1` 蒙版。
6. 比（≤ 4 轮）：`render.py` 主机位 + 全 4 机位；`compare.py` 颜色；`silhouette.py` 形；每轮 `read_file` 看并排图，先修形（比例、机位），再修材质（反照率、浮雕对比）。
   远看浮雕浅时先上真几何（纪功柱：`column.js` 的 `helixBand` 螺旋凸棱、基座画框真凹 0.12 m），再加法线/AO；受光面亮在地标反照率里压，不动 sky / 全局光（10-20 修订）。
7. 交付：`match.py --against <改前>` 证明别的机位只有地标像素变；证据（并排、numbers.json、notes.md、overview.jpg）进 `docs/cs/lookdev/landmarks/<名字>/`；`docs/living/next/` 加链接；NOW.md 覆盖对应一段。

**史诗夸张（主人 10-20 认可：「这个史诗城市里，地标要放大一些做对比，尤其大的史诗建筑」）**
- 每座地标文件一个常量 `HERO_SCALE`（默认 1.4），**只放大高（和跟着高走的细部）；占地照底账，不动**。纪功柱整座等比 ×1.4（51.95 → 72.7 m，柱径一起放大，不变细；台阶外沿 7.0 → 9.8 m，仍在广场院子里）；宁芙殿台基顶以上的高 ×1.4、神龛 / 壁龛 / 柱子宽粗 ×`HERO_W` 1.2、雕像 ×1.4，弦长、塔的平面不动（22.2 → 30.5 m）。
- buildings 里还在画的地标部件（`buildings.js` 的 `LM_SCALE`）：广场柱廊和粮仓的高 ×1.2（柱廊 8 → 9.6 px，粮仓 15.5–18 → 18.6–21.6 px）；蓄水池、孤寡院不放大。
- 这是有意的夸张，不是史料：notes 里的「史料尺寸」照旧按实际写，模型 = 史料 × HERO_SCALE。地标周围的屋脊线（半径 180 px 内民居屋顶中位数 ≈ 8 px）是对比的尺子，数字见 `docs/cs/lookdev/r3_ground_scale/numbers.json`。
- 新地标照这个做；机位 5、6 已按放大后的高重新对准（`shots.json` 的 `r3_note`），轮廓 IoU 不再是目标。

**第二座（宁芙殿）补的经验（10-20）**
- 机位先找开阔处：地标多半被房子围着。先用 nodes.json 的房子多边形 + 高度做一遍视线遮挡粗算（几十个候选点，只要几秒），再渲 4–5 个候选看图。**近端 / 远端到相机的距离比要接近参考**（宁芙殿参考约 1.4，太近时 2.0 → 近塔冲出画面、高宽比大一截）；退不出去就接受，在 notes 里写。fov / 俯仰按 lmmask 包围盒反算两轮就收敛（俯仰的号别弄反：内容偏下 → 俯仰减小）。
- 立面背光（sky 的太阳在方位 300°、高 14°，朝南的立面全在阴面）时，**在地标材质里加按世界法线的天光补光**（`nymphaeum.js` 的 `withFill`：onBeforeCompile 在 opaque_fragment 前加 `反照率 × 补光色 × (底量 + max(N·L_fill, 0))`，乘壁龛 AO，不吃阴影），柱子和线脚才有体积；唯一整片受光的面（塔的西面）单独压反照率。sky / 全局光不动。
- 宽地标比形只看 `silhouette.py` 的 `iou_bbox_aligned` 和 `h_to_w`：它的四段分法是给柱子写的；`iou_height_aligned` 的画布 400 宽，宽地标会被裁（要用请 core 放宽）。占位的「改前蒙版」= 改前 / 改后 `only=buildings` 渲染之差。
- **改前 / 改后都整套机位一次渲完**（`render.py` 默认 all）：water 的倒影随渲染顺序变，单机位分开渲，机位 4 港水会差几千像素，和地标无关。
- 删 buildings 占位时，如果占位往 `ctx._cols` 推过柱子，**留同样数量的零高度空实例**（`[x,b,z,0,0]`），后面广场柱廊的序号（柱子色差 `hsh(i,77)`）才不变；否则机位 5 的广场柱子整排变色。
- 弯的 / 折的立面：每个折面一个立面坐标矩阵 (s, y, d)，墙面用 `ShapeGeometry` 挖拱形龛口；檐部、台基、池栏用沿折线扫剖面（`nymphaeum.js` 的 `sweep`，斜接、实体在走向左边三角形就朝外）——下一座要用就搬进 `kit/`。几十个茛苕叶柱头会到 20 万三角形，立面柱子一律 `corinthian(lod:'far')`。
- 水：water 模块的材质没导出、倒影只对 y=0 的海面，池水用地标自己的 MeshPhong + onBeforeCompile（细浪法线 + 菲涅尔天光），水帘 = 抛物线带 + alpha 竖条，`tick(t)` 滚贴图；`index.js` 已把 tick 转给地标。

**第三座（狄奥多西广场，10-20）补的经验**：一个地标 id 可以挂几个文件（`index.js` 的 `BY[id]` 是列表：纪功柱 `column.js` + 广场 `forum.js`）；占地大、跨坡的地标导出 `selfFoot = true`，自己按 ≤ 30 px 分段 `ctx.footing` / `ctx.foot`，`index.js` 不替它按整块算 b；`__landmarkStats` 的键用文件的 `key`。
实例柱放在世界坐标时设 `frustumCulled = false`（网格本体在原点，默认包围球会把整排裁掉）；`ExtrudeGeometry` 搬进别的坐标架后按 (t, up, n) 的手性翻绕序，再 `computeVertexNormals`；贴地的施工土要比 streets 的 polygonOffset（广场 −5）更狠。证据在 `docs/cs/lookdev/landmarks/forum/`。

**可以复用的部件**：`kit/lathe.js`（lathe / squareLathe / merge / box）、`kit/relief.js`（relief（`aoMin` 凹缝最暗、`low` 地压暗、`patina` 暖色风化；默认同旧）+ soldier / captive / victory / garland / frame / ell / poly / line / rect）、`kit/acanthus.js`（corinthian，近/远）、`kit/baked.js`（读烘焙网格）、`kit/fill.js`（地标材质的天光补光，宁芙殿 withFill 的通用版）、`kit/club.js`（棍棒 / 树干柱 + 握拳）、`tools/cs/landmarks/bake_statue.py`（SDF 原语 + 平滑并 + marching cubes + 量化写盘的模板）、`tools/cs/landmarks/bake_nymph_statues.py`（同一套原语出 3 种站姿女像：顶罐、披袍、捧贝，近 / 远两档）、`tools/cs/lookdev/silhouette.py`。
