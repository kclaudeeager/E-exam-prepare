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

echo "🚀 Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
