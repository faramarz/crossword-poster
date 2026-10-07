#!/usr/bin/env bash
# Rebuild the preview images in docs/ from the fictional birthday sample (examples/sample_birthday.csv):
#   docs/sample_24x36_grey.png, docs/sample_18x24_black.png and docs/sample_solution.png
#   scripts/build_sample.sh [WORK_DIR]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-out/docs-build}"
if command -v crossword-poster >/dev/null 2>&1; then CLI=(crossword-poster); else CLI=(python3 -m crossword_poster); fi
COMMON=(--clues examples/sample_birthday.csv --title "Alex's 50th Birthday Crossword"
        --subtitle "Clues from the people who love you" --png-width 1400)
"${CLI[@]}" build "${COMMON[@]}" --size 24x36 --style grey  --out "$OUT/grey_24x36"
"${CLI[@]}" build "${COMMON[@]}" --size 18x24 --style black --out "$OUT/black_18x24"
mkdir -p docs
cp "$OUT/grey_24x36/poster_24x36_grey_preview.png"   docs/sample_24x36_grey.png
cp "$OUT/black_18x24/poster_18x24_black_preview.png" docs/sample_18x24_black.png
cp "$OUT/grey_24x36/answer_sheet_letter.png"         docs/sample_solution.png
echo "updated docs/sample_*.png"
