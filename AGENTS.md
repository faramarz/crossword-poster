# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI and others) working **in this
repository**. People read it too. The human version is [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

`crossword-poster` is a Python command line tool. It turns a spreadsheet of clues and answers into a print-ready,
newspaper-style crossword poster PDF (plus an answer key, an answer sheet and an actual-size check page). It lays out the
grid with its own generator, then prints with headless Chromium through Playwright. The audience is non-programmers
making a poster for a friend's or relative's special occasion, so messages and docs must be plain and friendly.

- Package: `crossword_poster/` (entry point `crossword_poster.cli:main`). Version lives in `crossword_poster/__init__.py`.
- Python 3.9 to 3.14 must keep working.
- Not published on PyPI. People install it from GitHub.

## Set up

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows (Command Prompt): .venv\Scripts\activate
pip install -e ".[dev,xlsx]"
crossword-poster install-browser       # one-time Chromium download; the end-to-end tests need it
crossword-poster doctor                # should end with "Everything is ready."
```

The extras are `dev` (pytest, ruff, build, twine, openpyxl, pyyaml) and `xlsx` (openpyxl, defusedxml).

## Check your work

Run these before you say a change is done. CI runs the same.

```bash
ruff check .
ruff format --check .        # fix with: ruff format .
pytest -q                    # everything; end-to-end tests skip themselves when Chromium cannot start
pytest -m "not e2e" -q       # fast, no browser
pytest -m e2e -q             # builds real posters (about a minute; needs Chromium)
```

The only custom pytest marker is `e2e`. After you change any `--help` text or option, run
`python scripts/sync_cli_docs.py`: it copies the help text into `docs/CLI.md`, and `tests/test_docs.py` fails if the two
disagree. For a visual check, build the fictional sample and look at the PNG and the actual-size page:

```bash
crossword-poster sample --out /tmp/try --size 24x36
```

## Where things are

```text
crossword_poster/   the package (cli, pipeline, pool, generate, validate, render_news, actual_size, verify, crops, ...)
crossword_poster/fonts/    bundled fonts (SIL OFL) and licence texts
crossword_poster/samples/  the bundled fictional sample clues
examples/           sample_birthday.csv (fictional) and sample_clues.csv (general trivia)
docs/               GUIDE.md, AI_AGENTS.md, CLI.md, TROUBLESHOOTING.md, ARCHITECTURE.md, sample images
scripts/            build_all.sh, build_sample.sh, check_licenses.sh, sync_cli_docs.py, release_notes.py
skills/crossword-poster/   the Claude skill for people who make posters (SKILL.md)
.claude/skills/crossword-poster   a symlink to skills/crossword-poster, so Claude Code finds the skill in a clone
tests/              pytest suite
data/               private clue files (gitignored)
```

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before a larger change. It explains the pipeline (pool, generate,
validate, render, verify), the fit loop and how to add a size or a style.

## Conventions

- Use `from __future__ import annotations` and `Optional[...]` (Python 3.9). Line length is 120. `ruff check` and
  `ruff format --check` must pass.
- Anything a user can fix (bad input, missing browser) raises `UserError` (or a subclass) with a plain message and a "how
  to fix" hint. Only real bugs should produce a traceback.
- Console output must be ASCII-safe (some Windows consoles cannot show other characters).
- Output must stay deterministic: the same clues and seed give the same grid.
- Add or update tests for every behaviour change. Mark tests that need Chromium with `@pytest.mark.e2e`.
- Keep docs in step with the code, and write them in plain language: short sentences, no jargon without a one-line
  explanation. Commands in docs go on one line (no trailing backslash), because they must paste into Windows too.
- Install instructions must install from GitHub (`git+https://github.com/faramarz/crossword-poster`), never by the bare
  name `crossword-poster`: a test enforces this.
- If your change is visible to users, add a line under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- Keep `skills/crossword-poster/SKILL.md` and `docs/AI_AGENTS.md` accurate when commands or flags change.
- Do not commit, push or tag unless the person asked you to. Small, focused changes with an imperative commit message.

## Privacy: never commit real clues

This tool is used for gifts and surprises, so clue files are personal.

- Never put real clues, names or answers in code, tests, docs, examples, issues, pull requests or commit messages. Use
  made-up ones. The fictional sample is `examples/sample_birthday.csv` ("Alex's 50th").
- A person's own clue files belong in `data/` or in a file named `*.private.*`; both are gitignored. Do not read them
  unless the person asks, and do not copy them anywhere.
- The tool runs offline and must keep doing so. Do not add network calls, telemetry or uploads. `crossword-poster
  feedback` only prints links.

## Licence

[PolyForm Noncommercial License 1.0.0](LICENSE): free for noncommercial use; commercial use needs a licence from the
maintainer. Source files are not "open source" in the OSI sense, so do not describe them that way. Bundled fonts are SIL
OFL (see `THIRD_PARTY_LICENSES.md`). By contributing you agree your change is released under the same licence (see
[CONTRIBUTING.md](CONTRIBUTING.md#licence-of-contributions)). Do not add a dependency without checking its licence
(`scripts/check_licenses.sh`).

## If the person wants to MAKE a poster (not change the code)

Do not edit the repository. Use the command line tool:

1. `crossword-poster doctor` (install per [README.md](README.md#quick-start) if missing; Chromium comes from
   `crossword-poster install-browser`).
2. Get their clues into a CSV with the columns `clue` and `answer` (`crossword-poster template my_clues.csv` writes a
   starter). Check for swapped columns, duplicates, answers with digits, and clues that are too long.
3. `crossword-poster build --clues my_clues.csv --title "Their Title" --size 24x36 --style grey --out poster/`
4. Read the summary, look at the preview PNG, and tell them to send `poster_..._bleed.pdf` to a print shop.

The step-by-step version, with prompts, is [docs/AI_AGENTS.md](docs/AI_AGENTS.md). Claude Code users get the project
skill in `skills/crossword-poster` automatically. Keep their clues on their computer.
