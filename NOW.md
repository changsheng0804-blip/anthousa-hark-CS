# NOW · CS 线现在到哪了

> 只覆盖不追加。接手的智能体先读这页，再读 AGENTS.md。历史看 git log、CS_LINE.md、tools/cs/factory/verdicts.json。
> 最后更新：2026-10-18 22:40 CST ——Hark（CS线）

## 方向（主人 2026-10-17 定）
底账 → 节点 → 渲染器（学 WorldGacha）：节点按顺序、可重抽，中间层是 OSM 形状 + 年份，近/远/地平线分层，一个渲染器。AI 写生成器和部件，不画内容。拆解见 tools/cs/nodes/README.md。

## 已有成品（南港一块，全链路跑通）
| 成品 | 地址 | 证据 | 主人 |
|---|---|---|---|
| 节点样板 nodes1 | docs/living/nodes/nangang/index.html | 无机器验收，perf 基线见 tools/cs/nodes/README.md | 留（「效果好多了」）|
| 长卷 scroll1 | docs/living/nodes/nangang/scroll.html | 无机器验收 | 留（「确实好不少」）|
| 路网节点 net.py | scroll.html?n=net | net_report.json：5163/5163 户入街，pass | 待评 |
| 水系节点（水道桥/蓄水池/井） | scroll.html | water_report.json | 待评 |
| 3D 试作 | docs/living/nodes/nangang/3d.html | 无 | 待评 |

灰度入口：docs/living/next/（主页加 ?flag=nodes-nangang 才露入口）。

## 进行中
- 居民试作（主人 10-18「试试看」）：不写人，写行为。tools/cs/people/people.py 从底账挑五个人（老渔夫=尤利安港栈桥边住得最久的一户；商人=主街带柱廊最高的铺面；挑水的女人=坡上、喷泉在下坡 50–120 米、高差最大的民居；孙子跟着渔夫；搬运工=亚历山大粮仓↔最近栈桥），推出步态/负重/一天五段/同伴/地位，写 nangang/people.json；nodes/people/people.js 用关节人形照着演。入口 scroll.html?n=net&people=1（灰度位有链接），页面无字，?key=1 看答案。修士换成了搬运工：南港底账里没有教堂。Mac M4 实测 100 fps。等主人做无字测试。

## 等主人
- 南港节点版「留」还是「再来」；留了就切成线上南港。
- 2D 长卷还是 3D 继续走。

## 下一步（主人点头后）
- 节点链往外长一块街区，验证跨街区接缝从结构上消失。
- 给长卷和 3D 补机器验收（在主人 Mac 上测帧率、截图）。
