# E-exam-prepare Setup Guide

## Quick Start with Docker (Recommended)

Docker Compose brings up **all 6 services** with one command. This is the easiest path.

### 1. Prerequisites
- **Docker Desktop** installed and running
- A **Groq API key** (free, no credit card): https://console.groq.com

### 2. Create `.env` in the project root

```env
# -- Database --
POSTGRES_USER=exam_prep
POSTGRES_PASSWORD=exam_prep_dev
POSTGRES_DB=exam_prep

# -- Auth --
SECRET_KEY=change-me-in-production

# -- LLM (Groq is FREE) --
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# -- Optional: better embeddings (otherwise uses free local FastEmbed) --
# OPENAI_API_KEY=sk-...

# -- Frontend --
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start everything

```bash
make docker-up
# or: docker compose up -d --build
```

This starts:
- **PostgreSQL 16** on port 5432
- **Redis 7** on port 6379
- **Backend** (FastAPI) on port 8000 — auto-runs DB migrations on startup
- **RAG Service** (LlamaIndex + Groq) on port 8001
- **Celery Worker** — async document ingestion
- **Frontend** (Next.js) on port 3000

### 4. Access the app

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend |
| http://localhost:8000/docs | Backend API docs (Swagger) |
| http://localhost:8001/health | RAG service health |

### 5. Seed data (optional)

```bash
cd backend && uv run python seed_db.py
```

Creates test accounts:
- **Admin**: admin@example.com / admin123
- **Student**: student@example.com / student123

---

## Local Development (without Docker)

If you prefer running services directly:

### 1. Install dependencies

```bash
# Python (uv manages the workspace with 3 packages)
uv sync --all-packages

# Frontend
cd frontend && npm install
```

### 2. Start PostgreSQL and Redis

Either install locally or run just the infra via Docker:
```bash
docker compose up -d postgres redis
```

### 3. Run database migrations

```bash
cd backend && uv run alembic upgrade head
```

### 4. Start services (3 terminals)

```bash
# Terminal 1 — RAG Service (port 8001)
cd rag-service && uv run uvicorn app.main:app --reload --port 8001

# Terminal 2 — Backend (port 8000)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend (port 3000)
cd frontend && npm run dev
```

Or use the Makefile shortcut:
```bash
make dev-all    # runs all 3 in parallel
```

---

## Environment Variables Reference

### Root `.env` (used by Docker Compose for all services)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | Yes | `exam_prep` | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | `exam_prep_dev` | PostgreSQL password |
| `POSTGRES_DB` | Yes | `exam_prep` | PostgreSQL database name |
| `SECRET_KEY` | Yes | `change-me-in-production` | JWT signing key |
| `LLAMA_INDEX_PROVIDER` | Yes | `groq` | LLM provider: `groq`, `openai`, `gemini` |
| `GROQ_API_KEY` | Yes (if groq) | — | Free from https://console.groq.com |
| `OPENAI_API_KEY` | No | — | For OpenAI embeddings or OpenAI provider |
| `GOOGLE_API_KEY` | No | — | For Gemini provider |
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Frontend API target |

### RAG Service Settings (from env)

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq LLM model |
| `GROQ_VISION_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Vision model for PDF OCR |
| `CHUNK_SIZE` | `1024` | Tokens per document chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `SIMILARITY_TOP_K` | `10` | Results to retrieve before synthesis |
| `KG_RAG_ENABLED` | `false` | Enable PropertyGraph (experimental) |
| `STORAGE_DIR` | `./storage` | Where vector indexes are persisted |

### Backend Settings (from env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://...` | Full PostgreSQL connection string |
| `RAG_SERVICE_URL` | `http://localhost:8001` | RAG service base URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis for Celery |
| `WEAK_TOPIC_THRESHOLD` | `0.60` | Accuracy below which topics are flagged |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT token TTL |

---

## Switching LLM Providers

Change one variable and restart:

| Provider | Env Variable | Cost | Embeddings |
|----------|-------------|------|------------|
| **Groq** (recommended) | `LLAMA_INDEX_PROVIDER=groq` | FREE LLM | FastEmbed local (free) or OpenAI |
| **OpenAI** | `LLAMA_INDEX_PROVIDER=openai` | ~$0.30/1K queries | OpenAI (included) |
| **Gemini** | `LLAMA_INDEX_PROVIDER=gemini` | Free tier | Gemini (included) |

When using **Groq** without `OPENAI_API_KEY`, embeddings use **FastEmbed** — a free, local ONNX model (`BAAI/bge-small-en-v1.5`). No API key needed.

---

## Common Tasks

### Upload Exam Papers
1. Log in as admin at http://localhost:3000/login
2. Go to Documents page
3. Upload PDF with subject, level, year
4. System auto-ingests: OCR -> chunk -> embed -> index
5. Document status updates: PENDING -> INGESTING -> COMPLETED

### Ask AI about a Paper
1. Log in as student
2. Go to Ask AI page
3. Select a collection (e.g. "P6_Social_studies")
4. Ask questions — system handles vague queries like "what about this paper?" with smart expansion

### Generate a Quiz
1. Student selects document + mode (adaptive / topic / real exam)
2. System generates questions from ingested papers via RAG
3. Timer starts, student answers
4. Auto-grading + per-topic score breakdown

---

## Troubleshooting

### Container won't start
```bash
docker compose logs <service-name>   # e.g. docker compose logs backend
docker compose ps                     # check health status
```

### "Cannot connect to RAG Service" (from backend/celery)
- Check RAG service is running: `docker compose logs rag-service`
- In Docker, backend connects via `http://rag-service:8001` (service name, not localhost)

### "No information available" on Ask AI
- Ensure the document was ingested (status = COMPLETED in admin documents page)
- Check RAG logs: `docker compose logs rag-service --tail=50`
- The system expands vague queries automatically, but very specific queries work best

### Database migration fails
```bash
docker compose exec backend uv run alembic current   # check state
docker compose exec backend uv run alembic upgrade head
```

### Rebuild a single service
```bash
docker compose up -d --build rag-service   # rebuild just RAG service
```

---

## Deployment Checklist

- [ ] Strong `SECRET_KEY` set (not the default)
- [ ] `GROQ_API_KEY` configured
- [ ] PostgreSQL credentials are production-grade
- [ ] `NEXT_PUBLIC_API_URL` points to your production backend URL
- [ ] Database migrations run successfully
- [ ] All containers healthy: `docker compose ps`
- [ ] Can register + login at the frontend
- [ ] Can upload a document and see it ingested
- [ ] Can ask AI about an ingested document

---

## Further Reading

All docs are in the `docs/` directory:
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and data flows
- [API_REFERENCE.md](API_REFERENCE.md) — Full REST API reference
- [PROVIDER_SETUP.md](PROVIDER_SETUP.md) — LLM provider comparison
- [DOCS_INDEX.md](DOCS_INDEX.md) — Full documentation index
