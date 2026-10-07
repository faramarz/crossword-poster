#!/usr/bin/env python3
"""Checks for rendered outputs (everything under OUTROOT written by `build` / `render`):
page sizes (poster = trim + 0.125 in bleed on every side, trim, key 11x17, letter pages), fonts embedded (none Type 3),
only black / white / the chosen fill colours in the vector content, thinnest stroke, no ink inside the outer margin,
every clue appears exactly once as one unbroken block, title and byline present, every PNG neutral grey (R=G=B),
DOM checks recorded in fit.json, and (unless --no-crops) per-cell stroke checks via crops.py.
Prints a PASS/FAIL report; exit status 1 on any failure.

Usage:
  python -m crossword_poster verify out --title "My Crossword" [--byline "..."] [--sizes 24x36,18x24]
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

from .common import BLEED, parse_size
from .render_news import DEFAULT_BYLINE, DEFAULT_TITLE, size_config

VARIANTS = ("A_black", "B_spot", "C_grey")


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(round(int(h[i:i + 2], 16) / 255, 3) for i in (0, 2, 4))


def verify(outroot, title=DEFAULT_TITLE, byline=DEFAULT_BYLINE, sizes=None, grid=None, block_fill=None,
           grey_fill="#a3a3a3", crops=True):
    import numpy as np
    import pymupdf as fitz
    from PIL import Image

    grid = grid or os.path.join(outroot, "grid.json")
    g = json.load(open(grid, encoding="utf-8"))
    clues = g["clues"]
    nlet = sum(1 for r in g["grid"] for c in r if c)
    if sizes is None:
        sizes = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(outroot, "*x*", "fit.json")))
    fail = []

    def chk(c, msg):
        print(("PASS " if c else "FAIL ") + msg)
        if not c:
            fail.append(msg)

    def norm(s):
        return re.sub(r"\s+", " ", s).strip()

    def cluetext(c):
        t = norm(c["clue"])
        if not re.search(r"\(\d+(,\d+)*\)\s*$", t):
            t += f" ({len(c['answer'])})"
        return t

    want = {(c["direction"], c["number"]): cluetext(c) for c in clues}
    BLACK, WHITE = (0, 0, 0), (1, 1, 1)
    fill_dark = hex_rgb(block_fill) if block_fill else BLACK
    fill_grey = hex_rgb(block_fill or grey_fill)
    chk(bool(sizes), f"found rendered sizes under {outroot}: {', '.join(sizes) or 'none'}")

    def fonts_ok(pdf, tag):
        pg = fitz.open(pdf)[0]
        fl = pg.get_fonts(full=False)
        emb = [f for f in fl if f[1] != "n/a"]
        chk(bool(fl) and len(emb) == len(fl) and not any(f[2] == "Type3" for f in fl),
            f"{tag}: {len(fl)} fonts, all embedded, none Type 3 ({', '.join(sorted({f[3].split('+')[-1] for f in fl}))})")

    def stroke_cols(pg):
        cols, minw = set(), 99
        for dr in pg.get_drawings():
            for k in ("color", "fill"):
                v = dr.get(k)
                if v is not None:
                    cols.add(tuple(round(x, 3) for x in v))
            if dr.get("color") is not None and dr.get("width"):
                minw = min(minw, dr["width"])
        return cols, minw

    done_variants = set()
    for size in sizes:
        tw, th = parse_size(size)
        mg = size_config(size)["margin"]
        for var in VARIANTS:
            d = f"{outroot}/{size}/{var}"
            if not os.path.isdir(d):
                continue
            done_variants.add(var)
            for name, (ew, eh) in (("poster.pdf", (tw + 2 * BLEED, th + 2 * BLEED)), ("poster_trim.pdf", (tw, th))):
                doc = fitz.open(f"{d}/{name}")
                pg = doc[0]
                chk(len(doc) == 1 and abs(pg.rect.width / 72 - ew) < .01 and abs(pg.rect.height / 72 - eh) < .01,
                    f"{size}/{var}/{name}: 1 page, {pg.rect.width / 72:.3f} x {pg.rect.height / 72:.3f} in (expect {ew:g} x {eh:g})")
            fonts_ok(f"{d}/poster.pdf", f"{size}/{var}")
            pg = fitz.open(f"{d}/poster_trim.pdf")[0]
            cols, minw = stroke_cols(pg)
            spans = [s for b in pg.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
            tcols = {s["color"] for s in spans}
            ok_cols = {BLACK, WHITE, fill_grey if var == "C_grey" else fill_dark}
            chk(cols <= ok_cols and tcols <= ({0} if var != "B_spot" else {0, 16777215}),
                f"{size}/{var}: only black, white and the block fill in vector content (draw {sorted(cols)}, text {sorted(tcols)})")
            chk(minw >= .5, f"{size}/{var}: thinnest stroke {minw:.2f} pt (>= 0.5)")
            pix = pg.get_pixmap(dpi=50, colorspace=fitz.csGRAY)
            im = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            m = int((mg - .02) * 50)
            ink = im < 250
            edge = ink[:m].any() or ink[-m:].any() or ink[:, :m].any() or ink[:, -m:].any()
            ys, xs = np.where(ink)
            chk(not edge, f"{size}/{var}: no ink in the outer {mg:g} in margin (ink bbox x {xs.min() / 50:.2f}-{xs.max() / 50:.2f}, y {ys.min() / 50:.2f}-{ys.max() / 50:.2f} in)")
            sq = lambda x: re.sub(r"\s+", "", x)
            blocks = [sq(b[4]) for b in pg.get_text("blocks")]
            hit = {k: sum(b.count(sq(f"{k[1]} {t}")) for b in blocks) for k, t in want.items()}
            missing = [k for k, v in hit.items() if v == 0]
            dup = [k for k, v in hit.items() if v > 1]
            chk(not missing and not dup, f"{size}/{var}: all {len(want)} clues appear exactly once, each unbroken inside one column block (missing {missing[:5]}, duplicated {dup[:5]})")
            sz = collections.Counter(round(s["size"], 1) for s in spans if len(s["text"]) > 12 and s["size"] < 30)
            print(f"      clue-ish font sizes: {sz.most_common(3)}")
            t = norm(pg.get_text().replace("\n", " "))
            chk(title.upper() in t.upper() and byline in t, f"{size}/{var}: title and byline text present")
        d = f"{outroot}/{size}"
        if os.path.exists(f"{d}/key.pdf"):
            k = fitz.open(f"{d}/key.pdf")
            chk(len(k) == 1 and abs(k[0].rect.width - 792) < .5 and abs(k[0].rect.height - 1224) < .5, f"{size}/key.pdf 11x17, 1 page")
            fonts_ok(f"{d}/key.pdf", f"{size}/key.pdf")
            ks = k[0].get_text("words")
            lett = sum(1 for w in ks if len(w[4]) == 1 and w[4].isalpha())
            chk(lett >= nlet, f"{size}/key.pdf has {lett} single-letter answers (grid has {nlet} letter cells)")
            cols, mw = stroke_cols(k[0])
            chk(cols <= {BLACK, WHITE, fill_grey} and mw >= .5, f"{size}/key.pdf: colours {sorted(cols)}, thinnest stroke {mw:.2f} pt (>= 0.5)")
        if os.path.exists(f"{d}/actual_size_check_letter.pdf"):
            a = fitz.open(f"{d}/actual_size_check_letter.pdf")
            chk(len(a) == 1 and abs(a[0].rect.width - 612) < 1 and abs(a[0].rect.height - 792) < 1, f"{size}/actual_size_check_letter.pdf letter, 1 page")
    sol = f"{outroot}/solution_letter.pdf"
    if os.path.exists(sol):
        s = fitz.open(sol)
        chk(len(s) == 1 and sorted([round(s[0].rect.width), round(s[0].rect.height)]) == [612, 792], "solution_letter.pdf letter size, 1 page")
        sl = [w for w in s[0].get_text("words") if len(w[4]) == 1 and w[4].isalpha()]
        chk(len(sl) >= nlet, f"solution has {len(sl)} letters")
        chk("THE SOLUTION" in s[0].get_text().upper().replace("\n", " "), "solution title text present")
        cols, mw = stroke_cols(s[0])
        chk(cols <= {BLACK, WHITE, fill_grey} and mw >= .5, f"solution_letter.pdf: colours {sorted(cols)}, thinnest stroke {mw:.2f} pt (>= 0.5)")
    for p in glob.glob(outroot + "/**/*.png", recursive=True):
        if "/.build/" in p or "/checks/" in p:
            continue
        im = Image.open(p)
        a = np.asarray(im.convert("RGB")).astype(int)
        ok = (a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all()
        chk(ok or bool(block_fill), f"{os.path.relpath(p, outroot)}: {im.size[0]}px wide, every pixel R=G=B" + ("" if ok else " (colour fill requested)"))
    for f in glob.glob(outroot + "/*/fit.json"):
        j = json.load(open(f))
        for v, r in j.get("verify", {}).items():
            chk(r["ok"] and not r["problems"], f"{os.path.relpath(f, outroot)} DOM check {v}: overflow-free, no heading at column foot, no clue over grid, header fits; clues={r['nClues']}")
    rc = 0
    if crops and sizes:
        from .crops import run_crops
        rc = run_crops(outroot, grid, sizes, sorted(done_variants, key=VARIANTS.index))
    print("\nFAILED:" if fail else "\nALL CHECKS PASSED", fail if fail else "")
    return 1 if (fail or rc) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outroot", help="the --out / --outroot directory of a build")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--byline", "--subtitle", dest="byline", default=DEFAULT_BYLINE)
    ap.add_argument("--sizes", default=None, help="comma list (default: every size directory found)")
    ap.add_argument("--grid", default=None, help="grid.json (default OUTROOT/grid.json)")
    ap.add_argument("--block-fill", default=None, help="the --block-fill used for rendering, if any")
    ap.add_argument("--grey-fill", default="#a3a3a3")
    ap.add_argument("--no-crops", action="store_true", help="skip the per-cell stroke check / crop images (crops.py)")
    a = ap.parse_args(argv)
    return verify(a.outroot, a.title, a.byline, a.sizes.split(",") if a.sizes else None, a.grid, a.block_fill,
                  a.grey_fill, not a.no_crops)


if __name__ == "__main__":
    sys.exit(main())
