# CS 线 · 改善清单（心跳每小时取一条）

规则：每轮只修一条。先写自动检查，确认它在修之前不过，修完以后才过；验收全过才推送，不过就回滚到上一版。
所有者的「再来」永远排第一。修完把这一条移到「已修」，写上检查名和版本号。

## 待修（从上往下取）
0. 【瓦片房子换成上游 house_types（P1–P3）】瓦片烤的是 cs29 分叉的老 tools/cs/factory/house_types.py（320 行）；换成上游 tools/house_types.py 的薄壳，只补 dock/horrea；vec 零件带年份区间，页面 worker 按年挑零件（/goal 3 项 4）。
1. 【码头工地更像工地·续】还可加吊杆、运石料的驳船；没建成的栈桥旁画上原有的船也该挪走或减少。
2. 【真栈桥认不全·剩余】cs19 剔掉了站在船上的 3 个站位，只剩 2 个。画上船旁边那条细长的栈桥（大约在 1060,1400）没有被认成栈桥，因为现在要求三张画都画了它。要做：栈桥按当年那张画来认，人走的网按年份分开；先写检查：画上细于 38 像素、连着岸的陆地条，八成以上都要能走。修好后，把 check_fleet「people standing on piers」改回原来的标准：至少 4 个站位，每年至少 8 人（cs19 暂时放宽了）。
5. 【炊烟找房子】烟囱的烟现在只保证在陆地上，但随机撒的，可能冒在空地、还没盖的年份里。要做：烟只从当年已盖好的房子上冒；先写检查：每个烟点 20 像素内有当年存在的房子。
6. 【海鸥圈】海鸥的圈心是抄干山的固定坐标（1300,1600 / 900,160），要核对在南港是不是绕在水面和港上；先写检查：圈心落在水里或码头边。

## 已修
- /goal 3 第 5 轮 项 7：事件落点接进瓦片页（按年淡入淡出、点了飞过去并切年、出卡、能拖的年份轴）；检查 check_chron_page.js（经 check_chronicle.py 调用）；flyTo 遇 0 年不切年的小毛病顺手修了。
- /goal 3 第 4 轮 · 年份轴 -657 到 70（tile_years.py；check_chronicle 第 8 段四条检查）+ 瓦片内容哈希去重（meta.alias），49 MB。
- /goal 3 第 3 轮 项 5：编年史事件落点。新检查 check_chronicle.py（events.json 不存在时红）；chron_events.py 生成 events.json，58 件有落点、13 件偏出画布（收到西缘，待所有者定）、4 条没地点。——Hark（CS线）
- /goal 3 第 2 轮 项 1b+2+3：check_lives 的 null.hid 是检查挑错例子（页面没坏）；新检查 check_landmark_src.py（修前 7 条不过，修后 0）；lm_src.py 让街区 city.json 和 places.json 的地标名字/位置/建成年/到期年读上游规格；标记按建成年亮。——Hark（CS线）
- /goal 3 第 1 轮 项 1：并上游 v24–v30 + 3D 管线；冲突 1 处（xerolophos/scene.json 取上游 + 补 next）；九块 accept 全过（底账落后转绿）、check_tiles 0 错。——Hark（CS线）
- /goal 2 第 10 轮（项 7a）：perf_tiles.py 三个新场景（飞行×2、倾斜带平移）；飞行冷启 33/24→42/39 FPS、最差帧 183/117→67 ms（拉伸旧层、瓦片预解码、载入排队、预取节流）；未达 ≥50/≤50，7b 接着做。
- /goal 2 第 9 轮 项 6：2.5D 微倾（倾角随缩放连续、房子立起来、倾斜里指针不漂、点屋顶出卡）。检查 check_tilt.py；check_zoom 把倾角算进对齐；check_tiles 淡入带字节预算 3.3 MB。——Hark（CS线）
- /goal 2 第 8 轮 项 5：九块活人层在瓦片页里就地长出来（炊烟+家户推演+敲门卡；粮船日仅南港）。检查 check_hearts9.py、check_card_tile.py --q <九块>。——Hark（CS线）
- 【/goal 2 项 4b】敲门卡接到瓦片页：tile_heart.py 多剪卡片段 + check_card_tile.py；顺手修街区页 csIncoming 遇建成年>60 房子抛错（第 7 轮）；FLEET.crowd/csIncoming 分帧，首次 ~300 ms 卡顿 → 0 个 >50 ms 长任务。
- 【/goal 2 项 4a】粮船日、家户推演、炊烟、时钟接到瓦片页（南港）：tile_heart.py + check_heart.py（第 6 轮）。
- /goal 2 第 5 轮：弧线飞行 + 滚轮缓动（项 3、2d）。check_fly 41 程 0 不过；顺手修街巷级换年份整屏品红、飞行中粗级垫底。
- /goal 2 第 4 轮：级间交叉淡入（项 2b）。检查 check_zoom：级间最大跳变 2.45→1.61/1.91，冒尖 5→0（地板 2.0）；check_tiles 0 错；perf 不退步。
- /goal 2 第 3 轮：换街巷级交叉淡入（项 2c）。检查 check_zoom：换街巷级跳变 15.2→1.15；check_tiles 0 错。
- /goal 2 第 2 轮：拼图补洞 tile_bake.fill_holes（三块街区框之间的无人角在级 0 本是透明的，缩放时漏底色）→ check_zoom 空白帧 60→0
- /goal 2 第 1 轮：全城推到门口的检查 check_zoom.py（现状空白帧 60、冒尖 4 处，交给 GOAL.md 项 2a–2c）
- cs37（/goal 第 1 轮）nanan 左半边没有街：streets_ng 连通修补只认「当年已开」的出框街，没房的出框街年份 999 → 整片当孤岛删掉。改成出框街没房也算通全城 → check_citynet「接缝」（修前 8/18 没接上，修后 18/18；nanan 街 635→1542 段）
- cs23 码头完善（所有者 cs22 留、说可以继续完善）：没建成的栈桥用 heart.py 算的 borrow 偏移从同一张画借干净海面、羽化盖住（cs22 是平涂色块，颜色还取错了年代）；工地加木料垛、石堆 → check_fleet「docks」加：每座没建成的栈桥在每张关键年画都借得到水
- cs22 所有者提「码头逐年长」：heart.py 给画上每座栈桥推建成年份（港 33 年挖成，按离泊位远近 + 港边 600 像素住户增长一座座建成：39、44、47、60），建前两年是工地；页面没建成的盖成水，人走到栈桥根就停在岸上 → check_fleet「docks」（修前 0 座，修后 4 座、4 个年份、没建成的栈桥上 0 人）；会动的东西登记册加「码头工地」
- cs21 backlog 0 续：40、50 两张也按底账草图重画；repaint.py 加「蒙版合成」（底账陆地、港墙上画成水的贴岸像素用最近的画上陆地补）→ 定律四改成必须过：按 4 像素格量底账陆地画成水 ≤50（cs19 旧画 965，现在 0）；栈桥不到 24 像素长的碎屑不算，栈桥检查把比 8 像素格还窄的尖单独报数
- cs20 backlog 0（只 60 年）+ backlog 1：60 年画用底账草图（不给旧画）重画 → 定律四 331→56 格；真栈桥认出 5 个，check_fleet 栈桥检查恢复严格（≥4 站位、每年 ≥8 人）；站位补人允许从岸上调人（修前 50 年 2/2/1/0/1，修后 3/3/3/3/3）
- cs19 查收图抓到：靠在栈桥边的船被并成了能走的「栈桥」，画上是水的格也能走 → heart.py 剔掉太宽的团，过半画成水的格一律不能走 → laws.py 定律一（修前 77 格、1 团太宽，修后 0）
- cs18 backlog 7：栈桥平均分人 → fleet_day 站位超员的人家改走广搜路线去空站位 → check_fleet「people per pier spot」（修前 24/0/0/0/0，修后 12/3/3/3/3 等，每个 ≥2）
- cs17 backlog 3：人去栈桥 → heart.py 给栈桥尖端和半腰加站位（scene.fleet.pier_spots），栈桥上扛包的人不跨水（页面 haul）→ check_fleet「people standing on piers」/ accept.py「栈桥上有人站」（修前 0 个站位、0 人，修后 5 个、每年 12–24 人）
- cs16 backlog 3：会动的东西登记册（页面 csMovers）→ check_fleet「movers」/ accept.py「每种会动的东西都登记并在该在的地方」（修前 炊烟 40/180、工地上的人 54/915、炉烟 3/55 在水里，修后 0；14 种）
- cs15 backlog 2：节奏 → fleet_day.js 船按「起步加速—匀速—最后 140 像素匀减速」走，散场分三拨 → check_fleet「ship peak speed / leave waves」（修前 峰值 599 px/h、1 拨，修后 400、3 拨）
- cs14 backlog 1：港口的口子按画 → heart.py 口子选画上的缺口 → accept.py「港口的口子对上画、船进得了港」（修前 口子 1/2、港里 0 艘，修后 2/2、2 艘）
- cs13 backlog 1：画上的栈桥 → heart.py 把栈桥并进 walk 网 → accept.py「画上的栈桥人走得上去」（修前 703/2149，修后 2083/2149）
- cs12 backlog 1：宽街无人 → 画上量出宽街中线（scene.json wide_street），heart.py 并入 city.roads（只留人走得上的几截）→ check_fleet「wide street empty 100px segments」（修前 15/18 段空，修后 0）
- cs11 backlog 1：街上的人和摊子按全街取样，偏到水里的回街心 → check_fleet「walker samples in water」（修前 56/191250，修后 0）
- cs7 再来：人从海里走 → 人走的网（check_fleet 人不下水）
- cs8 再来：画和底账的岸不一致；船太快 → 网要底账和画都认；船速上限 450
- cs9 再来：街上的人在海里走（city.json 的路是别的街区抄来的）→ 街从底账长，切掉落在水里的几截；检查「街的每个点都在网上」（cs10）
- 上游 v24（房子系统 P1，aafed1c）待并：xerolophos/scene.json 冲突，单独一轮处理

- 古城页签标题仍写「南港」，「这是怎么做的」文案还是旧的整张画做法：scene_auto 按配方 title 和生产方式生成（cs35 遗留）

- [cs36 遗留] 港池（狄奥多西港除外）在拼图法里画成带沙边的方块水，像贴上去的（普罗斯福里翁、尤利安港）。应该给 harbor 也画一张地标图或按岸线规则生成码头。
- [cs36 遗留] 街巷级横穿全城时帧率掉到 ~31（最差一帧 100ms）：矢量块 JSON 解析和图片解码都在主线程。改：矢量块预切成二进制 / Worker 解析，图片 createImageBitmap。
- [低配机] 推近后若仍卡：省力模式（限 devicePixelRatio、减行人、关倾斜精灵），按 deviceMemory/hardwareConcurrency 自动开。b5fec41 已修开局九块全载。

## /goal 3 第 6 轮（项 3b 完成）
check_landmark_src 加轮廓 IoU 和按年阶段（读烤好的级 0 瓦片）；5 座在画布内的固定地标全过。
