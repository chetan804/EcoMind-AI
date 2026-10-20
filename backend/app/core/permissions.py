"""Authorization primitives shared by all modules.

Permissions are plain strings of the form ``<resource>:<action>`` (for example
``waste_reports:read``). Roles and their permission grants are stored in the database and owned
by the ``users`` module; each module declares the permission strings it enforces in its own
``permissions.py``. This file only contains the module-independent check.
"""

from __future__ import annotations

from collections.abc import Collection

from app.core.exceptions import ForbiddenError


def missing_permissions(granted: Collection[str], required: Collection[str]) -> set[str]:
    """Return the permissions in ``required`` that are not in ``granted``."""
    return set(required) - set(granted)


def ensure_permissions(granted: Collection[str], required: Collection[str]) -> None:
    """Raise ``ForbiddenError`` unless every required permission has been granted.

    The error message deliberately does not list the missing permissions.
    """
    if missing_permissions(granted, required):
        raise ForbiddenError("You do not have permission to perform this action")
