#!/usr/bin/env python3
"""Freeform (barred-free, American-style "loose") crossword generator.

Standard library only. Greedy placement with randomized restarts.

Rules enforced
  * every word crosses at least one already-placed word (grid is connected)
  * a letter cell is shared by at most one Across and one Down word
  * no two words touch side-by-side (no illegal 2-letter adjacencies)
  * a word's start/end is bounded by an empty cell or the grid edge
  * no word is placed twice
Score = words_placed * 100 + 40 * density + 10 * crossings_per_word
(density = letter cells / bounding-box area, so compact + many words wins).

Two modes
  default   best-of-N layout that places as many words as it can; --required words must all be placed.
  --all     EVERY word must be placed. Many attempts are tried (in parallel) and the complete layout with the
            smallest bounding box wins. Without --max-width/--max-height the window is estimated from the letter
            count and grown automatically (--grow-tries) until a complete layout is found.

Examples
  python -m crossword_poster generate --csv out/pool.csv --column grid --clue-column clue \
      --all --attempts 2000 --seed 1 --out-json out/raw.json --out-txt out/raw.txt
  python -m crossword_poster generate --csv words.csv --column answer --max-width 25 --max-height 25 \
      --attempts 300 --seed 1 --required PLANET,RIVER

Read-only with respect to the input CSV.
"""
import argparse
import csv
import json
import math
import os
import random
import sys
import time

ACROSS, DOWN = 0, 1
DR = (0, 1)  # row step for ACROSS, DOWN
DC = (1, 0)  # col step


# ----------------------------------------------------------------- loading
def load_words(path, column="grid", min_len=3, max_len=15):
    """Unique, uppercase, alphabetic words with min_len <= len <= max_len."""
    seen, out = set(), []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w = (row.get(column) or "").strip().upper()
            if w.isalpha() and w.isascii() and min_len <= len(w) <= max_len and w not in seen:
                seen.add(w)
                out.append(w)
    return out


# ------------------------------------------------------------------- board
class Board:
    """Sparse board bounded by a W x H window anchored at the first word."""

    def __init__(self, width, height):
        self.W, self.H = width, height
        self.cells = {}      # (r, c) -> letter
        self.dirs = {}       # (r, c) -> bitmask of directions using the cell
        self.by_letter = {}  # letter -> list of (r, c)
        self.placed = []     # (word, r, c, dir)
        self.rmin = self.cmin = 10 ** 6
        self.rmax = self.cmax = -10 ** 6
        self.crossings = 0

    def bbox_after(self, r, c, d, n):
        r2, c2 = r + DR[d] * (n - 1), c + DC[d] * (n - 1)
        return (min(self.rmin, r), max(self.rmax, r2),
                min(self.cmin, c), max(self.cmax, c2))

    def can_place(self, word, r, c, d):
        """Return number of crossings if legal, else -1."""
        n = len(word)
        dr, dc = DR[d], DC[d]
        # window check
        if self.cells:
            r0, r1, c0, c1 = self.bbox_after(r, c, d, n)
            if r1 - r0 + 1 > self.H or c1 - c0 + 1 > self.W:
                return -1
        # cells just before / after must be empty
        if (r - dr, c - dc) in self.cells or (r + dr * n, c + dc * n) in self.cells:
            return -1
        cross = 0
        pr, pc = dc, dr  # perpendicular step
        for i in range(n):
            rr, cc = r + dr * i, c + dc * i
            ch = self.cells.get((rr, cc))
            if ch is not None:
                if ch != word[i] or (self.dirs[(rr, cc)] >> d) & 1:
                    return -1      # letter mismatch, or collinear overlap
                cross += 1
            else:
                # new cell: perpendicular neighbours must be empty
                if (rr + pr, cc + pc) in self.cells or (rr - pr, cc - pc) in self.cells:
                    return -1
        return cross

    def place(self, word, r, c, d, cross):
        dr, dc = DR[d], DC[d]
        for i, ch in enumerate(word):
            p = (r + dr * i, c + dc * i)
            if p not in self.cells:
                self.cells[p] = ch
                self.dirs[p] = 0
                self.by_letter.setdefault(ch, []).append(p)
            self.dirs[p] |= 1 << d
        r1, c1 = r + dr * (len(word) - 1), c + dc * (len(word) - 1)
        self.rmin, self.cmin = min(self.rmin, r), min(self.cmin, c)
        self.rmax, self.cmax = max(self.rmax, r1), max(self.cmax, c1)
        self.placed.append((word, r, c, d))
        self.crossings += cross

    def candidates(self, word):
        """Yield (r, c, d, crossings) for every legal crossing placement."""
        seen = set()
        for i, ch in enumerate(word):
            for (r, c) in self.by_letter.get(ch, ()):
                for d in (ACROSS, DOWN):
                    if (self.dirs[(r, c)] >> d) & 1:
                        continue
                    sr, sc = r - DR[d] * i, c - DC[d] * i
                    key = (sr, sc, d)
                    if key in seen:
                        continue
                    seen.add(key)
                    x = self.can_place(word, sr, sc, d)
                    if x >= 1:
                        yield sr, sc, d, x

    def density(self):
        if not self.cells:
            return 0.0
        h = self.rmax - self.rmin + 1
        w = self.cmax - self.cmin + 1
        return len(self.cells) / (h * w)

    def score(self):
        n = len(self.placed)
        return n * 100 + 40 * self.density() + 10 * (self.crossings / max(n, 1))


# --------------------------------------------------------------- one attempt
def build(words, required, W, H, rng, passes=3):
    b = Board(W, H)
    req = [w for w in required]
    rest = [w for w in words if w not in set(req)]
    rng.shuffle(rest)
    # bias: slightly favour long words early (they anchor), but keep randomness
    rest.sort(key=lambda w: -(len(w) + rng.random() * 6))
    queue = req + rest
    if not queue:
        return b
    # seed: longest of the first few, centred
    seed_w = queue[0] if req else max(queue[:8], key=len)
    queue.remove(seed_w)
    r0 = H // 2
    c0 = max(0, (W - len(seed_w)) // 2)
    b.place(seed_w, r0, c0, ACROSS, 0)
    for _ in range(passes):
        progress = False
        leftover = []
        for w in queue:
            best, best_key = None, None
            for (r, c, d, x) in b.candidates(w):
                r_lo, r_hi, c_lo, c_hi = b.bbox_after(r, c, d, len(w))
                area = (r_hi - r_lo + 1) * (c_hi - c_lo + 1)
                # prefer many crossings, small bbox, then random tiebreak
                key = (x, -area, rng.random())
                if best_key is None or key > best_key:
                    best, best_key = (r, c, d, x), key
            if best:
                b.place(w, *best[:3], best[3])
                progress = True
            else:
                leftover.append(w)
        queue = leftover
        if not progress or not queue:
            break
    return b


def generate(words, required=(), W=25, H=25, attempts=100, seed=0, passes=3):
    """Best of `attempts` randomized builds. Returns (Board, unplaced, stats)."""
    rng = random.Random(seed)
    req = [w.upper() for w in required]
    pool = list(dict.fromkeys(req + [w for w in words if w not in req]))
    best, best_score = None, -1
    t0 = time.time()
    for _ in range(attempts):
        b = build(pool, req, W, H, rng, passes)
        # required words must all be present to be eligible
        have = {p[0] for p in b.placed}
        s = b.score() + (0 if all(r in have for r in req) else -10 ** 6)
        if s > best_score:
            best, best_score = b, s
    placed = {p[0] for p in best.placed}
    unplaced = [w for w in pool if w not in placed]
    stats = {
        "words_placed": len(best.placed),
        "words_offered": len(pool),
        "bbox_rows": best.rmax - best.rmin + 1,
        "bbox_cols": best.cmax - best.cmin + 1,
        "letter_cells": len(best.cells),
        "density": round(best.density(), 3),
        "crossings": best.crossings,
        "attempts": attempts,
        "seed": seed,
        "seconds": round(time.time() - t0, 2),
        "required_missing": [r for r in req if r not in placed],
    }
    return best, unplaced, stats


# ------------------------------------------------- all-words-required search
def _attempt(words, W, H, seed, k, noise, passes):
    """One randomized build; attempt k of a run is fully determined by (seed, k). Returns (Board, leftover)."""
    rng = random.Random(f"{seed}:{k}")
    b = Board(W, H)
    q = sorted(words, key=lambda w: -(len(w) + rng.random() * noise))
    seed_w = q.pop(0)
    b.place(seed_w, H // 2, max(0, (W - len(seed_w)) // 2), ACROSS, 0)
    for _ in range(passes):
        left, progress = [], False
        for w in q:
            best, best_key = None, None
            for (r, c, d, x) in b.candidates(w):
                r0, r1, c0, c1 = b.bbox_after(r, c, d, len(w))
                key = (x, -((r1 - r0 + 1) * (c1 - c0 + 1)), rng.random())
                if best_key is None or key > best_key:
                    best, best_key = (r, c, d, x), key
            if best:
                b.place(w, *best[:3], best[3])
                progress = True
            else:
                left.append(w)
        q = left
        if not q or not progress:
            break
    return b, q


def _run_chunk(args):
    words, W, H, seed, ks, noise, passes = args
    best, ok = None, 0
    for k in ks:
        b, left = _attempt(words, W, H, seed, k, noise, passes)
        if left:
            continue
        ok += 1
        area = (b.rmax - b.rmin + 1) * (b.cmax - b.cmin + 1)
        key = (-area, b.crossings, -k)
        if best is None or key > best[0]:
            best = (key, list(b.placed), k)
    return best, ok


def auto_bounds(words, aspect=0.8, slack=1.3):
    """Estimate a W x H search window (cols x rows) from the letter count: area ~ letters / 0.4 density * slack."""
    letters = sum(len(w) for w in words)
    area = letters / 0.4 * slack
    w = max(int(math.ceil(math.sqrt(area * aspect))), max(len(x) for x in words) + 2)
    h = max(int(math.ceil(area / w)), max(len(x) for x in words) + 2)
    return w, h


def generate_all(words, W=None, H=None, attempts=1000, seed=0, noise=6.0, passes=6, workers=1,
                 aspect=0.8, grow_tries=6, grow=1.15, log=None):
    """Place EVERY word. Returns (Board | None, stats). Of all complete layouts found, the smallest bounding box wins.
    If W/H are omitted they are estimated and grown by `grow` per failed round (up to `grow_tries` times);
    explicit bounds are never grown. Deterministic for a given (words, bounds, attempts, seed), whatever `workers` is."""
    words = list(dict.fromkeys(words))
    if not words:
        raise ValueError("no words to place")
    auto = W is None or H is None
    if auto:
        W, H = auto_bounds(words, aspect)
    longest = max(len(w) for w in words)
    t0 = time.time()
    rounds = (grow_tries + 1) if auto else 1
    for rnd in range(rounds):
        W, H = max(W, longest), max(H, longest)
        ks = list(range(attempts))
        n = max(1, min(workers, attempts))
        chunks = [(words, W, H, seed, ks[i::n], noise, passes) for i in range(n)]
        if n > 1:
            from multiprocessing import Pool
            with Pool(n) as pool:
                res = pool.map(_run_chunk, chunks)
        else:
            res = [_run_chunk(c) for c in chunks]
        ok = sum(r[1] for r in res)
        found = [r[0] for r in res if r[0]]
        if log:
            log(f"  window {W}x{H}: {ok} complete layouts in {attempts} attempts")
        if found:
            _, placed, k = max(found, key=lambda x: x[0])
            b = Board(W, H)
            for (w, r, c, d) in placed:
                b.place(w, r, c, d, 0)
            stats = {"words_placed": len(b.placed), "words_offered": len(words),
                     "bbox_rows": b.rmax - b.rmin + 1, "bbox_cols": b.cmax - b.cmin + 1,
                     "letter_cells": len(b.cells), "density": round(b.density(), 3),
                     "attempts": attempts, "complete_layouts": ok, "seed": seed, "best_attempt": k,
                     "bound": [W, H], "seconds": round(time.time() - t0, 2), "required_missing": []}
            return b, stats
        if rnd < rounds - 1:
            W, H = int(math.ceil(W * grow)), int(math.ceil(H * grow))
    return None, {"words_offered": len(words), "attempts": attempts, "seed": seed, "bound": [W, H],
                  "seconds": round(time.time() - t0, 2), "required_missing": words}


# ------------------------------------------------------------------- output
def to_result(b, unplaced, stats, clues=None):
    """Crop to bounding box, number cells, return JSON-able dict."""
    R, C = b.rmax - b.rmin + 1, b.cmax - b.cmin + 1
    grid = [["" for _ in range(C)] for _ in range(R)]
    for (r, c), ch in b.cells.items():
        grid[r - b.rmin][c - b.cmin] = ch
    starts = {}
    for (w, r, c, d) in b.placed:
        starts[(r - b.rmin, c - b.cmin, d)] = w
    number, nxt = {}, 1
    for r in range(R):
        for c in range(C):
            if (r, c, ACROSS) in starts or (r, c, DOWN) in starts:
                number[(r, c)] = nxt
                nxt += 1
    placements = []
    for (r, c, d), w in sorted(starts.items(), key=lambda kv: (number[kv[0][:2]], kv[0][2])):
        p = {"number": number[(r, c)], "word": w, "row": r, "col": c,
             "direction": "across" if d == ACROSS else "down", "length": len(w)}
        if clues and w in clues:
            p["clue"] = clues[w]
        placements.append(p)
    return {"rows": R, "cols": C, "grid": grid, "placements": placements,
            "unplaced": unplaced, "stats": stats}


def preview(res):
    g = res["grid"]
    lines = [f"{res['rows']} rows x {res['cols']} cols | words {res['stats']['words_placed']} "
             f"| density {res['stats']['density']}", ""]
    lines.append("    " + "".join(f"{c % 10}" for c in range(res["cols"])))
    for r, row in enumerate(g):
        lines.append(f"{r:>3} " + "".join(ch if ch else "." for ch in row))
    for dname in ("across", "down"):
        lines += ["", dname.upper()]
        for p in res["placements"]:
            if p["direction"] == dname:
                lines.append(f"  {p['number']:>3}. {p['word']} ({p['length']})"
                             + (f"  {p['clue']}" if "clue" in p else ""))
    if res["unplaced"]:
        lines += ["", f"UNPLACED ({len(res['unplaced'])}): " + ", ".join(res["unplaced"])]
    return "\n".join(lines)


def attach_pool(res, pool_rows):
    """Attach clues from pool rows (dicts with grid, clue, display, id) to a to_result() dict, in place.
    Adds res['clues'] (one per placement) and clue/answer/source fields on each placement."""
    pool = {r["grid"]: r for r in pool_rows}
    clues = []
    for p in res["placements"]:
        r = pool[p["word"]]
        p["answer"], p["clue"], p["source"] = r["display"], r["clue"], r["id"]
        clues.append({"number": p["number"], "direction": p["direction"], "answer": p["word"],
                      "display_answer": r["display"], "clue": r["clue"], "id": r["id"], "source": r["id"],
                      "length": p["length"]})
    res["clues"] = clues
    return res


def write_grid_files(res, outdir):
    """Write grid.json, grid.txt and clues.csv (Across then Down) into outdir."""
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "grid.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    with open(os.path.join(outdir, "grid.txt"), "w", encoding="utf-8") as f:
        f.write(preview(res) + "\n")
    rows = sorted(res["clues"], key=lambda c: (c["direction"] != "across", c["number"]))
    with open(os.path.join(outdir, "clues.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "direction", "clue", "answer", "id"])
        for c in rows:
            w.writerow([c["number"], c["direction"], c["clue"], c["display_answer"], c["id"]])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster generate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--column", default="grid", help="column holding the grid words (default: grid, as written by `pool`)")
    ap.add_argument("--clue-column", default=None, help="optional; shown in the text preview")
    ap.add_argument("--max-width", type=int, default=None, help="window width in cells (default 25; auto with --all)")
    ap.add_argument("--max-height", type=int, default=None, help="window height in cells (default 25; auto with --all)")
    ap.add_argument("--attempts", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=15)
    ap.add_argument("--required", default="", help="comma-separated words that MUST be placed")
    ap.add_argument("--subset", type=int, default=0, help="random subset size of the word list (testing)")
    ap.add_argument("--all", action="store_true", help="every word must be placed; smallest complete layout wins")
    ap.add_argument("--workers", type=int, default=1, help="parallel processes for --all (result does not depend on it)")
    ap.add_argument("--noise", type=float, default=6.0, help="--all: randomness of the longest-first ordering")
    ap.add_argument("--passes", type=int, default=None, help="placement passes per attempt (default 3; 6 with --all)")
    ap.add_argument("--aspect", type=float, default=0.8, help="--all, auto window: width/height ratio (default 0.8)")
    ap.add_argument("--grow-tries", type=int, default=6, help="--all, auto window: times to enlarge the window by 15%% when no complete layout is found")
    ap.add_argument("--out-json")
    ap.add_argument("--out-txt")
    a = ap.parse_args(argv)

    words = load_words(a.csv, a.column, a.min_len, a.max_len)
    if a.subset and a.subset < len(words):
        words = random.Random(a.seed).sample(words, a.subset)
    req = [w.strip().upper() for w in a.required.split(",") if w.strip()]
    clues = None
    if a.clue_column:
        clues = {}
        with open(a.csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                clues.setdefault((row.get(a.column) or "").strip().upper(), row.get(a.clue_column, ""))
    if a.all:
        b, stats = generate_all(words, a.max_width, a.max_height, a.attempts, a.seed, a.noise, a.passes or 6,
                                a.workers, a.aspect, a.grow_tries, log=lambda m: print(m, file=sys.stderr))
        if b is None:
            print("ERROR: no complete layout found; raise --attempts, --max-width/--max-height or --grow-tries",
                  file=sys.stderr)
            return 2
        unplaced = []
    else:
        b, unplaced, stats = generate(words, req, a.max_width or 25, a.max_height or 25, a.attempts, a.seed, a.passes or 3)
    res = to_result(b, unplaced, stats, clues)
    txt = preview(res)
    if a.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(a.out_json)), exist_ok=True)
        with open(a.out_json, "w") as f:
            json.dump(res, f, indent=1)
    if a.out_txt:
        os.makedirs(os.path.dirname(os.path.abspath(a.out_txt)), exist_ok=True)
        with open(a.out_txt, "w") as f:
            f.write(txt + "\n")
    print(txt)
    if stats["required_missing"]:
        print("WARNING: required words not placed:", stats["required_missing"], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
