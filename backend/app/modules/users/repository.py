"""Database access for users, roles and permissions. Repositories never commit."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.modules.users.models import Permission, Role, RolePermission, User, UserRole


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))


def add(db: Session, *, email: str, password_hash: str, full_name: str) -> User:
    user = User(
        email=normalize_email(email), password_hash=password_hash, full_name=full_name.strip()
    )
    db.add(user)
    db.flush()
    return user


def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.scalar(select(Role).where(Role.name == name))


def assign_role(db: Session, *, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
    db.add(UserRole(user_id=user_id, role_id=role_id))
    db.flush()


def role_names(db: Session, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )
    return list(db.scalars(stmt))


def permission_codes(db: Session, user_id: uuid.UUID) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
        .distinct()
    )
    return set(db.scalars(stmt))


def lock_statement(user_id: uuid.UUID) -> Select[uuid.UUID]:
    """``SELECT id ... FOR UPDATE``: serialises work that must not interleave per user."""
    return select(User.id).where(User.id == user_id).with_for_update()


def list_page(
    db: Session,
    *,
    offset: int,
    limit: int,
    q_pattern: str | None,
    escape: str,
    role: str | None,
    is_active: bool | None,
) -> tuple[list[User], int]:
    stmt = select(User)
    if q_pattern is not None:
        stmt = stmt.where(
            User.email.ilike(q_pattern, escape=escape)
            | User.full_name.ilike(q_pattern, escape=escape)
        )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if role is not None:
        stmt = stmt.where(
            User.id.in_(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.name == role)
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.scalars(stmt.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit))
    return list(rows), int(total)


def roles_by_user(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    result: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
    if not user_ids:
        return result
    stmt = (
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_(user_ids))
        .order_by(Role.name)
    )
    for user_id, name in db.execute(stmt):
        result[user_id].append(name)
    return result


def list_roles(db: Session) -> list[tuple[Role, list[str], int]]:
    """Every role with its permission codes and how many users hold it."""
    permissions: dict[uuid.UUID, list[str]] = {}
    for role_id, code in db.execute(
        select(RolePermission.role_id, Permission.code)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .order_by(Permission.code)
    ):
        permissions.setdefault(role_id, []).append(code)
    holders = dict(
        db.execute(select(UserRole.role_id, func.count()).group_by(UserRole.role_id)).all()
    )
    roles = db.scalars(select(Role).order_by(Role.name))
    return [(r, permissions.get(r.id, []), int(holders.get(r.id, 0))) for r in roles]


def roles_by_names(db: Session, names: list[str]) -> list[Role]:
    return list(db.scalars(select(Role).where(Role.name.in_(names))))


def replace_roles(db: Session, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
    db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for role_id in role_ids:
        db.add(UserRole(user_id=user_id, role_id=role_id))
    db.flush()


def lock_active_administrators(db: Session) -> list[uuid.UUID]:
    """Lock and return every active administrator so concurrent demotions cannot all succeed."""
    stmt = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "administrator", User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update(of=User)
    )
    return list(db.scalars(stmt))
