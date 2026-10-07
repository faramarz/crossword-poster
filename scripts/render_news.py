#!/usr/bin/env python3
"""Thin wrapper: same as `python -m crossword_poster <command>` for the 'render_news' module (run from anywhere)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from crossword_poster.render_news import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
