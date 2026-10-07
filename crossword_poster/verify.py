"""Checks for rendered outputs (everything under OUTROOT written by `build` / `render`).

Covered: page sizes (poster = trim + 0.125 in bleed on every side, trim, key 11x17, letter pages), fonts embedded
(none Type 3), only black / white / the chosen fill colours in the vector content, thinnest stroke, no ink inside the
outer margin, every clue appears exactly once, title and byline present, every PNG neutral grey (R=G=B), DOM checks
recorded in fit.json, and (unless --no-crops) per-cell stroke checks via crops.py.
Prints a PASS/FAIL report; the exit status is 1 on any failure.

Usage:
  crossword-poster verify out/details --title "My Crossword" [--byline "..."] [--sizes 24x36,18x24]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from typing import Optional

from . import pdfutil
from .common import BLEED, parse_size
from .errors import UserError
from .pool import ENUM_RE
from .render_news import DEFAULT_BYLINE, DEFAULT_TITLE, size_config

VARIANTS = ("A_black", "B_spot", "C_grey")
BLACK, WHITE = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)


def hex_rgb(h: str) -> tuple:
    """``'#a3a3a3'`` -> ``(0.639, 0.639, 0.639)``."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(round(int(h[i : i + 2], 16) / 255, 3) for i in (0, 2, 4))


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


class Report:
    """Collects PASS/FAIL lines."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.passed = 0
        self.failed: list[str] = []

    def check(self, ok: bool, message: str) -> None:
        """Record one check; failures are always printed, passes only when verbose."""
        if ok:
            self.passed += 1
        else:
            self.failed.append(message)
        if self.verbose or not ok:
            print(("PASS " if ok else "FAIL ") + message)


def clue_text(clue: dict) -> str:
    """The clue as printed: whitespace normalised, with ``(n)`` appended when it has no enumeration."""
    text = re.sub(r"\s+", " ", clue["clue"]).strip()
    if not ENUM_RE.search(text):
        text += f" ({len(clue['answer'])})"
    return text


def _check_fonts(rep: Report, pdf: str, tag: str) -> None:
    fonts = pdfutil.page_fonts(pdf)
    ok = bool(fonts) and all(f.embedded and f.subtype != "Type3" for f in fonts)
    rep.check(ok, f"{tag}: {len(fonts)} fonts, all embedded, none Type 3 ({', '.join(sorted(f.name for f in fonts))})")


def _check_page_size(rep: Report, pdf: str, tag: str, expect: tuple) -> None:
    n = pdfutil.page_count(pdf)
    w, h = pdfutil.page_size_in(pdf)
    ok = n == 1 and abs(w - expect[0]) < 0.01 and abs(h - expect[1]) < 0.01
    rep.check(ok, f"{tag}: {n} page, {w:.3f} x {h:.3f} in (expect {expect[0]:g} x {expect[1]:g})")


def _check_poster(rep: Report, d: str, tag: str, trim: tuple, var: str, ctx: dict) -> None:
    import numpy as np

    tw, th = trim
    _check_page_size(rep, f"{d}/poster.pdf", f"{tag}/poster.pdf", (tw + 2 * BLEED, th + 2 * BLEED))
    _check_page_size(rep, f"{d}/poster_trim.pdf", f"{tag}/poster_trim.pdf", (tw, th))
    _check_fonts(rep, f"{d}/poster.pdf", tag)
    trim_pdf = f"{d}/poster_trim.pdf"
    gfx = pdfutil.page_graphics(trim_pdf)
    fill = ctx["fill_grey"] if var == "C_grey" else ctx["fill_dark"]
    allowed_text = {BLACK, WHITE} if var == "B_spot" else {BLACK}
    rep.check(
        gfx.colors() <= {BLACK, WHITE, fill} and gfx.text_colors <= allowed_text,
        f"{tag}: only black, white and the block fill in vector content "
        f"(draw {sorted(gfx.colors())}, text {sorted(gfx.text_colors)})",
    )
    rep.check(gfx.min_stroke_width() >= 0.5, f"{tag}: thinnest stroke {gfx.min_stroke_width():.2f} pt (>= 0.5)")

    margin = ctx["margins"][tw, th]
    im = pdfutil.render_gray(trim_pdf, 50)
    m = int((margin - 0.02) * 50)
    ink = im < 250
    edge = ink[:m].any() or ink[-m:].any() or ink[:, :m].any() or ink[:, -m:].any()
    ys, xs = np.where(ink)
    box = f"ink bbox x {xs.min() / 50:.2f}-{xs.max() / 50:.2f}, y {ys.min() / 50:.2f}-{ys.max() / 50:.2f} in"
    rep.check(not edge, f"{tag}: no ink in the outer {margin:g} in margin ({box})")

    text = _squeeze(pdfutil.page_text(trim_pdf))
    want = Counter(_squeeze(f"{n} {t}") for n, t in ctx["want"])
    bad = []
    for needle, expected in want.items():
        found = len(re.findall(r"(?<!\d)" + re.escape(needle), text))
        if found != expected:
            bad.append((needle[:40], found, expected))
    rep.check(not bad, f"{tag}: all {len(ctx['want'])} clues appear exactly once (problems: {bad[:5]})")
    rep.check(
        _squeeze(ctx["title"]).upper() in text.upper() and _squeeze(ctx["byline"]) in text,
        f"{tag}: title and byline text present",
    )


def _check_key(rep: Report, d: str, size: str, ctx: dict) -> None:
    pdf = f"{d}/key.pdf"
    n = pdfutil.page_count(pdf)
    w, h = pdfutil.page_size_pt(pdf)
    rep.check(n == 1 and abs(w - 792) < 0.5 and abs(h - 1224) < 0.5, f"{size}/key.pdf is 11x17, 1 page")
    _check_fonts(rep, pdf, f"{size}/key.pdf")
    letters = sum(1 for w_ in pdfutil.page_text(pdf).split() if len(w_) == 1 and w_.isalpha())
    rep.check(
        letters >= ctx["nlet"],
        f"{size}/key.pdf has {letters} single-letter answers (grid has {ctx['nlet']} letter cells)",
    )
    _check_colours(rep, pdf, f"{size}/key.pdf", ctx)


def _check_colours(rep: Report, pdf: str, tag: str, ctx: dict) -> None:
    gfx = pdfutil.page_graphics(pdf)
    ok = gfx.colors() <= {BLACK, WHITE, ctx["fill_grey"]} and gfx.min_stroke_width() >= 0.5
    rep.check(ok, f"{tag}: colours {sorted(gfx.colors())}, thinnest stroke {gfx.min_stroke_width():.2f} pt (>= 0.5)")


def _check_solution(rep: Report, pdf: str, ctx: dict) -> None:
    n = pdfutil.page_count(pdf)
    w, h = pdfutil.page_size_pt(pdf)
    rep.check(n == 1 and sorted([round(w), round(h)]) == [612, 792], "solution_letter.pdf is letter size, 1 page")
    text = pdfutil.page_text(pdf)
    letters = sum(1 for w_ in text.split() if len(w_) == 1 and w_.isalpha())
    rep.check(letters >= ctx["nlet"], f"solution has {letters} letters")
    rep.check("THE SOLUTION" in " ".join(text.upper().split()), "solution title text present")
    _check_colours(rep, pdf, "solution_letter.pdf", ctx)


def _check_pngs(rep: Report, outroot: str, block_fill: Optional[str]) -> None:
    import numpy as np
    from PIL import Image

    for p in glob.glob(outroot + "/**/*.png", recursive=True):
        if "/.build/" in p or "/checks/" in p:
            continue
        with Image.open(p) as im:
            a = np.asarray(im.convert("RGB")).astype(int)
            width = im.size[0]
        grey = bool((a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all())
        rep.check(
            grey or bool(block_fill),
            f"{os.path.relpath(p, outroot)}: {width}px wide, every pixel R=G=B"
            + ("" if grey else " (colour fill requested)"),
        )


def verify(
    outroot: str,
    title: str = DEFAULT_TITLE,
    byline: str = DEFAULT_BYLINE,
    sizes: Optional[list] = None,
    grid: Optional[str] = None,
    block_fill: Optional[str] = None,
    grey_fill: str = "#a3a3a3",
    crops: bool = True,
    verbose: bool = True,
) -> int:
    """Run every output check under ``outroot``; print a report and return 0 when all pass, else 1."""
    grid = grid or os.path.join(outroot, "grid.json")
    if not os.path.isfile(grid):
        raise UserError(
            f"{grid} not found.", "pass the folder that contains grid.json (the 'details' folder of a build)"
        )
    with open(grid, encoding="utf-8") as fh:
        g = json.load(fh)
    if sizes is None:
        sizes = sorted(
            os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(outroot, "*x*", "fit.json"))
        )
    rep = Report(verbose)
    ctx = dict(
        nlet=sum(1 for r in g["grid"] for c in r if c),
        want=[(c["number"], clue_text(c)) for c in g["clues"]],
        title=title,
        byline=byline,
        fill_dark=hex_rgb(block_fill) if block_fill else BLACK,
        fill_grey=hex_rgb(block_fill or grey_fill),
        margins={parse_size(s): size_config(s)["margin"] for s in sizes},
    )
    rep.check(bool(sizes), f"found rendered sizes under {outroot}: {', '.join(sizes) or 'none'}")
    done_variants = set()
    for size in sizes:
        trim = parse_size(size)
        for var in VARIANTS:
            d = f"{outroot}/{size}/{var}"
            if os.path.isdir(d):
                done_variants.add(var)
                _check_poster(rep, d, f"{size}/{var}", trim, var, ctx)
        if os.path.exists(f"{outroot}/{size}/key.pdf"):
            _check_key(rep, f"{outroot}/{size}", size, ctx)
        actual = f"{outroot}/{size}/actual_size_check_letter.pdf"
        if os.path.exists(actual):
            w, h = pdfutil.page_size_pt(actual)
            rep.check(
                pdfutil.page_count(actual) == 1 and abs(w - 612) < 1 and abs(h - 792) < 1,
                f"{size}/actual_size_check_letter.pdf is letter, 1 page",
            )
    sol = f"{outroot}/solution_letter.pdf"
    if os.path.exists(sol):
        _check_solution(rep, sol, ctx)
    _check_pngs(rep, outroot, block_fill)
    for f in glob.glob(outroot + "/*/fit.json"):
        with open(f, encoding="utf-8") as fh:
            j = json.load(fh)
        for v, r in j.get("verify", {}).items():
            rep.check(
                r["ok"] and not r["problems"],
                f"{os.path.relpath(f, outroot)} DOM check {v}: overflow-free, no heading at column foot, no clue over grid, header fits; clues={r['nClues']}",
            )
    rc = 0
    if crops and sizes:
        from .crops import run_crops

        rc = run_crops(outroot, grid, sizes, sorted(done_variants, key=VARIANTS.index), verbose=verbose)
    if rep.failed:
        print(f"\n{len(rep.failed)} check(s) FAILED:", *rep.failed, sep="\n  ")
    elif verbose:
        print("\nALL CHECKS PASSED")
    else:
        print(f"All {rep.passed} output checks passed.")
    return 1 if (rep.failed or rc) else 0


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``verify``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster verify", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("outroot", help="the details folder of a build (contains grid.json and the size folders)")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--byline", "--subtitle", dest="byline", default=DEFAULT_BYLINE)
    ap.add_argument("--sizes", default=None, help="comma list (default: every size folder found)")
    ap.add_argument("--grid", default=None, help="grid.json (default OUTROOT/grid.json)")
    ap.add_argument("--block-fill", default=None, help="the --block-fill used for rendering, if any")
    ap.add_argument("--grey-fill", default="#a3a3a3")
    ap.add_argument("--no-crops", action="store_true", help="skip the per-cell stroke check / crop images (faster)")
    a = ap.parse_args(argv)
    sizes = [s.strip() for s in a.sizes.split(",") if s.strip()] if a.sizes else None
    return verify(a.outroot, a.title, a.byline, sizes, a.grid, a.block_fill, a.grey_fill, not a.no_crops)


if __name__ == "__main__":
    sys.exit(main())
