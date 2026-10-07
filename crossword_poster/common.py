"""Shared helpers: bundled fonts, Chromium discovery and launch, PDF printing and PNG previews."""

from __future__ import annotations

import base64
import glob
import os
import re
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Optional

from .errors import EnvironmentProblem, UserError

BLEED = 0.125  # inches, all sides
CHROMIUM_ENV = "CROSSWORD_POSTER_CHROMIUM"

# (family directory, file name) of every bundled font the renderer uses
BUNDLED_FONTS = (
    ("ArchivoNarrow", "ArchivoNarrow-Regular.ttf"),
    ("ArchivoNarrow", "ArchivoNarrow-Medium.ttf"),
    ("ArchivoNarrow", "ArchivoNarrow-Bold.ttf"),
    ("Oswald", "Oswald-Bold.ttf"),
)


# ------------------------------------------------------------------ fonts
def font_resource(family_dir: str, filename: str):
    """The packaged font file as an importlib.resources Traversable."""
    return resources.files("crossword_poster").joinpath("fonts", family_dir, filename)


@cache
def font_data_uri(family_dir: str, filename: str) -> str:
    """The font as a base64 ``data:`` URI, so the generated HTML needs no file paths."""
    res = font_resource(family_dir, filename)
    if not res.is_file():
        raise EnvironmentProblem(
            f"The bundled font {family_dir}/{filename} is missing from the installation.",
            "Reinstall the package: pip install --force-reinstall crossword-poster",
        )
    return "data:font/ttf;base64," + base64.b64encode(res.read_bytes()).decode("ascii")


def font_face(css_family: str, family_dir: str, filename: str, weight: int, style: str = "normal") -> str:
    """A CSS ``@font-face`` rule for a bundled font."""
    return (
        f"@font-face{{font-family:'{css_family}';src:url('{font_data_uri(family_dir, filename)}') format('truetype');"
        f"font-weight:{weight};font-style:{style};}}"
    )


def missing_fonts() -> list[str]:
    """Names of bundled fonts that cannot be found (empty when the installation is healthy)."""
    return [f"{d}/{f}" for d, f in BUNDLED_FONTS if not font_resource(d, f).is_file()]


# --------------------------------------------------------------- chromium
def _autodetect() -> Iterator[str]:
    """Yield candidate Chromium/Chrome executables found on this machine."""
    roots = [
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
        str(Path.home() / ".cache" / "ms-playwright"),
        str(Path.home() / "Library" / "Caches" / "ms-playwright"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright") if os.environ.get("LOCALAPPDATA") else None,
    ]
    for root in filter(None, roots):
        root = os.path.expanduser(root)
        direct = os.path.join(root, "chromium")
        if os.path.isfile(direct):
            yield direct
        for pat in (
            "chromium-*/chrome-linux*/chrome",
            "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
            "chromium-*/chrome-win*/chrome.exe",
        ):
            yield from sorted(glob.glob(os.path.join(root, pat)), reverse=True)
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            yield found
    for fixed in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if os.path.isfile(fixed):
            yield fixed


def install_command(with_deps: bool = False) -> list[str]:
    """The command that downloads Playwright's Chromium, run with the Python that is running this program.

    ``sys.executable`` matters: under pipx, uv or a virtual environment a bare ``python`` is a different
    interpreter that does not have Playwright.
    """
    return [sys.executable, "-m", "playwright", "install", *(["--with-deps"] if with_deps else []), "chromium"]


def install_command_text(with_deps: bool = False) -> str:
    """:func:`install_command` as text to paste into a terminal (the interpreter path is quoted: it may hold spaces)."""
    cmd = install_command(with_deps)
    return " ".join([f'"{cmd[0]}"', *cmd[1:]])


def chromium_fix_message() -> str:
    """The exact instruction for getting a working Chromium."""
    return (
        "run `crossword-poster install-browser`; if that does not work, run "
        f"`{install_command_text()}` yourself (or set {CHROMIUM_ENV} to the path of a Chromium/Chrome executable)"
    )


def launch(pw):
    """Launch headless Chromium.

    Order: ``$CROSSWORD_POSTER_CHROMIUM`` (an executable path), Playwright's own browser, then auto-detection.
    Raises EnvironmentProblem with the exact fix command when nothing works.
    """
    exe = os.environ.get(CHROMIUM_ENV)
    if exe:
        try:
            return pw.chromium.launch(executable_path=exe)
        except Exception as exc:
            raise EnvironmentProblem(
                f"{CHROMIUM_ENV} is set to {exe!r}, but Chromium could not be started from it ({_first_line(exc)}).",
                f"fix or unset {CHROMIUM_ENV}, or {chromium_fix_message()}",
            ) from exc
    try:
        return pw.chromium.launch()
    except Exception as first:
        for cand in _autodetect():
            try:
                return pw.chromium.launch(executable_path=cand)
            except Exception:
                continue
        raise EnvironmentProblem(
            "Chromium (the browser used to print the poster) was not found or could not start.",
            chromium_fix_message(),
        ) from first


def check_chromium() -> tuple[bool, str]:
    """Try to start Chromium. Returns ``(ok, detail)``: the browser version, or why it failed (with the fix)."""
    try:
        sync_playwright = sync_playwright_or_fail()
        with sync_playwright() as pw:
            browser = launch(pw)
            try:
                return True, f"Chromium {browser.version}"
            finally:
                browser.close()
    except UserError as exc:
        return False, exc.message
    except Exception as exc:  # the Playwright driver itself failed to start
        return False, _first_line(exc)


def _first_line(exc: Exception) -> str:
    lines = str(exc).strip().splitlines()
    return lines[0] if lines else exc.__class__.__name__


def sync_playwright_or_fail():
    """Import Playwright lazily, with a friendly error if it is not installed."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - playwright is a hard dependency
        raise EnvironmentProblem(
            "The 'playwright' package is not installed.", "pip install --upgrade crossword-poster"
        ) from exc
    return sync_playwright


@contextmanager
def browser_context():
    """Yield a Playwright browser context backed by headless Chromium; the browser is closed on exit."""
    sync_playwright = sync_playwright_or_fail()
    with sync_playwright() as pw:
        browser = launch(pw)
        try:
            # offline: the poster page is self-contained, so no request may ever leave this machine
            yield browser.new_context(offline=True)
        finally:
            browser.close()


# ------------------------------------------------------------------ options
_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,30}")


def check_colour(value: Optional[str], flag: str) -> Optional[str]:
    """Return ``value`` if it is a hex colour or a plain colour name (or empty); otherwise raise UserError."""
    if value and not _COLOUR_RE.fullmatch(value):
        raise UserError(
            f"{flag} {value[:40]!r} is not a colour I understand.",
            "use a hex colour such as '#c8d6e5' (quote it: # starts a comment in some shells) or a colour name "
            "such as lightgrey",
        )
    return value


# ------------------------------------------------------------------ output
def png_preview(pdf: str | os.PathLike, png: str | os.PathLike, width_px: int = 1200) -> None:
    """Rasterise page 1 of a PDF to a PNG that is ``width_px`` wide (pypdfium2; no external tools needed)."""
    from .pdfutil import render_png

    render_png(pdf, png, width_px)


def run_pdf(page, w_in: float, h_in: float, out: str | os.PathLike) -> None:
    """Print a Playwright page to a PDF of exactly ``w_in`` x ``h_in`` inches."""
    page.pdf(
        path=str(out),
        width=f"{w_in}in",
        height=f"{h_in}in",
        print_background=True,
        margin=dict(top="0", right="0", bottom="0", left="0"),
        prefer_css_page_size=True,
    )


def parse_size(s: str) -> tuple[float, float]:
    """``'24x36'`` -> ``(24.0, 36.0)``. Raises UserError for anything else."""
    try:
        w, h = (float(x) for x in s.strip().lower().replace("\u00d7", "x").split("x"))
        if w <= 0 or h <= 0:
            raise ValueError
    except ValueError:
        raise UserError(
            f"{s!r} is not a poster size.", "write it as WIDTHxHEIGHT in inches, for example 24x36"
        ) from None
    return w, h


def is_windows() -> bool:
    """True on Windows (used to avoid multiprocessing surprises and to pick path hints)."""
    return sys.platform.startswith("win")
