"""Shared helpers: font lookup, Chromium discovery/launch, PNG previews."""
import glob
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLEED = 0.125  # inches, all sides


# ------------------------------------------------------------------ fonts
def font_dir():
    """fonts/ directory: $CROSSWORD_FONT_DIR, else <repo>/fonts, else ./fonts."""
    for cand in (os.environ.get("CROSSWORD_FONT_DIR"), REPO / "fonts", Path.cwd() / "fonts"):
        if cand and Path(cand).is_dir():
            return Path(cand)
    raise FileNotFoundError("fonts/ directory not found (set CROSSWORD_FONT_DIR or run from the repo root)")


def font_url(family_dir, filename):
    """file:// URL of fonts/<family_dir>/<filename>; clear error if the file is missing."""
    p = font_dir() / family_dir / filename
    if not p.is_file():
        raise FileNotFoundError(f"missing font file {p}. Run scripts/fetch_fonts.sh to download it.")
    return p.resolve().as_uri()


def font_face(css_family, family_dir, filename, weight, style="normal"):
    return (f"@font-face{{font-family:'{css_family}';src:url('{font_url(family_dir, filename)}') format('truetype');"
            f"font-weight:{weight};font-style:{style};}}")


# --------------------------------------------------------------- chromium
def _autodetect():
    """Yield candidate Chromium/Chrome executables."""
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), str(Path.home() / ".cache" / "ms-playwright"),
             str(Path.home() / "Library" / "Caches" / "ms-playwright")]
    for root in filter(None, roots):
        root = os.path.expanduser(root)
        direct = os.path.join(root, "chromium")
        if os.path.isfile(direct):
            yield direct
        for pat in ("chromium-*/chrome-linux*/chrome", "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
                    "chromium-*/chrome-win*/chrome.exe"):
            for p in sorted(glob.glob(os.path.join(root, pat)), reverse=True):
                yield p
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            yield p


def launch(pw):
    """Launch headless Chromium: $CROSSWORD_CHROMIUM (executable path) > Playwright's own build > auto-detected."""
    exe = os.environ.get("CROSSWORD_CHROMIUM")
    if exe:
        return pw.chromium.launch(executable_path=exe)
    try:
        return pw.chromium.launch()
    except Exception as first:
        for cand in _autodetect():
            try:
                return pw.chromium.launch(executable_path=cand)
            except Exception:
                continue
        raise RuntimeError("No Chromium found. Run `playwright install chromium`, or set CROSSWORD_CHROMIUM to a "
                           "Chromium/Chrome executable.") from first


# ------------------------------------------------------------------ output
def png_preview(pdf, png, width_px=1200):
    """Rasterise page 1 of a PDF to a PNG `width_px` wide (PyMuPDF; no poppler needed)."""
    import pymupdf as fitz
    doc = fitz.open(pdf)
    page = doc[0]
    z = width_px / page.rect.width
    page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csRGB, alpha=False).save(png)
    doc.close()


def run_pdf(page, w_in, h_in, out):
    page.pdf(path=out, width=f"{w_in}in", height=f"{h_in}in", print_background=True,
             margin=dict(top="0", right="0", bottom="0", left="0"), prefer_css_page_size=True)


def parse_size(s):
    """'24x36' -> (24.0, 36.0)."""
    try:
        w, h = (float(x) for x in s.lower().replace("×", "x").split("x"))
    except Exception:
        raise ValueError(f"bad size {s!r}; expected WxH in inches, e.g. 24x36")
    return w, h
