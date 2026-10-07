#!/usr/bin/env python3
"""Actual-size check page (US Letter, black): prints a 1-inch bar plus two true-scale windows cut out of the
finished poster, so the real box and type sizes can be judged from a desktop printer before ordering a big print.

The windows are located from the poster itself: the top-left corner of the largest filled grid rectangle and the
ACROSS heading (start of the clue columns). Works with any block fill (black or grey).

Usage:
  python -m crossword_poster actual-size POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT [--title T]
  python -m crossword_poster actual-size --from-fit out/24x36 [--variant A_black] [--title T]   # reads fit.json
"""
import argparse
import json
import os
import sys

I = 72


def make_actual_size(poster_pdf, out_pdf, label, box_in, clue_pt, num_pt, title="Crossword"):
    import pymupdf as fitz
    src = fitz.open(poster_pdf)
    sp = src[0]
    fills = [d["rect"] for d in sp.get_drawings()
             if d.get("fill") not in (None, (1.0, 1.0, 1.0)) and d["rect"].width > 5 * I and d["rect"].height > 5 * I]
    assert fills, "grid block rectangle not found in the poster PDF"
    g = max(fills, key=lambda r: r.width * r.height)
    gx, gy = g.x0 / I, g.y0 / I
    ax = ay = None
    for b in sp.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if s["text"].strip().upper() == "ACROSS":
                    ay, ax = s["bbox"][1] / I, s["bbox"][0] / I
    assert ay is not None, "ACROSS heading not found"
    K = (0, 0, 0)
    doc = fitz.open()
    pg = doc.new_page(width=8.5 * I, height=11 * I)
    pg.insert_text((0.5 * I, 0.62 * I), f"ACTUAL SIZE CHECK: {label} in poster, shown at 100% scale", fontsize=12, fontname="hebo", color=K)
    pg.insert_text((0.5 * I, 0.86 * I), "Print at 100% / Actual size (turn OFF 'Fit to page'). The black bar must measure exactly 1 inch.", fontsize=9, fontname="helv", color=K)
    y = 1.02 * I
    pg.draw_rect(fitz.Rect(0.5 * I, y, 1.5 * I, y + 0.08 * I), color=K, fill=K)
    pg.insert_text((1.6 * I, y + 0.08 * I), f"= 1 inch     boxes are {box_in:.3f} in ({box_in * 25.4:.1f} mm)     clues are {clue_pt:g} pt     grid numbers {num_pt:g} pt", fontsize=8.5, fontname="helv", color=K)

    def place(clip_in, dest_in, lab):
        x0, y0, w, h = clip_in
        dx, dy = dest_in
        clip = fitz.Rect(x0 * I, y0 * I, (x0 + w) * I, (y0 + h) * I)
        dest = fitz.Rect(dx * I, dy * I, (dx + w) * I, (dy + h) * I)
        pg.show_pdf_page(dest, src, 0, clip=clip)
        pg.draw_rect(dest, color=K, width=0.75, dashes="[3 2] 0")
        pg.insert_text((dx * I, (dy - 0.06) * I), lab, fontsize=8, fontname="helv", color=K)

    place((gx - 0.1, gy - 0.1, 7.5, 6.0), (0.5, 1.45), "Part of the grid (top-left corner), at real size")
    place((ax - 0.1, ay - 0.12, 7.5, 2.38), (0.5, 7.95), "Part of the clue list (start of the clue columns), at real size")
    pg.insert_text((0.5 * I, 10.85 * I), f"{title}: size check page (not for display)", fontsize=7.5, fontname="helv", color=K)
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    doc.save(out_pdf)
    return dict(grid_x=round(gx, 2), grid_y=round(gy, 2), clues_x=round(ax, 2), clues_y=round(ay, 2))


def from_fit(size_dir, variant="A_black", title="Crossword", out=None):
    """Build actual_size_check_letter.pdf for out/<size>/ using its fit.json (cell size, clue pt) and <variant>/poster_trim.pdf."""
    fit = json.load(open(os.path.join(size_dir, "fit.json")))["fit"]
    label = os.path.basename(os.path.normpath(size_dir))
    cell, fs = fit["cell"], fit["fs"]
    out = out or os.path.join(size_dir, "actual_size_check_letter.pdf")
    info = make_actual_size(os.path.join(size_dir, variant, "poster_trim.pdf"), out, label, cell, fs, round(0.27 * cell * 72, 1), title)
    return out, info


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster actual-size", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="*", help="POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT")
    ap.add_argument("--from-fit", metavar="SIZE_DIR", help="use SIZE_DIR/fit.json and SIZE_DIR/<variant>/poster_trim.pdf")
    ap.add_argument("--variant", default="A_black")
    ap.add_argument("--title", default="Crossword")
    a = ap.parse_args(argv)
    if a.from_fit:
        out, info = from_fit(a.from_fit, a.variant, a.title)
        print("ok", out, info)
        return 0
    if len(a.args) != 6:
        ap.error("expected POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT (or --from-fit)")
    src, out, label, box, clue, num = a.args
    info = make_actual_size(src, out, label, float(box), float(clue), float(num), a.title)
    print("ok", info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
