"""Marketplace: listing expiry, close outcome and listing photos.

Revision ID: 0013
Revises: 0012

``expires_at`` is backfilled for listings that are on offer today (published or reserved): they
get 30 days from the migration, so deploying this never closes an existing listing at once. The
outcome of listings closed earlier stays NULL: it was never recorded and is not guessed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "marketplace_listings", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "marketplace_listings",
        sa.Column("expiry_notice_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "marketplace_listings",
        sa.Column(
            "outcome",
            sa.Enum(
                "handed_over",
                "withdrawn",
                "expired",
                name="listingoutcome",
                native_enum=False,
                length=19,
            ),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE marketplace_listings SET expires_at = now() + interval '30 days' "
        "WHERE status IN ('published', 'reserved')"
    )
    op.create_index(
        op.f("ix_marketplace_listings_expires_at"), "marketplace_listings", ["expires_at"]
    )
    op.create_check_constraint(
        op.f("ck_marketplace_listings_outcome_valid"),
        "marketplace_listings",
        "outcome IN ('handed_over', 'withdrawn', 'expired')",
    )
    op.create_check_constraint(
        op.f("ck_marketplace_listings_expiry_needs_publication"),
        "marketplace_listings",
        "expires_at IS NULL OR published_at IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_marketplace_listings_outcome_only_when_closed"),
        "marketplace_listings",
        "outcome IS NULL OR status = 'closed'",
    )

    op.create_table(
        "marketplace_listing_photos",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(length=200), nullable=True),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_marketplace_listing_photos_position_non_negative")
        ),
        sa.CheckConstraint(
            "size_bytes > 0", name=op.f("ck_marketplace_listing_photos_size_positive")
        ),
        sa.CheckConstraint(
            "length(sha256) = 64", name=op.f("ck_marketplace_listing_photos_sha256_hex_length")
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["marketplace_listings.id"],
            name=op.f("fk_marketplace_listing_photos_listing_id_marketplace_listings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_marketplace_listing_photos_uploaded_by_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketplace_listing_photos")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_marketplace_listing_photos_storage_key")),
        sa.UniqueConstraint(
            "listing_id", "position", name=op.f("uq_marketplace_photos_listing_position")
        ),
    )
    op.create_index(
        op.f("ix_marketplace_listing_photos_listing_id"),
        "marketplace_listing_photos",
        ["listing_id"],
    )
    op.create_index(
        op.f("ix_marketplace_listing_photos_uploaded_by_id"),
        "marketplace_listing_photos",
        ["uploaded_by_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_marketplace_listing_photos_uploaded_by_id"),
        table_name="marketplace_listing_photos",
    )
    op.drop_index(
        op.f("ix_marketplace_listing_photos_listing_id"), table_name="marketplace_listing_photos"
    )
    op.drop_table("marketplace_listing_photos")
    op.drop_constraint(
        op.f("ck_marketplace_listings_outcome_only_when_closed"),
        "marketplace_listings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_marketplace_listings_expiry_needs_publication"),
        "marketplace_listings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_marketplace_listings_outcome_valid"), "marketplace_listings", type_="check"
    )
    op.drop_index(op.f("ix_marketplace_listings_expires_at"), table_name="marketplace_listings")
    op.drop_column("marketplace_listings", "outcome")
    op.drop_column("marketplace_listings", "expiry_notice_sent_at")
    op.drop_column("marketplace_listings", "expires_at")
