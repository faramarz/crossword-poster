# Contributing to crossword-poster

Thank you for helping. This project makes a crossword poster out of a list of clues, and it is meant to be friendly to
people who have never used a terminal. Improvements to the tool, the documentation and the examples are all welcome.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). To report a security problem, see
[SECURITY.md](SECURITY.md).

## Ways to help

- **Report a bug.** Open an [issue](https://github.com/faramarz/crossword-poster/issues/new/choose). The form asks for the
  output of `crossword-poster doctor`, your operating system and the command you ran.
- **Ask a question or share an idea** in [Discussions](https://github.com/faramarz/crossword-poster/discussions).
- **Improve the docs.** If a step confused you, it will confuse others. Pull requests that fix wording, add a missing
  step or add a screenshot are very welcome.
- **Fix a bug or add a feature.** See below.
- **Test on your computer.** Try the [beginner guide](docs/GUIDE.md) on macOS, Windows or Linux and tell us where it
  broke.

**Never put real clues, names or other private details in an issue, pull request, test or example.** Use made-up ones. The
tool is often used for gifts and surprises.

## Set up for development

You need Python 3.9 or newer and Git.

```bash
git clone https://github.com/faramarz/crossword-poster
cd crossword-poster
python3 -m venv .venv
source .venv/bin/activate              # Windows (Command Prompt): .venv\Scripts\activate
pip install -e ".[dev]"
crossword-poster install-browser       # one-time download; needed for the end-to-end tests
crossword-poster doctor                # should end with "Everything is ready."
```

The `dev` extra installs `pytest`, `ruff`, `build`, `openpyxl` and `pyyaml`.

## Run the checks

CI runs these on every pull request. Run them before you push:

```bash
ruff check .
ruff format --check .        # to fix formatting automatically: ruff format .
pytest -m "not e2e"          # fast unit tests, no browser needed
pytest -m e2e                # end-to-end tests that build real posters (about a minute; needs Chromium)
pytest                       # everything
```

The end-to-end tests skip themselves when Chromium cannot start. CI runs them on Linux. On macOS and Windows, CI runs
`doctor`, the unit tests and a real build of the sample poster. The unit tests run on Python 3.9 to 3.14. Another CI job
builds the wheel and sdist, checks them with `twine check`, and runs the unit tests from the sdist.

Try your change by hand as well:

```bash
crossword-poster sample --out /tmp/try
```

## Project layout

```text
crossword_poster/   the package: cli, pipeline, pool, generate, validate, render_news, actual_size, verify, crops, ...
crossword_poster/fonts/     bundled fonts (SIL OFL) and their licence texts
crossword_poster/samples/   the bundled sample clues
examples/           sample_birthday.csv (fictional) and sample_clues.csv (general trivia)
scripts/            build_all.sh, build_sample.sh (regenerates the images in docs/), check_licenses.sh
docs/               GUIDE.md, CLI.md, TROUBLESHOOTING.md, ARCHITECTURE.md and the sample images
tests/              pytest suite (unit tests and end-to-end tests)
data/               your private clue files (gitignored)
```

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains the pipeline, the module map, the grid generator, the fit loop and
the checks. Read it before a larger change.

## Code conventions

- Python 3.9 must keep working. Use `from __future__ import annotations` and `Optional[...]`.
- `ruff check` and `ruff format --check` must pass (line length 120).
- Anything a user can fix (bad input, missing browser) raises `UserError` (or a subclass) with a plain message and a "how to
  fix" hint. Only real bugs should produce a traceback.
- Console output must be ASCII-safe, because some Windows consoles cannot show other characters.
- Output must stay deterministic: the same clues and seed give the same grid.
- Add or update tests for every behaviour change. Put browser-free tests in the normal suite and mark tests that need
  Chromium with `@pytest.mark.e2e`.
- Keep the documentation in step with the code. If you change a command line option, run
  `python scripts/sync_cli_docs.py` (it copies the `--help` text into `docs/CLI.md`; a test checks that) and update any
  other page that mentions it.
- Write in plain language in anything a user reads: short sentences, no jargon without a one-line explanation.

## Commits and pull requests

- Make small, focused pull requests. One idea per pull request is easiest to review.
- Write commit messages in the imperative mood with a short summary line, for example `Add landscape example to the guide`.
  Add detail in the body when the reason is not obvious.
- Open an issue first for a big change, so we can agree on the approach before you spend time on it.
- Fill in the pull request template. Say what changed, why, and how you tested it.
- Make sure CI is green. A pull request that changes the look of a poster should include a before and after image made from the
  fictional sample, not from real clues.
- If your change is user-visible, add a line under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Proposing a new poster size or style

**A size.** Any `WIDTHxHEIGHT` in inches already works: sizes without tuned settings are scaled from the nearest tuned one.
Propose a tuned size when the scaled result is not good enough. Open a feature request and include the size, what it is for
(for example "A1 for a UK print shop"), and the summary lines from a build of the fictional sample at that size. Then follow
"Adding a size or a style" in [ARCHITECTURE.md](docs/ARCHITECTURE.md): add an entry to `SIZES` in `render_news.py`, build the
sample, read the square and font sizes from the summary, and check the actual-size page.

**A style.** Describe the look and when someone would pick it (for example "a dark blue for a graduation"). A sketch or a
picture helps. The new style needs a variant in the renderer, entries in the pipeline, verifier and crop checks, and tests.
Styles that need new artwork (like the cake and party hat) should keep the file size small and print well in black and
white or grey.

## Good first issues

Some ideas, from small to larger:

- Improve a page in `docs/`: fix a confusing sentence, add a missing step, or add a picture.
- Translate the beginner guide into another language (open an issue first so work is not duplicated).
- Add named paper sizes such as `--size A2` and `--size A1`.
- Add another small piece of artwork for the `icons` style, such as a balloon or a ring.
- Add a short screen recording or screenshots of the install steps for each operating system.

## Releasing (maintainer notes)

1. Update the version in `crossword_poster/__init__.py` and move the `[Unreleased]` notes in `CHANGELOG.md` under the new
   version and date.
2. Run the full checks. If a poster's look changed, regenerate the images with `scripts/build_sample.sh` and look at them.
   If a command's options changed, run `python scripts/sync_cli_docs.py` (a test fails when `docs/CLI.md` is out of date).
3. Commit, then tag the commit `vX.Y.Z` and push the tag. The `Release` workflow builds the sdist and wheel and creates
   the GitHub Release with the notes from `CHANGELOG.md` (preview them with `python scripts/release_notes.py X.Y.Z`).
   Nothing is uploaded to PyPI.
