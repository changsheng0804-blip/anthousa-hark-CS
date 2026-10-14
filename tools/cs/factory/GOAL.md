# CS 线 · /goal 3：同一座安托萨（时间轴接编年史 + 吃上游地标规格）

所有者 2026-10-13 20:54 PT 说「可以」开跑。方向是他定的：瓦片是「镜头」，上游安托萨是「内容」。瓦片页要变成同一座城的入口，不能是另立的第二座城。上一个 goal（全城推到门口，13 轮全部达标，所有者说「效果已经很不错了」）归档在 GOAL_v2.md，再上一个在 GOAL_v1.md。心跳 199cc52e 是兜底：/goal 跑的时候暂停，停了以后恢复。

页面：docs/living/tiles/index.html。

## 目标（全部达标才算完）
- H1 并上游：合并 origin/main 上新的 8 个提交（v24–v30 房子系统 P1–P3、地标规格卡、3D 管线 c72b1f3）。底账以上游为准；CS 线的块和页面都保留；冲突一处一处解，每处写一行理由，记进 CS_LINE.md。并完以后，九块 accept.py 全过（底账落后上游那一条也转绿），check_tiles.js errors 0，xerolophos 页（干山）照样能打开、链路通。
- H2 地标只有一个来源：瓦片的地标位置、轮廓、建成年和阶段，一律从上游 tools/landmark_registry.py 和 tools/landmarks/*.json 读，CS 线这边不再自己维护一份清单。AI 只负责画风格精灵。写 check_landmark_src：上游规格里每一座地标在瓦片里都有，位置差 ≤ 8 像素，各年份的阶段对得上；CS 线自己多出来的地标，要么能在上游找到对应，要么列进「待上游收录」交所有者定，不能悄悄留着。上游 v26 的房子一生（立架、换瓦、长苔、塌顶）和 v25 的柱廊、菜园，在街巷级矢量房子里能看出来。
- H3 时间轴接编年史：年份轴覆盖 chronicle/ 的全部时段（-657 到 70），级 0–1 每 10 年烤一套，街巷级至少有关键年。编年史里每条有地点的事件都在图上有落点，点一下 flyTo 飞过去，同时切到那一年；拖年份轴时，事件按年淡入淡出。写 check_chronicle：能定位的事件 100% 有落点、能飞到；没法定位的列出来。文案用编年史原文摘一句，不编故事。
- H4 不退步：perf_tiles.py 全部场景不比 perf.json 现在的数差（飞行 ≥50 FPS、最差帧 ≤50ms 的线守住）；首屏请求量 ≤ b5fec41 时的 1.2 倍；瓦片总体积另外记账，超过 80MB 要先停下来问所有者。
- 恒定约束：底账（world.json、proposals/、rules/、chronicle/、engine/）只从上游并，不手改；不新开地块，不改故事；街区页保留。

## 预算
- 最多 20 轮，或者到 2026-10-14 21:00 PT 为止，先到哪个算哪个。
- 同一项连着两轮修不好：回滚，标「卡住」，换下一项。

## 清单（每轮开工先重排，做最上面那条没卡住的）
| # | 项 | 对应 | 状态 |
|---|---|---|---|
| 1 | 并上游：git merge origin/main，冲突逐一处理（xerolophos/scene.json 保留 next 链路；index.html 两边的块都留）；九块 accept、check_tiles 全过 | H1 | 完成（第 1 轮） |
| 1b | check_lives.js 在干山页上抛 `null.hid`（并之前的 HEAD 就抛，不是合并引起）：查清再修 | H1 | 完成（第 2 轮：检查挑的例子是嫁到别的街区的女儿，没有丈夫家；页面没坏） |
| 2 | 写 check_landmark_src，先在现状上跑出「不过」（列出 CS 线和上游对不上的地标） | H2 | 完成（第 2 轮：tools/cs/check_landmark_src.py，修前 7 条不过） |
| 3 | 地标的名字、位置、建成年、到期年改成读上游 registry（lm_src.py → scene_auto / places）；CS 线多出来的列「待上游收录」（lm_pending.json） | H2 | 部分完成（第 2 轮：7 座规格固定地标 5 座全对、2 座画布外已登记；轮廓和阶段留给 3b） |
| 3b | 规格的轮廓（poly）和阶段表进瓦片：上游 stages（立架→换瓦→长苔→塌顶）、固定地标的 overlay；check_landmark_src 加轮廓 IoU 和阶段年份检查 | H2 | 待做 |
| 4 | 矢量房子吃上游 houses_geom（P1 户型）和房子一生阶段（P3），以及柱廊和菜园（P2） | H2 | 待做 |
| 5 | 写 check_chronicle：把编年史事件解析成「年份、地点、一句话」，定位到世界坐标（地名词典、地标、街区） | H3 | 待做 |
| 6 | 年份轴扩到 -657 到 70，级 0–1 每 10 年一套；体积先算清楚再烤 | H3 | 待做 |
| 7 | 事件落点：跟着年份淡入淡出，点一下飞过去并切年 | H3 | 待做 |
| 8 | perf 复测和优化，体积记账 | H4 | 待做 |
| 9 | 收口：九块 --live、perf、截图，写总结 | 全部 | 待做 |

## 轮次（每轮一行：时间、项、结果、重排）
- 2026-10-13 20:56 PT 立项（会话里），清单 9 项。
- 2026-10-13 21:10 PT 第 1 轮 · 项 1 · 完成：先用现成不过的检查——九块 accept.py 都红着「上游底账落后」。git merge origin/main（8 个提交 aafed1c…c72b1f3，v24–v30 房子 P1–P3、地标规格卡 tools/landmarks/*.json + landmark_registry.py、3D 管线）；world.json 上游没动。冲突只有 1 处：xerolophos/scene.json——上游改成多行并加了 hgeom，取上游整份、补回 next→南港（理由：底账以上游为准，链路是 CS 线的）；xerolophos/index.html 自动合并（上游加 geomHG/阶段年份，CS 线块和 id="next" 按钮都在）。九块 accept 全过且「底账落后」转绿（nangang 72、jinjiao 48、gucheng 120、siqiu 67、dongjia 41、xipo 68、qiangwai 51、jiaowan 41、nanan 54 项，0 红；注意九块并行跑会同时重写 world.json 读到半截 JSON，要串着跑）；check_tiles errors 0；干山页 check_talk、check_card 过（1123 张卡 0 坏）。查出 check_lives 抛 null.hid，开工前的 HEAD 就抛，不是合并引起。重排：加 1b（check_lives），放在 2 前面——H1 要干山页照样能打开，先确认它只是检查过时还是页面真坏。 线上复验（768f83e 部署后）：九块 accept --live 全过 0 红（nangang 88、jinjiao 64、gucheng 136、siqiu 83、dongjia 57、xipo 84、qiangwai 67、jiaowan 57、nanan 70）。
- 2026-10-13 21:40 PT 第 2 轮 · 项 1b + 2 + 3（前半）· 完成：① check_lives 的 null.hid 是检查自己挑错例子（挑中嫁到别的街区的女儿，csSpouse 为空），改成挑嫁到本街区的、找不到就明说；页面没坏，输出 3 条一生都在。② 新写 tools/cs/check_landmark_src.py：规格固定地标换算到瓦片像素（干山页框 = 世界格 (400,356)，瓦片原点 (416,192)，同一个 14.21875 像素/格），查有没有、位置差 ≤ 8、建成年、到期年、名字；瓦片多出来的分「只有底账」25 座和「CS 线自己的」fire_ruins；修前 7 条不过（水渠桥位置差 113 像素且名字写成「大水道桥」，运水人蓄水池差 13，三座没带建成年）。③ 新 lm_src.py 一处读上游规格；scene_auto（街区 city.json 的名字、故事、此刻、位置、到期年）和 places.py（地标位置、名字、built/until）改读它；names_zh.json 里 7 条规格已有的名字删掉，只剩底账有、规格没有的。规格没写建成年的（兵营）用底账的。修后规格固定地标 5 座全对，奠基者城门和阿里乌聚会所落在画布外 44、150 像素（画布 x 从世界格 416 起，正好盖住全部房子），登记进 lm_pending.json 等所有者定；fire_ruins（底账里没有这座建筑）也登记待收录。④ 瓦片页标记按 built/until 亮（亚历山大粮仓 55 年才亮）。⑤ accept：规格故事不写年份不算错（写了得对）。check_tiles errors 0；siqiu、xipo accept 本地 0 红。重排：3 拆成 3（名字/位置/年份，已做）和 3b（轮廓、阶段）；因为上游规格固定地标只有 7 座、全在干山页框里，原来「重烤地标层」不需要——地标图是按底账地基贴的，规格 poly 和底账地基是同一个多边形（莫德斯图斯蓄水池规格 poly 对得上）。 线上复验（9b48f8b 部署后）：siqiu、xipo accept --live 0 红。
