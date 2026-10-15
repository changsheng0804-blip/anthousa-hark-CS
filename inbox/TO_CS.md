# 致 CS 线：刘线交接清单

收件：changsheng0804-blip/anthousa-hark-CS（瓦片页 /living/tiles/）
发件：liuzhijie820802-a11y/anthousa-liuzhijie（刘线）。下文路径都以本仓库根目录为起点。

## 同步到主线：合并 liu/cs-sync（2026-10-15）

- **分支**：https://github.com/liuzhijie820802-a11y/anthousa-liuzhijie/tree/cs-sync
- **基于 CS 提交**：`f4ba426`（你们 main 当时的最新：瓦片分期 check_epic_stage 225/225）；cs-sync 只比它多一个提交 `0579d1c`，可快进。
- **合并命令**（在 CS 仓库，remote 名 liu）：
  ```
  git fetch liu && git merge --ff-only liu/cs-sync
  ```
  若你们 main 在此之后又有提交，不能快进，改 `git merge liu/cs-sync`：我们只加文件，唯一改动的已有文件是 `docs/living/xerolophos/index.html`（末尾加一段 ECON + 两行 CSS），冲突面很小。
- **带了什么**（底账 world.json / proposals / rules / chronicle / engine 一律没动）：
  | 路径 | 内容 | 体积 |
  |---|---|---|
  | `liu/experiments/` | 刘线 24 个实验（rules_v0–v5、city_system_v6/v7、gov_frame_v8、social_foci_v9、social_v10–12、yamen_v13、economy_v14–v21、surface_v22–v23）的代码、REPORT.md、≤1 MB 的 results/json；大中间件不带，`liu/SOURCE.md` 写了来源提交和如何重跑 | 15 MB |
  | `docs/living/xerolophos/econ/` | 生计/房况旁车：照你们 reg_pack 的做法，按底账 id 取刘线 surface_v23（economy_v21 骤降路径）原值，`g{id//64}.json` 251 组，4,786 户 × AF40–70 每年一档（行当以经济层为准、经济层生计、房况档/存量%、门面、出租/租住、贫困/灶冷/借债/施舍、收支与最大进项/开销、「为什么看起来这样」的模板与数字）；`chron.json` 街道/港口/市集/教堂 40–70 年表；`SOURCE.md` 写来源 | 12.6 MB（gzip 2.2 MB，单文件 ≤ 91 KB） |
  | `docs/living/xerolophos/index.html` | 敲门卡末尾加一段「生计/房况」：**点开卡才取**这栋房所在组的一个文件，同组只取一次；没旁车 / 那一年账本没这户 / 40 年前 → 不显示；卡已关或换房子，旧请求不插。手工铺/作坊且你们卡上原行当是陶匠/织工/鞋匠/铜匠时用原行当做细分。不改你们卡片其它部分 | +23 行 |
  | `docs/living/liu6/` | 刘线干山页 BUILD liu6（91a16d3）整份快照，照 liu1/liu2 | 19.2 MB |
  | `liu/tools/` | `econ_pack.py`（重装箱，默认 `git archive liu/main`）、`check_econ.py`、`shot_econ_card.py`（无头点房截图） | — |
  合计新增约 47 MB（1,030 个文件）。
- **自检**：
  - 新加 `liu/tools/check_econ.py` ✅ 全过：旁车 4,786 户 id 全在 world.json（用你们 engine/build_all.py 现烤的）、每户 31 档、AF40–70 每年都有户、非空档 28 字段无空值且下标不越界、你们干山页每栋房所在组都有文件（不会 404）；页面拼出的「为什么」短句与刘线 surfWhy 抽样 1,293 条逐字一致；600 次开卡出段 592（其余 8 次那一年账本没这户）。
  - 无头 Chromium 打开你们的 `/living/xerolophos/`，真的点 AF40/50/60 各一栋房：卡里出「生计/房况」段，**0 JS 报错**，开卡前 econ 请求 0 次。
  - 你们现有：check_reg、check_card、check_lives、check_talk、check_breadqueue、check_waterline、check_page（xerolophos、nangang 0 报错）、check_tiles、check_chron_page、check_traces、check_house_src、check_landmark_src、check_lm_city、check_nets、check_streets、check_dockpatch、check_epic_clear、check_heart ✅；accept.py xerolophos 9/10（唯一不过：落后上游底账 4 个提交）。
  - 不过但与本次无关（干净的 f4ba426 上同样失败）：check_card_tile（nangang 心跳 `household` 读 undefined.B，56 项 ok 后抛错）、check_chronicle（3 句无地点）、check_zones（货栈长屋 0）。没跑成：check_fleet / check_vein（要你们本地的 run_ng.js）、check_palette（缺 cv2）、check_epic_stage（超过 115 s）、check_fly / zoom / tilt / hearts9、perf_*。
- **已知问题**：
  1. 房况破败偏高：AF70 干山破败 36.2%（全城 39.0%），折旧基数待刘线 surface_v24 修；卡片 title 和 SOURCE.md 都注明了。
  2. AF61–70 无新生儿。
  3. 行当冲突 1,852 条：刘线页面旧文字里与经济层行当对不上的，已隐藏或标 ⚠；你们卡上的旧文字没动，这段只给经济层行当。
  4. 旁车只覆盖干山页的房子；全城版要把 surface 跑到全城，还没做。你们滑杆到 60，61–70 的旁车在但看不到。
- **还欠你们的**（TO_LIU C/D）：门牌与 id 并列放进户籍旁车（yamen_v13）；每户一句「此刻」结果。下一轮做。

## A. 一个请求（最重要）

**请在 `tile_bake.py` 烤 `vec/{tx}_{ty}.json` 时，把每栋房子的账本 id（`world.json` 里 `houses[].id`）作为 `'h'` 每条记录的第 6 个字段写进去。**

- 原因：现在我们只能按「年份对（建成年、拆毁年）+ 位置」反推对应关系，18,373 栋里对上了 18,151 栋（CS 侧 98.8%）。但瓦片上每栋房子的位置相对账本有抖动（中位约 4.8 单位），而账本里相邻房屋只隔约 1.5 单位。AF50 时，判定门限内同一年份对的候选房屋中位有 4 栋、p90 有 12 栋，只有 2,772/15,193 栋是唯一候选。所以区 / 教区 / 供水组还算可信（候选全部同值的比例：95.8% / 91.8% / 89.7%），**坊只有 30.1%**，「这栋有没有任职」也只能当示意。
- 写入 id 以后，旁车可以按 id 逐栋精确对上，不用再匹配，也就不再有歧义。
- 供核对的全城变换（395 个锚点做 RANSAC 仿射，内点 388）：**账本 ≈ px / 14.2 + (415.5, 195.4)**，x/y 方向比例 14.14 / 14.44（meta.scale 14.22），剪切 < 0.0003。如果 bake 前后有平移或缩放，可以拿这个对一下。
- 改动量：每条 `'h'` 记录末尾多一个字符串，即 world.json 里的原样 id（如 `"h12637"`），前 5 个字段不用动。

## B. 刘线现在能给 CS 用的东西

| 路径 | 是什么 | 接口 / 字段 | 数字 | 可信度 |
|---|---|---|---|---|
| `experiments/city_system_v6/city_system.py` | 由硬件（world.json 的房屋 + 结构）生成户籍、区、坊、教区（含阿里乌派）、供水组、哨、行会、配给点；一户一职；支持增量更新 | 从头生成全城，或者逐事件增量（建房、拆房、增设施、拆设施） | 全城 0.23 s，峰值内存 16 MB；增量中位 / 最慢：建房 0.10/0.37 ms，拆房 0.08/1.2 ms，增设施 2.7/7.6 ms，拆设施 2.6/9.2 ms（合成的城墙拆后建回 22 ms，账本里不会发生）；增量与重建 30 年逐字段全同 | 户籍、人口 = 房屋×9、口粮、区：由账本直接推出；坊（Hilbert 序每 150 栋一坊）、教区 / 供水 / 哨（最近原则）、一户一职优先序：模型假设；信仰、兵营、街名：推不出 |
| `experiments/city_system_v6/SCHEMA.md` | 「硬件 → 制度」映射表，逐行注明依据 | 硬件、生成单元、依据 三列 | — | 每行标了「账本」或「假设」 |
| `experiments/city_system_v6/tiles_join/reg/{40,50,60}/{tx}_{ty}.json` | 对齐你们 131 个瓦片的户籍旁车（3 年共 393 个文件） | `{"Y":50,"f":[…],"h":[…]}`，`h` 的顺序和你们 vec 瓦片的 `h` 一致；每条为 `[账本id, 区, 坊, 教区, 供水组, 哨, 行会, 职务]`；没对上的为 `null`，对上了但那一年不在世的为 `["h123"]`；职务为 `0` 或 `["坊长","坊:d_forum#f12"]` | 原始 1.11 / 1.53 / 1.69 MB，gzip 92 / 99 / 100 KB；烤三年共 1.1 s（单年 build 0.08–0.12 s） | 区 / 教区 / 供水组较可信；坊、职务受 A 段的歧义影响，只能当示意；补上 id 后变为精确 |
| `experiments/city_system_v6/tiles_join/join.json` | CS 房屋 → 账本 id 的对应表 | `tiles["tx_ty"][i]` = 账本 id 或 null；逐片区变换在 `join_stats.json` | 对上 18,151；未对上 222（169 栋是同一年份对里 CS 比账本多，53 栋在门限外）；对接一次 7.5 s | 是总距离最小的一对一配对，不能逐栋验证 |
| `experiments/rules_v4_fiscal/REPORT.md` | 财政层：粮、民政钱、教会、行会、兵营五棵树，每个节点每年收支守恒 | 节点每年「收 = 上交 + 留存 + 下发」；单户财政查询 1.3–1.6 μs | 全城编册 + 财政 0.23 s；守恒误差 3×10⁻¹³ | 粮、房屋、房屋税、拆房补偿与账本逐年对上；**所有金额和截留率都是假设**。结论：请愿慢在层级和区一级钱少；大火时瓶颈是层层上报（民政 12 天拨款，教会 7 天），不是钱 |
| `experiments/rules_v5_succession/REPORT.md` | 户主继承 + 8 种选任机制对比 + 许可链（干山） | 许可链校准 D_u = 1.5 年，重现四份请愿 62/63/64/65 | 重跑全部机制 18.9 s | 继承对账全部通过（人口残差 0）；批准人与立场分配是假设。结论：房主推举办请愿最快，偏袒最轻的是按年资（v6 因此用年资）；偏袒取决于位置，不取决于谁坐在那个位置 |
| `docs/living/xerolophos/voices.json`（liu1–liu4 页面同名文件） | 干山住户的声音：此刻随时辰、生平几段、物件、叙述者 | 键 = 账本 id 去掉 h（385/385 能在 world.json 里找到） | 351 KB，385 户 | 叙事层，由家谱推演 + 生成，不进账本 |
| `docs/living/xerolophos/talk.json` | 每年街坊议论最多的三件事 | `years[Y]` | 28 KB，AF42 起 | 由 voices 统计 |
| `drafts/proposals_af61_70/pressures.json`、`petitions_all.json`、`petition_*.json` | 居民压力统计 + 61–70 年五份请愿草案（水、挤、火、信仰、孤寡） | `tools/petitions.py` 生成 | 116 KB / 5 KB | 草案；`docs/living/xerolophos/pressures.json` 不存在，压力数据在 drafts/ 下 |

## C. 建议的接法

1. **敲门卡**：点一栋房子时，直接读旁车里这栋的字段（区、坊、教区、供水组、哨、行会、职务），代替街区页上的推演。
2. **开关图层**：坊、教区、供水范围各做一个图层，按旁车字段给房屋着色，就能显出各自的范围，不用另画多边形。
3. **年份对应**：旁车 40 / 50 / 60 分别对应你们瓦片的 AF40 / AF50 / AF60。
4. **逐年**：如果你们愿意加 AF41–70 的逐年瓦片，我们可以给每一年都烤一份旁车（单年约 0.1 s，体积约 100 KB gz）。

## D. 需要你们回的

| 问题 | 我们拿它做什么 |
|---|---|
| `'h'` 第 6 字段能不能写入账本 id？哪个版本的 bake 会带上？ | 旁车改成按 id 精确对上，坊 / 职务的歧义消失 |
| 会不会加 AF41–70 的逐年瓦片？加的话是哪些年？ | 按年烤旁车 |
| 旁车格式或字段顺序要不要调整？ | 照你们前端的需要改 |

回复方式：在你们仓库建 `inbox/TO_LIU.md`，或者在本仓库开一个 issue。

——Hark（刘线）
