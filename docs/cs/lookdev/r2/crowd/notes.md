# crowd · lookdev 第 2 轮（——Hark（CS线）2026-10-20，基于 3df0d79，streets 已合入）

**做了什么**：`3d/crowd.js` 从空壳变成把长卷人群接进 3D：载入 `crowd.json`（folk.py 从底账房子推出的 5966 口人：户籍、关系、路线），
用 `docs/living/nodes/people/crowd.js` + `pose.js` 原样演（import，不改）；转接写在 `3d/crowd/stage.js`：
- 部件改走 `ctx.add`、投影；人站在 `ctx.ground`（3D 地形网格）上，再加 streets 的铺面抬高（车道 +0.11 px、主街人行道再 +0.2 px 路缘，
  每次重建按当年的街和 `reg.frontage` 画一张 1 px 一格的抬高图，人脚不陷进人行道；读不到 frontage 就只有车道）。
- EX=1：房子不做竖向夸张，人也不夸张，人眼高机位才和人头一样高。
- 近处 100 m 内关节人（上限 200），远处着色小柱，400 m 外不算不画（给引擎一台远裁剪面收短的影子相机）；帧图小人（长卷斜俯专用）不建。
- 时钟锚在 people.json「正午」段的 930 s（930 是在正午段里按机位 2 主街人数挑的：主街 400 m 内 72 人，T/2=1066 时 60 人；`?crowdT=` 可改）。
  still 模式同一刻摆两遍（引擎「碰见熟人打招呼」读上一帧近处名单）→ 单拍机位 2 与 4 机位连拍逐像素相同。
- 只有 `ctx.year === crowd.json.year`（60）才出人：人群是第 60 年户籍推的，别的年份不出，免得和底账打架。
- 指到才出签（主人定）：非 still 模式下鼠标停在人头附近 28 px → 小签（谁、此刻在干什么、一句家事），不指不算。已用 `__crowd.tipAt` 验过（例：「巴尔巴拉，格里高利家的母亲 / 回娘家看看，去科斯马斯家」）。

**验收（动手前定）**：机位 2 ≥ 60 人可见、全部来自 crowd.json；主人 Mac 上 ≥ 60 fps（这里只报 CPU 毫秒）。
- 机位 2 可见（未遮挡 = 开/关人群两帧在人的躯干/头处像素不同）：任意大小 111、≥3 px 高 104、≥6 px 高 39、≥20 px 高 11；全部是 crowd.json 的人。
  → **按「看得见」算达标（104 ≥ 60）；按「≥6 px 认得出是人」算没达标（39）**。主街这一段底账推出来的路线就这么多（400 m 内 60–75 人，看时刻），没有加人。
- 每帧 CPU（crowd tick：5966 人位置 + 姿势 + 实例矩阵 + 铺面高度，机位 2：16–23 关节人 + ~370 柱）：沙箱最小 2.3 ms、p10 3.3 ms、中位 7.7 ms
  （2 核、别的代理把负载压到 ~9，最小值最接近真实）。M4 估计 ~1–1.5 ms，**未实测**。
- GPU：约 24 次实例绘制（+ 阴影一遍），机位 2 人群三角形 ~1.9–2.3 万；上限（200 关节人）约 16 万。
- 重建：crowd build 沙箱 ~260 ms，其中抬高图 ~130–320 ms（负载不同）。
- 带（对同 HEAD 关掉人群的渲染）：机位 2 buildings+crowd 边缘 0.046 → 0.054；机位 4 props+crowd+water 不变（0.012）——码头那段 crowd.json 没有路线（见下）。
- `match.py --skip crowd`（对同 HEAD 关掉人群）：MATCH（`match.txt`）。对 baseline/stats.json 只有 streets 自己那两带动（streets 的提交），不是 crowd。check_docs / check_flags 通过。

**要别人改的**：
- core：`__modStats.crowd.tris` 在 build 时（机位还没套上）数，人群是每帧变的实例数，这个数是 0；按机位的数在 `window.__crowdStats`。建议 core 在 `__still()` 后再数一遍。
- tools/cs/people（folk.py）：机位 4（粮仓码头）要搬运工，得给粮仓/栈桥推出「扛活」路线；本模块不新写人。
- streets：铺面剖面（PROF）现在在 crowd 里抄了一份数（车道 .11/.08/.06/.04、路缘 .2/.13）；若 streets 把「某点铺面高度」写进 `reg`（如 `reg.paveY(x,z)`），crowd 就改读它。
- 机位 1 / 3 的人在 340 m+ 外只有 1–3 px，不靠人群出效果。

**文件**：`sbs_shot2.jpg`（前后并排 + 局部放大）、`cmp_shot2.jpg`、`cmp_shot4.jpg`、`stats.json`、`match.txt`、`numbers.json`、`probe_all.json`、`probe_shot2_bench.json`、`probe.py`（计数 + CPU 探针）。
URL 调参（默认不用）：`?crowdT=` `?crowdFull=` `?crowdMaxFull=` `?crowdFar=` `?crowdN=`。
