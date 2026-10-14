
/goal 2 第 11 轮（项 7b）：层改在 Worker 里建、瓦片从 Blob 解码、矢量 JSON 限流；飞行 53–56 FPS、最差 33–50 ms，G5 达线。

/goal 3 第 1 轮（项 1，并上游）：合并 origin/main 的 v24–v30 + 3D 管线（c72b1f3）。冲突逐处理由：① docs/living/xerolophos/scene.json——取上游整份（多行格式、新增 hgeom 指向 houses_geom.json），只补回 CS 线的 next→../nangang/，因为底账/内容以上游为准、链路是 CS 线自己的；② xerolophos/index.html 自动合并无冲突，上游的 geomHG（房子吃 houses_geom、按年份显示部件）和 CS 线各块、id="next" 按钮都保留。九块 accept 全过，check_tiles 0 错。
