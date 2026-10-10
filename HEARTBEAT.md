# Heartbeat runbook (one wake = one decade)

1. Read world.json: last era's stats, rejections, events; read its chronicle.
2. Write proposals/era_NNNN.json for the next decade as five factions (emperor, church, merchants, people, army).
   Respond to pressure first (water, food, fire damage, crowding); then ambition.
   Grandeur rule: at least one monumental project in progress every 3 eras.
3. `python3 engine/step.py <file> --dry-run`; revise rejected actions at most 2 rounds; log them under "review".
   Rejections you choose not to fix stay in history.
4. Commit: `python3 engine/step.py <file>`; write chronicle/<from>_<to>.md (Chinese, {{id}} refs only to real structures).
5. `python3 engine/check.py` must pass; an independent reviewer (separate agent) reads chronicle vs data for contradictions.
6. `python3 engine/render.py`; publish docs/ and changed files.
Brakes: check fails twice in a row → stop, ask the user. Every 10 eras (a century) → pause for the user's direction.
