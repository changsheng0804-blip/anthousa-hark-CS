
## cs38 街巷级贴图（第 5 轮）
街巷级横穿全城 29.7→58.8 FPS，最差帧 100→33–50ms：瓦片层离屏缓存 + 镜头余量 + 每帧只画一层 + 人生成限流（docs/living/tiles/index.html）。

## /goal 2 第 1 轮：check_zoom
全城推到门口的自动检查 tools/cs/check_zoom.py：200 步缩放、每步两帧就截图，查空白（品红探针）和跳变冒尖。现状：空白帧 60（粗级瓦片自带透明洞）、冒尖 4 处（三次换级 + 换街巷级）。结果在 tools/cs/factory/out/zoom/zoom.json。

