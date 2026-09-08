from app.ai.base import BaseWasteClassifier
from app.ai.waste_classifier import KeywordWasteClassifier


class AIInference:
    """Selects an available provider while preserving a safe local fallback."""

    def __init__(self, waste_classifier: BaseWasteClassifier | None = None):
        self.waste_classifier = waste_classifier or KeywordWasteClassifier()

    def classify_waste(self, description: str):
        return self.waste_classifier.predict(description)


inference = AIInference()
