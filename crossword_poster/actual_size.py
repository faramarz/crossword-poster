"""Actual-size check page (US Letter): a 1-inch bar plus two true-scale windows cut out of the finished poster.

Print it at 100% on a desktop printer to judge the real box and type sizes before ordering the big print.
The windows are located from the poster itself: the top-left corner of the largest filled grid rectangle and the
ACROSS heading (the start of the clue columns). It works with any block fill.

The page is assembled with pypdf: the poster page becomes a form XObject that is drawn, clipped, at 1:1 scale.

Usage:
  crossword-poster actual-size POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT [--title T]
  crossword-poster actual-size --from-fit out/details/24x36 [--variant A_black] [--title T]   # reads fit.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from . import pdfutil
from .errors import UserError

PT = 72.0
LETTER = (8.5 * PT, 11.0 * PT)


class _Page:
    """Tiny content-stream builder for the check page (Helvetica text, rectangles)."""

    def __init__(self) -> None:
        self.ops: list[str] = []

    @staticmethod
    def _hex(text: str) -> str:
        return text.encode("cp1252", "replace").hex()

    def text(self, x_in: float, y_in: float, size: float, text: str, bold: bool = False) -> None:
        """Draw text with its baseline at (x, y) inches from the top-left of the page."""
        font = "F2" if bold else "F1"
        self.ops.append(
            f"BT /{font} {size} Tf {x_in * PT:.2f} {LETTER[1] - y_in * PT:.2f} Td <{self._hex(text)}> Tj ET"
        )

    def rect(
        self, x_in: float, y_in: float, w_in: float, h_in: float, fill: bool = False, dashed: bool = False
    ) -> None:
        """Draw a rectangle; (x, y) is its top-left corner in inches."""
        x, y, w, h = x_in * PT, LETTER[1] - (y_in + h_in) * PT, w_in * PT, h_in * PT
        style = "0 g f" if fill else ("0.75 w [3 2] 0 d S [] 0 d" if dashed else "0.75 w S")
        self.ops.append(f"0 G {x:.2f} {y:.2f} {w:.2f} {h:.2f} re {style}")


def make_actual_size(
    poster_pdf: str,
    out_pdf: str,
    label: str,
    box_in: float,
    clue_pt: float,
    num_pt: float,
    title: str = "Crossword",
) -> dict:
    """Write the actual-size check page for ``poster_pdf`` to ``out_pdf`` and return the window positions (inches)."""
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject

    grid = pdfutil.largest_fill(pdfutil.page_graphics(poster_pdf).drawings, 5 * PT)
    if grid is None:
        raise UserError("Could not find the grid in the poster PDF.", "run the check on a poster made by this tool")
    across = pdfutil.find_text(poster_pdf, "ACROSS")
    if across is None:
        raise UserError("Could not find the ACROSS heading in the poster PDF.")
    gx, gy = grid.rect[0] / PT, grid.rect[1] / PT
    ax, ay = across[0] / PT, across[1] / PT

    writer = PdfWriter(clone_from=str(poster_pdf))
    src = writer.pages[0]
    src_h = float(src.mediabox.height)
    src_w = float(src.mediabox.width)
    form = DecodedStreamObject()
    form.set_data(src.get_contents().get_data())
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(src_w), FloatObject(src_h)]),
            NameObject("/Resources"): src["/Resources"],
        }
    )
    form_ref = writer._add_object(form.flate_encode())

    pg = _Page()
    pg.text(0.5, 0.62, 12, f"ACTUAL SIZE CHECK: {label} in poster, shown at 100% scale", bold=True)
    pg.text(
        0.5, 0.86, 9, "Print at 100% / Actual size (turn OFF 'Fit to page'). The black bar must measure exactly 1 inch."
    )
    pg.rect(0.5, 1.02, 1.0, 0.08, fill=True)
    pg.text(
        1.6,
        1.10,
        8.5,
        f"= 1 inch     boxes are {box_in:.3f} in ({box_in * 25.4:.1f} mm)     clues are {round(clue_pt, 1):g} pt"
        f"     grid numbers {round(num_pt, 1):g} pt",
    )

    pg.text(
        0.5,
        1.28,
        8,
        "The dashed windows show part of the poster and cut it off at their edges on purpose: check the sizes, not the layout.",
    )

    def window(clip_in: tuple, dest_in: tuple, caption: str) -> None:
        sx, sy, w, h = (v * PT for v in clip_in)
        dx, dy = (v * PT for v in dest_in)
        dest_bottom = LETTER[1] - dy - h
        src_bottom = src_h - sy - h
        pg.ops.append(
            f"q {dx:.2f} {dest_bottom:.2f} {w:.2f} {h:.2f} re W n 1 0 0 1 {dx - sx:.2f} {dest_bottom - src_bottom:.2f} cm /Fm0 Do Q"
        )
        pg.rect(dest_in[0], dest_in[1], clip_in[2], clip_in[3], dashed=True)
        pg.text(dest_in[0], dest_in[1] - 0.06, 8, caption)

    window((gx - 0.1, gy - 0.1, 7.5, 6.0), (0.5, 1.45), "Part of the grid (top-left corner), at real size")
    window(
        (ax - 0.1, ay - 0.12, 7.5, 2.38), (0.5, 7.95), "Part of the clue list (start of the clue columns), at real size"
    )
    pg.text(0.5, 10.85, 7.5, f"{title}: size check page (not for display)")

    page = writer.add_blank_page(LETTER[0], LETTER[1])
    content = DecodedStreamObject()
    content.set_data("\n".join(pg.ops).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)
    helv = lambda name: DictionaryObject(  # noqa: E731
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(name),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): helv("/Helvetica"), NameObject("/F2"): helv("/Helvetica-Bold")}
            ),
            NameObject("/XObject"): DictionaryObject({NameObject("/Fm0"): form_ref}),
        }
    )
    writer.remove_page(0, clean=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    with open(out_pdf, "wb") as fh:
        writer.write(fh)
    return dict(grid_x=round(gx, 2), grid_y=round(gy, 2), clues_x=round(ax, 2), clues_y=round(ay, 2))


def from_fit(size_dir: str, variant: str = "A_black", title: str = "Crossword", out: Optional[str] = None) -> tuple:
    """Build ``actual_size_check_letter.pdf`` for ``<out>/<size>/`` from its fit.json (box size, clue pt)."""
    fit_path = os.path.join(size_dir, "fit.json")
    if not os.path.isfile(fit_path):
        raise UserError(f"{fit_path} not found.", "point --from-fit at a size folder written by `render` or `build`")
    with open(fit_path, encoding="utf-8") as fh:
        fit = json.load(fh)["fit"]
    label = os.path.basename(os.path.normpath(size_dir))
    cell, fs = fit["cell"], fit["fs"]
    out = out or os.path.join(size_dir, "actual_size_check_letter.pdf")
    poster = os.path.join(size_dir, variant, "poster_trim.pdf")
    if not os.path.isfile(poster):
        raise UserError(f"{poster} not found.", "render that variant first, or choose another with --variant")
    info = make_actual_size(poster, out, label, cell, fs, round(0.27 * cell * 72, 1), title)
    return out, info


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``actual-size``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster actual-size", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("args", nargs="*", help="POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT")
    ap.add_argument(
        "--from-fit", metavar="SIZE_DIR", help="use SIZE_DIR/fit.json and SIZE_DIR/<variant>/poster_trim.pdf"
    )
    ap.add_argument("--variant", default="A_black")
    ap.add_argument("--title", default="Crossword")
    a = ap.parse_args(argv)
    if a.from_fit:
        out, info = from_fit(a.from_fit, a.variant, a.title)
        print("wrote", out, info)
        return 0
    if len(a.args) != 6:
        ap.error("expected POSTER_TRIM.pdf OUT.pdf TRIM_LABEL BOX_IN CLUE_PT NUM_PT (or --from-fit)")
    src, out, label, box, clue, num = a.args
    try:
        nums = float(box), float(clue), float(num)
    except ValueError:
        raise UserError("BOX_IN, CLUE_PT and NUM_PT must be numbers.") from None
    print("wrote", out, make_actual_size(src, out, label, *nums, title=a.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
