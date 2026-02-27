"""Subject and enrollment schemas."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EducationLevel(str, Enum):
    P6 = "P6"
    S3 = "S3"
    S6 = "S6"
    TTC = "TTC"
    DRIVING = "DRIVING"


class SubjectCreate(BaseModel):
    """Create a new subject."""

    name: str
    level: EducationLevel
    description: str | None = None
    icon: str | None = None  # emoji


class SubjectRead(BaseModel):
    """Subject returned from API."""

    id: uuid.UUID
    name: str
    level: str
    description: str | None = None
    icon: str | None = None
    document_count: int = 0
    enrolled: bool = False  # Whether the current student is enrolled
    created_at: datetime

    model_config = {"from_attributes": True}


class SubjectDetailRead(SubjectRead):
    """Subject with full details including documents."""

    collection_name: str | None = None


class EnrollRequest(BaseModel):
    """Enroll in one or more subjects."""

    subject_ids: list[uuid.UUID]


class EnrollResponse(BaseModel):
    """Enrollment result."""

    enrolled_count: int
    subject_ids: list[uuid.UUID]
    message: str
