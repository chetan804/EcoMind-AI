"""Waste-material categories and sorting/disposal guidance. Owned by ``sorting_guide``.

A *material category* describes what a waste item is made of (e.g. PET plastic). It is distinct
from the *identified object/product* (e.g. "water bottle"), which only appears on a
classification prediction, and from the *guidance* on how to dispose of the material.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.sorting_guide.constants import DisposalMethod


class MaterialCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_categories"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class SortingGuidance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sorting_guidance"

    material_category_id: Mapped[uuid.UUID] = fk_uuid("material_categories.id", ondelete="CASCADE")
    disposal_method: Mapped[DisposalMethod] = mapped_column(
        enum_column(DisposalMethod), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    preparation_notes: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
