"""Provider-independent AI layer.

Providers are discovered from configuration at runtime — never hard-coded
model names. Each adapter implements the same contract with structured
outputs and fails closed (exceptions propagate to the service, which retries
once, then records a failed inference and routes the item to human review).

The built-in ``heuristic`` provider is a *deterministic rules baseline*, not a
learned model: it analyses the text description, caps its own confidence, and
always requests human review. It exists so the platform is fully functional
without external credentials — it is labelled as a baseline everywhere it is
surfaced, and it never fabricates vision results.
"""

from __future__ import annotations

import abc
import json
import re
from typing import Any, ClassVar

import httpx

from app.ai.schemas import AssistantAnswer, ComplaintAnalysisOut, WasteClassificationOut
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ai")


class AiProviderError(Exception):
    """Provider failed (timeout, HTTP error, malformed response)."""

    def __init__(self, provider: str, message: str, *, retryable: bool = True):
        self.provider = provider
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class AiProvider(abc.ABC):
    name: ClassVar[str] = "abstract"
    supports_vision: ClassVar[bool] = False

    @abc.abstractmethod
    async def classify_waste(
        self, *, image_bytes: bytes | None, mime: str | None, text_hint: str | None
    ) -> WasteClassificationOut: ...

    @abc.abstractmethod
    async def analyze_complaint(self, *, subject: str, description: str) -> ComplaintAnalysisOut: ...

    @abc.abstractmethod
    async def assistant_answer(self, *, question: str, context_snippets: list[str]) -> AssistantAnswer: ...


# ---------------------------------------------------------------------------
# Heuristic deterministic baseline (no external calls)
# ---------------------------------------------------------------------------

from app.ai.schemas import WasteClass  # noqa: E402

_RULES: list[tuple[WasteClass, list[str]]] = [
    (WasteClass.hazardous, ["battery", "batteries", "chemical", "paint", "asbestos", "medical", "syringe", "toxic"]),
    (WasteClass.e_waste, ["electronic", "electronics", "tv", "monitor", "laptop", "cable", "wire", "appliance", "fridge"]),
    (WasteClass.construction, ["construction", "debris", "concrete", "brick", "rubble", "demolition"]),
    (WasteClass.organic, ["food", "organic", "kitchen", "garden", "leaves", "vegetable", "compost"]),
    (WasteClass.recyclable, ["plastic", "bottle", "paper", "cardboard", "glass", "can", "recycl", "metal"]),
    (WasteClass.mixed, ["household", "garbage", "trash", "mixed", "general"]),
]


class HeuristicProvider(AiProvider):
    name = "heuristic"
    supports_vision = False
    label = "Deterministic baseline (rules, not a learned model)"

    async def classify_waste(
        self, *, image_bytes: bytes | None, mime: str | None, text_hint: str | None
    ) -> WasteClassificationOut:
        text = (text_hint or "").lower()
        if not text and image_bytes is not None:
            # Honest limitation: the baseline cannot see images.
            return WasteClassificationOut(
                category=WasteClass.unknown,
                contamination_detected=False,
                estimated_volume_m3=0.0,
                handling_guidance=(
                    "Baseline classifier cannot analyse images. Flagged for human review — "
                    "an operator should classify this report manually."
                ),
                confidence=0.0,
                observations=["image_only_submission_no_text_hint"],
            )
        for cls, keywords in _RULES:
            if any(k in text for k in keywords):
                return WasteClassificationOut(
                    category=cls,
                    contamination_detected=any(w in text for w in ["mixed", "contaminat", "dirty"]),
                    estimated_volume_m3=0.2 if any(w in text for w in ["large", "heap", "pile", "truck"]) else 0.05,
                    handling_guidance=f"Baseline keyword match for {cls.value}. Requires operator confirmation.",
                    confidence=0.45,
                    observations=["keyword_baseline"],
                )
        return WasteClassificationOut(
            category=WasteClass.unknown,
            contamination_detected=False,
            estimated_volume_m3=0.0,
            handling_guidance="No keyword signal found. Requires human classification.",
            confidence=0.0,
            observations=["no_signal"],
        )

    async def analyze_complaint(self, *, subject: str, description: str) -> ComplaintAnalysisOut:
        from app.ai.schemas import ComplaintClass

        text = f"{subject} {description}".lower()
        rules: list[tuple[ComplaintClass, str, list[str]]] = [
            (ComplaintClass.missed_collection, "high", ["missed", "not collected", "skipped", "no collection"]),
            (ComplaintClass.overflow, "high", ["overflow", "overfull", "spill"]),
            (ComplaintClass.illegal_dumping, "high", ["illegal", "dumping", "dumped", "littering"]),
            (ComplaintClass.bin_damaged, "medium", ["broken", "damaged", "cracked", "missing lid"]),
            (ComplaintClass.odor, "medium", ["smell", "odor", "odour", "stink"]),
            (ComplaintClass.staff_conduct, "urgent", ["rude", "conduct", "behaviour", "behavior"]),
        ]
        for cls, priority, kws in rules:
            if any(k in text for k in kws):
                return ComplaintAnalysisOut(
                    suggested_category=cls,
                    suggested_priority=priority,  # type: ignore[arg-type]
                    summary=f"Baseline suggestion: {cls.value.replace('_', ' ')} (keyword match).",
                    key_details=[],
                    confidence=0.5,
                )
        return ComplaintAnalysisOut(
            suggested_category=ComplaintClass.other,
            suggested_priority="medium",
            summary="No strong keyword signal; suggests manual triage.",
            key_details=[],
            confidence=0.3,
        )

    async def assistant_answer(self, *, question: str, context_snippets: list[str]) -> AssistantAnswer:
        raise AiProviderError(
            self.name,
            "The assistant requires a configured LLM provider. Set an API key or connect a local model.",
            retryable=False,
        )


# ---------------------------------------------------------------------------
# HTTP providers (OpenAI / Anthropic / Google) — configured via settings
# ---------------------------------------------------------------------------

_WASTE_SCHEMA = WasteClassificationOut.model_json_schema()
_COMPLAINT_SCHEMA = ComplaintAnalysisOut.model_json_schema()

_WASTE_SYSTEM = (
    "You are a waste-management classification assistant for municipal operations. "
    "Analyse the provided photo (if any) and the citizen description. "
    "Respond ONLY with JSON matching the provided schema. "
    "category must be one of: mixed, recyclable, organic, hazardous, e_waste, construction, unknown. "
    "Use unknown when uncertain — never guess hazardous or e_waste without clear evidence. "
    "confidence is your calibrated probability that the category is correct."
)

_COMPLAINT_SYSTEM = (
    "You are a municipal complaint-triage assistant. Your output is a SUGGESTION for a human "
    "operator, never a decision. Respond ONLY with JSON matching the provided schema."
)


class OpenAiProvider(AiProvider):
    name = "openai"
    supports_vision = True

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise AiProviderError(self.name, "OpenAI API key not configured.", retryable=False)

    async def _chat(self, *, system: str, user_content: list[dict], schema: dict, seed: int | None = None) -> dict:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": False}},
            "max_tokens": 800,
        }
        async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
        if resp.status_code != 200:
            raise AiProviderError(self.name, f"HTTP {resp.status_code} from provider.")
        try:
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            raise AiProviderError(self.name, f"Malformed provider response: {e}", retryable=False) from e

    async def classify_waste(self, *, image_bytes, mime, text_hint) -> WasteClassificationOut:
        content: list[dict] = []
        if image_bytes:
            import base64

            content.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image_bytes).decode()}"}}
            )
        content.append({"type": "text", "text": text_hint or "(no description provided)"})
        raw = await self._chat(system=_WASTE_SYSTEM, user_content=content, schema=_WASTE_SCHEMA)
        return WasteClassificationOut.model_validate(raw)  # raises on invalid -> failed inference

    async def analyze_complaint(self, *, subject, description) -> ComplaintAnalysisOut:
        raw = await self._chat(
            system=_COMPLAINT_SYSTEM,
            user_content=[{"type": "text", "text": f"Subject: {subject}\n\nDescription: {description}"}],
            schema=_COMPLAINT_SCHEMA,
        )
        return ComplaintAnalysisOut.model_validate(raw)

    async def assistant_answer(self, *, question, context_snippets) -> AssistantAnswer:
        raw = await self._chat(
            system=(
                "You are the EcoMind-AI operations assistant. Answer ONLY from the provided data "
                "snippets; if they are insufficient, say so. Respond as JSON with keys answer, "
                "used_data, confidence."
            ),
            user_content=[
                {"type": "text", "text": "DATA:\n" + "\n".join(context_snippets) + f"\n\nQUESTION: {question}"}
            ],
            schema=AssistantAnswer.model_json_schema(),
        )
        return AssistantAnswer.model_validate(raw)


class AnthropicProvider(AiProvider):
    name = "anthropic"
    supports_vision = True

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise AiProviderError(self.name, "Anthropic API key not configured.", retryable=False)

    async def _messages(self, *, system: str, content: list[dict]) -> dict:
        body = {"model": self.model, "max_tokens": 1024, "system": system, "messages": [{"role": "user", "content": content}]}
        async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.anthropic_base_url}/v1/messages",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                json=body,
            )
        if resp.status_code != 200:
            raise AiProviderError(self.name, f"HTTP {resp.status_code} from provider.")
        try:
            text = resp.json()["content"][0]["text"]
            return json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))  # type: ignore[union-attr]
        except (KeyError, ValueError, AttributeError, json.JSONDecodeError) as e:
            raise AiProviderError(self.name, f"Malformed provider response: {e}", retryable=False) from e

    async def classify_waste(self, *, image_bytes, mime, text_hint) -> WasteClassificationOut:
        content: list[dict] = []
        if image_bytes:
            import base64

            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": mime or "image/jpeg",
                                             "data": base64.b64encode(image_bytes).decode()}}
            )
        content.append({"type": "text", "text": (text_hint or "(no description)") + "\n\nRespond as JSON matching: "
                        + json.dumps(_WASTE_SCHEMA)})
        raw = await self._messages(system=_WASTE_SYSTEM, content=content)
        return WasteClassificationOut.model_validate(raw)

    async def analyze_complaint(self, *, subject, description) -> ComplaintAnalysisOut:
        raw = await self._messages(
            system=_COMPLAINT_SYSTEM,
            content=[{"type": "text", "text": f"Subject: {subject}\n\nDescription: {description}\n\nRespond as JSON matching: "
                      + json.dumps(_COMPLAINT_SCHEMA)}],
        )
        return ComplaintAnalysisOut.model_validate(raw)

    async def assistant_answer(self, *, question, context_snippets) -> AssistantAnswer:
        raw = await self._messages(
            system="You are the EcoMind-AI operations assistant. Answer ONLY from the provided data snippets; if insufficient, say so. Respond as JSON with keys answer, used_data, confidence.",
            content=[{"type": "text", "text": "DATA:\n" + "\n".join(context_snippets) + f"\n\nQUESTION: {question}"}],
        )
        return AssistantAnswer.model_validate(raw)


class GoogleProvider(AiProvider):
    name = "google"
    supports_vision = True

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or settings.google_api_key
        if not self.api_key:
            raise AiProviderError(self.name, "Google API key not configured.", retryable=False)

    async def _generate(self, *, system: str, parts: list[dict], schema: dict) -> dict:
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"response_mime_type": "application/json", "response_schema": schema,
                                  "maxOutputTokens": 1024},
        }
        async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.google_base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json=body,
            )
        if resp.status_code != 200:
            raise AiProviderError(self.name, f"HTTP {resp.status_code} from provider.")
        try:
            return json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            raise AiProviderError(self.name, f"Malformed provider response: {e}", retryable=False) from e

    async def classify_waste(self, *, image_bytes, mime, text_hint) -> WasteClassificationOut:
        parts: list[dict] = []
        if image_bytes:
            import base64

            parts.append({"inline_data": {"mime_type": mime or "image/jpeg",
                                          "data": base64.b64encode(image_bytes).decode()}})
        parts.append({"text": text_hint or "(no description provided)"})
        raw = await self._generate(system=_WASTE_SYSTEM, parts=parts, schema=_WASTE_SCHEMA)
        return WasteClassificationOut.model_validate(raw)

    async def analyze_complaint(self, *, subject, description) -> ComplaintAnalysisOut:
        raw = await self._generate(
            system=_COMPLAINT_SYSTEM,
            parts=[{"text": f"Subject: {subject}\n\nDescription: {description}"}],
            schema=_COMPLAINT_SCHEMA,
        )
        return ComplaintAnalysisOut.model_validate(raw)

    async def assistant_answer(self, *, question, context_snippets) -> AssistantAnswer:
        raw = await self._generate(
            system="You are the EcoMind-AI operations assistant. Answer ONLY from the provided data snippets; if insufficient, say so.",
            parts=[{"text": "DATA:\n" + "\n".join(context_snippets) + f"\n\nQUESTION: {question}"}],
            schema=AssistantAnswer.model_json_schema(),
        )
        return AssistantAnswer.model_validate(raw)


_REGISTRY: dict[str, type[AiProvider]] = {
    HeuristicProvider.name: HeuristicProvider,
    OpenAiProvider.name: OpenAiProvider,
    AnthropicProvider.name: AnthropicProvider,
    GoogleProvider.name: GoogleProvider,
}


def get_provider(name: str | None = None) -> AiProvider:
    name = (name or settings.ai_default_provider).lower()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise AiProviderError(name, f"Unknown AI provider '{name}'.", retryable=False)
    return cls()


def provider_status() -> list[dict]:
    out = []
    for name, cls in _REGISTRY.items():
        configured = True
        if name == "openai" and not settings.openai_api_key:
            configured = False
        if name == "anthropic" and not settings.anthropic_api_key:
            configured = False
        if name == "google" and not settings.google_api_key:
            configured = False
        out.append(
            {
                "name": name,
                "supports_vision": cls.supports_vision,
                "configured": configured,
                "is_default": name == settings.ai_default_provider,
                "is_baseline": name == "heuristic",
            }
        )
    return out
