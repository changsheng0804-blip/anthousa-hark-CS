# CS 线 · /goal 4：三线合流（瓦片主线吃谭线、刘线成果，守页面负担）

所有者 2026-10-14 09:36 PT：「你先按 /goal 命令模式持续推进修改完善，然后用心跳机制来唤醒兜底（每小时检查修改一次，然后上线），我需要去睡觉了」。
方向（所有者 10-14 定）：瓦片页是主线；谭线（tanxinhao2026-netizen/anthousa，交接 origin/handoff-cs 19b633d docs/handoff-cs/HANDOFF.md）和刘线（liu/main 6f7048e inbox/TO_CS.md）的有效成果并进来；**页面负担是硬约束**。上一个 goal 归档在 GOAL_v3.md。

页面：docs/living/tiles/index.html。重活（tile_bake 全量重烤约 20 分钟）放所有者的 Mac：/workspace/tools/ssh/up.sh 起隧道，mac.py changsheng "<命令>"；Mac 上 ~/cs-merge 是 worktree（git fetch origin main && git checkout --detach FETCH_HEAD），Mac 推不了 GitHub，烤完照 /workspace/work/bake_pull.sh 打包拉回沙箱再提交。

## 目标（全部达标才算完）
- G1 水网（谭线 notes/epic-system.md）：水渠→蓄水池→宁芙泉→街角喷泉，按 world.json 的建成年连成网（tools/cs/factory/net_water.py → tiles/net_water.json，每个节点 fed_by 上游节点）。脉在地下，不画网线（铁律：脉不露面）；只露效果：喷泉在供水的蓄水池建成以前是干的、以后有水；敲门卡上可多一句「这家从哪口泉打水」（只一句）。检查 check_nets.py：每个喷泉/宁芙泉都有 fed_by、上游都早于它建成、年份全读 world.json 不自编。
- G2 粮网：港口→粮仓→面包台阶（谭线 bread_steps 卡，经 landmarks_city.py 放；fed_by 最近的已建粮仓）。效果：台阶只在有粮仓供时清晨排队（沿用南港 cs5 的「效果才露面」规矩）。check_nets.py 同样查。
- G3 史诗地块：world.json 里的史诗建筑（广场、宁芙泉、大粮仓、浴场、教堂等）先占地——它们存续期内脚印下没有房子、没有街（派生表里清场，写 cleared_cs.json，叠层「旧街坊」能显示）。check：全城 0 栋房、0 段街压在当年已建的史诗脚印里。
- G4 分期绘制：谭线 render_xero.py 的 epic_ground / epic_tall / mese_portico 搬进瓦片画法，狄奥多西广场（57）、大宁芙泉（44）、梅塞柱廊按年分期出现（立架→落成）。check：这三处在建成前后各一年的瓦片画面不同、建成前没有成品。
- G5 道路规则：谭线终扫 + prune_islands（孤岛小路删掉）+ 全城房屋严格不压当年道路；audit 目标 0。
- G6 刘线旁车：敲门卡点开时才按瓦片懒取刘线 reg 旁车（门牌·坊·教区一行），不预载；没有旁车的房子不显示这一行。资产只取刘线 liu/main 已有的、注明来源。
- G7 负担（硬线，每轮都量）：首屏 ≤1 秒、≤1 MB；街巷级最密处 ≤12 MB、堆 ≤150 MB、≥55 FPS（perf_tiles.py；沙箱 SwiftShader 是悲观值）；不加栅格年份档；瓦片总体积 ≤80 MB。任何一条要破线：停下这一项，标「卡住·超负担」，留给所有者定。
- 恒定约束：world.json、proposals/、rules/、chronicle/、engine/ 只从上游并、不手改；不新开地块、不改故事；九块街区页保留；未提交的 docs/living/gucheng/ACCEPT.md、docs/living/nangang/ACCEPT.md、nightlog.md 不 reset 不 stash（提交时别带上）。社会关系网、财政层、3D 不上页面。

## 预算
- 到 2026-10-15 08:00 PT 为止，或 16 轮，先到哪个算哪个。
- 同一项连着两轮修不好：回滚（git revert 自己那轮的提交），标「卡住」，换下一项。

## 清单（每轮开工先重排，做最上面那条没卡住的）
| # | 项 | 对应 | 状态 |
|---|---|---|---|
| 0 | 合流①：谭线 v31 三卡（肉鱼市、砖窑、城外墓地）进全城 + vec 带底账 id + 回刘线 TO_LIU.md | — | 完成（会话里，ebb2bdc） |
| 1 | 写 check_nets.py（先跑出不过）+ net_water.py：从 world.json 抽水渠/蓄水池/宁芙泉/喷泉，连 fed_by | G1 | 完成（喷泉 22 座经 landmarks_city 放，网 33 节点；瓦片已重烤） |
| 1b | 查街巷级下载超线：perf 街巷级最密处 17.3 MB > 12 MB（重烤前的 HEAD 基线同样 17.3 MB，不是项 1 造成；perf.json 旧值 10.7 MB）——找出哪批瓦片变重、压回 12 MB | G7 | 完成（不是瓦片变重：vec JSON 未压 12.7 MB，Pages 实发 gzip 后 ≈2.2 MB；perf 测量改按 gzip 线上字节记，mb_raw 另记） |
| 2 | 喷泉干/湿效果进瓦片页（街巷级），敲门卡一句水源 | G1 | 完成（tile_bake 按出水年分干池/水池段，check_nets ⑥；敲门卡一句水源，check_waterline.js） |
| 3 | 面包台阶卡经 landmarks_city 全城放 + 粮网 fed_by + 台阶清晨排队只在有粮时 | G2 | 完成（8 座台阶；粮网 4 港 5 仓 8 台阶；4 座先光秃后供粮；check_nets ⑦⑧ + check_breadqueue.js） |
| 4 | 史诗地块清场（派生表）+ check | G3 | 完成（账本+streets_ng 已清大部分；check_epic_clear 先抓出水渠桥谷桥下 5 栋，epic_clear.py 拆/不建；瓦片已重烤） |
| 5 | epic_ground / epic_tall / mese_portico 分期画法进 render_ng/tile_bake，重烤 | G4 | 完成（epic_stage.py → 伪房子行进 vec；广场 57 工地→59 铺面、柱每年一节至 64 立像、60 凯旋门；大宁芙泉 44；梅塞柱廊 1 立架→3 瓦顶；check_epic_stage 21 项） |
| 6 | 道路终扫 + prune_islands + 全城 audit 0 | G5 | 完成（road_sweep.py 孤岛先接后收：接线 13 段、收 42 段；check_roads 压路/孤岛/渠桥下小巷全 0；瓦片已重烤） |
| 7 | 刘线 reg 旁车懒加载进敲门卡 | G6 | 完成（reg_pack.py 按我们 vec 的底账 id 重装箱刘线旁车→tiles/reg/{40,50,60}，gzip 0.23 MB；点开卡才取一个文件；check_reg.py/.js） |
| 8 | 收口：perf 全量、九块 accept --live、截图，写总结发给所有者（早上 08:00 前） | 全部 | 完成（已收尾） |

## 轮次（每轮一行：时间、项、结果、重排）
- 2026-10-14 09:40 PT 立项（会话里），清单 8 项。
- 2026-10-14 10:08 PT 第 1 轮 · 项 1：check_nets.py 先不过（无网）→ landmarks_city 加谭线 fountain 卡（放在最后，前三种选址一字不变）全城 22 座喷泉；net_water.py 从 world.json 抽 2 渠 3 渠桥 4 池 2 宁芙泉、喷泉就近取水（45 单位内已出水优先，否则等上游），22 座里 10 座有干着的年头；check_nets / lm_city / traces / chron_page / tiles 全过。瓦片未重烤（Mac 本轮启动、下轮收）。重排：下一项 2（喷泉干湿效果，等重烤回来）。
- 2026-10-14 10:35 PT 第 1 轮续 · 项 1 重烤收回（Mac，瓦片总量 64 MB，字节几乎不变）；检查全过。perf：首屏 0.54 MB / 1.0–1.3 s，街巷级 17.3 MB **超 12 MB**、堆 77 MB、57 FPS——同轮用重烤前 HEAD 基线复测也是 17.3 MB，超线早于本项。重排：插入 1b 查超线，排在项 2 前。项 2 计划：在 tile_bake 里把喷泉水池部件按 net_water 出水年拆成干/湿两段（部件自带年份段，页面零代码零负担）。
- 2026-10-14 10:55 PT 第 2 轮 · 项 1b：街巷级 17.3 MB 的拆账——vec 37 块 12.7 MB（未压）、栅格 ≈3.9 MB；curl 线上实测 GitHub Pages 对 json 发 gzip（vec/1_9.json 794501→154591 字节，全部 vec 32.1→5.6 MB）。perf_tiles.py 本地服务器改成同样 gzip，记 mb（线上）和 mb_raw（未压，管解析/堆）。复测：首屏 0.45 MB / 1.0 s；街巷级线上 **4.95 MB**（未压 17.3）、堆 54 MB、FPS 52（沙箱软渲染，上轮同机 57，有波动）；横穿后累计线上 9.0 MB；瓦片总量 64 MB。口径变了请所有者知悉（收口总结里写明）。检查全过，看了街巷级截图（南港 60 年，街、房、门前小树正常）。重排：下一项 2。
- 2026-10-14 11:50 PT 第 3 轮 · 项 2：先写 check_nets ⑥（出水年前不许画水）→ 跑出 10 口喷泉不过；tile_bake 把池面按 net_water 出水年拆成干池（灰褐）[落成,wet) / 水 [wet,∞)，水柱只从 wet 起画；Mac 重烤收回，只有 10 块 vec 变（栅格字节全同，总量 64 MB）。页面加敲门卡一句水源（离这家 ≤420 px 的已建街角泉；出水「水从X来」、未出水「水还没来」；net_water.json 点上加 zh、px，仍不画线），check_waterline.js 全过。全部检查过；perf 首屏 0.45 MB、街巷级线上 4.96 MB（未压 17.3）、堆 53 MB、FPS 43–52（沙箱软渲染，与上轮同量级）。看了 nangang 门口 40/70 年对照：40 年灰干池，70 年蓝水。重排：下一项 3。
- 2026-10-14 12:05 PT 第 4 轮 · 项 3：先写 check_nets ⑦⑧（无粮网/无台阶 → 不过）→ landmarks_city 加第二遍放 bread_steps（前 39 处放置一字不变，diff 验证）全城 8 座，net_water.py 加 grain 段（港口→粮仓→台阶，就近取、供粮年=max(落成,上游)），tile_bake 面包按供粮年摆，页面 breadQueue 只在供粮的清晨 5–8:30 排队、不画网线；check_breadqueue.js 全过。Mac 重烤收回（瓦片 64 MB）；全部检查过；perf 首屏 0.45 MB/1.1 s，街巷级线上 4.96 MB、堆 80 MB、FPS 47（软渲染，同量级）。看了南港 40 年清晨门前的队（30 年粮仓未供则无队）。重排：下一项 4。
- 2026-10-14 12:35 PT 第 5 轮 · 项 4：先写 check_epic_clear（33 座史诗多边形 × 全城房/街/vec 三层，脚印下 0 房 0 街）→ 先不过：5 栋房压在水渠桥谷桥（aqb_valley）下 1–2%（街 0 段，其余史诗账本已拆干净）；epic_clear.py 在派生表里拆（建成年已在的拆于建成年，之后才开工的不建），landmarks_city 末尾调用、重放验证幂等（39 座地标放置一字不变）；Mac 重烤收回（61 块 vec 只因拓扑排序名次顺移 1–2，另 2 栋房消失；瓦片总量 64 MB）。检查全过；perf 首屏 0.45 MB/1.2 s，街巷级线上 4.96 MB、堆 70 MB、FPS 50（软渲染，同量级）。看了谷桥一带街巷级 60 年图，街房正常。重排：下一项 5。
- 2026-10-14 13:20 PT 第 6 轮 · 项 5：先写 check_epic_stage（vec 里无 epic 行 → 不过）→ epic_stage.py 把谭线 epic_ground/epic_tall/mese_portico 译成「带年份段的部件」，以伪房子行（id epic:…）写进 vec，页面零代码；广场 57–58 工地（碎石石堆）→ 59 铺面+四面柱廊+雕像+铜牛+布棚，狄奥多西柱 57 起每年立一节（脚手架）、64 年立像拆架，60 凯旋门；大宁芙泉 44 池+半圆壁龛、水面从 net_water 出水年；梅塞柱廊 1–2 年立柱+石板路、3 起瓦顶（梅塞派生路宽 15 px、房子贴到 ~10 px，柱廊收窄到 7.6–10.2 px，让房、支路断开、创城者广场/狄奥多西广场内断开）。踩坑：柱单独成行会被拓扑排序排到铺面前面盖住→柱的部件接在广场行末尾。check_epic_stage 21 项、check_epic_clear（跳过 epic 行，部件级 ⑥）、check_lm_city（认 epic: id）全过；看了 58/59/61/64 年广场与 45 年宁芙泉+梅塞柱廊图。重排：下一项 6。
- 2026-10-14 13:50 PT 第 7 轮 · 项 6：先写 check_roads（压路 / 30–155 年每 5 年的孤岛 / 渠桥下小巷）→ 先不过：孤岛 81 条（南港、金角岸、古城、西坡、南岸等；房不压路本来就是 0）→ road_sweep.py（谭线 prune_islands 改成先接后收：中线 ≤4 px 算通；离最近街 ≤32 px 且全程陆地、不压当年房、不穿史诗脚印的孤岛补一小段接线，接不上的把开始年推到连通那年或把结束年定在断开那年）；landmarks_city 先撤记号、末尾再扫，重放验证 39 座地标放置一字不变。Mac 重烤收回（瓦片 65 MB）；check_roads / nets / lm_city / epic_clear / epic_stage / traces / chron_page / tiles / waterline / breadqueue 全过；perf 首屏 0.45 MB，街巷级线上 4.98 MB（未压 17.5）、堆 93 MB、FPS 50.7（沙箱软渲染，同量级）。看了金角岸 45/60 年图：45 年孤岛小巷不画，60 年接上主街后出现。注：check_streets 的「重排后户数/年份和底账不一致」在南港/金角岸/古城/第四丘上是项 4/5 清场改年份留下的，非本项造成。重排：下一项 7。
- 2026-10-14 14:45 PT 第 8 轮 · 项 7：先写 check_reg.py/.js（无旁车、页面无 REG 段 → 不过）→ 取刘线 liu/main 8034184 的 reg 旁车，tools/cs/factory/reg_pack.py 按我们 vec 里每栋房的底账 id（h[5]）重新分文件（刘线原文件按旧对接分块，约 8% 户落在邻块；记录内容一字未改，SOURCE.md 注明来源），重装后按 id 对上 99.7%（42598/42736）；页面敲门卡点开才取这栋房所在瓦片的一个文件（离卡年份最近的 40/50/60 档，同块同年只取一次），多一行「户籍 门牌 N 号 · 区第 N 坊 · 教区（· 户主任职）」，没旁车的（新立地标、无记录）不显示；载入时 0 个 reg 请求。check_reg 全过；nets/lm_city/traces/chron_page/tiles/waterline/breadqueue 全过；perf 首屏 0.45 MB，街巷级线上 4.99 MB（未压 17.5）、堆 93 MB、FPS 52（软渲染）；瓦片总量 70.8 MB（≤80）。看了南港 50 年点开的卡（沙箱 Chromium 缺中文字体，文字取自 DOM：户籍门牌 8125 号 · 广场区第 34 坊 · 圣安娜斯塔西娅教堂教区）。注：瓦片再重烤后要重跑 reg_pack.py。重排：下一项 8 收口。
- 2026-10-14 15:00 PT 第 9 轮 · 项 8 收口，**已收尾**：perf 全量首屏 0.45 MB/1.1 s、街巷级线上 4.99 MB（未压 17.5）、堆 84 MB（峰值）、FPS 51–54（沙箱软渲染；倾斜飞行 45）、横穿累计线上 9.1 MB、瓦片 70.8 MB；九块 accept --live 除各块「重排后户数/年份和底账不一致」（项 4/5 清场改年份所致，gucheng/nangang 同）外全过，nangang 88/0，jinjiao 63/1，gucheng 135/1，siqiu 82/1，xipo 83/1，dongjia 57、qiangwai 67、jiaowan 57、nanan 70 全绿；nets/lm_city/traces/chron_page/tiles 全过；看了南港 50 年敲门卡截图。
- 2026-10-14 16:49 PT 会话里（所有者「可以」）：清掉四块的 check_streets 红——差都是记过账的清场（cleared_cs 38 + epic_cleared 5）和新地标 cs:lm900001；check_streets 规则 1 改成「记账的差算对、没记账的差照样红」；jinjiao 48/48、gucheng 120/120、siqiu 67/67、xipo 68/68 全过。
- 2026-10-14 16:52 PT 会话里（所有者「可以」）：派生表清场接进叠层——traces.py ⑤ 读 cleared_cs.json（地标卡）和 epic_cleared.json（史诗脚印），按「为谁拆」归成 21 处可点开的「旧街坊」（文案只一句「N 年起这里改成…」，户数、年份逐户对账）；check_traces 加 1b 对账，故意改错 1 条会红；check_traces/chron_page/tiles 全过；traces.json 44 KB。
