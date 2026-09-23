"""Structured AI output schemas.

Provider output is *untrusted input*: it is parsed into these Pydantic models
with strict validation (enums, ranges, required fields) before it is allowed
into the domain. A syntactically valid JSON blob is never assumed correct.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class WasteClass(str, enum.Enum):
    mixed = "mixed"
    recyclable = "recyclable"
    organic = "organic"
    hazardous = "hazardous"
    e_waste = "e_waste"
    construction = "construction"
    unknown = "unknown"


class WasteClassificationOut(BaseModel):
    """Structured result of the waste-image classification task."""

    category: WasteClass
    contamination_detected: bool = False
    estimated_volume_m3: float = Field(default=0.0, ge=0.0, le=8.0)
    handling_guidance: str = Field(default="", max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)
    observations: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("handling_guidance")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("observations")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        return [s.strip()[:200] for s in v if s and s.strip()][:8]


class ComplaintClass(str, enum.Enum):
    missed_collection = "missed_collection"
    bin_damaged = "bin_damaged"
    overflow = "overflow"
    odor = "odor"
    illegal_dumping = "illegal_dumping"
    staff_conduct = "staff_conduct"
    billing = "billing"
    app_issue = "app_issue"
    other = "other"


class ComplaintAnalysisOut(BaseModel):
    """Suggestion only — a human triages; the model never decides."""

    suggested_category: ComplaintClass
    suggested_priority: Literal["low", "medium", "high", "urgent"]
    summary: str = Field(max_length=600)
    key_details: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)


class AssistantAnswer(BaseModel):
    answer: str = Field(max_length=4000)
    used_data: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
