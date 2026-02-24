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
    """Metadata sent alongside a file upload (admin designation)."""

    subject: str
    level: EducationLevel
    year: str
    official_duration_minutes: int | None = None
    instructions: str | None = None
    marking_scheme: str | None = None


class DocumentUploadRequest(BaseModel):
    """Request for student personal document upload."""

    subject: str
    level: EducationLevel
    year: str
    official_duration_minutes: int | None = None
    instructions: str | None = None


class DocumentRead(BaseModel):
    """Document row returned from API."""

    id: uuid.UUID
    filename: str
    subject: str
    level: str
    year: str
    uploaded_by: uuid.UUID
    ingestion_status: str
    is_personal: bool = False
    is_shared: bool = False
    official_duration_minutes: int | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentShareRequest(BaseModel):
    """POST request to share a personal document with another student."""

    student_ids: list[uuid.UUID]


class DocumentShareResponse(BaseModel):
    """Response after sharing a document."""

    document_id: uuid.UUID
    shared_count: int
    shared_with: list[uuid.UUID]
    message: str


class DocumentWithShareInfo(DocumentRead):
    """Document with sharing information."""

    shared_with_count: int = 0
    can_share: bool = False  # True if current user is the owner
    can_delete: bool = False  # True if current user is the owner
