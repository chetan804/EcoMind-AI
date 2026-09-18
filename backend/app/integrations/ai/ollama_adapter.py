import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.integrations.ai.base import AIResult, AIUnavailable


class OllamaAdapter:
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def classify(self, text: str) -> AIResult:
        if not text.strip():
            raise ValueError("Text must not be empty")
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps({"model": self.model_name, "prompt": text, "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AIUnavailable("Ollama inference is unavailable") from exc
        answer = str(payload.get("response", "")).strip()
        if not answer:
            raise AIUnavailable("Ollama returned an empty response")
        return AIResult(label=answer, confidence=0.0, model=self.model_name, provider="ollama")
