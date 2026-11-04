from __future__ import annotations

from enum import StrEnum


class RequestableRole(StrEnum):
    """Operational roles a signed-in person may ask for.

    ``administrator`` is deliberately absent: it is created only through the protected
    ``create-admin`` command or by another administrator.
    """

    COLLECTOR = "collector"
    FACILITY_OPERATOR = "facility_operator"
    MANAGER = "manager"


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
