"""``crossword-poster feedback``: show where to share feedback, and open the feedback form in a browser.

This module sends nothing anywhere and never reads a clues file. The only things it puts in the link are the program
version and a short description of this computer, which the person can see (and edit) in the form before sending.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import webbrowser
from typing import Optional
from urllib.parse import urlencode

from . import __version__

REPO_URL = "https://github.com/faramarz/crossword-poster"
FEEDBACK_EMAIL = "gm@faramarz.xyz"
FORM_URL = f"{REPO_URL}/issues/new"
FORM_TEMPLATE = "feedback.yml"
SHOW_AND_TELL_URL = f"{REPO_URL}/discussions/categories/show-and-tell"
NO_HINT_ENV = "CROSSWORD_POSTER_NO_FEEDBACK"


def platform_summary() -> str:
    """A short, plain description such as ``macOS 15.1 (arm64), Python 3.13.1``."""
    system = platform.system()
    if system == "Darwin":
        name = f"macOS {platform.mac_ver()[0]}".strip()
    elif system == "Windows":
        name = f"Windows {platform.release()}".strip()
    elif system == "Linux":
        name = "Linux"
        try:
            info = platform.freedesktop_os_release()  # Python 3.10 and newer
            name = info.get("PRETTY_NAME") or name
        except (AttributeError, OSError):
            pass
    else:
        name = f"{system} {platform.release()}".strip() or "unknown system"
    machine = platform.machine()
    where = f"{name} ({machine})" if machine else name
    return f"{where}, Python {platform.python_version()}"


def feedback_url(version: Optional[str] = None, os_summary: Optional[str] = None) -> str:
    """The feedback form link, with the version and system filled in (URL-encoded)."""
    query = urlencode(
        {
            "template": FORM_TEMPLATE,
            "version": __version__ if version is None else version,
            "os": platform_summary() if os_summary is None else os_summary,
        }
    )
    return f"{FORM_URL}?{query}"


def hint_text() -> str:
    """The one-line nudge printed after a successful build or sample."""
    return f"Made a poster? Tell us how it went: crossword-poster feedback  (or {FORM_URL}?template={FORM_TEMPLATE})"


def hint_disabled(flag: bool = False) -> bool:
    """True when the nudge is switched off by ``--no-feedback-hint`` or ``CROSSWORD_POSTER_NO_FEEDBACK``."""
    if flag:
        return True
    return os.environ.get(NO_HINT_ENV, "").strip().lower() not in ("", "0", "false", "no", "off")


def print_hint(flag: bool = False) -> None:
    """Print the nudge as the very last output, unless it is switched off."""
    if not hint_disabled(flag):
        print()
        print(hint_text())


def _has_display() -> bool:
    """False on a Linux computer with no screen (for example over SSH), where opening a browser cannot work."""
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def main(argv: Optional[list] = None) -> int:
    """Command line entry point for ``feedback``. Always exits 0."""
    ap = argparse.ArgumentParser(
        prog="crossword-poster feedback",
        description="Show how to share feedback or show off your poster, and open the feedback form in your browser. "
        "The link has the program version and a short description of this computer filled in; you can change both "
        "in the form. This command sends nothing anywhere itself and never reads your clues file. Please do not put "
        "private clues or names in feedback.",
    )
    ap.add_argument("--no-open", action="store_true", help="only print the links; do not open the browser")
    a = ap.parse_args(argv)
    url = feedback_url()
    print("Thank you for trying crossword-poster! We would love to hear how it went.")
    print()
    print("Feedback form (takes about a minute):")
    print(f"  {url}")
    print("Show and tell (share a photo of your poster):")
    print(f"  {SHOW_AND_TELL_URL}")
    print("No GitHub account, or want privacy? Email:")
    print(f"  {FEEDBACK_EMAIL}")
    print()
    print("Please never share private clues or names. This command sent nothing; it only prints and opens the links.")
    if a.no_open:
        return 0
    if not _has_display():
        print("(No screen was found, so the browser was not opened. Copy the link above into a browser.)")
        return 0
    try:
        opened = webbrowser.open(url)
    except Exception:  # never crash because a browser could not start
        opened = False
    if opened:
        print("Opening the form in your browser...")
    else:
        print("(The browser could not be opened. Copy the link above into a browser.)")
    return 0
