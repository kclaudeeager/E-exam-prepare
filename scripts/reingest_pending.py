"""Trigger re-ingestion for all PENDING documents using the Celery task directly."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Read DATABASE_URL from backend/.env
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
DATABASE_URL = None
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith('DATABASE_URL'):
            DATABASE_URL = line.split('=', 1)[1].strip()
            break

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in backend/.env")
    sys.exit(1)

print("Connecting to DB...")

from app.db.models import Document, IngestionStatusEnum
from app.tasks import ingest_document

engine = create_engine(DATABASE_URL)
with Session(engine) as db:
    docs = db.query(Document).filter(Document.ingestion_status == IngestionStatusEnum.PENDING).all()
    print(f"Found {len(docs)} PENDING doc(s):")
    for d in docs:
        print(f"  [{d.id}] {d.filename} @ {d.file_path}")

    confirm = input("\nTrigger ingestion for all? [y/N] ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)

    for d in docs:
        print(f"\n→ Triggering ingest for {d.filename}...")
        try:
            result = ingest_document.delay(str(d.id), d.file_path)
            print(f"   ✅ {result}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
