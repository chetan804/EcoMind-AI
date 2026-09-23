"""Media assets (untrusted uploads).

Uploads are validated (size, MIME, extension), stored in object storage under
organization-namespaced keys, and referenced by ID. Content is served through
authorised endpoints only.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDMixin


class MediaKind(str, enum.Enum):
    image = "image"
    document = "document"


class ScanStatus(str, enum.Enum):
    pending = "pending"
    clean = "clean"
    failed = "failed"


class MediaAsset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    uploader_user_id: Mapped[uuid.UUID | None] = mapped_column()
    kind: Mapped[MediaKind] = mapped_column(
        SAEnum(MediaKind, native_enum=False, length=16), default=MediaKind.image, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    scan_status: Mapped[ScanStatus] = mapped_column(
        SAEnum(ScanStatus, native_enum=False, length=16), default=ScanStatus.pending, nullable=False
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
