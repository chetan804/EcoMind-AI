"""Surplus-material listings and requests. Owned by the ``marketplace`` module."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.marketplace.constants import (
    ListingCategory,
    ListingCondition,
    ListingStatus,
    ListingUnit,
    RequestStatus,
)


class Listing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Surplus material or items offered for reuse. No price and no payment exist."""

    __tablename__ = "marketplace_listings"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)", name="closed_timestamp_consistent"
        ),
        CheckConstraint(
            "(status IN ('published', 'reserved', 'closed')) OR published_at IS NULL",
            name="published_timestamp_consistent",
        ),
    )

    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[ListingCategory] = mapped_column(
        enum_column(ListingCategory), nullable=False, index=True
    )
    quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[ListingUnit] = mapped_column(enum_column(ListingUnit), nullable=False)
    condition: Mapped[ListingCondition] = mapped_column(
        enum_column(ListingCondition), nullable=False
    )
    pickup_city: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[ListingStatus] = mapped_column(
        enum_column(ListingStatus),
        nullable=False,
        index=True,
        server_default=ListingStatus.DRAFT.value,
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(String(500))


class ListingRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One user's request for a listing (at most one per user and listing)."""

    __tablename__ = "marketplace_requests"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "requester_id", name="uq_marketplace_requests_listing_requester"
        ),
        CheckConstraint(
            "(status IN ('pending')) = (decided_at IS NULL)", name="decision_timestamp_consistent"
        ),
    )

    listing_id: Mapped[uuid.UUID] = fk_uuid("marketplace_listings.id", ondelete="CASCADE")
    requester_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        enum_column(RequestStatus),
        nullable=False,
        index=True,
        server_default=RequestStatus.PENDING.value,
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
