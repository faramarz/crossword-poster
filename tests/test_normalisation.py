"""Answer normalisation and enumerations."""

import pytest

from crossword_poster.pool import ENUM_RE, enumeration, enumeration_total, grid_word


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Paris", "PARIS"),
        ("Big Ben", "BIGBEN"),
        ("Mount Saint-Hélène", "MOUNTSAINTHELENE"),
        ("  café au lait! ", "CAFEAULAIT"),
        ("O'Brien", "OBRIEN"),
        ("Straße", "STRASSE"),
        ("Ångström", "ANGSTROM"),
        ("Łódź", "LODZ"),
        ("", ""),
        ("1984", ""),
    ],
)
def test_grid_word(text, expected):
    assert grid_word(text) == expected


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("Paris", ""),
        ("Big Ben", "(3,3)"),
        ("Milky Way", "(5,3)"),
        ("Mother-in-law", "(6,2,3)"),
        ("Café au lait", "(4,2,4)"),
    ],
)
def test_enumeration(display, expected):
    assert enumeration(display) == expected


def test_enumeration_regex_and_total():
    assert enumeration_total("Capital (5)") == 5
    assert enumeration_total("London clock tower (3,3)") == 6
    assert enumeration_total("Mother in law (6-2-3)") == 11
    assert enumeration_total("No enumeration here") is None
    # a year in brackets is not an enumeration
    assert enumeration_total("Moon landing year (1969)") is None
    assert ENUM_RE.search("clue (3, 3)")
