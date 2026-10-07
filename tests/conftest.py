"""Shared fixtures. End-to-end tests (marker ``e2e``) are skipped automatically when Chromium cannot start."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_BIRTHDAY = ROOT / "crossword_poster" / "samples" / "sample_birthday.csv"
SAMPLE_TRIVIA = ROOT / "examples" / "sample_clues.csv"

SMALL_ROWS = [
    ("Ringed planet's neighbour", "Planet"),
    ("It flows to the sea", "River"),
    ("Striped big cat", "Tiger"),
    ("Hard rock", "Stone"),
    ("Atlantic or Pacific", "Ocean"),
    ("Bird of prey", "Eagle"),
    ("Dark time", "Night"),
    ("Choo-choo", "Train"),
    ("Sweet crystals", "Sugar"),
    ("Sour yellow fruit", "Lemon"),
]


def write_csv(path: Path, rows, header=("clue", "answer"), encoding="utf-8", delimiter=",") -> Path:
    """Write a small CSV for a test."""
    with open(path, "w", newline="", encoding=encoding) as fh:
        w = csv.writer(fh, delimiter=delimiter)
        if header:
            w.writerow(header)
        w.writerows(rows)
    return path


@pytest.fixture
def small_csv(tmp_path):
    """A ten-word clue file that builds into a small grid."""
    return write_csv(tmp_path / "small.csv", SMALL_ROWS)


@pytest.fixture
def small_pool(small_csv):
    """The pool rows of ``small_csv``."""
    from crossword_poster import pool

    rows, _ = pool.build_pool(str(small_csv))
    return rows


@pytest.fixture
def small_grid(small_pool, tmp_path):
    """A solved and written grid.json for ``small_pool``: returns (path, result dict)."""
    from crossword_poster import generate as gen

    sol = gen.solve([r["grid"] for r in small_pool], attempts=50, workers=1)
    assert sol.complete
    res = gen.attach_pool(gen.to_result(sol.board, [], sol.stats), small_pool)
    gen.write_grid_files(res, str(tmp_path))
    return tmp_path / "grid.json", res


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    """Skip e2e tests when Chromium is not available (checked once, only if some e2e test was selected)."""
    e2e = [i for i in items if "e2e" in i.keywords]
    if not e2e:
        return
    from crossword_poster.common import check_chromium

    ok, detail = check_chromium()
    if not ok:
        skip = pytest.mark.skip(reason=f"Chromium is not available: {detail}")
        for item in e2e:
            item.add_marker(skip)
