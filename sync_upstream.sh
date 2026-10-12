#!/bin/sh
# Daily sync with tanxinhao line. Ledger/canon (world.json, proposals/, rules/, chronicle/, engine/) always follows upstream: one ledger, one history.
set -e
git fetch -q upstream
git merge --no-edit upstream/main || {
  for p in world.json proposals rules chronicle engine; do git checkout --theirs -- $p 2>/dev/null || true; git add -A $p 2>/dev/null || true; done
  git commit --no-edit
}
python3 engine/build_all.py >/dev/null && python3 engine/check.py
