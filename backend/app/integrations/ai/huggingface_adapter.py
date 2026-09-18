from app.integrations.ai.base import AIAdapter, AIResult, AIUnavailable


class HuggingFaceAdapter:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._classifier = None

    def _load(self):
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise AIUnavailable("Hugging Face support requires transformers") from exc
        if self._classifier is None:
            self._classifier = pipeline("text-classification", model=self.model_name)
        return self._classifier

    def classify(self, text: str) -> AIResult:
        if not text.strip():
            raise ValueError("Text must not be empty")
        try:
            result = self._load()(text, truncation=True)[0]
        except Exception as exc:
            raise AIUnavailable("Hugging Face inference failed") from exc
        return AIResult(
            label=str(result["label"]),
            confidence=float(result["score"]),
            model=self.model_name,
            provider="huggingface",
        )
