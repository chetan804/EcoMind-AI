"""Questions about the person's own records ("how many points do I have?").

These are matched by a few deliberately narrow patterns, never by free interpretation, and each
needs the permission that already guards the same data elsewhere in the API. The answer is read
from the database at the moment of asking; the assistant never remembers or guesses figures.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import Principal
from app.modules.rewards import service as rewards
from app.modules.support.constants import TicketStatus
from app.modules.support.models import SupportTicket
from app.modules.waste_reports.constants import WasteReportStatus
from app.modules.waste_reports.models import WasteReport


@dataclasses.dataclass(frozen=True)
class AccountAnswer:
    intent: str
    content: str
    source_title: str


@dataclasses.dataclass(frozen=True)
class Refusal:
    intent: str
    content: str


_BALANCE = re.compile(
    r"\b(my (reward )?(points?|balance)|(how many|what('s| is)) (reward )?points|"
    r"points (do )?i (have|got)|do i have .{0,30}points?|how much (have i|did i) earn)",
    re.IGNORECASE,
)
_REPORTS = re.compile(
    r"\b(my (waste )?(reports?|submissions?)|"
    r"(status|progress|update) (of|on) (my|the) (waste )?(reports?|submissions?)|"
    r"(have|did) i (reported|submitted)|how many (waste )?reports (have|did) i)",
    re.IGNORECASE,
)
_TICKETS = re.compile(
    r"\b(my (support )?(tickets?|requests?)|"
    r"(status|update) (of|on) my (support )?(ticket|request))",
    re.IGNORECASE,
)

# "How do I redeem my points?" asks for a procedure (a help article), not for the balance.
_PROCEDURAL = re.compile(
    r"\b(how (do|can|could|would|should|to)|where (do|can)|ways? to|can i|could i|may i)\b"
    r".*\b(redeem|earn|spend|cancel|use|claim|change|reset|transfer|collect|get|gain|raise|"
    r"increase|improve|buy|exchange|submit|file|make|open|create)\b",
    re.IGNORECASE,
)

_REPORT_LABEL = {
    WasteReportStatus.SUBMITTED: "submitted",
    WasteReportStatus.UNDER_REVIEW: "under review",
    WasteReportStatus.VERIFIED: "verified",
    WasteReportStatus.REJECTED: "rejected",
    WasteReportStatus.CLOSED: "closed",
}
_TICKET_LABEL = {
    TicketStatus.OPEN: "open",
    TicketStatus.IN_PROGRESS: "in progress",
    TicketStatus.RESOLVED: "resolved",
    TicketStatus.CLOSED: "closed",
}


def _points(db: Session, principal: Principal) -> AccountAnswer:
    net, earned, impact_kg, entries = rewards.balance_of(db, principal.user_id)
    if entries == 0:
        content = (
            "You have 0 points. Points are earned when a collection of your report is "
            "completed with a verified weight."
        )
    else:
        content = (
            f"You have {net} points ({earned} earned in total, {impact_kg.normalize():f} kg "
            f"of recovered material counted). Open the Rewards screen for the full history."
        )
    return AccountAnswer("rewards_balance", content, "Your rewards balance")


def _reports(db: Session, principal: Principal) -> AccountAnswer:
    rows = db.execute(
        select(WasteReport.status, func.count())
        .where(WasteReport.reporter_id == principal.user_id)
        .group_by(WasteReport.status)
    ).all()
    counts = {status: int(n) for status, n in rows}
    total = sum(counts.values())
    if total == 0:
        content = "You have not submitted any waste reports yet."
    else:
        parts = [f"{counts[s]} {_REPORT_LABEL[s]}" for s in WasteReportStatus if counts.get(s)]
        noun = "report" if total == 1 else "reports"
        content = (
            f"You have submitted {total} {noun}: {', '.join(parts)}. "
            "Open Waste intake records for details."
        )
    return AccountAnswer("my_reports", content, "Your waste reports")


def _tickets(db: Session, principal: Principal) -> AccountAnswer:
    rows = db.execute(
        select(SupportTicket.status, func.count())
        .where(SupportTicket.user_id == principal.user_id)
        .group_by(SupportTicket.status)
    ).all()
    counts = {status: int(n) for status, n in rows}
    total = sum(counts.values())
    if total == 0:
        content = "You have not opened any support requests."
    else:
        parts = [f"{counts[s]} {_TICKET_LABEL[s]}" for s in TicketStatus if counts.get(s)]
        noun = "request" if total == 1 else "requests"
        content = (
            f"You have {total} support {noun}: {', '.join(parts)}. "
            "Open Support to read the replies."
        )
    return AccountAnswer("my_tickets", content, "Your support requests")


_INTENTS: tuple[
    tuple[re.Pattern[str], str, str, Callable[[Session, Principal], AccountAnswer]], ...
] = (
    (_BALANCE, "rewards_balance", "rewards:read_own", _points),
    (_REPORTS, "my_reports", "waste_reports:read_own", _reports),
    (_TICKETS, "my_tickets", "support:ask", _tickets),
)


def answer_about_account(
    db: Session, principal: Principal, question: str
) -> AccountAnswer | Refusal | None:
    """``None`` when the question is not about the person's own records."""
    if _PROCEDURAL.search(question):
        return None
    for pattern, intent, permission, handler in _INTENTS:
        if pattern.search(question):
            if not principal.has(permission):
                return Refusal(
                    intent,
                    "Your role does not include that information. If you think it should, "
                    "ask the support team.",
                )
            return handler(db, principal)
    return None
