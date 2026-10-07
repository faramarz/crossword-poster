#!/usr/bin/env python3
"""Rebuild the README/guide visuals in docs/images/ from the fictional birthday sample.

Everything here is made from ``examples/sample_birthday.csv`` ("Alex's 50th", all made-up clues).
No real data is used.

Files written (to ``docs/images/`` unless ``--images`` says otherwise):

    how-it-works.svg    hand-written flow diagram: clues -> grid -> checks -> layout -> print files
    gallery-styles.png  the grey, black and icons styles side by side at the same size
    gallery-sizes.png   18x24, 24x36 and 36x48 drawn to scale relative to each other
    demo.gif            animated terminal: ``crossword-poster sample --out my-first-poster`` then ``ls``

Usage (from the repository root):

    python scripts/build_visuals.py                    # build everything
    python scripts/build_visuals.py svg styles         # only some of: svg styles sizes gif
    python scripts/build_visuals.py --work /tmp/vis    # keep the scratch builds somewhere else
    python scripts/build_visuals.py --images docs/images

Needs the ``crossword-poster`` command (or ``python -m crossword_poster``) with its Chromium installed, plus Pillow.
The PNGs and the GIF call the command line tool, so they take about a minute in total. The SVG needs nothing.
A scratch folder (default ``out/visuals-build``) holds the intermediate posters; it is safe to delete.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import textwrap
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLUES = ROOT / "examples" / "sample_birthday.csv"
TITLE = "Alex's 50th"
SUBTITLE = "Clues from the people who love you"
FAST = ["--no-key", "--no-solution", "--no-actual-size", "--no-verify", "--no-crops"]

if shutil.which("crossword-poster"):
    CLI = ["crossword-poster"]
else:
    CLI = [sys.executable, "-m", "crossword_poster"]


def run(args, cwd=None, quiet=True):
    """Run the command line tool and return its combined output; stop with a message if it fails."""
    res = subprocess.run(
        CLI + list(args),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "NO_COLOR": "1", "COLUMNS": "100"},
    )
    if res.returncode != 0:
        sys.exit(f"crossword-poster {' '.join(args)} failed ({res.returncode}):\n{res.stdout}")
    return res.stdout


# ---------------------------------------------------------------------------------------------------- font helpers
def find_font(names, size):
    from PIL import ImageFont

    for p in names:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


SANS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
SANS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consola.ttf",
]
MONO_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consolab.ttf",
]


def save_png(img, path, limit_kb=800):
    """Save an RGB image as an optimised PNG, falling back to a 256-colour palette if it is too big."""
    img.save(path, optimize=True)
    if path.stat().st_size > limit_kb * 1024:
        img.quantize(colors=256, method=0, dither=0).save(path, optimize=True)


# ---------------------------------------------------------------------------------------------------- 1. the SVG
def _text(x, y, lines, size, weight="400", fill="#374151", anchor="start", leading=None):
    leading = leading or size * 1.4
    out = [f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">']
    for i, ln in enumerate(lines):
        out.append(f'<tspan x="{x}" dy="{0 if i == 0 else leading:g}">{ln}</tspan>')
    out.append("</text>")
    return "".join(out)


def build_svg():
    ink, sub = "#111827", "#374151"
    stages = [
        ("1", "Your clues", ["A spreadsheet with a", "clue column and an", "answer column"], "#dbeafe"),
        ("2", "Grid builder", ["Fits every answer", "into one connected", "crossword grid"], "#dcfce7"),
        ("3", "Checks", ["A validator re-reads", "the grid letter by", "letter (no slips)"], "#fef3c7"),
        ("4", "Layout &amp; fit", ["Finds the largest", "squares that still", "keep clues readable"], "#fce7f3"),
    ]
    outputs = [
        ("Poster PDF", ["With 0.125 in bleed.", "Send this one to", "the print shop."]),
        ("Trim PDF", ["Exact final size, for", "shops that add their", "own bleed."]),
        ("Answer sheet", ["The filled grid on a", "letter page, plus an", "11x17 key for the host."]),
        ("Actual-size check", ["Print it at 100% to", "judge the squares and", "the type first."]),
    ]
    p = []
    p.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 450" width="900" height="450" role="img" '
        'aria-labelledby="t d">'
    )
    p.append('<title id="t">How crossword-poster works</title>')
    p.append(
        '<desc id="d">Your clues go into a grid builder, then checks, then layout and fit, which produces the print files: '
        "a poster PDF with bleed, a trim PDF, an answer sheet and an actual-size check page.</desc>"
    )
    p.append(
        '<style>text{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}</style>'
    )
    p.append(
        '<defs><marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{ink}"/></marker></defs>'
    )
    p.append(f'<rect x="3" y="3" width="894" height="444" rx="18" fill="#ffffff" stroke="{ink}" stroke-width="2"/>')
    p.append(_text(36, 46, ["From a spreadsheet to a poster you can hang on a wall"], 18, "700", ink))

    # the four stages
    bw, bh, gap, x0, y0 = 180, 112, 36, 36, 70
    for i, (num, title, body, fill) in enumerate(stages):
        x = x0 + i * (bw + gap)
        p.append(
            f'<rect x="{x}" y="{y0}" width="{bw}" height="{bh}" rx="12" fill="{fill}" stroke="{ink}" stroke-width="1.5"/>'
        )
        p.append(f'<circle cx="{x + 24}" cy="{y0 + 26}" r="12" fill="{ink}"/>')
        p.append(_text(x + 24, y0 + 31, [num], 14, "700", "#ffffff", "middle"))
        p.append(_text(x + 44, y0 + 31, [title], 16, "700", ink))
        p.append(_text(x + 16, y0 + 60, body, 13, "400", sub, leading=18))
        if i < len(stages) - 1:
            ax = x + bw
            p.append(
                f'<line x1="{ax + 4}" y1="{y0 + bh / 2}" x2="{ax + gap - 3}" y2="{y0 + bh / 2}" '
                f'stroke="{ink}" stroke-width="2" marker-end="url(#ah)"/>'
            )

    # fan-out from stage 4 to the four outputs
    cw, ch, cgap, cy = 198, 118, 20, 282
    cx0 = 774 - 99 - 3 * (cw + cgap)
    stem_x = 774
    bus_y = 246
    p.append(f'<line x1="{stem_x}" y1="{y0 + bh}" x2="{stem_x}" y2="{bus_y}" stroke="{ink}" stroke-width="2"/>')
    first_c = cx0 + cw / 2
    p.append(f'<line x1="{first_c:g}" y1="{bus_y}" x2="{stem_x}" y2="{bus_y}" stroke="{ink}" stroke-width="2"/>')
    # pill on the stem
    p.append(
        f'<rect x="{stem_x - 64}" y="{y0 + bh + 14}" width="128" height="30" rx="15" fill="#ffffff" stroke="{ink}" stroke-width="1.5"/>'
    )
    p.append(_text(stem_x, y0 + bh + 34, ["5  Print files"], 14, "700", ink, "middle"))
    for i, (title, body) in enumerate(outputs):
        x = cx0 + i * (cw + cgap)
        c = x + cw / 2
        p.append(
            f'<line x1="{c:g}" y1="{bus_y}" x2="{c:g}" y2="{cy - 3}" stroke="{ink}" stroke-width="2" marker-end="url(#ah)"/>'
        )
        p.append(
            f'<rect x="{x}" y="{cy}" width="{cw}" height="{ch}" rx="12" fill="#f3f4f6" stroke="{ink}" stroke-width="1.5"/>'
        )
        p.append(_text(x + 16, cy + 30, [title], 15, "700", ink))
        p.append(_text(x + 16, cy + 56, body, 13, "400", sub, leading=18))

    p.append(
        _text(
            450,
            428,
            ["Everything runs on your own computer. The same clues and seed always give the same poster."],
            12.5,
            "400",
            "#4b5563",
            "middle",
        )
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def make_svg(images: Path):
    svg = build_svg()
    xml.dom.minidom.parseString(svg)  # raises if it is not well-formed XML
    (images / "how-it-works.svg").write_text(svg, encoding="utf-8")
    print("wrote how-it-works.svg")


# ---------------------------------------------------------------------------------------------------- 2. style gallery
def build_previews(work: Path, name, size, styles, extra=()):
    out = work / name
    shutil.rmtree(out, ignore_errors=True)
    run(
        [
            "build",
            "--clues",
            str(CLUES),
            "--title",
            TITLE,
            "--subtitle",
            SUBTITLE,
            "--size",
            size,
            "--style",
            styles,
            "--png-width",
            "1400",
            "--out",
            str(out),
            *FAST,
            *extra,
        ]
    )
    return out


def make_styles(work: Path, images: Path):
    from PIL import Image, ImageDraw

    out = build_previews(work, "styles", "24x36", "all", ["--spot-text", "50"])
    names = ["grey", "black", "icons"]
    W, M, GAP = 520, 60, 60
    shots = [Image.open(out / f"poster_24x36_{s}_preview.png").convert("RGB") for s in names]
    H = max(round(im.height * W / im.width) for im in shots)
    cw = M * 2 + 3 * W + 2 * GAP
    top, label_h = 50, 100
    canvas = Image.new("RGB", (cw, top + H + label_h), "white")
    d = ImageDraw.Draw(canvas)
    font = find_font(SANS_BOLD, 38)
    for i, (n, im) in enumerate(zip(names, shots)):
        x = M + i * (W + GAP)
        im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
        canvas.paste(im, (x, top))
        d.rectangle([x - 1, top - 1, x + W, top + im.height], outline="#c9ced6", width=2)
        d.text((x + W / 2, top + H + 50), n, font=font, fill="#111827", anchor="mm")
    save_png(canvas, images / "gallery-styles.png")
    print("wrote gallery-styles.png", canvas.size)


# ---------------------------------------------------------------------------------------------------- 3. size gallery
def make_sizes(work: Path, images: Path):
    from PIL import Image, ImageDraw

    sizes = [(18, 24), (24, 36), (36, 48)]
    out = build_previews(work, "sizes", ",".join(f"{w}x{h}" for w, h in sizes), "grey")
    CW, M, GAP = 1800, 70, 70
    ppi = (CW - 2 * M - 2 * GAP) / sum(w for w, _ in sizes)
    top, label_h = 120, 110
    tallest = round(max(h for _, h in sizes) * ppi)
    canvas = Image.new("RGB", (CW, top + tallest + label_h), "white")
    d = ImageDraw.Draw(canvas)
    d.text((CW / 2, 52), "Drawn to scale", font=find_font(SANS_BOLD, 34), fill="#111827", anchor="mm")
    d.text(
        (CW / 2, 92),
        "same fictional sample at three poster sizes, bottom-aligned",
        font=find_font(SANS, 24),
        fill="#4b5563",
        anchor="mm",
    )
    x = M
    base = top + tallest
    lab = find_font(SANS_BOLD, 32)
    for w, h in sizes:
        im = Image.open(out / f"poster_{w}x{h}_grey_preview.png").convert("RGB")
        pw, ph = round(w * ppi), round(h * ppi)
        im = im.resize((pw, ph), Image.LANCZOS)
        canvas.paste(im, (x, base - ph))
        d.rectangle([x - 1, base - ph - 1, x + pw, base], outline="#c9ced6", width=2)
        d.text((x + pw / 2, base + 55), f"{w} x {h} in", font=lab, fill="#111827", anchor="mm")
        x += pw + GAP
    save_png(canvas, images / "gallery-sizes.png")
    print("wrote gallery-sizes.png", canvas.size)


# ---------------------------------------------------------------------------------------------------- 4. terminal GIF
def capture_demo(work: Path):
    """Run the two commands for real in a scratch folder and return their output with paths made relative."""
    cwd = work / "demo"
    shutil.rmtree(cwd, ignore_errors=True)
    cwd.mkdir(parents=True)
    out1 = run(["sample", "--out", "my-first-poster"], cwd=cwd)
    ls = subprocess.run(
        ["ls", "-C", "-w", "92", "my-first-poster"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    ).stdout
    # no absolute paths in the picture
    for base in {str(cwd), str(cwd.resolve())}:
        out1 = out1.replace(base + "/", "").replace(base, ".")
    out1 = re.sub(r"(/tmp|/home|/Users|/root|/var)/\S*", "my-first-poster", out1)
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    return ansi.sub("", out1).rstrip("\n"), ls.expandtabs(8).rstrip("\n")


def make_gif(work: Path, images: Path):
    from PIL import Image, ImageDraw

    out1, ls = capture_demo(work)
    COLS, ROWS = 106, 31
    fs = 13
    font, bold = find_font(MONO, fs), find_font(MONO_BOLD, fs)
    cw_px = round(font.getlength("M"))
    lh = 20
    PAD, BAR = 14, 40
    W = 900
    twidth = W - 2 * 20
    COLS = (twidth - 2 * PAD) // cw_px
    H = 20 + BAR + ROWS * lh + 2 * PAD + 20
    BG, WIN, TERM, BORDER = "#0d1117", "#161b22", "#0f141a", "#30363d"
    FG, DIM, GREEN, CYAN, YEL = "#e6edf3", "#9aa7b4", "#56d364", "#79c0ff", "#e3b341"

    # lines: list of (segments, delay_before_ms); segments = [(text, colour, bold)]
    def wrap(s):
        return textwrap.wrap(s, COLS, drop_whitespace=False, replace_whitespace=False) or [""]

    def colour_for(line):
        if re.match(r"\[\d/6\]", line):
            return [(line, CYAN, True)]
        if line.startswith("Done in"):
            return [(line, GREEN, True)]
        if re.match(r"(All \d+ output checks passed|Every answer was placed|Output checks: all passed)", line):
            return [(line, GREEN, False)]
        m = re.match(r"^(  )(\S+)(\s{2,})(.*)$", line)
        if m and (m.group(2).endswith((".pdf", ".png", ".csv")) or m.group(2) == "details/"):
            segs = [(m.group(1) + m.group(2), FG, False), (m.group(3), FG, False)]
            rest = m.group(4)
            if rest.startswith("PRINT THIS"):
                segs += [("PRINT THIS", YEL, True), (rest[len("PRINT THIS") :], DIM, False)]
            else:
                segs.append((rest, DIM, False))
            return segs
        if line.startswith("Made a poster?") or line.startswith("Before ordering"):
            return [(line, DIM, False)]
        return [(line, FG, False)]

    stage1 = []  # (segments, delay_ms before the line appears)
    for raw in out1.split("\n"):
        wrapped = wrap(raw) if len(raw) > COLS else [raw]
        for j, w in enumerate(wrapped):
            if j:
                w = w.lstrip()
            delay = 60
            if re.match(r"\[\d/6\]", w):
                delay = 650 if not w.startswith("[1/6]") else 500
            if w.startswith("  54 words in a") or w.startswith("  18x24: squares"):
                delay = 450
            if w.startswith("Done in"):
                delay = 500
            stage1.append((colour_for(w) if raw.strip() else [("", FG, False)], delay))
    ls_lines = [([(ln, FG, False)], 40) for ln in ls.split("\n")]

    prompt = ("$ ", GREEN, True)
    # history of lines shown so far; each frame is a list of segment lists
    frames = []  # (history_snapshot, cursor_visible_on_last_line, duration_ms)

    def render(history, cursor=True):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([20, 20, W - 20, H - 20], radius=12, fill=WIN, outline=BORDER, width=1)
        d.rounded_rectangle([20, 20, W - 20, 20 + BAR], radius=12, fill="#21262d")
        d.rectangle([21, 20 + BAR - 12, W - 21, 20 + BAR], fill="#21262d")  # square off the bottom of the bar
        for k, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
            cx = 44 + k * 24
            d.ellipse([cx - 7, 40 - 7 + 0, cx + 7, 40 + 7], fill=c)
        d.text((W / 2, 20 + BAR / 2), "Terminal", font=find_font(SANS, 13), fill="#8b949e", anchor="mm")
        d.rectangle([21, 20 + BAR, W - 21, H - 21], fill=TERM)
        d.rounded_rectangle([20, H - 20 - 24, W - 20, H - 20], radius=12, fill=TERM)
        d.rectangle([21, H - 20 - 24, W - 21, H - 20 - 12], fill=TERM)
        d.rounded_rectangle([20, 20, W - 20, H - 20], radius=12, outline=BORDER, width=1)
        vis = history[-ROWS:]
        x0, y0 = 20 + PAD, 20 + BAR + PAD
        for r, segs in enumerate(vis):
            x = x0
            for text, col, b in segs:
                if text:
                    d.text((x, y0 + r * lh), text, font=bold if b else font, fill=col)
                    x += round(font.getlength(text))
            if cursor and r == len(vis) - 1:
                d.rectangle([x + 1, y0 + r * lh + 1, x + cw_px, y0 + r * lh + lh - 3], fill="#c9d1d9")
        return img

    history = []

    def snap(ms, cursor=True):
        frames.append((render(history, cursor), ms))

    def type_command(cmd):
        history.append([prompt])
        snap(450)
        step = 2
        for i in range(step, len(cmd) + step, step):
            history[-1] = [prompt, (cmd[:i], FG, False)]
            snap(55)
        snap(350)
        history[-1] = [prompt, (cmd, FG, False)]  # "press Enter": cursor leaves the line

    type_command("crossword-poster sample --out my-first-poster")
    snap(250, cursor=False)
    for segs, delay in stage1:
        history.append(segs)
        snap(delay, cursor=False)
    snap(900, cursor=False)
    type_command("ls my-first-poster")
    snap(200, cursor=False)
    for segs, delay in ls_lines:
        history.append(segs)
        snap(delay, cursor=False)
    history.append([prompt])
    snap(3000, cursor=True)

    # merge identical neighbours, build one shared palette so the colours do not flicker
    imgs = [f for f, _ in frames]
    durs = [d for _, d in frames]
    # one shared palette for every frame (so colours never flicker): built from a few frames stacked together,
    # with octree quantising so the small coloured dots and text colours survive
    picks = [imgs[i] for i in sorted({0, len(imgs) // 3, len(imgs) // 2, (2 * len(imgs)) // 3, len(imgs) - 1})]
    stack = Image.new("RGB", (W, H * len(picks)))
    for k, im in enumerate(picks):
        stack.paste(im, (0, k * H))
    pal = stack.quantize(colors=48, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pframes = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    dst = images / "demo.gif"
    pframes[0].save(dst, save_all=True, append_images=pframes[1:], duration=durs, loop=0, optimize=True, disposal=1)
    print(f"wrote demo.gif {W}x{H}, {len(pframes)} frames, {sum(durs) / 1000:.1f} s, {dst.stat().st_size // 1024} KB")


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", nargs="*", help="which visuals to build: svg styles sizes gif (default: all)")
    ap.add_argument(
        "--work", default=str(ROOT / "out" / "visuals-build"), help="scratch folder for the intermediate posters"
    )
    ap.add_argument("--images", default=str(ROOT / "docs" / "images"), help="where to write the images")
    a = ap.parse_args()
    todo = a.what or ["svg", "styles", "sizes", "gif"]
    bad = [w for w in todo if w not in ("svg", "styles", "sizes", "gif")]
    if bad:
        ap.error(f"unknown visual(s): {', '.join(bad)} (choose from svg styles sizes gif)")
    images, work = Path(a.images), Path(a.work)
    images.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    if "svg" in todo:
        make_svg(images)
    if "styles" in todo:
        make_styles(work, images)
    if "sizes" in todo:
        make_sizes(work, images)
    if "gif" in todo:
        make_gif(work, images)


if __name__ == "__main__":
    main()
