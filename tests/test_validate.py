"""The independent validator must accept good grids and catch corrupted ones."""

import copy
import json

from crossword_poster import validate as val


def write(tmp_path, data, name="g.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_good_grid_is_valid(small_grid, small_pool):
    path, _ = small_grid
    errs, info = val.validate(str(path), pool=small_pool)
    assert errs == []
    assert any("words 10" in line for line in info)


def test_changed_letter_is_caught(small_grid, tmp_path):
    _, res = small_grid
    bad = copy.deepcopy(res)
    r, c = next((r, c) for r, row in enumerate(bad["grid"]) for c, ch in enumerate(row) if ch)
    bad["grid"][r][c] = "#" if bad["grid"][r][c] != "#" else "A"
    errs, _ = val.validate(write(tmp_path, bad))
    assert errs


def test_extra_stray_letter_is_caught(small_grid, tmp_path):
    _, res = small_grid
    bad = copy.deepcopy(res)
    # add a letter diagonally next to the grid so it is not part of any word
    bad["grid"].append([""] * bad["cols"])
    bad["grid"][-1][0] = "Q"
    errs, _ = val.validate(write(tmp_path, bad))
    assert errs


def test_missing_clue_is_caught(small_grid, tmp_path):
    _, res = small_grid
    bad = copy.deepcopy(res)
    bad["clues"][0]["clue"] = "  "
    errs, _ = val.validate(write(tmp_path, bad))
    assert any("empty clue" in str(e) for e in errs)


def test_wrong_numbering_is_caught(small_grid, tmp_path):
    _, res = small_grid
    bad = copy.deepcopy(res)
    bad["placements"][0]["number"] = 99
    errs, _ = val.validate(write(tmp_path, bad))
    assert errs


def test_wrong_enumeration_is_caught(small_grid, tmp_path):
    _, res = small_grid
    bad = copy.deepcopy(res)
    bad["clues"][0]["clue"] += " (9)"
    errs, _ = val.validate(write(tmp_path, bad))
    assert any("enumeration" in str(e) for e in errs)


def test_pool_entry_missing_from_grid_is_caught(small_grid, small_pool, tmp_path):
    path, _ = small_grid
    pool = [*small_pool, {"id": "ghost", "grid": "GHOST", "clue": "x", "display": "Ghost"}]
    errs, _ = val.validate(str(path), pool=pool)
    assert any("MUST-INCLUDE" in str(e) for e in errs)


def test_bound_check(small_grid):
    path, _ = small_grid
    errs, _ = val.validate(str(path), max_rows=2, max_cols=2)
    assert errs


def test_command_line_exit_status(small_grid, tmp_path, capsys):
    path, res = small_grid
    assert val.main([str(path)]) == 0
    bad = copy.deepcopy(res)
    bad["grid"][0][0] = "Z"
    assert val.main([write(tmp_path, bad)]) == 1
