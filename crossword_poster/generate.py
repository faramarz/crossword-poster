"""Freeform ("loose", barred-free) crossword generator. Standard library only.

Greedy placement with randomised restarts. Rules enforced:
  * every word crosses at least one already-placed word (the grid is connected)
  * a letter cell is shared by at most one Across and one Down word
  * no two words touch side by side (no illegal 2-letter adjacencies)
  * a word's start and end are bounded by an empty cell or the edge of the window
  * no word is placed twice
Score = words_placed * 100 + 40 * density + 10 * crossings_per_word
(density = letter cells / bounding-box area, so compact layouts with many words win).

Modes
  default   best-of-N layout that places as many words as it can; --required words must all be placed.
  --all     EVERY word must be placed. Many attempts are tried (in parallel) and the complete layout with the
            smallest bounding box (nudged toward --aspect) wins. Without --max-width/--max-height the window is estimated from the letter
            count and grown automatically (--grow-tries) until a complete layout is found.

Examples
  crossword-poster generate --csv out/pool.csv --all --attempts 2000 --seed 1 --out-json out/raw.json
  crossword-poster generate --csv words.csv --column answer --max-width 25 --max-height 25 --required PLANET,RIVER

The input CSV is only read, never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .errors import UserError

ACROSS, DOWN = 0, 1
DR = (0, 1)  # row step for ACROSS, DOWN
DC = (1, 0)  # column step

Log = Optional[Callable[[str], None]]


# ----------------------------------------------------------------- loading
def load_words(path: str, column: str = "grid", min_len: int = 2, max_len: int = 20) -> list[str]:
    """Unique, upper-case, alphabetic words from one CSV column with ``min_len <= len <= max_len``."""
    seen, out = set(), []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            if column not in (rd.fieldnames or []):
                raise UserError(
                    f"{path} has no '{column}' column.",
                    f"columns found: {', '.join(rd.fieldnames or [])}; use --column",
                )
            for row in rd:
                w = (row.get(column) or "").strip().upper()
                if w.isalpha() and w.isascii() and min_len <= len(w) <= max_len and w not in seen:
                    seen.add(w)
                    out.append(w)
    except FileNotFoundError:
        raise UserError(f"File not found: {path}") from None
    return out


# ------------------------------------------------------------------- board
class Board:
    """Sparse board bounded by a W x H window anchored at the first word."""

    def __init__(self, width: int, height: int) -> None:
        self.W, self.H = width, height
        self.cells: dict = {}  # (r, c) -> letter
        self.dirs: dict = {}  # (r, c) -> bitmask of directions using the cell
        self.by_letter: dict = {}  # letter -> list of (r, c)
        self.placed: list = []  # (word, r, c, direction)
        self.rmin = self.cmin = 10**6
        self.rmax = self.cmax = -(10**6)
        self.crossings = 0

    def bbox_after(self, r: int, c: int, d: int, n: int) -> tuple:
        """Bounding box (rmin, rmax, cmin, cmax) if an ``n``-letter word were placed at (r, c) going ``d``."""
        r2, c2 = r + DR[d] * (n - 1), c + DC[d] * (n - 1)
        return (min(self.rmin, r), max(self.rmax, r2), min(self.cmin, c), max(self.cmax, c2))

    def can_place(self, word: str, r: int, c: int, d: int) -> int:
        """Number of crossings if the placement is legal, else -1."""
        n = len(word)
        dr, dc = DR[d], DC[d]
        if self.cells:
            r0, r1, c0, c1 = self.bbox_after(r, c, d, n)
            if r1 - r0 + 1 > self.H or c1 - c0 + 1 > self.W:
                return -1
        if (r - dr, c - dc) in self.cells or (r + dr * n, c + dc * n) in self.cells:
            return -1  # the cells just before and after the word must be empty
        cross = 0
        pr, pc = dc, dr  # perpendicular step
        for i in range(n):
            rr, cc = r + dr * i, c + dc * i
            ch = self.cells.get((rr, cc))
            if ch is not None:
                if ch != word[i] or (self.dirs[(rr, cc)] >> d) & 1:
                    return -1  # letter mismatch, or collinear overlap
                cross += 1
            elif (rr + pr, cc + pc) in self.cells or (rr - pr, cc - pc) in self.cells:
                return -1  # a new cell may not touch another word sideways
        return cross

    def place(self, word: str, r: int, c: int, d: int, cross: int) -> None:
        """Put a word on the board (the placement must already be known to be legal)."""
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

    def candidates(self, word: str):
        """Yield (r, c, d, crossings) for every legal crossing placement of ``word``."""
        seen = set()
        for i, ch in enumerate(word):
            for r, c in self.by_letter.get(ch, ()):
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

    def area(self) -> int:
        """Area of the bounding box in cells."""
        return (self.rmax - self.rmin + 1) * (self.cmax - self.cmin + 1)

    def density(self) -> float:
        """Letter cells divided by bounding-box area."""
        return len(self.cells) / self.area() if self.cells else 0.0

    def score(self) -> float:
        """Layout score used to pick the best of many attempts (higher is better)."""
        n = len(self.placed)
        return n * 100 + 40 * self.density() + 10 * (self.crossings / max(n, 1))


# --------------------------------------------------------------- one attempt
def _attempt(words, W, H, seed, k, noise, passes, required=()):
    """One randomised build. Attempt ``k`` of a run is fully determined by ``(seed, k)``. Returns (Board, leftover)."""
    rng = random.Random(f"{seed}:{k}")
    req = list(required)
    rest = sorted((w for w in words if w not in req), key=lambda w: -(len(w) + rng.random() * noise))
    queue = req + rest
    b = Board(W, H)
    first = queue.pop(0)
    b.place(first, H // 2, max(0, (W - len(first)) // 2), ACROSS, 0)
    for _ in range(passes):
        left, progress = [], False
        for w in queue:
            best, best_key = None, None
            for r, c, d, x in b.candidates(w):
                r0, r1, c0, c1 = b.bbox_after(r, c, d, len(w))
                key = (x, -((r1 - r0 + 1) * (c1 - c0 + 1)), rng.random())  # many crossings, small box, random tie-break
                if best_key is None or key > best_key:
                    best, best_key = (r, c, d, x), key
            if best:
                b.place(w, *best[:3], best[3])
                progress = True
            else:
                left.append(w)
        queue = left
        if not queue or not progress:
            break
    return b, queue


def _stats(b: Board, offered: int, attempts: int, seed: int, t0: float, **extra) -> dict:
    out = {
        "words_placed": len(b.placed),
        "words_offered": offered,
        "bbox_rows": b.rmax - b.rmin + 1,
        "bbox_cols": b.cmax - b.cmin + 1,
        "letter_cells": len(b.cells),
        "density": round(b.density(), 3),
        "crossings": sum(len(p[0]) for p in b.placed) - len(b.cells),
        "attempts": attempts,
        "seed": seed,
        "seconds": round(time.time() - t0, 2),
    }
    out.update(extra)
    return out


def _past(deadline: Optional[float]) -> bool:
    """True once the wall-clock ``deadline`` (a ``time.time()`` value) has passed."""
    return deadline is not None and time.time() > deadline


def generate(words, required=(), W=25, H=25, attempts=100, seed=0, passes=3, noise=6.0, deadline=None):
    """Best of ``attempts`` randomised builds, placing as many words as possible. Returns (Board, unplaced, stats).

    Stops early once ``deadline`` has passed (at least one attempt always runs).
    """
    req = [w.upper() for w in required]
    pool = list(dict.fromkeys(req + [w for w in words if w not in req]))
    if not pool:
        raise UserError("There are no words to place.")
    best, best_score = None, -(10**9)
    t0 = time.time()
    for k in range(attempts):
        if k and _past(deadline):
            break
        b, _ = _attempt(pool, W, H, seed, k, noise, passes, req)
        have = {p[0] for p in b.placed}
        s = b.score() + (0 if all(r in have for r in req) else -(10**6))  # required words must all be present
        if s > best_score:
            best, best_score = b, s
    placed = {p[0] for p in best.placed}
    unplaced = [w for w in pool if w not in placed]
    return (
        best,
        unplaced,
        _stats(best, len(pool), attempts, seed, t0, required_missing=[r for r in req if r not in placed]),
    )


# ------------------------------------------------- all-words-required search
def layout_cost(b: Board, aspect: float) -> float:
    """Cost of a complete layout (lower is better): its area, inflated the further its shape is from ``aspect``."""
    ratio = (b.cmax - b.cmin + 1) / (b.rmax - b.rmin + 1)
    return b.area() * (1 + abs(math.log(ratio / aspect)))


def _run_chunk(args):
    words, W, H, seed, ks, noise, passes, aspect, deadline = args
    best, ok = None, 0
    for k in ks:
        if _past(deadline):
            break
        b, left = _attempt(words, W, H, seed, k, noise, passes)
        if left:
            continue
        ok += 1
        key = (-layout_cost(b, aspect), b.crossings, -k)
        if best is None or key > best[0]:
            best = (key, list(b.placed), k)
    return best, ok


def auto_bounds(words, aspect: float = 1.0, slack: float = 1.3) -> tuple:
    """Estimate a (width, height) search window in cells from the letter count: area ~ letters / 0.4 x slack."""
    letters = sum(len(w) for w in words)
    area = letters / 0.4 * slack
    longest = max(len(x) for x in words) + 2
    w = max(int(math.ceil(math.sqrt(area * aspect))), longest)
    h = max(int(math.ceil(area / w)), longest)
    return w, h


def _map_chunks(chunks: list) -> list:
    """Run chunks in a process pool when there is more than one, falling back to serial if a pool cannot start."""
    if len(chunks) > 1:
        try:
            from multiprocessing import Pool

            with Pool(len(chunks)) as pool:
                return pool.map(_run_chunk, chunks)
        except (OSError, ImportError, RuntimeError):
            pass
    return [_run_chunk(c) for c in chunks]


PROGRESS_EVERY = 5.0  # seconds between "still searching" lines


def generate_all(
    words,
    W=None,
    H=None,
    attempts: int = 1000,
    seed: int = 0,
    noise: float = 6.0,
    passes: int = 6,
    workers: int = 1,
    aspect: float = 1.0,
    grow_tries: int = 6,
    grow: float = 1.15,
    log: Log = None,
    deadline: Optional[float] = None,
):
    """Place EVERY word. Returns (Board | None, stats).

    Of all complete layouts found, the one with the lowest :func:`layout_cost` wins (small and close to ``aspect``).

    If W and H are both omitted they are estimated and grown by ``grow`` after each failed round (up to
    ``grow_tries`` times); a bound given explicitly is never grown (an omitted one is estimated).
    Deterministic for a given (words, bounds, attempts, seed), whatever ``workers`` is, as long as the search is not
    cut short.

    ``deadline`` (a ``time.time()`` value) stops the search early, and ``stats["time_limit_hit"]`` is then True.
    Attempts run in a few batches so that progress can be logged every few seconds; the batching does not change
    which layout wins.
    """
    words = list(dict.fromkeys(words))
    if not words:
        raise UserError("There are no words to place.")
    auto = W is None and H is None  # a bound given by the user is never grown
    if W is None or H is None:
        aw, ah = auto_bounds(words, aspect)
        W, H = W or aw, H or ah
    longest = max(len(w) for w in words)
    t0 = time.time()
    rounds = (grow_tries + 1) if auto else 1
    timed_out = False
    for rnd in range(rounds):
        W, H = max(W, longest), max(H, longest)
        n = max(1, min(workers, attempts))
        batch = max(n * 8, -(-attempts // 5))
        done, ok, found, last_log = 0, 0, [], time.time()
        while done < attempts and not timed_out:
            ks = list(range(done, min(attempts, done + batch)))
            res = _map_chunks([(words, W, H, seed, ks[i::n], noise, passes, aspect, deadline) for i in range(n)])
            ok += sum(r[1] for r in res)
            found += [r[0] for r in res if r[0]]
            done += len(ks)
            timed_out = _past(deadline)
            if log and not timed_out and done < attempts and time.time() - last_log >= PROGRESS_EVERY:
                last_log = time.time()
                log(f"  still searching ({W}x{H} window): {done} of {attempts} layouts tried, {ok} complete, "
                    f"{time.time() - t0:.0f} s so far")  # fmt: skip
        if log:
            log(f"  window {W}x{H}: {ok} complete layouts in {done} attempts")
        if found:
            _, placed, k = max(found, key=lambda x: x[0])
            b = Board(W, H)
            for w, r, c, d in placed:
                b.place(w, r, c, d, 0)
            stats = _stats(
                b,
                len(words),
                attempts,
                seed,
                t0,
                complete_layouts=ok,
                best_attempt=k,
                bound=[W, H],
                required_missing=[],
            )
            if timed_out:
                stats["time_limit_hit"] = True
            return b, stats
        if timed_out:
            break
        if rnd < rounds - 1:
            W, H = int(math.ceil(W * grow)), int(math.ceil(H * grow))
    stats = {"words_offered": len(words), "attempts": attempts, "seed": seed, "bound": [W, H],
             "seconds": round(time.time() - t0, 2), "required_missing": words}  # fmt: skip
    if timed_out:
        stats["time_limit_hit"] = True
    return None, stats


# -------------------------------------------------------- resilient solver
@dataclass
class Solution:
    """Outcome of :func:`solve`: the board, which words were left out (and why) and run statistics."""

    board: Board
    left_out: dict = field(default_factory=dict)  # word -> plain-language reason
    stats: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """True when every offered word was placed."""
        return not self.left_out


def _isolated(words: list[str]) -> list[str]:
    """Words that share no letter with any other word (they can never cross anything)."""
    out = []
    for w in words:
        others = set("".join(o for o in words if o is not w))
        if not set(w) & others:
            out.append(w)
    return out


def solve(
    words: list[str],
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    attempts: int = 1000,
    seed: int = 1,
    noise: float = 6.0,
    passes: int = 6,
    workers: int = 1,
    aspect: float = 1.0,
    grow_tries: int = 6,
    log: Log = None,
    time_limit: Optional[float] = None,
) -> Solution:
    """Find a grid for ``words``, trying hard to place every one and degrading gracefully.

    1. ``attempts`` randomised layouts in an estimated window, enlarging the window up to ``grow_tries`` times.
    2. If no layout holds every word: three times as many attempts in a larger window (explicit bounds stay fixed).
    3. If that fails too: the best partial layout; the words that did not fit are reported in ``Solution.left_out``.
    Words that share no letter with any other word are left out immediately, since they can never cross anything.
    The result depends only on the inputs and ``seed``, not on ``workers`` or timing, unless ``time_limit`` (seconds
    of wall-clock time, None for no limit) is reached: the search then stops, the best layout so far is used and
    ``stats["time_limit_hit"]`` is True.
    """
    deadline = time.time() + time_limit if time_limit else None
    words = list(dict.fromkeys(words))
    left_out = dict.fromkeys(
        _isolated(words), "shares no letters with the other answers, so it cannot cross any of them"
    )
    usable = [w for w in words if w not in left_out]
    if len(usable) < 2:
        raise UserError(
            "Not enough words can be crossed to make a crossword.", "check that the answers share some letters"
        )
    log = log or (lambda _m: None)
    explicit = max_width is not None or max_height is not None
    common = dict(noise=noise, passes=passes, workers=workers, aspect=aspect, log=log, deadline=deadline)
    stats: dict = {}
    b = None
    if not left_out:
        b, stats = generate_all(usable, max_width, max_height, attempts, seed, grow_tries=grow_tries, **common)
    if b is None and not left_out and not stats.get("time_limit_hit"):
        log("  no complete layout yet; trying again with more attempts and a larger window")
        bw, bh = stats.get("bound") or auto_bounds(usable, aspect)
        if not explicit:
            bw, bh = int(math.ceil(bw * 1.15)), int(math.ceil(bh * 1.15))
        b, stats = generate_all(usable, bw, bh, attempts * 3, seed, grow_tries=0 if explicit else 3, **common)
    if b is not None:
        return Solution(b, left_out, stats)
    hit = bool(stats.get("time_limit_hit"))
    bw, bh = stats.get("bound") or (
        max_width or auto_bounds(usable, aspect)[0],
        max_height or auto_bounds(usable, aspect)[1],
    )
    if left_out:
        log(f"  {len(left_out)} word(s) cannot cross anything; placing the rest")
        b, stats = generate_all(usable, max_width, max_height, attempts, seed, grow_tries=grow_tries, **common)
        if b is not None:
            return Solution(b, left_out, stats)
        hit = hit or bool(stats.get("time_limit_hit"))
        bw, bh = stats["bound"]
    if hit:
        log(f"  the time limit ({time_limit:g} s) ran out before every answer was placed; using the best layout found")
    log(f"  placing as many words as possible in a {bw}x{bh} window")
    # the fallback gets a little extra time so that a limit that ran out still ends with a layout
    b, unplaced, stats = generate(
        usable, (), bw, bh, attempts, seed, passes, noise, deadline=time.time() + 5 if hit else deadline
    )
    stats["bound"] = [bw, bh]
    if hit:
        stats["time_limit_hit"] = True
    for w in unplaced:
        left_out[w] = "could not be fitted into the grid"
    return Solution(b, left_out, stats)


# ------------------------------------------------------------------- output
def to_result(b: Board, unplaced: list, stats: dict, clues: Optional[dict] = None) -> dict:
    """Crop the board to its bounding box, number the cells and return a JSON-able dict."""
    R, C = b.rmax - b.rmin + 1, b.cmax - b.cmin + 1
    grid = [["" for _ in range(C)] for _ in range(R)]
    for (r, c), ch in b.cells.items():
        grid[r - b.rmin][c - b.cmin] = ch
    starts = {}
    for w, r, c, d in b.placed:
        starts[(r - b.rmin, c - b.cmin, d)] = w
    number, nxt = {}, 1
    for r in range(R):
        for c in range(C):
            if (r, c, ACROSS) in starts or (r, c, DOWN) in starts:
                number[(r, c)] = nxt
                nxt += 1
    placements = []
    for (r, c, d), w in sorted(starts.items(), key=lambda kv: (number[kv[0][:2]], kv[0][2])):
        p = {
            "number": number[(r, c)],
            "word": w,
            "row": r,
            "col": c,
            "direction": "across" if d == ACROSS else "down",
            "length": len(w),
        }
        if clues and w in clues:
            p["clue"] = clues[w]
        placements.append(p)
    return {"rows": R, "cols": C, "grid": grid, "placements": placements, "unplaced": unplaced, "stats": stats}


def preview(res: dict) -> str:
    """A plain-text picture of the grid followed by the Across and Down lists."""
    g = res["grid"]
    lines = [
        f"{res['rows']} rows x {res['cols']} cols | words {res['stats']['words_placed']} | density {res['stats']['density']}",
        "",
    ]
    lines.append("    " + "".join(f"{c % 10}" for c in range(res["cols"])))
    for r, row in enumerate(g):
        lines.append(f"{r:>3} " + "".join(ch if ch else "." for ch in row))
    for dname in ("across", "down"):
        lines += ["", dname.upper()]
        for p in res["placements"]:
            if p["direction"] == dname:
                lines.append(
                    f"  {p['number']:>3}. {p['word']} ({p['length']})" + (f"  {p['clue']}" if "clue" in p else "")
                )
    if res["unplaced"]:
        lines += ["", f"UNPLACED ({len(res['unplaced'])}): " + ", ".join(res["unplaced"])]
    return "\n".join(lines)


def attach_pool(res: dict, pool_rows: list[dict]) -> dict:
    """Attach clues from pool rows (dicts with grid, clue, display, id) to a :func:`to_result` dict, in place.

    Adds ``res['clues']`` (one per placement) and clue/answer/source fields on each placement.
    """
    pool = {r["grid"]: r for r in pool_rows}
    clues = []
    for p in res["placements"]:
        r = pool[p["word"]]
        p["answer"], p["clue"], p["source"] = r["display"], r["clue"], r["id"]
        clues.append({
            "number": p["number"], "direction": p["direction"], "answer": p["word"], "display_answer": r["display"],
            "clue": r["clue"], "id": r["id"], "source": r["id"], "length": p["length"],
        })  # fmt: skip
    res["clues"] = clues
    return res


def write_grid_files(res: dict, outdir: str) -> None:
    """Write grid.json, grid.txt and clues.csv (Across then Down) into ``outdir``."""
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


def _write(path: Optional[str], text: str) -> None:
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``generate``."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster generate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--csv", required=True, help="CSV with one word per row (the pool.csv written by `pool` works)")
    ap.add_argument("--column", default="grid", help="column holding the grid words (default: %(default)s)")
    ap.add_argument("--clue-column", default=None, help="optional; shown in the text preview")
    ap.add_argument(
        "--max-width", type=int, default=None, help="window width in cells (default 25; estimated with --all)"
    )
    ap.add_argument(
        "--max-height", type=int, default=None, help="window height in cells (default 25; estimated with --all)"
    )
    ap.add_argument("--attempts", type=int, default=100, help="randomised layouts to try (default %(default)s)")
    ap.add_argument("--seed", type=int, default=0, help="random seed; the same seed gives the same grid")
    ap.add_argument("--min-len", type=int, default=2)
    ap.add_argument("--max-len", type=int, default=20)
    ap.add_argument("--required", default="", help="comma-separated words that MUST be placed")
    ap.add_argument("--all", action="store_true", help="every word must be placed; smallest complete layout wins")
    ap.add_argument(
        "--workers", type=int, default=1, help="parallel processes for --all (the result does not depend on it)"
    )
    ap.add_argument("--noise", type=float, default=6.0, help="randomness of the longest-first ordering")
    ap.add_argument("--passes", type=int, default=None, help="placement passes per attempt (default 3; 6 with --all)")
    ap.add_argument("--aspect", type=float, default=1.0, help="--all, estimated window: width/height ratio")
    ap.add_argument(
        "--grow-tries",
        type=int,
        default=6,
        help="--all, estimated window: times to enlarge it by 15%% when nothing fits",
    )
    ap.add_argument(
        "--time-limit",
        type=float,
        default=0,
        metavar="SECONDS",
        help="stop searching after this many seconds (default: no limit)",
    )
    ap.add_argument("--out-json", help="write the grid as JSON here")
    ap.add_argument("--out-txt", help="write the text preview here")
    a = ap.parse_args(argv)

    words = load_words(a.csv, a.column, a.min_len, a.max_len)
    if len(words) < 2:
        raise UserError(
            f"Only {len(words)} usable word(s) in {a.csv}.", "run `crossword-poster pool` first to prepare the words"
        )
    req = [w.strip().upper() for w in a.required.split(",") if w.strip()]
    clues = None
    if a.clue_column:
        clues = {}
        with open(a.csv, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                clues.setdefault((row.get(a.column) or "").strip().upper(), row.get(a.clue_column, ""))
    deadline = time.time() + a.time_limit if a.time_limit > 0 else None
    if a.all:
        b, stats = generate_all(words, a.max_width, a.max_height, a.attempts, a.seed, a.noise, a.passes or 6,
                                a.workers, a.aspect, a.grow_tries, log=lambda m: print(m, file=sys.stderr),
                                deadline=deadline)  # fmt: skip
        if b is None:
            raise UserError(
                "No layout places every word"
                + (f" within {a.time_limit:g} s." if stats.get("time_limit_hit") else "."),
                "use fewer words (30 to 60 is ideal), or raise --time-limit, --attempts, --max-width/--max-height "
                "or --grow-tries, or drop --all",
            )
        unplaced = []
    else:
        b, unplaced, stats = generate(
            words,
            req,
            a.max_width or 25,
            a.max_height or 25,
            a.attempts,
            a.seed,
            a.passes or 3,
            a.noise,
            deadline=deadline,
        )
    res = to_result(b, unplaced, stats, clues)
    txt = preview(res)
    _write(a.out_json, json.dumps(res, indent=1))
    _write(a.out_txt, txt + "\n")
    print(txt)
    if stats["required_missing"]:
        print("WARNING: required words not placed:", stats["required_missing"], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
