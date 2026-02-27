"""SQLAlchemy ORM models for the exam‑prep platform.

Tables
------
- users           – student / admin profiles
- documents       – uploaded exam papers + answer PDFs
- topics          – subject → topic hierarchy
- questions       – extracted from documents (linked to topic)
- solutions       – answer explanations (linked to question)
- subscriptions   – student ↔ topic many‑to‑many
- quizzes         – generated quiz instances
- attempts        – student exam submissions
- attempt_answers – per‑question answers in an attempt
- progress        – per‑student per‑topic running metrics
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── helpers ───────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ── Enums (stored as VARCHAR via SQLAlchemy Enum) ─────────────────────────────


class RoleEnum(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class AccountTypeEnum(str, enum.Enum):
    ACADEMIC = "academic"
    PRACTICE = "practice"


class EducationLevelEnum(str, enum.Enum):
    P6 = "P6"
    S3 = "S3"
    S6 = "S6"
    TTC = "TTC"
    DRIVING = "DRIVING"


class IngestionStatusEnum(str, enum.Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    COMPLETED = "completed"
    FAILED = "failed"


class QuizModeEnum(str, enum.Enum):
    ADAPTIVE = "adaptive"
    TOPIC_FOCUSED = "topic-focused"
    REAL_EXAM = "real-exam"


class QuestionTypeEnum(str, enum.Enum):
    MCQ = "mcq"
    SHORT_ANSWER = "short-answer"
    ESSAY = "essay"


class DocumentCategoryEnum(str, enum.Enum):
    EXAM_PAPER = "exam_paper"
    MARKING_SCHEME = "marking_scheme"
    SYLLABUS = "syllabus"
    TEXTBOOK = "textbook"
    NOTES = "notes"
    DRIVING_MANUAL = "driving_manual"
    OTHER = "other"


class PracticeStatusEnum(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# ── Users ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum"), default=RoleEnum.STUDENT
    )
    account_type: Mapped[AccountTypeEnum] = mapped_column(
        Enum(
            AccountTypeEnum,
            name="account_type_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AccountTypeEnum.ACADEMIC,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    education_level: Mapped[EducationLevelEnum | None] = mapped_column(
        Enum(EducationLevelEnum, name="education_level_enum", create_constraint=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="student")
    progress_records: Mapped[list["Progress"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    uploaded_documents: Mapped[list["Document"]] = relationship(
        back_populates="uploader", foreign_keys="Document.uploaded_by"
    )
    shared_documents: Mapped[list["DocumentShare"]] = relationship(
        back_populates="shared_with_user", cascade="all, delete-orphan"
    )
    enrolled_subjects: Mapped[list["StudentSubject"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


# ── Subjects ──────────────────────────────────────────────────────────────────


class Subject(Base):
    """A subject available for a given education level (e.g. S6 Mathematics)."""

    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[EducationLevelEnum] = mapped_column(
        Enum(EducationLevelEnum, name="education_level_enum", create_constraint=False)
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # emoji icon
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    enrollments: Mapped[list["StudentSubject"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="subject_rel",
        foreign_keys="Document.subject_id",
    )

    __table_args__ = (
        UniqueConstraint("name", "level", name="uq_subject_name_level"),
    )


class StudentSubject(Base):
    """Enrollment of a student in a subject."""

    __tablename__ = "student_subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    student: Mapped["User"] = relationship(back_populates="enrolled_subjects")
    subject: Mapped["Subject"] = relationship(back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )


# ── Topics ────────────────────────────────────────────────────────────────────


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    subject: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )

    parent: Mapped["Topic | None"] = relationship(
        "Topic", remote_side="Topic.id", back_populates="children"
    )
    children: Mapped[list["Topic"]] = relationship("Topic", back_populates="parent")
    questions: Mapped[list["Question"]] = relationship(back_populates="topic")

    __table_args__ = (
        UniqueConstraint("subject", "name", name="uq_topic_subject_name"),
    )


# ── Documents ─────────────────────────────────────────────────────────────────


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    filename: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[EducationLevelEnum] = mapped_column(
        Enum(EducationLevelEnum, name="education_level_enum")
    )
    year: Mapped[str] = mapped_column(String(10))
    official_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    marking_scheme: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_personal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ingestion_status: Mapped[IngestionStatusEnum] = mapped_column(
        Enum(IngestionStatusEnum, name="ingestion_status_enum"),
        default=IngestionStatusEnum.PENDING,
    )
    collection_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document_category: Mapped[DocumentCategoryEnum] = mapped_column(
        Enum(DocumentCategoryEnum, name="document_category_enum"),
        default=DocumentCategoryEnum.EXAM_PAPER,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    uploader: Mapped["User"] = relationship(
        "User", foreign_keys=[uploaded_by], back_populates="uploaded_documents"
    )
    subject_rel: Mapped["Subject | None"] = relationship(
        "Subject", back_populates="documents", foreign_keys=[subject_id]
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="source_document", cascade="all, delete-orphan"
    )
    shared_with: Mapped[list["DocumentShare"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    comments: Mapped[list["DocumentComment"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="DocumentComment.created_at.desc()",
    )
    archiver: Mapped["User | None"] = relationship(
        "User", foreign_keys=[archived_by],
    )


# ── Document Comments / Highlights (admin annotations) ────────────────────────


class DocumentComment(Base):
    """Admin comment or highlight on a document."""

    __tablename__ = "document_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    content: Mapped[str] = mapped_column(Text)
    comment_type: Mapped[str] = mapped_column(
        String(20), default="comment"
    )  # "comment", "highlight", "issue"
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    highlight_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # text being highlighted
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    document: Mapped["Document"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])


# ── Document Sharing (personal document sharing between students) ──────────────


class DocumentShare(Base):
    __tablename__ = "document_shares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    shared_with_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    document: Mapped["Document"] = relationship(back_populates="shared_with")
    shared_with_user: Mapped["User"] = relationship(back_populates="shared_documents")

    __table_args__ = (
        UniqueConstraint("document_id", "shared_with_user_id", name="uq_document_share"),
    )


# ── Questions ─────────────────────────────────────────────────────────────────


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionTypeEnum] = mapped_column(
        Enum(QuestionTypeEnum, name="question_type_enum"), default=QuestionTypeEnum.MCQ
    )
    options: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string for MCQ
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    topic: Mapped["Topic | None"] = relationship(back_populates="questions")
    source_document: Mapped["Document"] = relationship(back_populates="questions")
    solution: Mapped["Solution | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


# ── Solutions ─────────────────────────────────────────────────────────────────


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), unique=True
    )
    explanation: Mapped[str] = mapped_column(Text)
    source_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    question: Mapped["Question"] = relationship(back_populates="solution")


# ── Subscriptions (student ↔ topic) ──────────────────────────────────────────


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    topic: Mapped["Topic"] = relationship("Topic")

    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic"),)


# ── Quizzes ───────────────────────────────────────────────────────────────────


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    mode: Mapped[QuizModeEnum] = mapped_column(
        Enum(QuizModeEnum, name="quiz_mode_enum")
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[EducationLevelEnum | None] = mapped_column(
        Enum(EducationLevelEnum, name="education_level_enum", create_constraint=False),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    creator: Mapped["User"] = relationship("User")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    """Join table between Quiz and Question with ordering."""

    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    quiz: Mapped["Quiz"] = relationship(back_populates="quiz_questions")
    question: Mapped["Question"] = relationship("Question")


# ── Attempts ──────────────────────────────────────────────────────────────────


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    student: Mapped["User"] = relationship(back_populates="attempts")
    quiz: Mapped["Quiz"] = relationship("Quiz")
    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AttemptAnswer(Base):
    """Individual answer within an attempt."""

    __tablename__ = "attempt_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attempts.id")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id")
    )
    answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship("Question")


# ── Progress (per‑student, per‑topic running metrics) ─────────────────────────


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id")
    )
    total_correct: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    student: Mapped["User"] = relationship(back_populates="progress_records")
    topic: Mapped["Topic"] = relationship("Topic")

    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_student_topic_progress"),
    )


# ── Practice Sessions (question-by-question with RAG grading) ────────────────


class PracticeSession(Base):
    """A practice session where a student works through questions one by one."""

    __tablename__ = "practice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    collection_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[PracticeStatusEnum] = mapped_column(
        Enum(PracticeStatusEnum, name="practice_status_enum"),
        default=PracticeStatusEnum.IN_PROGRESS,
    )
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    student: Mapped["User"] = relationship("User")
    subject: Mapped["Subject | None"] = relationship("Subject")
    document: Mapped["Document | None"] = relationship("Document")
    answers: Mapped[list["PracticeAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PracticeAnswer(Base):
    """A student's answer to a single practice question, graded by RAG."""

    __tablename__ = "practice_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practice_sessions.id")
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True
    )
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(20), default="short-answer")
    student_answer: Mapped[str] = mapped_column(Text)
    is_handwritten: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_references: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: [{page, content, score}]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    session: Mapped["PracticeSession"] = relationship(back_populates="answers")
    question: Mapped["Question | None"] = relationship("Question")


# ── Chat Sessions (conversation history for Ask AI) ──────────────────────────


class ChatSession(Base):
    """A conversation session between a student and the AI tutor."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    collection: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(500), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """A single message in a chat session."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id")
    )
    role: Mapped[str] = mapped_column(String(20))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string of sources
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
