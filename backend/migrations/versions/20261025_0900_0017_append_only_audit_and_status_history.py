"""Enforce append-only behaviour of the audit log and the collection status history in the database.

Revision ID: 0017
Revises: 0016

Found by the requirements review: FR-AUD-1 and FR-COL-3 say these records are append-only, and
application code never changes them, but only ``custody_events`` and ``reward_ledger_entries`` (migration
0007) and ``vehicle_location_events`` (0011) had a database guarantee. Now an UPDATE or DELETE on
``audit_logs`` or ``collection_task_status_history`` fails, so a bug, a script or a manual statement cannot
rewrite who did what.

One exception, deliberate: ``audit_logs.actor_id`` is a foreign key with ``ON DELETE SET NULL``. If a user
row is ever removed (for example to honour an erasure request) the database must be able to detach the
person from their audit rows, so an UPDATE is allowed when it changes nothing except setting ``actor_id`` to
NULL. Every other change, and every DELETE, is refused. TRUNCATE is not covered by row triggers; deny it by
privilege (the application role needs no TRUNCATE).

The history table keeps its ``ON DELETE CASCADE`` from collection tasks, which the trigger turns into a
refusal: a task that has history cannot be deleted. The application never deletes tasks.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND NEW.actor_id IS NULL
               AND OLD.actor_id IS NOT NULL
               AND (to_jsonb(NEW) - 'actor_id') = (to_jsonb(OLD) - 'actor_id') THEN
                RETURN NEW;  -- ON DELETE SET NULL of the actor: the only permitted change
            END IF;
            RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()"
    )
    # prevent_ledger_mutation() was created by 0007 and is shared.
    op.execute(
        "CREATE TRIGGER collection_task_status_history_append_only BEFORE UPDATE OR DELETE "
        "ON collection_task_status_history FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS collection_task_status_history_append_only ON collection_task_status_history"
    )
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
