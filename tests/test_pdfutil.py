"""PDF helpers, tested on tiny hand-made PDFs (no browser needed)."""

import pytest

pypdf = pytest.importorskip("pypdf")

from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import DecodedStreamObject, NameObject  # noqa: E402

from crossword_poster import pdfutil  # noqa: E402


def make_pdf(path, content, width=612, height=792):
    w = PdfWriter()
    page = w.add_blank_page(width, height)
    stream = DecodedStreamObject()
    stream.set_data(content.encode("latin-1"))
    page[NameObject("/Contents")] = w._add_object(stream)
    with open(path, "wb") as fh:
        w.write(fh)
    return str(path)


def test_page_size_and_count(tmp_path):
    p = make_pdf(tmp_path / "a.pdf", "", 18 * 72, 24 * 72)
    assert pdfutil.page_count(p) == 1
    assert pdfutil.page_size_in(p) == (18.0, 24.0)
    assert pdfutil.page_size_pt(p) == (1296.0, 1728.0)


def test_graphics_reports_fills_strokes_and_widths(tmp_path):
    content = "0.5 g 72 72 144 72 re f  1 0 0 RG 2 w 10 10 50 50 re S"
    g = pdfutil.page_graphics(make_pdf(tmp_path / "a.pdf", content))
    fills = [d for d in g.drawings if d.fill is not None]
    strokes = [d for d in g.drawings if d.stroke is not None]
    assert fills[0].fill == (0.5, 0.5, 0.5)
    # origin is the TOP-left: a rect at y=72..144 from the bottom of a 792 pt page spans 648..720 from the top
    assert fills[0].rect == pytest.approx((72, 648, 216, 720))
    assert strokes[0].stroke == (1.0, 0.0, 0.0)
    assert g.min_stroke_width() == pytest.approx(2.0)


def test_graphics_follow_the_transformation_matrix(tmp_path):
    content = "q 0.5 0 0 0.5 0 0 cm 1 w 0 0 1 rg 0 G 100 100 200 200 re B Q"
    g = pdfutil.page_graphics(make_pdf(tmp_path / "a.pdf", content))
    d = g.drawings[0]
    assert d.w == pytest.approx(100) and d.h == pytest.approx(100)
    assert d.width == pytest.approx(0.5)  # a 1 unit line drawn at half scale


def test_largest_fill_ignores_white_and_small(tmp_path):
    content = "1 g 0 0 600 700 re f 0 g 100 100 300 300 re f 0 g 10 10 20 20 re f"
    g = pdfutil.page_graphics(make_pdf(tmp_path / "a.pdf", content))
    big = pdfutil.largest_fill(g.drawings, 100)
    assert big is not None and big.fill == (0.0, 0.0, 0.0) and big.w == pytest.approx(300)
    assert pdfutil.largest_fill(g.drawings, 1000) is None


def test_fonts_of_a_page_without_text(tmp_path):
    assert pdfutil.page_fonts(make_pdf(tmp_path / "a.pdf", "")) == []


def test_render_png_has_the_requested_width(tmp_path):
    from PIL import Image

    p = make_pdf(tmp_path / "a.pdf", "0 g 100 100 200 200 re f")
    out = tmp_path / "a.png"
    pdfutil.render_png(p, out, 300)
    with Image.open(out) as im:
        assert im.size[0] == 300
        assert abs(im.size[1] - 300 * 792 / 612) <= 1
        assert im.convert("L").getpixel((100, 290)) < 10  # the black square


def test_render_gray_is_a_numpy_array(tmp_path):
    p = make_pdf(tmp_path / "a.pdf", "")
    arr = pdfutil.render_gray(p, 36)
    assert arr.shape == (396, 306)
    assert arr.min() == 255
