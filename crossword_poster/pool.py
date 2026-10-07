"""Pool builder: a clue/answer table (CSV or XLSX) -> normalised pool of grid words, clues and display answers.

For every input row it
  * finds the clue and answer columns by name (case-insensitive: clue/clues/question, answer/answers/word)
  * skips blank rows silently and reports rows with a missing clue or answer by their spreadsheet row number
  * normalises the answer to the letters that go in the grid (A-Z, accents folded, spaces and punctuation dropped)
    and explains any answer that cannot be used (digits, other alphabets, too short, too long)
  * keeps the first of several rows with the same grid word and warns about the others
  * appends an enumeration such as "(5,3)" to the clue of a multi-word answer that has none
  * reports "giveaways": clues that contain an answer as a whole word or phrase

Writes OUT (default pool.csv; columns grid,clue,display,id) and OUT-with-_report.json.

Usage:
  crossword-poster pool --clues mine.csv --out out/pool.csv
  crossword-poster pool --clues mine.csv --clue-column Question --answer-column Word
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
from typing import Optional

from .errors import UserError

# a trailing enumeration such as "(5)", "(3,3)" or "(5-3)"
ENUM_RE = re.compile(r"\(\s*\d{1,2}(?:\s*[,-]\s*\d{1,2})*\s*\)\s*$")

CLUE_NAMES = ("clue", "clues", "question", "questions", "hint", "hints")
ANSWER_NAMES = ("answer", "answers", "word", "words", "solution", "solutions")
ID_NAMES = ("id",)
ENUM_NAMES = ("enumeration", "enum")
DEFAULT_MIN_LEN = 2
DEFAULT_MAX_LEN = 20
SPARSE_BELOW = 8
CROWDED_ABOVE = 120

# letters that Unicode decomposition does not turn into A-Z
_SPECIAL = str.maketrans(
    {"ß": "SS", "æ": "AE", "Æ": "AE", "œ": "OE", "Œ": "OE", "ø": "O", "Ø": "O",
     "đ": "D", "Đ": "D", "ł": "L", "Ł": "L", "ı": "I", "þ": "TH", "Þ": "TH"}
)  # fmt: skip


def _fold(text: str) -> str:
    """Upper-case ``text`` with accents removed (NFKD), keeping every other character."""
    s = unicodedata.normalize("NFKD", (text or "").translate(_SPECIAL))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).upper()


def grid_word(text: str) -> str:
    """``'Mount Saint-Hélène'`` -> ``'MOUNTSAINTHELENE'`` (A-Z only)."""
    return re.sub(r"[^A-Z]", "", _fold(text))


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", _fold(text))


def enumeration(display: str) -> str:
    """``'Big Ben'`` -> ``'(3,3)'``; an empty string for a single word."""
    parts = [len(grid_word(p)) for p in re.split(r"[^A-Za-z0-9À-ɏ]+", display or "") if grid_word(p)]
    return "(" + ",".join(map(str, parts)) + ")" if len(parts) > 1 else ""


def enumeration_total(clue: str) -> Optional[int]:
    """The letter count a trailing enumeration in ``clue`` claims, or None when there is none."""
    m = ENUM_RE.search(clue)
    return sum(int(n) for n in re.findall(r"\d+", m.group())) if m else None


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ------------------------------------------------------------------ reading
def _decode(raw: bytes, path: str) -> tuple[str, Optional[str]]:
    """Decode a CSV: UTF-8 (with or without BOM), falling back to Windows-1252 as Excel writes it."""
    try:
        return raw.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252"), "the file is not UTF-8; it was read as Windows-1252 (Excel's default)"
    except UnicodeDecodeError:
        raise UserError(
            f"{path} does not look like a text file.", "save it as 'CSV UTF-8' from Excel / Google Sheets"
        ) from None


def _read_csv(path: str) -> tuple[list[list[str]], list[str]]:
    with open(path, "rb") as fh:
        text, note = _decode(fh.read(), path)
    notes = [note] if note else []
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = max(",;\t", key=first.count) if first.count(",") + first.count(";") + first.count("\t") else ","
    try:
        rows = [list(r) for r in csv.reader(io.StringIO(text, newline=""), delimiter=delim)]
    except csv.Error as exc:
        raise UserError(f"{path} could not be read as CSV ({exc}).", "re-save it as 'CSV UTF-8'") from exc
    return rows, notes


def _read_xlsx(path: str) -> tuple[list[list[str]], list[str]]:
    try:
        import openpyxl
    except ImportError:
        raise UserError(
            "Reading .xlsx files needs the optional 'openpyxl' package.",
            "either save the sheet as CSV (File > Save As > CSV UTF-8) or run: pip install 'crossword-poster[xlsx]'",
        ) from None
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise UserError(f"{path} could not be opened as an Excel file ({exc}).", "re-save it, or export a CSV") from exc
    try:
        ws = wb.worksheets[0]
        rows = [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
        note = f"read the first sheet ('{ws.title}') of the workbook" if len(wb.worksheets) > 1 else None
    finally:
        wb.close()
    return rows, [note] if note else []


def read_table(path: str) -> tuple[list[list[str]], list[str]]:
    """Read a CSV or XLSX file into a list of rows (each a list of strings) plus notes about how it was read."""
    if not os.path.exists(path):
        raise UserError(f"File not found: {path}", "check the path and spelling (tip: drag the file into the terminal)")
    if os.path.isdir(path):
        raise UserError(f"{path} is a folder, not a file.", "give the path of the CSV file")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        raise UserError("Old .xls files are not supported.", "open it in Excel / Sheets and save as CSV UTF-8 or .xlsx")
    rows, notes = _read_xlsx(path) if ext == ".xlsx" else _read_csv(path)
    return rows, notes


def find_column(headers: list[str], names, explicit: Optional[str], what: str, required: bool = True) -> Optional[int]:
    """Index of the column called ``explicit`` or, failing that, any of ``names`` (case-insensitive)."""
    norm = [h.strip().lower() for h in headers]
    if explicit:
        if explicit.strip().lower() in norm:
            return norm.index(explicit.strip().lower())
        raise UserError(
            f"There is no column called '{explicit}' (the {what} column).",
            f"the columns in your file are: {', '.join(repr(h) for h in headers if h.strip())}",
        )
    for n in names:
        if n in norm:
            return norm.index(n)
    if required:
        raise UserError(
            f"Could not find the {what} column. The columns in your file are: "
            f"{', '.join(repr(h) for h in headers if h.strip()) or '(none)'}.",
            f"rename the header cell to '{names[0]}', or pass --{what}-column NAME. "
            "`crossword-poster template my_clues.csv` writes a correct starter file.",
        )
    return None


# ----------------------------------------------------------------- building
def build_pool(
    path: str,
    clue_col: Optional[str] = None,
    answer_col: Optional[str] = None,
    id_col: Optional[str] = None,
    grid_col: Optional[str] = None,
    min_len: int = DEFAULT_MIN_LEN,
    max_len: int = DEFAULT_MAX_LEN,
) -> tuple[list[dict], dict]:
    """Read ``path`` and return ``(rows, report)``.

    ``rows`` is a list of dicts with keys ``grid`` (A-Z word), ``clue``, ``display`` (the answer as written) and ``id``.
    ``report`` has ``rows_in``, ``kept``, ``skipped`` (row/answer/reason), ``warnings``, ``notes`` and ``giveaways``.
    Raises UserError for problems with the file as a whole (missing, no usable columns, nothing usable).
    """
    table, notes = read_table(path)
    while table and not any(c.strip() for c in table[0]):
        table.pop(0)  # blank lines above the header
    if not table:
        raise UserError(f"{path} is empty.", "it needs a header row (clue, answer) and one row per clue")
    headers = [h.strip() for h in table[0]]
    ci = find_column(headers, CLUE_NAMES, clue_col, "clue")
    ai = find_column(headers, ANSWER_NAMES, answer_col, "answer")
    ii = find_column(headers, ID_NAMES, id_col, "id", required=False)
    ei = find_column(headers, ENUM_NAMES, None, "enumeration", required=False)
    gi = find_column(headers, (), grid_col, "grid", required=False) if grid_col else None

    def cell(row: list[str], idx: Optional[int]) -> str:
        return _clean(row[idx]) if idx is not None and idx < len(row) else ""

    rows: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []
    seen: dict[str, int] = {}
    used_ids: set[str] = set()
    blank = 0
    for n, row in enumerate(table[1:], start=2):  # n = the row number a spreadsheet shows
        if not any(c.strip() for c in row):
            blank += 1
            continue
        clue, display = cell(row, ci), cell(row, ai)
        gw = grid_word(cell(row, gi) or display)
        rid = cell(row, ii) or f"row{n}"
        why = _reject_reason(clue, display, gw, min_len, max_len)
        if why:
            skipped.append(dict(id=rid, row=n, answer=display, reason=why))
            continue
        if gw in seen:
            warnings.append(
                f"Row {n}: '{display}' is a duplicate of row {seen[gw]}; kept the first and ignored this one."
            )
            skipped.append(dict(id=rid, row=n, answer=display, reason=f"duplicate of row {seen[gw]}", duplicate=True))
            continue
        seen[gw] = n
        if rid in used_ids:
            warnings.append(f"Row {n}: id '{rid}' is used twice; renamed to 'row{n}'.")
            rid = f"row{n}"
        used_ids.add(rid)
        clue = _with_enumeration(clue, display, gw, cell(row, ei), n, warnings)
        rows.append(dict(grid=gw, clue=clue, display=display, id=rid, row=n))

    if len(rows) < 2:
        raise UserError(
            f"Only {len(rows)} usable clue(s) found in {path}; a crossword needs at least 2.",
            "check the skipped rows listed above, or add more clues",
        )
    if len(rows) < SPARSE_BELOW:
        warnings.append(f"Only {len(rows)} clues: the poster will look sparse. About 30 to 60 clues works best.")
    if len(rows) > CROWDED_ABOVE:
        warnings.append(
            f"{len(rows)} clues is a lot for one poster; the type will be small. Try a bigger --size or fewer clues."
        )
    report = dict(
        rows_in=len(table) - 1 - blank, kept=len(rows), skipped=skipped, warnings=warnings, notes=notes,
        blank_rows=blank, giveaways=giveaways(rows),
        columns=dict(clue=headers[ci], answer=headers[ai]),
    )  # fmt: skip
    return rows, report


def _reject_reason(clue: str, display: str, gw: str, min_len: int, max_len: int) -> Optional[str]:
    """Why a row cannot be used, in plain language (None when it is fine)."""
    if not clue and not display:
        return "no clue and no answer"
    if not clue:
        return "missing clue"
    if not display:
        return "missing answer"
    if re.search(r"\d", display):
        return "the answer contains a digit; crossword answers are letters only (spell numbers out, e.g. 'Nineteen eighty four')"
    stray = sorted({ch for ch in _fold(display) if ch.isalpha() and not ("A" <= ch <= "Z")})
    if stray:
        return f"the answer contains letters outside A-Z ({' '.join(stray)}); only the Latin alphabet is supported"
    if not gw:
        return "the answer has no letters A-Z"
    if len(gw) < min_len:
        return f"too short: {len(gw)} letter(s), the minimum is {min_len}"
    if len(gw) > max_len:
        return f"too long: {len(gw)} letters, the maximum is {max_len} (shorten it or raise --max-len)"
    return None


def _with_enumeration(clue: str, display: str, gw: str, given: str, row: int, warnings: list[str]) -> str:
    """Return the clue with a correct trailing enumeration for multi-word answers (single words get one at render)."""
    base = ENUM_RE.sub("", clue).rstrip()
    if given:
        text = given if given.startswith("(") else f"({given})"
        if enumeration_total(text) == len(gw):
            return f"{base} {text}"
        warnings.append(
            f"Row {row}: the enumeration column says {text} but '{display}' has {len(gw)} letters; ignored it."
        )
    claimed = enumeration_total(clue)
    if claimed is not None:
        if claimed == len(gw):
            return clue
        warnings.append(
            f"Row {row}: the clue ends in a length of {claimed} but '{display}' has {len(gw)} letters; corrected it."
        )
    enum = enumeration(display)
    return f"{base} {enum}" if enum else base


def giveaways(rows: list[dict]) -> list[dict]:
    """Clues that contain an answer (whole word, or whole phrase for multi-word answers), their own included."""
    out = []
    for r in rows:
        words = _words(ENUM_RE.sub("", r["clue"]))
        for o in rows:
            disp = _words(o["display"])
            if len(disp) > 1:
                n = len(disp)
                hit = any(words[i : i + n] == disp for i in range(len(words) - n + 1))
            else:
                hit = o["grid"] in words
            if hit:
                out.append(dict(id=r["id"], clue=r["clue"], contains=o["grid"], itself=o is r))
    return out


# ------------------------------------------------------------------- output
def write_pool(rows: list[dict], out: str) -> None:
    """Write the pool to ``out`` as CSV (columns grid, clue, display, id)."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["grid", "clue", "display", "id"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_pool(path: str) -> list[dict]:
    """Read a pool CSV written by :func:`write_pool`."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def print_pool_report(rep: dict, report_path: Optional[str] = None) -> None:
    """Print the human-readable summary of a pool report."""
    extra = f" (details: {report_path})" if report_path else ""
    print(
        f"  {rep['kept']} usable of {rep['rows_in']} rows; {len(rep['skipped'])} skipped; {len(rep['giveaways'])} giveaway pairs{extra}"
    )
    for note in rep["notes"]:
        print(f"  note: {note}")
    for s in rep["skipped"]:
        if not s.get("duplicate"):
            print(f"  skipped row {s['row']} ({s['answer']!r}): {s['reason']}")
    for w in rep["warnings"]:
        print(f"  warning: {w}")
    for g in rep["giveaways"]:
        which = "its own answer" if g["itself"] else f"the answer {g['contains']}"
        print(f"  giveaway? the clue {g['clue']!r} contains {which}")


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``pool``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster pool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--clues", required=True, help="input CSV (or .xlsx) with a clue column and an answer column")
    ap.add_argument("--clue-column", default=None, help="header of the clue column (default: clue, clues or question)")
    ap.add_argument(
        "--answer-column", default=None, help="header of the answer column (default: answer, answers or word)"
    )
    ap.add_argument("--grid-column", default=None, help="optional column with the pre-normalised grid word")
    ap.add_argument("--id-column", default=None, help="optional unique id column (default: the row number)")
    ap.add_argument(
        "--min-len", type=int, default=DEFAULT_MIN_LEN, help="shortest allowed answer (default %(default)s)"
    )
    ap.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN, help="longest allowed answer (default %(default)s)")
    ap.add_argument("--out", default="pool.csv", help="where to write the pool (default %(default)s)")
    a = ap.parse_args(argv)
    rows, rep = build_pool(a.clues, a.clue_column, a.answer_column, a.id_column, a.grid_column, a.min_len, a.max_len)
    write_pool(rows, a.out)
    report_path = os.path.splitext(a.out)[0] + "_report.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    print(f"pool: {rep['kept']} usable of {rep['rows_in']} rows -> {a.out}")
    print_pool_report(rep, report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
