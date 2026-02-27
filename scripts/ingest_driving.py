#!/usr/bin/env python3
"""Ingest curated driving-test documents from rag-service/storage/raw/driving/.

Usage:
    # Check what's available first:
    python scripts/ingest_driving.py --dry-run

    # Ingest all driving PDFs:
    python scripts/ingest_driving.py

    # Force overwrite existing indexes:
    python scripts/ingest_driving.py --overwrite

Requires the RAG service to be running on localhost:8001 (or set RAG_URL env var).
"""

import argparse
import json
import os
import sys

import requests

RAG_URL = os.environ.get("RAG_URL", "http://localhost:8001")


def check_available():
    """List available seed folders and their contents."""
    resp = requests.get(f"{RAG_URL}/ingest/seed/available", timeout=30)
    resp.raise_for_status()
    data = resp.json()

    print(f"\n📂 Raw seed directory: {data['raw_dir']}\n")

    if not data["folders"]:
        print("  (empty — no subfolders found)")
        return

    for folder in data["folders"]:
        status = "✅ mapped" if folder["has_mapping"] else "⚠️  no mapping"
        print(f"  📁 {folder['name']}/ — {folder['pdf_count']} PDF(s) [{status}]")
        for pdf in folder["pdf_files"]:
            print(f"      • {pdf}")
        if folder["collections"]:
            print(f"      → Collections: {', '.join(folder['collections'])}")
        print()


def run_seed_ingestion(folder: str = "driving", overwrite: bool = False):
    """Trigger seed ingestion via the RAG service."""
    print(f"\n🚀 Starting seed ingestion for '{folder}'…")
    print(f"   RAG service: {RAG_URL}")
    print(f"   Overwrite:   {overwrite}\n")

    resp = requests.post(
        f"{RAG_URL}/ingest/seed",
        json={"folder": folder, "overwrite": overwrite},
        timeout=600,  # Ingestion can take a while with OCR
    )
    resp.raise_for_status()
    data = resp.json()

    print(f"\n{'✅' if data['success'] else '⚠️'}  {data['message']}\n")

    for result in data.get("results", []):
        file_name = result.get("source_file", "?")
        collection = result.get("collection", "?")

        if result.get("skipped"):
            print(
                f"  ⏭️  {file_name}\n"
                f"     → {collection} | SKIPPED: {result.get('reason', 'already exists')}"
            )
        elif result.get("success"):
            nodes = result.get("nodes_created", 0)
            images = result.get("images_extracted", 0)
            secs = result.get("time_seconds", 0)
            print(
                f"  ✅ {file_name}\n"
                f"     → {collection} | {nodes} nodes | {images} images | {secs}s"
            )
        else:
            error = result.get("error", "unknown error")
            print(f"  ❌ {file_name}\n     → {collection} | ERROR: {error}")

    print()
    return data["success"]


def main():
    parser = argparse.ArgumentParser(description="Ingest curated driving documents")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list available documents, don't ingest",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing collections",
    )
    parser.add_argument(
        "--folder",
        default="driving",
        help="Raw subfolder to ingest (default: driving)",
    )
    args = parser.parse_args()

    # Always show what's available
    try:
        check_available()
    except requests.ConnectionError:
        print(f"\n❌ Cannot connect to RAG service at {RAG_URL}")
        print("   Make sure the RAG service is running: make dev-rag  or  docker compose up rag-service")
        sys.exit(1)

    if args.dry_run:
        print("ℹ️  Dry run — no ingestion performed. Remove --dry-run to ingest.")
        return

    success = run_seed_ingestion(folder=args.folder, overwrite=args.overwrite)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
