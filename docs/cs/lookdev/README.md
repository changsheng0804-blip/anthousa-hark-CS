# 南港 lookdev（CS 线）

学 Leonxlnx/athenaion 的工作流：参考图 → 美术圣经 + 模块契约 → 各模块并行「改 → 渲染 → 和参考比数字」。

- `ART_BIBLE.md` 光、色、材质、密度、年代规矩，每个机位必须读成什么
- `MODULE_CONTRACT.md` 模块拆分、各自的文件/输入/边界/自查机位、预算、一轮怎么跑
- `refs/` 4 张参考图（AI 生成，已按底账核过：南港没有教堂）
- `baseline/` 第 1 轮基线：`render/` 渲染图、`cmp_shotN.jpg` 并排图、`overview.jpg` 总览、`stats.json` 数字、`report.md` 差距排名和第 2 轮分工
- 机位：`docs/living/nodes/nangang/shots.json`；工具：`tools/cs/lookdev/render.py`、`tools/cs/lookdev/compare.py`
