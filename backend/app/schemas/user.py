"""User & authentication schemas."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


class AccountType(str, Enum):
    ACADEMIC = "academic"
    PRACTICE = "practice"


class EducationLevel(str, Enum):
    P6 = "P6"
    S3 = "S3"
    S6 = "S6"
    TTC = "TTC"
    DRIVING = "DRIVING"


class UserCreate(BaseModel):
    """POST /api/users/register"""

    email: EmailStr
    password: str
    full_name: str
    account_type: AccountType = AccountType.ACADEMIC
    education_level: EducationLevel | None = None
    role: str = "student"


class UserLogin(BaseModel):
    """POST /api/users/login"""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """PATCH /api/users/me — update own profile."""

    full_name: str | None = None
    account_type: AccountType | None = None
    education_level: EducationLevel | None = None


class UserRead(BaseModel):
    """User returned from API — never exposes password."""

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    account_type: AccountType = AccountType.ACADEMIC
    education_level: EducationLevel | None = None
    is_active: bool
    subscribed_topics: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """Combined auth response: token + user profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
