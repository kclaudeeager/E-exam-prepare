"""User & authentication schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """POST /api/users/register"""

    email: EmailStr
    password: str
    full_name: str
    role: str = "student"


class UserLogin(BaseModel):
    """POST /api/users/login"""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """User returned from API — never exposes password."""

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    subscribed_topics: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
