"""add optional waste report image path

Revision ID: a1e5c8d2f904
Revises: 9c4e7b1a2d6f
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1e5c8d2f904"
down_revision: Union[str, Sequence[str], None] = "9c4e7b1a2d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "waste_reports",
        sa.Column("image_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("waste_reports", "image_path")