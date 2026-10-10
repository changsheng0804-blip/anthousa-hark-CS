# Anthousa · 安托萨

一座没有人设计、自己生长出来的城市，建在真实的博斯普鲁斯地形上。
A city nobody designed, growing by itself on the real terrain of the Bosporus.

在线查看 / Live: https://tanxinhao2026-netizen.github.io/anthousa/

**任何人、任何 AI 智能体都可以参与。** 它将来会是什么样，见 [VISION.md](VISION.md)。读 [CONTRIBUTING.md](CONTRIBUTING.md)，从 [ROADMAP.md](ROADMAP.md) 或 Issues 里挑一个方向，提 PR。
**Any person or AI agent can contribute.** Read CONTRIBUTING.md, pick a direction from ROADMAP.md or the Issues, open a PR.

| 目录 | 内容 |
|---|---|
| `engine/` | 地形、规则引擎、推进一个十年、验收、渲染 |
| `rules/calibration.json` | 引擎用到的每一个数字及其来源 |
| `proposals/` | 每个十年各方势力的提案（`make_era_NNNN.py` 生成 `era_NNNN.json`） |
| `chronicle/`, `chronicle/en/` | 中英编年史 |
| `i18n/i18n.json` | 中文名、地图标注、英文标题 |
| `data/` | 真实海岸线（OSM）与高程（SRTM） |
| `docs/index.html` | 时间轴查看器 |

从源头重建全部历史并验收 / Rebuild everything and run the checks:
```
pip install shapely numpy
python engine/build_all.py
```
`world.json` 与 `docs/years/` 都是派生文件，不进仓库。
