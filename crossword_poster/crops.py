"""Corner/edge crops at 150 dpi for every grid output, plus an automated stroke check.

Every letter cell must show all four strokes (a dark pixel at the centre of each of its 4 edges, sampled away from
the corners) and the frame must be continuous on all four sides. Writes OUTROOT/checks/<name>/*.png and a montage
OUTROOT/checks/<name>.png. The exit status is 1 on failure.

Usage: crossword-poster crops OUTROOT [--sizes 24x36,18x24] [--grid OUTROOT/grid.json]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Optional

from . import pdfutil

DPI = 150
VARIANTS = ("A_black", "B_spot", "C_grey")


def _targets(outroot: str, sizes: list, variants) -> list:
    targets = []
    for size in sizes:
        for v in variants or VARIANTS:
            p = f"{outroot}/{size}/{v}/poster_trim.pdf"
            if os.path.exists(p):
                targets.append((f"{size}_{v}", p))
        if os.path.exists(f"{outroot}/{size}/key.pdf"):
            targets.append((f"{size}_key", f"{outroot}/{size}/key.pdf"))
    if os.path.exists(f"{outroot}/solution_letter.pdf"):
        targets.append(("solution_letter", f"{outroot}/solution_letter.pdf"))
    return targets


def run_crops(
    outroot: str,
    grid: Optional[str] = None,
    sizes: Optional[list] = None,
    variants=None,
    verbose: bool = True,
) -> int:
    """Check every letter cell's four strokes and the frame in each output PDF; write crop images. Returns 0/1."""
    grid = grid or os.path.join(outroot, "grid.json")
    with open(grid, encoding="utf-8") as fh:
        g = json.load(fh)["grid"]
    rows, cols = len(g), len(g[0])
    letters = [(r, c) for r in range(rows) for c in range(cols) if g[r][c]]
    if sizes is None:
        sizes = sorted(
            os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(outroot, "*x*", "fit.json"))
        )
    out = os.path.join(outroot, "checks")
    os.makedirs(out, exist_ok=True)
    fails = []
    for name, pdf in _targets(outroot, sizes, variants):
        block = pdfutil.largest_fill(pdfutil.page_graphics(pdf).drawings, 3 * 72)
        if block is None:
            fails.append(name)
            print(f"FAIL {name}: grid block rectangle not found")
            continue
        x0p, y0p, x1p, y1p = block.rect
        cell = block.w / cols / 72  # inches
        im = pdfutil.render_gray(pdf, DPI)
        px = im.load()
        k = DPI / 72
        X0, Y0, X1, Y1 = x0p * k, y0p * k, x1p * k, y1p * k
        cp = cell * DPI

        def dark(x, y, horizontal, px=px, size=im.size):
            x, y = int(round(x)), int(round(y))
            if not (1 <= x < size[0] - 1 and 1 <= y < size[1] - 1):
                return False
            if horizontal:  # a horizontal edge: look across it (vertical window)
                return min(px[x, y - 1], px[x, y], px[x, y + 1]) < 110
            return min(px[x - 1, y], px[x, y], px[x + 1, y]) < 110

        bad, badlist = 0, []
        for r, c in letters:
            xl, xr = X0 + c * cp, X0 + (c + 1) * cp
            yt, yb = Y0 + r * cp, Y0 + (r + 1) * cp
            top = any(dark(xl + t * cp, yt, True) for t in (0.45, 0.6, 0.75))
            bot = any(dark(xl + t * cp, yb, True) for t in (0.3, 0.5, 0.7))
            lef = any(dark(xl, yt + t * cp, False) for t in (0.3, 0.5, 0.7))
            rig = any(dark(xr, yt + t * cp, False) for t in (0.3, 0.5, 0.7))
            if not (top and bot and lef and rig):
                bad += 1
                badlist.append((r, c, top, bot, lef, rig))
        frame_gaps = 0
        for t in (0.02 + 0.96 * i / 59 for i in range(60)):
            for x, y, horizontal in (
                (X0 + t * (X1 - X0), Y0 - 1.5, True),
                (X0 + t * (X1 - X0), Y1 + 1.5, True),
                (X0 - 1.5, Y0 + t * (Y1 - Y0), False),
                (X1 + 1.5, Y0 + t * (Y1 - Y0), False),
            ):
                if not dark(x, y, horizontal):
                    frame_gaps += 1
        ok = not bad and not frame_gaps
        if verbose or not ok:
            print(
                ("PASS " if ok else "FAIL ")
                + f"{name}: cell {cell:.3f} in; letter cells with a missing stroke: {bad} of {len(letters)}; "
                f"frame gaps: {frame_gaps}/240",
                badlist[:3] if badlist else "",
            )
        if not ok:
            fails.append(name)
        _write_crops(out, name, im, (X0, Y0, X1, Y1), cell)
    if fails:
        print(f"\nStroke check FAILED for: {', '.join(fails)}")
    elif verbose:
        print("\nALL STROKE CHECKS PASSED")
    return 1 if fails else 0


def _write_crops(out: str, name: str, im, box: tuple, cell: float) -> None:
    """Write eight corner/edge crops of the grid and a montage of them."""
    from PIL import Image

    X0, Y0, X1, Y1 = box
    win = max(4.2 * cell, 0.9) * DPI
    folder = f"{out}/{name}"
    os.makedirs(folder, exist_ok=True)
    pts = {
        "TL": (X0, Y0),
        "TR": (X1, Y0),
        "BL": (X0, Y1),
        "BR": (X1, Y1),
        "top_mid": ((X0 + X1) / 2, Y0),
        "bottom_mid": ((X0 + X1) / 2, Y1),
        "left_mid": (X0, (Y0 + Y1) / 2),
        "right_mid": (X1, (Y0 + Y1) / 2),
    }
    pad = int(win) + 50
    img = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 255)
    img.paste(im, (pad, pad))
    tiles = []
    for key, (cx, cy) in pts.items():
        tile = img.crop(
            (int(cx - win / 2) + pad, int(cy - win / 2) + pad, int(cx + win / 2) + pad, int(cy + win / 2) + pad)
        )
        tile.save(f"{folder}/{key}.png")
        tiles.append(tile)
    s = 380
    montage = Image.new("L", (4 * s + 5 * 6, 2 * s + 3 * 6), 128)
    for i, tile in enumerate(tiles):
        resample = Image.NEAREST if win < s else Image.LANCZOS
        montage.paste(tile.resize((s, s), resample), (6 + (i % 4) * (s + 6), 6 + (i // 4) * (s + 6)))
    montage.save(f"{out}/{name}.png")


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``crops``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster crops", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("outroot")
    ap.add_argument("--sizes", default=None)
    ap.add_argument("--grid", default=None)
    a = ap.parse_args(argv)
    sizes = [s.strip() for s in a.sizes.split(",") if s.strip()] if a.sizes else None
    return run_crops(a.outroot, a.grid, sizes)


if __name__ == "__main__":
    sys.exit(main())
