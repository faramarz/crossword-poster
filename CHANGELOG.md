# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.2.0] - 2026-10-07

### Added

- **Pictures in the README and guide.** A "how it works" diagram, a gallery of the three styles and the three poster
  sizes drawn to scale, and a short recording of the sample being built. `python scripts/build_visuals.py` remakes them
  from the fictional sample.
- **Make your poster with an AI assistant** ([docs/AI_AGENTS.md](docs/AI_AGENTS.md)): step-by-step instructions and
  copy-paste prompts for Claude Code, the Claude desktop app with Cowork, Claude chat, OpenAI Codex, Cursor, GitHub
  Copilot and Gemini CLI.
- **A Claude skill** in [skills/crossword-poster](skills/crossword-poster/SKILL.md). Claude Code finds it automatically
  in a clone; each release also attaches `crossword-poster-skill.zip` for the Claude apps.
- **AGENTS.md and CLAUDE.md**, which coding assistants read automatically.

- **A feedback form.** There is a new "Share feedback or show your poster" form in the GitHub issue chooser. It asks how
  it went, what worked and what to improve. The chooser also links to an email address (gm@faramarz.xyz) for people
  without a GitHub account, and to the Show and tell discussions where you can share a photo of your poster.
- **`crossword-poster feedback`.** A new command that prints the links above and opens the feedback form in your browser
  with the version and your computer filled in. It sends nothing itself and never reads your clues. Add `--no-open` to
  only print the links.
- **A one-line reminder after a successful `build` or `sample`** that points to `crossword-poster feedback`. Turn it off
  with `--no-feedback-hint` or by setting `CROSSWORD_POSTER_NO_FEEDBACK=1`.

### Changed

- The README introduction and the guide's size advice are now written in general terms.

## [1.1.0] - 2026-10-07

### Changed

- **Licence.** crossword-poster is now under the
  [PolyForm Noncommercial License 1.0.0](LICENSE) instead of MIT. It is free for personal, family, school, club and
  charity use. Commercial use, including selling the software, building a paid product or service on it, or making
  posters for paying customers, needs a commercial licence (write to gm@faramarz.xyz). Posters you make for a
  noncommercial purpose are yours, and the `Required Notice:` lines in [LICENSE](LICENSE) must travel with every copy.
- The bundled fonts stay under the SIL Open Font License 1.1.

### Fixed

- Fitting keeps a small safety margin per column, so the blank poster, answer key and bleed pages always lay out the
  same on every machine.
- Piping output into a program that closes early (`| more` on Windows) exits quietly.

## [1.0.0] - 2026-10-07 [YANKED]

The first public release, under the MIT licence. It was withdrawn the same day and replaced by 1.1.0 under the
PolyForm Noncommercial License.

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
- **Project tooling.** CI on Python 3.9 to 3.14 with a package build and `twine check`, a macOS and Windows sample build,
  a release workflow that attaches the sdist and wheel to a GitHub Release with the notes from this file, and a test
  that keeps `docs/CLI.md` identical to `--help` (`python scripts/sync_cli_docs.py` regenerates it).
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

[Unreleased]: https://github.com/faramarz/crossword-poster/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/faramarz/crossword-poster/releases/tag/v1.2.0
[1.1.0]: https://github.com/faramarz/crossword-poster/releases/tag/v1.1.0
