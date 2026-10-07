"""The 'every clue appears exactly once' check must survive what a PDF does to text."""

from crossword_poster import verify
from crossword_poster.verify import _occurrences, normalise_text

HYPHEN_CLUE = "Sam's favourite UK-based airline (7,7)"
BLANK_CLUE = "Guilty-pleasure TV show: Friends of ____ (6)"


def test_pdfium_writes_a_wrapped_hyphen_as_u_fffe_and_it_still_matches():
    # what text extraction gives when "UK-based" is broken after the hyphen
    extracted = "82 Sam's favourite UK￾\nbased airline (7,7)"
    assert normalise_text("82 " + HYPHEN_CLUE) in normalise_text(extracted)


def test_a_blank_that_wraps_or_changes_length_still_matches():
    extracted = "142 Guilty￾\npleasure TV show: Friends of\n___\n_ (6)"
    assert normalise_text("142 " + BLANK_CLUE) in normalise_text(extracted)
    assert normalise_text("1 Fill ____") == normalise_text("1 Fill ________")


def test_quotes_dashes_ligatures_and_whitespace_are_normalised():
    assert normalise_text("Sam’s “fine” ﬁlm – so­ft") == normalise_text('Sam\'s "fine" film  soft')
    assert normalise_text("a—b‐c−d") == "abcd"
    assert normalise_text(" a \n b\t​c ") == "abc"


def test_a_clue_is_counted_once_even_when_its_tail_wrapped_differently():
    page = normalise_text(
        "7 Sam's favourite UK-based airline that flies to many places around the world, ev\nery day (7,7) 8 Other"
    )
    needle = normalise_text(
        "7 Sam's favourite UK-based airline that flies to many places around the world, every day (7,7)"
    )
    assert _occurrences(page, needle) == 1  # found by its first 60 characters, which include the number


def test_a_missing_or_duplicated_clue_is_still_reported():
    page = normalise_text("1 One clue (3) 2 Another clue (4) 2 Another clue (4)")
    assert _occurrences(page, normalise_text("1 One clue (3)")) == 1
    assert _occurrences(page, normalise_text("2 Another clue (4)")) == 2
    assert _occurrences(page, normalise_text("3 A missing clue (5)")) == 0


def test_the_number_keeps_two_clues_with_the_same_text_apart():
    page = normalise_text("12 Same words here (4) 112 Same words here (4)")
    assert _occurrences(page, normalise_text("12 Same words here (4)")) == 1


def test_squeeze_is_the_same_function():
    assert verify._squeeze is normalise_text
