"""Help articles: staff write them, everyone with ``support:ask`` reads the published ones."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.support.models import KnowledgeArticle
from app.modules.support.schemas import ArticleCreate, ArticleOut, ArticleUpdate

_SEEDED_FIELDS = ("title", "body", "category", "keywords")
PLATFORM_HELP = Path(__file__).parent / "knowledge" / "platform_help.json"


def list_articles(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    q: str | None,
    category: str | None,
    include_unpublished: bool,
) -> Page[ArticleOut]:
    stmt = select(KnowledgeArticle)
    if not (include_unpublished and principal.has("knowledge:manage")):
        stmt = stmt.where(KnowledgeArticle.published.is_(True))
    if category:
        stmt = stmt.where(KnowledgeArticle.category == category)
    pattern = contains_pattern(q) if q else None
    if pattern:
        stmt = stmt.where(
            KnowledgeArticle.title.ilike(pattern, escape=LIKE_ESCAPE)
            | KnowledgeArticle.body.ilike(pattern, escape=LIKE_ESCAPE)
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.scalars(
        stmt.order_by(KnowledgeArticle.category, KnowledgeArticle.title, KnowledgeArticle.id)
        .limit(params.limit)
        .offset(params.offset)
    )
    return Page.build([ArticleOut.model_validate(r) for r in rows], total, params)


def categories(db: Session, principal: Principal) -> list[str]:
    stmt = select(KnowledgeArticle.category).distinct().order_by(KnowledgeArticle.category)
    return list(db.scalars(stmt))


def get_article(db: Session, principal: Principal, article_id: uuid.UUID) -> ArticleOut:
    article = db.get(KnowledgeArticle, article_id)
    if article is None or (not article.published and not principal.has("knowledge:manage")):
        raise NotFoundError("Article not found")
    return ArticleOut.model_validate(article)


def create_article(
    db: Session, principal: Principal, payload: ArticleCreate, *, context: RequestContext
) -> ArticleOut:
    if db.scalar(select(KnowledgeArticle.id).where(KnowledgeArticle.slug == payload.slug)):
        raise ConflictError("An article with this slug already exists")
    article = KnowledgeArticle(
        **payload.model_dump(), created_by_id=principal.user_id, updated_by_id=principal.user_id
    )
    db.add(article)
    db.flush()
    audit.record(
        db,
        action="knowledge_article.created",
        entity_type="knowledge_article",
        entity_id=article.id,
        actor_id=principal.user_id,
        context=context,
        changes={"slug": article.slug, "published": article.published},
    )
    db.commit()
    db.refresh(article)
    return ArticleOut.model_validate(article)


def update_article(
    db: Session,
    principal: Principal,
    article_id: uuid.UUID,
    payload: ArticleUpdate,
    *,
    context: RequestContext,
) -> ArticleOut:
    article = db.scalar(
        select(KnowledgeArticle).where(KnowledgeArticle.id == article_id).with_for_update()
    )
    if article is None:
        raise NotFoundError("Article not found")
    changed: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new = getattr(payload, field)
        if new is None or new == getattr(article, field):
            continue
        changed[field] = (
            {"changed": True}
            if field == "body"
            else {
                "from": getattr(article, field),
                "to": new,
            }
        )
        setattr(article, field, new)
    if changed:
        article.updated_by_id = principal.user_id
        audit.record(
            db,
            action="knowledge_article.updated",
            entity_type="knowledge_article",
            entity_id=article.id,
            actor_id=principal.user_id,
            context=context,
            changes={"fields": changed},
        )
        db.commit()
        db.refresh(article)
    return ArticleOut.model_validate(article)


def seed_platform_help(db: Session) -> tuple[int, int]:
    """Load the shipped platform help. Idempotent: articles are matched by slug.

    Existing articles that staff edited are left alone when ``source`` no longer says
    ``platform-help`` (so a local rewrite is never overwritten by an upgrade).
    Returns ``(created, updated)``.
    """
    entries = json.loads(PLATFORM_HELP.read_text(encoding="utf-8"))
    created = updated = 0
    for entry in entries:
        article = db.scalar(select(KnowledgeArticle).where(KnowledgeArticle.slug == entry["slug"]))
        if article is None:
            db.add(KnowledgeArticle(**entry))
            created += 1
        elif article.source == entry["source"] and any(
            getattr(article, field) != entry.get(field, "") for field in _SEEDED_FIELDS
        ):
            for field in _SEEDED_FIELDS:
                setattr(article, field, entry.get(field, ""))
            updated += 1
    db.commit()
    return created, updated
