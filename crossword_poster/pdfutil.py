"""Small PDF toolbox built on pypdf (structure, graphics, fonts) and pypdfium2 (text and rasterising).

Both libraries are permissively licensed (BSD / Apache-2.0). Coordinates returned by this module use points
(1/72 in) with the origin at the TOP-LEFT of the page, like screen coordinates.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Optional

Color = tuple  # (r, g, b) floats 0..1, rounded to 3 places
Rect = tuple  # (x0, y0, x1, y1) in points, top-left origin


# ---------------------------------------------------------------- basics
def _reader(pdf):
    from pypdf import PdfReader

    return PdfReader(str(pdf))


def page_count(pdf) -> int:
    """Number of pages in a PDF."""
    return len(_reader(pdf).pages)


def page_size_pt(pdf, index: int = 0) -> tuple[float, float]:
    """(width, height) of a page in points."""
    box = _reader(pdf).pages[index].mediabox
    return float(box.width), float(box.height)


def page_size_in(pdf, index: int = 0) -> tuple[float, float]:
    """(width, height) of a page in inches."""
    w, h = page_size_pt(pdf, index)
    return w / 72.0, h / 72.0


def page_text(pdf, index: int = 0) -> str:
    """All text on a page, in reading order (pypdfium2)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        return doc[index].get_textpage().get_text_range()
    finally:
        doc.close()


def find_text(pdf, needle: str, index: int = 0) -> Optional[Rect]:
    """Bounding box of the first occurrence of ``needle`` on a page, or None."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        page = doc[index]
        height = page.get_size()[1]
        tp = page.get_textpage()
        hit = tp.search(needle).get_next()
        if not hit:
            return None
        start, count = hit
        boxes = [tp.get_charbox(i, loose=True) for i in range(start, start + count)]
        x0 = min(b[0] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y_bottom = min(b[1] for b in boxes)
        y_top = max(b[3] for b in boxes)
        return (x0, height - y_top, x1, height - y_bottom)
    finally:
        doc.close()


def render_png(pdf, png, width_px: int = 1200) -> None:
    """Rasterise page 1 of a PDF to a PNG ``width_px`` wide."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        page = doc[0]
        scale = width_px / page.get_size()[0]
        page.render(scale=scale).to_pil().convert("RGB").save(str(png))
    finally:
        doc.close()


def render_gray(pdf, dpi: float):
    """Page 1 as a 2-D uint8 numpy array (0 = black, 255 = white) at ``dpi``."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        return doc[0].render(scale=dpi / 72.0, grayscale=True).to_numpy().copy()
    finally:
        doc.close()


# ----------------------------------------------------------------- fonts
@dataclass
class FontInfo:
    """One font used by a page."""

    name: str
    subtype: str
    embedded: bool


def page_fonts(pdf, index: int = 0) -> list[FontInfo]:
    """Fonts used by a page (including those inside form XObjects), with their embedding status."""
    page = _reader(pdf).pages[index]
    found: dict[str, FontInfo] = {}
    _collect_fonts(page.get("/Resources"), found, set())
    return list(found.values())


def _collect_fonts(resources, found, seen) -> None:
    resources = _deref(resources)
    if not resources or id(resources) in seen:
        return
    seen.add(id(resources))
    for font in (_deref(resources.get("/Font")) or {}).values():
        font = _deref(font)
        subtype = str(font.get("/Subtype", ""))
        name = str(font.get("/BaseFont", "?")).lstrip("/")
        desc = _deref(font.get("/FontDescriptor"))
        if subtype == "/Type0":
            descendants = _deref(font.get("/DescendantFonts")) or []
            child = _deref(descendants[0]) if descendants else {}
            desc = _deref(child.get("/FontDescriptor"))
        embedded = bool(desc) and any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        found.setdefault(name, FontInfo(name.split("+")[-1], subtype.lstrip("/"), embedded))
    for xobj in (_deref(resources.get("/XObject")) or {}).values():
        xobj = _deref(xobj)
        if xobj.get("/Subtype") == "/Form":
            _collect_fonts(xobj.get("/Resources"), found, seen)


def _deref(obj):
    return obj.get_object() if hasattr(obj, "get_object") else obj


# -------------------------------------------------------------- graphics
@dataclass
class Drawing:
    """A painted path: bounding box, fill and stroke colours and stroke width (all in page points)."""

    rect: Rect
    fill: Optional[Color]
    stroke: Optional[Color]
    width: float

    @property
    def w(self) -> float:
        return self.rect[2] - self.rect[0]

    @property
    def h(self) -> float:
        return self.rect[3] - self.rect[1]


@dataclass
class Graphics:
    """Everything a page paints: vector drawings and the colours used for text."""

    drawings: list = field(default_factory=list)
    text_colors: set = field(default_factory=set)

    def colors(self) -> set:
        """Every fill and stroke colour used by vector drawings."""
        out = set()
        for d in self.drawings:
            out.update(c for c in (d.fill, d.stroke) if c is not None)
        return out

    def min_stroke_width(self) -> float:
        """Thinnest stroked line in points (99 when nothing is stroked)."""
        widths = [d.width for d in self.drawings if d.stroke is not None and d.width]
        return min(widths) if widths else 99.0


_MATRIX_ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_WHITE = (1.0, 1.0, 1.0)


def _mul(m, n):
    """Matrix product m x n for PDF row-vector matrices [a b c d e f]."""
    return (
        m[0] * n[0] + m[1] * n[2],
        m[0] * n[1] + m[1] * n[3],
        m[2] * n[0] + m[3] * n[2],
        m[2] * n[1] + m[3] * n[3],
        m[4] * n[0] + m[5] * n[2] + n[4],
        m[4] * n[1] + m[5] * n[3] + n[5],
    )


def _color(operands) -> Color:
    vals = [float(x) for x in operands]
    if len(vals) == 1:
        vals = vals * 3
    elif len(vals) == 4:
        c, m, y, k = vals
        vals = [(1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)]
    return tuple(round(v, 3) for v in vals[:3])


def page_graphics(pdf, index: int = 0) -> Graphics:
    """Interpret a page's content stream and report painted rectangles/paths and text colours.

    This understands the operators Chromium and Skia emit (q/Q, cm, re, m/l/c/h, f/S/B, rg/g/k and friends, Do for
    form XObjects). It is deliberately small; it is not a general PDF renderer.
    """
    reader = _reader(pdf)
    page = reader.pages[index]
    out = Graphics()
    top = float(page.mediabox.top)
    left = float(page.mediabox.left)
    base = (1.0, 0.0, 0.0, -1.0, -left, top)  # flips y so the origin is top-left
    _interpret(reader, page.get_contents(), page.get("/Resources"), _mul(_MATRIX_ID, base), out, 0)
    return out


def _interpret(reader, contents, resources, ctm0, out: Graphics, depth: int) -> None:
    from pypdf.generic import ContentStream

    if contents is None or depth > 6:
        return
    ops = ContentStream(contents, reader).operations
    ctm = ctm0
    fill: Color = (0.0, 0.0, 0.0)
    stroke: Color = (0.0, 0.0, 0.0)
    lw = 1.0
    stack = []
    path: list = []
    for operands, op in ops:
        op = op.decode("latin-1") if isinstance(op, bytes) else str(op)
        if op == "q":
            stack.append((ctm, fill, stroke, lw))
        elif op == "Q":
            if stack:
                ctm, fill, stroke, lw = stack.pop()
        elif op == "cm":
            ctm = _mul(tuple(float(x) for x in operands), ctm)
        elif op == "w":
            lw = float(operands[0])
        elif op == "gs" and resources is not None:
            state = _deref((_deref(resources.get("/ExtGState")) or {}).get(operands[0])) or {}
            if "/LW" in state:
                lw = float(state["/LW"])
        elif op in ("g", "rg", "k"):
            fill = _color(operands)
        elif op in ("G", "RG", "K"):
            stroke = _color(operands)
        elif op in ("sc", "scn") and all(_is_number(x) for x in operands) and operands:
            fill = _color(operands)
        elif op in ("SC", "SCN") and all(_is_number(x) for x in operands) and operands:
            stroke = _color(operands)
        elif op == "re":
            x, y, w, h = (float(v) for v in operands)
            path += [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        elif op in ("m", "l"):
            path.append((float(operands[0]), float(operands[1])))
        elif op == "c":
            path += [(float(operands[i]), float(operands[i + 1])) for i in (0, 2, 4)]
        elif op in ("v", "y"):
            path += [(float(operands[i]), float(operands[i + 1])) for i in (0, 2)]
        elif op in ("f", "F", "f*", "S", "s", "B", "B*", "b", "b*"):
            if path:
                do_fill = op in ("f", "F", "f*", "B", "B*", "b", "b*")
                do_stroke = op in ("S", "s", "B", "B*", "b", "b*")
                pts = [(ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5]) for x, y in path]
                scale = math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                out.drawings.append(
                    Drawing(
                        (min(xs), min(ys), max(xs), max(ys)),
                        fill if do_fill else None,
                        stroke if do_stroke else None,
                        lw * scale if do_stroke else 0.0,
                    )
                )
            path = []
        elif op == "n":
            path = []
        elif op in ("Tj", "TJ", "'", '"'):
            out.text_colors.add(fill)
        elif op == "Do" and resources is not None:
            xobjs = _deref(resources.get("/XObject")) or {}
            xo = _deref(xobjs.get(operands[0]))
            if xo is not None and xo.get("/Subtype") == "/Form":
                matrix = tuple(float(v) for v in xo.get("/Matrix", _MATRIX_ID))
                _interpret(reader, xo, xo.get("/Resources", resources), _mul(matrix, ctm), out, depth + 1)


def _is_number(x) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def largest_fill(drawings: Iterable[Drawing], min_size_pt: float, ignore_white: bool = True) -> Optional[Drawing]:
    """The biggest filled drawing wider and taller than ``min_size_pt`` (white fills ignored by default)."""
    cands = [
        d
        for d in drawings
        if d.fill is not None and not (ignore_white and d.fill == _WHITE) and d.w > min_size_pt and d.h > min_size_pt
    ]
    return max(cands, key=lambda d: d.w * d.h) if cands else None
