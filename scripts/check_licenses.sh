#!/usr/bin/env bash
# Print the licence of every runtime dependency of crossword-poster, using a throw-away virtual environment.
# Use it after changing the dependencies in pyproject.toml and update THIRD_PARTY_LICENSES.md to match.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 -m venv "$TMP/venv"
"$TMP/venv/bin/pip" install --quiet "$ROOT" pip-licenses
# NOTE: pip-licenses reports package-level metadata only. Binary wheels (Pillow, ...) can bundle shared libraries
# under other licences (some LGPL / GPL with the GCC runtime exception); see THIRD_PARTY_LICENSES.md.
"$TMP/venv/bin/pip-licenses" --format=markdown --with-urls --order=name
if "$TMP/venv/bin/pip-licenses" --format=csv | grep -Ei 'GPL|AGPL|LGPL' | grep -v 'pip-licenses'; then
  echo "WARNING: a copyleft licence was found above" >&2
  exit 1
fi
