# 刘线 → CS 主线同步（liu/cs-sync）

基于 CS main f4ba426（changsheng0804-blip/anthousa-hark-CS）。合并：`git fetch liu && git merge --ff-only liu/cs-sync`。
只加文件、只改一处页面（docs/living/xerolophos/index.html 末尾加 ECON 段 + 两行 CSS，包住 showCard 在卡片末尾懒插一段）。底账（world.json proposals rules chronicle engine）未动。

## 带了什么
| 路径 | 内容 | 体积 |
|---|---|---|
| liu/experiments/ | 刘线 24 个实验（rules_v0–v5、city_system_v6/v7、gov_frame_v8、social_foci_v9、social_v10–12、yamen_v13、economy_v14–v21、surface_v22–v23）的代码、REPORT.md、≤1 MB 的 results/json；大中间件见 liu/SOURCE.md | 15 MB |
| liu/tools/econ_pack.py | 生计/房况旁车装箱（照 reg_pack.py：按底账 id 取、原样不改、写 SOURCE.md） | — |
| liu/tools/check_econ.py | 旁车自检（id 在 world.json、40–70 覆盖、无空值、页面懒取/短句逐字一致） | — |
| liu/tools/shot_econ_card.py | 无头浏览器点房、看卡、截图、收 JS 报错 | — |
| docs/living/xerolophos/econ/ | g{id//64}.json 251 个（4,786 户 × AF40–70）+ chron.json（街道/港口/市集/教堂年表 105 KB）+ SOURCE.md | 12.6 MB（gzip 2.2 MB；单文件 ≤ 91 KB） |
| docs/living/liu6/ | 刘线干山页 BUILD liu6（91a16d3）整份快照 | 19.2 MB |

## 自检（cs-sync 上，2026-10-15）
- 新：check_econ ✅ 全过（短句比对 1,293 条 0 不一致；卡片 600 次出段 592，缺的 8 次是那一年账本没这户）。
- 无头点房（CS 干山页 AF40/50/60 各一栋）：卡里出「生计/房况」段，0 JS 报错，点开前 econ 请求 0 次、点 3 栋共取 2 个文件。
- CS 现有：check_reg、check_card、check_lives、check_talk、check_breadqueue、check_waterline、check_page（xerolophos / nangang 0 报错）、check_tiles、check_chron_page、check_traces、check_house_src、check_landmark_src、check_lm_city、check_nets、check_streets、check_dockpatch、check_epic_clear、check_heart ✅；accept.py xerolophos 9/10（唯一不过：CS 落后上游底账 4 个提交）。
- 不过、与本次无关（在干净的 CS f4ba426 上同样失败）：check_card_tile（nangang 心跳 household 读 undefined.B，56 项 ok 后抛错）、check_chronicle（3 句无地点）、check_zones（货栈长屋 0）。
- 没跑成：check_fleet/check_vein（要 CS 本地 /workspace/work/csjs/run_ng.js，仓库里没有）、check_palette（缺 cv2）、check_epic_stage（>115 s 超时）、check_citynet（要 frame.json，干山没有）、check_fly/zoom/tilt/hearts9、perf_*（重）。

## 已知问题
- 房况折旧偏高：AF70 干山破败 36.2%（全城 39.0%），待刘线 surface_v24 修折旧基数（敏感性：0.45→干山破败 531 栋、0.3→28）。
- AF61–70 无新生儿（刘线已知问题，未修）。
- 行当冲突 1,852 条：刘线页面旧文字与经济层行当对不上的，已隐藏或标 ⚠（见 liu6 快照 conflicts.json）；CS 页面的旧文字没动，这段只给经济层行当（手工铺/作坊才用页面原行当做细分）。
- 旁车只覆盖干山页的房子（底账 id = 页面 id）；全城旁车要重跑 surface 到全城，未做。CS 滑杆到 60，61–70 的旁车数据在但页面看不到。
——Hark（刘线）
