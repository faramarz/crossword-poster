#!/usr/bin/env bash
# Download the fonts used by the renderers from github.com/google/fonts (all SIL OFL 1.1), together with each
# family's OFL.txt, into fonts/<Family>/.
#
#   scripts/fetch_fonts.sh            # only what is missing: Playfair Display + Source Serif 4 (classic renderer)
#   scripts/fetch_fonts.sh --all      # also (re)download the four families that are already committed
#
# The newspaper renderer (the main one) needs only Archivo Narrow + Oswald, which are committed in fonts/.
# The classic renderer (styles A/B/M) also needs Playfair Display, Source Serif 4 (both have a Reserved Font Name,
# so they are fetched and instanced locally rather than redistributed here), Bebas Neue and DM Sans.
#
# Requirements: curl, python3 with fonttools (pip install fonttools).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONTS="$ROOT/fonts"
RAW="https://raw.githubusercontent.com/google/fonts/main/ofl"
ALL=0; [[ "${1:-}" == "--all" ]] && ALL=1

get() { curl -sS -f -L --retry 3 -o "$2" "$1"; }

# ---- families with statics that are fetched as-is (only with --all) --------------------------------------------
if [[ $ALL == 1 ]]; then
  mkdir -p "$FONTS/BebasNeue" "$FONTS/Oswald" "$FONTS/ArchivoNarrow" "$FONTS/DMSans"
  get "$RAW/bebasneue/OFL.txt" "$FONTS/BebasNeue/OFL.txt"
  get "$RAW/bebasneue/BebasNeue-Regular.ttf" "$FONTS/BebasNeue/BebasNeue-Regular.ttf"
  get "$RAW/oswald/OFL.txt" "$FONTS/Oswald/OFL.txt"
  get "$RAW/archivonarrow/OFL.txt" "$FONTS/ArchivoNarrow/OFL.txt"
fi

# ---- variable fonts -> static instances (Chromium embeds real TrueType instead of Type 3) -------------------------
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fetch_var() {   # dir  url-name  local-name
  mkdir -p "$FONTS/$1"
  get "$RAW/$2/OFL.txt" "$FONTS/$1/OFL.txt"
  get "$RAW/$2/$3" "$TMP/$4"
}
instance() {    # src-file  out-dir  out-name  axis=value ...
  python3 - "$@" <<'PY'
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
src, outdir, name, *axes = sys.argv[1:]
f = TTFont(src)
loc = {k: float(v) for k, v in (a.split("=") for a in axes)}
for tag in [a.axisTag for a in f["fvar"].axes if a.axisTag not in loc]:
    loc[tag] = [a.defaultValue for a in f["fvar"].axes if a.axisTag == tag][0]
instancer.instantiateVariableFont(f, loc, inplace=True)
f.save(f"{outdir}/{name}")
print("wrote", f"{outdir}/{name}")
PY
}

if [[ ! -f "$FONTS/PlayfairDisplay/PlayfairDisplay-Bold.ttf" || $ALL == 1 ]]; then
  fetch_var PlayfairDisplay playfairdisplay 'PlayfairDisplay%5Bwght%5D.ttf' pf.ttf
  get "$RAW/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf" "$TMP/pfi.ttf"
  D="$FONTS/PlayfairDisplay"
  instance "$TMP/pf.ttf"  "$D" PlayfairDisplay-Bold.ttf        wght=700
  instance "$TMP/pf.ttf"  "$D" PlayfairDisplay-Black.ttf       wght=900
  instance "$TMP/pfi.ttf" "$D" PlayfairDisplay-Italic.ttf      wght=400
  instance "$TMP/pfi.ttf" "$D" PlayfairDisplay-BlackItalic.ttf wght=900
fi
if [[ ! -f "$FONTS/SourceSerif4/SourceSerif4-Regular.ttf" || $ALL == 1 ]]; then
  fetch_var SourceSerif4 sourceserif4 'SourceSerif4%5Bopsz%2Cwght%5D.ttf' ss.ttf
  D="$FONTS/SourceSerif4"
  instance "$TMP/ss.ttf" "$D" SourceSerif4-Regular.ttf  wght=400
  instance "$TMP/ss.ttf" "$D" SourceSerif4-SemiBold.ttf wght=600
  instance "$TMP/ss.ttf" "$D" SourceSerif4-Bold.ttf     wght=700
fi
echo "fonts ready in $FONTS"
