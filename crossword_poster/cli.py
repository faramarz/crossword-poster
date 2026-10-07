"""Command line interface: ``crossword-poster <command> [options]`` (also ``python -m crossword_poster``)."""

from __future__ import annotations

import argparse
import contextlib
import csv
import os
import sys
from importlib import import_module, resources
from typing import Optional

from . import __version__
from .errors import UserError
from .pipeline import STYLES, BuildOptions, build, parse_sizes

ISSUES_URL = "https://github.com/faramarz/crossword-poster/issues"

EASY = {
    "build": "make a poster, answer key, answer sheet and size-check page from a clues file",
    "sample": "build the bundled birthday example so you can see the result in one command",
    "template": "write a starter clues file (CSV) to fill in",
    "doctor": "check that this computer is ready (Python, fonts, Chromium)",
}
POWER = {
    "pool": "clues file -> cleaned list of answers, with a report of problems",
    "generate": "grid generator on its own",
    "validate": "independent check of a grid.json",
    "render": "poster renderer on its own (from a grid.json)",
    "verify": "checks on the files of a finished build",
    "actual-size": "100% scale check page cut out of a poster PDF",
    "crops": "corner crops and per-square stroke check",
    "transpose": "swap rows and columns of a grid.json",
}
MODULES = {
    "pool": "pool", "generate": "generate", "validate": "validate", "render": "render_news", "verify": "verify",
    "actual-size": "actual_size", "crops": "crops", "transpose": "transpose", "doctor": "doctor",
}  # fmt: skip


def top_help() -> str:
    """The text shown by ``crossword-poster --help``."""
    lines = [
        f"crossword-poster {__version__}: turn a spreadsheet of clues and answers into a print-ready crossword poster.",
        "",
        "usage: crossword-poster [--version] <command> [options]",
        "",
        "Start here:",
    ]
    lines += [f"  {k.ljust(12)} {v}" for k, v in EASY.items()]
    lines += ["", "For power users (each runs one stage of `build`):"]
    lines += [f"  {k.ljust(12)} {v}" for k, v in POWER.items()]
    lines += [
        "",
        "Run `crossword-poster <command> --help` for the options of a command.",
        'Typical use:   crossword-poster build --clues my_clues.csv --title "Sam\'s 50th" --size 24x36 --out poster/',
        "Exit status: 0 = success, 1 = built but needs attention (checks failed, or --require-all and some answers did not fit),",
        "             2 = problem with your input or options, 3 = the computer is missing something (run `doctor`).",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------- build
def _build_parser(prog: str = "crossword-poster build") -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=prog,
        description="Read a CSV (or .xlsx) of clues and answers, build a crossword grid with every answer in it, and "
        "print the poster(s), answer key, answer sheet and an actual-size check page.",
        epilog="Example:\n  crossword-poster build --clues my_clues.csv --title \"Sam's 50th Birthday\" "
        "--subtitle \"Clues from everyone who loves you\" --size 24x36 --style grey --out poster/\n\n"
        "Your clues file needs a header row with 'clue' and 'answer' columns (see `crossword-poster template`).\n"
        "Exit status: 0 success; 1 built but needs attention; 2 problem with your input; 3 Chromium missing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )  # fmt: skip
    g = ap.add_argument_group("what to build")
    g.add_argument("--clues", required=True, metavar="FILE", help="CSV or .xlsx with one clue and one answer per row")
    g.add_argument("--title", default="My Crossword", help="title across the top of the poster (default: %(default)r)")
    g.add_argument("--subtitle", "--byline", dest="subtitle", default="A custom crossword poster.",
                   help="line next to the title (default: %(default)r)")  # fmt: skip
    g.add_argument("--size", default="24x36", metavar="WxH",
                   help="poster size in inches; 18x24, 24x36 and 36x48 are tuned; several sizes: 18x24,24x36 (default %(default)s)")  # fmt: skip
    g.add_argument("--style", default="grey", choices=[*STYLES, "all"],
                   help="grey = grey blocks, saves ink and easy to write on; black = solid black blocks; "
                   "icons = black with a cake and party hat; all = all three (default %(default)s)")  # fmt: skip
    g.add_argument("--out", default="out", metavar="DIR", help="folder for the results (default: %(default)s)")
    g.add_argument("--seed", type=int, default=1, help="random seed: the same clues + seed give the same grid; try another for a different layout (default %(default)s)")  # fmt: skip
    g.add_argument("--require-all", action="store_true",
                   help="fail (exit status 1, nothing printed) if any answer cannot be placed; otherwise leave it out and say so")  # fmt: skip
    g = ap.add_argument_group("reading the file")
    g.add_argument(
        "--clue-column",
        default=None,
        metavar="NAME",
        help="header of the clue column (default: clue, clues or question)",
    )
    g.add_argument(
        "--answer-column",
        default=None,
        metavar="NAME",
        help="header of the answer column (default: answer, answers or word)",
    )
    g.add_argument(
        "--id-column", default=None, metavar="NAME", help="optional unique id column (default: the row number)"
    )
    g.add_argument(
        "--grid-column", default=None, metavar="NAME", help="optional column with a ready-made A-Z grid word"
    )
    g.add_argument("--min-len", type=int, default=2, help="shortest allowed answer in letters (default %(default)s)")
    g.add_argument("--max-len", type=int, default=20, help="longest allowed answer in letters (default %(default)s)")
    g = ap.add_argument_group("grid search (the defaults are fine for most files)")
    g.add_argument("--attempts", type=int, default=1000, help="layouts to try per search round (default %(default)s)")
    g.add_argument("--workers", type=int, default=BuildOptions.workers, help="parallel processes; the result does not depend on it (default %(default)s)")  # fmt: skip
    g.add_argument("--max-width", type=int, default=None, help="limit the grid width in squares (default: automatic)")
    g.add_argument("--max-height", type=int, default=None, help="limit the grid height in squares (default: automatic)")
    g.add_argument("--aspect", type=float, default=1.0, help="automatic window: width / height (default %(default)s)")
    g.add_argument(
        "--grow-tries",
        type=int,
        default=6,
        help="times the automatic window is enlarged when nothing fits (default %(default)s)",
    )
    g.add_argument("--noise", type=float, default=6.0, help=argparse.SUPPRESS)
    g.add_argument("--passes", type=int, default=6, help=argparse.SUPPRESS)
    g = ap.add_argument_group("look")
    g.add_argument(
        "--block-fill",
        default=None,
        metavar="COLOR",
        help="CSS colour for the empty squares in every style, e.g. '#c8d6e5'",
    )
    g.add_argument(
        "--grey-fill", default="#a3a3a3", metavar="COLOR", help="the grey of --style grey (default %(default)s)"
    )
    g.add_argument(
        "--spot-text", default="", help="short text (e.g. 50) reversed out of the biggest black area in --style icons"
    )
    g.add_argument("--mode", default="any", choices=["any", "full"], help="'full' forbids clue columns beside the grid")
    g.add_argument("--png-width", type=int, default=1200, help="preview picture width in pixels (default %(default)s)")
    g = ap.add_argument_group("skip things")
    g.add_argument("--no-key", action="store_true", help="skip the 11x17 answer key")
    g.add_argument("--no-solution", action="store_true", help="skip the letter-size answer sheet")
    g.add_argument("--no-actual-size", action="store_true", help="skip the actual-size check page")
    g.add_argument("--no-verify", action="store_true", help="skip the checks on the finished files")
    g.add_argument(
        "--no-crops", action="store_true", help="make the checks faster by skipping the per-square stroke check"
    )
    g.add_argument("--verbose", action="store_true", help="print every check instead of a short summary")
    return ap


def _options_from_args(a: argparse.Namespace) -> BuildOptions:
    return BuildOptions(
        clues=a.clues, out=a.out, title=a.title, subtitle=a.subtitle, sizes=parse_sizes(a.size), style=a.style,
        seed=a.seed, attempts=a.attempts, workers=max(1, a.workers), require_all=a.require_all,
        clue_column=a.clue_column, answer_column=a.answer_column, id_column=a.id_column, grid_column=a.grid_column,
        min_len=a.min_len, max_len=a.max_len, max_width=a.max_width, max_height=a.max_height, noise=a.noise,
        passes=a.passes, aspect=a.aspect, grow_tries=a.grow_tries, block_fill=a.block_fill, grey_fill=a.grey_fill,
        spot_text=a.spot_text, mode=a.mode, png_width=a.png_width, no_key=a.no_key, no_solution=a.no_solution,
        no_actual_size=a.no_actual_size, no_verify=a.no_verify, no_crops=a.no_crops, verbose=a.verbose,
    )  # fmt: skip


def cmd_build(argv: list) -> int:
    """``build``: the end-to-end pipeline."""
    a = _build_parser().parse_args(argv)
    result = build(_options_from_args(a))
    return 0 if result.checks_ok else 1


# ------------------------------------------------------------------ sample
def cmd_sample(argv: list) -> int:
    """``sample``: build the bundled birthday example."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster sample",
        description="Build the bundled, fictional birthday crossword (Alex's 50th) so you can see what the tool makes.",
    )
    ap.add_argument(
        "--out", default="sample-poster", metavar="DIR", help="folder for the results (default: %(default)s)"
    )
    ap.add_argument("--size", default="18x24", metavar="WxH", help="poster size in inches (default %(default)s)")
    ap.add_argument("--style", default="grey", choices=[*STYLES, "all"], help="default %(default)s")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    csv_path = os.path.join(a.out, "sample_birthday.csv")
    with open(csv_path, "wb") as fh:
        fh.write(resources.files("crossword_poster").joinpath("samples", "sample_birthday.csv").read_bytes())
    print(f"Building the sample poster. The clues file it uses was copied to {csv_path} so you can see the format.")
    opts = BuildOptions(
        clues=csv_path, out=a.out, title="Alex's 50th Birthday Crossword", subtitle="Clues from the people who love you",
        sizes=parse_sizes(a.size), style=a.style, seed=a.seed,
    )  # fmt: skip
    return 0 if build(opts).checks_ok else 1


# ---------------------------------------------------------------- template
TEMPLATE_ROWS = (
    ("1", "Capital of France", "Paris"),
    ("2", "Nickname of the clock tower at Westminster", "Big Ben"),
    ("3", "Our favourite pizza topping, the one Sam always picks", "Pineapple"),
)


def cmd_template(argv: list) -> int:
    """``template``: write a starter CSV."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster template",
        description="Write a starter clues file with the right headers and three example rows. Replace the examples "
        "with your own clues (a clue is the question; the answer is the word that goes in the grid).",
    )
    ap.add_argument("out", metavar="OUT.csv", help="where to write the file, e.g. my_clues.csv")
    ap.add_argument("--force", action="store_true", help="overwrite the file if it already exists")
    a = ap.parse_args(argv)
    if os.path.exists(a.out) and not a.force:
        raise UserError(f"{a.out} already exists.", "choose another name, or add --force to overwrite it")
    folder = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(folder, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel opens it as UTF-8
        w = csv.writer(fh)
        w.writerow(["id", "clue", "answer"])
        w.writerows(TEMPLATE_ROWS)
    print(f"Wrote {a.out}. Edit it in Excel / Google Sheets (save as CSV UTF-8), then run:")
    print(f'  crossword-poster build --clues {a.out} --title "My Crossword" --out poster/')
    return 0


# -------------------------------------------------------------------- main
def _commands() -> dict:
    cmds = {"build": cmd_build, "sample": cmd_sample, "template": cmd_template}
    for name, mod in MODULES.items():
        cmds[name] = (lambda m: lambda argv: import_module(f".{m}", __package__).main(argv) or 0)(mod)
    return cmds


def main(argv: Optional[list] = None) -> int:
    """Run the command line. Returns the exit status; user mistakes print a friendly message, not a traceback."""
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):  # never crash on a console that cannot show a character
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="replace")
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(top_help())
        return 0 if argv else 2
    if argv[0] in ("-V", "--version", "version"):
        print(f"crossword-poster {__version__}")
        return 0
    cmd, rest = argv[0], argv[1:]
    commands = _commands()
    if cmd not in commands:
        near = [c for c in commands if c.startswith(cmd[:2])] or list(EASY)
        print(
            f"Error: '{cmd}' is not a command. Did you mean: {', '.join(near)}?\nRun `crossword-poster --help` for the list.",
            file=sys.stderr,
        )
        return 2
    try:
        return commands[cmd](rest)
    except UserError as exc:
        print(f"\nError: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"How to fix: {exc.hint}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        if os.environ.get("CROSSWORD_POSTER_DEBUG"):
            raise
        print(f"\nSomething unexpected went wrong: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        print(
            f"Please report it at {ISSUES_URL} and include your command (set CROSSWORD_POSTER_DEBUG=1 for details).",
            file=sys.stderr,
        )
        return 70
