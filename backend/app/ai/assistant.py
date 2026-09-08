from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantResponse:
    answer: str
    provider: str
    model_name: str
    is_fallback: bool


class FallbackAssistant:
    """Safe guidance fallback used when an optional local model is unavailable."""

    GUIDANCE = {
        "plastic": "Rinse plastic containers, separate reusable items, and place clean recyclable plastic in the appropriate collection stream.",
        "e-waste": "Keep electronics and batteries separate from household waste and use an authorized e-waste collection point.",
        "organic": "Separate food and garden waste from dry recyclables so it can be composted or processed safely.",
    }

    def answer(self, prompt: str, context: dict[str, object]) -> AssistantResponse:
        text = prompt.lower()
        for keyword, guidance in self.GUIDANCE.items():
            if keyword in text:
                return AssistantResponse(
                    answer=guidance,
                    provider="fallback",
                    model_name="ecomind-guidance-baseline",
                    is_fallback=True,
                )

        if "status" in text and context.get("report_count") is not None:
            return AssistantResponse(
                answer=f"Your account has {context['report_count']} report(s). Open My Reports for the current status of each report.",
                provider="fallback",
                model_name="ecomind-guidance-baseline",
                is_fallback=True,
            )

        return AssistantResponse(
            answer="I can help explain waste categories, recycling guidance, report status, collections, and sustainability activities. Ask about one of those topics.",
            provider="fallback",
            model_name="ecomind-guidance-baseline",
            is_fallback=True,
        )
