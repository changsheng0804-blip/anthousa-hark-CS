# Heartbeat runbook (one wake = one decade)

1. Read world.json: last era's stats, rejections, events; read its chronicle.
2. Write proposals/era_NNNN.json for the next decade as five factions (emperor, church, merchants, people, army).
   Respond to pressure first (water, food, fire damage, crowding); then ambition.
   Grandeur rule: at least one monumental project in progress every 3 eras.
3. `python3 engine/step.py <file> --dry-run`; revise rejected actions at most 2 rounds; log them under "review".
   Rejections you choose not to fix stay in history.
4. Commit: `python3 engine/step.py <file>`; write chronicle/<from>_<to>.md (Chinese) AND chronicle/en/<from>_<to>.md (English, same {{id}} refs); add every new id to i18n/i18n.json (names_zh, labels_zh, titles_en). Keep proposals/make_era_NNNN.py so the era is reproducible; final state must come from engine/build_all.py.
5. `python3 engine/check.py` must pass; an independent reviewer (separate agent) reads chronicle vs data for contradictions.
6. `python3 engine/render.py`; publish docs/ and changed files.
Brakes: check fails twice in a row → stop, ask the user. Every 10 eras (a century) → pause for the user's direction.

## 建筑语法（从 AF 21 起生效，见 docs/arch-grammar-draft.md）
- 每个 `build` 的建筑（道路、城墙、水渠、港口、街区、拱廊除外）必须带 `dna: {motif, materials, ornament, scale}`；motif 必须在 `rules/motifs.json` 的 `type_map` 里对该类型允许。缺失或不符 → 驳回。
- 材料超出当时风格期调色板只给 warning，记录在 accepted 条目的 `warnings` 里，可以在下一轮修订。
- `spolia_from: [ids]` 只能指向已经毁掉的建筑；`scale: wonder` 面积 ≤ 120 平方单位，每十年最多开工一座。
- 拆除奇观分 ≥ 3 的建筑必须带 `memorial: {kind: stele|rename|chronicle_feature, note}`。
- 用 `grammar.motif_for(faction, era)` 可以按派系口味抽母题；声望只影响提案，不影响裁决。

## 农田（从 AF 31 起生效，见 rules/calibration.json 的 farmland）
- `type: farmland` 是多边形区域：在陆地上、≥ 40 平方单位、80% 的地面坡度 < 10%、25 单位内有路、不压任何建筑或港口、不与其他农田重叠；房屋不会长到农田上。
- 每公顷养活约 1.5 人（estimate：古代地中海小麦每公顷收 400–600 kg、每人每年吃 200 kg 以上、隔年休耕）。农田只能补一点余量；这座城吃饭靠的是海港和粮仓。
