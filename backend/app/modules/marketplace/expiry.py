"""Listing expiry: the daily job behind ``python -m app.cli expire-marketplace-listings``.

The platform has no scheduler, so the job is idempotent and safe to run as often as wanted (cron,
systemd timer, a platform scheduler). Between runs the API already behaves correctly: a published
listing past ``expires_at`` is hidden from other people and cannot be requested (see
``service.is_expired``); the job makes it official by closing it.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.marketplace import repository
from app.modules.marketplace.constants import (
    EXPIRY_NOTICE_DAYS,
    ListingOutcome,
    ListingStatus,
    RequestStatus,
)
from app.modules.marketplace.models import Listing
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory

EXPIRED_REASON = "The listing expired"


@dataclass(frozen=True)
class ExpiryResult:
    closed: int
    announced: int


def _notify(db: Session, user_id: uuid.UUID, title: str, listing: Listing, body: str) -> None:
    notifications.notify(
        db,
        recipient_id=user_id,
        category=NotificationCategory.SYSTEM,
        title=title,
        body=body,
        entity_type="marketplace_listing",
        entity_id=listing.id,
    )


def run(db: Session, *, now: dt.datetime | None = None) -> ExpiryResult:
    """Close lapsed listings and warn owners of those about to lapse. Commits once."""
    moment = now or dt.datetime.now(dt.UTC)
    closed = 0
    for listing in repository.lapsed(db, moment):
        listing.status = ListingStatus.CLOSED
        listing.closed_at = moment
        listing.close_reason = EXPIRED_REASON
        listing.outcome = ListingOutcome.EXPIRED
        declined: list[str] = []
        for request in repository.pending_requests(db, listing.id):
            request.status = RequestStatus.DECLINED
            request.decided_at = moment
            declined.append(str(request.id))
            _notify(
                db, request.requester_id, "A listing you asked for expired", listing, listing.title
            )
        _notify(
            db,
            listing.created_by_id,
            "Your listing expired",
            listing,
            f"{listing.title} is no longer on offer. Publish a new listing to offer it again.",
        )
        audit.record(
            db,
            action="marketplace_listing.expired",
            entity_type="marketplace_listing",
            entity_id=listing.id,
            context=RequestContext(),
            changes={"declined_requests": declined},
        )
        closed += 1
    announced = 0
    horizon = moment + dt.timedelta(days=EXPIRY_NOTICE_DAYS)
    for listing in repository.expiring_unannounced(db, moment, horizon):
        listing.expiry_notice_sent_at = moment
        _notify(
            db,
            listing.created_by_id,
            "Your listing expires soon",
            listing,
            f"{listing.title} lapses in under {EXPIRY_NOTICE_DAYS} days. "
            "Renew it to keep it on offer.",
        )
        announced += 1
    db.commit()
    return ExpiryResult(closed=closed, announced=announced)
