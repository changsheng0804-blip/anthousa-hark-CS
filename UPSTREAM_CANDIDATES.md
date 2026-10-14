# 上游候选（待评估，只挑更好的手动 cherry-pick）
已审阅到：c72b1f3655129c5c4798daa9630fbbe12ad980d4（上一次：e5e49be）
详见 SYNC_2026-10-13.md。

- a473bc0 living v30: historic landmarks (cisterns, baths, barracks, city gate, aqueduct bridge, Arian meeting yard) migrated to spec cards in tools/landmarks; landmark_registry.py is the single source …
  → 取（空间事实，只读）：tools/landmarks/*.json 规格卡 + 上游 v24–v30 累积的街名/地块/街区/路口事实，经 tools/facts_from_upstream.py 落到 docs/living/xerolophos/facts_upstream/（新增 landmarks.json）。v30 的画面层（docs/living/v30/、贴图、kits、scenes、landmark_registry/landmarks.py/streets_xero/district_rules 生成代码）不取。
- c72b1f3 merge from branches: b2 standby 3D pipeline (docs/3d.html viewer, engine/export_to_sim3d.py, RFC, Blender hillshade tool; Pages builds anthousa_world3d.json after build_all) + persons-layer schema doc …
  → 部分取：docs/persons-schema.md（人物层 schema，户籍系统将来对接上游人物层的格式依据）原样取自 c72b1f3；engine/export_to_sim3d.py 已随账本目录同步。docs/3d.html、docs/rfc-3d-pipeline.md、tools/bake_hillshade_blender.py、.github/workflows/pages.yml、.gitignore 改动不取（3D 表现层，刘线制度系统不依赖）。
