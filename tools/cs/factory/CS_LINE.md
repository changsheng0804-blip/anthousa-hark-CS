
/goal 2 第 11 轮（项 7b）：层改在 Worker 里建、瓦片从 Blob 解码、矢量 JSON 限流；飞行 53–56 FPS、最差 33–50 ms，G5 达线。

/goal 3 第 1 轮（项 1，并上游）：合并 origin/main 的 v24–v30 + 3D 管线（c72b1f3）。冲突逐处理由：① docs/living/xerolophos/scene.json——取上游整份（多行格式、新增 hgeom 指向 houses_geom.json），只补回 CS 线的 next→../nangang/，因为底账/内容以上游为准、链路是 CS 线自己的；② xerolophos/index.html 自动合并无冲突，上游的 geomHG（房子吃 houses_geom、按年份显示部件）和 CS 线各块、id="next" 按钮都保留。九块 accept 全过，check_tiles 0 错。

/goal 3 第 2 轮（项 1b、2、3 前半）：地标只认上游规格一个来源（lm_src.py 读 landmark_registry，scene_auto / places.py 用）；check_landmark_src.py 查位置 ≤ 8 像素、建成年、到期年、名字，修前 7 条不过、修后 0；CS 线自有地标和画布外的规格地标登记在 lm_pending.json 等所有者定；check_lives 的 null.hid 是检查挑错例子，已改。详见根目录 CS_LINE.md。

/goal 3 第 4 轮（项 6，年份轴）：瓦片页年份从 40/50/60 扩到 -657、-400、-200、0、10…70 共 11 个（tools/cs/factory/tile_years.py 一处定）。非关键年的地面由 ground_ng 出到 out/ground_y/（不进 docs），地标只留当年已建成的；tile_bake 整套年份一起烤，之后做内容哈希去重，meta.alias 记指向，页面 tileKey() 解析；瓦片 49 MB（去重省 25.7 MB）。部分年份南港一带无房子（10 年才起），check_tiles 据此放宽。注意：以后重烤必须整套年份一起烤（去重要看全部年份）。
