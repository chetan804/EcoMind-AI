"""Surplus-material listings and requests. Owned by the ``marketplace`` module."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.marketplace.constants import (
    ListingCategory,
    ListingCondition,
    ListingOutcome,
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
        CheckConstraint(
            "expires_at IS NULL OR published_at IS NOT NULL", name="expiry_needs_publication"
        ),
        CheckConstraint("outcome IS NULL OR status = 'closed'", name="outcome_only_when_closed"),
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
    # A published listing lapses at this moment (the ``expire-marketplace-listings`` CLI job).
    # NULL only on drafts and on listings that predate expiry.
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Set once, when the owner is told the listing is about to lapse.
    expiry_notice_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[ListingOutcome | None] = mapped_column(enum_column(ListingOutcome))


class ListingPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A photo of a listing. The bytes live in the file-storage backend (re-encoded, no EXIF)."""

    __tablename__ = "marketplace_listing_photos"
    __table_args__ = (
        UniqueConstraint("listing_id", "position", name="uq_marketplace_photos_listing_position"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("length(sha256) = 64", name="sha256_hex_length"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    listing_id: Mapped[uuid.UUID] = fk_uuid("marketplace_listings.id", ondelete="CASCADE")
    uploaded_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200))
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)


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
