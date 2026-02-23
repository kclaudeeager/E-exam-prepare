"""Document upload and listing routes."""

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.models import Document, EducationLevelEnum, User
from app.db.session import get_db
from app.schemas.document import DocumentRead, EducationLevel
from app.tasks import ingest_document
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("uploads")


def _trigger_ingestion(document_id: str, file_path: str) -> None:
    """Dispatch ingestion task.

    - In production (CELERY_TASK_ALWAYS_EAGER=False): dispatched to a real Celery worker.
    - In development (CELERY_TASK_ALWAYS_EAGER=True): Celery runs the task synchronously,
      so we wrap it in a daemon thread to avoid blocking the HTTP response.
    """
    if settings.CELERY_TASK_ALWAYS_EAGER:
        # Run in background thread so the upload response returns immediately
        t = threading.Thread(
            target=ingest_document.delay,
            args=(document_id, file_path),
            daemon=True,
        )
        t.start()
    else:
        ingest_document.delay(document_id, file_path)


@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    subject: str = Form(...),
    level: EducationLevel = Form(...),
    year: str = Form(...),
    official_duration_minutes: int | None = Form(None),
    instructions: str | None = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload an exam paper PDF (admin only)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(dest, "wb") as f:
        content = file.file.read()
        f.write(content)

    doc = Document(
        filename=file.filename or "unknown.pdf",
        subject=subject,
        level=EducationLevelEnum(level.value),
        year=year,
        official_duration_minutes=official_duration_minutes,
        instructions=instructions,
        file_path=str(dest),
        uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger ingestion (async worker in prod, threaded in dev)
    _trigger_ingestion(str(doc.id), str(dest))

    return doc


@router.get("/", response_model=list[DocumentRead])
def list_documents(
    subject: str | None = None,
    level: EducationLevel | None = None,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List documents with optional subject/level filters.

    By default archived documents are hidden; pass ``include_archived=true``
    to include them (admin archive management view).
    """
    query = db.query(Document)
    if not include_archived:
        query = query.filter(Document.is_archived == False)  # noqa: E712
    if subject:
        query = query.filter(Document.subject == subject)
    if level:
        query = query.filter(Document.level == EducationLevelEnum(level.value))
    return query.offset(skip).limit(limit).all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a single document by ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return doc


@router.patch("/{document_id}/archive", response_model=DocumentRead)
def archive_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Soft-archive a document (admin only). Document remains in DB and can be restored."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is already archived")
    doc.is_archived = True
    doc.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    logger.info("Document %s archived by admin %s", document_id, _current_user.id)
    return doc


@router.patch("/{document_id}/restore", response_model=DocumentRead)
def restore_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Restore a soft-archived document (admin only)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not doc.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is not archived")
    doc.is_archived = False
    doc.archived_at = None
    db.commit()
    db.refresh(doc)
    logger.info("Document %s restored by admin %s", document_id, _current_user.id)
    return doc
