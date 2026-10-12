#!/bin/sh
# check new batches against the ledger, and repetition across voices.json + batches
python3 tools/check_stories.py docs/living/xerolophos/voices.json "$@"
