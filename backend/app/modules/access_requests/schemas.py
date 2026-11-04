"""Request and response bodies of the role-request API."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.access_requests.constants import RequestableRole, RequestStatus

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=2000)]
Organisation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class RoleRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_role: RequestableRole
    reason: Reason
    organisation: Organisation | None = None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: Note | None = None


class RoleRequestOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    requester_email: str
    requester_name: str
    requested_role: RequestableRole
    status: RequestStatus
    reason: str
    organisation: str | None
    decided_by_id: uuid.UUID | None
    decided_at: dt.datetime | None
    decision_note: str | None
    created_at: dt.datetime
