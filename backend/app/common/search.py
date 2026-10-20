"""Helpers for user-supplied search text."""

from __future__ import annotations

MAX_SEARCH_LENGTH = 100
_LIKE_ESCAPE = "\\"


def contains_pattern(text: str) -> str | None:
    """``%text%`` for ``ILIKE ... ESCAPE '\\'`` with the user's wildcards neutralised.

    ``%``, ``_`` and the escape character itself are literal when typed by a user. Returns
    ``None`` for blank input so callers can skip the filter. Text is trimmed and truncated.
    """
    cleaned = text.strip()[:MAX_SEARCH_LENGTH]
    if not cleaned:
        return None
    escaped = (
        cleaned.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


LIKE_ESCAPE = _LIKE_ESCAPE
