from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role_id: int


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role_id: int

    class Config:
        from_attributes = True