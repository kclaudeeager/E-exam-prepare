"""Attempt schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AttemptSubmit(BaseModel):
    """POST /api/attempts — submit all answers for a quiz."""

    quiz_id: uuid.UUID
    answers: dict[str, str]  # {question_id: answer_text}


class TopicScore(BaseModel):
    """Per‑topic score in an attempt result."""

    topic: str
    correct: int
    total: int
    accuracy: float


class AttemptRead(BaseModel):
    """Attempt result returned after grading."""

    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    score: int
    total: int
    percentage: float
    topic_breakdown: list[TopicScore] = []
    started_at: datetime
    submitted_at: datetime | None = None

    model_config = {"from_attributes": True}


class AttemptAnswerRead(BaseModel):
    """Single answer within an attempt detail view."""

    question_id: uuid.UUID
    question_text: str
    student_answer: str
    correct_answer: str | None = None
    is_correct: bool | None = None
    topic: str | None = None
    options: list[str] | None = None


class AttemptDetailRead(AttemptRead):
    """Attempt with full answer details for review."""

    answers: list[AttemptAnswerRead] = []
