"""create roles table

Revision ID: 16320f5646e9
Revises: None
Create Date: 2026-08-22 21:54:11.243869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "16320f5646e9"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_roles_id", "roles", ["id"], unique=False)
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.Integer()),
            sa.column("name", sa.String(length=50)),
        ),
        [
            {"id": 4, "name": "admin"},
            {"id": 5, "name": "citizen"},
            {"id": 6, "name": "collector"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
