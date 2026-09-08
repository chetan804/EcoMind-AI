"""add AI metadata and operation logs

Revision ID: b82d1f6a4c90
Revises: a68c2d9f4e71
Create Date: 2026-09-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b82d1f6a4c90"
down_revision: Union[str, Sequence[str], None] = "a68c2d9f4e71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    report_columns = [
        sa.Column("ai_model_name", sa.String(length=120), nullable=True),
        sa.Column("ai_model_version", sa.String(length=50), nullable=True),
        sa.Column("ai_provider", sa.String(length=80), nullable=True),
        sa.Column("ai_inference_ms", sa.Float(), nullable=True),
        sa.Column("ai_created_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in report_columns:
        op.add_column("waste_reports", column)

    complaint_columns = [
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("ai_category", sa.String(length=50), nullable=True),
        sa.Column("ai_priority", sa.String(length=20), nullable=True),
        sa.Column("ai_keywords", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_model_name", sa.String(length=120), nullable=True),
        sa.Column("ai_model_version", sa.String(length=50), nullable=True),
        sa.Column("ai_created_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in complaint_columns:
        op.add_column("complaints", column)

    op.create_table(
        "ai_operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("input_type", sa.String(length=40), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_operation_logs_id", "ai_operation_logs", ["id"], unique=False)
    op.create_index("ix_ai_operation_logs_operation", "ai_operation_logs", ["operation"])


def downgrade() -> None:
    op.drop_index("ix_ai_operation_logs_operation", table_name="ai_operation_logs")
    op.drop_index("ix_ai_operation_logs_id", table_name="ai_operation_logs")
    op.drop_table("ai_operation_logs")

    for column in [
        "ai_created_at",
        "ai_model_version",
        "ai_model_name",
        "ai_confidence",
        "ai_keywords",
        "ai_priority",
        "ai_category",
        "longitude",
        "latitude",
        "title",
    ]:
        op.drop_column("complaints", column)

    for column in [
        "ai_created_at",
        "ai_inference_ms",
        "ai_provider",
        "ai_model_version",
        "ai_model_name",
    ]:
        op.drop_column("waste_reports", column)
