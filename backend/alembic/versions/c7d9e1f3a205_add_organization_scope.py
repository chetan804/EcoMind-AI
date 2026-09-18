"""add organization scope foundation

Revision ID: c7d9e1f3a205
Revises: a1e5c8d2f904
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d9e1f3a205"
down_revision: Union[str, Sequence[str], None] = "a1e5c8d2f904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"], unique=False)
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_users_organization_id", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"], unique=False)

    with op.batch_alter_table("waste_reports") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_waste_reports_organization_id", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_waste_reports_organization_id", "waste_reports", ["organization_id"], unique=False)

    with op.batch_alter_table("complaints") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_complaints_organization_id", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_complaints_organization_id", "complaints", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_complaints_organization_id", table_name="complaints")
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_constraint("fk_complaints_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")
    op.drop_index("ix_waste_reports_organization_id", table_name="waste_reports")
    with op.batch_alter_table("waste_reports") as batch_op:
        batch_op.drop_constraint("fk_waste_reports_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")
    op.drop_index("ix_users_organization_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")