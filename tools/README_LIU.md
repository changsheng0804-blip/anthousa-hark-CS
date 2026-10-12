# 刘线 · 人家故事流水线（liu1）
1. `node tools/export_households.js docs/living/xerolophos > ../hh_all.json` —— 用页面自己的 household() 推演出每栋房子里的每一家（名字、生卒、出嫁、离家、行当、籍贯、信仰）。
2. `python3 tools/select_households.py 220 > ../briefs.txt` —— 选出干山上 1950–60 年间同一家人一直住着的房子，给每户指定一位讲述人（附近另一户里真实住着的人），写出 `tools/voices_selected.json` 和写作提要。
3. LLM 按提要分批写 `tools/batches/bNN.json`（街坊闲话体；三种写法的样本在 `tools/samples/`）。
4. `python3 tools/check_stories.py tools/batches/*.json` 逐条核对；不通过的重写。`--merge docs/living/xerolophos/voices.json tools/batches/b0*.json` 合并（未通过的自动丢弃）。
5. `python3 tools/smoke_voices.py http://localhost:8765/docs/living/xerolophos/ shot.png` 无头浏览器点房子自查。
页面读取 `voices.json`：只在那一家（fam = 搬进来的年份）还住着时显示；「此刻」只在故事最后一条之后、且提到的人都在家时显示；手写的 stories.json 优先。
