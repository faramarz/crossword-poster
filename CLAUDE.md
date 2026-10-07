@AGENTS.md

## Claude Code notes

- The project skill `crossword-poster` lives in `skills/crossword-poster/` and is linked into `.claude/skills/`. Use it
  when the person wants to make a poster or clean up a clue list. Keep it in sync with the CLI when flags change.
- For visual checks, build the fictional sample (`crossword-poster sample --out /tmp/try --size 24x36`) and open the
  preview PNG and the actual-size page. Never use real clues for screenshots, tests or examples.
- After editing any `--help` text, run `python scripts/sync_cli_docs.py`, then `pytest -q tests/test_docs.py`.
- Run `ruff check .` and `ruff format --check .` before finishing, and `pytest -m "not e2e" -q` for a fast pass.
- Do not commit, push or tag unless asked.
