"""Database access for users, roles and permissions. Repositories never commit."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
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
