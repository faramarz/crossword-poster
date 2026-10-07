#!/usr/bin/env python3
"""Transpose a grid.json (rows<->cols, across<->down), renumber in reading order, keep every answer and clue.
Handy for turning a wide layout into a tall one (or vice versa) to suit the poster shape.

usage: python -m crossword_poster transpose SRC_GRID.json OUT_DIR   (writes OUT_DIR/grid.json and OUT_DIR/clues.csv)
"""
import csv
import json
import os
import sys


def transpose(d):
    g = d["grid"]
    R, C = len(g), len(g[0])
    t = [[g[r][c] for r in range(R)] for c in range(C)]  # C rows x R cols
    flip = {"across": "down", "down": "across"}
    old = {(p["row"], p["col"], p["direction"]): p for p in d["placements"]}
    clues_old = {(c["number"], c["direction"]): c for c in d["clues"]}
    starts = {}  # (row, col, dir) -> (old placement, old clue)
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
    res["stats"] = dict(d.get("stats", {}), bbox_rows=C, bbox_cols=R,
                        note="transposed (rows<->cols), renumbered; same answers and clues")
    return res


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    src, out = argv[0], argv[1].rstrip("/")
    res = transpose(json.load(open(src, encoding="utf-8")))
    os.makedirs(out, exist_ok=True)
    with open(out + "/grid.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    rows = sorted(res["clues"], key=lambda c: (c["direction"] != "across", c["number"]))
    with open(out + "/clues.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "direction", "clue", "answer", "id"])
        for c in rows:
            w.writerow([c["number"], c["direction"], c["clue"], c["display_answer"], c.get("id", c.get("source", ""))])
    print("rows", res["rows"], "cols", res["cols"], "words", len(res["placements"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
