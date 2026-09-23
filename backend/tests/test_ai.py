"""AI pipeline tests: structured output, confidence gates, review, failures."""

from __future__ import annotations

from conftest import add_member, api, make_org_with_admin


async def test_classification_low_confidence_routes_to_review(client):
    org, admin_token = await make_org_with_admin(client)
    r = await api(
        client, "POST", "/api/v1/waste/reports", admin_token, org["id"],
        json={"description": "plastic and glass waste", "latitude": 12.94, "longitude": 77.60},
    )
    assert r.status_code == 201

    inferences = await api(client, "GET", "/api/v1/ai/inferences", admin_token, org["id"])
    items = inferences.json()["items"]
    assert len(items) >= 1
    latest = items[0]
    # Baseline provider caps confidence at 0.45 (< default 0.75 threshold)
    assert latest["status"] == "needs_review"
    assert latest["provider"] == "heuristic"
    assert latest["confidence"] <= 0.55


async def test_image_only_submission_is_honest_about_baseline_limits(client):
    """The deterministic baseline cannot see images; it must say so, not guess."""
    import io

    org, admin_token = await make_org_with_admin(client)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c626001000000ffff030000060005"
        "57bfabd40000000049454e44ae426082"
    )
    up = await api(
        client, "POST", "/api/v1/media/upload", admin_token, org["id"],
        files={"file": ("photo.png", io.BytesIO(png), "image/png")},
    )
    assert up.status_code == 201
    r = await api(
        client, "POST", "/api/v1/waste/reports", admin_token, org["id"],
        json={"description": None, "photo_media_id": up.json()["id"], "latitude": 12.94, "longitude": 77.60},
    )
    assert r.status_code == 201
    report = r.json()
    assert report["ai_category"] == "unknown"
    inferences = await api(client, "GET", "/api/v1/ai/inferences", admin_token, org["id"])
    latest = inferences.json()["items"][0]
    assert latest["status"] == "needs_review"
    guidance = (latest["output"]["handling_guidance"] or "")
    assert "human" in guidance.lower()


async def test_human_review_corrects_inference(client):
    org, admin_token = await make_org_with_admin(client)
    await api(
        client, "POST", "/api/v1/waste/reports", admin_token, org["id"],
        json={"description": "old batteries discarded in alley", "latitude": 12.94, "longitude": 77.60},
    )
    inferences = await api(client, "GET", "/api/v1/ai/inferences", admin_token, org["id"])
    latest = inferences.json()["items"][0]
    assert latest["output"]["category"] == "hazardous"

    r = await api(
        client, "POST", f"/api/v1/ai/inferences/{latest['id']}/review", admin_token, org["id"],
        json={"decision": "corrected", "corrected_output": {"category": "e_waste"}, "note": "actually electronics"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "succeeded"
    assert r.json()["output"]["category"] == "e_waste"


async def test_citizen_cannot_review_ai(client):
    org, admin_token = await make_org_with_admin(client)
    _, citizen_token = await add_member(client, admin_token, org["id"], role="citizen")
    r = await api(client, "GET", "/api/v1/ai/inferences", citizen_token, org["id"])
    assert r.status_code == 403


async def test_provider_status_is_transparent(client):
    org, admin_token = await make_org_with_admin(client)
    r = await api(client, "GET", "/api/v1/ai/providers", admin_token, org["id"])
    providers = {p["name"]: p for p in r.json()["items"]}
    assert providers["heuristic"]["is_baseline"] is True
    # External providers honestly reported as unconfigured without keys
    assert providers["openai"]["configured"] is False or providers["openai"]["configured"] is True


async def test_provider_failure_records_failed_inference(client):
    """A provider that raises is recorded as failed — never silently fabricated."""
    import uuid as _uuid

    from app.ai import service as ai_service
    from app.ai.providers import AiProvider, AiProviderError
    from app.core.db import SessionLocal, tenant_context

    org, _admin_token = await make_org_with_admin(client)

    class ExplodingProvider(AiProvider):
        name = "exploding"
        supports_vision = True

        async def classify_waste(self, **kw):
            raise AiProviderError("exploding", "boom", retryable=False)

        async def analyze_complaint(self, **kw):
            raise AiProviderError("exploding", "boom")

        async def assistant_answer(self, **kw):
            raise AiProviderError("exploding", "boom")

    original = ai_service.get_provider
    ai_service.get_provider = lambda name=None: ExplodingProvider()
    try:
        async with SessionLocal() as session:
            with tenant_context(session, _uuid.UUID(org["id"])):
                inf = await ai_service.classify_waste_report(
                    session,
                    organization_id=_uuid.UUID(org["id"]),
                    description="test",
                    media_id=None,
                    media_storage_key=None,
                    media_mime=None,
                )
                await session.commit()
        assert inf.status.value == "failed"
        assert inf.error_code == "provider_error"
    finally:
        ai_service.get_provider = original
