# 生计/房况旁车 econ/g{id//64}.json + chron.json

来源：刘线（liuzhijie820802-a11y/anthousa-liuzhijie）liu/main 91a16d3，docs/living/xerolophos/surface_AF40…70.json + trades.json；数值原样取，未改。
- 经济层：experiments/economy_v21（25d9843）骤降路径（AF65 到港 ×0.3）逐年流；表面层：experiments/surface_v22（f64ab4c）+ surface_v23（91a16d3）。
- 行当以经济层为准（surface_v23 trades.json：每栋每年生计码，40 年前按 40 年回推）；手工铺/作坊的细分（陶匠/织工/鞋匠/铜匠）以页面原散列行当为准，旁车只给经济层用语。
- 房况 = 存量四档（折旧 0.6×(0.6+0.8×房龄/60)×(1+0.5×(1−C/V))、修房按栋摊回、档界 0.90/0.75/0.55）。**已知偏高：AF70 干山破败 36.2%（全城 39.0%），折旧基数待 surface_v24 修。**
- 「为什么」短句：旁车带模板（why，取自 surface_AF*.json）和所需数字，页面按刘线 surfWhy 逐字拼；liu/tools/econ_why_sample.json 是 Python 端生成的抽样，check_econ 比对。
- 覆盖：干山页面房屋（底账 id = 页面 id，AF40 2,638 户 → AF70 4,605 户，含账本 AF61–70 新建 208 栋）；这里没有的房子敲门卡不显示这一段。
装箱：liu/tools/econ_pack.py 按底账 id//64 分组，每组一个文件；CS 干山页只在敲门卡点开时才取这栋房所在组的一个文件。
重跑：python3 liu/tools/econ_pack.py（默认 git archive liu/main）。
