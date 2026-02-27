"""Subject management and student enrollment routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.models import (
    Document,
    EducationLevelEnum,
    IngestionStatusEnum,
    RoleEnum,
    Subject,
    StudentSubject,
    User,
)
from app.db.session import get_db
from app.schemas.subject import (
    EnrollRequest,
    EnrollResponse,
    SubjectCreate,
    SubjectDetailRead,
    SubjectRead,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Default subjects per education level ─────────────────────────────────────

_DEFAULT_SUBJECTS: dict[str, list[dict[str, str]]] = {
    "P6": [
        {"name": "Mathematics", "icon": "🔢"},
        {"name": "English", "icon": "📝"},
        {"name": "Science and Elementary Technology", "icon": "🔬"},
        {"name": "Social Studies", "icon": "🌍"},
        {"name": "Kinyarwanda", "icon": "📖"},
        {"name": "French", "icon": "🇫🇷"},
    ],
    "S3": [
        {"name": "Mathematics", "icon": "🔢"},
        {"name": "Physics", "icon": "⚡"},
        {"name": "Chemistry", "icon": "🧪"},
        {"name": "Biology", "icon": "🧬"},
        {"name": "English", "icon": "📝"},
        {"name": "Geography", "icon": "🌍"},
        {"name": "History", "icon": "📜"},
        {"name": "Entrepreneurship", "icon": "💼"},
        {"name": "Kinyarwanda", "icon": "📖"},
        {"name": "Computer Science", "icon": "💻"},
    ],
    "S6": [
        {"name": "Mathematics", "icon": "🔢"},
        {"name": "Physics", "icon": "⚡"},
        {"name": "Chemistry", "icon": "🧪"},
        {"name": "Biology", "icon": "🧬"},
        {"name": "English", "icon": "📝"},
        {"name": "Geography", "icon": "🌍"},
        {"name": "History", "icon": "📜"},
        {"name": "Entrepreneurship", "icon": "💼"},
        {"name": "Economics", "icon": "📊"},
        {"name": "Computer Science", "icon": "💻"},
        {"name": "Literature", "icon": "📚"},
        {"name": "French", "icon": "🇫🇷"},
    ],
    "TTC": [
        {"name": "Education Foundations", "icon": "🎓"},
        {"name": "Mathematics", "icon": "🔢"},
        {"name": "English", "icon": "📝"},
        {"name": "Science", "icon": "🔬"},
        {"name": "Social Studies", "icon": "🌍"},
        {"name": "Kinyarwanda", "icon": "📖"},
        {"name": "French", "icon": "🇫🇷"},
        {"name": "Special Needs Education", "icon": "♿"},
    ],
    # Professional levels: only a single catch-all subject.
    # Admin can create additional subjects as needed.
    "DRIVING": [
        {"name": "Driving Prep", "icon": "🚗"},
    ],
}


def ensure_default_subjects(db: Session) -> int:
    """Seed default subjects for all education levels.

    Callable at startup (no auth) or via the admin endpoint.
    Returns the number of new subjects created.
    """
    created = 0
    for level_str, subjects in _DEFAULT_SUBJECTS.items():
        level = EducationLevelEnum(level_str)
        for subj in subjects:
            existing = (
                db.query(Subject)
                .filter(Subject.name == subj["name"], Subject.level == level)
                .first()
            )
            if not existing:
                db.add(
                    Subject(
                        name=subj["name"],
                        level=level,
                        icon=subj.get("icon"),
                    )
                )
                created += 1
    if created:
        db.commit()
    return created


def auto_enroll_user_in_level(db: Session, user_id: uuid.UUID, level: EducationLevelEnum) -> int:
    """Enroll a user in ALL subjects for a given education level.

    Used to auto-enroll practice users (e.g. DRIVING) on registration.
    Returns the number of new enrollments.
    """
    subjects = db.query(Subject).filter(Subject.level == level).all()
    enrolled = 0
    for subj in subjects:
        existing = (
            db.query(StudentSubject)
            .filter(
                StudentSubject.student_id == user_id,
                StudentSubject.subject_id == subj.id,
            )
            .first()
        )
        if not existing:
            db.add(StudentSubject(student_id=user_id, subject_id=subj.id))
            enrolled += 1
    if enrolled:
        db.commit()
    return enrolled


@router.post("/seed-defaults", status_code=status.HTTP_201_CREATED)
def seed_default_subjects(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Seed default subjects for all education levels (admin only)."""
    created = ensure_default_subjects(db)
    return {"message": f"Seeded {created} new subjects", "created": created}


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    body: SubjectCreate,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new subject (admin only)."""
    existing = (
        db.query(Subject)
        .filter(
            Subject.name == body.name,
            Subject.level == EducationLevelEnum(body.level.value),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject '{body.name}' already exists for level {body.level.value}",
        )

    subject = Subject(
        name=body.name,
        level=EducationLevelEnum(body.level.value),
        description=body.description,
        icon=body.icon,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_to_read(subject, db, None)


@router.get("", response_model=list[SubjectRead])
def list_subjects(
    level: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List subjects, optionally filtered by education level.

    For students: shows subjects for their education level with enrollment status.
    For admins: shows all subjects.
    """
    query = db.query(Subject)

    if level:
        query = query.filter(Subject.level == EducationLevelEnum(level))
    elif (
        current_user.role == RoleEnum.STUDENT
        and current_user.education_level is not None
    ):
        query = query.filter(Subject.level == current_user.education_level)

    subjects = query.order_by(Subject.name).all()
    return [_subject_to_read(s, db, current_user) for s in subjects]


@router.get("/{subject_id}", response_model=SubjectDetailRead)
def get_subject(
    subject_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a subject with details."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    read = _subject_to_read(subject, db, current_user)
    collection = f"{subject.level.value}_{subject.name}".replace(" ", "_")

    return SubjectDetailRead(
        **read.model_dump(),
        collection_name=collection,
    )


@router.post("/enroll", response_model=EnrollResponse)
def enroll_in_subjects(
    body: EnrollRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enroll current student in one or more subjects."""
    if current_user.role != RoleEnum.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can enroll in subjects",
        )

    enrolled = 0
    for sid in body.subject_ids:
        subject = db.query(Subject).filter(Subject.id == sid).first()
        if not subject:
            continue
        existing = (
            db.query(StudentSubject)
            .filter(
                StudentSubject.student_id == current_user.id,
                StudentSubject.subject_id == sid,
            )
            .first()
        )
        if not existing:
            db.add(StudentSubject(student_id=current_user.id, subject_id=sid))
            enrolled += 1

    db.commit()
    return EnrollResponse(
        enrolled_count=enrolled,
        subject_ids=body.subject_ids,
        message=f"Enrolled in {enrolled} subject(s)",
    )


@router.delete("/enroll/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def unenroll_from_subject(
    subject_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unenroll from a subject."""
    enrollment = (
        db.query(StudentSubject)
        .filter(
            StudentSubject.student_id == current_user.id,
            StudentSubject.subject_id == subject_id,
        )
        .first()
    )
    if enrollment:
        db.delete(enrollment)
        db.commit()
    return None


@router.get("/{subject_id}/documents")
def get_subject_documents(
    subject_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents associated with a subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Find documents matching this subject name + level
    docs = (
        db.query(Document)
        .filter(
            Document.subject == subject.name,
            Document.level == subject.level,
            Document.is_archived == False,  # noqa: E712
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "subject": doc.subject,
            "level": doc.level.value if hasattr(doc.level, "value") else doc.level,
            "year": doc.year,
            "document_category": (
                doc.document_category.value
                if hasattr(doc.document_category, "value")
                else str(doc.document_category)
            ),
            "ingestion_status": (
                doc.ingestion_status.value
                if hasattr(doc.ingestion_status, "value")
                else doc.ingestion_status
            ),
            "page_count": doc.page_count,
            "is_personal": doc.is_personal,
            "official_duration_minutes": doc.official_duration_minutes,
            "uploaded_by": str(doc.uploaded_by),
            "created_at": doc.created_at.isoformat(),
        }
        for doc in docs
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _subject_to_read(
    subject: Subject, db: Session, current_user: User | None
) -> SubjectRead:
    """Convert a Subject model to SubjectRead with computed fields."""
    doc_count = (
        db.query(Document)
        .filter(
            Document.subject == subject.name,
            Document.level == subject.level,
            Document.is_archived == False,  # noqa: E712
        )
        .count()
    )

    enrolled = False
    if current_user and current_user.role == RoleEnum.STUDENT:
        enrolled = (
            db.query(StudentSubject)
            .filter(
                StudentSubject.student_id == current_user.id,
                StudentSubject.subject_id == subject.id,
            )
            .first()
            is not None
        )

    return SubjectRead(
        id=subject.id,
        name=subject.name,
        level=subject.level.value if hasattr(subject.level, "value") else subject.level,
        description=subject.description,
        icon=subject.icon,
        document_count=doc_count,
        enrolled=enrolled,
        created_at=subject.created_at,
    )
