#!/bin/sh
set -e

echo "⏳ Bootstrapping database schema from models..."
uv run python - <<'PY'
from app.db.session import Base, get_engine
import app.db.models  # noqa: F401 - ensure models are registered on Base

Base.metadata.create_all(bind=get_engine())
print("✅ Base tables ready")

# Add missing columns to existing tables (safe no-op if already present)
from sqlalchemy import text, inspect
engine = get_engine()
with engine.connect() as conn:
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("documents")}
    if "archived_by" not in cols:
        conn.execute(text("ALTER TABLE documents ADD COLUMN archived_by UUID REFERENCES users(id)"))
        print("  + Added documents.archived_by")
    if "archive_reason" not in cols:
        conn.execute(text("ALTER TABLE documents ADD COLUMN archive_reason TEXT"))
        print("  + Added documents.archive_reason")

    # Fix enum values that may have been added with wrong casing
    try:
        conn.execute(text("ALTER TYPE document_category_enum RENAME VALUE 'driving_manual' TO 'DRIVING_MANUAL'"))
        print("  + Fixed document_category_enum: driving_manual → DRIVING_MANUAL")
    except Exception:
        pass  # already correct or doesn't exist — safe to ignore

    conn.commit()
print("✅ Schema migrations applied")
PY

echo "⏳ Stamping Alembic version to head..."
uv run alembic stamp head
echo "✅ Schema ready"

echo "⏳ Backfilling document subject_id linkage..."
uv run python - <<'PY'
from app.db.session import get_session_factory
from app.db.models import Document, Subject

SessionLocal = get_session_factory()
db = SessionLocal()
try:
    unlinked = db.query(Document).filter(Document.subject_id.is_(None)).all()
    linked = 0
    for doc in unlinked:
        subj = db.query(Subject).filter(
            Subject.name == doc.subject,
            Subject.level == doc.level,
        ).first()
        if subj:
            doc.subject_id = subj.id
            linked += 1
    db.commit()
    if linked:
        print(f"  Linked {linked} documents to subjects")
    else:
        print("  All documents already linked")
finally:
    db.close()
PY

echo "⏳ Seeding default subjects..."
uv run python - <<'PY'
from app.db.session import get_session_factory
from app.api.subjects import ensure_default_subjects

SessionLocal = get_session_factory()
db = SessionLocal()
try:
    created = ensure_default_subjects(db)
    if created:
        print(f"  Seeded {created} new subjects")
    else:
        print("  All default subjects already exist")
finally:
    db.close()
PY
echo "✅ Subjects ready"

echo "⏳ Scheduling seed ingestion of raw documents (background)..."
# Run in background: wait for RAG service, trigger seed ingest, register docs in DB
(
  RAG_URL="${RAG_SERVICE_URL:-http://rag-service:8001}"
  MAX_WAIT=120
  WAITED=0
  echo "  Waiting for RAG service at $RAG_URL ..."
  while [ $WAITED -lt $MAX_WAIT ]; do
    if uv run python -c "import httpx; httpx.get('$RAG_URL/health', timeout=5).raise_for_status()" 2>/dev/null; then
      echo "  ✅ RAG service is ready (waited ${WAITED}s)"

      # Seed RAG indexes + register documents in the database
      uv run python - <<'PYDB'
import httpx, os, sys

RAG_URL = os.environ.get("RAG_SERVICE_URL", "http://rag-service:8001")

from app.db.session import get_session_factory
from app.db.models import (
    Document, Subject, User, EducationLevelEnum,
    IngestionStatusEnum, DocumentCategoryEnum, RoleEnum,
)

# ── Step 1: Get available seed folders ───────────────────────────────────────
r = httpx.get(f"{RAG_URL}/ingest/seed/available", timeout=30)
folders = r.json().get("folders", [])

if not folders:
    print("  No seed folders found")
    sys.exit(0)

# ── Step 2: Trigger RAG seed ingest for each folder ─────────────────────────
# Collect per-file results (source_file + collection) for DB registration
all_results = []  # list of (folder_name, source_file, collection)

for f in folders:
    name = f["name"]
    if not f.get("has_mapping"):
        continue
    print(f"  Seeding folder: {name} ({f['pdf_count']} PDFs)...")
    resp = httpx.post(
        f"{RAG_URL}/ingest/seed",
        json={"folder": name, "overwrite": False},
        timeout=600,
    )
    data = resp.json()
    results = data.get("results", [])
    skipped = data.get("skipped", 0)
    total = len(results)
    ingested = total - skipped

    if skipped == total:
        print(f"    ⏭️  All {total} already ingested — skipped")
    elif ingested > 0:
        print(f"    ✅ Ingested {ingested}, skipped {skipped}")
    else:
        print(f"    ℹ️  {data.get('message', 'done')}")

    # Collect results for DB registration (both ingested and skipped)
    for res in results:
        src = res.get("source_file", "")
        col = res.get("collection", "")
        if src and col:
            all_results.append((name, src, col))

# ── Step 3: Register seeded documents in the database ────────────────────────
print("  ⏳ Registering seeded documents in database...")

db = get_session_factory()()
try:
    # Find system user (or admin) as uploader
    sys_user = db.query(User).filter(User.email == "system@local").first()
    if not sys_user:
        sys_user = db.query(User).filter(User.role == RoleEnum.ADMIN).first()
    if not sys_user:
        print("    ⚠️  No system/admin user found — cannot register documents")
        sys.exit(0)

    registered = 0
    skipped_db = 0

    for folder_name, pdf_name, collection in all_results:
        # Skip if already in DB
        existing = db.query(Document).filter(
            Document.filename == pdf_name
        ).first()
        if existing:
            skipped_db += 1
            continue

        # Parse level and subject from collection: "DRIVING_Traffic_Rules_and_Regulations"
        parts = collection.split("_", 1)
        level_str = parts[0] if parts else folder_name.upper()

        # Resolve EducationLevel enum
        try:
            level_enum = EducationLevelEnum(level_str)
        except ValueError:
            print(f"    ⚠️  Unknown level '{level_str}' for {pdf_name} — skipping")
            continue

        # Professional levels (e.g. DRIVING) use a single catch-all subject;
        # academic levels parse subject from the collection name.
        PROFESSIONAL_LEVELS = {"DRIVING"}
        if level_str in PROFESSIONAL_LEVELS:
            subject_name = "Driving Prep"
            category = DocumentCategoryEnum.DRIVING_MANUAL
        else:
            subject_name = parts[1].replace("_", " ") if len(parts) > 1 else collection
            category = DocumentCategoryEnum.EXAM_PAPER

        # Find matching Subject in DB
        subject = db.query(Subject).filter(
            Subject.name == subject_name,
            Subject.level == level_enum,
        ).first()

        doc = Document(
            filename=pdf_name,
            subject=subject_name,
            level=level_enum,
            year="2024",
            file_path=f"seed/{folder_name}/{pdf_name}",
            uploaded_by=sys_user.id,
            ingestion_status=IngestionStatusEnum.COMPLETED,
            collection_name=collection,
            document_category=category,
            is_personal=False,
            subject_id=subject.id if subject else None,
        )
        db.add(doc)
        registered += 1

    db.commit()
    if registered:
        print(f"    ✅ Registered {registered} new document(s)")
    if skipped_db:
        print(f"    ⏭️  {skipped_db} document(s) already registered")
    if not registered and not skipped_db:
        print("    ℹ️  No documents to register")

except Exception as e:
    print(f"    ⚠️  Error registering documents: {e}")
    import traceback; traceback.print_exc()
    db.rollback()
finally:
    db.close()
PYDB
      echo "  ✅ Seed ingestion complete"
      break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
  done
  if [ $WAITED -ge $MAX_WAIT ]; then
    echo "  ⚠️  RAG service not available after ${MAX_WAIT}s — skipping seed ingestion"
  fi
) &

echo "🚀 Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
