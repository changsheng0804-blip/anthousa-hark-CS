
## cs38 街巷级贴图（第 5 轮）
街巷级横穿全城 29.7→58.8 FPS，最差帧 100→33–50ms：瓦片层离屏缓存 + 镜头余量 + 每帧只画一层 + 人生成限流（docs/living/tiles/index.html）。

## /goal 2 第 1 轮：check_zoom
全城推到门口的自动检查 tools/cs/check_zoom.py：200 步缩放、每步两帧就截图，查空白（品红探针）和跳变冒尖。现状：空白帧 60（粗级瓦片自带透明洞）、冒尖 4 处（三次换级 + 换街巷级）。结果在 tools/cs/factory/out/zoom/zoom.json。


## /goal 2 第 5 轮（项 3 弧线飞行）
flyTo(x,y,z,{year}) 走 van Wijk 曲线，沿路预取，落地等 pending()=0；tiles/places.json（places.py）= 31 座地标 + 九块中心 + 48 年大火；点图上圆点或下拉「飞去…」即飞；滚轮走同一个动画器。检查 tools/cs/check_fly.py（--set quick|all|edge）。修了街巷级换年份整屏品红（prepStreet 等地面）。——Hark（CS线）
