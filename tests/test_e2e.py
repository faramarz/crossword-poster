"""End-to-end tests: real Chromium, real PDFs. Skipped automatically when Chromium cannot start."""

import csv
import json
import re

import pytest

from crossword_poster import cli, pdfutil
from tests.conftest import SMALL_ROWS, write_csv

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def sample_run(tmp_path_factory, request):
    """Build the bundled sample at 18x24 once for the whole module."""
    out = tmp_path_factory.mktemp("sample")
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["sample", "--out", str(out), "--size", "18x24"])
    return out, code, buf.getvalue()


def test_sample_builds_and_every_check_passes(sample_run):
    _, code, _ = sample_run
    assert code == 0


def test_sample_pdf_page_sizes(sample_run):
    out, _, _ = sample_run
    w, h = pdfutil.page_size_in(out / "poster_18x24_grey_bleed.pdf")
    assert (round(w, 3), round(h, 3)) == (18.25, 24.25)
    w, h = pdfutil.page_size_in(out / "poster_18x24_grey_trim.pdf")
    assert (round(w, 3), round(h, 3)) == (18.0, 24.0)
    assert pdfutil.page_size_in(out / "answer_key_18x24_11x17.pdf") == (11.0, 17.0)
    assert pdfutil.page_size_in(out / "actual_size_check_18x24.pdf") == (8.5, 11.0)
    w, h = pdfutil.page_size_in(out / "answer_sheet_letter.pdf")
    assert sorted((round(w, 2), round(h, 2))) == [8.5, 11.0]
    for pdf in out.glob("*.pdf"):
        assert pdfutil.page_count(pdf) == 1


def test_sample_png_preview_and_answer_sheet_exist(sample_run):
    from PIL import Image

    out, _, _ = sample_run
    png = out / "poster_18x24_grey_preview.png"
    assert png.stat().st_size > 10_000
    with Image.open(png) as im:
        assert im.size[0] == 1200
    assert (out / "answer_sheet_letter.pdf").stat().st_size > 1_000
    assert (out / "answer_sheet_letter.png").exists()


def test_sample_answer_sheet_shows_the_solution(sample_run):
    out, _, _ = sample_run
    text = pdfutil.page_text(out / "answer_sheet_letter.pdf")
    assert "THE SOLUTION" in " ".join(text.upper().split())
    grid = json.loads((out / "details" / "grid.json").read_text(encoding="utf-8"))
    letters = sum(1 for row in grid["grid"] for ch in row if ch)
    assert sum(1 for t in text.split() if len(t) == 1 and t.isalpha()) >= letters


def test_sample_poster_contains_every_clue_once(sample_run):
    out, _, _ = sample_run
    text = re.sub(r"\s+", "", pdfutil.page_text(out / "poster_18x24_grey_trim.pdf"))
    with open(out / "clues_and_answers.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 54
    for row in rows:
        needle = re.sub(r"\s+", "", f"{row['number']} {row['clue']}")
        assert len(re.findall(r"(?<!\d)" + re.escape(needle), text)) >= 1, row["clue"]


def test_sample_summary_reports_sizes_and_words(sample_run):
    _, _, text = sample_run
    assert "each square is" in text and " mm)" in text
    assert "clue text is" in text and " pt" in text
    assert "Every answer was placed." in text
    assert "answer_sheet_letter.pdf" in text


def test_sample_check_page_is_true_scale(sample_run):
    out, _, _ = sample_run
    gfx = pdfutil.page_graphics(out / "actual_size_check_18x24.pdf")
    bar = [d for d in gfx.drawings if d.fill is not None and d.h < 8 and d.w > 60]
    assert bar, "the 1 inch bar is missing"
    assert bar[0].w == pytest.approx(72.0, abs=0.5)


def test_same_seed_gives_identical_grids(tmp_path, small_csv):
    grids = []
    for name in ("a", "b"):
        out = tmp_path / name
        code = cli.main(
            [
                "build",
                "--clues",
                str(small_csv),
                "--size",
                "18x24",
                "--out",
                str(out),
                "--seed",
                "4",
                "--no-crops",
                "--attempts",
                "100",
            ]
        )
        assert code == 0
        grids.append((out / "details" / "grid.json").read_text(encoding="utf-8"))
    assert grids[0] == grids[1]


def test_markup_in_clues_is_printed_literally(tmp_path):
    rows = list(SMALL_ROWS)
    rows[0] = ("<script>alert(1)</script> & <b>bold</b>", "Planet")
    rows[1] = ("Crème brûlée & café", "River")
    path = write_csv(tmp_path / "x.csv", rows)
    out = tmp_path / "out"
    code = cli.main(["build", "--clues", str(path), "--size", "18x24", "--out", str(out), "--no-crops", "--attempts", "100",
                     "--title", "<i>Tom</i> & Jerry", "--subtitle", "a < b"])  # fmt: skip
    assert code == 0
    text = re.sub(r"\s+", "", pdfutil.page_text(out / "poster_18x24_grey_trim.pdf"))
    assert "<script>alert(1)</script>&<b>bold</b>" in text
    assert "Crèmebrûlée&café" in text
    assert "<I>TOM</I>&JERRY" in text.upper()


def test_unplaceable_word_is_left_out_with_an_explanation(tmp_path, capsys):
    rows = [*SMALL_ROWS, ("Odd one out", "Zzyzx")]
    path = write_csv(tmp_path / "x.csv", rows)
    out = tmp_path / "out"
    code = cli.main(
        ["build", "--clues", str(path), "--size", "18x24", "--out", str(out), "--no-crops", "--attempts", "100"]
    )
    text = capsys.readouterr().out
    assert code == 0  # not an error unless --require-all is given
    assert "could not be placed" in text and "Zzyzx" in text
    assert "1 answer(s) were left out" in text
    assert (out / "poster_18x24_grey_bleed.pdf").exists()
    grid = json.loads((out / "details" / "grid.json").read_text(encoding="utf-8"))
    assert "ZZYZX" not in {p["word"] for p in grid["placements"]}


def test_all_styles_and_two_sizes_in_one_build(tmp_path):
    out = tmp_path / "out"
    path = write_csv(tmp_path / "x.csv", SMALL_ROWS)
    code = cli.main(
        [
            "build",
            "--clues",
            str(path),
            "--size",
            "18x24,24x36",
            "--style",
            "all",
            "--out",
            str(out),
            "--no-crops",
            "--attempts",
            "100",
        ]
    )
    assert code == 0
    for size in ("18x24", "24x36"):
        for style in ("black", "grey", "icons"):
            assert (out / f"poster_{size}_{style}_bleed.pdf").exists()
        assert (out / f"answer_key_{size}_11x17.pdf").exists()
        assert (out / f"actual_size_check_{size}.pdf").exists()


def test_a_second_build_cleans_up_stale_working_files(tmp_path):
    out = tmp_path / "out"
    path = write_csv(tmp_path / "x.csv", SMALL_ROWS)
    args = ["build", "--clues", str(path), "--size", "18x24", "--out", str(out), "--no-crops", "--attempts", "100"]
    assert cli.main([*args, "--style", "black"]) == 0
    assert cli.main([*args, "--style", "grey"]) == 0
    assert not list((out / "details" / "18x24").glob("A_black"))


def test_doctor_passes_on_a_working_machine(capsys):
    assert cli.main(["doctor"]) == 0
    assert "Everything is ready" in capsys.readouterr().out


def test_verify_notices_a_wrong_title(sample_run, capsys):
    out, _, _ = sample_run
    good = [
        "verify",
        str(out / "details"),
        "--title",
        "Alex's 50th Birthday Crossword",
        "--subtitle",
        "Clues from the people who love you",
        "--no-crops",
    ]
    assert cli.main(good) == 0
    bad = ["verify", str(out / "details"), "--title", "Some other title", "--no-crops"]
    assert cli.main(bad) == 1
    assert "title and byline text present" in capsys.readouterr().out
