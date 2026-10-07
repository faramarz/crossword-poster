# Command line reference

Everything the tool does is one command: `crossword-poster`. This page lists every command and option, what the exit
codes mean, the environment variables, and the format of the clues file. The help text below was captured from
`crossword-poster <command> --help` (version 1.0.0). Your own `--help` is always the final word.

`python -m crossword_poster ...` does the same as `crossword-poster ...`.

**On this page**

- [Commands at a glance](#commands-at-a-glance)
- [Exit codes](#exit-codes)
- [Environment variables](#environment-variables)
- [The clues file](#the-clues-file) (CSV format spec)
- [The files `build` writes](#the-files-build-writes)
- [`build`](#build), [`sample`](#sample), [`template`](#template), [`doctor`](#doctor), [`install-browser`](#install-browser)
- [Single-stage commands](#single-stage-commands): [`pool`](#pool), [`generate`](#generate), [`validate`](#validate), [`render`](#render), [`verify`](#verify), [`actual-size`](#actual-size), [`crops`](#crops), [`transpose`](#transpose)

## Commands at a glance

```text
crossword-poster 1.0.0: turn a spreadsheet of clues and answers into a print-ready crossword poster.

usage: crossword-poster [--version] <command> [options]

Start here:
  build            make a poster, answer key, answer sheet and size-check page from a clues file
  sample           build the bundled birthday example so you can see the result in one command
  template         write a starter clues file (CSV) to fill in
  doctor           check that this computer is ready (Python, fonts, Chromium)
  install-browser  download the Chromium browser that prints the poster (one time)

For power users (each runs one stage of `build`):
  pool             clues file -> cleaned list of answers, with a report of problems
  generate         grid generator on its own
  validate         independent check of a grid.json
  render           poster renderer on its own (from a grid.json)
  verify           checks on the files of a finished build
  actual-size      100% scale check page cut out of a poster PDF
  crops            corner crops and per-square stroke check
  transpose        swap rows and columns of a grid.json

Run `crossword-poster <command> --help` for the options of a command.
Typical use:   crossword-poster build --clues my_clues.csv --title "Sam's 50th" --size 24x36 --out poster/
Exit status: 0 = success, 1 = built but needs attention (checks failed, or --require-all and some answers did not fit),
             2 = problem with your input or options, 3 = the computer is missing something (run `doctor`).
```

`crossword-poster --version` (or `-V`, or `version`) prints the version. `crossword-poster help` and `--help` print the
list above. Running `crossword-poster` with no command prints it and exits with status 2. A mistyped command gets a
"Did you mean" hint.

Most people only need `doctor`, `sample`, `template` and `build`. The rest each run one stage of `build` and are for
power users and developers. `build` runs them in this order: read the clues (`pool`), build the grid (`generate`),
check it (`validate`), print the posters (`render`), make the answer sheet and check page (`render --solution`,
`actual-size`), check the files (`verify`, `crops`).

## Exit codes

| Code | Meaning | Example |
|---:|---|---|
| 0 | Success. | A normal build, even when some answers were left out (unless `--require-all`). |
| 1 | It ran, but something needs your attention. | A `build` whose output checks failed. `build --require-all` when an answer did not fit. `validate`, `verify` or `crops` found a problem. `doctor` found a missing piece. |
| 2 | A problem with your input or options. | File not found, no `clue` column, a size like `banana`, a missing required option, a command that does not exist. |
| 3 | The computer is missing something. | Chromium is not installed or cannot start. Run `crossword-poster doctor`. |
| 70 | An unexpected error (a bug). | Please report it. Set `CROSSWORD_POSTER_DEBUG=1` to get the full traceback. |
| 130 | You pressed Ctrl+C. | |

Friendly errors print `Error: ...` and a `How to fix: ...` line on the error stream (stderr), never a traceback.

## Environment variables

| Variable | What it does |
|---|---|
| `CROSSWORD_POSTER_CHROMIUM` | Full path to a Chromium or Chrome program to use instead of the one Playwright installs. If it is set but cannot start, the tool stops with a message (it does not fall back). Unset it to go back to the default search. |
| `CROSSWORD_POSTER_DEBUG` | Set to any non-empty value to show a full Python traceback instead of the short "unexpected error" message. Useful for bug reports. |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwright's own setting: the folder where it keeps (and the tool looks for) downloaded browsers. |

**How the tool finds Chromium.** In this order:

1. `CROSSWORD_POSTER_CHROMIUM`, if set.
2. The browser Playwright installed with `crossword-poster install-browser`.
3. Any Chromium found by search: folders named in `PLAYWRIGHT_BROWSERS_PATH`, Playwright's usual cache folders
   (`~/.cache/ms-playwright` on Linux, `~/Library/Caches/ms-playwright` on macOS, `%LOCALAPPDATA%\ms-playwright` on
   Windows), then `chromium`, `chromium-browser`, `google-chrome`, `google-chrome-stable`, `chrome` or `msedge` on your
   PATH, then the usual Chrome and Edge install locations on macOS and Windows.

The project's tests and CI use the Chromium that Playwright installs. Other browsers found in step 3 are a convenience.

## The clues file

`build`, `pool` and the other commands read a table of clues and answers, one clue per row, with a header row.

### Minimal example

```csv
id,clue,answer
1,Capital of France,Paris
2,Nickname of the clock tower at Westminster,Big Ben
3,Our favourite pizza topping,Pineapple
```

(That is what `crossword-poster template my_clues.csv` writes.)

### Columns

Column names are matched without regard to capital letters, and spaces around them are ignored. Columns you do not need
(timestamp, name, story) are ignored.

| Column | Required | Accepted names | Meaning |
|---|---|---|---|
| clue | Yes | `clue`, `clues`, `question`, `questions`, `hint`, `hints` | The hint that is printed on the poster. |
| answer | Yes | `answer`, `answers`, `word`, `words`, `solution`, `solutions` | The answer, as you would write it. |
| id | No | `id` | A short unique label. Without it the tool uses `row<N>`. A repeated id is renamed to `row<N>` with a warning. |
| enumeration | No | `enumeration`, `enum` | The printed length for this clue, such as `6`, `(6)`, `3,3` or `(4-3)`. It is used only if its letters add up to the real length of the answer. Otherwise it is ignored with a warning. |

If your headings are different, name them on the command line: `--clue-column`, `--answer-column`, `--id-column`. There is
also `--grid-column` for a column that already holds the A to Z grid word.

Blank lines above the header row are skipped. A completely blank row is skipped silently. A row with only a clue or only
an answer is skipped and listed by row number. The row number is the number a spreadsheet shows.

### File formats

| Format | Notes |
|---|---|
| `.csv` | UTF-8, with or without a BOM (byte order mark). If the file is not valid UTF-8, it is read as Windows-1252 (the old Excel default) and the tool says so. Choose "CSV UTF-8" when saving to avoid any doubt. |
| Delimiter | A comma, semicolon or tab, detected from the first non-empty line. Excel in some countries writes semicolons. Both work. |
| `.xlsx` | Needs the optional `openpyxl` package: `pip install "crossword-poster[xlsx]"`. The first sheet is read. Formulas show their saved values. |
| `.xls` | Not supported. Save as CSV UTF-8 or `.xlsx`. |
| Anything else | Read as CSV. |

### How answers are turned into grid letters

The answer you write is kept for display. The **grid word** is made from it by these rules:

1. Accents are removed (`Café` becomes `CAFE`, `Zoë` becomes `ZOE`) and letters are made upper case.
2. A few letters are spelled out: `ß` becomes `SS`, `æ` becomes `AE`, `œ` becomes `OE`, `ø` becomes `O`, `đ` becomes `D`,
   `ł` becomes `L`, `ı` becomes `I`, `þ` becomes `TH`.
3. Everything that is not a letter A to Z is dropped: spaces, hyphens, apostrophes and punctuation. `Big Ben` becomes
   `BIGBEN`.
4. The result must be 2 to 20 letters (`--min-len` and `--max-len` change the limits).

An answer is **skipped**, with an explanation, if it contains a digit, contains letters from another alphabet (for
example Greek or Cyrillic, or Chinese characters), has no letters, or is too short or too long. The Latin alphabet is
the only one supported.

### Lengths printed in the clues

The printed length is added at the end of each clue.

- A single word gets `(n)`, such as `(7)`.
- A multi-word answer gets a list of word lengths, such as `(3,3)` for `Big Ben`. Only spaces separate words.
  Apostrophes and other punctuation inside a word are not counted, so `O'Brien` is a single word of six letters and gets
  `(6)`. A hyphenated word keeps its hyphens: `Mother-in-law` is `(6-2-3)`, and `Well-known cake` is `(4-5,4)`. To print
  a different length, add an `enumeration` column (for example `6`).
- If the clue already ends with a length such as `(5,3)` and the total is right, it is kept as you wrote it. If the
  total is wrong, the tool corrects it and prints a warning.
- Single-word lengths are added when the poster is drawn. So `clues_and_answers.csv` shows your clue, and the poster
  shows your clue plus the length.

### Duplicates, giveaways and warnings

- **Duplicates.** If two rows have the same grid word, the first is kept and the others are ignored, with a warning.
  The comparison is on the letters only, so `Big Ben` and `BIG-BEN` count as the same answer.
- **Giveaways.** A clue that contains an answer as a whole word (or a whole phrase, for multi-word answers), including
  its own answer, is reported as a possible giveaway. The build prints the count. The list is in
  `<out>/details/pool_report.json`. It is a warning only.
- **Few or many clues.** Fewer than 2 usable clues is an error. Fewer than 8 gives a "will look sparse" warning. More
  than 120 gives a "type will be small" warning. More than 400 usable clues is an error: split the file, or keep the best.
- **Long clues.** A clue longer than 300 characters is skipped, with its length shown, because it cannot be laid out
  legibly. Shorten it.
- **Swapped columns.** If most "answers" are sentences of four or more words and longer than their "clues", the tool
  warns that the two columns look swapped and prints the `--clue-column` and `--answer-column` options that fix it. (If
  every row was rejected because of this, the same advice is in the error message.)
- **Clue text is printed literally.** Characters such as `<`, `>` and `&` appear exactly as typed and cannot change the
  poster's layout. Runs of spaces and line breaks inside a clue become one space.

## The files `build` writes

In the folder you give to `--out` (default `out`). `<size>` is the poster size such as `24x36`, and `<style>` is
`grey`, `black` or `icons`. A build of several sizes or styles writes one set per size and style.

| File | What it is |
|---|---|
| `poster_<size>_<style>_bleed.pdf` | The file to print: trim size plus 0.125 in on every side. |
| `poster_<size>_<style>_trim.pdf` | Exactly the trim size, for shops that add their own bleed. |
| `poster_<size>_<style>_preview.png` | A picture of the poster (width set by `--png-width`, default 1200 px). |
| `answer_key_<size>_11x17.pdf` | The poster scaled onto 11 x 17 in, with the answers filled in. Skipped by `--no-key`. |
| `actual_size_check_<size>.pdf` | A US Letter page at 100% scale. Skipped by `--no-actual-size`. |
| `answer_sheet_letter.pdf` and `.png` | The filled grid on one letter page. Skipped by `--no-solution`. |
| `clues_and_answers.csv` | Columns `number`, `direction`, `clue`, `answer`, `id`. |
| `details/` | Working files: `grid.json`, `grid.txt`, `pool.csv`, `pool_report.json`, one folder per size, and `checks/`. |

Each time you build into a folder that already has a `details/grid.json`, the old `details/` is removed first, so old
styles never end up in the checks. Other files already in the folder are left alone and same-named files are overwritten.

# Commands

## build

Runs the whole pipeline. This is the command most people use.

```text
usage: crossword-poster build [-h] --clues FILE [--title TITLE] [--subtitle SUBTITLE] [--size WxH]
                              [--style {black,icons,grey,all}] [--out DIR] [--seed SEED]
                              [--require-all] [--clue-column NAME] [--answer-column NAME]
                              [--id-column NAME] [--grid-column NAME] [--min-len MIN_LEN]
                              [--max-len MAX_LEN] [--attempts ATTEMPTS] [--workers WORKERS]
                              [--max-width MAX_WIDTH] [--max-height MAX_HEIGHT] [--aspect ASPECT]
                              [--grow-tries GROW_TRIES] [--time-limit SECONDS]
                              [--block-fill COLOR] [--grey-fill COLOR] [--spot-text SPOT_TEXT]
                              [--mode {any,full}] [--png-width PNG_WIDTH] [--no-key]
                              [--no-solution] [--no-actual-size] [--no-verify] [--no-crops]
                              [--verbose]

Read a CSV (or .xlsx) of clues and answers, build a crossword grid with every answer in it, and print the poster(s), answer key, answer sheet and an actual-size check page.

options:
  -h, --help            show this help message and exit

what to build:
  --clues FILE          CSV or .xlsx with one clue and one answer per row
  --title TITLE         title across the top of the poster (default: 'My Crossword')
  --subtitle, --byline SUBTITLE
                        line next to the title (default: 'A custom crossword poster.')
  --size WxH            poster size in inches; 18x24, 24x36 and 36x48 are tuned; several sizes:
                        18x24,24x36 (default 24x36)
  --style {black,icons,grey,all}
                        grey = grey blocks, saves ink and easy to write on; black = solid black
                        blocks; icons = black with a cake and party hat; all = all three (default
                        grey)
  --out DIR             folder for the results (default: out)
  --seed SEED           random seed: the same clues + seed give the same grid; try another for a
                        different layout (default 1)
  --require-all         fail (exit status 1, nothing printed) if any answer cannot be placed;
                        otherwise leave it out and say so

reading the file:
  --clue-column NAME    header of the clue column (default: clue, clues or question)
  --answer-column NAME  header of the answer column (default: answer, answers or word)
  --id-column NAME      optional unique id column (default: the row number)
  --grid-column NAME    optional column with a ready-made A-Z grid word
  --min-len MIN_LEN     shortest allowed answer in letters (default 2)
  --max-len MAX_LEN     longest allowed answer in letters (default 20)

grid search (the defaults are fine for most files):
  --attempts ATTEMPTS   layouts to try per search round (default 1000)
  --workers WORKERS     parallel processes; the result does not depend on it (default 2)
  --max-width MAX_WIDTH
                        limit the grid width in squares (default: automatic)
  --max-height MAX_HEIGHT
                        limit the grid height in squares (default: automatic)
  --aspect ASPECT       automatic window: width / height (default 1.0)
  --grow-tries GROW_TRIES
                        times the automatic window is enlarged when nothing fits (default 6)
  --time-limit SECONDS  stop searching after this many seconds and use the best layout found; 0 =
                        no limit (default 180)

look:
  --block-fill COLOR    CSS colour for the empty squares in every style, e.g. '#c8d6e5'
  --grey-fill COLOR     the grey of --style grey (default #a3a3a3)
  --spot-text SPOT_TEXT
                        short text (e.g. 50) reversed out of the biggest black area in --style
                        icons
  --mode {any,full}     'full' forbids clue columns beside the grid
  --png-width PNG_WIDTH
                        preview picture width in pixels (default 1200)

skip things:
  --no-key              skip the 11x17 answer key
  --no-solution         skip the letter-size answer sheet
  --no-actual-size      skip the actual-size check page
  --no-verify           skip the checks on the finished files
  --no-crops            make the checks faster by skipping the per-square stroke check
  --verbose             print every check instead of a short summary

Example:
  crossword-poster build --clues my_clues.csv --title "Sam's 50th Birthday" --subtitle "Clues from everyone who loves you" --size 24x36 --style grey --out poster/

Your clues file needs a header row with 'clue' and 'answer' columns (see `crossword-poster template`).
Exit status: 0 success; 1 built but needs attention; 2 problem with your input; 3 Chromium missing.
```

**Examples**

```bash
# the usual
crossword-poster build --clues my_clues.csv --title "Sam's 50th Birthday" --subtitle "Clues from everyone who loves you" --size 24x36 --style grey --out poster

# two sizes in one run
crossword-poster build --clues my_clues.csv --size 18x24,24x36 --out poster

# all three styles
crossword-poster build --clues my_clues.csv --style all --out poster

# other column names
crossword-poster build --clues quiz.csv --clue-column Question --answer-column Word --out poster

# A2 poster, with a spot of text reversed out of a black area (icons style)
crossword-poster build --clues my_clues.csv --size 16.54x23.39 --style icons --spot-text 50 --out poster

# a different layout of the same clues
crossword-poster build --clues my_clues.csv --seed 2 --out poster-v2

# every size and style at once (the script wraps this command)
scripts/build_all.sh my_clues.csv out "My Crossword"
```

**Notes**

- `--size` accepts `WIDTHxHEIGHT` in inches, decimals allowed. `18x24`, `24x36` and `36x48` are tuned. Other sizes scale
  the nearest tuned size by width. Widths under 18 inches print a note that text may be small. Landscape works
  (`36x24`).
- `--seed`: the same clues and the same seed always give the same grid, whatever `--workers` is.
- `--attempts`, `--max-width`, `--max-height`, `--aspect`, `--grow-tries`: control the grid search. The defaults suit
  most files. When no size is given the tool estimates a window from the number of letters and enlarges it up to
  `--grow-tries` times (by 15% each time) until every answer fits.
- `--time-limit SECONDS` (default 180, 0 for no limit) caps the search for a grid. While it runs, a "still searching" line
  is printed every few seconds. When the limit is reached the best layout found so far is used, any answers that did not
  fit are listed, and the build says how to avoid it (fewer answers, or a longer limit). If the limit is not reached the
  grid is exactly the same as without it.
- The fitting step enlarges the clue text when a poster has few clues: if 8% or more of its height would be blank at the
  bottom, the text grows (up to 1.5 times the tuned maximum) until the page is filled. The build prints a warning if the
  clue text ends up under 9 pt, the squares under 0.3 in, or 8% or more of the height is still blank.
- `--mode full` does not put clue columns beside the grid. All clues go under it.
- `--block-fill` sets the colour of the non-letter squares in every style. `--grey-fill` sets only the grey of `--style
  grey`, the answer key and the answer sheet. `--spot-text` only affects `--style icons`.
- `--no-verify` skips the final output checks. `--no-crops` skips only the per-square stroke check (faster).
  `--verbose` prints each check and the full clue-reading report.
- With `--require-all`, a build that cannot place every answer stops with exit code 1 and writes no posters.
- The build checks that Chromium can start before it does any layout work. If it cannot, you get exit code 3.

## sample

Builds the bundled, fictional "Alex's 50th" crossword so you can see what the tool makes. The clues file it uses is
copied into the output folder so you can open it as an example.

```text
usage: crossword-poster sample [-h] [--out DIR] [--size WxH] [--style {black,icons,grey,all}]
                               [--seed SEED]

Build the bundled, fictional birthday crossword (Alex's 50th) so you can see what the tool makes.

options:
  -h, --help            show this help message and exit
  --out DIR             folder for the results (default: sample-poster)
  --size WxH            poster size in inches (default 18x24)
  --style {black,icons,grey,all}
                        default grey
  --seed SEED
```

```bash
crossword-poster sample --out my-first-poster
crossword-poster sample --size 24x36 --style black --out sample-24x36
```

## template

Writes a starter clues file with the headings `id,clue,answer` and three example rows. The file is saved with a BOM so
Excel opens it as UTF-8.

```text
usage: crossword-poster template [-h] [--force] OUT.csv

Write a starter clues file with the right headers and three example rows. Replace the examples
with your own clues (a clue is the question; the answer is the word that goes in the grid).

positional arguments:
  OUT.csv     where to write the file, e.g. my_clues.csv

options:
  -h, --help  show this help message and exit
  --force     overwrite the file if it already exists
```

```bash
crossword-poster template my_clues.csv
crossword-poster template my_clues.csv --force    # overwrite
```

## doctor

Checks Python, the libraries, the bundled fonts and that Chromium can start. Each failing line has a `Fix:` line.
Exit code 0 when everything is ready, 1 otherwise.

```text
usage: crossword-poster doctor [-h]

Check Python, the installed libraries, the bundled fonts and that Chromium can start.

options:
  -h, --help  show this help message and exit
```

Real output on a working machine:

```text
crossword-poster 1.0.0: checking this computer

  [ok] Python 3.13.16 (needs 3.9 or newer)
  [ok] crossword-poster 1.0.0 imports; libraries: playwright 1.63.0, pypdf 6.19.0, pypdfium2 5.14.0, Pillow 12.3.0
  [ok] Bundled fonts found (Archivo Narrow, Oswald)
  [ok] Chromium 141.0.7390.37

Everything is ready. Try:  crossword-poster sample --out my-first-poster
```

And with Chromium missing:

```text
crossword-poster 1.0.0: checking this computer

  [ok] Python 3.13.16 (needs 3.9 or newer)
  [ok] crossword-poster 1.0.0 imports; libraries: playwright 1.63.0, pypdf 6.19.0, pypdfium2 5.14.0, Pillow 12.3.0
  [ok] Bundled fonts found (Archivo Narrow, Oswald)
  [FAIL] Chromium could not start: Chromium (the browser used to print the poster) was not found or could not start.
         Fix: run `crossword-poster install-browser`; if that does not work, run `"/usr/bin/python3" -m playwright install chromium` yourself (or set CROSSWORD_POSTER_CHROMIUM to the path of a Chromium/Chrome executable)

Some checks failed. Follow the 'Fix' lines above, then run `crossword-poster doctor` again.
```

The manual command in the `Fix:` line uses the full path of the Python that is running the tool, in quotes (so a path
with spaces works), because under pipx, uv or a virtual environment a bare `python` is a different Python. The path
shown here is only an example. On Windows PowerShell, put `& ` in front of the quoted path.

## install-browser

Downloads Chromium once, with Playwright's installer, using the same Python that runs `crossword-poster`. It works
however the tool was installed (pip, pipx, uv). It prints the command it runs, runs it, then checks that Chromium starts.
Exit code 0 on success and 3 if the download or the check fails.

```bash
crossword-poster install-browser               # macOS, Windows, Linux with the libraries already present
crossword-poster install-browser --with-deps   # Linux: also install Chromium's system libraries (uses sudo)
```

## Single-stage commands

Most people will never need these. `pool` and `generate` work on their own. `validate`, `render`, `verify`,
`actual-size`, `crops` and `transpose` expect the `details/grid.json` that `build` writes (the bare grid that
`generate` writes does not carry the clues).

### pool

Reads the clues file and writes the cleaned list of answers (`pool.csv`, with columns `grid`, `clue`, `display`, `id`)
and a report (`pool_report.json`, next to it).

```text
usage: crossword-poster pool [-h] --clues CLUES [--clue-column CLUE_COLUMN]
                             [--answer-column ANSWER_COLUMN] [--grid-column GRID_COLUMN]
                             [--id-column ID_COLUMN] [--min-len MIN_LEN] [--max-len MAX_LEN]
                             [--out OUT]

Pool builder: a clue/answer table (CSV or XLSX) -> normalised pool of grid words, clues and display answers.

For every input row it
  * finds the clue and answer columns by name (case-insensitive: clue/clues/question, answer/answers/word)
  * skips blank rows silently and reports rows with a missing clue or answer by their spreadsheet row number
  * normalises the answer to the letters that go in the grid (A-Z, accents folded, spaces and punctuation dropped)
    and explains any answer that cannot be used (digits, other alphabets, too short, too long)
  * keeps the first of several rows with the same grid word and warns about the others
  * appends an enumeration such as "(5,3)" to the clue of a multi-word answer that has none
  * reports "giveaways": clues that contain an answer as a whole word or phrase

Writes OUT (default pool.csv; columns grid,clue,display,id) and OUT-with-_report.json.

Usage:
  crossword-poster pool --clues mine.csv --out out/pool.csv
  crossword-poster pool --clues mine.csv --clue-column Question --answer-column Word

options:
  -h, --help            show this help message and exit
  --clues CLUES         input CSV (or .xlsx) with a clue column and an answer column
  --clue-column CLUE_COLUMN
                        header of the clue column (default: clue, clues or question)
  --answer-column ANSWER_COLUMN
                        header of the answer column (default: answer, answers or word)
  --grid-column GRID_COLUMN
                        optional column with the pre-normalised grid word
  --id-column ID_COLUMN
                        optional unique id column (default: the row number)
  --min-len MIN_LEN     shortest allowed answer (default 2)
  --max-len MAX_LEN     longest allowed answer (default 20)
  --out OUT             where to write the pool (default pool.csv)
```

```bash
crossword-poster pool --clues my_clues.csv --out out/pool.csv
```

### generate

The grid generator on its own. Reads a CSV with one grid word per row (the `pool.csv` that `pool` writes works).

```text
usage: crossword-poster generate [-h] --csv CSV [--column COLUMN] [--clue-column CLUE_COLUMN]
                                 [--max-width MAX_WIDTH] [--max-height MAX_HEIGHT]
                                 [--attempts ATTEMPTS] [--seed SEED] [--min-len MIN_LEN]
                                 [--max-len MAX_LEN] [--required REQUIRED] [--all]
                                 [--workers WORKERS] [--noise NOISE] [--passes PASSES]
                                 [--aspect ASPECT] [--grow-tries GROW_TRIES]
                                 [--time-limit SECONDS] [--out-json OUT_JSON] [--out-txt OUT_TXT]

Freeform ("loose", barred-free) crossword generator. Standard library only.

Greedy placement with randomised restarts. Rules enforced:
  * every word crosses at least one already-placed word (the grid is connected)
  * a letter cell is shared by at most one Across and one Down word
  * no two words touch side by side (no illegal 2-letter adjacencies)
  * a word's start and end are bounded by an empty cell or the edge of the window
  * no word is placed twice
Score = words_placed * 100 + 40 * density + 10 * crossings_per_word
(density = letter cells / bounding-box area, so compact layouts with many words win).

Modes
  default   best-of-N layout that places as many words as it can; --required words must all be placed.
  --all     EVERY word must be placed. Many attempts are tried (in parallel) and the complete layout with the
            smallest bounding box (nudged toward --aspect) wins. Without --max-width/--max-height the window is estimated from the letter
            count and grown automatically (--grow-tries) until a complete layout is found.

Examples
  crossword-poster generate --csv out/pool.csv --all --attempts 2000 --seed 1 --out-json out/raw.json
  crossword-poster generate --csv words.csv --column answer --max-width 25 --max-height 25 --required PLANET,RIVER

The input CSV is only read, never modified.

options:
  -h, --help            show this help message and exit
  --csv CSV             CSV with one word per row (the pool.csv written by `pool` works)
  --column COLUMN       column holding the grid words (default: grid)
  --clue-column CLUE_COLUMN
                        optional; shown in the text preview
  --max-width MAX_WIDTH
                        window width in cells (default 25; estimated with --all)
  --max-height MAX_HEIGHT
                        window height in cells (default 25; estimated with --all)
  --attempts ATTEMPTS   randomised layouts to try (default 100)
  --seed SEED           random seed; the same seed gives the same grid
  --min-len MIN_LEN
  --max-len MAX_LEN
  --required REQUIRED   comma-separated words that MUST be placed
  --all                 every word must be placed; smallest complete layout wins
  --workers WORKERS     parallel processes for --all (the result does not depend on it)
  --noise NOISE         randomness of the longest-first ordering
  --passes PASSES       placement passes per attempt (default 3; 6 with --all)
  --aspect ASPECT       --all, estimated window: width/height ratio
  --grow-tries GROW_TRIES
                        --all, estimated window: times to enlarge it by 15% when nothing fits
  --time-limit SECONDS  stop searching after this many seconds (default: no limit)
  --out-json OUT_JSON   write the grid as JSON here
  --out-txt OUT_TXT     write the text preview here
```

```bash
crossword-poster generate --csv out/pool.csv --all --attempts 2000 --seed 1 --workers 4 --clue-column clue --out-json out/raw.json
```

### validate

An independent check of a `grid.json` (it does not use the generator's code). Exit code 0 means valid, 1 means errors.
`MAXROWS` and `MAXCOLS` are optional positional numbers, not options.

```text
usage: crossword-poster validate [-h] [--pool POOL] target [MAX_ROWS] [MAX_COLS]

Independent grid validator (it does not import the generator).

Checks a grid.json, as written by `build` (with clues) or by `generate --out-json` (without clues):
  * the grid fits within MAX_ROWS x MAX_COLS (optional) and its bounding box is tight
  * every across/down run of 2+ letters is a listed placement, and vice versa; letters match; no duplicate starts
  * numbering follows reading order; every placement has exactly one non-empty clue whose answer matches
  * no orphan letters (every letter is in a word), the letters form one connected shape, no duplicate answers
  * with --pool: every pool entry (by id) appears in the grid
  * a trailing enumeration such as "(3,3)" in a clue matches the answer length
A raw `generate` file has no clues, so the clue checks and --pool are skipped and the output says so.

Usage:
  crossword-poster validate out/details/grid.json [MAX_ROWS MAX_COLS] [--pool out/details/pool.csv]
Exit status 0 = valid, 1 = errors.

positional arguments:
  target       grid.json, or a folder containing grid.json
  MAX_ROWS     optional: report an error if the grid has more rows than this
  MAX_COLS     optional: report an error if the grid has more columns than this

options:
  -h, --help   show this help message and exit
  --pool POOL  pool CSV from `pool`: every entry must be in the grid
```

```bash
crossword-poster validate out/details/grid.json --pool out/details/pool.csv
crossword-poster validate out/details            # a folder that contains grid.json also works
crossword-poster validate raw.json               # the output of `generate --out-json` also works
```

`validate` accepts both `build`'s `grid.json` and the bare grid from `generate --out-json`. A bare grid has no clues, so
the clue checks and `--pool` are skipped, and the output says so. A file that is not a grid at all gets a friendly
"not a usable grid file" error.

### render

The poster renderer on its own: `grid.json` to PDFs through Chromium. `--make` takes a comma list: `A` (black),
`B` (icons), `C` (grey), `key` (the 11x17 answer key).

```text
usage: crossword-poster render [-h] [--trim TRIM] [--outroot OUTROOT] [--make MAKE]
                               [--block-fill COLOR] [--grey-fill GREY_FILL] [--title TITLE]
                               [--byline BYLINE] [--spot-text SPOT_TEXT] [--quiet] [--solution]
                               [--mode {any,full}] [--png-width PNG_WIDTH] [--build-dir BUILD_DIR]
                               grid

Newspaper-style crossword poster renderer (black & white / grey): grid JSON -> vector PDFs via Chromium/Playwright.

Design: full-width header (heavy condensed caps title left, byline right, rule under), solid-fill freeform grid
(every non-letter cell inside the bounding rectangle is a filled square), clue columns of one width and one gutter that
run beside the grid (wrap layout) and/or beneath it, filled by a JavaScript column-pour with a fit loop.

Per size it writes (OUT = --outroot/<size>):
  A_black/poster.pdf (+0.125 in bleed), poster_trim.pdf, poster.png   solid black blocks            (--make A)
  B_spot/ ...                                                          black + reversed-out icons    (--make B)
  C_grey/ ...                                                          grey blocks, saves ink        (--make C)
  key.pdf                                                              11x17 answer key (the poster, scaled, letters filled)
  fit.json                                                             chosen layout + verification report
and, once per run with --solution, OUTROOT/solution_letter.pdf/.png (the letter-size filled solution).

Usage:
  crossword-poster render out/details/grid.json --trim 24x36 --outroot out/details --make A,C,key --title "My Crossword"
  crossword-poster render out/details/grid.json --solution --outroot out/details --title "My Crossword"
Sizes: any WxH in inches. 18x24, 24x36 and 36x48 have tuned settings; other sizes are scaled from the nearest one.
Fills: --block-fill COLOR forces one colour for every variant; otherwise A/B use black, C/key/solution use --grey-fill.

positional arguments:
  grid                  grid JSON with a top-level 'clues' array (the grid.json written by
                        `build`)

options:
  -h, --help            show this help message and exit
  --trim TRIM           trim size WxH in inches (default 24x36; tuned: 18x24, 24x36, 36x48)
  --outroot OUTROOT     folder to write into (default: current folder)
  --make MAKE           comma list: A (A_black), B (B_spot: black + white icons), C (C_grey), key
                        (grey 11x17 key)
  --block-fill COLOR    CSS colour for the non-letter squares in EVERY variant. Default: A/B
                        black, C/key/solution --grey-fill
  --grey-fill GREY_FILL
                        colour of the grey style, the key and the solution (default #a3a3a3)
  --title TITLE         poster title (default: 'My Crossword')
  --byline, --subtitle BYLINE
                        line to the right of the title (default: 'A custom crossword poster.')
  --spot-text SPOT_TEXT
                        short text (e.g. a number) reversed out of the widest black void in
                        variant B
  --quiet               print less
  --solution            write OUTROOT/solution_letter.pdf/.png instead of a poster
  --mode {any,full}     'full' forbids the wrap layout (clues only beneath the grid)
  --png-width PNG_WIDTH
                        preview width in pixels (default 1200)
  --build-dir BUILD_DIR
                        scratch HTML directory (default OUTROOT/.build)
```

```bash
crossword-poster render out/details/grid.json --trim 24x36 --outroot out/details --make A,C,key --title "My Crossword"
crossword-poster render out/details/grid.json --solution --outroot out/details --title "My Crossword"
```

### verify

Checks the files of a finished build: page sizes, embedded fonts, colours, thinnest line, margins, that every clue
appears exactly once, that the title and byline are present, and per-square strokes. It prints PASS or FAIL for each
check. Exit code 1 on any failure.

**Give it the same `--title` and `--byline` you built with.** The default title is `My Crossword`. Checking a poster with
a different title reports a failed "title and byline" check.

```text
usage: crossword-poster verify [-h] [--title TITLE] [--byline BYLINE] [--sizes SIZES]
                               [--grid GRID] [--block-fill BLOCK_FILL] [--grey-fill GREY_FILL]
                               [--no-crops]
                               outroot

Checks for rendered outputs (everything under OUTROOT written by `build` / `render`).

Covered: page sizes (poster = trim + 0.125 in bleed on every side, trim, key 11x17, letter pages), fonts embedded
(none Type 3), only black / white / the chosen fill colours in the vector content, thinnest stroke, no ink inside the
outer margin, every clue appears exactly once, title and byline present, every PNG neutral grey (R=G=B), DOM checks
recorded in fit.json, and (unless --no-crops) per-cell stroke checks via crops.py.
Prints a PASS/FAIL report; the exit status is 1 on any failure.

Usage:
  crossword-poster verify out/details --title "My Crossword" [--byline "..."] [--sizes 24x36,18x24]

positional arguments:
  outroot               the details folder of a build (contains grid.json and the size folders)

options:
  -h, --help            show this help message and exit
  --title TITLE
  --byline, --subtitle BYLINE
  --sizes SIZES         comma list (default: every size folder found)
  --grid GRID           grid.json (default OUTROOT/grid.json)
  --block-fill BLOCK_FILL
                        the --block-fill used for rendering, if any
  --grey-fill GREY_FILL
  --no-crops            skip the per-cell stroke check / crop images (faster)
```

```bash
crossword-poster verify out/details --title "Sam's 50th Birthday" --byline "Clues from everyone who loves you"
```

### actual-size

Builds the US Letter actual-size check page from a poster PDF. In `build` this runs for you.

```text
usage: crossword-poster actual-size [-h] [--from-fit SIZE_DIR] [--variant VARIANT] [--title TITLE]
                                    [args ...]

Actual-size check page (US Letter): a 1-inch bar plus two true-scale windows cut out of the finished poster.

Print it at 100% on a desktop printer to judge the real box and type sizes before ordering the big print.
The windows are located from the poster itself: the top-left corner of the largest filled grid rectangle and the
ACROSS heading (the start of the clue columns). It works with any block fill.

The page is assembled with pypdf: the poster page becomes a form XObject that is drawn, clipped, at 1:1 scale.

Usage:
  crossword-poster actual-size POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT [--title T]
  crossword-poster actual-size --from-fit out/details/24x36 [--variant A_black] [--title T]   # reads fit.json

positional arguments:
  args                 POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT

options:
  -h, --help           show this help message and exit
  --from-fit SIZE_DIR  use SIZE_DIR/fit.json and SIZE_DIR/<variant>/poster_trim.pdf
  --variant VARIANT
  --title TITLE
```

```bash
crossword-poster actual-size --from-fit out/details/24x36 --variant C_grey --title "My Crossword"
```

`--variant` is the folder name of a style: `A_black`, `B_spot` (icons) or `C_grey`. The default is `A_black`.

### crops

Writes corner and edge crops at 150 dpi for every output, and checks that each letter square shows all four edges and
that the outer frame is unbroken. Writes into `OUTROOT/checks/`. Exit code 1 on failure.

```text
usage: crossword-poster crops [-h] [--sizes SIZES] [--grid GRID] outroot

Corner/edge crops at 150 dpi for every grid output, plus an automated stroke check.

Every letter cell must show all four strokes (a dark pixel at the centre of each of its 4 edges, sampled away from
the corners) and the frame must be continuous on all four sides. Writes OUTROOT/checks/<name>/*.png and a montage
OUTROOT/checks/<name>.png. The exit status is 1 on failure.

Usage: crossword-poster crops OUTROOT [--sizes 24x36,18x24] [--grid OUTROOT/grid.json]

positional arguments:
  outroot

options:
  -h, --help     show this help message and exit
  --sizes SIZES
  --grid GRID
```

```bash
crossword-poster crops out/details
```

### transpose

Swaps rows and columns of a `grid.json` (across becomes down) and renumbers it. Handy to turn a wide grid into a tall
one. It writes `grid.json` and `clues.csv` into the folder you name. Render from the new `grid.json`.

```text
usage: crossword-poster transpose [-h] src out_dir

Transpose a grid.json (rows <-> columns, across <-> down), renumber in reading order, keep every answer and clue.

Handy for turning a wide layout into a tall one (or the other way round) to suit the poster shape.

Usage: crossword-poster transpose SRC_GRID.json OUT_DIR   (writes OUT_DIR/grid.json and OUT_DIR/clues.csv)

positional arguments:
  src         grid.json to transpose
  out_dir     folder to write the new grid.json and clues.csv into

options:
  -h, --help  show this help message and exit
```

```bash
crossword-poster transpose out/details/grid.json out/transposed
```

## See also

- [Beginner guide](GUIDE.md) for a walk-through.
- [Troubleshooting](TROUBLESHOOTING.md) for common problems.
- [Architecture](ARCHITECTURE.md) for how the stages work inside.
