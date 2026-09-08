from time import perf_counter

from app.ai.base import Prediction, utc_now
from app.ai.model_registry import BASELINE_WASTE_MODEL


class KeywordWasteClassifier:
    CATEGORIES = {
        "plastic": (
            "plastic",
            "polythene",
            "polybag",
            "wrapper",
            "plastic bottle",
            "plastic bag",
        ),
        "paper": ("paper", "newspaper", "cardboard", "carton", "book", "magazine"),
        "glass": ("glass", "glass bottle", "broken glass"),
        "metal": ("metal", "iron", "steel", "aluminium", "aluminum", "copper", "tin"),
        "organic": ("food", "vegetable", "fruit", "organic", "kitchen", "leaves", "garden"),
        "e-waste": ("electronic", "computer", "laptop", "mobile", "phone", "charger", "battery", "television", "tv"),
    }

    def predict(self, description: str) -> Prediction:
        started = perf_counter()
        text = (description or "").lower().strip()
        label = "other"
        confidence = 0.0 if not text else 0.2
        for category, keywords in self.CATEGORIES.items():
            if any(keyword in text for keyword in keywords):
                label = category
                confidence = 0.9
                break
        return Prediction(
            label=label,
            confidence=confidence,
            model_name=BASELINE_WASTE_MODEL.name,
            model_version=BASELINE_WASTE_MODEL.version,
            provider=BASELINE_WASTE_MODEL.provider,
            created_at=utc_now(),
            inference_time_ms=(perf_counter() - started) * 1000,
        )
