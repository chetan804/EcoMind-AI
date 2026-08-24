from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.core.security import hash_password
from app.core.security import get_current_user, hash_password, require_role

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post("/", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    hashed_password = hash_password(user_data.password)

    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password,
        role_id=user_data.role_id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.get("/admin-test")
def admin_test(
    current_user: User = Depends(require_role(4)),
):
    return {
        "message": "Admin access granted",
        "user_id": current_user.id,
        "role_id": current_user.role_id,
    }