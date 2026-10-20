"""Introspection of the mounted routes: which ones require sign-in, and which permissions.

Used by the route-inventory security test and by ``scripts/security/generate_route_matrix.py`` so
that "every route is protected unless it is deliberately public" is checked mechanically, not by
reading code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.modules.auth.dependencies import get_current_principal


@dataclass(frozen=True)
class RouteInfo:
    method: str
    path: str
    requires_sign_in: bool
    permissions: tuple[str, ...]
    any_of: bool
    requires_csrf_header: bool


def _walk(dependant: Dependant) -> list[Dependant]:
    found = [dependant]
    for sub in dependant.dependencies:
        found.extend(_walk(sub))
    return found


def _closure_permissions(call: Any) -> tuple[tuple[str, ...], bool] | None:
    """Permissions captured by a ``require_permissions``/``require_any_permission`` closure."""
    code = getattr(call, "__code__", None)
    if code is None or code.co_name != "dependency" or not call.__closure__:
        return None
    names = code.co_freevars
    values = {n: c.cell_contents for n, c in zip(names, call.__closure__, strict=True)}
    if "required" in values:
        return tuple(values["required"]), False
    if "accepted" in values:
        return tuple(values["accepted"]), True
    return None


def _mounted(app: FastAPI) -> list[tuple[str, set[str], Dependant]]:
    """(full path, methods, dependant) of every API route, including routers added with a prefix.

    FastAPI 0.153 resolves ``include_router`` lazily and exposes the flattened routes through
    ``effective_route_contexts()``; older versions list ``APIRoute`` objects directly. Both are
    handled so the inventory cannot silently come back empty (a test asserts a minimum count).
    """
    found: list[tuple[str, set[str], Dependant]] = []
    for route in app.routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            for ctx in contexts():
                found.append((ctx.path, set(ctx.methods or ()), ctx.dependant))
        elif isinstance(route, APIRoute):
            found.append((route.path, set(route.methods or ()), route.dependant))
    return found


def inventory(app: FastAPI) -> list[RouteInfo]:
    result: list[RouteInfo] = []
    for path, methods, dependant in _mounted(app):
        calls = [n.call for n in _walk(dependant) if n.call is not None]
        permissions: tuple[str, ...] = ()
        any_of = False
        for call in calls:
            captured = _closure_permissions(call)
            if captured:
                permissions, any_of = captured
        for method in sorted(methods - {"HEAD", "OPTIONS"}):
            result.append(
                RouteInfo(
                    method=method,
                    path=path,
                    requires_sign_in=get_current_principal in calls,
                    permissions=permissions,
                    any_of=any_of,
                    requires_csrf_header=any(
                        getattr(c, "__name__", "") == "require_csrf_header" for c in calls
                    ),
                )
            )
    return sorted(result, key=lambda r: (r.path, r.method))
