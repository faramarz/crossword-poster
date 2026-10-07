"""Keep the ``--help`` excerpts in docs/CLI.md identical to what the program prints.

    python scripts/sync_cli_docs.py           # rewrite the help blocks in docs/CLI.md
    python scripts/sync_cli_docs.py --check   # exit 1 (and say so) when docs/CLI.md is out of date

A help block is a ```text fenced block whose first line is ``usage: crossword-poster <command> ...`` (one block per
command) or the first line of ``crossword-poster --help``. Everything else in the file is left alone. The help is
captured at a terminal width of 100 columns so that the line wrapping is always the same.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_MD = ROOT / "docs" / "CLI.md"
BLOCK = re.compile(r"```text\n(.*?)\n```", re.S)
TOP_LINE = re.compile(r"crossword-poster \d+\.\d+\.\d+: turn a spreadsheet")
USAGE_LINE = re.compile(r"usage: crossword-poster ([a-z-]+) ")


def help_text(command: str | None) -> str:
    """What ``crossword-poster [command] --help`` prints (at 100 columns)."""
    env = dict(os.environ, COLUMNS="100", PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    args = [sys.executable, "-m", "crossword_poster", *([command] if command else []), "--help"]
    out = subprocess.run(args, capture_output=True, text=True, env=env, check=True)
    return out.stdout.rstrip("\n")


def block_command(block: str):
    """``None`` for the top-level help block, the command name for a command's block, ``False`` for any other block."""
    first = block.split("\n", 1)[0]
    if TOP_LINE.match(first):
        return None
    m = USAGE_LINE.match(first)
    return m.group(1) if m else False


def blocks(text: str):
    """Yield ``(command, current_block)`` for every help block in ``text``."""
    for m in BLOCK.finditer(text):
        command = block_command(m.group(1))
        if command is not False:
            yield command, m.group(1)


def sync(text: str) -> str:
    """``text`` with every help block replaced by the program's current help."""

    def replace(m: re.Match) -> str:
        command = block_command(m.group(1))
        if command is False:
            return m.group(0)
        return "```text\n" + help_text(command) + "\n```"

    return BLOCK.sub(replace, text)


def main(argv: list[str]) -> int:
    """Command line entry point."""
    text = CLI_MD.read_text(encoding="utf-8")
    new = sync(text)
    if "--check" in argv:
        if new != text:
            print("docs/CLI.md is out of date. Run: python scripts/sync_cli_docs.py", file=sys.stderr)
            return 1
        return 0
    if new != text:
        CLI_MD.write_text(new, encoding="utf-8")
        print("updated docs/CLI.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
