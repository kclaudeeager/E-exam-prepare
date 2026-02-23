"""Admin dashboard schemas — student listing, system analytics."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.progress import TopicMetric


# ── Student listing ──────────────────────────────────────────────────────────


class StudentSummary(BaseModel):
    """Compact view for the admin student list."""

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    total_attempts: int = 0
    overall_accuracy: float = 0.0
    last_attempt_at: datetime | None = None

    model_config = {"from_attributes": True}


class StudentDetail(StudentSummary):
    """Full view for a single student."""

    topic_metrics: list[TopicMetric] = []
    weak_topics: list[str] = []
    recent_attempts: list["StudentAttemptSummary"] = []


class StudentAttemptSummary(BaseModel):
    """Lightweight attempt row for the admin detail view."""

    id: uuid.UUID
    score: int
    total: int
    percentage: float
    started_at: datetime
    submitted_at: datetime | None = None


# ── System analytics ─────────────────────────────────────────────────────────


class SystemOverview(BaseModel):
    """High-level platform KPIs."""

    total_students: int = 0
    total_admins: int = 0
    total_documents: int = 0
    total_questions: int = 0
    total_quizzes: int = 0
    total_attempts: int = 0
    avg_accuracy: float = 0.0
    active_students_7d: int = 0
    active_students_30d: int = 0


class SubjectStat(BaseModel):
    """Per-subject aggregate."""

    subject: str
    document_count: int = 0
    question_count: int = 0
    attempt_count: int = 0
    avg_accuracy: float = 0.0


class TrendPoint(BaseModel):
    """Single data-point on a time-series chart."""

    date: str  # ISO date string  YYYY-MM-DD
    attempts: int = 0
    avg_accuracy: float = 0.0
    active_students: int = 0


class TopicStat(BaseModel):
    """Per-topic aggregate across all students."""

    topic: str
    total_attempts: int = 0
    avg_accuracy: float = 0.0
    student_count: int = 0


class AnalyticsResponse(BaseModel):
    """Full analytics payload."""

    overview: SystemOverview
    subject_stats: list[SubjectStat] = []
    trends: list[TrendPoint] = []
    topic_stats: list[TopicStat] = []
    recent_attempts: list["RecentAttempt"] = []


class RecentAttempt(BaseModel):
    """An attempt row for the admin analytics feed."""

    id: uuid.UUID
    student_name: str
    score: int
    total: int
    percentage: float
    submitted_at: datetime | None = None
