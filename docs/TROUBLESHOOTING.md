# Troubleshooting and FAQ

Start with this command. It checks your computer and prints an exact fix for anything that is missing:

```bash
crossword-poster doctor
```

If you are new to the terminal, the [beginner guide](GUIDE.md) explains how to open it and what to type.

**Jump to**

- [Install and setup](#install-and-setup)
- [Windows problems](#windows-problems)
- [Reading your clues file](#reading-your-clues-file)
- [Building the poster](#building-the-poster)
- [Printing](#printing)
- [General questions](#general-questions)
- [Still stuck?](#still-stuck)

---

## Install and setup

### `crossword-poster: command not found` (or "is not recognized")

Your computer cannot find the program. The usual causes:

1. **The Python environment is switched off.** If you installed in a virtual environment (the `.venv` folder in the
   guide), you must switch it on in every new terminal window. Go to your folder and run:
   - macOS and Linux: `source .venv/bin/activate`
   - Windows (Command Prompt): `.venv\Scripts\activate`

   You should see `(.venv)` at the start of the line.
2. **You installed with pipx and the folder is not on your PATH.** Run `pipx ensurepath`, then close the terminal and open
   a new one.
3. **You installed with uv.** Run `uv tool update-shell`, then open a new terminal.
4. **You installed in a different environment from the one you are using.** Check where the program is:
   `which crossword-poster` (macOS and Linux) or `where crossword-poster` (Windows).

A fallback that works whenever the package is installed in the Python you are running:

```bash
python3 -m crossword_poster doctor        # macOS and Linux
py -m crossword_poster doctor             # Windows
```

### Chromium is missing: "Chromium ... was not found or could not start"

Chromium is the browser engine the tool uses to lay out and print the poster. It is a separate one-time download. Install
it **with the same Python environment that has crossword-poster**:

| How you installed the tool | Install Chromium with |
|---|---|
| pip in a virtual environment (switched on) | `python -m playwright install chromium` |
| pipx | `pipx run --spec git+https://github.com/faramarz/crossword-poster playwright install chromium` |
| uv | `uv tool install --force --with-executables-from playwright git+https://github.com/faramarz/crossword-poster`, then `playwright install chromium` |

Then run `crossword-poster doctor` again.

**Why not just follow the `doctor` hint?** `doctor` suggests `python -m playwright install chromium`. That works for pip
and a switched-on virtual environment. With pipx or uv, `python` is not the tool's own environment, so use the commands
in the table. (Another option with pipx is to install with `pipx install --include-deps git+https://github.com/faramarz/crossword-poster`. That adds a `playwright` command that you can run as `playwright install chromium`.)

Chromium is stored in a shared folder (`~/.cache/ms-playwright` on Linux, `~/Library/Caches/ms-playwright` on macOS,
`%LOCALAPPDATA%\ms-playwright` on Windows), and the tool searches there. A Chromium that does not exactly match your
Playwright version is still found and used.

**Other things to try**

- **Use a browser you already have.** The tool also looks for `chromium`, `google-chrome` and `msedge` on your PATH and
  in the usual install folders on macOS and Windows, so an existing Chrome or Edge may be picked up without a download.
  To point at one yourself, set `CROSSWORD_POSTER_CHROMIUM` to its full path:

  ```bash
  export CROSSWORD_POSTER_CHROMIUM="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"    # macOS
  ```

  ```bat
  set CROSSWORD_POSTER_CHROMIUM=C:\Program Files\Google\Chrome\Application\chrome.exe
  ```

  The project is tested with the Chromium that Playwright installs. Another browser should work, but if the output looks
  wrong, install the Playwright one.
- **Linux says a shared library is missing.** Install Chromium's system libraries (Ubuntu and Debian; this uses `sudo`):
  `python -m playwright install --with-deps chromium`.
- **The download fails.** A work or school network may block it. Try another network, or ask your IT team to allow
  downloads from `cdn.playwright.dev` and `playwright.download.prss.microsoft.com`.

### `error: externally-managed-environment` when I run `pip install`

Newer Linux and Homebrew Pythons refuse to install packages into the system Python. That protects your system. Use a
virtual environment (the guide's steps) or pipx:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/faramarz/crossword-poster
```

### `git: command not found`, or an error mentioning `git clone`

The `git+https://...` install form needs Git. Install Git, or install from a ZIP file instead, which needs no Git:

```bash
pip install https://github.com/faramarz/crossword-poster/archive/refs/heads/main.zip
```

### `python3 -m venv` fails on Ubuntu or Debian

Install the missing piece: `sudo apt install python3-venv`. Then try again.

### "requires a different Python" or "No matching distribution found"

The tool needs Python 3.9 or newer. Check with `python3 --version` (`py --version` on Windows). If it is older, install a
newer Python from [python.org/downloads](https://www.python.org/downloads/).

### Which Python versions work?

3.9, 3.10, 3.11, 3.12 and 3.13. These are the versions the project's tests run on.

---

## Windows problems

The project's automated tests build a full poster with Chromium on Linux. On Windows and macOS they run `doctor` and
the unit tests. If you hit a Windows-only problem that is not listed here, please
[open an issue](https://github.com/faramarz/crossword-poster/issues/new/choose).

### `'py' is not recognized`, or typing `python` opens the Microsoft Store

- Run the Python installer from [python.org](https://www.python.org/downloads/windows/) again and tick **Add python.exe to
  PATH** on the first screen. Choose **Repair** if Python is already installed. Then open a **new** Command Prompt.
- If `python` opens the Store, go to **Settings > Apps > Advanced app settings > App execution aliases** and turn off the
  "Python" entries. Or use `py` instead of `python` for the first commands, as the guide does.

### PowerShell says "running scripts is disabled on this system"

That blocks the line that switches the environment on. Use Command Prompt instead (Start, type `cmd`, Enter). It does not
have this restriction.

### The path has spaces or the file is "not found"

Put the path in double quotes: `crossword-poster build --clues "C:\Users\Sam\My Documents\my_clues.csv"`. Or put the
CSV in the folder you are working in and use its plain name. You can also drag the file into the window to paste its full
path.

### The tool cannot read my file, and it is open in Excel

Excel can lock a file while it is open. Close the file in Excel (save it first), then run the command again.

### The print dialog in Edge or Chrome

When you open a PDF in a browser and press Print, set **Scale** to **100%** (or **Default**), not **Fit to page**. In
Adobe Reader, choose **Actual size**.

---

## Reading your clues file

### "Could not find the clue column" (or answer column)

The first row of your file must have headings the tool recognises. It looks for `clue`, `clues`, `question`, `questions`,
`hint`, `hints` and `answer`, `answers`, `word`, `words`, `solution`, `solutions`, in any capital letters. The error
lists the headings it found. Either rename the headings in your spreadsheet, or name them on the command line:

```bash
crossword-poster build --clues my_clues.csv --clue-column "Your clue" --answer-column "Your answer"
```

If you used a Google Form, name the questions exactly `Clue` and `Answer`.

### "File not found"

Check the spelling and the folder. The terminal looks in the folder you are in. You can drag the file into the terminal
window to paste its full path.

### My accented letters turned into strange characters

That happens when a spreadsheet saves a CSV in an old encoding, so `Zoë` becomes `ZoÃ«` or `Zo?`. Re-save as **CSV UTF-8**:

- Excel: File > Save As > "CSV UTF-8 (Comma delimited) (\*.csv)". Plain "CSV (Comma delimited)" is the old encoding.
- Google Sheets and Numbers: their CSV export is already UTF-8.

The tool reads UTF-8 (with or without BOM) and, if that fails, falls back to Windows-1252, the old Excel encoding. It tells
you when it does. If you see the fallback note and the letters still look wrong, re-save as UTF-8.

### Can I use accented letters, or other languages?

**Accents: yes.** `Café` becomes `CAFE` in the grid. Your original spelling is kept in `clues_and_answers.csv`.
A few letters are spelled out: `ß` is `SS`, `æ` is `AE`, `œ` is `OE`, `ø` is `O`.

**Other alphabets: no.** Answers with Greek, Cyrillic, Arabic, Chinese or other non-Latin letters are skipped with an
explanation, because the grid only holds A to Z. Clues can contain any characters your fonts can show, but the bundled
fonts (Archivo Narrow and Oswald) cover Latin text only. You can write an answer from another language in Latin letters
(for example "Nowruz" or "Sayonara").

### Why was my answer skipped?

The build lists every skipped row with its row number and a reason. The common ones:

| Message | Meaning and fix |
|---|---|
| the answer contains a digit | Answers are letters only. Spell numbers out. |
| too short (under 2 letters) | Use a longer answer. |
| too long (over 20 letters) | Shorten it, or raise `--max-len`. |
| contains letters outside A-Z | Other alphabets are not supported. |
| missing clue / missing answer | Fill in the empty cell. |
| duplicate of row N | Same answer twice. The first is kept. |

### Some of my clues look like answers

The tool cannot tell a clue from an answer. If people typed the answer in the clue box, the poster will have a sentence in
the grid and a single word as the clue. Scan your answer column (sort by it) before you build. See
[the guide](GUIDE.md#3-clean-and-edit-the-clues).

### The length shown in the clue looks wrong, for example `(1,5)` for `O'Brien`

Words are split at apostrophes and hyphens when the length is worked out. Add an `enumeration` column to your file and type
the length you want: `6` for `O'Brien`, or `4-3` for `Jean-Luc`. See [the CSV format](CLI.md#the-clues-file).

---

## Building the poster

### Some of my answers did not fit

The tool says which ones and why, and still builds a poster without them. Things to try, in order:

1. Add `--seed 2` (then 3, 4...) for a different layout.
2. Add `--attempts 3000` to search harder.
3. Change an answer that shares few letters with the others. An answer with no letters in common with any other cannot cross,
   so it can never fit.
4. Use a bigger `--size`, or fewer or shorter answers.
5. Add `--require-all` if you would rather the build stop than leave anything out.

### The text is too small

Look at the summary line: `Poster 24x36: each square is 0.62 in; clue text is 18.0 pt`. Small text comes from many clues on
a small poster. Fix it by:

- choosing a bigger `--size` (for example 24x36 instead of 18x24);
- using fewer clues;
- shortening long clues (long clues need more lines);
- checking with the [actual-size page](GUIDE.md#6-check-before-printing) rather than the screen.

The [clue count table](GUIDE.md#how-many-clues-fit-each-poster-size) shows what to expect.

### There is a big empty space at the bottom of the poster

This happens when you have few clues for a large size. The grid is as large as it can be and the clue text has reached its
size limit, so there is room left over. Use a smaller poster, or add clues. It is a layout choice, not an error.

### Does it matter that my layout changes when I edit the clues?

Yes, a little. The layout depends on the **answers**, the **order of the rows** and the **seed**. Rewording a clue does not
change the layout. Changing or adding an answer, deleting a row, or reordering the rows can give a different layout. So
finish your answers first, then proofread the final poster. If you like a layout, keep the same file order and `--seed`.

### How long does it take?

The sample (54 clues) builds in about 12 seconds on a modest two-core computer. A list of 99 clues took around a minute
for one size. Bigger lists take longer to search. Building several sizes or styles takes longer. To go faster, add
`--no-verify`, or `--no-crops` which skips only the slowest check.

### "The clues do not fit on a ... poster at a readable size"

The layout code could not fit all the clues on the poster. The message ends with the fix: choose a bigger `--size`, or use
fewer or shorter clues, then build again. The build exits with code 2 and writes no poster. This is rare. A more common
case is that the poster is built but the type is very small, so always read the `clue text is ... pt` line in the summary.

### "Output checks: SOME FAILED"

The tool checks the finished files for the right page sizes, embedded fonts, colours, margins and that every clue appears
once. If a check fails, the message above it says which. Look at the PDFs before you print, and try a bigger size or fewer
clues. If the PDFs look right and you cannot see the problem, please [open an issue](https://github.com/faramarz/crossword-poster/issues/new/choose).

### "Something unexpected went wrong"

That is a bug, not your fault. Run the same command again with `CROSSWORD_POSTER_DEBUG=1` in front (macOS and Linux:
`CROSSWORD_POSTER_DEBUG=1 crossword-poster build ...`; Windows Command Prompt: `set CROSSWORD_POSTER_DEBUG=1` on its own line
first). Then open an issue with the output and your command.

---

## Printing

### The print shop asked for a different file

| They say | Send |
|---|---|
| "Do you have a PDF with bleed?" | `poster_..._bleed.pdf` (0.125 in bleed on every side). |
| "We add our own bleed", "send it at final size" | `poster_..._trim.pdf`. |
| "Send a high-resolution image" | Ask if a PDF is acceptable. It is a vector PDF and prints sharply at any size. If they insist, ask what pixel size they need. The `_preview.png` is only a screen preview and is too small to print big. |
| "What colour mode?" | Black and white or grayscale. The file contains only black, white and grey. |
| "Is it outlined?" or "Are fonts embedded?" | Yes, all fonts are embedded in the PDF. |

A copy-paste message for the shop is in [the guide](GUIDE.md#what-to-tell-the-print-shop).

### Can I use A2, A1 or another size?

Yes. Any width and height in inches works. The layout is tuned for 18x24, 24x36 and 36x48 and scales other sizes from the
nearest one.

| Size | Command |
|---|---|
| A2 (420 x 594 mm) | `--size 16.54x23.39` |
| A1 (594 x 841 mm) | `--size 23.39x33.11` |
| A0 (841 x 1189 mm) | `--size 33.11x46.81` |
| 20 x 30 in | `--size 20x30` |
| 24 x 36 in, landscape | `--size 36x24` |

I tested A2, A1, 12x18, 20x30, 11x17 and a landscape 36x24 poster. They build and look right. A0 follows the same rules but
is not part of the tests. A size under 18 inches wide prints a note that the text may come out small. For A2 with about
40 clues, it came out at 12.9 pt, which is readable. Check the summary and the [actual-size page](GUIDE.md#6-check-before-printing).

The tool prints bleed of 0.125 in. Metric shops may ask for 3 mm. 0.125 in is 3.2 mm, which is fine.

### The actual-size page is cut off on A4 paper

The check page is US Letter (8.5 x 11 in). A4 is a little narrower, so the right edge can be cut by a few millimetres at
100%. That is expected. The black bar still measures exactly one inch from its left end. If the bar measures one inch,
the scale is right.

### The black bar does not measure one inch

Your printer scaled the page. In the print dialog choose **Actual size** or **100%**, and turn off "Fit to page", "Shrink
to fit" and "Scale to fit paper". Print again. Check any "borderless" or "fit to media" options too.

### The big black areas print streaky

A solid black area this large can print unevenly on some wide-format inkjets. Use `--style grey` (it uses far less ink and is
easier to write on), or ask the shop for a test strip. A matte stock is best. You can also pick a lighter tone with
`--block-fill "#555555"`.

### Can people write on it?

Yes, on uncoated matte paper. Glossy and laminated surfaces repel ink. Test your pens on a proof or on the back of the
actual-size page first.

---

## General questions

### Is my data private?

Yes. Everything runs on your computer. The tool reads your CSV, builds the PDFs locally and uploads nothing. It does not
phone home or collect usage data. The only network use is the one-time downloads you start yourself (the tool from GitHub
and Chromium). Keep your clue files out of public places: the repository's `.gitignore` already ignores the `data/` folder
and any file named `*.private.*` so they never get committed by accident.

### Do I need to be online?

Only to install. After that the tool works offline.

### How many clues should I use?

About 30 to 60 for a typical poster. See [the table](GUIDE.md#how-many-clues-fit-each-poster-size).

### Can I change the fonts, colours or title style?

Colours: yes (`--block-fill`, `--grey-fill`). Title and subtitle text: yes. Fonts and other artwork need changes to the
code. See [CONTRIBUTING](../CONTRIBUTING.md) and [ARCHITECTURE](ARCHITECTURE.md).

### Can I make a different kind of crossword (symmetrical, with a dictionary fill)?

No. The tool makes a free-form crossword: it places exactly your answers and crosses them wherever letters allow. It does
not make symmetrical patterns or fill the grid with extra words.

### Can I use it for something other than a birthday?

Yes. Anniversaries, retirements, weddings, reunions, quiz nights, classrooms and team events all work. Change the title and
the subtitle, and pick the `grey` or `black` style. The `icons` style draws a cake and a party hat, so it suits birthdays.

### Can I use the posters commercially?

Yes. The code is MIT licensed and the bundled fonts are under the SIL Open Font License, which allows use in printed
work. See [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).

---

## Still stuck?

1. Run `crossword-poster doctor` and read the `Fix:` lines.
2. Search the [existing issues](https://github.com/faramarz/crossword-poster/issues).
3. Ask in [Discussions](https://github.com/faramarz/crossword-poster/discussions) for help using the tool.
4. [Open an issue](https://github.com/faramarz/crossword-poster/issues/new/choose) for a bug. Include the output of `doctor`,
   your operating system, the exact command, and the message you saw. **Do not paste private clues or names.** A few made-up
   lines that cause the same problem are enough.
