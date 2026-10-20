"""Classification runtime: richer predictions, one active model, material-category seed.

Revision ID: 0004
Revises: 0003

* ``classification_predictions`` gains what a real inference returns and a reviewer needs: the
  needs-review decision and its reasons, the calibrated class distribution, the similarity to the
  training set and the inference latency. No rows exist yet (there was no inference API).
* A partial unique index guarantees at most one ``active`` model version.
* The six material categories the waste classifier predicts are seeded (idempotent).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = [
    ("cardboard", "Cardboard", "Corrugated and flat cardboard, boxes and card packaging."),
    ("glass", "Glass", "Glass bottles, jars and broken glass."),
    ("metal", "Metal", "Metal cans, tins, foil and other metal objects."),
    ("paper", "Paper", "Paper, newspaper, magazines and paper packaging."),
    ("plastic", "Plastic", "Plastic bottles, containers, bags and packaging."),
    (
        "trash",
        "Residual / other waste",
        "Items that do not fit the other five material classes (the dataset's 'trash' class).",
    ),
]


def upgrade() -> None:
    op.add_column(
        "classification_predictions",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "classification_predictions",
        sa.Column(
            "review_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "classification_predictions",
        sa.Column(
            "class_probabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "classification_predictions",
        sa.Column("novelty_similarity", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "classification_predictions",
        sa.Column("inference_ms", sa.Numeric(8, 1), nullable=True),
    )
    op.create_index(
        "uq_classification_model_versions_one_active",
        "classification_model_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    for code, name, description in CATEGORIES:
        op.execute(
            sa.text(
                "INSERT INTO material_categories (id, code, name, description, is_active) "
                "VALUES (gen_random_uuid(), :code, :name, :description, true) "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code, name=name, description=description)
        )


def downgrade() -> None:
    # Categories are only removed when nothing references them; otherwise the FK stops the
    # downgrade rather than silently orphaning data.
    for code, _, _ in CATEGORIES:
        op.execute(
            sa.text("DELETE FROM material_categories WHERE code = :code").bindparams(code=code)
        )
    op.drop_index(
        "uq_classification_model_versions_one_active",
        table_name="classification_model_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    for column in (
        "inference_ms",
        "novelty_similarity",
        "class_probabilities",
        "review_reasons",
        "needs_review",
    ):
        op.drop_column("classification_predictions", column)
