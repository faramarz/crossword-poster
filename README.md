# crossword-poster

Turn a spreadsheet of clues and answers into a large-format **newspaper-style crossword poster**, ready to print.

Give it a CSV with one clue and one answer per row. It builds a free-form (loose, "barred-free") crossword grid in which
**every one of your answers is used**, validates it, lays the poster out in Chromium, and writes print-ready PDFs
(with and without bleed), a PNG preview, an 11x17 answer key, a letter-size solution sheet and a 100%-scale
"actual size" check page you can print on a desktop printer before ordering the big print.

![Sample poster, 18x24, black](docs/sample_18x24_black.png)

*The sample above is built from the synthetic data in `examples/sample_clues.csv` (56 generic trivia clues):
18x24 in, solid black blocks. Below: the same data at 24x36 in with grey blocks, which saves ink.*

![Sample poster, 24x36, grey](docs/sample_24x36_grey.png)

## Features

- One command, end to end: pool -> grid -> validate -> render -> verify.
- Every answer is required: the generator searches many randomized layouts and keeps the smallest complete one.
- Any trim size (tuned for 18x24, 24x36 and 36x48 in; others are scaled), 0.125 in bleed, trim-size PDF, PNG preview.
- Layout fit loop: finds the largest box size that still lets all clues fit at a readable size, wrapping clue columns
  beside the grid when that gives bigger boxes.
- Variants: solid black, grey (ink saving), or black with reversed-out spot icons; `--block-fill` for any colour.
- Extras: answer key (11x17), solution sheet (letter), actual-size check page, independent grid validator, output
  verifier (page sizes, embedded fonts, colours, margins, every clue exactly once, per-cell strokes).
- An earlier "classic" renderer with three more styles (Broadsheet, Courtside, Mono).

## Install

```bash
git clone <this repository> crossword-poster && cd crossword-poster
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium            # or point CROSSWORD_CHROMIUM at an existing Chromium/Chrome
```

Python 3.9+. **Chromium is required** for layout and PDF output. Resolution order: the `CROSSWORD_CHROMIUM` environment
variable (path to an executable), then Playwright's own browser, then auto-detection (`PLAYWRIGHT_BROWSERS_PATH`,
`~/.cache/ms-playwright`, `chromium`/`google-chrome` on `PATH`).

Fonts: Archivo Narrow, Oswald, Bebas Neue and DM Sans are included in `fonts/` with their SIL OFL licence texts. The
main renderer needs only Archivo Narrow and Oswald. For the classic renderer's styles A and M run
`scripts/fetch_fonts.sh` once (needs `pip install fonttools`). See [fonts/README.md](fonts/README.md).

## Quick start

```bash
python -m crossword_poster build --clues examples/sample_clues.csv --size 24x36 --style grey --out out/ \
    --title "My Crossword" --byline "Trivia for everyone"
```

Run from the repository root (or put it on `PYTHONPATH`). Results appear under `out/`:

```
out/
  pool.csv  pool_report.json          normalised clue pool, skipped rows, "giveaway" clues
  grid.json  grid.txt  clues.csv      the grid, a text preview, the numbered clue list
  24x36/
    C_grey/poster.pdf                 24.25 x 36.25 in: trim + 0.125 in bleed on every side
    C_grey/poster_trim.pdf            exactly 24 x 36 in
    C_grey/poster.png                 preview
    key.pdf                           11x17 answer key
    actual_size_check_letter.pdf      letter page, print at 100%
    fit.json                          chosen layout (box size, clue font size, columns) + DOM checks
  solution_letter.pdf  .png           letter-size filled grid
  checks/                             corner crops and per-cell stroke check images
```

Style folders: `A_black` (`--style black`), `C_grey` (`grey`), `B_spot` (`icons`); `--style all` builds all three.

Several sizes in one go: `--size 18x24,24x36,36x48`. `scripts/build_all.sh CLUES.csv OUT` builds every size and style.

### Your own clues

Put private data in `data/` (gitignored; see [data/README.md](data/README.md)):

```bash
python -m crossword_poster build --clues data/my_clues.csv --clue-column Clue --answer-column Answer \
    --id-column No --size 24x36 --style black --title "Pub Quiz" --byline "Questions from the quiz team" --out out/
```

Input CSV: one row per entry; the answer may contain spaces, hyphens and accents ("Big Ben", "Café"). The grid word is
the answer folded to A-Z (`BIGBEN`); multi-word answers get an enumeration such as `(3,3)` appended to the clue
automatically. Rows with an empty clue/answer, an answer outside 3-15 letters (`--min-len/--max-len`) or a duplicate
answer are skipped and listed in the report. The pool step also flags *giveaways*: clues that contain another entry's
answer as a whole word.

### Running the steps individually

```bash
python -m crossword_poster pool      --clues examples/sample_clues.csv --out out/pool.csv
python -m crossword_poster generate  --csv out/pool.csv --all --attempts 2000 --seed 1 --workers 4 \
                                     --clue-column clue --out-json out/raw.json --out-txt out/raw.txt
python -m crossword_poster validate  out/grid.json --pool out/pool.csv
python -m crossword_poster render    out/grid.json --trim 24x36 --outroot out --make A,C,key --title "My Crossword"
python -m crossword_poster render    out/grid.json --solution --outroot out --title "My Crossword"
python -m crossword_poster actual-size --from-fit out/24x36 --variant A_black --title "My Crossword"
python -m crossword_poster verify    out --title "My Crossword"
python -m crossword_poster transpose out/grid.json out/transposed      # wide <-> tall layout
python -m crossword_poster render-classic out/grid.json --style M --outdir out/classic --title "My Crossword"
```

`generate` alone writes only the bare grid (`raw.json` has no clues); `build` attaches the clues from the pool
(`generate.attach_pool`) and writes `grid.json`, which is what `validate`, `render` and `verify` expect. The same tools are
available as plain scripts in `scripts/` (`make_pool.py`, `generate.py`, `validate.py`, `render_news.py`,
`render_classic.py`, `actual_size.py`, `verify.py`, `crops.py`, `transpose.py`).

## CLI reference

### `build`

| Option | Default | Meaning |
|---|---|---|
| `--clues CSV` | required | input clues |
| `--clue-column`, `--answer-column` | `clue`, `answer` | column names |
| `--id-column`, `--grid-column` | none | optional unique id / pre-normalised grid word columns |
| `--min-len`, `--max-len` | 3, 15 | allowed grid-word length |
| `--max-width`, `--max-height` | auto | search window in cells; auto = estimated from the letter count and grown (x1.15, up to `--grow-tries`) until a complete layout is found |
| `--attempts` | 1000 | randomized layouts per window |
| `--seed` | 1 | RNG seed; same inputs + seed = same grid, whatever `--workers` is |
| `--workers` | up to 4 | parallel processes |
| `--noise`, `--passes`, `--aspect`, `--grow-tries` | 6, 6, 0.8, 6 | generator tuning (see below) |
| `--size` | `24x36` | trim size(s) `WxH` in inches, comma separated |
| `--style` | `black` | `black`, `grey`, `icons` or `all` |
| `--block-fill COLOR` | none | one CSS colour for the non-letter squares of every variant (env `BLOCK_FILL` also honoured) |
| `--grey-fill COLOR` | `#a3a3a3` | the grey of `--style grey`, the key and the solution sheet |
| `--title`, `--byline` (alias `--subtitle`) | `My Crossword`, `A custom crossword poster.` | header text |
| `--spot-text TEXT` | none | text reversed out of the widest void in the `icons` style (the cake and party hat are always used) |
| `--mode` | `any` | `full` forbids the wrap layout (clues only beneath the grid) |
| `--png-width` | 1200 | preview width in pixels |
| `--out` | `out` | output directory |
| `--no-key`, `--no-solution`, `--no-actual-size`, `--no-verify`, `--no-crops` | | skip an output / check |

Exit status is non-zero if the grid cannot be completed, validation fails, rendering fails or any verification check fails.

### Other commands

| Command | Purpose | Main options |
|---|---|---|
| `pool` | clue CSV -> normalised pool + report | `--clues --clue-column --answer-column --grid-column --id-column --min-len --max-len --out` |
| `generate` | grid generator | `--csv --column --clue-column --max-width --max-height --attempts --seed --min-len --max-len --required --subset --all --workers --noise --passes --aspect --grow-tries --out-json --out-txt` |
| `validate` | independent grid check | `GRID [MAXROWS MAXCOLS] --pool POOL.csv` |
| `render` | newspaper renderer | `GRID --trim --outroot --make A,B,C,key --solution --block-fill --grey-fill --title --byline --spot-text --mode --png-width --build-dir --quiet` |
| `render-classic` | styles A / B / M | `GRID --style --csv --outdir --prefix --make poster,trim,key,test,solution_letter --trim --cell --cell-min --font --font-min --title --subtitle --kicker --est --edition --footer --clue-cols --margin ...` |
| `actual-size` | 100% check page | `POSTER_TRIM.pdf OUT.pdf LABEL BOX_IN CLUE_PT NUM_PT`, or `--from-fit SIZE_DIR` |
| `verify` | output checks | `OUTROOT --title --byline --sizes --block-fill --no-crops` |
| `crops` | corner crops + stroke check | `OUTROOT --sizes` |
| `transpose` | swap rows and columns | `GRID OUT_DIR` |

`python -m crossword_poster <command> --help` shows every option.

## Design notes

**Newspaper layout.** A full-width header carries a heavy condensed title (Oswald Bold, auto-sized to the widest size that
still leaves room for the byline) over a rule. The grid is a solid-fill rectangle: every cell that is not part of a word
is a filled block, so the grid reads as one bold shape and prints cleanly. Letter cells have a 0.75-1.5 pt outline
(never below 0.5 pt, which the verifier enforces) and a heavy outer frame. Clues are set in Archivo Narrow in columns of
one width and one gutter, "poured" top to bottom. A heading never sits alone at the foot of a column, and a clue is never
split between columns. Slack at the foot of each column is spread between clues so the columns end level.

**Fit loop.** For each candidate number of text columns and grid width the layout code computes the box size, then
bisects for the largest clue font (and line height) at which every clue still fits. It prefers the largest boxes and,
among near-equal choices, the larger type. A few dozen clues on a very large trim will hit the font ceiling and leave
white space at the bottom: use a smaller trim or add clues.

**Bleed, trim and files.** `poster.pdf` is trim + 0.125 in bleed on every side (the block fill and white background run
into the bleed); `poster_trim.pdf` is exactly the trim size for print shops that add their own bleed. Content stays at
least 0.5 in inside the trim (more on 36x48). All fonts are embedded as real TrueType (never Type 3).

**Black-and-white and grayscale printing tips.**
- Matte paper (or matte poster stock) keeps glare off a large black-and-white sheet and hides fingerprints. Satin or
  gloss shows reflections and banding in big solid areas.
- Large flooded black can print streaky or take a long time to dry on some wide-format inkjets. The grey style
  (`--style grey`) uses far less ink and is easier to write on with a pen; `--block-fill` lets you pick the exact tone.
- Ask the shop to print in grayscale / black-only mode and to **not** colour-manage, so there is no colour cast on the greys.
- Send `poster.pdf` (with bleed) unless they ask for the trim file; check the size in the PDF viewer
  (File > Properties) before paying. `verify` does this check for you.
- Print `actual_size_check_letter.pdf` at 100% ("Actual size", never "Fit to page"): the bar must measure exactly one inch,
  and the two windows show real boxes and real clue type, so you can judge legibility from arm's length.
- `key.pdf` is the finished poster scaled onto 11x17 with the answers filled in.

**Generator.** `generate.py` is standard-library only. A sparse board holds placed words. To place a word it finds every cell
that already holds one of its letters and tries to cross there; a placement is legal only if the word's ends are bounded by
an empty cell or the window edge, no new cell touches another word sideways, letters agree where words cross, and a cell is
used by at most one Across and one Down word. Among legal crossings it prefers the one with the most crossings, then the
smallest bounding box, with a random tie-break. One attempt orders the words longest first with random noise, places the
first one centred, and makes several passes over the leftovers. In the default mode the best of N attempts by score
(`words*100 + 40*density + 10*crossings per word`) wins and `--required` words must be present. With `--all`, an attempt only counts if it placed
every word; the smallest bounding box among complete layouts wins. Attempt *k* of seed *s* is seeded by `(s, k)`, so the result
does not depend on the worker count. When no window is given it is estimated (area ~ letters / 0.4 x 1.3, aspect `--aspect`)
and enlarged until a complete layout exists. The independent validator re-derives every run, number and clue link from the
letters alone.

## Limitations

- Free-form layout only: no rotational symmetry, no black-square patterns, no dictionary fill. Answers are placed as given,
  so very short or letter-poor answers (few vowels) cross less and need more attempts.
- Answers are folded to A-Z; other scripts are not supported. Length 3-15 letters by default.
- Clues are not rewritten. The giveaway check is a whole-word match only; check that clues are clues, not answers.
- Needs Chromium (Playwright) for layout; layout is tuned for Latin text in Archivo Narrow / Oswald.
- The fit loop optimises box size first. With few clues on a large trim you get large boxes and empty space at the foot; with
  very many clues, type gets small (the minimum font is per size: 11 pt at 24x36). Clue text is never truncated or split;
  if nothing fits, rendering stops with `FIT FAILED`.
- The `icons` style draws a cake and a party hat; other artwork needs code changes (`pick_icons` / `icon` in `render_news.py`).
- Print-shop colour handling is outside the tool's control; always run the actual-size check and order a small proof.

## Tests

```bash
python -m unittest discover -s tests -v      # or: pytest tests
```

`tests/test_smoke.py` builds the pool and grid for the sample, validates it, checks determinism and that the validator
rejects a corrupted grid; if Playwright and Chromium are available it also runs the end-to-end build at 18x24 and checks
the PDF page sizes (18.25 x 24.25 in with bleed, 18 x 24 trim), the PNG and the extra outputs.

## Repository layout

```
crossword_poster/   package: cli, pool, generate, validate, render_news, render_classic, actual_size, verify, crops, transpose
scripts/            thin wrappers, build_all.sh, build_sample.sh, fetch_fonts.sh
examples/           sample_clues.csv (synthetic trivia)
fonts/              OFL fonts + licence texts
docs/               README images
data/               your private inputs (gitignored)
tests/              smoke test
```

## Licence

Code: MIT (see `LICENSE`). Fonts: SIL Open Font License 1.1, see `fonts/<Family>/OFL.txt`.
