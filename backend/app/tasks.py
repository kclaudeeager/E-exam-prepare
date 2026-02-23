"""Background tasks executed by Celery workers."""

import logging

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.db.models import Document, IngestionStatusEnum
from app.services.rag_client import get_rag_client

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ingest_document", max_retries=3)
def ingest_document(self, document_id: str, file_path: str) -> dict:
    """Ingest a document into the RAG vector store.

    Steps:
        1. Mark document status → INGESTING
        2. Call RAG service ``/ingest``
        3. Mark document status → COMPLETED (or FAILED on error)
    """
    factory = get_session_factory()
    db = factory()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc is None:
            logger.error("Document %s not found — skipping ingestion", document_id)
            return {"success": False, "error": "document_not_found"}

        # 1. Mark as ingesting
        doc.ingestion_status = IngestionStatusEnum.INGESTING
        db.commit()

        # 2. Call RAG micro-service
        rag = get_rag_client()
        collection = f"{doc.level.value}_{doc.subject}".replace(" ", "_")
        result = rag.ingest(
            source_path=file_path,
            collection=collection,
            overwrite=False,
        )
        logger.info("RAG ingestion complete for %s → %s", document_id, result)

        # 3. Success
        doc.ingestion_status = IngestionStatusEnum.COMPLETED
        db.commit()

        return {"success": True, "document_id": document_id, "rag_result": result}

    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        # Mark as failed in DB
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.ingestion_status = IngestionStatusEnum.FAILED
                db.commit()
        except Exception:
            db.rollback()

        # Retry with exponential back-off (10s, 30s, 90s)
        raise self.retry(exc=exc, countdown=10 * (3**self.request.retries))

    finally:
        db.close()
