from __future__ import annotations

import pytest

from app.common.search import MAX_SEARCH_LENGTH, contains_pattern


def test_blank_input_means_no_filter() -> None:
    assert contains_pattern("") is None
    assert contains_pattern("   ") is None


def test_plain_text_is_wrapped() -> None:
    assert contains_pattern("  plastic  ") == "%plastic%"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("100%", "%100\\%%"), ("a_b", "%a\\_b%"), ("c:\\dir", "%c:\\\\dir%"), ("%_%", "%\\%\\_\\%%")],
)
def test_user_wildcards_are_literal(typed: str, expected: str) -> None:
    assert contains_pattern(typed) == expected


def test_length_is_capped() -> None:
    pattern = contains_pattern("x" * 1000)
    assert pattern is not None and len(pattern) == MAX_SEARCH_LENGTH + 2
