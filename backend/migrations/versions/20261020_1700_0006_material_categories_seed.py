"""Seed the four taxonomy categories that migration 0004 does not create.

Revision ID: 0006
Revises: 0005

Migration 0004 seeds the six categories the active model predicts; together with these four the
codes match the ten-class taxonomy in ``docs/ml/dataset-research``. Only names and one-line
descriptions are seeded: no sorting rules are invented here (administrators add guidance with its
source). The downgrade removes a category only when nothing references it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("organic", "Organic and food waste", "Food scraps and other biodegradable waste."),
    ("textile", "Textiles", "Clothing, fabric and other textile waste."),
    ("e_waste", "Electronic waste", "Electrical and electronic equipment, cables and batteries."),
    ("medical", "Medical waste", "Syringes, masks, gloves and medicines: special handling."),
)

_DELETE_IF_UNUSED = sa.text(
    "DELETE FROM material_categories c WHERE c.code = :code "
    "AND NOT EXISTS (SELECT 1 FROM sorting_guidance t WHERE t.material_category_id = c.id) "
    "AND NOT EXISTS (SELECT 1 FROM recovery_records t WHERE t.material_category_id = c.id) "
    "AND NOT EXISTS (SELECT 1 FROM material_passports t WHERE t.material_category_id = c.id) "
    "AND NOT EXISTS (SELECT 1 FROM forecast_results t WHERE t.material_category_id = c.id) "
    "AND NOT EXISTS (SELECT 1 FROM anomaly_alerts t WHERE t.material_category_id = c.id)"
)


def upgrade() -> None:
    conn = op.get_bind()
    for code, name, description in CATEGORIES:
        conn.execute(
            sa.text(
                "INSERT INTO material_categories (code, name, description, is_active) "
                "VALUES (:code, :name, :description, true) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "description": description},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for code, _, _ in CATEGORIES:
        conn.execute(_DELETE_IF_UNUSED, {"code": code})
