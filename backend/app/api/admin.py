"""Admin dashboard routes — student listing, student detail, system analytics."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings
from app.db.models import (
    Attempt,
    AttemptAnswer,
    Document,
    Progress,
    Question,
    Quiz,
    RoleEnum,
    Topic,
    User,
)
from app.db.session import get_db
from app.schemas.admin import (
    AnalyticsResponse,
    RecentAttempt,
    StudentAttemptSummary,
    StudentDetail,
    StudentSummary,
    SubjectStat,
    SystemOverview,
    TopicStat,
    TrendPoint,
)

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. Student list ──────────────────────────────────────────────────────────


@router.get("/students", response_model=list[StudentSummary])
def list_students(
    search: str | None = Query(None, description="Search by name or email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all students with aggregated attempt stats."""

    q = db.query(User).filter(User.role == RoleEnum.STUDENT)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (User.full_name.ilike(pattern)) | (User.email.ilike(pattern))
        )

    students = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    results: list[StudentSummary] = []
    for s in students:
        # Aggregate from attempts table
        agg = (
            db.query(
                func.count(Attempt.id).label("total_attempts"),
                func.coalesce(func.avg(Attempt.percentage), 0).label("avg_pct"),
                func.max(Attempt.submitted_at).label("last_at"),
            )
            .filter(Attempt.student_id == s.id, Attempt.submitted_at.isnot(None))
            .one()
        )

        results.append(
            StudentSummary(
                id=s.id,
                email=s.email,
                full_name=s.full_name,
                is_active=s.is_active,
                created_at=s.created_at,
                total_attempts=agg.total_attempts or 0,
                overall_accuracy=round((agg.avg_pct or 0) / 100, 4),
                last_attempt_at=agg.last_at,
            )
        )
    return results


# ── 2. Single-student detail ─────────────────────────────────────────────────


@router.get("/students/{student_id}", response_model=StudentDetail)
def get_student_detail(
    student_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return a student's full progress, topic metrics, and recent attempts."""
    import uuid as _uuid

    student = (
        db.query(User)
        .filter(User.id == _uuid.UUID(student_id), User.role == RoleEnum.STUDENT)
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Aggregate
    agg = (
        db.query(
            func.count(Attempt.id).label("total_attempts"),
            func.coalesce(func.avg(Attempt.percentage), 0).label("avg_pct"),
            func.max(Attempt.submitted_at).label("last_at"),
        )
        .filter(Attempt.student_id == student.id, Attempt.submitted_at.isnot(None))
        .one()
    )

    # Topic metrics from Progress table
    from app.schemas.progress import TopicMetric

    progress_rows = db.query(Progress).filter(Progress.student_id == student.id).all()
    topic_metrics = []
    weak_topics = []
    for r in progress_rows:
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

    # Recent attempts
    recent = (
        db.query(Attempt)
        .filter(Attempt.student_id == student.id, Attempt.submitted_at.isnot(None))
        .order_by(Attempt.submitted_at.desc())
        .limit(20)
        .all()
    )
    recent_attempts = [
        StudentAttemptSummary(
            id=a.id,
            score=a.score,
            total=a.total,
            percentage=a.percentage,
            started_at=a.started_at,
            submitted_at=a.submitted_at,
        )
        for a in recent
    ]

    return StudentDetail(
        id=student.id,
        email=student.email,
        full_name=student.full_name,
        is_active=student.is_active,
        created_at=student.created_at,
        total_attempts=agg.total_attempts or 0,
        overall_accuracy=round((agg.avg_pct or 0) / 100, 4),
        last_attempt_at=agg.last_at,
        topic_metrics=topic_metrics,
        weak_topics=weak_topics,
        recent_attempts=recent_attempts,
    )


# ── 3. System analytics ──────────────────────────────────────────────────────


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    days: int = Query(30, ge=7, le=365, description="Trend window in days"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return system-wide KPIs, subject stats, trends, and topic breakdown."""
    now = _utcnow()
    window_start = now - timedelta(days=days)

    # ── overview ──────────────────────────────────────────────────────────
    total_students = db.query(func.count(User.id)).filter(User.role == RoleEnum.STUDENT).scalar() or 0
    total_admins = db.query(func.count(User.id)).filter(User.role == RoleEnum.ADMIN).scalar() or 0
    total_documents = db.query(func.count(Document.id)).filter(Document.is_archived.is_(False)).scalar() or 0
    total_questions = db.query(func.count(Question.id)).scalar() or 0
    total_quizzes = db.query(func.count(Quiz.id)).scalar() or 0
    total_attempts = db.query(func.count(Attempt.id)).filter(Attempt.submitted_at.isnot(None)).scalar() or 0
    avg_accuracy_raw = (
        db.query(func.avg(Attempt.percentage))
        .filter(Attempt.submitted_at.isnot(None))
        .scalar()
    ) or 0
    avg_accuracy = round(avg_accuracy_raw / 100, 4)

    # Active students: distinct students with attempts in last 7/30 days
    active_7d = (
        db.query(func.count(distinct(Attempt.student_id)))
        .filter(Attempt.submitted_at >= now - timedelta(days=7))
        .scalar()
    ) or 0
    active_30d = (
        db.query(func.count(distinct(Attempt.student_id)))
        .filter(Attempt.submitted_at >= now - timedelta(days=30))
        .scalar()
    ) or 0

    overview = SystemOverview(
        total_students=total_students,
        total_admins=total_admins,
        total_documents=total_documents,
        total_questions=total_questions,
        total_quizzes=total_quizzes,
        total_attempts=total_attempts,
        avg_accuracy=avg_accuracy,
        active_students_7d=active_7d,
        active_students_30d=active_30d,
    )

    # ── subject stats ─────────────────────────────────────────────────────
    # Documents grouped by subject
    doc_counts = dict(
        db.query(Document.subject, func.count(Document.id))
        .filter(Document.is_archived.is_(False))
        .group_by(Document.subject)
        .all()
    )
    # Questions grouped by source document's subject
    q_counts = dict(
        db.query(Document.subject, func.count(Question.id))
        .join(Question, Question.document_id == Document.id)
        .group_by(Document.subject)
        .all()
    )

    subjects = sorted(set(list(doc_counts.keys()) + list(q_counts.keys())))
    subject_stats = [
        SubjectStat(
            subject=subj,
            document_count=doc_counts.get(subj, 0),
            question_count=q_counts.get(subj, 0),
        )
        for subj in subjects
    ]

    # ── daily trends ──────────────────────────────────────────────────────
    # Group attempts by date within the window
    date_trunc = func.date(Attempt.submitted_at)
    trend_rows = (
        db.query(
            date_trunc.label("day"),
            func.count(Attempt.id).label("attempts"),
            func.coalesce(func.avg(Attempt.percentage), 0).label("avg_pct"),
            func.count(distinct(Attempt.student_id)).label("active_students"),
        )
        .filter(
            Attempt.submitted_at.isnot(None),
            Attempt.submitted_at >= window_start,
        )
        .group_by(date_trunc)
        .order_by(date_trunc)
        .all()
    )
    trends = [
        TrendPoint(
            date=str(row.day),
            attempts=row.attempts,
            avg_accuracy=round(row.avg_pct / 100, 4),
            active_students=row.active_students,
        )
        for row in trend_rows
    ]

    # ── topic stats ───────────────────────────────────────────────────────
    topic_rows = (
        db.query(
            Topic.name.label("topic"),
            func.sum(Progress.attempt_count).label("total_attempts"),
            func.coalesce(func.avg(Progress.accuracy), 0).label("avg_acc"),
            func.count(distinct(Progress.student_id)).label("student_count"),
        )
        .join(Progress, Progress.topic_id == Topic.id)
        .group_by(Topic.name)
        .order_by(func.sum(Progress.attempt_count).desc())
        .all()
    )
    topic_stats = [
        TopicStat(
            topic=row.topic,
            total_attempts=row.total_attempts or 0,
            avg_accuracy=round(row.avg_acc, 4),
            student_count=row.student_count or 0,
        )
        for row in topic_rows
    ]

    # ── recent attempts feed ──────────────────────────────────────────────
    recent_rows = (
        db.query(Attempt, User.full_name)
        .join(User, Attempt.student_id == User.id)
        .filter(Attempt.submitted_at.isnot(None))
        .order_by(Attempt.submitted_at.desc())
        .limit(15)
        .all()
    )
    recent_attempts = [
        RecentAttempt(
            id=a.id,
            student_name=name,
            score=a.score,
            total=a.total,
            percentage=a.percentage,
            submitted_at=a.submitted_at,
        )
        for a, name in recent_rows
    ]

    return AnalyticsResponse(
        overview=overview,
        subject_stats=subject_stats,
        trends=trends,
        topic_stats=topic_stats,
        recent_attempts=recent_attempts,
    )
