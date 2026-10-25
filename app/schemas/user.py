import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole

_PASSWORD_RE = re.compile(r"(?=.*[A-Za-z])(?=.*\d).{8,}", re.DOTALL)


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: UserRole = Field(default=UserRole.viewer)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not _PASSWORD_RE.fullmatch(value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserLogin(UserBase):
    password: str


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
