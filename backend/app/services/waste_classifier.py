from app.ai.waste_classifier import KeywordWasteClassifier


class WasteClassifier(KeywordWasteClassifier):
    """Backward-compatible service facade for the baseline AI adapter."""

    def classify(self, description: str) -> str:
        return self.predict(description).label

    def classify_with_confidence(self, description: str) -> tuple[str, float]:
        prediction = self.predict(description)
        return prediction.label, prediction.confidence
