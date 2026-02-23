"""Progress / analytics schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TopicMetric(BaseModel):
    """Running accuracy for one topic."""

    topic: str
    accuracy: float
    attempts: int
    last_attempted: datetime | None = None


class ProgressRead(BaseModel):
    """Student progress summary."""

    student_id: uuid.UUID
    overall_accuracy: float
    total_attempts: int
    topic_metrics: list[TopicMetric] = []
    weak_topics: list[str] = []
    recommendations: list[str] = []
    last_attempt_at: datetime | None = None
