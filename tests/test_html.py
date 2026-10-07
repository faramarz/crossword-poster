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
