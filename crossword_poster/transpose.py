"""Transpose a grid.json (rows <-> columns, across <-> down), renumber in reading order, keep every answer and clue.

Handy for turning a wide layout into a tall one (or the other way round) to suit the poster shape.

Usage: crossword-poster transpose SRC_GRID.json OUT_DIR   (writes OUT_DIR/grid.json and OUT_DIR/clues.csv)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Optional

from .errors import UserError


def transpose(d: dict) -> dict:
    """Return a transposed copy of a grid dict (placements and clues renumbered)."""
    g = d["grid"]
    R, C = len(g), len(g[0])
    t = [[g[r][c] for r in range(R)] for c in range(C)]  # C rows x R cols
    flip = {"across": "down", "down": "across"}
    old = {(p["row"], p["col"], p["direction"]): p for p in d["placements"]}
    clues_old = {(c["number"], c["direction"]): c for c in d["clues"]}
    starts = {}  # (row, col, direction) -> (old placement, old clue)
    for (r, c, di), p in old.items():
        starts[(c, r, flip[di])] = (p, clues_old[(p["number"], di)])
    num, n = {}, 0
    for r in range(C):
        for c in range(R):
            if t[r][c] and any((r, c, x) in starts for x in ("across", "down")):
                n += 1
                num[(r, c)] = n
    placements, clues = [], []
    for (r, c, di), (p, cl) in sorted(starts.items(), key=lambda kv: (num[kv[0][:2]], kv[0][2])):
        q = dict(p)
        q.update(number=num[(r, c)], row=r, col=c, direction=di)
        placements.append(q)
        k = dict(cl)
        k.update(number=num[(r, c)], direction=di)
        clues.append(k)
    res = dict(d)
    res.update(rows=C, cols=R, grid=t, placements=placements, clues=clues)
    res["stats"] = dict(
        d.get("stats", {}),
        bbox_rows=C,
        bbox_cols=R,
        note="transposed (rows<->cols), renumbered; same answers and clues",
    )
    return res


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``transpose``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster transpose", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("src", help="grid.json to transpose")
    ap.add_argument("out_dir", help="folder to write the new grid.json and clues.csv into")
    a = ap.parse_args(argv)
    try:
        with open(a.src, encoding="utf-8") as fh:
            res = transpose(json.load(fh))
    except FileNotFoundError:
        raise UserError(f"{a.src} not found.") from None
    out = a.out_dir
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "grid.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    rows = sorted(res["clues"], key=lambda c: (c["direction"] != "across", c["number"]))
    with open(os.path.join(out, "clues.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "direction", "clue", "answer", "id"])
        for c in rows:
            w.writerow([c["number"], c["direction"], c["clue"], c["display_answer"], c.get("id", c.get("source", ""))])
    print(f"wrote {out}: {res['rows']} rows x {res['cols']} cols, {len(res['placements'])} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
