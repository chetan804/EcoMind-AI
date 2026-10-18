import pytest

from app.core.exceptions import ForbiddenError
from app.core.permissions import ensure_permissions, missing_permissions


def test_missing_permissions() -> None:
    assert missing_permissions({"a:read"}, {"a:read", "a:write"}) == {"a:write"}


def test_ensure_permissions_passes_when_all_granted() -> None:
    ensure_permissions({"a:read", "a:write"}, ["a:read"])


def test_ensure_permissions_denies_without_leaking_names() -> None:
    with pytest.raises(ForbiddenError) as excinfo:
        ensure_permissions(set(), ["secret_area:admin"])
    assert "secret_area" not in excinfo.value.message
