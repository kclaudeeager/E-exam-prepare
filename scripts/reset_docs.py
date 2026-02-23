"""Reset completed documents to PENDING so they get re-ingested with pdfplumber."""
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

print(f"Connecting to DB...")

from app.db.models import Document, IngestionStatusEnum

engine = create_engine(DATABASE_URL)
with Session(engine) as db:
    docs = db.query(Document).filter(Document.ingestion_status == IngestionStatusEnum.COMPLETED).all()
    print(f"Found {len(docs)} completed doc(s):")
    for d in docs:
        print(f"  [{d.id}] {d.filename} — {d.level}_{d.subject}")
        d.ingestion_status = IngestionStatusEnum.PENDING
    db.commit()
    print(f"\n✅ Reset {len(docs)} docs to PENDING — re-upload or trigger ingest via admin UI")
