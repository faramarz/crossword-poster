# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.0.0] - 2026-10-07

The first public release.

### Added

- **One-command pipeline.** `crossword-poster build` reads a clues file, builds a crossword grid that uses every answer,
  checks it, lays out and prints the poster with Chromium, and checks the finished files. It ends with a plain-language
  summary: the files written, the square size, the clue text size and any answers that did not fit.
- **Beginner-friendly commands.** `sample` builds a bundled, fictional birthday crossword. `template` writes a starter
  clues file. `doctor` checks Python, the libraries, the bundled fonts and Chromium, and prints the exact fix for anything
  missing.
- **`install-browser`** downloads Chromium with the same Python that runs the tool, so it works under pip, pipx and uv.
  `doctor` prints that command and, as a fallback, the manual one with the full interpreter path.
- **Safety limits and guidance.** Clues over 300 characters are skipped, more than 400 words is an error, the grid
  search has a wall-clock budget (`--time-limit`) with progress lines, and swapped clue and answer columns are noticed.
  Builds warn when clue text is under 9 pt, squares under 0.3 in, or the poster foot is blank; few-clue posters get
  larger clue text instead of empty space. Printed lengths treat only spaces as word breaks (`O'Brien` is `(6)`,
  `Mother-in-law` is `(6-2-3)`).
- **Print-ready output.** Vector PDFs with embedded fonts, with 0.125 in bleed and at exact trim size. A PNG preview, an
  11x17 answer key, a letter-size answer sheet, and a letter-size actual-size check page for printing at 100%.
- **Sizes and styles.** Layouts tuned for 18x24, 24x36 and 36x48 inches. Any other size, including A sizes and landscape,
  scales from the nearest one. Styles: `grey`, `black` and `icons`. `--block-fill`, `--grey-fill` and `--spot-text` for
  custom looks.
- **A fit loop** that picks the largest squares that still let every clue appear at a readable size, with clue columns
  beside or under the grid.
- **Forgiving input.** CSV (UTF-8 with or without BOM, or Windows-1252 as Excel writes it; comma, semicolon or tab
  separated) and `.xlsx` (with the optional `xlsx` extra). Column names are found automatically (`clue`, `question`,
  `answer`, `word`, and more). Accents are folded to A to Z, lengths such as `(3,3)` are added, duplicates are
  reported, and answers that cannot be used are skipped with an explanation.
- **Independent checks.** A grid validator that re-derives the grid from its letters. An output verifier for page sizes,
  fonts, colours, margins, clue coverage and per-square strokes.
- **Friendly errors.** Mistakes in input or setup print a message and a "how to fix" line, with exit codes 1, 2 and 3.
  Only real bugs produce a traceback.
- **Single-stage commands** for power users: `pool`, `generate`, `validate`, `render`, `verify`, `actual-size`, `crops`
  and `transpose`.
- **Documentation:** a beginner guide, a command line reference, a troubleshooting FAQ and an architecture overview.
- **Tests and CI.** A pytest suite with unit and end-to-end tests (real Chromium). GitHub Actions run lint, unit tests on
  Python 3.9 to 3.13, end-to-end tests, and smoke tests on macOS and Windows. Dependabot keeps dependencies current.
- **Community files:** contributing guide, code of conduct, security policy and issue and pull request templates.

### Licensing

- The code is MIT licensed.
- The bundled fonts, Archivo Narrow and Oswald, are under the SIL Open Font License 1.1, with their licence texts shipped in
  the package.
- PDFs are read with `pypdf` and rendered with `pypdfium2`. The earlier AGPL dependency (PyMuPDF) is not used. No
  Python dependency is copyleft. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

[Unreleased]: https://github.com/faramarz/crossword-poster/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/faramarz/crossword-poster/releases/tag/v1.0.0
