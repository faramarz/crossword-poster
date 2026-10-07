"""Independent grid validator (it does not import the generator).

Checks a grid.json, as written by `build` (with clues) or by `generate --out-json` (without clues):
  * the grid fits within MAX_ROWS x MAX_COLS (optional) and its bounding box is tight
  * every across/down run of 2+ letters is a listed placement, and vice versa; letters match; no duplicate starts
  * numbering follows reading order; every placement has exactly one non-empty clue whose answer matches
  * no orphan letters (every letter is in a word), the letters form one connected shape, no duplicate answers
  * with --pool: every pool entry (by id) appears in the grid
  * a trailing enumeration such as "(3,3)" in a clue matches the answer length
A raw `generate` file has no clues, so the clue checks and --pool are skipped and the output says so.

Usage:
  crossword-poster validate out/details/grid.json [MAX_ROWS MAX_COLS] [--pool out/details/pool.csv]
Exit status 0 = valid, 1 = errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from .errors import UserError
from .pool import enumeration_total, read_pool


def check_shape(d: object, path: str, letters_only: bool = False) -> None:
    """Raise a friendly UserError unless ``d`` has the structure of a grid.json.

    With ``letters_only`` every cell must also be empty or a single letter A-Z (the renderer needs that; the
    validator instead reports odd cells as errors).
    """

    def bad(why: str):
        return UserError(
            f"{path} is not a usable grid file: {why}.",
            "use the grid.json written by `build` or `generate --out-json`",
        )

    if not isinstance(d, dict):
        raise bad("it should hold one JSON object")
    g = d.get("grid")
    if not isinstance(g, list) or not g or not all(isinstance(row, list) and row for row in g):
        raise bad("the 'grid' is missing or empty")
    if len({len(row) for row in g}) != 1:
        raise bad("the rows of the 'grid' have different lengths")
    for row in g:
        for ch in row:
            if not isinstance(ch, str) or (letters_only and ch and not (len(ch) == 1 and "A" <= ch <= "Z")):
                raise bad(f"grid cells must be empty or a single letter A-Z, found {str(ch)[:20]!r}")
    pl = d.get("placements")
    if not isinstance(pl, list):
        raise bad("'placements' is missing")
    for p in pl:
        if not isinstance(p, dict) or not {"number", "word", "row", "col", "direction"} <= set(p):
            raise bad("a placement lacks number, word, row, col or direction")
        ints = all(isinstance(p[k], int) and not isinstance(p[k], bool) for k in ("number", "row", "col"))
        if not (ints and isinstance(p["word"], str) and p["direction"] in ("across", "down")):
            raise bad("a placement has a value of the wrong type")
    cl = d.get("clues")
    if cl is not None and (
        not isinstance(cl, list)
        or not all(isinstance(c, dict) and {"number", "direction", "answer", "clue", "id"} <= set(c) for c in cl)
    ):
        raise bad("'clues' should be a list of entries with number, direction, answer, clue and id")


def validate(
    grid_path: str, max_rows: Optional[int] = None, max_cols: Optional[int] = None, pool: Optional[list] = None
) -> tuple:
    """Check a grid.json. Returns ``(errors, info)``; ``errors`` is an empty list when the grid is valid."""
    try:
        with open(grid_path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        raise UserError(f"{grid_path} not found.") from None
    except json.JSONDecodeError as exc:
        raise UserError(f"{grid_path} is not a valid grid file ({exc}).") from exc
    check_shape(d, grid_path)
    g = d["grid"]
    R, C = len(g), len(g[0])
    errs, info = [], []
    odd = [
        (r, c, ch)
        for r, row in enumerate(g)
        for c, ch in enumerate(row)
        if ch and not (len(ch) == 1 and "A" <= ch <= "Z")
    ]
    if odd:
        errs.append(("cell is not a single letter A-Z", odd[:5]))
    if (max_rows and max_rows < R) or (max_cols and max_cols < C):
        errs.append(("bound exceeded", R, C))

    def cell(r, c):
        return g[r][c] if 0 <= r < R and 0 <= c < C else ""

    runs = {}
    for r in range(R):
        c = 0
        while c < C:
            if cell(r, c):
                s = c
                while cell(r, c):
                    c += 1
                if c - s >= 2:
                    runs[(r, s, "across")] = "".join(g[r][s:c])
            else:
                c += 1
    for c in range(C):
        r = 0
        while r < R:
            if cell(r, c):
                s = r
                while cell(r, c):
                    r += 1
                if r - s >= 2:
                    runs[(s, c, "down")] = "".join(g[x][c] for x in range(s, r))
            else:
                r += 1

    listed = {}
    for p in d["placements"]:
        k = (p["row"], p["col"], p["direction"])
        if k in listed:
            errs.append(("dup start", k))
        listed[k] = p["word"]
        for i, ch in enumerate(p["word"]):
            rr, cc = (p["row"], p["col"] + i) if p["direction"] == "across" else (p["row"] + i, p["col"])
            if cell(rr, cc) != ch:
                errs.append(("letter mismatch", p["word"], rr, cc))
    if runs != listed:
        errs.append(
            (
                "runs != listed",
                {k: v for k, v in runs.items() if listed.get(k) != v},
                {k: v for k, v in listed.items() if runs.get(k) != v},
            )
        )

    num, n = {}, 1
    for r in range(R):
        for c in range(C):
            if cell(r, c) and ((r, c, "across") in runs or (r, c, "down") in runs):
                num[(r, c)] = n
                n += 1
    for p in d["placements"]:
        if num.get((p["row"], p["col"])) != p["number"]:
            errs.append(("number", p["word"], p["number"], num.get((p["row"], p["col"]))))

    cl = d.get("clues")
    has_clues = cl is not None
    if not has_clues:
        cl = []
        info.append("INFO no clues in this file (raw `generate` output): clue checks and --pool were skipped")
    elif len(cl) != len(d["placements"]):
        errs.append("clue count")
    for c_ in cl:
        p = [x for x in d["placements"] if x["number"] == c_["number"] and x["direction"] == c_["direction"]]
        if len(p) != 1 or p[0]["word"] != c_["answer"]:
            errs.append(("clue mismatch", c_["number"], c_["direction"]))
        if not c_["clue"].strip():
            errs.append(("empty clue", c_["number"]))

    cov = set()
    for (r, c, di), w in runs.items():
        for i in range(len(w)):
            cov.add((r, c + i) if di == "across" else (r + i, c))
    letters = {(r, c) for r in range(R) for c in range(C) if g[r][c]}
    if not letters:
        errs.append("empty grid")
        return errs, info
    if letters != cov:
        errs.append(("orphan letters", sorted(letters - cov)))
    seen, st = set(), [next(iter(letters))]
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x)
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            y = (x[0] + dr, x[1] + dc)
            if y in letters and y not in seen:
                st.append(y)
    if seen != letters:
        errs.append(("disconnected", len(letters - seen)))

    ws = [p["word"] for p in d["placements"]]
    if len(set(ws)) != len(ws):
        errs.append("duplicate answers")
    subs = [(a, b) for a in ws for b in ws if a != b and a in b]
    if subs:
        info.append(f"INFO substring pairs (allowed, all words required): {len(subs)} {subs[:8]}")
    if not any(g[0]) or not any(g[-1]) or not any(row[0] for row in g) or not any(row[-1] for row in g):
        errs.append("bbox not tight")

    if pool and has_clues:
        must = [r["id"] for r in pool]
        ids = {c["id"] for c in cl}
        miss = [m for m in must if m not in ids]
        if miss:
            errs.append(("MUST-INCLUDE missing", miss))
        info.append(f"pool entries required: {len(must)}")

    for c_ in cl:
        claimed = enumeration_total(c_["clue"])
        if claimed is not None and claimed != len(c_["answer"]):
            errs.append(("enumeration != length", c_["number"], c_["clue"], len(c_["answer"])))

    info.insert(
        0,
        f"{grid_path}: words {len(ws)} across {sum(1 for k in runs if k[2] == 'across')} "
        f"down {sum(1 for k in runs if k[2] == 'down')} letters {len(letters)} bbox {R} x {C}",
    )
    return errs, info


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``validate``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster validate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("target", help="grid.json, or a folder containing grid.json")
    ap.add_argument("max_rows", nargs="?", type=int, default=None, metavar="MAX_ROWS",
                    help="optional: report an error if the grid has more rows than this")  # fmt: skip
    ap.add_argument("max_cols", nargs="?", type=int, default=None, metavar="MAX_COLS",
                    help="optional: report an error if the grid has more columns than this")  # fmt: skip
    ap.add_argument("--pool", default=None, help="pool CSV from `pool`: every entry must be in the grid")
    a = ap.parse_args(argv)
    path = os.path.join(a.target, "grid.json") if os.path.isdir(a.target) else a.target
    errs, info = validate(path, a.max_rows, a.max_cols, read_pool(a.pool) if a.pool else None)
    for line in info:
        print(line)
    print("ERRORS:", errs if errs else "none")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
