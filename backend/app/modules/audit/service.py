"""Append-only audit trail.

``record`` only adds a row to the caller's session: the caller's service owns the transaction, so
the audit entry commits or rolls back together with the change it describes. Security events that
must survive a failed request (for example a rejected login) are committed by the caller before
it raises.

Never pass secrets, password hashes or tokens in ``changes``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


@dataclass(frozen=True)
class RequestContext:
    """Who/where a request came from, for audit rows and session metadata."""

    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    @classmethod
    def from_request(cls, request: Request) -> RequestContext:
        # ``request.client`` is the direct peer. Behind a reverse proxy this is the proxy's
        # address unless the ASGI server is configured to trust forwarded headers; X-Forwarded-For
        # is deliberately not read here because any client can forge it.
        client = request.client
        agent = request.headers.get("user-agent")
        return cls(
            request_id=getattr(request.state, "request_id", None),
            ip_address=client.host[:45] if client else None,
            user_agent=agent[:255] if agent else None,
        )


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    context: RequestContext | None = None,
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    ctx = context or RequestContext()
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=ctx.request_id,
        ip_address=ctx.ip_address,
        changes=changes,
    )
    db.add(entry)
    return entry
