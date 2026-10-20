"""Enforce append-only behaviour of the chain-of-custody and reward ledgers in the database.

Revision ID: 0007
Revises: 0006

``custody_events`` and ``reward_ledger_entries`` are documented as append-only. Application code
never updates or deletes them, but a documented rule is not a guarantee: these triggers make
any UPDATE or DELETE fail, so a bug, a script or a manual statement cannot rewrite history.
Corrections are new rows (a reversal or adjustment entry, a further custody event).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("custody_events", "reward_ledger_entries")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_ledger_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation()"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_ledger_mutation()")
