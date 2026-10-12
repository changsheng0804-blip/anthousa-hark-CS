# CS 线 · 街区生产线

目标：用底账「长」出一个新街区，人只做一件事——挑。

```
底账 world.json ──grow.py──▶ 街区数据 + 引擎草图（每栋房子、路、港、公共建筑、火烧地，逐栋对齐）
        │
        └─ 草图 + 已有画作的风格 ──AI 画师（并行 N 张）──▶ 候选画
                                                    │
                       critic.py 自动评分（房子命中率 / 空地干净度 / 水 / 火烧地）
                                                    │
                       reroof.py：从 AI 画里剪下屋顶当零件，按底账一栋一栋铺回去
                                                    │
                       页面（同一份 index.html，scene.json 换一个街区）──▶ 所有者：留 / 再来
```

## 一个街区怎么长出来（南港是第一个）
1. `python engine/build_all.py` —— 从提案重建 world.json。
2. `python tools/cs/factory/grow.py nangang 445 418 40 50 60` —— 截世界框（128×144，与已有街区同比例），出 houses.json、frame.json、每个关键年代的草图 base_Y.png。约 3 秒。
3. 每个关键年代把草图 + 风格参考图交给 AI 画师，各画 2 张（提示词要点：每个红块就是一栋房子、位置不许动；火烧地、港、公共建筑按草图）。
4. `python tools/cs/factory/critic.py nangang 50 候选1.png 候选2.png …` —— 选分高的，再用眼睛看一眼。
5. `python tools/cs/factory/reroof.py nangang 50 候选.png ng_af50.jpg` —— 屋顶归位到底账。约 5 秒。
6. 写 scene.json（关键年代、标题、此刻滚动条）和 city.json 的地标（名字和故事只用 chronicle 里有的事实）。
7. `node tools/cs/check_talk.js`（把目录换成新街区）—— 每扇门的回答零空值。

## 南港第一次的分数（critic.py，houses = 命中率与空地干净度的调和平均）
| 画 | houses | 说明 |
|---|---|---|
| 上游干山 40 / 50 / 60 年（人工挑过的 AI 画） | 0.66 / 0.80 / 0.74 | 基准 |
| 南港 40 / 50 / 60 年（生产线出品） | 0.86 / 0.89 / 0.89 | 6 张候选里各挑 1 张，屋顶归位 |

人工：0 行手写坐标、0 次手工修图；所有者只需要看最后的页面。
