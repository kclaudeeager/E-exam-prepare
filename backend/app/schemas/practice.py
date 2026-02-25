"""Practice session schemas — question-by-question RAG-graded practice."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PracticeStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DocumentCategory(str, Enum):
    EXAM_PAPER = "exam_paper"
    MARKING_SCHEME = "marking_scheme"
    SYLLABUS = "syllabus"
    TEXTBOOK = "textbook"
    NOTES = "notes"
    OTHER = "other"


class PracticeStartRequest(BaseModel):
    """Start a new practice session.

    Primary flow: provide subject_id to practice across all papers in a subject.
    Optional document_id for single-paper practice (e.g. real-exam simulation).
    """

    subject_id: uuid.UUID  # Required: which subject to practice
    document_id: uuid.UUID | None = None  # Optional: restrict to single paper
    question_count: int = 5
    difficulty: str = "medium"
    topics: list[str] | None = None
    mode: str = "practice"  # "practice" or "real_exam"


class QuestionSourceReference(BaseModel):
    """Lightweight source ref attached to a question (so student can view the page)."""

    page_number: int | None = None
    document_name: str | None = None
    document_id: str | None = None
    content_snippet: str | None = None  # brief excerpt for context


class PracticeQuestionRead(BaseModel):
    """A single question served to the student during practice."""

    id: uuid.UUID
    question_number: int
    text: str
    question_type: str  # mcq, short-answer, essay
    options: list[str] | None = None
    topic: str | None = None
    difficulty: str | None = None
    total_questions: int
    source_references: list[QuestionSourceReference] = []


class PracticeAnswerSubmit(BaseModel):
    """Submit an answer to a practice question."""

    question_id: uuid.UUID | None = None
    question_text: str | None = None  # For RAG-generated Qs without DB ID
    answer_text: str | None = None
    # For handwritten answers: base64-encoded image
    answer_image_base64: str | None = None


class SourceReference(BaseModel):
    """A reference to where in the document the answer was found."""

    page_number: int | None = None
    content: str
    score: float = 0.0
    document_name: str | None = None
    document_id: str | None = None


class PracticeAnswerResult(BaseModel):
    """Result of grading a single practice answer."""

    question_text: str
    student_answer: str
    is_correct: bool | None = None
    score: float  # 0.0 to 1.0
    feedback: str  # Detailed RAG-generated explanation
    correct_answer: str | None = None
    source_references: list[SourceReference] = []
    was_handwritten: bool = False
    ocr_text: str | None = None


class PracticeSessionRead(BaseModel):
    """Practice session summary."""

    id: uuid.UUID
    student_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    status: PracticeStatus
    total_questions: int
    answered_count: int
    correct_count: int
    accuracy: float = 0.0
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PracticeSessionDetail(PracticeSessionRead):
    """Practice session with all answers."""

    answers: list[PracticeAnswerResult] = []
