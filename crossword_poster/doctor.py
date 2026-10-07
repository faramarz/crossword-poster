"""``crossword-poster doctor``: check that this machine can build posters, with the exact fix for anything missing."""

from __future__ import annotations

import argparse
import sys
from importlib import import_module, metadata
from typing import Optional

from . import __version__
from .common import check_chromium, chromium_fix_message, missing_fonts

MIN_PYTHON = (3, 9)
REQUIRED = (
    ("playwright", "playwright"),
    ("pypdf", "pypdf"),
    ("pypdfium2", "pypdfium2"),
    ("numpy", "numpy"),
    ("Pillow", "PIL"),
)


def _line(status: str, text: str) -> None:
    print(f"  [{status}] {text}")


def run_checks() -> list[tuple[bool, str, str]]:
    """Run every check. Returns a list of ``(ok, description, fix)``; ``fix`` is empty when ``ok``."""
    results = []
    v = sys.version_info
    ok = v >= MIN_PYTHON
    results.append(
        (ok, f"Python {v.major}.{v.minor}.{v.micro} (needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer)",
         "" if ok else "install a newer Python from https://www.python.org/downloads/")
    )  # fmt: skip
    missing = []
    versions = []
    for dist, module in REQUIRED:
        try:
            import_module(module)
            versions.append(f"{dist} {metadata.version(dist)}")
        except Exception:
            missing.append(dist)
    results.append(
        (not missing, f"crossword-poster {__version__} imports; libraries: {', '.join(versions) or 'none'}",
         "" if not missing else f"pip install --upgrade crossword-poster   (missing: {', '.join(missing)})")
    )  # fmt: skip
    bad_fonts = missing_fonts()
    results.append(
        (not bad_fonts, "Bundled fonts found (Archivo Narrow, Oswald)" if not bad_fonts else f"Bundled fonts missing: {', '.join(bad_fonts)}",
         "" if not bad_fonts else "pip install --force-reinstall crossword-poster")
    )  # fmt: skip
    ok, detail = check_chromium()
    results.append(
        (ok, detail if ok else f"Chromium could not start: {detail}",
         "" if ok else chromium_fix_message())
    )  # fmt: skip
    return results


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``doctor``. Exit status 0 when everything is ready, 1 otherwise."""
    argparse.ArgumentParser(
        prog="crossword-poster doctor",
        description="Check Python, the installed libraries, the bundled fonts and that Chromium can start.",
    ).parse_args(argv)
    print(f"crossword-poster {__version__}: checking this computer\n")
    results = run_checks()
    for ok, text, fix in results:
        _line("ok" if ok else "FAIL", text)
        if fix:
            print(f"         Fix: {fix}")
    if all(r[0] for r in results):
        print("\nEverything is ready. Try:  crossword-poster sample --out my-first-poster")
        return 0
    print("\nSome checks failed. Follow the 'Fix' lines above, then run `crossword-poster doctor` again.")
    return 1
