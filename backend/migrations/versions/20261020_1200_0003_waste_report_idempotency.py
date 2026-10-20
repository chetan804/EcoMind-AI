"""Idempotency key and request fingerprint on waste reports.

Revision ID: 0003
Revises: 0002

Lets a client retry ``POST /waste-reports`` (flaky mobile network, double click) without creating
a duplicate: the key is unique per reporter. Existing rows keep NULL for both columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "waste_reports", sa.Column("idempotency_key", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "waste_reports", sa.Column("request_fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_check_constraint(
        "idempotency_complete",
        "waste_reports",
        "(idempotency_key IS NULL) = (request_fingerprint IS NULL)",
    )
    op.create_unique_constraint(
        "uq_waste_reports_reporter_id_idempotency_key",
        "waste_reports",
        ["reporter_id", "idempotency_key"],
    )


def downgrade() -> None:
    # The naming convention prefixes check constraints itself, so pass the short name here.
    op.drop_constraint(
        "uq_waste_reports_reporter_id_idempotency_key", "waste_reports", type_="unique"
    )
    op.drop_constraint("idempotency_complete", "waste_reports", type_="check")
    op.drop_column("waste_reports", "request_fingerprint")
    op.drop_column("waste_reports", "idempotency_key")
