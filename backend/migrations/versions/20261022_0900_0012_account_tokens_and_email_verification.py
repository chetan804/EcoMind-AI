"""Account tokens (password reset, e-mail verification) and ``users.email_verified_at``.

Revision ID: 0012
Revises: 0011

``account_tokens`` stores only the SHA-256 digest of each one-time token. Existing accounts keep
``email_verified_at`` NULL on purpose: nobody has proved control of those mailboxes, so the
migration does not claim they did (see docs/operations/account-recovery.md for enabling
EMAIL_VERIFICATION_REQUIRED on a system that already has users).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "password_reset",
                "email_verification",
                name="accounttokenpurpose",
                native_enum=False,
                length=26,
            ),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('password_reset', 'email_verification')",
            name=op.f("ck_account_tokens_purpose_valid"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_account_tokens_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_account_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_account_tokens_token_hash")),
    )
    op.create_index(op.f("ix_account_tokens_user_id"), "account_tokens", ["user_id"], unique=False)
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_index(op.f("ix_account_tokens_user_id"), table_name="account_tokens")
    op.drop_table("account_tokens")
