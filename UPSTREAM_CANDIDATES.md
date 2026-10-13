# 上游候选（待评估，只挑更好的手动 cherry-pick）
已审阅到：3cd473c8139d6f5afeb530d9c65cfba0e884c560
- aafed1c living v24: house system P1 — house_types.py is the one geometry source (row/domus/insula/yard/casa/std/hut/hall/flat), exported to houses_geom.json for the page; rows share one ridge and colour per street side; lots south of a street set back; audit now counts roof rise ——Hark
  → 不采纳：房屋几何/柱廊/房屋年龄外观，属谭线画面层，刘线户籍系统不依赖
- 3e1951b living v25: house system P2 — porticos with columns along row fronts (stalls under market ones), kitchen gardens behind homes, domus garden walls, flat terrace roofs with parapet; audit covers porticos (fixpo) ——Hark
  → 不采纳：房屋几何/柱廊/房屋年龄外观，属谭线画面层，刘线户籍系统不依赖
- d130869 living v26: house system P3 — houses live through years: timber frame the year after foundations, re-laid tiles and moss as roofs age, lean-to added in kitchen gardens, roof falls in the last 2 years before demolition (not for fire); geometry stage table + center-relative coords ——Hark
  → 不采纳：房屋几何/柱廊/房屋年龄外观，属谭线画面层，刘线户籍系统不依赖
- 279b940 living v27: open landmark typology — specs gen/landmarks/*.json + shape vocabulary landmark_shapes.py (basilica, steps), placed by landmarks.py with strict road audit; first: 2 bread steps on the market street, a church growing oratory -> hall+atrium -> basilica with apse; house card shows the landmark's name by stage ——Hark
  → 不采纳：地标类型与选址属画面层；其合并地块/拆房的空间事实若需要可日后经 facts_from_upstream 只读取用
- 911cee8 living v28: medium landmarks merge the neighbouring lot (parish buys the plot next door; that house comes down when the church starts); 3 churches now (7764, 5999+6240, 4651+5079); story/scene households protected; softer landmark shadow ——Hark
  → 不采纳：地标类型与选址属画面层；其合并地块/拆房的空间事实若需要可日后经 facts_from_upstream 只读取用
- e5e49be living v29: landmark siting fully spec-driven (fn/typ/front_on/prefer); new types fountain (nymphaeum exedra + basin), horrea (buttressed granary, lengthened after 12 yrs), inn (rooms round a yard + stable); 12 landmarks in Xerolophos, strict audit 0 ——Hark
  → 不采纳：地标类型与选址属画面层；其合并地块/拆房的空间事实若需要可日后经 facts_from_upstream 只读取用
