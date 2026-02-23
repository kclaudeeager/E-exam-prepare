"""Document schemas."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EducationLevel(str, Enum):
    P6 = "P6"
    S3 = "S3"
    S6 = "S6"
    TTC = "TTC"


class DocumentCreate(BaseModel):
    """Metadata sent alongside a file upload."""

    subject: str
    level: EducationLevel
    year: str
    official_duration_minutes: int | None = None
    instructions: str | None = None
    marking_scheme: str | None = None


class DocumentRead(BaseModel):
    """Document row returned from API."""

    id: uuid.UUID
    filename: str
    subject: str
    level: str
    year: str
    uploaded_by: uuid.UUID
    ingestion_status: str
    official_duration_minutes: int | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
