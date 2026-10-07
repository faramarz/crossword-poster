#!/usr/bin/env python3
"""Pool builder: clue/answer CSV -> normalised pool (grid word, clue, display answer, id) + a quality report.

For every input row it
  * normalises the answer to the letters that go in the grid (A-Z, accents folded, spaces/punctuation dropped)
  * skips rows with an empty clue/answer, an answer outside --min-len/--max-len, or a duplicate grid word
  * appends an enumeration such as "(3,3)" to the clue of a multi-word answer that has none
  * reports "giveaways": clues that contain another entry's answer (or their own) as a whole word / phrase

Writes OUT (default pool.csv; columns grid,clue,display,id) and OUT-with-.json-extension report.

Usage:
  python -m crossword_poster pool --clues examples/sample_clues.csv --out out/pool.csv
  python -m crossword_poster pool --clues mine.csv --clue-column Clue --answer-column Answer --id-column No
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata

ENUM_RE = re.compile(r"\(\d+(?:[,-]\d+)*\)\s*$")


def grid_word(text):
    """'Mount Saint-Hélène' -> 'MOUNTSAINTHELENE'."""
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z]", "", s.upper())


def _words(text):
    return re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper())


def enumeration(display):
    parts = [len(grid_word(p)) for p in re.split(r"[^A-Za-z0-9]+", unicodedata.normalize("NFKD", display)) if grid_word(p)]
    return "(" + ",".join(map(str, parts)) + ")" if len(parts) > 1 else ""


def build_pool(path, clue_col="clue", answer_col="answer", id_col=None, grid_col=None, min_len=3, max_len=15):
    """Return (rows, report). rows: list of dict(grid, clue, display, id)."""
    rows, skipped, seen, n = [], [], {}, 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        missing = [c for c in (clue_col, answer_col) if c not in (rd.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: missing column(s) {missing}; found {rd.fieldnames}")
        for n, row in enumerate(rd, 1):
            clue = re.sub(r"\s+", " ", row.get(clue_col) or "").strip()
            display = re.sub(r"\s+", " ", row.get(answer_col) or "").strip()
            gw = grid_word(row.get(grid_col) if grid_col and row.get(grid_col) else display)
            rid = (row.get(id_col) or "").strip() if id_col else ""
            rid = rid or f"row{n}"
            why = None
            if not clue:
                why = "empty clue"
            elif not gw:
                why = "empty answer"
            elif not (min_len <= len(gw) <= max_len):
                why = f"length {len(gw)} outside {min_len}-{max_len}"
            elif gw in seen:
                why = f"duplicate answer (first seen in {seen[gw]})"
            if why:
                skipped.append(dict(id=rid, row=n, answer=display, reason=why))
                continue
            seen[gw] = rid
            enum = enumeration(display)
            if enum and not ENUM_RE.search(clue):
                clue = f"{clue} {enum}"
            rows.append(dict(grid=gw, clue=clue, display=display, id=rid))
    return rows, dict(rows_in=n, kept=len(rows), skipped=skipped, giveaways=giveaways(rows))


def giveaways(rows):
    """Clues that contain another answer (whole word, or whole phrase for multi-word answers) or their own."""
    out = []
    for r in rows:
        words = _words(re.sub(r"\(\d+(?:[,-]\d+)*\)", "", r["clue"]))
        for o in rows:
            disp = _words(o["display"])
            if len(disp) > 1:
                n = len(disp)
                hit = any(words[i:i + n] == disp for i in range(len(words) - n + 1))
            else:
                hit = o["grid"] in words
            if hit:
                out.append(dict(id=r["id"], clue=r["clue"], contains=o["grid"], itself=o is r))
    return out


def write_pool(rows, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["grid", "clue", "display", "id"])
        w.writeheader()
        w.writerows(rows)


def read_pool(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster pool", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clues", required=True, help="input CSV with a clue column and an answer column")
    ap.add_argument("--clue-column", default="clue")
    ap.add_argument("--answer-column", default="answer", help="answer as it should read (may have spaces, accents)")
    ap.add_argument("--grid-column", default=None, help="optional column with the pre-normalised grid word")
    ap.add_argument("--id-column", default=None, help="optional unique id column (default: row number)")
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=15)
    ap.add_argument("--out", default="pool.csv")
    a = ap.parse_args(argv)
    rows, rep = build_pool(a.clues, a.clue_column, a.answer_column, a.id_column, a.grid_column, a.min_len, a.max_len)
    write_pool(rows, a.out)
    rpt = os.path.splitext(a.out)[0] + "_report.json"
    json.dump(rep, open(rpt, "w"), indent=1, ensure_ascii=False)
    gv = rep["giveaways"]
    print(f"pool: {rep['kept']} usable of {rep['rows_in']} rows -> {a.out}")
    for s in rep["skipped"]:
        print(f"  skipped row {s['row']} ({s['answer']!r}): {s['reason']}")
    print(f"giveaway pairs (a clue contains an answer as a whole word/phrase): {len(gv)}")
    for g in gv:
        print(f"  {g['id']}: {g['clue']!r} contains {g['contains']}" + (" (its own answer)" if g["itself"] else ""))
    if not rows:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
