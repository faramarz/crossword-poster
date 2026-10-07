#!/usr/bin/env bash
# Build the synthetic sample (examples/sample_clues.csv) at 24x36 grey and 18x24 black, and refresh the README images in docs/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-out/sample}"
python3 -m crossword_poster build --clues examples/sample_clues.csv --size 24x36 --style grey  --out "$OUT/grey_24x36"  --title "My Crossword"
python3 -m crossword_poster build --clues examples/sample_clues.csv --size 18x24 --style black --out "$OUT/black_18x24" --title "My Crossword"
mkdir -p docs
cp "$OUT/black_18x24/18x24/A_black/poster.png" docs/sample_18x24_black.png
cp "$OUT/grey_24x36/24x36/C_grey/poster.png"   docs/sample_24x36_grey.png
echo "updated docs/sample_*.png"
