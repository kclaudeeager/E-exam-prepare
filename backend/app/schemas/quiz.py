"""Quiz schemas."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class QuizMode(str, Enum):
    ADAPTIVE = "adaptive"
    TOPIC_FOCUSED = "topic-focused"
    REAL_EXAM = "real-exam"


class EducationLevel(str, Enum):
    P6 = "P6"
    S3 = "S3"
    S6 = "S6"
    TTC = "TTC"


class QuizGenerateRequest(BaseModel):
    """POST /api/quiz/generate — now requires document selection."""

    mode: QuizMode
    document_id: uuid.UUID  # Required: which exam paper to practice from
    subject: str  # Required: which subject area
    topics: list[str] | None = None  # Optional: filter within subject
    difficulty: str = "medium"
    count: int = 15


class QuestionRead(BaseModel):
    """Single question inside a quiz response."""

    id: uuid.UUID
    text: str
    topic: str | None = None
    subtopic: str | None = None
    difficulty: str | None = None
    options: list[str] | None = None
    question_type: str
    source_document: str | None = None

    model_config = {"from_attributes": True}


class QuizRead(BaseModel):
    """Full quiz returned to a student."""

    id: uuid.UUID
    mode: QuizMode
    duration_minutes: int | None = None
    instructions: str | None = None
    questions: list[QuestionRead]
    question_count: int
    document_id: uuid.UUID | None = None  # Track source document
    created_at: datetime

    model_config = {"from_attributes": True}
