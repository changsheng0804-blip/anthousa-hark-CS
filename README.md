# Anthousa · 安托萨

一座没有人设计、自己生长出来的城市。

- `engine/terrain.py` 地形（种子 330，决定海岸、金角湾与七丘）
- `engine/rules.py` 规则引擎：AI 提议，代码裁决
- `engine/step.py` 推进一个十年：裁决提案 → 房屋沿街生长 → 掷骰（火灾/地震/瘟疫）
- `engine/check.py` 验收：世界一致性 + 编年史引用必须对得上数据
- `engine/render.py` 渲染每个年代的地图与 `docs/data.json`
- `proposals/` 每个十年各方势力的提案（含被驳回后的修改记录）
- `chronicle/` 编年史
- `docs/index.html` 时间轴查看器（本地：`cd docs && python3 -m http.server`）

重建全部历史：
```
python3 engine/genesis.py
for f in proposals/era_*.json; do python3 engine/step.py $f; done
python3 engine/check.py && python3 engine/render.py
```
