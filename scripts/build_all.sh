#!/usr/bin/env bash
# Build every size (18x24, 24x36, 36x48) and every style (grey, black, icons) from a clues file.
#   scripts/build_all.sh CLUES.csv [OUT_DIR] [TITLE] [extra `crossword-poster build` options...]
# Same as: crossword-poster build --clues CLUES.csv --size 18x24,24x36,36x48 --style all --out OUT_DIR --title TITLE
set -euo pipefail
CLUES="${1:?usage: build_all.sh CLUES.csv [OUT_DIR] [TITLE] [extra options]}"
OUT="${2:-out}"
TITLE="${3:-My Crossword}"
shift $(( $# < 3 ? $# : 3 ))
if command -v crossword-poster >/dev/null 2>&1; then CLI=(crossword-poster); else CLI=(python3 -m crossword_poster); fi
"${CLI[@]}" build --clues "$CLUES" --size 18x24,24x36,36x48 --style all --out "$OUT" --title "$TITLE" "$@"
