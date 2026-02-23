"""Progress & analytics routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.db.models import Progress, User
from app.db.session import get_db
from app.schemas.progress import ProgressRead, TopicMetric

router = APIRouter()


@router.get("/", response_model=ProgressRead)
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current student's per‑topic progress and recommendations."""
    rows = db.query(Progress).filter(Progress.student_id == current_user.id).all()

    topic_metrics: list[TopicMetric] = []
    weak_topics: list[str] = []
    total_correct = 0
    total_questions = 0
    total_attempts = 0
    last_attempt_at = None

    for r in rows:
        topic_name = r.topic.name if r.topic else "Unknown"
        topic_metrics.append(
            TopicMetric(
                topic=topic_name,
                accuracy=r.accuracy,
                attempts=r.attempt_count,
                last_attempted=r.last_attempted_at,
            )
        )
        if r.accuracy < settings.WEAK_TOPIC_THRESHOLD:
            weak_topics.append(topic_name)

        total_correct += r.total_correct
        total_questions += r.total_questions
        total_attempts += r.attempt_count
        if r.last_attempted_at and (
            last_attempt_at is None or r.last_attempted_at > last_attempt_at
        ):
            last_attempt_at = r.last_attempted_at

    overall_accuracy = (
        round(total_correct / total_questions, 4) if total_questions else 0.0
    )

    # Simple recommendation engine
    recommendations: list[str] = []
    for wt in weak_topics:
        recommendations.append(
            f"Practice more {wt} questions — your accuracy is below {settings.WEAK_TOPIC_THRESHOLD:.0%}."
        )
    if not weak_topics and total_attempts > 0:
        recommendations.append(
            "Great job! All topics are above the threshold. Try a real exam simulation!"
        )

    return ProgressRead(
        student_id=current_user.id,
        overall_accuracy=overall_accuracy,
        total_attempts=total_attempts,
        topic_metrics=topic_metrics,
        weak_topics=weak_topics,
        recommendations=recommendations,
        last_attempt_at=last_attempt_at,
    )
