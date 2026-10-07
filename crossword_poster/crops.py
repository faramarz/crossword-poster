#!/usr/bin/env python3
"""Corner/edge crops at 150 dpi for every grid output + an automated stroke check:
every letter cell must show all four strokes (dark pixel at the centre of each of its 4 edges, sampled away from the
corners), and the frame must be continuous on all four sides. Writes OUTROOT/checks/<name>/*.png and a montage
OUTROOT/checks/<name>.png. Exit status 1 on failure.

Usage: python -m crossword_poster crops OUTROOT [--sizes 24x36,18x24] [--grid OUTROOT/grid.json]
"""
import argparse
import glob
import json
import os
import sys

DPI = 150
VARIANTS = ("A_black", "B_spot", "C_grey")


def run_crops(outroot, grid=None, sizes=None, variants=None):
    import numpy as np
    import pymupdf as fitz
    from PIL import Image

    grid = grid or os.path.join(outroot, "grid.json")
    g = json.load(open(grid, encoding="utf-8"))["grid"]
    ROWS, COLS = len(g), len(g[0])
    letters = [(r, c) for r in range(ROWS) for c in range(COLS) if g[r][c]]
    if sizes is None:
        sizes = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(outroot, "*x*", "fit.json")))
    targets = []
    for size in sizes:
        for v in (variants or VARIANTS):
            p = f"{outroot}/{size}/{v}/poster_trim.pdf"
            if os.path.exists(p):
                targets.append((f"{size}_{v}", p))
        if os.path.exists(f"{outroot}/{size}/key.pdf"):
            targets.append((f"{size}_key", f"{outroot}/{size}/key.pdf"))
    if os.path.exists(f"{outroot}/solution_letter.pdf"):
        targets.append(("solution_letter", f"{outroot}/solution_letter.pdf"))
    out = os.path.join(outroot, "checks")
    os.makedirs(out, exist_ok=True)
    fails = []
    for name, pdf in targets:
        doc = fitz.open(pdf)
        pg = doc[0]
        rects = [d for d in pg.get_drawings() if d.get("fill") not in (None, (1.0, 1.0, 1.0)) and d["rect"].width > 3 * 72 and d["rect"].height > 3 * 72]
        blk = max(rects, key=lambda d: d["rect"].width * d["rect"].height)["rect"]  # block (cell-area) rectangle, in pt
        cell = blk.width / COLS / 72  # inches
        pix = pg.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        im = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(int)
        k = DPI / 72
        X0, Y0, X1, Y1 = blk.x0 * k, blk.y0 * k, blk.x1 * k, blk.y1 * k
        cp = cell * DPI

        def dark(x, y, horiz):
            x, y = int(round(x)), int(round(y))
            if horiz:  # a horizontal edge: look across it (vertical window)
                return im[y - 1:y + 2, x].min() < 110
            return im[y, x - 1:x + 2].min() < 110

        bad, badlist = 0, []
        for (r, c) in letters:
            xl, xr = X0 + c * cp, X0 + (c + 1) * cp
            yt, yb = Y0 + r * cp, Y0 + (r + 1) * cp
            top = any(dark(xl + t * cp, yt, True) for t in (0.45, 0.6, 0.75))
            bot = any(dark(xl + t * cp, yb, True) for t in (0.3, 0.5, 0.7))
            lef = any(dark(xl, yt + t * cp, False) for t in (0.3, 0.5, 0.7))
            rig = any(dark(xr, yt + t * cp, False) for t in (0.3, 0.5, 0.7))
            if not (top and bot and lef and rig):
                bad += 1
                badlist.append((r, c, top, bot, lef, rig))
        ft = 0
        for t in np.linspace(0.02, 0.98, 60):
            for (x, y, h) in ((X0 + t * (X1 - X0), Y0 - 1.5, True), (X0 + t * (X1 - X0), Y1 + 1.5, True),
                              (X0 - 1.5, Y0 + t * (Y1 - Y0), False), (X1 + 1.5, Y0 + t * (Y1 - Y0), False)):
                if not dark(x, y, h):
                    ft += 1
        print(("PASS " if not bad and not ft else "FAIL ") + f"{name}: cell {cell:.3f} in; letter cells with a missing stroke: {bad} of {len(letters)}; frame gaps: {ft}/240", badlist[:3])
        if bad or ft:
            fails.append(name)
        win = max(4.2 * cell, 0.9) * DPI
        d = f"{out}/{name}"
        os.makedirs(d, exist_ok=True)
        pts = {"TL": (X0, Y0), "TR": (X1, Y0), "BL": (X0, Y1), "BR": (X1, Y1),
               "top_mid": ((X0 + X1) / 2, Y0), "bottom_mid": ((X0 + X1) / 2, Y1),
               "left_mid": (X0, (Y0 + Y1) / 2), "right_mid": (X1, (Y0 + Y1) / 2)}
        tiles = []
        full = pg.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        img0 = Image.frombytes("L", (full.width, full.height), full.samples)
        PAD = int(win) + 50
        img = Image.new("L", (full.width + 2 * PAD, full.height + 2 * PAD), 255)
        img.paste(img0, (PAD, PAD))
        for key, (cx, cy) in pts.items():
            box = (int(cx - win / 2) + PAD, int(cy - win / 2) + PAD, int(cx + win / 2) + PAD, int(cy + win / 2) + PAD)
            t = img.crop(box)
            t.save(f"{d}/{key}.png")
            tiles.append(t)
        S = 380
        mont = Image.new("L", (4 * S + 5 * 6, 2 * S + 3 * 6), 128)
        for i, t in enumerate(tiles):
            mont.paste(t.resize((S, S), Image.NEAREST if win < S else Image.LANCZOS), (6 + (i % 4) * (S + 6), 6 + (i // 4) * (S + 6)))
        mont.save(f"{out}/{name}.png")
    print("\nALL STROKE CHECKS PASSED" if not fails else f"\nFAILED: {fails}")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster crops", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outroot")
    ap.add_argument("--sizes", default=None)
    ap.add_argument("--grid", default=None)
    a = ap.parse_args(argv)
    return run_crops(a.outroot, a.grid, a.sizes.split(",") if a.sizes else None)


if __name__ == "__main__":
    sys.exit(main())
