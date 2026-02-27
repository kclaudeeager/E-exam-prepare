"""Document upload, listing, PDF serving, and sharing routes."""

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_current_user, require_admin
from app.db.models import Document, DocumentCategoryEnum, DocumentComment, EducationLevelEnum, Subject, User, DocumentShare, RoleEnum
from app.db.session import get_db
from app.schemas.document import (
    DocumentArchiveRequest,
    DocumentCategory,
    DocumentCommentCreate,
    DocumentCommentRead,
    DocumentCommentUpdate,
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


def _doc_to_read(doc: Document) -> DocumentRead:
    """Convert a Document ORM object to DocumentRead with enriched fields."""
    return DocumentRead(
        id=doc.id,
        filename=doc.filename,
        subject=doc.subject,
        level=doc.level.value,
        year=doc.year,
        uploaded_by=doc.uploaded_by,
        uploader_name=doc.uploader.full_name if doc.uploader else None,
        ingestion_status=doc.ingestion_status.value,
        document_category=doc.document_category.value if doc.document_category else "exam_paper",
        is_personal=doc.is_personal,
        is_shared=doc.is_shared,
        official_duration_minutes=doc.official_duration_minutes,
        page_count=doc.page_count,
        subject_id=doc.subject_id,
        collection_name=doc.collection_name,
        is_archived=doc.is_archived,
        archived_at=doc.archived_at,
        archived_by=doc.archived_by,
        archive_reason=doc.archive_reason,
        archiver_name=doc.archiver.full_name if doc.archiver else None,
        comment_count=len(doc.comments) if doc.comments else 0,
        created_at=doc.created_at,
    )


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
    document_category: DocumentCategory = Form(DocumentCategory.EXAM_PAPER),
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

    # Count pages
    page_count = _count_pdf_pages(dest)

    doc = Document(
        filename=file.filename or "unknown.pdf",
        subject=subject,
        level=EducationLevelEnum(level.value),
        year=year,
        document_category=DocumentCategoryEnum(document_category.value),
        official_duration_minutes=official_duration_minutes,
        instructions=instructions,
        file_path=str(dest),
        uploaded_by=current_user.id,
        is_personal=False,
        page_count=page_count,
    )
    # Auto-link to subject if one matches
    matched_subject = (
        db.query(Subject)
        .filter(Subject.name == subject, Subject.level == EducationLevelEnum(level.value))
        .first()
    )
    if matched_subject:
        doc.subject_id = matched_subject.id
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
    document_category: DocumentCategory = Form(DocumentCategory.EXAM_PAPER),
    official_duration_minutes: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a personal document for help (student only).
    
    Supports: exam papers, marking schemes, syllabi, textbooks, notes.
    Personal documents are private by default.
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

    page_count = _count_pdf_pages(dest)

    doc = Document(
        filename=file.filename or "unknown.pdf",
        subject=subject,
        level=EducationLevelEnum(level.value),
        year=year,
        document_category=DocumentCategoryEnum(document_category.value),
        official_duration_minutes=official_duration_minutes,
        file_path=str(dest),
        uploaded_by=current_user.id,
        is_personal=True,
        page_count=page_count,
    )
    # Auto-link to subject if one matches
    matched_subject = (
        db.query(Subject)
        .filter(Subject.name == subject, Subject.level == EducationLevelEnum(level.value))
        .first()
    )
    if matched_subject:
        doc.subject_id = matched_subject.id
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

    return [_doc_to_read(d) for d in query.options(
        joinedload(Document.uploader),
        joinedload(Document.archiver),
        selectinload(Document.comments),
    ).offset(skip).limit(limit).all()]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single document by ID if user has access."""
    doc = (
        db.query(Document)
        .options(
            joinedload(Document.uploader),
            joinedload(Document.archiver),
            selectinload(Document.comments),
        )
        .filter(Document.id == document_id)
        .first()
    )
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

    return _doc_to_read(doc)


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
    body: DocumentArchiveRequest | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Soft-archive a document (admin only) with an optional reason.

    Especially useful when archiving a student-uploaded document.
    """
    doc = db.query(Document).options(
        joinedload(Document.uploader),
        selectinload(Document.comments),
    ).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is already archived")
    doc.is_archived = True
    doc.archived_at = datetime.now(timezone.utc)
    doc.archived_by = _current_user.id
    doc.archive_reason = body.reason if body else None
    db.commit()
    db.refresh(doc)
    logger.info("Document %s archived by admin %s (reason: %s)", document_id, _current_user.id, doc.archive_reason or "none")
    return _doc_to_read(doc)


@router.patch("/{document_id}/restore", response_model=DocumentRead)
def restore_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Restore a soft-archived document (admin only)."""
    doc = db.query(Document).options(
        joinedload(Document.uploader),
        selectinload(Document.comments),
    ).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not doc.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is not archived")
    doc.is_archived = False
    doc.archived_at = None
    doc.archived_by = None
    doc.archive_reason = None
    db.commit()
    db.refresh(doc)
    logger.info("Document %s restored by admin %s", document_id, _current_user.id)
    return _doc_to_read(doc)


# ── PDF serving ───────────────────────────────────────────────────────────────


@router.get("/{document_id}/pdf")
def serve_document_pdf(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the PDF file for in-app viewing.

    Returns the raw PDF with proper Content-Type headers for embedding
    in a PDF viewer (react-pdf, pdf.js, or browser built-in).
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check access permissions (same logic as get_document)
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
        not doc.is_personal and doc.level == current_user.education_level
    )
    is_admin = current_user.role == RoleEnum.ADMIN

    if not (is_owner or is_shared or is_level_designated or is_admin):
        raise HTTPException(status_code=403, detail="No access to this document")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        # Seed documents live in the rag_storage volume, not uploads
        rag_path = Path("/app/rag_storage/raw") / Path(doc.file_path).relative_to("seed") if doc.file_path.startswith("seed/") else None
        if rag_path and rag_path.exists():
            file_path = rag_path
        else:
            raise HTTPException(status_code=404, detail="PDF file not found on server")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=doc.filename,
        headers={
            "Content-Disposition": f'inline; filename="{doc.filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ── Document Comments ─────────────────────────────────────────────────────────


def _comment_to_read(c: DocumentComment) -> DocumentCommentRead:
    return DocumentCommentRead(
        id=c.id,
        document_id=c.document_id,
        author_id=c.author_id,
        author_name=c.author.full_name if c.author else None,
        content=c.content,
        comment_type=c.comment_type,
        page_number=c.page_number,
        highlight_text=c.highlight_text,
        resolved=c.resolved,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/{document_id}/comments", response_model=list[DocumentCommentRead])
def list_document_comments(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """List all comments/highlights on a document (admin only)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    comments = (
        db.query(DocumentComment)
        .options(joinedload(DocumentComment.author))
        .filter(DocumentComment.document_id == document_id)
        .order_by(DocumentComment.created_at.desc())
        .all()
    )
    return [_comment_to_read(c) for c in comments]


@router.post("/{document_id}/comments", response_model=DocumentCommentRead, status_code=status.HTTP_201_CREATED)
def create_document_comment(
    document_id: uuid.UUID,
    body: DocumentCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Add a comment or highlight to a document (admin only)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    comment = DocumentComment(
        document_id=document_id,
        author_id=current_user.id,
        content=body.content,
        comment_type=body.comment_type.value,
        page_number=body.page_number,
        highlight_text=body.highlight_text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    logger.info("Comment added to document %s by %s", document_id, current_user.id)
    return _comment_to_read(comment)


@router.patch("/{document_id}/comments/{comment_id}", response_model=DocumentCommentRead)
def update_document_comment(
    document_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: DocumentCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a comment on a document (admin only)."""
    comment = (
        db.query(DocumentComment)
        .options(joinedload(DocumentComment.author))
        .filter(
            DocumentComment.id == comment_id,
            DocumentComment.document_id == document_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if body.content is not None:
        comment.content = body.content
    if body.resolved is not None:
        comment.resolved = body.resolved
    db.commit()
    db.refresh(comment)
    return _comment_to_read(comment)


@router.delete("/{document_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_comment(
    document_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Delete a comment from a document (admin only)."""
    comment = (
        db.query(DocumentComment)
        .filter(
            DocumentComment.id == comment_id,
            DocumentComment.document_id == document_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _count_pdf_pages(file_path: Path) -> int | None:
    """Count PDF pages using PyPDF2 or pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except ImportError:
        pass
    except Exception:
        pass  # Corrupt or invalid PDF — fall through
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        count = doc.page_count
        doc.close()
        return count
    except ImportError:
        pass
    except Exception:
        pass  # Corrupt or invalid PDF
    return None
