# AI Architecture

The AI layer is provider-independent and records model name, version, provider, confidence, timestamp, and latency where applicable.

Current active implementations:

- Deterministic keyword waste classifier.
- Deterministic complaint analyzer.
- Safe local guidance fallback assistant.

These are baselines, not deep-learning models. Hugging Face, PyTorch, scikit-learn, Ollama, image classification, duplicate detection, evaluation metrics, and drift monitoring remain optional future adapters. External model outputs must be validated, traced, and marked as fallback or unavailable when appropriate.
