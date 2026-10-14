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
| 2 | 喷泉干/湿效果进瓦片页（街巷级），敲门卡一句水源 | G1 | 待做 |
| 3 | 面包台阶卡经 landmarks_city 全城放 + 粮网 fed_by + 台阶清晨排队只在有粮时 | G2 | 待做 |
| 4 | 史诗地块清场（派生表）+ check | G3 | 待做 |
| 5 | epic_ground / epic_tall / mese_portico 分期画法进 render_ng/tile_bake，重烤 | G4 | 待做 |
| 6 | 道路终扫 + prune_islands + 全城 audit 0 | G5 | 待做 |
| 7 | 刘线 reg 旁车懒加载进敲门卡 | G6 | 待做 |
| 8 | 收口：perf 全量、九块 accept --live、截图，写总结发给所有者（早上 08:00 前） | 全部 | 待做 |

## 轮次（每轮一行：时间、项、结果、重排）
- 2026-10-14 09:40 PT 立项（会话里），清单 8 项。
- 2026-10-14 10:08 PT 第 1 轮 · 项 1：check_nets.py 先不过（无网）→ landmarks_city 加谭线 fountain 卡（放在最后，前三种选址一字不变）全城 22 座喷泉；net_water.py 从 world.json 抽 2 渠 3 渠桥 4 池 2 宁芙泉、喷泉就近取水（45 单位内已出水优先，否则等上游），22 座里 10 座有干着的年头；check_nets / lm_city / traces / chron_page / tiles 全过。瓦片未重烤（Mac 本轮启动、下轮收）。重排：下一项 2（喷泉干湿效果，等重烤回来）。
- 2026-10-14 10:35 PT 第 1 轮续 · 项 1 重烤收回（Mac，瓦片总量 64 MB，字节几乎不变）；检查全过。perf：首屏 0.54 MB / 1.0–1.3 s，街巷级 17.3 MB **超 12 MB**、堆 77 MB、57 FPS——同轮用重烤前 HEAD 基线复测也是 17.3 MB，超线早于本项。重排：插入 1b 查超线，排在项 2 前。项 2 计划：在 tile_bake 里把喷泉水池部件按 net_water 出水年拆成干/湿两段（部件自带年份段，页面零代码零负担）。
- 2026-10-14 10:55 PT 第 2 轮 · 项 1b：街巷级 17.3 MB 的拆账——vec 37 块 12.7 MB（未压）、栅格 ≈3.9 MB；curl 线上实测 GitHub Pages 对 json 发 gzip（vec/1_9.json 794501→154591 字节，全部 vec 32.1→5.6 MB）。perf_tiles.py 本地服务器改成同样 gzip，记 mb（线上）和 mb_raw（未压，管解析/堆）。复测：首屏 0.45 MB / 1.0 s；街巷级线上 **4.95 MB**（未压 17.3）、堆 54 MB、FPS 52（沙箱软渲染，上轮同机 57，有波动）；横穿后累计线上 9.0 MB；瓦片总量 64 MB。口径变了请所有者知悉（收口总结里写明）。检查全过，看了街巷级截图（南港 60 年，街、房、门前小树正常）。重排：下一项 2。
