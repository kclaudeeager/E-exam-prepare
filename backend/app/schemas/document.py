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
    DRIVING = "DRIVING"


class DocumentCategory(str, Enum):
    EXAM_PAPER = "exam_paper"
    MARKING_SCHEME = "marking_scheme"
    SYLLABUS = "syllabus"
    TEXTBOOK = "textbook"
    NOTES = "notes"
    DRIVING_MANUAL = "driving_manual"
    OTHER = "other"


class DocumentCreate(BaseModel):
    """Metadata sent alongside a file upload (admin designation)."""

    subject: str
    level: EducationLevel
    year: str
    document_category: DocumentCategory = DocumentCategory.EXAM_PAPER
    official_duration_minutes: int | None = None
    instructions: str | None = None
    marking_scheme: str | None = None


class DocumentUploadRequest(BaseModel):
    """Request for student personal document upload."""

    subject: str
    level: EducationLevel
    year: str
    document_category: DocumentCategory = DocumentCategory.EXAM_PAPER
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
    uploader_name: str | None = None
    ingestion_status: str
    document_category: str = "exam_paper"
    is_personal: bool = False
    is_shared: bool = False
    official_duration_minutes: int | None = None
    page_count: int | None = None
    subject_id: uuid.UUID | None = None
    collection_name: str | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    archived_by: uuid.UUID | None = None
    archive_reason: str | None = None
    archiver_name: str | None = None
    comment_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentArchiveRequest(BaseModel):
    """Request body for archiving a document with a reason."""

    reason: str | None = None


# ── Document Comment schemas ─────────────────────────────────────────────────


class CommentType(str, Enum):
    COMMENT = "comment"
    HIGHLIGHT = "highlight"
    ISSUE = "issue"


class DocumentCommentCreate(BaseModel):
    """Create a new comment/highlight on a document."""

    content: str
    comment_type: CommentType = CommentType.COMMENT
    page_number: int | None = None
    highlight_text: str | None = None


class DocumentCommentUpdate(BaseModel):
    """Update an existing comment."""

    content: str | None = None
    resolved: bool | None = None


class DocumentCommentRead(BaseModel):
    """A document comment returned from API."""

    id: uuid.UUID
    document_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None = None
    content: str
    comment_type: str = "comment"
    page_number: int | None = None
    highlight_text: str | None = None
    resolved: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Sharing schemas ──────────────────────────────────────────────────────────


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
