"""Surplus marketplace: listings, requests and their permissions.

Revision ID: 0010
Revises: 0009

The permission and role-grant rows are literal copies of what ``app.modules.users.rbac`` defines for
the marketplace at this revision (migrations never import application code).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "marketplace:read": "Browse surplus-material listings",
    "marketplace:request": "Ask for a surplus-material listing",
    "marketplace:create": "Offer surplus material in the marketplace",
    "marketplace:manage": "Moderate and act on any marketplace listing",
}
GRANTS = {
    "citizen": ("marketplace:read", "marketplace:request"),
    "collector": ("marketplace:read", "marketplace:request"),
    "facility_operator": ("marketplace:read", "marketplace:request", "marketplace:create"),
    "manager": (
        "marketplace:read",
        "marketplace:request",
        "marketplace:create",
        "marketplace:manage",
    ),
    "administrator": tuple(PERMISSIONS),
}


def _id_and_timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "marketplace_listings",
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "plastics",
                "metals",
                "paper",
                "glass",
                "e_waste",
                "organics",
                "textiles",
                "wood",
                "furniture",
                "other",
                name="listingcategory",
                native_enum=False,
                length=17,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "unit",
            sa.Enum("kg", "units", name="listingunit", native_enum=False, length=13),
            nullable=False,
        ),
        sa.Column(
            "condition",
            sa.Enum(
                "like_new",
                "good",
                "fair",
                "damaged",
                name="listingcondition",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("pickup_city", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "published",
                "reserved",
                "closed",
                name="listingstatus",
                native_enum=False,
                length=17,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=500), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint(
            "category IN ('plastics', 'metals', 'paper', 'glass', 'e_waste', 'organics', "
            "'textiles', 'wood', 'furniture', 'other')",
            name=op.f("ck_marketplace_listings_category_valid"),
        ),
        sa.CheckConstraint(
            "unit IN ('kg', 'units')", name=op.f("ck_marketplace_listings_unit_valid")
        ),
        sa.CheckConstraint(
            "condition IN ('like_new', 'good', 'fair', 'damaged')",
            name=op.f("ck_marketplace_listings_condition_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'reserved', 'closed')",
            name=op.f("ck_marketplace_listings_status_valid"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_marketplace_listings_quantity_positive")),
        sa.CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)",
            name=op.f("ck_marketplace_listings_closed_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "(status IN ('published', 'reserved', 'closed')) OR published_at IS NULL",
            name=op.f("ck_marketplace_listings_published_timestamp_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_marketplace_listings_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_marketplace_listings_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketplace_listings")),
    )
    for column in ("created_by_id", "facility_id", "category", "status"):
        op.create_index(op.f(f"ix_marketplace_listings_{column}"), "marketplace_listings", [column])

    op.create_table(
        "marketplace_requests",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "declined",
                "withdrawn",
                name="requeststatus",
                native_enum=False,
                length=17,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'withdrawn')",
            name=op.f("ck_marketplace_requests_status_valid"),
        ),
        sa.CheckConstraint(
            "(status IN ('pending')) = (decided_at IS NULL)",
            name=op.f("ck_marketplace_requests_decision_timestamp_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["marketplace_listings.id"],
            name=op.f("fk_marketplace_requests_listing_id_marketplace_listings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_marketplace_requests_requester_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketplace_requests")),
        sa.UniqueConstraint(
            "listing_id", "requester_id", name="uq_marketplace_requests_listing_requester"
        ),
    )
    for column in ("listing_id", "requester_id", "status"):
        op.create_index(op.f(f"ix_marketplace_requests_{column}"), "marketplace_requests", [column])

    conn = op.get_bind()
    for code, description in PERMISSIONS.items():
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, description) VALUES (:code, :description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "description": description},
        )
    for role, codes in GRANTS.items():
        for code in codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.name = :role AND p.code = :code ON CONFLICT DO NOTHING"
                ),
                {"role": role, "code": code},
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(PERMISSIONS)}
    )
    op.drop_table("marketplace_requests")
    op.drop_table("marketplace_listings")
