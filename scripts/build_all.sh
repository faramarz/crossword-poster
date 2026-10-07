#!/usr/bin/env bash
# Build every size and every style (black, grey, icons) from a clue CSV, then verify.
#   scripts/build_all.sh CLUES.csv [OUT_DIR] [TITLE] [extra build options...]
# Equivalent to: python -m crossword_poster build --clues CLUES.csv --size 18x24,24x36,36x48 --style all --out OUT_DIR
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUES="${1:?usage: build_all.sh CLUES.csv [OUT_DIR] [TITLE] [extra options]}"
OUT="${2:-out}"
TITLE="${3:-My Crossword}"
shift $(( $# < 3 ? $# : 3 ))
cd "$ROOT"
python3 -m crossword_poster build --clues "$CLUES" --size 18x24,24x36,36x48 --style all --out "$OUT" --title "$TITLE" "$@"
