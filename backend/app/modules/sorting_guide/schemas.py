"""Request and response bodies of the sorting-guide API."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.sorting_guide.constants import DisposalMethod

CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=5000)]
Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
GuidanceSort = Literal["title", "created_at", "disposal_method"]


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Lower-case identifier, e.g. `glass`")
    name: Name
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        code = value.strip().lower()
        if not CODE.fullmatch(code):
            raise ValueError(
                "code must be 2-64 characters: a-z, 0-9 and underscore, starting with a letter"
            )
        return code


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    guidance_count: int = Field(default=0, description="Active guidance entries for this category")


class GuidanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_category_id: uuid.UUID
    disposal_method: DisposalMethod
    title: Title
    instructions: Body
    preparation_notes: Body | None = None
    source_reference: Source | None = Field(
        default=None, description="Where this rule comes from (regulation, municipality, guide)"
    )
    is_active: bool = True


class GuidanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposal_method: DisposalMethod | None = None
    title: Title | None = None
    instructions: Body | None = None
    preparation_notes: Body | None = None
    source_reference: Source | None = None
    is_active: bool | None = None


class GuidanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    material_category_id: uuid.UUID
    category_code: str
    category_name: str
    disposal_method: DisposalMethod
    title: str
    instructions: str
    preparation_notes: str | None
    source_reference: str | None
    has_source: bool = Field(description="False when no source is recorded: treat as unverified")
    is_active: bool
    updated_at: dt.datetime
