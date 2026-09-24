"""User profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import CurrentUser, DbSession
from app.core.errors import ValidationApiError
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    locale: str | None = None
    notification_prefs: dict | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me")
async def update_profile(body: ProfileUpdate, user: CurrentUser, session: DbSession):
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, k, v)
    await session.commit()
    return {"ok": True}


@router.post("/me/change-password")
async def change_password(body: PasswordChange, user: CurrentUser, session: DbSession):
    if not user.password_hash or not verify_password(user.password_hash, body.current_password):
        raise ValidationApiError("Current password is incorrect.")
    if len(body.new_password) < 10:
        raise ValidationApiError("New password must be at least 10 characters.")
    user.password_hash = hash_password(body.new_password)
    await session.commit()
    return {"ok": True}
