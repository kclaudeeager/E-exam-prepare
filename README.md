# E-exam-prepare

Personalized exam preparation platform powered by **RAG** (Retrieval-Augmented Generation). Students practice with past papers through adaptive quizzes, timed simulations, and concept-driven learning with AI-generated explanations.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 · React 18 · TailwindCSS · TypeScript · Zustand · SWR |
| Backend | FastAPI · SQLAlchemy · PostgreSQL · Celery + Redis |
| RAG | LlamaIndex · OpenAI / Gemini · BM25 · PropertyGraph |
| Tooling | **uv** (Python) · npm (JS) · Docker Compose · Ruff |

## Quick start

```bash
# 1. Install everything (Python + Node)
make install          # runs: uv sync --all-packages && cd frontend && npm install

# 2. Copy env template and add your keys
cp .env.example .env

# 3. Start all services
make dev-all          # backend :8000 · rag :8001 · frontend :3000

# Or with Docker (includes Postgres + Redis):
make docker-up
```

## Project status

✅ **Backend**: Fully implemented & tested
- 11 API routes (auth, documents, quiz, attempts, progress)
- SQLAlchemy ORM with 11 models
- JWT authentication + role-based access control
- Document ingestion queued via Celery
- RAG client HTTP integration

✅ **RAG Service**: Fully implemented
- LlamaIndex with dual indexes (vector + PropertyGraph)
- Hybrid retrieval (semantic + BM25 + reranking)
- Support for OpenAI & Gemini LLMs

✅ **Frontend**: Fully implemented
- 11 pages (auth, dashboard, student views, admin views)
- Complete API client with auth interceptors
- Custom hooks for all data fetching
- Zustand state management with localStorage persistence
- SWR caching & auto-revalidation
- Responsive TailwindCSS design
- Full TypeScript type safety

## Project structure

```
├── pyproject.toml              ← uv workspace root (3 members)
├── .python-version             ← Python 3.12
├── backend/
│   ├── app/
│   │   ├── main.py             ← FastAPI app (11 routes)
│   │   ├── config.py           ← Pydantic Settings
│   │   ├── celery_app.py       ← Celery worker config
│   │   ├── tasks.py            ← ingest_document task
│   │   ├── api/                ← 6 route handlers
│   │   ├── core/security.py    ← JWT + password hashing
│   │   ├── db/                 ← SQLAlchemy models + session
│   │   ├── schemas/            ← Pydantic request/response
│   │   └── services/rag_client.py
│   ├── alembic/                ← Database migrations
│   └── tests/
├── rag-service/
│   └── app/
│       ├── main.py             ← FastAPI app (4 routes)
│       ├── config.py           ← Settings
│       ├── routes/             ← ingest, retrieve, query, explore
│       └── rag/engine.py       ← LlamaIndexRAGEngine
├── frontend/
│   ├── lib/
│   │   ├── api/                ← Axios client + endpoints
│   │   ├── hooks/              ← useAuth, useDocuments, etc.
│   │   ├── stores/auth.ts      ← Zustand state
│   │   └── types.ts            ← TypeScript interfaces
│   ├── config/constants.ts     ← Routes, API endpoints
│   ├── app/                    ← Next.js App Router
│   │   ├── (auth)/             ← Login + Register
│   │   ├── dashboard/          ← Role-based dashboard
│   │   ├── student/            ← Practice, Progress, Attempts
│   │   ├── admin/              ← Documents, Students, Analytics
│   │   ├── layout.tsx          ← Root + Providers
│   │   └── page.tsx            ← Home page
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── package.json
│   ├── DEVELOPMENT.md          ← Frontend guide
│   └── INTEGRATION.md          ← API integration docs
├── verify_integration.py       ← Integration test
├── docker-compose.yml
├── Makefile
└── .github/copilot-instructions.md
```

## API routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/users/register` | — | Create account |
| POST | `/api/users/login` | — | Get JWT token |
| GET | `/api/users/me` | ✓ | Current user |
| POST | `/api/documents/` | Admin | Upload PDF (async ingestion) |
| GET | `/api/documents/` | ✓ | List documents |
| POST | `/api/quiz/generate` | ✓ | Generate quiz (3 modes) |
| GET | `/api/quiz/{id}` | ✓ | Get quiz details |
| POST | `/api/attempts/` | ✓ | Submit + auto-grade answers |
| GET | `/api/attempts/` | ✓ | Past attempts |
| GET | `/api/progress/` | ✓ | Per-topic metrics + recommendations |

## Development commands

```bash
make install          # uv sync + npm install
make dev-all          # Run backend + rag + frontend
make dev-backend      # Backend on :8000
make dev-rag          # RAG on :8001
make dev-frontend     # Next.js on :3000
make docker-up        # Docker Compose (postgres + redis + all services)
make lint             # ruff check
make format           # ruff format
make test             # pytest + jest
```

## Integration verification

```bash
python3 verify_integration.py
```

Verifies:
- ✓ Backend health & all 10 API routes responding
- ✓ Frontend files present (lib/, config/, app/ pages)
- ✓ TypeScript syntax valid
- ✓ Environment variables configured

All 5 checks should pass before running frontend.

## Getting started

### 1. Install dependencies

```bash
make install  # or: uv sync --all-packages && cd frontend && npm install
```

### 2. Start all services

Option A: **Local dev** (requires PostgreSQL + Redis running)
```bash
make dev-all  # starts 3 servers in parallel
```

Option B: **Docker** (all-in-one)
```bash
make docker-up
# Services at http://localhost:8000, :8001, :3000
```

### 3. Test integration

```bash
python3 verify_integration.py
# All checks should pass
```

### 4. Open frontend

- Navigate to **http://localhost:3000**
- Register new account
- Explore dashboard based on role
- Admin: upload PDFs → triggers RAG ingestion
- Student: select quiz mode → get questions from RAG → submit answers → auto-grade

## Key architectural patterns

### Authentication Flow
- User registers/logs in → JWT token stored in localStorage
- All requests include `Authorization: Bearer {token}`
- 401 responses clear token + redirect to login
- Zustand store persists auth state across page reloads

### Data Fetching
- All GET requests use SWR for automatic caching
- Mutations call `.mutate()` to revalidate cache
- Deduping: same request within 60s uses cache
- Focus revalidation disabled for better UX

### Backend Business Logic
- `POST /api/quiz/generate` queries Progress table for weak topics
- Adaptive mode: filters RAG questions by weak topics
- Real exam mode: pulls full exam with official duration
- `POST /api/attempts/` auto-grades + updates Progress table

### Async Tasks
- Document upload returns immediately
- Celery task queued: `ingest_document(doc_id, file_path)`
- Task calls RAG service `/ingest` endpoint
- Progress updated: PENDING → INGESTING → COMPLETED/FAILED

## Database schema

11 tables with relationships:
- **users** — student/admin accounts
- **topics** — curriculum topics (self-referential for hierarchy)
- **documents** — exam papers with metadata + ingestion status
- **questions** — extracted from documents, tagged with topics
- **solutions** — answer explanations linked to questions
- **subscriptions** — M2M user↔topic (what students focus on)
- **quizzes** — quiz instances with mode + duration
- **quiz_questions** — M2M quiz↔question (order preserved)
- **attempts** — student submissions with scores + duration
- **attempt_answers** — individual answer + correctness
- **progress** — per-student per-topic accuracy metrics

## Frontend pages implemented

### Public
- `/` — Home page with features + sign up CTA
- `/login` — Sign-in form, stores JWT
- `/register` — Account creation form

### Student (role=student)
- `/dashboard` — Role-based dashboard with quick links
- `/student/practice` — Quiz mode selector (adaptive/topic/real-exam)
- `/student/progress` — Learning analytics (accuracy %, weak topics, recommendations)
- `/student/attempts` — Quiz history with scores + duration

### Admin (role=admin)
- `/dashboard` — Admin dashboard with quick links
- `/admin/documents` — Upload form + list with ingestion status
- `/admin/students` — Student progress (placeholder, ready to implement)
- `/admin/analytics` — System insights (placeholder, ready to implement)

## Next steps

1. **Quiz Renderer** — `/student/quiz/[id]/page.tsx` with:
   - Question display (one per screen)
   - Timer countdown
   - Answer input (text/MCQ/essay based on question_type)
   - Submit button → POST /api/attempts/
   - Results page with score breakdown

2. **Attempt Details** — `/student/attempts/[id]/page.tsx` with:
   - All answers shown with correctness
   - Correct answers from backend
   - Call RAG to fetch explanations

3. **Admin Analytics** — `/admin/analytics/page.tsx` with:
   - System-wide charts (Recharts)
   - Total students/attempts/accuracy
   - Most attempted topics, hardest questions

4. **Database** — Initialize PostgreSQL:
   ```bash
   make db-upgrade  # runs alembic upgrade head
   ```

5. **RAG Setup** — Upload sample documents:
   - Use `/admin/documents` to upload PDFs
   - System auto-ingests into vector store
   - Verify at `/api/documents/` (check ingestion_status = completed)

## Documentation

- [**Frontend Development Guide**](frontend/DEVELOPMENT.md) — Setup, testing, deployment
- [**Frontend Integration Guide**](frontend/INTEGRATION.md) — API flows, patterns, troubleshooting
- [**Architecture Doc**](docs/ARCHITECTURE.md) — System design, data flows, RAG patterns
- [**Copilot Instructions**](.github/copilot-instructions.md) — Project vision, patterns, onboarding

## Deployment

### Vercel (Frontend)
```bash
vercel deploy --prod
```

### Docker Compose
```bash
docker compose -f docker-compose.yml up -d
# All services deployed: Postgres, Redis, Backend, RAG, Frontend
```

### Environment Variables
```
# .env (backend & rag)
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/exam_prep
CELERY_BROKER_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
SECRET_KEY=your-secret-key

# frontend/.env.local
NEXT_PUBLIC_API_URL=https://api.example.com
```
