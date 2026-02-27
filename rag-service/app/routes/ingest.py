"""Document ingestion endpoint."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.rag.engine import get_rag_engine

logger = logging.getLogger(__name__)
router = APIRouter()

_storage = Path(settings.STORAGE_DIR)
_raw_dir = _storage / "raw"

# ── Mapping of raw subfolder names to collections ─────────────────────────────
# Each key is a folder name under storage/raw/.
# The value is a list of (glob_or_filename_pattern, collection_name) tuples.
# If a PDF doesn't match any pattern, it falls into the "General" collection for
# that category.  Collections follow the convention: LEVEL_SubjectName
#
# For driving, all docs are now mapped to a single collection for unified access.
SEED_FOLDER_MAPPINGS: dict[str, dict[str, str]] = {
    "driving": {
        "_default": "DRIVING",
    },
}


class IngestRequest(BaseModel):
    source_path: str
    collection: str
    overwrite: bool = False


class SeedRequest(BaseModel):
    """Request to ingest curated documents from raw/ folder."""
    folder: Optional[str] = None  # e.g. "driving". None = ingest all raw subfolders.
    overwrite: bool = False


@router.post("/")
async def ingest_documents(body: IngestRequest):
    """Ingest PDFs from *source_path* into the given collection index."""
    src = Path(body.source_path)
    if not src.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path not found: {body.source_path}",
        )

    engine = get_rag_engine()
    result = engine.ingest(str(src), body.collection, overwrite=body.overwrite)
    return result


def _match_collection(filename: str, mapping: dict[str, str]) -> str:
    """Return the collection name for a PDF based on filename prefix matching."""
    lower = filename.lower()
    for prefix, collection in mapping.items():
        if prefix != "_default" and lower.startswith(prefix):
            return collection
    return mapping.get("_default", "General")


@router.post("/seed")
async def seed_ingest(body: SeedRequest):
    """Ingest curated documents from ``storage/raw/`` subfolders.

    If *folder* is specified, only ingest that subfolder (e.g. ``driving``).
    Otherwise, ingest every subfolder that has a mapping in ``SEED_FOLDER_MAPPINGS``.
    """
    if not _raw_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Raw seed directory not found: {_raw_dir}",
        )

    folders_to_process: list[str] = []
    if body.folder:
        if body.folder not in SEED_FOLDER_MAPPINGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No mapping for folder '{body.folder}'. "
                    f"Available: {list(SEED_FOLDER_MAPPINGS.keys())}"
                ),
            )
        folders_to_process = [body.folder]
    else:
        # All folders that exist on disk AND have a mapping
        folders_to_process = [
            d.name
            for d in _raw_dir.iterdir()
            if d.is_dir() and d.name in SEED_FOLDER_MAPPINGS
        ]

    if not folders_to_process:
        return {"success": True, "message": "No raw folders to process.", "results": []}

    engine = get_rag_engine()
    results: list[dict] = []

    for folder_name in sorted(folders_to_process):
        folder_path = _raw_dir / folder_name
        mapping = SEED_FOLDER_MAPPINGS[folder_name]

        # Group PDFs by collection
        collection_files: dict[str, list[Path]] = {}
        for pdf in sorted(folder_path.rglob("*.pdf")):
            col = _match_collection(pdf.name, mapping)
            collection_files.setdefault(col, []).append(pdf)

        logger.info(
            "Seed folder '%s': %d PDFs → %d collections",
            folder_name,
            sum(len(v) for v in collection_files.values()),
            len(collection_files),
        )

        for col, files in sorted(collection_files.items()):
            # Skip collections that already have a persisted index (unless overwrite)
            col_persist_dir = _storage / col
            if not body.overwrite and (col_persist_dir / "index_store.json").exists():
                logger.info(
                    "Skipping collection '%s' — already ingested (%d PDFs). "
                    "Use overwrite=true to re-ingest.",
                    col, len(files),
                )
                for pdf_file in files:
                    results.append({
                        "success": True,
                        "collection": col,
                        "source_file": pdf_file.name,
                        "skipped": True,
                        "reason": "Collection already ingested",
                    })
                continue

            logger.info("Ingesting %d PDF(s) into collection '%s'…", len(files), col)

            # If multiple PDFs go to the same collection, ingest each one
            # (the engine merges into the existing index unless overwrite=True)
            first_overwrite = body.overwrite
            for pdf_file in files:
                try:
                    result = engine.ingest(
                        str(pdf_file), col, overwrite=first_overwrite
                    )
                    result["source_file"] = pdf_file.name
                    results.append(result)
                    # After first file, don't overwrite (to accumulate)
                    first_overwrite = False
                except Exception as exc:
                    logger.error("Failed to ingest %s: %s", pdf_file.name, exc)
                    results.append({
                        "success": False,
                        "collection": col,
                        "source_file": pdf_file.name,
                        "error": str(exc),
                    })

    succeeded = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = sum(1 for r in results if not r.get("success"))

    parts = []
    if succeeded:
        parts.append(f"{succeeded} ingested")
    if skipped:
        parts.append(f"{skipped} skipped (already exist)")
    if failed:
        parts.append(f"{failed} failed")

    return {
        "success": failed == 0,
        "message": f"Seed ingestion complete: {', '.join(parts) or 'nothing to process'}.",
        "results": results,
        "skipped": skipped,
    }


@router.get("/seed/available")
async def list_seed_folders():
    """List available raw seed folders and their PDF counts."""
    if not _raw_dir.exists():
        return {"raw_dir": str(_raw_dir), "folders": []}

    folders = []
    for d in sorted(_raw_dir.iterdir()):
        if not d.is_dir():
            continue
        pdfs = list(d.rglob("*.pdf"))
        has_mapping = d.name in SEED_FOLDER_MAPPINGS
        folders.append({
            "name": d.name,
            "pdf_count": len(pdfs),
            "pdf_files": [p.name for p in sorted(pdfs)],
            "has_mapping": has_mapping,
            "collections": (
                list(set(
                    _match_collection(p.name, SEED_FOLDER_MAPPINGS[d.name])
                    for p in pdfs
                ))
                if has_mapping
                else []
            ),
        })

    return {"raw_dir": str(_raw_dir), "folders": folders}
