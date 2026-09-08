from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDescriptor:
    name: str
    provider: str
    task: str
    version: str
    license: str
    source: str
    enabled: bool = True


BASELINE_WASTE_MODEL = ModelDescriptor(
    name="keyword-waste-classifier",
    provider="EcoMind baseline",
    task="text-classification",
    version="1.0.0",
    license="Internal project logic",
    source="backend/app/ai/waste_classifier.py",
)

BASELINE_COMPLAINT_MODEL = ModelDescriptor(
    name="keyword-complaint-analyzer",
    provider="EcoMind baseline",
    task="text-classification",
    version="1.0.0",
    license="Internal project logic",
    source="backend/app/ai/complaint_analyzer.py",
)
