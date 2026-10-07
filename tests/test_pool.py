"""Reading clue files: column detection, row problems, normalisation, duplicates, enumerations."""

import pytest

from crossword_poster import pool
from crossword_poster.errors import UserError
from tests.conftest import SAMPLE_BIRTHDAY, SAMPLE_TRIVIA, write_csv


def build(path, **kw):
    return pool.build_pool(str(path), **kw)


def warnings_of(rep):
    """Report warnings, ignoring the 'only N clues' note that tiny test files always trigger."""
    return [w for w in rep["warnings"] if "sparse" not in w]


# ------------------------------------------------------------- columns
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (("clue", "answer"), (0, 1)),
        (("Clue", "Answer"), (0, 1)),
        (("CLUES", "ANSWERS"), (0, 1)),
        (("Question", "Word"), (0, 1)),
        (("  clue ", " answer "), (0, 1)),
        (("answer", "clue"), (1, 0)),
    ],
)
def test_column_detection_is_case_insensitive(tmp_path, header, expected):
    rows = [("Capital of France", "Paris"), ("Largest planet", "Jupiter")]
    if header[0].strip().lower() in pool.ANSWER_NAMES:
        rows = [(a, c) for c, a in rows]
    path = write_csv(tmp_path / "x.csv", rows, header=header)
    got, rep = build(path)
    assert [r["grid"] for r in got] == ["PARIS", "JUPITER"]
    assert rep["columns"] == {"clue": header[expected[0]].strip(), "answer": header[expected[1]].strip()}


def test_explicit_columns_override_detection(tmp_path):
    path = write_csv(
        tmp_path / "x.csv", [("a", "Paris", "Capital"), ("b", "Rome", "Eternal city")], header=("code", "Town", "Hint")
    )
    rows, _ = build(path, clue_col="hint", answer_col="TOWN")
    assert [r["grid"] for r in rows] == ["PARIS", "ROME"]
    assert rows[1]["clue"] == "Eternal city"


def test_missing_columns_error_lists_what_was_found(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("a", "b")], header=("foo", "bar"))
    with pytest.raises(UserError) as exc:
        build(path)
    assert "clue column" in exc.value.message
    assert "'foo'" in exc.value.message
    assert "template" in exc.value.hint


def test_explicit_column_not_found(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Capital", "Paris")])
    with pytest.raises(UserError, match="no column called 'Hints'"):
        build(path, clue_col="Hints")


def test_optional_id_and_enumeration_columns(tmp_path):
    path = write_csv(
        tmp_path / "x.csv",
        [("A1", "Where Big Ben stands", "Big Ben", "3,3"), ("A2", "Capital of France", "Paris", "")],
        header=("ID", "Clue", "Answer", "Enumeration"),
    )
    rows, _ = build(path)
    assert [r["id"] for r in rows] == ["A1", "A2"]
    assert rows[0]["clue"] == "Where Big Ben stands (3,3)"


# ------------------------------------------------------------ encodings
def test_utf8_with_and_without_bom(tmp_path):
    for enc in ("utf-8", "utf-8-sig"):
        path = write_csv(tmp_path / f"{enc}.csv", [("Café in Paris", "Café"), ("Capital", "Paris")], encoding=enc)
        rows, rep = build(path)
        assert rows[0]["grid"] == "CAFE"
        assert rows[0]["display"] == "Café"
        assert rep["columns"]["clue"] == "clue"  # a BOM must not end up in the header name


def test_windows_1252_fallback_is_reported(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Café in Paris", "Café"), ("Capital", "Paris")], encoding="cp1252")
    rows, rep = build(path)
    assert rows[0]["display"] == "Café"
    assert any("Windows-1252" in n for n in rep["notes"])


def test_semicolon_and_tab_delimiters(tmp_path):
    for delim in (";", "\t"):
        path = write_csv(tmp_path / "x.csv", [("Capital", "Paris"), ("Eternal city", "Rome")], delimiter=delim)
        rows, _ = build(path)
        assert [r["grid"] for r in rows] == ["PARIS", "ROME"]


def test_xlsx_is_read(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Clue", "Answer"])
    ws.append(["Capital of France", "Paris"])
    ws.append([None, None])
    ws.append(["Eternal city", "Rome"])
    path = tmp_path / "x.xlsx"
    wb.save(path)
    rows, rep = build(path)
    assert [r["grid"] for r in rows] == ["PARIS", "ROME"]
    assert rep["blank_rows"] == 1


# -------------------------------------------------------------- file errors
def test_missing_file(tmp_path):
    with pytest.raises(UserError, match="File not found"):
        build(tmp_path / "nope.csv")


def test_folder_instead_of_file(tmp_path):
    with pytest.raises(UserError, match="folder"):
        build(tmp_path)


def test_empty_file(tmp_path):
    (tmp_path / "e.csv").write_text("", encoding="utf-8")
    with pytest.raises(UserError, match="empty"):
        build(tmp_path / "e.csv")


def test_old_xls_is_rejected_with_advice(tmp_path):
    (tmp_path / "old.xls").write_bytes(b"x")
    with pytest.raises(UserError, match=r"\.xls"):
        build(tmp_path / "old.xls")


def test_too_few_usable_rows(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Capital", "Paris"), ("", "")])
    with pytest.raises(UserError, match="at least 2"):
        build(path)


# ------------------------------------------------------------------ rows
def test_blank_rows_are_skipped_silently(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Capital", "Paris"), ("", ""), ("  ", " "), ("Eternal city", "Rome")])
    rows, rep = build(path)
    assert len(rows) == 2
    assert rep["skipped"] == []
    assert rep["blank_rows"] == 2


def test_missing_clue_or_answer_reported_by_row_number(tmp_path):
    path = write_csv(
        tmp_path / "x.csv",
        [("Capital", "Paris"), ("", "Orphan"), ("Clue only", ""), ("Eternal city", "Rome")],
    )
    rows, rep = build(path)
    assert len(rows) == 2
    reasons = {s["row"]: s["reason"] for s in rep["skipped"]}
    # row 1 is the header, as in a spreadsheet
    assert reasons == {3: "missing clue", 4: "missing answer"}


@pytest.mark.parametrize(
    ("answer", "fragment"),
    [
        ("R2D2", "digit"),
        ("1984", "digit"),
        ("A", "too short"),
        ("!!!", "no letters"),
        ("Supercalifragilisticexpialidocious", "too long"),
        ("東京", "outside A-Z"),
        ("مانا", "outside A-Z"),
    ],
)
def test_rejected_answers_are_explained(tmp_path, answer, fragment):
    path = write_csv(tmp_path / "x.csv", [("Capital", "Paris"), ("Eternal city", "Rome"), ("Bad one", answer)])
    rows, rep = build(path)
    assert len(rows) == 2
    assert len(rep["skipped"]) == 1
    assert fragment in rep["skipped"][0]["reason"]
    assert rep["skipped"][0]["row"] == 4


def test_min_and_max_length_options(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Two", "Ox"), ("Five", "Hello"), ("Long", "Wonderful"), ("Other", "World")])
    rows, rep = build(path, min_len=3, max_len=6)
    assert [r["grid"] for r in rows] == ["HELLO", "WORLD"]
    assert len(rep["skipped"]) == 2


def test_two_letter_answers_are_allowed_by_default(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Ox", "Ox"), ("Hello", "Hello")])
    rows, _ = build(path)
    assert len(rows) == 2


def test_duplicate_answers_warn_and_keep_the_first(tmp_path):
    path = write_csv(
        tmp_path / "x.csv",
        [("First clue", "Paris"), ("Eternal city", "Rome"), ("Second clue", "PARIS"), ("Third", "p a r i s")],
    )
    rows, rep = build(path)
    assert [r["grid"] for r in rows] == ["PARIS", "ROME"]
    assert rows[0]["clue"] == "First clue"
    assert len(warnings_of(rep)) == 2
    assert "duplicate of row 2" in warnings_of(rep)[0]
    assert all(s.get("duplicate") for s in rep["skipped"])


def test_duplicate_ids_are_made_unique(tmp_path):
    path = write_csv(
        tmp_path / "x.csv", [("1", "Capital", "Paris"), ("1", "Eternal city", "Rome")], header=("id", "clue", "answer")
    )
    rows, rep = build(path)
    assert len({r["id"] for r in rows}) == 2
    assert any("used twice" in w for w in warnings_of(rep))


# ------------------------------------------------------------ enumeration
def test_multiword_answers_get_an_enumeration(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("London clock tower", "Big Ben"), ("Capital of France", "Paris")])
    rows, _ = build(path)
    assert rows[0]["clue"] == "London clock tower (3,3)"
    assert rows[1]["clue"] == "Capital of France"  # single words get theirs when the poster is rendered


def test_existing_enumeration_is_kept_not_doubled(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("London clock tower (3,3)", "Big Ben"), ("Capital (5)", "Paris")])
    rows, rep = build(path)
    assert rows[0]["clue"] == "London clock tower (3,3)"
    assert rows[1]["clue"] == "Capital (5)"
    assert warnings_of(rep) == []


def test_wrong_enumeration_is_corrected_with_a_warning(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("London clock tower (4,3)", "Big Ben"), ("Capital (7)", "Paris")])
    rows, rep = build(path)
    assert rows[0]["clue"] == "London clock tower (3,3)"
    assert rows[1]["clue"] == "Capital"
    assert len(warnings_of(rep)) == 2


def test_year_in_brackets_is_not_mistaken_for_an_enumeration(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Moon landing year (1969)", "Apollo"), ("Capital", "Paris")])
    rows, rep = build(path)
    assert rows[0]["clue"] == "Moon landing year (1969)"
    assert warnings_of(rep) == []


def test_clue_whitespace_is_collapsed(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("  Capital   of\nFrance ", " Paris "), ("Eternal city", "Rome")])
    rows, _ = build(path)
    assert rows[0]["clue"] == "Capital of France"
    assert rows[0]["display"] == "Paris"


# ------------------------------------------------------------- giveaways
def test_giveaways_are_reported(tmp_path):
    path = write_csv(tmp_path / "x.csv", [("Paris is the capital of France", "Paris"), ("Eternal city", "Rome")])
    _, rep = build(path)
    assert [(g["contains"], g["itself"]) for g in rep["giveaways"]] == [("PARIS", True)]


# ----------------------------------------------------------------- samples
@pytest.mark.parametrize("sample", [SAMPLE_BIRTHDAY, SAMPLE_TRIVIA])
def test_bundled_samples_are_clean(sample):
    rows, rep = build(sample)
    assert rep["skipped"] == []
    assert rep["warnings"] == []
    assert rep["giveaways"] == []
    assert len(rows) >= 45
