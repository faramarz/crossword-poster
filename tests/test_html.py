"""Clue text ends up inside generated HTML and JavaScript; it must always be treated as plain text."""

import json
import re

from crossword_poster import generate as gen
from crossword_poster import render_news as rn

NASTY = [
    "<script>alert(1)</script> hello",
    "Fish & chips <b>bold</b> &amp; \"quoted\" 'single'",
    "</script><img src=x onerror=alert(2)>",
    "<!-- comment --> tail",
    "Backslash \\ and ${template} and `ticks`",
]


def make_grid(clues):
    words = ["PLANET", "RIVER", "TIGER", "STONE", "OCEAN"]
    rows = [{"grid": w, "clue": c, "display": w.title(), "id": str(i)} for i, (w, c) in enumerate(zip(words, clues), 1)]
    sol = gen.solve(words, attempts=30, workers=1)
    res = gen.attach_pool(gen.to_result(sol.board, [], sol.stats), rows)
    return rn.analyse(res)


def page_for(clues, title="T", byline="B"):
    an = make_grid(clues)
    tcfg = rn.size_config("18x24")
    data = rn.build_data(an, tcfg, 17.0, 23.0, title=title, byline=byline)
    return rn.build_poster_html(data, (18.0, 24.0), 0.125, tcfg)


def embedded_data(html):
    match = re.search(r"const D=(.*?);\nconst IN=", html, re.S)
    assert match, "data block not found"
    return json.loads(match.group(1).replace("<\\/", "</").replace("<\\!--", "<!--"))


def test_script_terminators_cannot_escape_the_data_block():
    html = page_for(NASTY)
    start = html.index("const D=")
    end = html.index("const IN=")
    block = html[start:end]
    assert "</script" not in block.lower()
    assert "<!--" not in block


def test_clue_text_survives_the_round_trip_unchanged():
    html = page_for(NASTY)
    texts = {e["text"] for e in embedded_data(html)["entries"]}
    for clue in NASTY:
        assert any(t.startswith(clue) for t in texts), clue


def test_title_and_byline_are_escaped_too():
    html = page_for(NASTY, title="</script><b>T</b>", byline="a & <i>b</i>")
    data = embedded_data(html)
    assert data["title"] == "</script><b>T</b>"
    assert data["byline"] == "a & <i>b</i>"
    assert html.lower().count("</script>") == 1  # only the real end of the page script


def test_javascript_escapes_markup_before_using_innerhtml():
    # the page inserts clue text with innerHTML through esc(); make sure it neutralises &, < and >
    assert "const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')" in rn.PAGE
    assert "textContent=D.title" in rn.PAGE.replace(" ", "")


def test_embedded_fonts_carry_their_copyright_and_licence_notice():
    html = page_for(["a", "b", "c", "d", "e"])
    head = html[: html.index("@font-face")]
    assert "Archivo Narrow Project Authors" in head
    assert "Oswald Project Authors" in head
    assert "SIL Open Font License 1.1" in head
    assert html.count("base64,") >= 4


def test_colour_options_are_validated():
    import pytest

    from crossword_poster.errors import UserError

    for good in (None, "", "#c8d6e5", "#fff", "lightgrey", "Black"):
        assert rn.RenderOptions(block_fill=good).fill_dark
    for bad in ('red"/><script>', "url(http://x)", "#12", "rgb(1,2,3)", "a b", "#ggg"):
        with pytest.raises(UserError) as exc:
            rn.RenderOptions(block_fill=bad)
        assert "--block-fill" in exc.value.message
    with pytest.raises(UserError, match="--grey-fill"):
        rn.RenderOptions(grey_fill="x;y")


def test_every_generated_label_goes_through_esc():
    for needle in ("esc(it.label)", "esc(it.e.number)", "esc(c.n)", "esc(c.l)", "esc(D.blockFill"):
        assert needle in rn.PAGE or needle in rn.SOLUTION_PAGE, needle
    assert "const esc=" in rn.SOLUTION_PAGE
    assert "${c.n}" not in rn.PAGE + rn.SOLUTION_PAGE and "${c.l}" not in rn.PAGE + rn.SOLUTION_PAGE


def test_the_renderer_rejects_a_tampered_grid_file(small_grid, tmp_path):
    import copy
    import json

    import pytest

    from crossword_poster.errors import UserError

    _, res = small_grid
    bad = copy.deepcopy(res)
    r, c = next((r, c) for r, row in enumerate(bad["grid"]) for c, ch in enumerate(row) if ch)
    bad["grid"][r][c] = "<img src=x onerror=alert(1)>"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(UserError) as exc:
        rn.load_grid(str(path))
    assert "single letter" in exc.value.message
    # a grid whose clues disagree with the letters is an error message, not an AssertionError dump
    worse = copy.deepcopy(res)
    worse["clues"][0]["answer"] = "QQQQ"
    path.write_text(json.dumps(worse), encoding="utf-8")
    with pytest.raises(UserError, match="the grid spells"):
        rn.load_grid(str(path))


def test_size_warnings_for_tiny_text_tiny_squares_and_a_blank_foot():
    from crossword_poster.render_news import size_warnings

    fine = dict(fs=12.0, cell=0.5, blankFrac=0.02)
    assert size_warnings("24x36", fine) == []
    assert size_warnings("24x36", dict(fine, fs=9.0, cell=0.3, blankFrac=0.0799)) == []  # exactly at the limits is fine
    small_text = size_warnings("18x24", dict(fine, fs=8.4))
    assert len(small_text) == 1 and "8.4 pt" in small_text[0] and "below 9 pt" in small_text[0]
    assert "bigger --size" in small_text[0]
    small_squares = size_warnings("18x24", dict(fine, cell=0.28))
    assert len(small_squares) == 1 and "0.28 in" in small_squares[0] and "below 0.3 in" in small_squares[0]
    blank = size_warnings("24x36", dict(fine, blankFrac=0.14))
    assert len(blank) == 1 and "14%" in blank[0] and "smaller --size" in blank[0]
    assert len(size_warnings("18x24", dict(fs=8, cell=0.2, blankFrac=0.5))) == 3


def test_the_no_fit_hint_only_suggests_a_bigger_size_when_there_is_one():
    from crossword_poster.render_news import no_fit_error

    for trim in ("18x24", "24x36"):
        assert "bigger --size" in no_fit_error(trim).hint
    big = no_fit_error("36x48")
    assert "bigger --size" not in big.hint and "fewer or shorter clues" in big.hint
    assert "36x48 poster" in big.message
