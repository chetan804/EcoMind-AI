from time import perf_counter

from app.ai.base import ComplaintAnalysis, utc_now
from app.ai.model_registry import BASELINE_COMPLAINT_MODEL


class KeywordComplaintAnalyzer:
    RULES = {
        "illegal_dumping": ("dump", "dumping", "disposed"),
        "overflowing_bin": ("overflow", "full bin", "overflowing"),
        "missed_collection": ("missed", "not collected", "skipped"),
        "hazardous_waste": ("chemical", "medical", "hazard", "sharp", "toxic"),
        "roadside_waste": ("roadside", "road", "street", "highway"),
        "plastic_pollution": ("plastic", "polythene", "wrapper"),
    }

    def analyze(self, title: str, description: str) -> ComplaintAnalysis:
        started = perf_counter()
        text = f"{title} {description}".lower().strip()
        category = "other"
        keywords: list[str] = []
        for candidate, terms in self.RULES.items():
            matches = [term for term in terms if term in text]
            if matches:
                category = candidate
                keywords.extend(matches)
                break

        priority = "medium"
        if category == "hazardous_waste":
            priority = "critical"
        elif category in {"illegal_dumping", "overflowing_bin"}:
            priority = "high"
        elif category == "other":
            priority = "low"

        return ComplaintAnalysis(
            category=category,
            priority=priority,
            keywords=sorted(set(keywords)),
            confidence=0.85 if keywords else 0.2,
            model_name=BASELINE_COMPLAINT_MODEL.name,
            model_version=BASELINE_COMPLAINT_MODEL.version,
            provider=BASELINE_COMPLAINT_MODEL.provider,
            created_at=utc_now(),
            inference_time_ms=(perf_counter() - started) * 1000,
        )
