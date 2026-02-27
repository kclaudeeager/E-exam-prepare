"""Trigger re-ingestion for PENDING or FAILED documents.

Usage:
    python scripts/reingest_pending.py              # Only PENDING docs
    python scripts/reingest_pending.py --failed      # Include FAILED docs too
    python scripts/reingest_pending.py --all         # Re-queue all non-COMPLETED docs
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Read DATABASE_URL from backend/.env
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
DATABASE_URL = None
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('DATABASE_URL'):
                DATABASE_URL = line.split('=', 1)[1].strip()
                break

# Fallback: try environment variable
if not DATABASE_URL:
    DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in backend/.env or environment")
    sys.exit(1)

parser = argparse.ArgumentParser(description="Re-ingest documents")
parser.add_argument("--failed", action="store_true", help="Include FAILED documents")
parser.add_argument("--all", action="store_true", help="Include all non-COMPLETED documents")
args = parser.parse_args()

print("Connecting to DB...")

from app.db.models import Document, IngestionStatusEnum
from app.tasks import ingest_document

statuses = [IngestionStatusEnum.PENDING]
if args.failed or args.all:
    statuses.append(IngestionStatusEnum.FAILED)
if args.all:
    statuses.append(IngestionStatusEnum.INGESTING)  # stuck jobs

engine = create_engine(DATABASE_URL)
with Session(engine) as db:
    docs = db.query(Document).filter(Document.ingestion_status.in_(statuses)).all()

    # Also report how many are already completed (skipped)
    completed = db.query(Document).filter(
        Document.ingestion_status == IngestionStatusEnum.COMPLETED
    ).count()

    print(f"Found {len(docs)} doc(s) to re-ingest (statuses: {[s.value for s in statuses]}):")
    print(f"  ({completed} already COMPLETED — will be skipped)")
    for d in docs:
        print(f"  [{d.id}] {d.filename} [{d.ingestion_status.value}] @ {d.file_path}")

    if not docs:
        print("\nNothing to re-ingest.")
        sys.exit(0)

    confirm = input("\nTrigger ingestion for all? [y/N] ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)

    for d in docs:
        print(f"\n→ Triggering ingest for {d.filename}...")
        try:
            result = ingest_document.delay(str(d.id), d.file_path)
            print(f"   ✅ Queued: {result}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
