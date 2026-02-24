"""Document upload and listing routes."""

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.models import Document, EducationLevelEnum, User, DocumentShare, RoleEnum
from app.db.session import get_db
from app.schemas.document import (
    DocumentRead,
    DocumentShareRequest,
    DocumentShareResponse,
    DocumentWithShareInfo,
    EducationLevel,
)
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


@router.post("/admin", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_admin_document(
    file: UploadFile = File(...),
    subject: str = Form(...),
    level: EducationLevel = Form(...),
    year: str = Form(...),
    official_duration_minutes: int | None = Form(None),
    instructions: str | None = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload an exam paper PDF designated for a specific level (admin only).
    
    This document will be visible to all students with that education level.
    """
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
        is_personal=False,  # Admin-designated document
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger ingestion (async worker in prod, threaded in dev)
    _trigger_ingestion(str(doc.id), str(dest))
    logger.info("Admin document uploaded: %s for level %s", doc.id, level)

    return doc


@router.post("/student", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_personal_document(
    file: UploadFile = File(...),
    subject: str = Form(...),
    level: EducationLevel = Form(...),
    year: str = Form(...),
    official_duration_minutes: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a personal document for help (student only).
    
    Personal documents are private by default and only visible to:
    - The uploader
    - Students the uploader shares it with
    """
    if current_user.role != RoleEnum.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can upload personal documents",
        )

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
        file_path=str(dest),
        uploaded_by=current_user.id,
        is_personal=True,  # Student personal document
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger ingestion (async worker in prod, threaded in dev)
    _trigger_ingestion(str(doc.id), str(dest))
    logger.info("Personal document uploaded by student %s: %s", current_user.id, doc.id)

    return doc


@router.get("", response_model=list[DocumentRead])
def list_documents(
    subject: str | None = None,
    level: EducationLevel | None = None,
    only_shared: bool = False,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents visible to the current user.
    
    **For Students:**
    - Admin-designated documents matching their education level
    - Their own personal documents
    - Documents other students have shared with them
    
    **For Admins:**
    - All documents (to manage and designate)
    
    Optional filters:
    - subject: filter by subject
    - level: filter by education level
    - only_shared: show only shared personal documents
    - include_archived: include archived documents
    """
    query = db.query(Document)
    
    if not include_archived:
        query = query.filter(Document.is_archived == False)  # noqa: E712

    # Role-based visibility filtering
    if current_user.role == RoleEnum.ADMIN:
        # Admins see all documents
        pass
    else:
        # Students see: admin-designated + own + shared
        # Admin-designated documents: if student has no education_level yet,
        # show ALL admin docs as a fallback so they're never left with nothing.
        admin_doc_filter = Document.is_personal == False  # noqa: E712
        if current_user.education_level is not None:
            admin_doc_filter = (
                (Document.is_personal == False) &  # noqa: E712
                (Document.level == current_user.education_level)
            )

        query = query.filter(
            or_(
                admin_doc_filter,
                # Own personal documents
                Document.uploaded_by == current_user.id,
                # Documents shared with them
                Document.shared_with.any(DocumentShare.shared_with_user_id == current_user.id),
            )
        )

    # Apply optional filters
    if subject:
        query = query.filter(Document.subject == subject)
    if level:
        query = query.filter(Document.level == EducationLevelEnum(level.value))

    if only_shared:
        # Show only shared personal documents (excluding own)
        query = query.filter(
            (Document.is_personal == True) &  # noqa: E712
            (Document.uploaded_by != current_user.id) &
            Document.shared_with.any(DocumentShare.shared_with_user_id == current_user.id)
        )

    return query.offset(skip).limit(limit).all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single document by ID if user has access."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Check access permissions
    is_owner = doc.uploaded_by == current_user.id
    is_shared = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == current_user.id,
        )
        .first()
        is not None
    )
    is_level_designated = (
        not doc.is_personal
        and doc.level == current_user.education_level
    )
    is_admin = current_user.role == RoleEnum.ADMIN

    if not (is_owner or is_shared or is_level_designated or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document",
        )

    return doc


@router.post("/{document_id}/share", response_model=DocumentShareResponse)
def share_personal_document(
    document_id: uuid.UUID,
    request: DocumentShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Share a personal document with other students."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Only owner can share
    if doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document owner can share it",
        )

    if not doc.is_personal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share admin-designated documents",
        )

    # Verify all students exist
    students = db.query(User).filter(User.id.in_(request.student_ids)).all()
    if len(students) != len(request.student_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some student IDs do not exist",
        )

    shared_count = 0
    for student_id in request.student_ids:
        if student_id == current_user.id:
            continue  # Don't share with self
        
        # Check if already shared
        existing = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_user_id == student_id,
            )
            .first()
        )
        if not existing:
            share = DocumentShare(
                document_id=document_id,
                shared_with_user_id=student_id,
            )
            db.add(share)
            shared_count += 1

    if shared_count > 0:
        doc.is_shared = True
        db.commit()
        logger.info(
            "Document %s shared by %s with %d students",
            document_id,
            current_user.id,
            shared_count,
        )

    return DocumentShareResponse(
        document_id=document_id,
        shared_count=shared_count,
        shared_with=request.student_ids,
        message=f"Document shared with {shared_count} new student(s)",
    )


@router.delete("/{document_id}/share/{student_id}")
def unshare_personal_document(
    document_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unshare a personal document from a student."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document owner can unshare it",
        )

    share = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == student_id,
        )
        .first()
    )

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This document is not shared with that student",
        )

    db.delete(share)
    
    # Check if document is still shared with anyone
    remaining_shares = (
        db.query(DocumentShare)
        .filter(DocumentShare.document_id == document_id)
        .count()
    )
    if remaining_shares == 0:
        doc.is_shared = False

    db.commit()
    logger.info(
        "Document %s unshared by %s from %s",
        document_id,
        current_user.id,
        student_id,
    )

    return {"message": "Document unshared successfully"}


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
