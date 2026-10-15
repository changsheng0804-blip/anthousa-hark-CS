# liu/ — 刘线成果（带进 CS 主线的部分）

来源：刘线 fork https://github.com/liuzhijie820802-a11y/anthousa-liuzhijie ，main @ 91a16d3（2026-10-15）。目录 `experiments/` 原样搬到 `liu/experiments/`，只带代码、REPORT.md、小的 results/json（每文件 ≤ 1 MB）。
底账（world.json、proposals、rules、chronicle、engine）一律不动，跟谭线。

## 怎么重跑

脚本里的路径按刘线仓库根写（`experiments/<名>/...`、`docs/living/xerolophos/...`），在 CS 仓库里直接跑会找不到中间件。重跑：
```
git fetch liu && git worktree add /tmp/liu liu/main   # 或 git clone https://github.com/liuzhijie820802-a11y/anthousa-liuzhijie
cd /tmp/liu && python3 experiments/<名>/<脚本>.py        # 各目录 REPORT.md 写了入口和参数
```

链条：city_system_v6 → v7_streets → gov_frame_v8 → social_foci_v9 → social_v10–v12；yamen_v13（门牌户籍）→ economy_v14–v21（经济流）→ surface_v22–v23（街面）。rules_v0–v5 是更早的规则预演。

## 各实验（首/末提交）

| 实验 | 首次 | 最后 | 末次说明 |
|---|---|---|---|
| city_system_v6 | c28cd3c  | d3b1cc4  | city_system_v6/tiles_join：CS 瓦片房屋→账本 id 对接（18,151/18,373 匹配，… |
| city_system_v7_streets | 962f21e  | 962f21e  | city_system_v7_streets：空间依据换成逐年街道网络（账本道路19条+上游街名仿射补细，AF70门口账… |
| economy_v14 | 3b5f502  | 3b5f502  | economy_v14：门牌户籍+官府之上的经济流——每户一种生计（上游第9栏 4,578 户，其余同坊/同街/距离推断… |
| economy_v15 | e02fa56  | e02fa56  | economy_v15：三部门替代宫廷采购——港口转口（600 船×600 份，关税 10% 1/3 留城，装卸/仓储/… |
| economy_v16 | 8034184  | 8034184  | economy_v16：劳动市场（工位=劳动需求，工钱 3.0–4.5 全城出清，港口→区内→跨区→公役→码头零工）、面… |
| economy_v17 | 33ce749  | 33ce749  | economy_v17：营收回到真实需求（修房 ≤ 维护需求 V_h×2%×房数、添置 ≤ 2×基本开支、超出部分外购奢… |
| economy_v18 | 592fa5c  | 592fa5c  | economy_v18：冲击缓冲——储备库（平年截留皇库关税 15% 存城里，上限 20,000；到港 <80% 基线触… |
| economy_v19 | 87880d4  | 87880d4  | economy_v19：缓冲的退出与上限——触发后强度 1.0/0.75/0.4 逐年递减延续、扩招按就业缺口（剩余无工… |
| economy_v20 | d084fe1  | d084fe1  | economy_v20：剩余贫困两块——先用 v19 AF70 重诊（净<线 1,829：手工铺 631/2,105、体… |
| economy_v21 | 25d9843  | 25d9843  | economy_v21：手工需求内生（日常必需 q_craft 0.5→0.3 + 上年净收入分档边际消费 4.5/8/… |
| gov_frame_v8 | 3fb83a6  | 3fb83a6  | gov_frame_v8：政府架构规则成数据（offices.json 14 类职位/上级/辖区由 v7 推出/职权/资… |
| rules_v0 | e3db9b8  | e3db9b8  | rules_v0 规则预演（实验，不上线）：13 条城自己的制度逐年现算弱关系，交叉点存强关系；干山样本 85 栋→干山… |
| rules_v1 | dcd73d7  | dcd73d7  | rules_v1 规则预演优化（实验，不上线）：不生成边、直接找交叉点（户状态矩阵 + cKDTree 组内近邻 + 同… |
| rules_v2_econpol | 949cacf  | 949cacf  | rules_v2_econpol 经济政治骨架预演 + 反过来推演对账（实验，不上线）：星形骨架每户每年 3.16 条边… |
| rules_v3_registry | 302521f  | 302521f  | rules_v3_registry 户籍册 + 治理分层预演（实验，不上线）：页面干山对全城账本房屋中位 8.8px，横… |
| rules_v4_fiscal | 6e3d1e4  | 6e3d1e4  | rules_v4_fiscal 财政层预演（实验，不上线）：五棵树（粮/民政钱/教会/行会/兵营）逐节点 收=上交+留存… |
| rules_v5_succession | 3742120  | 6bc6c29  | rules_v5_succession 第二段：许可链 D_u=1.5 年校准请愿 62–65；8 机制重跑请愿/偏袒/… |
| social_foci_v9 | da9df34  | d082dfe  | v9 REPORT：更正闭合来源占比 ——Hark（刘线）… |
| social_v10 | 1937b25  | 1937b25  | social_v10：亲属（子户分出成链 11,240 户/亲属对 65,721）+婚姻（22,206 门，AF52 后… |
| social_v11 | a761de5  | a761de5  | social_v11：Dunbar 层靶改按户（5/15/50/150 人 ÷2.2 人/户 → 3/7/23/68 户… |
| social_v12 | bb8886b  | bb8886b  | social_v12：市场关系改为常客群（市场节点下按方位扇区×距离环分群，信仰/行会同质拆分，跨年稳定；认识层市场关系… |
| surface_v22 | f64ab4c  | f64ab4c  | surface_v22：经济层→街面——页面房屋 id = 账本 h<id>（AF40–60 匹配 100%，AF65/… |
| surface_v23 | 91a16d3  | 91a16d3  | surface_v23：行当统一——页面行当一律读经济层逐年生计（economy_v21 骤降路径 AF40–70 每年… |
| yamen_v13 | bf28595  | bf28595  | yamen_v13：门牌×户籍×官府——v7 街网逐户编门牌（沿街起编、左单右双假设、上游号能对上就用、新房 12A 式… |

## 没带的大中间件（> 1 MB、.gz、.pkl/.npz）

都在刘线 main @ 91a16d3 的同一路径下；需要时 `git show liu/main:<路径>` 取，或照对应 REPORT.md 重跑生成。

- **economy_v14**：`flows_AF40.json.gz` 0.60 MB；`flows_AF50.json.gz` 0.91 MB；`flows_AF60.json.gz` 1.02 MB；`flows_AF70.json.gz` 1.08 MB
- **economy_v15**：`flows_AF40.json.gz` 0.69 MB；`flows_AF50.json.gz` 1.11 MB；`flows_AF60.json.gz` 1.22 MB；`flows_AF70.json.gz` 1.32 MB
- **economy_v16**：`flows_AF40.json.gz` 0.77 MB；`flows_AF50.json.gz` 1.19 MB；`flows_AF60.json.gz` 1.30 MB；`flows_AF70.json.gz` 1.40 MB
- **economy_v17**：`flows_AF40.json.gz` 0.78 MB；`flows_AF50.json.gz` 1.19 MB；`flows_AF60.json.gz` 1.32 MB；`flows_AF70.json.gz` 1.44 MB
- **economy_v18**：`flows_AF40.json.gz` 0.78 MB；`flows_AF50.json.gz` 1.19 MB；`flows_AF60.json.gz` 1.32 MB；`flows_AF70.json.gz` 1.44 MB
- **economy_v19**：`flows_AF40.json.gz` 0.78 MB；`flows_AF50.json.gz` 1.19 MB；`flows_AF60.json.gz` 1.31 MB；`flows_AF70.json.gz` 1.42 MB
- **economy_v20**：`flows_AF40.json.gz` 0.78 MB；`flows_AF50.json.gz` 1.18 MB；`flows_AF60.json.gz` 1.30 MB；`flows_AF70.json.gz` 1.41 MB
- **economy_v21**：`flows_AF40.json.gz` 0.80 MB；`flows_AF50.json.gz` 1.27 MB；`flows_AF60.json.gz` 1.33 MB；`flows_AF70.json.gz` 1.42 MB
- **gov_frame_v8**：`graph_AF40.json.gz` 0.67 MB；`graph_AF50.json.gz` 0.91 MB；`graph_AF60.json.gz` 1.06 MB；`graph_AF70.json.gz` 1.13 MB
- **social_foci_v9**：`ties_AF40.json.gz` 0.88 MB；`ties_AF50.json.gz` 1.27 MB；`ties_AF60.json.gz` 1.45 MB；`ties_AF70.json.gz` 1.55 MB
- **social_v10**：`lost_neighbors.json.gz` 0.18 MB；`ties_AF40.json.gz` 4.32 MB；`ties_AF50.json.gz` 5.98 MB；`ties_AF60.json.gz` 6.61 MB；`ties_AF70.json.gz` 7.08 MB
- **social_v11**：`ties_AF70.json.gz` 2.56 MB
- **social_v12**：`ties_AF70.json.gz` 2.35 MB
- **yamen_v13**：`addr_history.json.gz` 0.15 MB；`offices_seated.json` 1.09 MB；`registry_AF40.json.gz` 0.20 MB；`registry_AF50.json.gz` 0.27 MB；`registry_AF60.json.gz` 0.30 MB；`registry_AF70.json.gz` 0.34 MB

另：surface_v23 本地中间件 `.path/flows_AF40…70.json.gz`（economy_v21 骤降路径逐年流，约 30 MB）未入库，由 `experiments/surface_v23/path_run.py` 重跑生成。

## 带进 CS 页面的东西

- `docs/living/xerolophos/econ/`：生计/房况旁车（liu/tools/econ_pack.py 生成，来源见 econ/SOURCE.md）；CS 干山页敲门卡点开才取。
- `docs/living/liu6/`：刘线干山页 BUILD liu6（91a16d3）整份快照。
- `liu/tools/check_econ.py`：旁车自检；`liu/tools/shot_econ_card.py`：无头点房截图。

——Hark（刘线）
