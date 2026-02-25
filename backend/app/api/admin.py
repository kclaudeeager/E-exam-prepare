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
    PracticeSession,
    PracticeStatusEnum,
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
    StudentPerformanceTrend,
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
        # Aggregate from attempts table (quizzes)
        attempt_agg = (
            db.query(
                func.count(Attempt.id).label("total_attempts"),
                func.coalesce(func.sum(Attempt.score), 0).label("total_correct"),
                func.coalesce(func.sum(Attempt.total), 0).label("total_questions"),
                func.max(Attempt.submitted_at).label("last_at"),
            )
            .filter(Attempt.student_id == s.id, Attempt.submitted_at.isnot(None))
            .one()
        )

        # Aggregate from practice sessions (RAG practice)
        practice_agg = (
            db.query(
                func.count(PracticeSession.id).label("total_sessions"),
                func.coalesce(func.sum(PracticeSession.correct_count), 0).label("total_correct"),
                func.coalesce(func.sum(PracticeSession.total_questions), 0).label("total_questions"),
                func.max(PracticeSession.completed_at).label("last_at"),
            )
            .filter(
                PracticeSession.student_id == s.id,
                PracticeSession.status == PracticeStatusEnum.COMPLETED,
            )
            .one()
        )

        # Aggregate from Progress table for best overall accuracy signal
        progress_agg = (
            db.query(
                func.coalesce(func.sum(Progress.total_correct), 0).label("total_correct"),
                func.coalesce(func.sum(Progress.total_questions), 0).label("total_questions"),
                func.max(Progress.last_attempted_at).label("last_at"),
            )
            .filter(Progress.student_id == s.id)
            .one()
        )

        progress_total_questions = progress_agg.total_questions or 0
        progress_total_correct = progress_agg.total_correct or 0
        if progress_total_questions:
            overall_accuracy = round(progress_total_correct / progress_total_questions, 4)
        else:
            combined_total_correct = (attempt_agg.total_correct or 0) + (
                practice_agg.total_correct or 0
            )
            combined_total_questions = (attempt_agg.total_questions or 0) + (
                practice_agg.total_questions or 0
            )
            overall_accuracy = (
                round(combined_total_correct / combined_total_questions, 4)
                if combined_total_questions
                else 0.0
            )

        total_attempts = (
            db.query(func.coalesce(func.sum(Progress.attempt_count), 0))
            .filter(Progress.student_id == s.id)
            .scalar()
        ) or 0

        last_attempt_at = max(
            [
                dt
                for dt in [
                    progress_agg.last_at,
                    attempt_agg.last_at,
                    practice_agg.last_at,
                ]
                if dt is not None
            ],
            default=None,
        )

        results.append(
            StudentSummary(
                id=s.id,
                email=s.email,
                full_name=s.full_name,
                is_active=s.is_active,
                created_at=s.created_at,
                total_attempts=total_attempts,
                overall_accuracy=overall_accuracy,
                last_attempt_at=last_attempt_at,
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

    # Aggregate attempts (quizzes)
    attempt_agg = (
        db.query(
            func.count(Attempt.id).label("total_attempts"),
            func.coalesce(func.sum(Attempt.score), 0).label("total_correct"),
            func.coalesce(func.sum(Attempt.total), 0).label("total_questions"),
            func.max(Attempt.submitted_at).label("last_at"),
        )
        .filter(Attempt.student_id == student.id, Attempt.submitted_at.isnot(None))
        .one()
    )

    # Aggregate practice sessions
    practice_agg = (
        db.query(
            func.count(PracticeSession.id).label("total_sessions"),
            func.coalesce(func.sum(PracticeSession.correct_count), 0).label("total_correct"),
            func.coalesce(func.sum(PracticeSession.total_questions), 0).label("total_questions"),
            func.max(PracticeSession.completed_at).label("last_at"),
        )
        .filter(
            PracticeSession.student_id == student.id,
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
        )
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

    # Recent attempts (quizzes + practice sessions)
    recent_quiz_rows = (
        db.query(Attempt)
        .filter(Attempt.student_id == student.id, Attempt.submitted_at.isnot(None))
        .order_by(Attempt.submitted_at.desc())
        .limit(20)
        .all()
    )
    recent_practice_rows = (
        db.query(PracticeSession, Document.filename)
        .outerjoin(Document, PracticeSession.document_id == Document.id)
        .filter(
            PracticeSession.student_id == student.id,
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
        )
        .order_by(PracticeSession.completed_at.desc())
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
        for a in recent_quiz_rows
    ]
    recent_attempts.extend(
        [
            StudentAttemptSummary(
                id=s.id,
                score=s.correct_count,
                total=s.total_questions,
                percentage=(
                    round((s.correct_count / s.total_questions) * 100, 2)
                    if s.total_questions
                    else 0.0
                ),
                document_name=doc_name,
                started_at=s.created_at,
                submitted_at=s.completed_at,
            )
            for s, doc_name in recent_practice_rows
        ]
    )
    recent_attempts.sort(
        key=lambda x: x.submitted_at or x.started_at, reverse=True
    )
    recent_attempts = recent_attempts[:20]

    # Overall accuracy from Progress totals (fallback to attempts + practice)
    total_correct = sum(r.total_correct for r in progress_rows)
    total_questions = sum(r.total_questions for r in progress_rows)
    if total_questions:
        overall_accuracy = round(total_correct / total_questions, 4)
    else:
        combined_total_correct = (attempt_agg.total_correct or 0) + (
            practice_agg.total_correct or 0
        )
        combined_total_questions = (attempt_agg.total_questions or 0) + (
            practice_agg.total_questions or 0
        )
        overall_accuracy = (
            round(combined_total_correct / combined_total_questions, 4)
            if combined_total_questions
            else 0.0
        )

    total_attempts = sum(r.attempt_count for r in progress_rows)
    last_attempt_at = max(
        [
            dt
            for dt in [
                max((r.last_attempted_at for r in progress_rows), default=None),
                attempt_agg.last_at,
                practice_agg.last_at,
            ]
            if dt is not None
        ],
        default=None,
    )

    return StudentDetail(
        id=student.id,
        email=student.email,
        full_name=student.full_name,
        is_active=student.is_active,
        created_at=student.created_at,
        total_attempts=total_attempts,
        overall_accuracy=overall_accuracy,
        last_attempt_at=last_attempt_at,
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
    attempt_totals = (
        db.query(
            func.count(Attempt.id).label("total_attempts"),
            func.coalesce(func.sum(Attempt.score), 0).label("total_correct"),
            func.coalesce(func.sum(Attempt.total), 0).label("total_questions"),
        )
        .filter(Attempt.submitted_at.isnot(None))
        .one()
    )
    practice_totals = (
        db.query(
            func.count(PracticeSession.id).label("total_sessions"),
            func.coalesce(func.sum(PracticeSession.correct_count), 0).label("total_correct"),
            func.coalesce(func.sum(PracticeSession.total_questions), 0).label("total_questions"),
        )
        .filter(PracticeSession.status == PracticeStatusEnum.COMPLETED)
        .one()
    )
    total_attempts = (attempt_totals.total_attempts or 0) + (
        practice_totals.total_sessions or 0
    )

    combined_total_correct = (attempt_totals.total_correct or 0) + (
        practice_totals.total_correct or 0
    )
    combined_total_questions = (attempt_totals.total_questions or 0) + (
        practice_totals.total_questions or 0
    )
    avg_accuracy = (
        round(combined_total_correct / combined_total_questions, 4)
        if combined_total_questions
        else 0.0
    )

    # Active students: distinct students with attempts in last 7/30 days
    active_attempt_7d = (
        db.query(distinct(Attempt.student_id))
        .filter(Attempt.submitted_at >= now - timedelta(days=7))
        .all()
    )
    active_practice_7d = (
        db.query(distinct(PracticeSession.student_id))
        .filter(PracticeSession.completed_at >= now - timedelta(days=7))
        .all()
    )
    active_7d = len(
        {
            *[row[0] for row in active_attempt_7d],
            *[row[0] for row in active_practice_7d],
        }
    )

    active_attempt_30d = (
        db.query(distinct(Attempt.student_id))
        .filter(Attempt.submitted_at >= now - timedelta(days=30))
        .all()
    )
    active_practice_30d = (
        db.query(distinct(PracticeSession.student_id))
        .filter(PracticeSession.completed_at >= now - timedelta(days=30))
        .all()
    )
    active_30d = len(
        {
            *[row[0] for row in active_attempt_30d],
            *[row[0] for row in active_practice_30d],
        }
    )

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
    attempt_date = func.date(Attempt.submitted_at)
    attempt_trend_rows = (
        db.query(
            attempt_date.label("day"),
            func.count(Attempt.id).label("attempts"),
            func.coalesce(func.sum(Attempt.score), 0).label("correct"),
            func.coalesce(func.sum(Attempt.total), 0).label("total"),
            func.count(distinct(Attempt.student_id)).label("active_students"),
        )
        .filter(
            Attempt.submitted_at.isnot(None),
            Attempt.submitted_at >= window_start,
        )
        .group_by(attempt_date)
        .order_by(attempt_date)
        .all()
    )

    practice_date = func.date(PracticeSession.completed_at)
    practice_trend_rows = (
        db.query(
            practice_date.label("day"),
            func.count(PracticeSession.id).label("attempts"),
            func.coalesce(func.sum(PracticeSession.correct_count), 0).label("correct"),
            func.coalesce(func.sum(PracticeSession.total_questions), 0).label("total"),
            func.count(distinct(PracticeSession.student_id)).label("active_students"),
        )
        .filter(
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
            PracticeSession.completed_at.isnot(None),
            PracticeSession.completed_at >= window_start,
        )
        .group_by(practice_date)
        .order_by(practice_date)
        .all()
    )

    attempt_student_rows = (
        db.query(attempt_date.label("day"), Attempt.student_id)
        .filter(
            Attempt.submitted_at.isnot(None),
            Attempt.submitted_at >= window_start,
        )
        .distinct()
        .all()
    )
    practice_student_rows = (
        db.query(practice_date.label("day"), PracticeSession.student_id)
        .filter(
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
            PracticeSession.completed_at.isnot(None),
            PracticeSession.completed_at >= window_start,
        )
        .distinct()
        .all()
    )

    trend_map: dict[str, dict] = {}
    for row in attempt_trend_rows:
        key = str(row.day)
        trend_map[key] = {
            "attempts": row.attempts or 0,
            "correct": row.correct or 0,
            "total": row.total or 0,
            "active_students": set(),
        }
    for row in practice_trend_rows:
        key = str(row.day)
        trend_map.setdefault(
            key, {"attempts": 0, "correct": 0, "total": 0, "active_students": set()}
        )
        trend_map[key]["attempts"] += row.attempts or 0
        trend_map[key]["correct"] += row.correct or 0
        trend_map[key]["total"] += row.total or 0

    for day, student_id in attempt_student_rows:
        key = str(day)
        trend_map.setdefault(
            key, {"attempts": 0, "correct": 0, "total": 0, "active_students": set()}
        )
        trend_map[key]["active_students"].add(student_id)

    for day, student_id in practice_student_rows:
        key = str(day)
        trend_map.setdefault(
            key, {"attempts": 0, "correct": 0, "total": 0, "active_students": set()}
        )
        trend_map[key]["active_students"].add(student_id)

    trends = []
    for day in sorted(trend_map.keys()):
        entry = trend_map[day]
        total_questions = entry["total"]
        avg_accuracy = (
            round(entry["correct"] / total_questions, 4)
            if total_questions
            else 0.0
        )
        trends.append(
            TrendPoint(
                date=day,
                attempts=entry["attempts"],
                avg_accuracy=avg_accuracy,
                active_students=len(entry["active_students"]),
            )
        )

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
    recent_quiz_rows = (
        db.query(Attempt, User.full_name)
        .join(User, Attempt.student_id == User.id)
        .filter(Attempt.submitted_at.isnot(None))
        .order_by(Attempt.submitted_at.desc())
        .limit(15)
        .all()
    )
    recent_practice_rows = (
        db.query(PracticeSession, User.full_name)
        .join(User, PracticeSession.student_id == User.id)
        .filter(
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
            PracticeSession.completed_at.isnot(None),
        )
        .order_by(PracticeSession.completed_at.desc())
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
        for a, name in recent_quiz_rows
    ]
    recent_attempts.extend(
        [
            RecentAttempt(
                id=s.id,
                student_name=name,
                score=s.correct_count,
                total=s.total_questions,
                percentage=(
                    round((s.correct_count / s.total_questions) * 100, 2)
                    if s.total_questions
                    else 0.0
                ),
                submitted_at=s.completed_at,
            )
            for s, name in recent_practice_rows
        ]
    )
    recent_attempts.sort(
        key=lambda x: x.submitted_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    recent_attempts = recent_attempts[:15]

    return AnalyticsResponse(
        overview=overview,
        subject_stats=subject_stats,
        trends=trends,
        topic_stats=topic_stats,
        recent_attempts=recent_attempts,
    )


# ── 4. Student Performance Analytics (Personalized Learning Insights) ──────────


@router.get("/students/{student_id}/performance", response_model=StudentPerformanceTrend)
def get_student_performance(
    student_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Get detailed performance metrics for a single student.
    
    Returns:
    - Overall accuracy and attempt count
    - Weak topics (accuracy < WEAK_TOPIC_THRESHOLD)
    - Strong topics (high accuracy)
    - Recent attempts with document sources
    - Learning trajectory
    
    Used by admins to identify students needing intervention.
    """
    import uuid as _uuid

    try:
        student_uuid = _uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID"
        )

    student = db.query(User).filter(User.id == student_uuid).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    # Overall accuracy
    student_progress = (
        db.query(Progress).filter(Progress.student_id == student_uuid).all()
    )
    overall_accuracy = 0.0
    if student_progress:
        total_correct = sum(p.total_correct for p in student_progress)
        total_questions = sum(p.total_questions for p in student_progress)
        overall_accuracy = (
            round(total_correct / total_questions, 4) if total_questions else 0.0
        )

    # Attempt count (quizzes + practice sessions)
    attempt_count = (
        db.query(func.count(Attempt.id))
        .filter(Attempt.student_id == student_uuid)
        .scalar()
        or 0
    )
    practice_count = (
        db.query(func.count(PracticeSession.id))
        .filter(
            PracticeSession.student_id == student_uuid,
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
        )
        .scalar()
        or 0
    )
    attempt_count += practice_count

    # Weak topics (accuracy < threshold)
    weak_topics_data = [
        {
            "topic_name": p.topic.name if p.topic else "Unknown",
            "accuracy": round(p.accuracy, 4),
            "attempt_count": p.attempt_count,
        }
        for p in student_progress
        if p.accuracy < settings.WEAK_TOPIC_THRESHOLD
    ]
    weak_topics_data.sort(key=lambda x: x["accuracy"])  # Sort by ascending accuracy

    # Strong topics (accuracy >= 80%)
    strong_topics_data = [
        {
            "topic_name": p.topic.name if p.topic else "Unknown",
            "accuracy": round(p.accuracy, 4),
            "attempt_count": p.attempt_count,
        }
        for p in student_progress
        if p.accuracy >= 0.80
    ]
    strong_topics_data.sort(key=lambda x: x["accuracy"], reverse=True)

    # Recent attempts with document source
    recent_attempts_rows = (
        db.query(Attempt, Document.filename)
        .outerjoin(Document, Attempt.document_id == Document.id)
        .filter(Attempt.student_id == student_uuid)
        .order_by(Attempt.submitted_at.desc())
        .limit(10)
        .all()
    )
    recent_practice_rows = (
        db.query(PracticeSession, Document.filename)
        .outerjoin(Document, PracticeSession.document_id == Document.id)
        .filter(
            PracticeSession.student_id == student_uuid,
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
        )
        .order_by(PracticeSession.completed_at.desc())
        .limit(10)
        .all()
    )
    recent_attempts = [
        StudentAttemptSummary(
            id=a.id,
            score=a.score,
            total=a.total,
            percentage=a.percentage,
            document_name=doc_name,
            started_at=a.started_at,
            submitted_at=a.submitted_at,
        )
        for a, doc_name in recent_attempts_rows
    ]
    recent_attempts.extend(
        [
            StudentAttemptSummary(
                id=s.id,
                score=s.correct_count,
                total=s.total_questions,
                percentage=(
                    round((s.correct_count / s.total_questions) * 100, 2)
                    if s.total_questions
                    else 0.0
                ),
                document_name=doc_name,
                started_at=s.created_at,
                submitted_at=s.completed_at,
            )
            for s, doc_name in recent_practice_rows
        ]
    )
    recent_attempts.sort(
        key=lambda x: x.submitted_at or x.started_at, reverse=True
    )
    recent_attempts = recent_attempts[:10]

    # Last attempted date
    last_attempt = (
        db.query(Attempt)
        .filter(Attempt.student_id == student_uuid)
        .order_by(Attempt.submitted_at.desc())
        .first()
    )
    last_practice = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.student_id == student_uuid,
            PracticeSession.status == PracticeStatusEnum.COMPLETED,
        )
        .order_by(PracticeSession.completed_at.desc())
        .first()
    )
    last_attempted_at = max(
        [
            dt
            for dt in [
                last_attempt.submitted_at if last_attempt else None,
                last_practice.completed_at if last_practice else None,
            ]
            if dt is not None
        ],
        default=None,
    )

    return StudentPerformanceTrend(
        student_id=student_uuid,
        student_name=student.full_name,
        overall_accuracy=overall_accuracy,
        attempt_count=attempt_count,
        weak_topics=weak_topics_data,
        strong_topics=strong_topics_data,
        recent_attempts=recent_attempts,
        last_attempted_at=last_attempted_at,
    )


@router.get("/students/weak-topics/summary")
def get_weak_topics_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Get a summary of students with weak topics across the platform.
    
    Returns list of students sorted by urgency (lowest accuracy topics first).
    Used to identify students who need personalized intervention.
    """
    from app.schemas.admin import StudentPerformanceTrend

    # Get all students with weak topics
    weak_progress = (
        db.query(Progress, User.full_name, User.id)
        .join(User, Progress.student_id == User.id)
        .filter(Progress.accuracy < settings.WEAK_TOPIC_THRESHOLD)
        .order_by(Progress.accuracy.asc())
        .all()
    )

    results = {}
    for progress, student_name, student_id in weak_progress:
        if student_id not in results:
            results[student_id] = {
                "student_name": student_name,
                "weak_topics": [],
            }
        if progress.topic:
            results[student_id]["weak_topics"].append(
                {
                    "topic_name": progress.topic.name,
                    "accuracy": round(progress.accuracy, 4),
                }
            )

    return {
        "students_needing_help": [
            {
                "student_id": sid,
                "student_name": data["student_name"],
                "weak_topic_count": len(data["weak_topics"]),
                "weakest_topics": sorted(
                    data["weak_topics"], key=lambda x: x["accuracy"]
                )[:3],
            }
            for sid, data in results.items()
        ],
        "total_students_with_weak_topics": len(results),
    }
