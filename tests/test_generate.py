"""The grid generator: placement, determinism, graceful degradation."""

import pytest

from crossword_poster import generate as gen
from crossword_poster.errors import UserError

WORDS = ["PLANET", "RIVER", "TIGER", "STONE", "OCEAN", "EAGLE", "NIGHT", "TRAIN", "SUGAR", "LEMON"]


def grid_of(board):
    return gen.to_result(board, [], {})["grid"]


def test_all_words_placed_for_a_small_set():
    board, stats = gen.generate_all(WORDS, attempts=100, seed=1)
    assert board is not None
    assert stats["words_placed"] == len(WORDS)
    assert {p[0] for p in board.placed} == set(WORDS)


def test_every_word_is_readable_in_the_grid():
    board, _ = gen.generate_all(WORDS, attempts=100, seed=3)
    res = gen.to_result(board, [], {})
    g = res["grid"]
    for p in res["placements"]:
        dr, dc = (0, 1) if p["direction"] == "across" else (1, 0)
        letters = "".join(g[p["row"] + dr * i][p["col"] + dc * i] for i in range(p["length"]))
        assert letters == p["word"]


def test_same_seed_gives_the_same_grid():
    a, _ = gen.generate_all(WORDS, attempts=60, seed=7)
    b, _ = gen.generate_all(WORDS, attempts=60, seed=7)
    assert grid_of(a) == grid_of(b)


def test_result_does_not_depend_on_worker_count():
    a, _ = gen.generate_all(WORDS, attempts=60, seed=7, workers=1)
    b, _ = gen.generate_all(WORDS, attempts=60, seed=7, workers=2)
    assert grid_of(a) == grid_of(b)


def test_different_seeds_can_differ():
    grids = {str(grid_of(gen.generate_all(WORDS, attempts=5, seed=s)[0])) for s in range(6)}
    assert len(grids) > 1


def test_numbering_follows_reading_order():
    board, _ = gen.generate_all(WORDS, attempts=50, seed=2)
    res = gen.to_result(board, [], {})
    starts = sorted({(p["row"], p["col"]) for p in res["placements"]})
    numbers = {}
    for p in res["placements"]:
        numbers.setdefault((p["row"], p["col"]), p["number"])
    assert [numbers[s] for s in starts] == list(range(1, len(starts) + 1))


def test_solve_reports_a_word_that_cannot_cross_anything():
    sol = gen.solve([*WORDS, "ZZYZX"], attempts=40, workers=1)
    assert not sol.complete
    assert list(sol.left_out) == ["ZZYZX"]
    assert "no letters" in sol.left_out["ZZYZX"]
    assert len(sol.board.placed) == len(WORDS)


def test_solve_places_what_it_can_when_the_window_is_too_small():
    # an explicit 6x6 window cannot hold ten words: expect a partial grid and an explanation, not an error
    sol = gen.solve(WORDS, max_width=6, max_height=6, attempts=20, workers=1)
    assert not sol.complete
    assert 0 < len(sol.board.placed) < len(WORDS)
    assert set(sol.left_out) | {p[0] for p in sol.board.placed} == set(WORDS)
    assert all("could not be fitted" in why for why in sol.left_out.values())


def test_solve_is_deterministic():
    a = gen.solve(WORDS, attempts=30, seed=5, workers=1)
    b = gen.solve(WORDS, attempts=30, seed=5, workers=1)
    assert grid_of(a.board) == grid_of(b.board)


def test_solve_needs_at_least_two_crossable_words():
    with pytest.raises(UserError):
        gen.solve(["ABC", "XYZ"], attempts=5, workers=1)


def test_explicit_bounds_are_respected():
    board, stats = gen.generate_all(WORDS, W=12, H=12, attempts=200, seed=1)
    if board is not None:
        assert stats["bbox_cols"] <= 12
        assert stats["bbox_rows"] <= 12


def test_best_effort_mode_honours_required_words():
    board, unplaced, stats = gen.generate(WORDS, required=["PLANET"], W=8, H=8, attempts=30, seed=1)
    assert "PLANET" in {p[0] for p in board.placed}
    assert stats["required_missing"] == []


def test_no_two_words_touch_side_by_side():
    board, _ = gen.generate_all(WORDS, attempts=50, seed=4)
    cells = board.cells
    # every maximal horizontal/vertical run of 2+ letters must be a placed word
    placed = {(r, c, d): w for w, r, c, d in board.placed}
    for (r, c), _ch in cells.items():
        if (r, c - 1) not in cells and (r, c + 1) in cells:
            assert (r, c, gen.ACROSS) in placed
        if (r - 1, c) not in cells and (r + 1, c) in cells:
            assert (r, c, gen.DOWN) in placed


def test_load_words_filters_and_dedupes(tmp_path):
    p = tmp_path / "w.csv"
    p.write_text("grid\nCAT\ncat\nA\nTOOLONGWORD\nR2D2\néclair\nDOG\n", encoding="utf-8")
    assert gen.load_words(str(p), "grid", min_len=2, max_len=8) == ["CAT", "DOG"]


def test_load_words_missing_column(tmp_path):
    p = tmp_path / "w.csv"
    p.write_text("word\nCAT\n", encoding="utf-8")
    with pytest.raises(UserError, match="no 'grid' column"):
        gen.load_words(str(p))


# ------------------------------------------------------- wall-clock budget
def test_an_expired_deadline_stops_the_search_and_says_so():
    board, stats = gen.generate_all(WORDS, attempts=1000, seed=1, deadline=0.001)  # long in the past
    assert board is None
    assert stats["time_limit_hit"] is True


def test_solve_with_an_expired_limit_still_returns_a_layout():
    sol = gen.solve(WORDS, attempts=1000, seed=1, time_limit=1e-6)
    assert sol.board.placed  # at least one attempt always runs
    assert sol.stats["time_limit_hit"] is True


def test_a_limit_that_is_not_reached_does_not_change_the_result():
    plain = gen.solve(WORDS, attempts=60, seed=2, workers=1)
    timed = gen.solve(WORDS, attempts=60, seed=2, workers=1, time_limit=600)
    assert grid_of(plain.board) == grid_of(timed.board)
    assert "time_limit_hit" not in timed.stats


def test_long_searches_log_progress(monkeypatch):
    monkeypatch.setattr(gen, "PROGRESS_EVERY", 0.0)
    lines = []
    gen.generate_all(WORDS, attempts=100, seed=1, log=lines.append)
    assert any("still searching" in ln for ln in lines)
