---
name: crossword-poster
description: Guides making a personalised, print-ready crossword poster from a list of clues and answers for a birthday, anniversary, retirement, wedding, reunion or other special occasion, using the crossword-poster command line tool. Use when the user wants a custom crossword poster or puzzle gift, wants to turn friends-and-family clues (a spreadsheet, CSV, Google Form export or pasted list) into a poster, or wants a clue list cleaned up first (swapped clue and answer columns, duplicates, answers with numbers, clues that are too long). Covers checking the install, cleaning clues into a clue,answer CSV, choosing title, size and style, building the PDFs, reviewing warnings, and handing the file to a print shop. Keeps the clues private.
---

# Crossword poster

You help a non-programmer turn clues from friends and family into a crossword poster PDF with the
`crossword-poster` command line tool. It lays out a free-form crossword that uses every answer, and writes a print-ready
PDF, an answer key, an answer sheet and a page for checking sizes. It runs offline on the user's computer.

Be warm and plain-spoken. The poster is usually a gift or a surprise. Explain what you are about to do in one line
before you run a command, and never show a traceback to the user: summarise what went wrong and what you will try.

## Privacy rules (always)

- The clues are personal. Keep the clue file and the generated poster on the user's computer. Do not upload them, post
  them anywhere, commit them to a public repository, or paste them into an issue, discussion or feedback form.
- If you work inside a clone of the crossword-poster repository, keep the user's files out of git: put them in a folder
  that is ignored (`data/` is) or outside the repository, and do not run `git add` on them.
- When something needs reporting or debugging, use made-up example clues, not the real ones.

## Workflow

Work through these steps in order. Tell the user which step you are on.

### 1. Check the install

Run:

```bash
crossword-poster doctor
```

- `Everything is ready.` means go on to step 2.
- `command not found`: the tool is not installed. Install it from GitHub (it is not on PyPI), with whichever of these is
  available (`pipx --version` or `uv --version` tells you):

  ```bash
  pipx install git+https://github.com/faramarz/crossword-poster
  ```

  ```bash
  uv tool install git+https://github.com/faramarz/crossword-poster
  ```

  Then run `crossword-poster install-browser` (a one-time download of about 300 MB of Chromium, the browser engine that
  prints the poster). On Linux add `--with-deps` (it uses `sudo`). If the command is still not found, `pipx ensurepath`
  or `uv tool update-shell` fixes the PATH; the user may need to open a new terminal. If neither pipx nor uv exists, the
  beginner guide at https://github.com/faramarz/crossword-poster/blob/main/docs/GUIDE.md#4-install-the-tool has plain pip
  steps for macOS, Windows and Linux.
- A `[FAIL]` line comes with a `Fix:` line. Do what it says, then run `doctor` again.
- If the download of Chromium is blocked (a sandbox or a work network), do not keep retrying. Tell the user which
  commands to run on their own computer (the two install commands above) and carry on once they have.

Check the version with `crossword-poster --version` if you need to be sure a flag exists. `crossword-poster build --help`
is the final word on options.

### 2. Collect and clean the clues

The tool needs a CSV (or `.xlsx`) with a header row and two columns: **`clue`** (the hint printed on the poster) and
**`answer`** (the word that goes in the grid). Other columns, such as name or timestamp, are ignored. An optional `id`
column and an optional `enumeration` column (the printed length, such as `3,3`) are also understood.

If the user has no file yet, offer a starter file:

```bash
crossword-poster template my_clues.csv
```

If the clues are pasted text, a Google Form export or a messy sheet, turn them into `clue,answer` rows yourself. Work on
a copy and keep the original untouched. Then check and fix these, asking the user whenever you are not sure:

1. **Swapped columns.** Some people typed the answer in the clue box. An answer that is a sentence, ends in a question
   mark, or is three or more words long is probably a clue. If most rows are swapped, swap the whole columns. Show the
   user the rows you changed.
2. **Letters only.** Answers cannot contain digits (`1976`, `50th`): ask the user to spell it out (`Nineteen seventy
   six`) or change the clue. Accents are fine (`Café` becomes `CAFE`). Non-Latin alphabets are not supported.
3. **Length.** Answers must be 2 to 20 letters once spaces, hyphens and apostrophes are dropped. Four to ten letters fit
   best. A clue longer than 300 characters is skipped; aim for 12 words or fewer.
4. **Duplicates.** The same answer twice (`Biscuit`, `biscuit`, `Big Ben` and `BIG-BEN`) keeps only the first row. Show
   both clues and let the user pick the better one. Also look for near-duplicates the tool cannot see (`Biscuit` and
   `Biscuits`).
5. **Giveaways.** A clue must not contain its own answer or another answer on the poster.
6. **Empty cells.** A row with no clue or no answer is skipped. Fill it in or remove it.
7. **Kindness and facts.** The guest of honour will read every clue. Flag anything embarrassing, hurtful or private
   (health, money, exes, age jokes, addresses, phone numbers). Flag names and dates that may be misspelt or wrong. Do not
   delete a clue silently: suggest, and let the user decide.
8. **Count.** About 30 to 60 clues is a good range for most posters. Fewer than 8 will look sparse; more than 250 gets
   small squares (see the size table in the guide).

Save as UTF-8 with the headings `clue,answer`. Then run a quick check that needs no browser. It lists the rows that would
be skipped and warns about duplicates, swapped columns and sparse lists:

```bash
crossword-poster pool --clues my_clues.csv --out pool_check.csv
```

Fix what it reports and run it again until only expected warnings remain. The `pool_check.csv` file is a throwaway.

### 3. Ask for the details

Ask the user, in one short message, for:

- **Title** for the top of the poster (for example `Sam's 50th Birthday`).
- **Subtitle**, a short line beside the title (for example `Clues from everyone who loves you`). Optional.
- **Size** in inches. `24x36` is the best all-round choice (40 to 150 clues). `18x24` is cheaper and smaller (30 to 70
  clues). `36x48` suits a crowd (70 to 200 clues). Other sizes work too, such as `16.54x23.39` for A2.
- **Style**: `grey` (the default; saves ink and is easy to write on), `black` (bold) or `icons` (black with a cake and a
  party hat, for birthdays; `--spot-text 50` puts a number in the big black area). `--style all` builds all three to
  compare.
- **Where to save the results.** Default to a new folder next to the clue file, for example `poster/`.

If the user is unsure, suggest `24x36` and `grey`.

### 4. Build

Run it as one line (do not split it across lines with a backslash):

```bash
crossword-poster build --clues my_clues.csv --title "Sam's 50th Birthday" --subtitle "Clues from everyone who loves you" --size 24x36 --style grey --out poster/
```

It takes from about 10 seconds to a couple of minutes. The first time, `crossword-poster sample --out my-first-poster`
builds a fictional example in about 15 seconds if the user wants to see what they will get. Useful options when needed:

| Situation | Option |
|---|---|
| Some answers did not fit and the user wants a different layout | `--seed 2` (then 3, 4) or `--attempts 3000` |
| The build should stop if any answer is left out | `--require-all` |
| Compare sizes or styles | `--size 18x24,24x36` or `--style all` |
| The column headings are not `clue` and `answer` | `--clue-column "Question" --answer-column "Word"` |
| More than 250 clues | `--time-limit 300` |
| Hide the one-line feedback reminder | `--no-feedback-hint` |

The exit code tells you how it went: `0` success, `1` built but needs attention (checks failed, or `--require-all` and an
answer did not fit), `2` a problem with the input or options (read the `Error:` and `How to fix:` lines), `3` the computer
is missing something (run `crossword-poster doctor`, then `crossword-poster install-browser`).

### 5. Review the result

Read the summary at the end of the build and report to the user in plain words:

- `Every answer was placed.` Good. Otherwise it lists the answers that did not fit and why. Offer: change that answer, try
  another `--seed`, pick a bigger size, or drop it.
- `each square is ... in` and `clue text is ... pt`. About 0.6 in (15 mm) squares or more are comfortable for a pen;
  below about 0.5 in the writing gets cramped. Clue text of 14 pt or more is comfortable. Warnings such as "tight" or
  "blank foot" mean a different size or clue count would look better.
- `Output checks: all passed.` If it says `SOME FAILED`, look at the PDFs and tell the user before they print.
- Skipped rows and giveaway warnings that appeared earlier in the output.

Then look at the picture of the poster, `poster_<size>_<style>_preview.png`, and read `clues_and_answers.csv` for
proofreading (the numbered clue and answer for every entry). Remind the user to read every clue and answer aloud and to
ask a second person to proofread. If a clue changes, fix the CSV and build again; a new build replaces the old files.

Tell the user to print the **actual-size check** (`actual_size_check_<size>.pdf`) at 100% scale ("Actual size", never "Fit to
page") on a home printer and measure the black bar at the top: it must be exactly 1 inch (25.4 mm). They can then see
the real squares and the real clue text before paying for the big print.

### 6. Hand-off for printing

The files in the output folder:

| File | Use |
|---|---|
| `poster_<size>_<style>_bleed.pdf` | **Send this to the print shop.** It has 0.125 in of bleed on every side. |
| `poster_<size>_<style>_trim.pdf` | Exactly the final size, for shops that add their own bleed. |
| `poster_<size>_<style>_preview.png` | A picture to look at or share. Not for printing. |
| `answer_key_<size>_11x17.pdf` | The whole poster shrunk onto 11x17 in with answers filled in, for the host. |
| `answer_sheet_letter.pdf` and `.png` | The filled grid on one letter page. Print at home. |
| `actual_size_check_<size>.pdf` | The size check page described above. |
| `clues_and_answers.csv` | The numbered list for proofreading. |

Suggest wording for the shop: one copy from the attached PDF, final size (for example 24 x 36 in, trim from the bleed
file), print at 100% with no scaling or "fit to page", black and white or grayscale, matte or uncoated paper so pens
work, no lamination, and ask for the price and when it will be ready. Allow extra days for foam board mounting or
shipping. The full copy-paste message is in the guide:
https://github.com/faramarz/crossword-poster/blob/main/docs/GUIDE.md#what-to-tell-the-print-shop

Mention the party ideas if the user wants them: a pen station, the answer sheet as a finale, and photographing the
finished poster.

### 7. Wrap up

Tell the user where every file is. Offer one thing at a time: a different size or style, a new layout with another
`--seed`, or party tips. When they are done, mention that `crossword-poster feedback` prints the links for sharing how it
went or showing the poster, and that it sends nothing itself. Do not share their clues there.

## If something goes wrong

- `Error:` lines come with a `How to fix:` line: follow it.
- Chromium missing (exit code 3): `crossword-poster install-browser`, then `crossword-poster doctor`.
- "Could not find the clue column": rename the headings in the file, or pass `--clue-column` and `--answer-column`.
- "The clues do not fit on a ... poster at a readable size": choose a bigger `--size`, or use fewer or shorter clues.
- A strange character in the clues (such as `ZoÃ«`): the file was saved in an old encoding. Save it as CSV UTF-8.
- "Something unexpected went wrong" is a bug. Run the same command again with the environment variable
  `CROSSWORD_POSTER_DEBUG=1` to see details, and describe the problem with made-up clues if reporting it.
- More help: https://github.com/faramarz/crossword-poster/blob/main/docs/TROUBLESHOOTING.md
