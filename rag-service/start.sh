#!/bin/bash
set -e

# Merge all driving indexes into a single DRIVING collection before starting the service
# python3 scripts/merge_driving_indexes.py

# Start the RAG service
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
