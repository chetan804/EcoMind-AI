"""Classification API: predict, replay, review, model status and activation."""

from __future__ import annotations

import io
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text

from app.modules.classification.constants import ModelVersionStatus
from app.modules.classification.provider import get_runtime_provider
from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.classification import (
    FakeProvider,
    FakeRuntime,
    add_model_version,
    confident,
    unsure,
    write_artifact,
)

CLS = "/api/v1/classification"
MEDIA = "/api/v1/waste-reports/media"


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 120, 70)).save(buffer, format="PNG")
    return buffer.getvalue()


class Setup:
    def __init__(self, client: TestClient, engine: Engine, artifacts: Path) -> None:
        self.client, self.engine, self.artifacts = client, engine, artifacts
        self.provider = FakeProvider()
        client.app.dependency_overrides[get_runtime_provider] = lambda: self.provider  # type: ignore[attr-defined]
        self.owner = self._user("owner@example.org", ("citizen",))
        self.stranger = self._user("stranger@example.org", ("citizen",))
        self.manager = self._user("manager@example.org", ("manager",))
        self.admin = self._user("admin@example.org", ("administrator",))
        self.norole = self._user("norole@example.org", ())

    def _user(self, email: str, roles: tuple[str, ...]) -> dict[str, str]:
        create_user(self.engine, email=email, roles=roles)
        return bearer(login(self.client, email)["access_token"])

    def upload(self, headers: dict[str, str] | None = None) -> str:
        response = self.client.post(MEDIA, content=png(), headers=headers or self.owner)
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    def predict(self, media_id: str, headers: dict[str, str] | None = None) -> Any:
        return self.client.post(
            f"{CLS}/predictions", json={"media_id": media_id}, headers=headers or self.owner
        )

    def scalar(self, sql: str, **params: Any) -> Any:
        with self.engine.connect() as connection:
            return connection.execute(text(sql), params).scalar_one()


@pytest.fixture
def s(make_client: ClientFactory, db_engine: Engine, tmp_path: Path) -> Setup:
    client = make_client(
        file_storage_local_path=tmp_path / "storage", model_artifacts_dir=tmp_path / "artifacts"
    )
    return Setup(client, db_engine, tmp_path / "artifacts")


# -- model status and the honest "no model" state ------------------------------------------------
def test_model_endpoint_requires_login_and_reports_no_active_model(s: Setup) -> None:
    assert s.client.get(f"{CLS}/model").status_code == 401
    body = s.client.get(f"{CLS}/model", headers=s.owner).json()
    assert body["active"] is None and body["scope"] == "material_category"
    assert "real-world dataset" in body["note"] and "suggestion" in body["note"]


def test_predict_without_an_active_model_is_503_and_stores_nothing(s: Setup) -> None:
    media = s.upload()
    response = s.predict(media)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_active_model"
    assert s.scalar("SELECT count(*) FROM classification_predictions") == 0
    assert s.provider.runtime.calls == 0


def test_a_retired_or_candidate_model_never_answers(s: Setup) -> None:
    add_model_version(s.engine, version="0.9.0", status=ModelVersionStatus.RETIRED)
    add_model_version(s.engine, version="1.0.0", status=ModelVersionStatus.CANDIDATE)
    assert s.predict(s.upload()).status_code == 503


# -- predict -------------------------------------------------------------------------------------
def test_predict_persists_a_real_prediction_with_version_confidence_and_audit(s: Setup) -> None:
    add_model_version(s.engine)
    response = s.predict(s.upload())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["material_category"]["code"] == "plastic"
    assert body["material_category"]["name"] == "Plastic"
    assert body["confidence"] == pytest.approx(0.93)
    assert body["needs_review"] is False and body["review_reasons"] == []
    assert body["object_label"] is None  # the model does not produce object labels
    assert body["model_name"] == "waste-material-classifier" and body["model_version"] == "1.0.0"
    assert sum(body["class_probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
    assert body["review"]["status"] == "unreviewed"
    row = (
        s.engine.connect()
        .execute(
            text(
                "SELECT material_confidence, needs_review, inference_ms FROM classification_predictions"
            )
        )
        .one()
    )
    assert row.material_confidence == Decimal("0.9300") and row.needs_review is False
    assert row.inference_ms == Decimal("12.3")
    assert (
        s.scalar("SELECT count(*) FROM audit_logs WHERE action = 'classification.predicted'") == 1
    )


def test_asking_again_replays_the_stored_prediction_without_recomputing(s: Setup) -> None:
    add_model_version(s.engine)
    media = s.upload()
    first = s.predict(media)
    again = s.predict(media)
    assert first.status_code == 201 and again.status_code == 200
    assert again.headers["Idempotent-Replayed"] == "true"
    assert again.json()["id"] == first.json()["id"]
    assert s.provider.runtime.calls == 1
    assert s.scalar("SELECT count(*) FROM classification_predictions") == 1


def test_an_uncertain_prediction_is_flagged_and_listed_for_review(s: Setup) -> None:
    add_model_version(s.engine)
    s.provider.runtime = FakeRuntime(lambda _d: unsure("glass"))
    body = s.predict(s.upload()).json()
    assert body["needs_review"] is True and body["review_reasons"] == ["low_confidence"]
    queue = s.client.get(f"{CLS}/predictions", params={"needs_review": True}, headers=s.manager)
    assert [p["id"] for p in queue.json()["items"]] == [body["id"]]
    none = s.client.get(f"{CLS}/predictions", params={"needs_review": False}, headers=s.manager)
    assert none.json()["total"] == 0


def test_predict_access_rules(s: Setup) -> None:
    add_model_version(s.engine)
    media = s.upload()
    assert s.client.post(f"{CLS}/predictions", json={"media_id": media}).status_code == 401
    assert s.predict(media, s.norole).status_code == 403
    assert s.predict(media, s.stranger).status_code == 404  # someone else's photo: invisible
    assert s.predict("00000000-0000-4000-8000-000000000000").status_code == 404
    assert s.client.post(f"{CLS}/predictions", json={}, headers=s.owner).status_code == 422
    bad = s.client.post(f"{CLS}/predictions", json={"media_id": media, "extra": 1}, headers=s.owner)
    assert bad.status_code == 422
    assert s.predict(media, s.manager).status_code == 201  # staff with read_all may classify it
    assert s.provider.runtime.calls == 1


def test_a_missing_category_is_an_honest_503_not_a_wrong_answer(s: Setup) -> None:
    add_model_version(s.engine)
    s.provider.runtime = FakeRuntime(
        lambda _d: confident("plastic"), codes={"plastic": "no_such_code"}
    )
    response = s.predict(s.upload())
    assert response.status_code == 503 and response.json()["error"]["code"] == "model_unavailable"
    assert s.scalar("SELECT count(*) FROM classification_predictions") == 0


# -- read ----------------------------------------------------------------------------------------
def test_reading_a_prediction_is_limited_to_its_owner_and_staff(s: Setup) -> None:
    add_model_version(s.engine)
    pid = s.predict(s.upload()).json()["id"]
    assert s.client.get(f"{CLS}/predictions/{pid}", headers=s.owner).status_code == 200
    assert s.client.get(f"{CLS}/predictions/{pid}", headers=s.manager).status_code == 200
    assert s.client.get(f"{CLS}/predictions/{pid}", headers=s.stranger).status_code == 404
    assert s.client.get(f"{CLS}/predictions", headers=s.owner).status_code == 403
    assert s.client.get(f"{CLS}/predictions", headers=s.norole).status_code == 403


# -- review --------------------------------------------------------------------------------------
def review(s: Setup, pid: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    return s.client.post(f"{CLS}/predictions/{pid}/review", json=body, headers=headers or s.manager)


def test_a_correction_is_recorded_and_the_model_output_is_kept(s: Setup) -> None:
    add_model_version(s.engine)
    pid = s.predict(s.upload()).json()["id"]
    response = review(
        s, pid, {"decision": "corrected", "material_category_code": "metal", "notes": " tin can "}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review"]["status"] == "corrected"
    assert body["review"]["corrected_category"]["code"] == "metal"
    assert body["review"]["notes"] == "tin can" and body["review"]["reviewed_at"]
    assert body["material_category"]["code"] == "plastic"  # what the model said is not rewritten
    assert body["confidence"] == pytest.approx(0.93)
    assert s.scalar("SELECT count(*) FROM audit_logs WHERE action = 'classification.reviewed'") == 1


def test_confirm_and_reject_and_one_review_only(s: Setup) -> None:
    add_model_version(s.engine)
    first = s.predict(s.upload()).json()["id"]
    assert review(s, first, {"decision": "confirmed"}).json()["review"]["status"] == "confirmed"
    again = review(s, first, {"decision": "rejected"})
    assert (
        again.status_code == 409 and again.json()["error"]["code"] == "prediction_already_reviewed"
    )
    second = s.predict(s.upload()).json()["id"]
    assert review(s, second, {"decision": "rejected", "notes": "blurry"}).status_code == 200
    queue = s.client.get(
        f"{CLS}/predictions", params={"review_status": "rejected"}, headers=s.manager
    ).json()
    assert queue["total"] == 1


def test_review_validation_and_permissions(s: Setup) -> None:
    add_model_version(s.engine)
    pid = s.predict(s.upload()).json()["id"]
    assert review(s, pid, {"decision": "corrected"}).status_code == 422
    assert (
        review(s, pid, {"decision": "confirmed", "material_category_code": "glass"}).status_code
        == 422
    )
    assert review(s, pid, {"decision": "maybe"}).status_code == 422
    unknown = review(s, pid, {"decision": "corrected", "material_category_code": "plutonium"})
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "invalid_review"
    same = review(s, pid, {"decision": "corrected", "material_category_code": "plastic"})
    assert same.status_code == 422 and "use 'confirmed'" in same.json()["error"]["message"]
    assert review(s, pid, {"decision": "confirmed"}, s.owner).status_code == 403
    missing = review(s, "00000000-0000-4000-8000-000000000000", {"decision": "confirmed"})
    assert missing.status_code == 404
    assert (
        s.scalar(
            "SELECT count(*) FROM classification_predictions WHERE review_status <> 'unreviewed'"
        )
        == 0
    )


# -- model registry ------------------------------------------------------------------------------
def test_listing_and_activating_models_needs_manage_permission(s: Setup) -> None:
    write_artifact(s.artifacts, "1.0.0")
    version_id = _register(s, "1.0.0")
    assert s.client.get(f"{CLS}/models", headers=s.owner).status_code == 403
    assert s.client.get(f"{CLS}/models", headers=s.manager).status_code == 403
    listed = s.client.get(f"{CLS}/models", headers=s.admin).json()
    assert [m["version"] for m in listed] == ["1.0.0"] and listed[0]["status"] == "candidate"
    assert listed[0]["evaluation_metrics"]["accuracy"] == 0.867
    assert (
        s.client.post(f"{CLS}/models/{version_id}/activate", headers=s.manager).status_code == 403
    )
    activated = s.client.post(f"{CLS}/models/{version_id}/activate", headers=s.admin)
    assert activated.status_code == 200 and activated.json()["status"] == "active"
    assert s.client.get(f"{CLS}/model", headers=s.owner).json()["active"]["version"] == "1.0.0"
    assert (
        s.scalar("SELECT count(*) FROM audit_logs WHERE action = 'classification.model_activated'")
        == 1
    )


def _register(s: Setup, version: str) -> str:
    from sqlalchemy.orm import sessionmaker

    from app.modules.classification import service

    with sessionmaker(bind=s.engine, expire_on_commit=False)() as session:
        return str(service.register_model(session, s.artifacts, version).id)


def test_activating_a_new_version_retires_the_previous_one(s: Setup) -> None:
    write_artifact(s.artifacts, "1.0.0")
    write_artifact(s.artifacts, "1.1.0")
    first, second = _register(s, "1.0.0"), _register(s, "1.1.0")
    assert s.client.post(f"{CLS}/models/{first}/activate", headers=s.admin).status_code == 200
    assert s.client.post(f"{CLS}/models/{second}/activate", headers=s.admin).status_code == 200
    with s.engine.connect() as connection:
        rows = connection.execute(
            text("SELECT version, status FROM classification_model_versions")
        ).all()
    states = {row.version: row.status for row in rows}
    assert states == {"1.0.0": "retired", "1.1.0": "active"}
    again = s.client.post(f"{CLS}/models/{second}/activate", headers=s.admin)  # no-op, no new audit
    assert again.status_code == 200
    assert (
        s.scalar("SELECT count(*) FROM audit_logs WHERE action = 'classification.model_activated'")
        == 2
    )


def test_a_tampered_or_missing_artifact_cannot_be_activated(s: Setup) -> None:
    directory = write_artifact(s.artifacts, "1.0.0")
    version_id = _register(s, "1.0.0")
    with (directory / "head.npz").open("ab") as handle:
        handle.write(b"tamper")
    response = s.client.post(f"{CLS}/models/{version_id}/activate", headers=s.admin)
    assert response.status_code == 503 and response.json()["error"]["code"] == "model_unavailable"
    assert s.scalar("SELECT status FROM classification_model_versions") == "candidate"
    (directory / "model.json").unlink()
    assert s.client.post(f"{CLS}/models/{version_id}/activate", headers=s.admin).status_code == 503
    unknown = s.client.post(
        f"{CLS}/models/00000000-0000-4000-8000-000000000000/activate", headers=s.admin
    )
    assert (
        unknown.status_code == 404 and unknown.json()["error"]["code"] == "model_version_not_found"
    )


def test_the_database_allows_only_one_active_model(s: Setup) -> None:
    add_model_version(s.engine, version="1.0.0")
    with pytest.raises(Exception, match="uq_classification_model_versions_one_active"):
        add_model_version(s.engine, version="1.1.0")


def test_registering_twice_is_idempotent_and_a_changed_artifact_is_refused(s: Setup) -> None:
    directory = write_artifact(s.artifacts, "1.0.0")
    assert _register(s, "1.0.0") == _register(s, "1.0.0")
    manifest = json.loads((directory / "model.json").read_text())
    manifest["temperature"] = 2.0
    (directory / "model.json").write_text(json.dumps(manifest))
    with pytest.raises(Exception, match="already registered with different artifacts"):
        _register(s, "1.0.0")  # model.json changed -> hash no longer matches its files' record


# -- the photo behind a prediction, for reviewers ------------------------------------------------
def test_reviewers_can_see_the_classified_photo_and_nobody_else(s: Setup) -> None:
    add_model_version(s.engine)
    pid = s.predict(s.upload()).json()["id"]
    url = f"{CLS}/predictions/{pid}/image"
    operator = s._user("operator@example.org", ("facility_operator",))
    # An operator can review but holds no report-reading right: the image must still be served.
    for headers in (s.manager, s.admin, operator):
        response = s.client.get(url, headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("image/")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-security-policy"] == "default-src 'none'; sandbox"
        assert Image.open(io.BytesIO(response.content)).size == (64, 48)
    assert s.client.get(url).status_code == 401
    # The uploader and strangers lack the review permission; the ordinary media route is theirs.
    assert s.client.get(url, headers=s.owner).status_code == 403
    assert s.client.get(url, headers=s.stranger).status_code == 403
    assert s.client.get(url, headers=s.norole).status_code == 403


def test_the_prediction_image_of_an_unknown_prediction_is_404(s: Setup) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    assert s.client.get(f"{CLS}/predictions/{missing}/image", headers=s.manager).status_code == 404
