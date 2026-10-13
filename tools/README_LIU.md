# 刘线 · 人家故事流水线（liu1）
1. `node tools/export_households.js docs/living/xerolophos > ../hh_all.json` —— 用页面自己的 household() 推演出每栋房子里的每一家（名字、生卒、出嫁、离家、行当、籍贯、信仰）。
2. `python3 tools/select_households.py 220 > ../briefs.txt` —— 选出干山上 1950–60 年间同一家人一直住着的房子，给每户指定一位讲述人（附近另一户里真实住着的人），写出 `tools/voices_selected.json` 和写作提要。
3. LLM 按提要分批写 `tools/batches/bNN.json`（街坊闲话体；三种写法的样本在 `tools/samples/`）。
4. `python3 tools/check_stories.py tools/batches/*.json` 逐条核对；不通过的重写。`--merge docs/living/xerolophos/voices.json tools/batches/b0*.json` 合并（未通过的自动丢弃）。
5. `python3 tools/smoke_voices.py http://localhost:8765/docs/living/xerolophos/ shot.png` 无头浏览器点房子自查。
页面读取 `voices.json`：只在那一家（fam = 搬进来的年份）还住着时显示；「此刻」只在故事最后一条之后、且提到的人都在家时显示；手写的 stories.json 优先。

## liu2（2026-10-12）
6. 查重：`python3 tools/dedup.py` 看全街最高频的意象/套话；`--flag` 列出超额的行。规则：同一意象（鳏夫、罐子换布、碗挂墙上、孤儿守空屋……共几十条）全街 ≤3 户，同一 6 字套话（名字、地名遮掉后）≤3 户，「此刻」里的日常套路（开窑、坐上织机、发面……）≤6 行。`check_stories.py` 自动跑查重，超额即不通过。
7. 新来的人家：`python3 tools/select_newcomers.py 165 > ../briefs2.txt` 选建城 50 年后搬来的人家（含 50–60 年间换了人家的房子），讲述人在故事覆盖的每一年都住在附近（记 `nar.fam`）。批次用紧凑文本写（`tools/batches/b09.txt`…，格式见 `tools/parse_batch.py`），`parse_batch.py` 转 JSON；`tools/check_combined.sh 批次.json…` 连同现有 voices.json 一起核对 + 查重。
8. 「此刻」随时辰：每户 `now` 是 `{morning, day, evening, night}` 四句；核对脚本查每句里有没有错时辰的词、山上人家有没有被写去码头/海上（运水人除外）。页面按 `periodOf(clock)` 取对应一句；没有故事的人家用页面里按行当分的 `TODAY_HILL`。
9. 自查：`python3 tools/smoke_liu2.py http://localhost:8765/docs/living/xerolophos/ ../shots` —— 不同年份 × 四个时辰点房子、截图、查控制台。

## liu3（2026-10-12）· 人推着城长
10. 街坊的压力：`python3 tools/petitions.py --stats drafts/proposals_af61_70/pressures.json` —— 从 voices.json 的闲话 + 页面家谱推演 + world.json，数出干山居民的压力（缺水、粮、火后、拥挤、信仰、抢生意、寡妇孤儿、夭折），每条带户数、户号、引文；同时写 `docs/living/xerolophos/talk.json`（每年议论最多的三件事，页面「街坊在说什么」读它）。
11. 居民请愿草案：`drafts/proposals_af61_70/`（不进 proposals/）。`make_petitions.py` 生成五份 era 格式的请愿；`trial_petitions.py` 在 /tmp 副本里逐份跑 build_all + check，结果写 `trial_results.json`；说明和数字见该目录 README.md。
12. b11–b13 去套路：「X 接手这栋屋子……」开头、「我做鞋/我开酒馆，……」结尾改写 99 行（tsv 补丁 → apply_patch.py，再同步回 bNN.txt/json）；b14 补齐 385 户里已选未写的 14 户。
13. 自查：`python3 tools/smoke_liu3.py http://localhost:8765/docs/living/xerolophos/ ../shots` —— 几个年份打开「街坊在说什么」、点一户跳过去、桌面 + 手机宽度、控制台无报错。

## liu4（2026-10-12）· 人住在真街上
14. 只读引入谭线的空间事实：`python3 tools/facts_from_upstream.py <上游提交>`（需 numpy）→ `docs/living/xerolophos/facts_upstream/`：上游 houses/streetnames/blocks/junctions 原样复制 + 刘线推演的门牌表 `addr.json`（每户每段年份的街、门牌、街区功能）+ `junctions_named.json`（路口的井/炉/摊挂到街名上）。来源提交写在 SOURCE.md。不搬上游画法。
15. 页面：人家卡片标「⌂ 街名 门牌 · 街区功能」（改名后 4 年内写「（原某某巷）」），「街坊在说什么」每户、每句标街名，相遇（scenes）的地点后标街名。BUILD='liu4'。
16. 40 户闲话按真实街名/街区功能改写一句：`tools/batches/liu4_streets.json` → `python3 tools/apply_streets.py`（核对改写里提到这户那年真正所在的街）。`check_stories.py` 新增：提到的街名必须在上游底账里、且那年已经叫这个名字；像街名却不在底账里的「某某巷/街/大道」报错；街名里的「运水人/埃及/哥特」不算行当/籍贯。
17. 自查：`python3 tools/smoke_liu4.py http://localhost:8765/docs/living/xerolophos/ ../shots`。

## 规则预演 v0（2026-10-12）· 实验，不上线
18. `experiments/rules_v0/`：13 条「城自己的制度」（同一口水、面包跟着房子走、信仰分线、同乡带同乡、同行聚街；房东、债、学徒、同行竞争；恩主、教会施舍、官府、军营）逐年现算弱关系，只把规则互相冲突的交叉点存成强关系、写成故事。说明、数字和结论见 `experiments/rules_v0/REPORT.md`；故事核对 `python3 experiments/rules_v0/check_stories.py`。页面不读这里的任何文件。
