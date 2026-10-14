
## cs38 街巷级贴图（第 5 轮）
街巷级横穿全城 29.7→58.8 FPS，最差帧 100→33–50ms：瓦片层离屏缓存 + 镜头余量 + 每帧只画一层 + 人生成限流（docs/living/tiles/index.html）。

## /goal 2 第 1 轮：check_zoom
全城推到门口的自动检查 tools/cs/check_zoom.py：200 步缩放、每步两帧就截图，查空白（品红探针）和跳变冒尖。现状：空白帧 60（粗级瓦片自带透明洞）、冒尖 4 处（三次换级 + 换街巷级）。结果在 tools/cs/factory/out/zoom/zoom.json。


## /goal 2 第 5 轮（项 3 弧线飞行）
flyTo(x,y,z,{year}) 走 van Wijk 曲线，沿路预取，落地等 pending()=0；tiles/places.json（places.py）= 31 座地标 + 九块中心 + 48 年大火；点图上圆点或下拉「飞去…」即飞；滚轮走同一个动画器。检查 tools/cs/check_fly.py（--set quick|all|edge）。修了街巷级换年份整屏品红（prepStreet 等地面）。——Hark（CS线）

## /goal 2 第 6 轮（项 4a 心跳接到瓦片页）
tools/cs/factory/tile_heart.py <q> 把街区页的粮船日、家户推演一字不改地剪成 docs/living/tiles/heart/<q>.js，瓦片页进街区框且到街巷级才载入；炊烟跟房子走；右上角时钟。检查 tools/cs/check_heart.py（南港：船、人不下水、炊烟、节律、退出不画）。街区页改了心跳段，重跑 tile_heart.py。下一轮：4b 敲门卡。

## /goal 2 第 7 轮（项 4b 敲门卡接到瓦片页）
tile_heart.py 现在连卡片一起剪（renderCard、cs1 敲门问话、cs2 跟一个人走一生，原样），heart/<q>.js 返回 openHouse/cardClick/nearestHouse 等；瓦片页点街巷级的房子开 #card，选中圈跟着，年份可跳到任意一年。检查 tools/cs/check_card_tile.py（含与街区页逐字比对）。同时修了街区页 csIncoming 对建成年>60 的房子抛错（九块 index.html 都改了一处），并把 FLEET.crowd / csIncoming 改成可分帧（生成器，街区页同步调用不变）。

## /goal 2 第 10 轮（项 7a perf 飞行场景 + 第一刀优化）
perf_tiles.py 加「全城→南港门口」「南港门口→第四丘门口」（z=4.5 倾斜带）和「倾斜带平移」三个场景，FPS 取飞行期间 rAF 均值。查出飞行慢的四个真因（每帧整层重画、大瓦片首绘同步解码 123 ms、2 核机器上预取解码饿住主线程、预取每帧扫），改后冷飞 33/24→42/39 FPS，最差帧 183/117→67 ms；飞行途中旧层拉伸（只在飞行里，步进缩放不拉伸，否则 check_zoom 冒尖）。离 G5 的 ≥50/≤50 还差：落地等瓦片时现建 zr=4 的大层。下一轮做 7b。

## 第 13 轮 收口（/goal 2）
九块 --live 全过，perf 飞行 53–54 FPS，G1–G5 达标，共 13 轮。

## /goal 3 第 5 轮（项 7 事件落点接进瓦片页）
编年史事件（events.json，58 件）经 places.py 进 places.json，每件带 show_year；瓦片页里事件跟年份淡入淡出、点一下 flyTo 并切年、出卡（编年史原文）；年份轴 #yrs 是能拖的 range。检查 tools/cs/check_chron_page.js，由 check_chronicle.py 调。

