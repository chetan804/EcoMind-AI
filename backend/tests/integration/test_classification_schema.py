from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from tests.fixtures.database import downgrade, upgrade

CODES = {"cardboard", "glass", "metal", "paper", "plastic", "trash"}


def _codes(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        return {r[0] for r in connection.execute(text("SELECT code FROM material_categories"))}


def test_migration_seeds_the_six_material_categories_the_model_predicts(
    migrated_engine: Engine,
) -> None:
    assert _codes(migrated_engine) == CODES
    with migrated_engine.connect() as connection:
        rows = connection.execute(text("SELECT code, name FROM material_categories")).all()
    names = {row.code: row.name for row in rows}
    assert names["trash"] == "Residual / other waste" and names["glass"] == "Glass"


def test_prediction_columns_and_the_one_active_index_exist(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    columns = {c["name"] for c in inspector.get_columns("classification_predictions")}
    assert {
        "needs_review",
        "review_reasons",
        "class_probabilities",
        "novelty_similarity",
        "inference_ms",
    } <= columns
    indexes = {i["name"]: i for i in inspector.get_indexes("classification_model_versions")}
    assert indexes["uq_classification_model_versions_one_active"]["unique"]


def test_0004_round_trips_and_reseeding_is_idempotent(migrated_engine: Engine) -> None:
    downgrade(migrated_engine, "0003")
    assert _codes(migrated_engine) == set()
    assert "needs_review" not in {
        c["name"] for c in inspect(migrated_engine).get_columns("classification_predictions")
    }
    upgrade(migrated_engine)
    assert _codes(migrated_engine) == CODES
    with migrated_engine.begin() as connection:  # a manual re-run of the seed must not duplicate
        connection.execute(
            text(
                "INSERT INTO material_categories (id, code, name, is_active) "
                "VALUES (gen_random_uuid(), 'glass', 'dup', true) ON CONFLICT (code) DO NOTHING"
            )
        )
    assert len(_codes(migrated_engine)) == 6
