"""The end-to-end build: clues file -> grid -> validation -> posters, answer key, answer sheet, check page -> checks.

``build(BuildOptions(...))`` is what ``crossword-poster build`` and ``crossword-poster sample`` call. Working files
(grid.json, per-variant PDFs, fit reports) go into ``<out>/details``; the files a person needs are copied to ``<out>``
under friendly names.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import actual_size, render_news
from . import generate as gen
from . import pool as poolmod
from . import validate as val
from . import verify as ver
from .common import BLEED, browser_context, check_chromium, check_colour, chromium_fix_message, parse_size
from .errors import EnvironmentProblem, IncompleteGrid, UserError

STYLES = {"black": "A", "icons": "B", "grey": "C"}
FOLDERS = {"A": "A_black", "B": "B_spot", "C": "C_grey"}
TUNED_WIDTH_MIN = 18.0
Log = Callable[[str], None]


@dataclass
class BuildOptions:
    """Everything ``build`` needs. The defaults match the command line."""

    clues: str
    out: str = "out"
    title: str = render_news.DEFAULT_TITLE
    subtitle: str = render_news.DEFAULT_BYLINE
    sizes: list = field(default_factory=lambda: ["24x36"])
    style: str = "grey"
    seed: int = 1
    attempts: int = 1000
    workers: int = max(1, min(4, os.cpu_count() or 1))
    require_all: bool = False
    clue_column: Optional[str] = None
    answer_column: Optional[str] = None
    id_column: Optional[str] = None
    grid_column: Optional[str] = None
    min_len: int = poolmod.DEFAULT_MIN_LEN
    max_len: int = poolmod.DEFAULT_MAX_LEN
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    noise: float = 6.0
    passes: int = 6
    aspect: float = 1.0
    grow_tries: int = 6
    time_limit: float = 180.0
    block_fill: Optional[str] = None
    grey_fill: str = "#a3a3a3"
    spot_text: str = ""
    mode: str = "any"
    png_width: int = 1200
    no_key: bool = False
    no_solution: bool = False
    no_actual_size: bool = False
    no_verify: bool = False
    no_crops: bool = False
    verbose: bool = False


@dataclass
class SizeInfo:
    """What was produced for one poster size."""

    size: str
    cell_in: float
    clue_pt: float
    warnings: list = field(default_factory=list)


@dataclass
class BuildResult:
    """Outcome of a build: files written, per-size details, words left out and the verification status."""

    out: str
    files: list = field(default_factory=list)  # (path relative to out, description)
    sizes: list = field(default_factory=list)
    grid_cols: int = 0
    grid_rows: int = 0
    words_placed: int = 0
    left_out: list = field(default_factory=list)  # dicts: answer, clue, reason
    checks_ok: bool = True
    seconds: float = 0.0


def parse_sizes(text: str) -> list[str]:
    """``'18x24, 24x36'`` -> ``['18x24', '24x36']`` (validated, normalised, de-duplicated)."""
    out = []
    for part in text.split(","):
        if part.strip():
            w, h = parse_size(part)
            name = f"{w:g}x{h:g}"
            if name not in out:
                out.append(name)
    if not out:
        raise UserError(
            "No poster size given.", "use --size 24x36 (width x height in inches); several sizes: 18x24,24x36"
        )
    return out


def _step(log: Log, n: int, total: int, msg: str) -> None:
    log(f"\n[{n}/{total}] {msg}")


def build(opts: BuildOptions, log: Log = lambda m: print(m, flush=True)) -> BuildResult:
    """Run the whole pipeline and return what was produced. Raises UserError for problems the user can fix."""
    t0 = time.time()
    if opts.style not in (*STYLES, "all"):
        raise UserError(f"Unknown style {opts.style!r}.", "choose grey, black, icons or all")
    check_colour(opts.block_fill, "--block-fill")
    check_colour(opts.grey_fill, "--grey-fill")
    sizes = opts.sizes
    for s in sizes:
        w, _ = parse_size(s)
        if w < TUNED_WIDTH_MIN:
            log(f"  note: {s} is smaller than the tuned sizes (18x24 and up); the text may come out very small.")
    letters = ["A", "B", "C"] if opts.style == "all" else [STYLES[opts.style]]
    names = {"A": "black", "B": "icons", "C": "grey"}
    out = opts.out
    details = os.path.join(out, "details")
    total = 6

    result = BuildResult(out=os.path.abspath(out))

    # 1. read the clues
    _step(log, 1, total, "Reading your clues")
    rows, rep = poolmod.build_pool(
        opts.clues, opts.clue_column, opts.answer_column, opts.id_column, opts.grid_column, opts.min_len, opts.max_len
    )
    if os.path.isfile(os.path.join(details, "grid.json")):
        shutil.rmtree(details, ignore_errors=True)  # a previous build's working folder; start clean
    os.makedirs(details, exist_ok=True)
    poolmod.write_pool(rows, os.path.join(details, "pool.csv"))
    report_path = os.path.join(details, "pool_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    if opts.verbose:
        poolmod.print_pool_report(rep, report_path)
    else:
        _brief_pool_report(rep, log)

    ok, detail = check_chromium()
    if not ok:
        raise EnvironmentProblem(
            f"Chromium (the browser that prints the poster) is not working: {detail}", chromium_fix_message()
        )

    # 2. build the grid
    _step(log, 2, total, f"Building the crossword grid ({len(rows)} answers; this can take a minute for big lists)")
    sol = gen.solve(
        [r["grid"] for r in rows], opts.max_width, opts.max_height, opts.attempts, opts.seed, opts.noise, opts.passes,
        opts.workers, opts.aspect, opts.grow_tries, log=log, time_limit=opts.time_limit or None,
    )  # fmt: skip
    by_grid = {r["grid"]: r for r in rows}
    result.left_out = [
        dict(answer=by_grid[w]["display"], clue=by_grid[w]["clue"], reason=why, row=by_grid[w]["row"])
        for w, why in sol.left_out.items()
    ]
    if result.left_out:
        log(f"\n  {len(result.left_out)} answer(s) could not be placed:")
        for item in result.left_out:
            log(f"    - {item['answer']} (row {item['row']}): {item['reason']}")
        log(
            "  To fit them: choose a bigger --size, use fewer or shorter answers, raise --attempts, or try another --seed."
        )
        if sol.stats.get("time_limit_hit"):
            log(
                f"  The search stopped at the time limit of {opts.time_limit:g} s. With fewer answers (30 to 60 is "
                "ideal) it is much quicker; or give it longer with --time-limit."
            )
        if opts.require_all:
            raise IncompleteGrid("Not every answer fits, and --require-all was given, so no poster was made.")
    placed_rows = [r for r in rows if r["grid"] not in sol.left_out]
    # timing is left out of grid.json so the same clues and seed always give byte-identical files
    stable_stats = {k: v for k, v in sol.stats.items() if k != "seconds"}
    res = gen.attach_pool(gen.to_result(sol.board, [], stable_stats), placed_rows)
    gen.write_grid_files(res, details)
    st = sol.stats
    result.grid_cols, result.grid_rows, result.words_placed = st["bbox_cols"], st["bbox_rows"], st["words_placed"]
    log(
        f"  {st['words_placed']} words in a {st['bbox_cols']} x {st['bbox_rows']} grid (seed {opts.seed}, {st['seconds']}s)"
    )

    # 3. validate
    _step(log, 3, total, "Checking the grid")
    grid_json = os.path.join(details, "grid.json")
    errs, info = val.validate(grid_json, pool=placed_rows)
    if errs:
        raise UserError(
            f"The generated grid failed its own validation: {errs}", "this is a bug; please report it with your CSV"
        )
    log("  grid is valid: every word crosses, every clue matches")

    # 4. posters
    _step(log, 4, total, f"Printing the poster(s) with Chromium: {', '.join(sizes)} ({opts.style})")
    ropts = render_news.RenderOptions(
        opts.title, opts.subtitle, opts.block_fill, opts.grey_fill, opts.spot_text, opts.mode, opts.png_width,
        os.path.join(details, ".build"), True,
    )  # fmt: skip
    an = render_news.load_grid(grid_json)
    make = set(letters) | (set() if opts.no_key else {"key"})
    with browser_context() as ctx:
        for s in sizes:
            report = render_news.render_size(ctx, an, s, details, make, ropts, log=log)
            result.sizes.append(SizeInfo(s, report["fit"]["cell"], report["fit"]["fs"], report["warnings"]))
        # 5. answer sheet and check page
        _step(log, 5, total, "Making the answer sheet and the actual-size check page")
        if not opts.no_solution:
            render_news.render_solution(ctx, an, details, ropts)
    if not opts.no_actual_size:
        for s in sizes:
            actual_size.from_fit(os.path.join(details, s), FOLDERS[letters[0]], opts.title)
    _collect(result, details, out, sizes, letters, names, opts)

    # 6. verify
    if not opts.no_verify:
        _step(log, 6, total, "Checking the finished files")
        rc = ver.verify(details, opts.title, opts.subtitle, sizes, grid_json, opts.block_fill, opts.grey_fill,
                        crops=not opts.no_crops, verbose=opts.verbose)  # fmt: skip
        result.checks_ok = rc == 0
    result.seconds = time.time() - t0
    log(summary(result, opts))
    return result


def _brief_pool_report(rep: dict, log: Log) -> None:
    """The short form of the pool report: counts, then every skipped row and warning."""
    log(f"  {rep['kept']} usable clues from {rep['rows_in']} rows")
    for note in rep["notes"]:
        log(f"  note: {note}")
    for s in rep["skipped"]:
        if not s.get("duplicate"):
            log(f"  skipped row {s['row']} ({s['answer']!r}): {s['reason']}")
    for w in rep["warnings"]:
        log(f"  warning: {w}")
    if rep["giveaways"]:
        log(
            f"  {len(rep['giveaways'])} clue(s) may contain an answer (see details/pool_report.json): check that they are not giveaways"
        )


def _copy(src: str, dst: str) -> bool:
    if os.path.exists(src):
        shutil.copyfile(src, dst)
        return True
    return False


def _collect(
    result: BuildResult, details: str, out: str, sizes: list, letters: list, names: dict, opts: BuildOptions
) -> None:
    """Copy the deliverables out of the working folder under friendly names and record them."""

    def add(src: str, name: str, what: str) -> None:
        if _copy(os.path.join(details, src), os.path.join(out, name)):
            result.files.append((name, what))

    for s in sizes:
        tw, th = parse_size(s)
        for letter in letters:
            base = f"poster_{s}_{names[letter]}"
            folder = f"{s}/{FOLDERS[letter]}"
            add(
                f"{folder}/poster.pdf",
                f"{base}_bleed.pdf",
                f"PRINT THIS: {tw + 2 * BLEED:g} x {th + 2 * BLEED:g} in, with 0.125 in bleed",
            )
            add(
                f"{folder}/poster_trim.pdf",
                f"{base}_trim.pdf",
                f"{tw:g} x {th:g} in, no bleed (for printers that add their own)",
            )
            add(f"{folder}/poster.png", f"{base}_preview.png", "picture preview of the poster")
        if not opts.no_key:
            add(f"{s}/key.pdf", f"answer_key_{s}_11x17.pdf", "answer key, scaled to 11 x 17 in")
        if not opts.no_actual_size:
            add(
                f"{s}/actual_size_check_letter.pdf",
                f"actual_size_check_{s}.pdf",
                "letter page to print at 100% and judge the real sizes",
            )
    if not opts.no_solution:
        add("solution_letter.pdf", "answer_sheet_letter.pdf", "answer sheet (filled grid) on one letter page")
        add("solution_letter.png", "answer_sheet_letter.png", "picture of the answer sheet")
    add("clues.csv", "clues_and_answers.csv", "numbered list of every clue and answer")


def summary(result: BuildResult, opts: BuildOptions) -> str:
    """The plain-language summary printed at the end of a build."""
    lines = ["", f"Done in {result.seconds:.0f}s. Your files are in: {result.out}", ""]
    width = max((len(n) for n, _ in result.files), default=0)
    for name, what in result.files:
        lines.append(f"  {name.ljust(width)}  {what}")
    lines.append(
        f"  details/{' ' * max(0, width - 8)}  working files (grid.json, checks, one folder per size and style)"
    )
    lines.append("")
    lines.append(f"Grid: {result.grid_cols} x {result.grid_rows} squares, {result.words_placed} words.")
    for s in result.sizes:
        lines.append(
            f"Poster {s.size}: each square is {s.cell_in:.3f} in ({s.cell_in * 25.4:.1f} mm); clue text is {s.clue_pt:.1f} pt."
        )
        lines.extend(f"  Warning: {w}" for w in s.warnings)
    if result.left_out:
        lines.append(
            f"{len(result.left_out)} answer(s) were left out: " + ", ".join(i["answer"] for i in result.left_out) + "."
        )
        lines.append("  Fix: bigger --size, fewer or shorter answers, more --attempts or a different --seed.")
    else:
        lines.append("Every answer was placed.")
    if not opts.no_verify:
        lines.append(
            "Output checks: all passed."
            if result.checks_ok
            else "Output checks: SOME FAILED (see above); look at the PDFs before printing."
        )
    lines.append("Before ordering a big print, print the actual-size check page at 100% and look at the real sizes.")
    return "\n".join(lines)
