"""Command line entry point: python -m crossword_poster <command> [options]

  build           end to end: pool -> generate -> validate -> render poster(s) + key + solution + actual-size check -> verify
  pool            clue/answer CSV -> normalised pool + quality report (giveaways, duplicates, bad lengths)
  generate        freeform crossword generator (--all: every word must be placed)
  validate        independent validator for a grid.json
  render          newspaper-style poster renderer (main)
  render-classic  earlier renderer (styles A / B / M)
  actual-size     letter-size 100% scale check page cut out of a finished poster
  verify          checks on a build directory (page sizes, fonts, colours, clues, margins, strokes)
  crops           corner/edge crops + per-cell stroke check
  transpose       transpose a grid.json (rows <-> cols)
"""
import argparse
import csv
import json
import os
import sys
import time

COMMANDS = ("build", "pool", "generate", "validate", "render", "render-classic", "actual-size", "verify", "crops", "transpose")
STYLES = {"black": "A", "icons": "B", "grey": "C"}


def _build(argv):
    from . import actual_size, generate as gen, pool as poolmod, render_news, validate as val, verify as ver
    from .common import parse_size

    ap = argparse.ArgumentParser(
        prog="crossword_poster build",
        description="End-to-end build: pool -> grid (all answers required) -> validate -> poster PDFs/PNG + key + "
                    "solution sheet + actual-size check -> verify.",
        epilog="Example: python -m crossword_poster build --clues examples/sample_clues.csv --size 24x36 --style grey --out out/")
    g = ap.add_argument_group("input")
    g.add_argument("--clues", required=True, help="CSV with one clue and one answer per row")
    g.add_argument("--clue-column", default="clue")
    g.add_argument("--answer-column", default="answer")
    g.add_argument("--grid-column", default=None, help="optional pre-normalised grid-word column")
    g.add_argument("--id-column", default=None, help="optional unique id column (default: row number)")
    g.add_argument("--min-len", type=int, default=3)
    g.add_argument("--max-len", type=int, default=15)
    g = ap.add_argument_group("grid generation")
    g.add_argument("--max-width", type=int, default=None, help="search window width in cells (default: estimated, grown if needed)")
    g.add_argument("--max-height", type=int, default=None, help="search window height in cells")
    g.add_argument("--attempts", type=int, default=1000, help="randomized layouts per window (default %(default)s)")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)), help="parallel processes (result does not depend on it)")
    g.add_argument("--noise", type=float, default=6.0)
    g.add_argument("--passes", type=int, default=6)
    g.add_argument("--aspect", type=float, default=0.8, help="auto window: width/height ratio")
    g.add_argument("--grow-tries", type=int, default=6)
    g = ap.add_argument_group("poster")
    g.add_argument("--size", default="24x36", help="trim size(s) WxH in inches, comma separated (default %(default)s; e.g. 18x24,24x36,36x48)")
    g.add_argument("--style", default="black", choices=list(STYLES) + ["all"],
                   help="black = solid black blocks, grey = grey blocks (saves ink), icons = black + spot icons, all = the three")
    g.add_argument("--block-fill", default=None, metavar="COLOR", help="CSS colour for the non-letter squares in every variant (overrides --style colours)")
    g.add_argument("--grey-fill", default="#a3a3a3", help="colour of the grey style (default %(default)s)")
    g.add_argument("--title", default="My Crossword")
    g.add_argument("--byline", "--subtitle", dest="byline", default="A custom crossword poster.")
    g.add_argument("--spot-text", default="", help="text reversed out of the widest void in the icons style")
    g.add_argument("--mode", default="any", choices=["any", "full"], help="'full' forbids the clue-wrap layout beside the grid")
    g.add_argument("--png-width", type=int, default=1200)
    g = ap.add_argument_group("output")
    g.add_argument("--out", default="out", help="output directory (default %(default)s)")
    g.add_argument("--no-key", action="store_true", help="skip the 11x17 answer key")
    g.add_argument("--no-solution", action="store_true", help="skip the letter-size solution sheet")
    g.add_argument("--no-actual-size", action="store_true", help="skip the actual-size check page")
    g.add_argument("--no-verify", action="store_true", help="skip the output verification")
    g.add_argument("--no-crops", action="store_true", help="verify without the per-cell stroke crops (faster)")
    a = ap.parse_args(argv)

    out = a.out
    os.makedirs(out, exist_ok=True)
    sizes = [s.strip().lower() for s in a.size.split(",") if s.strip()]
    for s in sizes:
        parse_size(s)
    letters = ["A", "B", "C"] if a.style == "all" else [STYLES[a.style]]
    folders = {"A": "A_black", "B": "B_spot", "C": "C_grey"}
    t0 = time.time()

    def step(n, msg):
        print(f"\n[{n}/5] {msg}", flush=True)

    # 1. pool
    step(1, "pool")
    rows, rep = poolmod.build_pool(a.clues, a.clue_column, a.answer_column, a.id_column, a.grid_column, a.min_len, a.max_len)
    pool_csv = os.path.join(out, "pool.csv")
    poolmod.write_pool(rows, pool_csv)
    json.dump(rep, open(os.path.join(out, "pool_report.json"), "w"), indent=1, ensure_ascii=False)
    print(f"  {rep['kept']} usable of {rep['rows_in']} rows; {len(rep['skipped'])} skipped; {len(rep['giveaways'])} giveaway pairs "
          f"(details: {os.path.join(out, 'pool_report.json')})")
    for s in rep["skipped"]:
        print(f"  skipped row {s['row']} ({s['answer']!r}): {s['reason']}")
    if not rows:
        print("ERROR: no usable clues", file=sys.stderr)
        return 1

    # 2. generate (all answers required)
    step(2, "generate grid (every answer required)")
    b, stats = gen.generate_all([r["grid"] for r in rows], a.max_width, a.max_height, a.attempts, a.seed, a.noise,
                                a.passes, a.workers, a.aspect, a.grow_tries, log=print)
    if b is None:
        print("ERROR: no complete layout; raise --attempts / --grow-tries or give larger --max-width/--max-height", file=sys.stderr)
        return 2
    res = gen.attach_pool(gen.to_result(b, [], stats), rows)
    gen.write_grid_files(res, out)
    print(f"  {stats['words_placed']} words in {stats['bbox_cols']} x {stats['bbox_rows']} cells, density {stats['density']} "
          f"(window {stats['bound'][0]}x{stats['bound'][1]}, seed {a.seed}, {stats['seconds']}s)")

    # 3. validate
    step(3, "validate")
    errs, info = val.validate(os.path.join(out, "grid.json"), pool=rows)
    for line in info:
        print("  " + line)
    print("  ERRORS:", errs if errs else "none")
    if errs:
        return 1

    # 4. render
    grid_json = os.path.join(out, "grid.json")
    common = ["--outroot", out, "--title", a.title, "--byline", a.byline, "--grey-fill", a.grey_fill,
              "--png-width", str(a.png_width), "--spot-text", a.spot_text, "--mode", a.mode, "--quiet"]
    if a.block_fill:
        common += ["--block-fill", a.block_fill]
    step(4, f"render {', '.join(sizes)} ({a.style})")
    for s in sizes:
        make = ",".join(letters + ([] if a.no_key else ["key"]))
        rc = render_news.main([grid_json, "--trim", s, "--make", make] + common)
        if rc:
            print(f"ERROR: render failed for {s}", file=sys.stderr)
            return rc
        if not a.no_actual_size:
            outp, _ = actual_size.from_fit(os.path.join(out, s), folders[letters[0]], a.title)
            print(f"  actual-size check page: {outp}")
    if not a.no_solution:
        rc = render_news.main([grid_json, "--solution"] + common)
        if rc:
            return rc

    # 5. verify
    if not a.no_verify:
        step(5, "verify outputs")
        rc = ver.verify(out, a.title, a.byline, sizes, grid_json, a.block_fill, a.grey_fill, crops=not a.no_crops)
        if rc:
            return rc
    print(f"\nBuilt in {time.time() - t0:.0f}s. Outputs in {os.path.abspath(out)}")
    for s in sizes:
        for l in letters:
            print(f"  {os.path.join(out, s, folders[l])}/poster.pdf (with bleed), poster_trim.pdf, poster.png")
        if not a.no_key:
            print(f"  {os.path.join(out, s)}/key.pdf")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"unknown command {cmd!r}; choose from: {', '.join(COMMANDS)}", file=sys.stderr)
        return 2
    if cmd == "build":
        return _build(rest)
    mod = {"pool": "pool", "generate": "generate", "validate": "validate", "render": "render_news",
           "render-classic": "render_classic", "actual-size": "actual_size", "verify": "verify",
           "crops": "crops", "transpose": "transpose"}[cmd]
    import importlib
    return importlib.import_module(f".{mod}", __package__).main(rest) or 0
