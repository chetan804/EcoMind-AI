"""Cursor-free offset pagination with a consistent envelope.

{"items": [...], "pagination": {"page": 1, "page_size": 25, "total": 132, "pages": 6}}
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class PageMeta(BaseModel):
    page: int = 1
    page_size: int = 25
    total: int = 0
    pages: int = 0


class Page(BaseModel):
    items: list[Any] = Field(default_factory=list)
    pagination: PageMeta = PageMeta()

    @classmethod
    def build(cls, items: list[Any], total: int, page: int, page_size: int) -> "Page":
        return cls(
            items=items,
            pagination=PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                pages=math.ceil(total / page_size) if page_size else 0,
            ),
        )


@dataclass(slots=True)
class PageParams:
    page: int = 1
    page_size: int = 25
    max_page_size: int = 100

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return min(self.page_size, self.max_page_size)


def page_params(page: int = 1, page_size: int = 25) -> PageParams:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25
    return PageParams(page=page, page_size=page_size)
