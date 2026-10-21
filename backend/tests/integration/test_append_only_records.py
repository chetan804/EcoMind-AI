"""FR-AUD-1 and FR-COL-3: the audit log and the collection status history cannot be rewritten (migration 0017)."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


@pytest.fixture
def conn(migrated_engine: Engine) -> Iterator[Connection]:
    with migrated_engine.connect() as connection:
        yield connection
        connection.rollback()


def new_user(conn: Connection, email: str) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name) VALUES (:e, 'x', 'N') RETURNING id"
                ),
                {"e": email},
            ).scalar_one()
        )
    )


def new_audit_row(conn: Connection, actor: uuid.UUID | None) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO audit_logs (actor_id, action, entity_type) "
                    "VALUES (:a, 'thing.done', 'thing') RETURNING id"
                ),
                {"a": actor},
            ).scalar_one()
        )
    )


def refused(conn: Connection, statement: str, **params: object) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        conn.execute(text(statement), params)
    conn.rollback()


def test_audit_rows_cannot_be_updated_or_deleted(conn: Connection) -> None:
    actor = new_user(conn, "actor@example.org")
    row = new_audit_row(conn, actor)
    conn.commit()
    refused(conn, "UPDATE audit_logs SET action = 'tampered' WHERE id = :i", i=row)
    refused(conn, "UPDATE audit_logs SET changes = '{}'::jsonb WHERE id = :i", i=row)
    refused(
        conn, "UPDATE audit_logs SET occurred_at = now() - interval '1 day' WHERE id = :i", i=row
    )
    refused(conn, "DELETE FROM audit_logs WHERE id = :i", i=row)
    assert (
        conn.execute(text("SELECT action FROM audit_logs WHERE id = :i"), {"i": row}).scalar_one()
        == "thing.done"
    )


def test_the_actor_can_only_be_detached_not_swapped_or_combined_with_another_change(
    conn: Connection,
) -> None:
    first, second = new_user(conn, "one@example.org"), new_user(conn, "two@example.org")
    row = new_audit_row(conn, first)
    conn.commit()
    refused(
        conn, "UPDATE audit_logs SET actor_id = :b WHERE id = :i", b=second, i=row
    )  # attribute to someone else
    refused(
        conn, "UPDATE audit_logs SET actor_id = NULL, action = 'x' WHERE id = :i", i=row
    )  # detach and edit
    nobody = new_audit_row(conn, None)
    conn.commit()
    refused(
        conn, "UPDATE audit_logs SET actor_id = :a WHERE id = :i", a=first, i=nobody
    )  # attach afterwards


def test_removing_a_user_detaches_their_audit_rows_but_keeps_them(conn: Connection) -> None:
    actor = new_user(conn, "leaver@example.org")
    row = new_audit_row(conn, actor)
    conn.commit()
    conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": actor})
    conn.commit()
    found = conn.execute(
        text("SELECT actor_id, action FROM audit_logs WHERE id = :i"), {"i": row}
    ).one()
    assert found.actor_id is None and found.action == "thing.done"


def test_status_history_is_append_only_but_can_be_added_to(conn: Connection) -> None:
    user = new_user(conn, "mgr@example.org")
    task = conn.execute(
        text("INSERT INTO collection_tasks (created_by_id, title) VALUES (:u, 'T') RETURNING id"),
        {"u": user},
    ).scalar_one()
    history = conn.execute(
        text(
            "INSERT INTO collection_task_status_history (collection_task_id, to_status, changed_by_id) "
            "VALUES (:t, 'pending', :u) RETURNING id"
        ),
        {"t": task, "u": user},
    ).scalar_one()
    conn.commit()
    refused(
        conn,
        "UPDATE collection_task_status_history SET to_status = 'completed' WHERE id = :i",
        i=history,
    )
    refused(conn, "DELETE FROM collection_task_status_history WHERE id = :i", i=history)
    refused(
        conn, "DELETE FROM collection_tasks WHERE id = :t", t=task
    )  # would cascade into the history
    conn.execute(
        text(
            "INSERT INTO collection_task_status_history (collection_task_id, from_status, to_status, changed_by_id) "
            "VALUES (:t, 'pending', 'assigned', :u)"
        ),
        {"t": task, "u": user},
    )
    conn.commit()
    count = conn.execute(
        text("SELECT count(*) FROM collection_task_status_history WHERE collection_task_id = :t"),
        {"t": task},
    ).scalar_one()
    assert count == 2
