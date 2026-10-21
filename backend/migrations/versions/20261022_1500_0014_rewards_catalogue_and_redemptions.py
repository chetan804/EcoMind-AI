"""Rewards catalogue and redemptions, and the ``rewards:redeem`` permission.

Revision ID: 0014
Revises: 0013

The ledger stays append-only. A redemption is a negative ``redeemed`` ledger entry (and a positive
``reversal`` when it is cancelled), so ``reward_ledger_entries.source_type`` gains the value
``reward_redemption``. No catalogue rows are seeded: staff enter the rewards, nothing is invented.

The permission and role-grant rows are literal copies of what ``app.modules.users.rbac`` defines
for rewards at this revision (migrations never import application code).

Downgrade is refused once redemptions exist: the ledger cannot be edited, and removing the source
type would leave its entries invalid.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PERMISSIONS = {"rewards:redeem": "Spend reward points on catalogue items"}
GRANTS = {"citizen": ("rewards:redeem",), "administrator": ("rewards:redeem",)}
SOURCES_BEFORE = (
    "'waste_report', 'collection_task', 'recovery_record', 'community_incident', 'manual'"
)
SOURCES_AFTER = SOURCES_BEFORE + ", 'reward_redemption'"
SOURCE_CHECK = "ck_reward_ledger_entries_source_type_valid"


def _set_source_check(allowed: str) -> None:
    op.drop_constraint(op.f(SOURCE_CHECK), "reward_ledger_entries", type_="check")
    op.create_check_constraint(
        op.f(SOURCE_CHECK), "reward_ledger_entries", f"source_type IN ({allowed})"
    )


def upgrade() -> None:
    _set_source_check(SOURCES_AFTER)
    op.create_table(
        "reward_items",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points_cost", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("max_per_user", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
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
            "max_per_user IS NULL OR max_per_user >= 1", name=op.f("ck_reward_items_limit_positive")
        ),
        sa.CheckConstraint("points_cost > 0", name=op.f("ck_reward_items_cost_positive")),
        sa.CheckConstraint(
            "stock IS NULL OR stock >= 0", name=op.f("ck_reward_items_stock_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_reward_items_created_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reward_items")),
    )
    op.create_index(op.f("ix_reward_items_active"), "reward_items", ["active"], unique=False)
    op.create_index(
        op.f("ix_reward_items_created_by_id"), "reward_items", ["created_by_id"], unique=False
    )
    op.create_table(
        "reward_redemptions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("item_name", sa.String(length=120), nullable=False),
        sa.Column("points_spent", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("client_request_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "fulfilled",
                "cancelled",
                name="redemptionstatus",
                native_enum=False,
                length=17,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("ledger_entry_id", sa.UUID(), nullable=False),
        sa.Column("refund_entry_id", sa.UUID(), nullable=True),
        sa.Column("fulfilled_by_id", sa.UUID(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by_id", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
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
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name=op.f("ck_reward_redemptions_cancelled_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') = (refund_entry_id IS NOT NULL)",
            name=op.f("ck_reward_redemptions_refund_iff_cancelled"),
        ),
        sa.CheckConstraint(
            "(status = 'fulfilled') = (fulfilled_at IS NOT NULL)",
            name=op.f("ck_reward_redemptions_fulfilled_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'fulfilled', 'cancelled')",
            name=op.f("ck_reward_redemptions_status_valid"),
        ),
        sa.CheckConstraint("points_spent > 0", name=op.f("ck_reward_redemptions_points_positive")),
        sa.ForeignKeyConstraint(
            ["cancelled_by_id"],
            ["users.id"],
            name=op.f("fk_reward_redemptions_cancelled_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["fulfilled_by_id"],
            ["users.id"],
            name=op.f("fk_reward_redemptions_fulfilled_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["reward_items.id"],
            name=op.f("fk_reward_redemptions_item_id_reward_items"),
        ),
        sa.ForeignKeyConstraint(
            ["ledger_entry_id"],
            ["reward_ledger_entries.id"],
            name=op.f("fk_reward_redemptions_ledger_entry_id_reward_ledger_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["refund_entry_id"],
            ["reward_ledger_entries.id"],
            name=op.f("fk_reward_redemptions_refund_entry_id_reward_ledger_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_reward_redemptions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reward_redemptions")),
        sa.UniqueConstraint("code", name=op.f("uq_reward_redemptions_code")),
        sa.UniqueConstraint(
            "user_id", "client_request_id", name="uq_reward_redemptions_user_client_request"
        ),
    )
    op.create_index(
        op.f("ix_reward_redemptions_cancelled_by_id"),
        "reward_redemptions",
        ["cancelled_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reward_redemptions_fulfilled_by_id"),
        "reward_redemptions",
        ["fulfilled_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reward_redemptions_item_id"), "reward_redemptions", ["item_id"], unique=False
    )
    op.create_index(
        op.f("ix_reward_redemptions_ledger_entry_id"),
        "reward_redemptions",
        ["ledger_entry_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_reward_redemptions_refund_entry_id"),
        "reward_redemptions",
        ["refund_entry_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_reward_redemptions_status"), "reward_redemptions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_reward_redemptions_user_id"), "reward_redemptions", ["user_id"], unique=False
    )

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
    if conn.execute(sa.text("SELECT count(*) FROM reward_redemptions")).scalar_one():
        raise RuntimeError(
            "Cannot downgrade 0014: redemptions exist and the append-only ledger holds their "
            "entries. Restore from a backup taken before the upgrade instead."
        )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(PERMISSIONS)}
    )
    op.drop_index(op.f("ix_reward_redemptions_user_id"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_status"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_refund_entry_id"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_ledger_entry_id"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_item_id"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_fulfilled_by_id"), table_name="reward_redemptions")
    op.drop_index(op.f("ix_reward_redemptions_cancelled_by_id"), table_name="reward_redemptions")
    op.drop_table("reward_redemptions")
    op.drop_index(op.f("ix_reward_items_created_by_id"), table_name="reward_items")
    op.drop_index(op.f("ix_reward_items_active"), table_name="reward_items")
    op.drop_table("reward_items")
    _set_source_check(SOURCES_BEFORE)
