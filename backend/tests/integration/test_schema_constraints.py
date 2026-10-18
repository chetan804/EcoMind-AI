"""Database-level rules that must hold regardless of application code."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


@pytest.fixture
def conn(migrated_engine: Engine) -> Iterator[Connection]:
    with migrated_engine.connect() as connection:
        yield connection
        connection.rollback()


def new_user(conn: Connection, email: str = "a@example.org") -> uuid.UUID:
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


def new_facility(conn: Connection, code: str = "F1") -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO facilities (code, name, facility_type) VALUES (:c, 'F', 'depot') RETURNING id"
                ),
                {"c": code},
            ).scalar_one()
        )
    )


def new_category(conn: Connection, code: str = "pet") -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO material_categories (code, name) VALUES (:c, 'PET') RETURNING id"
                ),
                {"c": code},
            ).scalar_one()
        )
    )


def test_defaults_are_generated_by_the_database(conn: Connection) -> None:
    row = conn.execute(
        text(
            "INSERT INTO users (email, password_hash, full_name) VALUES ('d@example.org','x','D') "
            "RETURNING id, is_active, created_at, updated_at"
        )
    ).one()
    assert row.id is not None and row.is_active is True
    assert row.created_at is not None and row.created_at.tzinfo is not None


def test_email_is_unique_case_insensitively(conn: Connection) -> None:
    new_user(conn, "Person@Example.org")
    with pytest.raises(IntegrityError):
        new_user(conn, "person@example.ORG")


def test_invalid_enum_value_is_rejected(conn: Connection) -> None:
    with pytest.raises(IntegrityError, match="facility_type_valid"):
        conn.execute(
            text("INSERT INTO facilities (code, name, facility_type) VALUES ('X','X','castle')")
        )


def test_coordinates_are_range_checked_and_paired(conn: Connection) -> None:
    with pytest.raises(IntegrityError, match="latitude_range"):
        conn.execute(
            text(
                "INSERT INTO facilities (code,name,facility_type,latitude,longitude) VALUES ('A','A','depot',91,0)"
            )
        )
    conn.rollback()
    with pytest.raises(IntegrityError, match="geo_point_complete"):
        conn.execute(
            text(
                "INSERT INTO facilities (code,name,facility_type,latitude) VALUES ('B','B','depot',10)"
            )
        )


def test_recovered_weight_cannot_exceed_input_weight(conn: Connection) -> None:
    user, facility, category = new_user(conn), new_facility(conn), new_category(conn)
    insert = text(
        "INSERT INTO recovery_records (facility_id, material_category_id, recovery_method, input_weight_kg,"
        " recovered_weight_kg, processed_at, created_by_id) VALUES (:f, :c, 'recycled', 10, :r, now(), :u)"
    )
    params = {"f": facility, "c": category, "u": user}
    conn.execute(insert, {**params, "r": 10})
    with pytest.raises(IntegrityError, match="recovered_within_input"):
        conn.execute(insert, {**params, "r": 10.001})


def test_verified_recovery_requires_verifier_and_timestamp(conn: Connection) -> None:
    user, facility, category = new_user(conn), new_facility(conn), new_category(conn)
    with pytest.raises(IntegrityError, match="verification_timestamp_consistent"):
        conn.execute(
            text(
                "INSERT INTO recovery_records (facility_id, material_category_id, recovery_method, input_weight_kg,"
                " recovered_weight_kg, processed_at, created_by_id, verification_status)"
                " VALUES (:f, :c, 'recycled', 10, 5, now(), :u, 'verified')"
            ),
            {"f": facility, "c": category, "u": user},
        )


def test_route_stop_targets_exactly_one_of_task_or_facility(conn: Connection) -> None:
    user, facility = new_user(conn), new_facility(conn)
    plan = conn.execute(
        text(
            "INSERT INTO route_plans (name, planned_date, created_by_id) VALUES ('R', current_date, :u) RETURNING id"
        ),
        {"u": user},
    ).scalar_one()
    conn.execute(
        text("INSERT INTO route_stops (route_plan_id, sequence, facility_id) VALUES (:p, 1, :f)"),
        {"p": plan, "f": facility},
    )
    with pytest.raises(IntegrityError, match="exactly_one_target"):
        conn.execute(
            text("INSERT INTO route_stops (route_plan_id, sequence) VALUES (:p, 2)"), {"p": plan}
        )
    conn.rollback()


def test_route_stop_sequence_is_unique_within_a_plan(conn: Connection) -> None:
    user, facility = new_user(conn), new_facility(conn)
    plan = conn.execute(
        text(
            "INSERT INTO route_plans (name, planned_date, created_by_id) VALUES ('R', current_date, :u) RETURNING id"
        ),
        {"u": user},
    ).scalar_one()
    stop = text("INSERT INTO route_stops (route_plan_id, sequence, facility_id) VALUES (:p, 1, :f)")
    conn.execute(stop, {"p": plan, "f": facility})
    with pytest.raises(IntegrityError, match="uq_route_stops_route_plan_id_sequence"):
        conn.execute(stop, {"p": plan, "f": facility})


def test_only_one_active_assignment_per_collection_task(conn: Connection) -> None:
    user = new_user(conn)
    task = conn.execute(
        text("INSERT INTO collection_tasks (created_by_id, title) VALUES (:u, 'T') RETURNING id"),
        {"u": user},
    ).scalar_one()
    assign = text(
        "INSERT INTO collection_assignments (collection_task_id, assignee_id, assigned_by_id) VALUES (:t, :u, :u)"
    )
    conn.execute(assign, {"t": task, "u": user})
    with pytest.raises(IntegrityError, match="uq_collection_assignments_active_task"):
        conn.execute(assign, {"t": task, "u": user})
    conn.rollback()


def test_ended_assignment_allows_a_new_one(conn: Connection) -> None:
    user = new_user(conn)
    task = conn.execute(
        text("INSERT INTO collection_tasks (created_by_id, title) VALUES (:u, 'T') RETURNING id"),
        {"u": user},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO collection_assignments (collection_task_id, assignee_id, assigned_by_id, unassigned_at)"
            " VALUES (:t, :u, :u, now())"
        ),
        {"t": task, "u": user},
    )
    conn.execute(
        text(
            "INSERT INTO collection_assignments (collection_task_id, assignee_id, assigned_by_id) VALUES (:t, :u, :u)"
        ),
        {"t": task, "u": user},
    )


def test_earned_ledger_entries_are_idempotent_per_source(conn: Connection) -> None:
    user, source = new_user(conn), uuid.uuid4()
    earn = text(
        "INSERT INTO reward_ledger_entries (user_id, entry_type, points, source_type, source_id)"
        " VALUES (:u, 'earned', 10, 'waste_report', :s)"
    )
    conn.execute(earn, {"u": user, "s": source})
    with pytest.raises(IntegrityError, match="uq_reward_ledger_entries_idempotency"):
        conn.execute(earn, {"u": user, "s": source})


def test_ledger_rejects_zero_points_and_orphan_reversals(conn: Connection) -> None:
    user = new_user(conn)
    with pytest.raises(IntegrityError, match="points_non_zero"):
        conn.execute(
            text(
                "INSERT INTO reward_ledger_entries (user_id, entry_type, points, source_type) VALUES (:u,'adjustment',0,'manual')"
            ),
            {"u": user},
        )
    conn.rollback()
    with pytest.raises(IntegrityError, match="reversal_references_entry"):
        conn.execute(
            text(
                "INSERT INTO reward_ledger_entries (user_id, entry_type, points, source_type) VALUES (:u,'reversal',-5,'manual')"
            ),
            {"u": user},
        )


def test_prediction_review_fields_must_be_consistent(conn: Connection) -> None:
    user, category = new_user(conn), new_category(conn)
    media = conn.execute(
        text(
            "INSERT INTO media_assets (uploaded_by_id, storage_backend, storage_key, content_type, size_bytes, sha256)"
            " VALUES (:u, 'local', 'k1', 'image/png', 10, :h) RETURNING id"
        ),
        {"u": user, "h": "a" * 64},
    ).scalar_one()
    model = conn.execute(
        text(
            "INSERT INTO classification_model_versions (name, version) VALUES ('m', '1') RETURNING id"
        )
    ).scalar_one()
    insert = text(
        "INSERT INTO classification_predictions (media_asset_id, model_version_id, material_category_id,"
        " material_confidence, review_status, reviewed_at) VALUES (:m, :v, :c, :conf, :s, :r)"
    )
    base = {"m": media, "v": model, "c": category}
    with pytest.raises(IntegrityError, match="material_confidence_range"):
        conn.execute(insert, {**base, "conf": 1.5, "s": "unreviewed", "r": None})
    conn.rollback()


def test_forecast_interval_and_period_ordering(conn: Connection) -> None:
    with pytest.raises(IntegrityError, match="period_ordered"):
        conn.execute(
            text(
                "INSERT INTO forecast_results (metric, unit, granularity, period_start, period_end, predicted_value,"
                " model_name, model_version, generated_at) VALUES ('w','kg','day', now(), now(), 1, 'baseline','1', now())"
            )
        )


def test_anomaly_alert_requires_an_explanation(conn: Connection) -> None:
    with pytest.raises(IntegrityError, match="explanation_required"):
        conn.execute(
            text(
                "INSERT INTO anomaly_alerts (metric, unit, severity, window_start, window_end, observed_value,"
                " expected_value, detector_name, detector_version, explanation, detected_at)"
                " VALUES ('w','kg','warning', now() - interval '1 day', now(), 1, 1, 'd', '1', '', now())"
            )
        )


def test_deleting_a_user_with_history_is_restricted(conn: Connection) -> None:
    user = new_user(conn)
    conn.execute(
        text("INSERT INTO waste_reports (reporter_id, title) VALUES (:u, 'pile')"), {"u": user}
    )
    with pytest.raises(IntegrityError):
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
