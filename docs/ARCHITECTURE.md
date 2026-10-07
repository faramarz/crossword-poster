# Architecture (for contributors)

crossword-poster turns a table of clues and answers into print-ready PDFs. This page explains how the pieces fit so you
can change them safely. For usage, see the README.

## Pipeline

```
clues.csv/.xlsx --pool--> pool (grid words + clues) --generate--> grid --validate--> render (Chromium) --> PDFs/PNGs
                                                                                                   |
                                                    actual-size check page <- poster_trim.pdf <----+---> verify
```

`crossword-poster build` (`pipeline.build`) runs six stages and prints each one:

1. **Read** the clues (`pool.build_pool`): detect columns, normalise answers, report problems.
2. **Generate** the grid (`generate.solve`): every answer if possible, otherwise the best partial grid plus a list of left-out words.
3. **Validate** (`validate.validate`): an independent re-derivation of the grid from its letters.
4. **Render** each size (`render_news.render_size`): fit loop, then PDFs for each style and the 11x17 key.
5. **Answer sheet and check page** (`render_news.render_solution`, `actual_size.make_actual_size`).
6. **Verify** (`verify.verify`, `crops.run_crops`): checks on the finished files.

Working files go to `<out>/details/`; the deliverables are copied to `<out>/` under friendly names (`pipeline._collect`).
A previous `details/` folder is removed first so stale styles never get verified.

## Module map

| Module | Role |
|---|---|
| `cli.py` | argument parsing, command dispatch, the friendly error boundary (`UserError` -> message + exit code; no tracebacks for user mistakes) |
| `pipeline.py` | `BuildOptions`, `build()`, file naming, the end-of-run summary |
| `pool.py` | reading CSV/XLSX, column detection, normalisation, enumerations, duplicates, giveaway detection |
| `generate.py` | the freeform board, one randomised attempt, `generate_all`, the resilient `solve`, JSON/text output |
| `validate.py` | independent grid checker (does not import `generate`) |
| `render_news.py` | HTML/CSS/JS page templates, the fit loop (in JavaScript), Playwright printing |
| `actual_size.py` | builds the letter-size 100% check page with pypdf |
| `verify.py`, `crops.py` | output checks (page sizes, fonts, colours, clue coverage, stroke checks) |
| `pdfutil.py` | PDF toolbox on pypdf and pypdfium2 (sizes, text, fonts, a small content-stream interpreter, rasterising) |
| `common.py` | bundled fonts as data URIs, Chromium discovery/launch, PDF printing, size parsing |
| `doctor.py` | `crossword-poster doctor` |
| `errors.py` | `UserError` (exit 2), `EnvironmentProblem` (3), `IncompleteGrid` (1) |
| `transpose.py` | swap rows and columns of a grid.json |
| `fonts/`, `samples/` | package data (OFL fonts, bundled sample CSV) |

## How the generator works

A `Board` is a sparse dict of cells inside a `W x H` window. A word may be placed only if: it crosses at least one existing
word (the grid stays connected), letters agree where words cross, a cell holds at most one Across and one Down word,
the cells before and after the word are empty, and no new cell touches another word sideways.

One **attempt** (`_attempt`) orders the words longest first with random noise (`--noise`), places the first one centred,
and then makes several passes over the rest. For each word it enumerates every legal crossing and picks the best by
`(crossings, -bounding-box area, random tie-break)`. Attempt *k* of seed *s* uses `random.Random(f"{s}:{k}")`, so a result
never depends on how attempts are split across processes. The same seed always gives the same grid.

`generate_all` runs many attempts (optionally in a process pool) and keeps, among attempts that placed **every** word,
the one with the lowest `layout_cost`: bounding-box area inflated by how far its aspect ratio is from `--aspect`
(default 1.0; a squarish grid leaves room for clue columns under it). If no window is given it is estimated from the
letter count (`auto_bounds`: area = letters / 0.4 x 1.3) and enlarged by 15% per failed round.

`solve` adds the graceful degradation: words that share no letter with any other word are left out up front; then
`attempts` layouts in the estimated window with growth; then three times the attempts in a larger window; finally the
best partial layout (`generate`, scored `words*100 + 40*density + 10*crossings/word`). Everything is deterministic: no
wall-clock limits are used.

## Layout and the fit loop

`render_news.py` embeds a data object (`build_data`) into an HTML page. JavaScript in the page does the layout:

* `buildHeader` picks the largest title that leaves room for the byline on one line.
* For each number of text columns `kT` and number of columns `m` spanned by the grid, `planGeom` computes the square size.
  Candidates are tried largest square first.
* `maxFs` bisects for the largest clue font at which a **column pour** (`pour`) of all clues fits: clues are poured top to
  bottom through the columns beside the grid (`kL`) and beneath it, never splitting a clue, never leaving a heading
  alone at a column foot. `maxLh` then widens line height.
* The best plan is the largest squares within 1.5% of the top size, preferring bigger type. `applyPlan` builds the DOM,
  balances column feet, and `verify()` (in the page) records DOM checks into `fit.json`.

Per-size knobs (margin, gutter, font range, minimum square, stroke widths) live in `render_news.SIZES`; other sizes scale
the nearest one by width.

## The renderer

HTML is generated per variant and printed by headless Chromium through Playwright (`page.pdf` with exact inch sizes, so
output is real vector PDF with embedded TrueType fonts). Fonts are inlined as base64 `@font-face` rules, so nothing
depends on file paths. The page is fitted once (no bleed), then rendered twice per style: with bleed and at trim size.
The 11x17 key is the same page scaled by a CSS transform with letters filled in. The PNG preview is rasterised from the
bleed PDF by pypdfium2.

Clue text is untrusted input. It reaches the page two ways: inside a JSON data block (`_js_json` escapes `</` and `<!--`
so it cannot close the `<script>`), and into the DOM through `esc()` (escapes `& < >`) or `textContent`. Titles use
`textContent`. `tests/test_html.py` and the e2e test `test_markup_in_clues_is_printed_literally` guard this.

## Verification

`validate` (grid): runs and numbering re-derived from letters, every clue matches an answer, connectivity, no orphans, trailing
enumerations match lengths, and (with a pool) every entry present. `verify` (files): page sizes (poster = trim + 2 x 0.125
in, key 11x17, letter pages), fonts embedded and none Type 3, only black/white/fill colours, thinnest stroke at least
0.5 pt, no ink inside the margin, every clue exactly once in the PDF text, title and byline present, PNGs neutral grey,
and the DOM checks from `fit.json`. `crops` checks that each letter square shows all four edges and the frame is
unbroken, and writes corner crops to `details/checks/`. PDF facts come from `pdfutil`, whose `page_graphics` interprets
the small set of operators Chromium emits (including `gs` line widths and form XObjects).

## Adding a size or a style

**Size.** Any `WxH` works already (scaled from the nearest tuned size). To tune one, add an entry to `SIZES` in
`render_news.py` (`margin`, `gutter`, `fs_min`, `fs_max`, `cell_min`, `rule`, `sw`, `outer`, `clue_weight`, `tmax`), build
the sample at that size and read the squares and font size from the summary, then check the actual-size page.

**Style.** Styles are variants in `render_news.render_size` (letter `A`, `B`, `C` with a folder name and a fill colour).
Add a variant tuple there, a folder name in `pipeline.FOLDERS`, a name in `pipeline.STYLES`/`names`, an entry in
`verify.VARIANTS` and `crops.VARIANTS`, and (if it uses new colours) allow them in `verify._check_poster`. Artwork such
as the cake and hat lives in `pick_icons` / `icon()` in the page script.

**Font.** See `crossword_poster/fonts/README.md`.

## Conventions

* Everything user-facing raises `UserError` with a message and a "how to fix" hint; only bugs produce tracebacks.
* Output to the console is ASCII-safe (Windows consoles).
* `ruff check` and `ruff format --check` must pass; Python 3.9 is supported (`from __future__ import annotations`, `Optional`).
* Tests: `pytest -m "not e2e"` is fast and browserless; `e2e` tests need Chromium and skip themselves without it.
