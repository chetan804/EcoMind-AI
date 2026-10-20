"""Sorting-guide use cases.

Reading needs ``sorting_guide:read`` (every role); inactive entries are visible only with
``sorting_guide:manage``. Guidance is content owned by administrators: the platform ships the
material taxonomy but no invented local rules, and every entry can record its ``source_reference``.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.sorting_guide import repository
from app.modules.sorting_guide.constants import DisposalMethod
from app.modules.sorting_guide.models import MaterialCategory, SortingGuidance
from app.modules.sorting_guide.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    GuidanceCreate,
    GuidanceOut,
    GuidanceUpdate,
)

MANAGE = "sorting_guide:manage"


def _can_manage(principal: Principal) -> bool:
    return MANAGE in principal.permissions


def _category_out(row: MaterialCategory, guidance_count: int) -> CategoryOut:
    out = CategoryOut.model_validate(row, from_attributes=True)
    out.guidance_count = guidance_count
    return out


def _guidance_out(row: SortingGuidance, category: MaterialCategory) -> GuidanceOut:
    return GuidanceOut(
        id=row.id,
        material_category_id=row.material_category_id,
        category_code=category.code,
        category_name=category.name,
        disposal_method=row.disposal_method,
        title=row.title,
        instructions=row.instructions,
        preparation_notes=row.preparation_notes,
        source_reference=row.source_reference,
        has_source=bool(row.source_reference),
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


def list_categories(
    db: Session, principal: Principal, params: PageParams, *, include_inactive: bool, q: str | None
) -> Page[CategoryOut]:
    rows, total = repository.list_categories(
        db, params, include_inactive=include_inactive and _can_manage(principal), q=q
    )
    return Page.build([_category_out(r, n) for r, n in rows], total, params)


def create_category(
    db: Session, principal: Principal, payload: CategoryCreate, *, context: RequestContext
) -> CategoryOut:
    if repository.get_category_by_code(db, payload.code) is not None:
        raise ConflictError("A category with this code already exists")
    try:
        row = repository.add_category(
            db, code=payload.code, name=payload.name, description=payload.description
        )
    except IntegrityError as exc:  # concurrent creation of the same code
        db.rollback()
        raise ConflictError("A category with this code already exists") from exc
    audit.record(
        db,
        action="material_category.created",
        entity_type="material_category",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes={"code": row.code},
    )
    db.commit()
    return _category_out(row, 0)


def update_category(
    db: Session,
    principal: Principal,
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    *,
    context: RequestContext,
) -> CategoryOut:
    row = repository.get_category(db, category_id)
    if row is None:
        raise NotFoundError("Material category not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise UnprocessableError("name cannot be null")
    if "is_active" in changes and changes["is_active"] is None:
        raise UnprocessableError("is_active cannot be null")
    for field, value in changes.items():
        setattr(row, field, value)
    audit.record(
        db,
        action="material_category.updated",
        entity_type="material_category",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes={k: v for k, v in changes.items() if k != "description"}
        | ({"description_changed": True} if "description" in changes else {}),
    )
    db.commit()
    db.refresh(row)
    return _category_out(row, repository.guidance_counts(db, [row.id]).get(row.id, 0))


def list_guidance(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    category_id: uuid.UUID | None,
    disposal_method: DisposalMethod | None,
    include_inactive: bool,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[GuidanceOut]:
    rows, total = repository.list_guidance(
        db,
        params,
        category_id=category_id,
        disposal_method=disposal_method,
        include_inactive=include_inactive and _can_manage(principal),
        q=q,
        sort_by=sort_by,
        descending=order is SortOrder.DESC,
    )
    return Page.build([_guidance_out(g, c) for g, c in rows], total, params)


def get_guidance(db: Session, principal: Principal, guidance_id: uuid.UUID) -> GuidanceOut:
    row = repository.get_guidance(db, guidance_id)
    category = repository.get_category(db, row.material_category_id) if row else None
    if row is None or category is None:
        raise NotFoundError("Sorting guidance not found")
    if not _can_manage(principal) and not (row.is_active and category.is_active):
        raise NotFoundError("Sorting guidance not found")  # inactive content is not disclosed
    return _guidance_out(row, category)


def create_guidance(
    db: Session, principal: Principal, payload: GuidanceCreate, *, context: RequestContext
) -> GuidanceOut:
    category = repository.get_category(db, payload.material_category_id)
    if category is None:
        raise UnprocessableError("material_category_id does not refer to an existing category")
    row = repository.add_guidance(db, **payload.model_dump())
    audit.record(
        db,
        action="sorting_guidance.created",
        entity_type="sorting_guidance",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes={"category": category.code, "disposal_method": row.disposal_method.value},
    )
    db.commit()
    db.refresh(row)
    return _guidance_out(row, category)


def update_guidance(
    db: Session,
    principal: Principal,
    guidance_id: uuid.UUID,
    payload: GuidanceUpdate,
    *,
    context: RequestContext,
) -> GuidanceOut:
    row = repository.get_guidance(db, guidance_id)
    category = repository.get_category(db, row.material_category_id) if row else None
    if row is None or category is None:
        raise NotFoundError("Sorting guidance not found")
    changes = payload.model_dump(exclude_unset=True)
    for required in ("disposal_method", "title", "instructions", "is_active"):
        if required in changes and changes[required] is None:
            raise UnprocessableError(f"{required} cannot be null")
    for field, value in changes.items():
        setattr(row, field, value)
    audit.record(
        db,
        action="sorting_guidance.updated",
        entity_type="sorting_guidance",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(row)
    return _guidance_out(row, category)
