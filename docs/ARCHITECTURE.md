# E-exam-prepare Architecture

## System Overview

E-exam-prepare is a three-tier application with clear separation of concerns, fully containerised via Docker Compose.

```
+------------------------------------------------------------------+
|                     Next.js Frontend                              |
|  (UI, routing, Zustand state, AuthGuard, SWR data fetching)      |
+-----------------------------+------------------------------------+
                              | HTTP REST
+-----------------------------v------------------------------------+
|                   FastAPI Backend                                 |
|  (Auth, documents, quiz, attempts, progress, RAG proxy, chat)    |
+--------------+--------------------------+-----------+------------+
               |                          |           |
   SQLAlchemy  |              HTTP Client |           | Celery
               |                          |           |
   +-----------v--------+   +------------v---+   +---v-----------+
   | PostgreSQL 16      |   | RAG Service    |   | Celery Worker |
   | (users, docs,      |   | (LlamaIndex,   |   | (async ingest |
   |  quizzes, scores,  |   |  Groq LLM,     |   |  via RAG svc) |
   |  progress)         |   |  FastEmbed)    |   |               |
   +--------------------+   +-------+--------+   +---------------+
                                    |
                          +---------+---------+
                          |                   |
                   +------v------+   +--------v-------+
                   | Groq API    |   | Local ONNX     |
                   | (LLM)      |   | Embeddings     |
                   | llama-3.3  |   | (FastEmbed     |
                   | 70b        |   |  bge-small)    |
                   +-------------+   +----------------+
```

## Docker Compose Services

All services are orchestrated via `docker-compose.yml`:

| Service | Image / Build | Port | Purpose |
|---------|--------------|------|---------|
| **postgres** | `postgres:16-alpine` | 5432 | Relational database |
| **redis** | `redis:7-alpine` | 6379 | Celery broker + result backend |
| **backend** | `./backend/Dockerfile` | 8000 | FastAPI main API |
| **rag-service** | `./rag-service/Dockerfile` | 8001 | RAG engine (LlamaIndex) |
| **celery-worker** | `./backend/Dockerfile` | — | Async document ingestion |
| **frontend** | `./frontend/Dockerfile` | 3000 | Next.js UI |

### Shared Volumes
- `backend_uploads` — mounted on **backend**, **rag-service**, and **celery-worker** so all three can read uploaded PDFs
- `rag_storage` — mounted on **rag-service** and **celery-worker** for persisted vector indexes
- `postgres_data` / `redis_data` — persistent data stores

### Startup Order
```
postgres (healthy) + redis (healthy)
  -> backend (runs alembic migrate on start via start.sh)
  -> rag-service
  -> celery-worker (depends on postgres + redis + rag-service)
  -> frontend (depends on backend)
```

---

## Core Components

### 1. Frontend (Next.js)

**Tech**: Next.js 14 (App Router) + React 18 + TypeScript + TailwindCSS + Zustand + SWR

**Key Patterns**:
- **AuthGuard** component wraps protected layouts; waits for Zustand hydration before checking auth
- **Zustand auth store** with `persist` middleware + `hasHydrated` flag to prevent SSR/hydration flash
- **SWR** for GET requests (auto-cache, dedup, revalidation)
- **Axios interceptors**: inject `Authorization: Bearer {token}`, clear store + redirect on 401

**Auth Flow**:
1. User logs in via `/login` -> `POST /api/users/login`
2. Backend returns `AuthResponse { access_token, token_type, user }`
3. Frontend stores token via `apiClient.setToken()` and user in Zustand
4. AuthGuard blocks rendering until `hasHydrated === true`
5. 401 response -> Axios interceptor clears Zustand store -> redirect to `/login`

**Directory Structure**:
```
frontend/
  app/
    (auth)/login, register     # Public auth pages
    dashboard/                 # Role-based dashboard
    student/practice, progress, attempts, ask-ai
    admin/documents, students, analytics
    layout.tsx                 # Root layout + Providers
  components/
    AuthGuard.tsx             # Hydration-aware auth wrapper
    Navbar.tsx
  lib/
    api/client.ts             # Axios singleton + interceptors
    api/endpoints.ts          # authAPI, documentAPI, ragAPI, chatAPI
    hooks/index.ts            # useAuth, useDocuments, useQuiz, etc.
    stores/auth.ts            # Zustand with persist + hasHydrated
    types.ts                  # TypeScript interfaces
  config/constants.ts         # Routes, API URLs, education levels
```

### 2. Backend (FastAPI)

**Tech**: FastAPI + SQLAlchemy ORM + PostgreSQL 16 + Celery + Redis + JWT (PyJWT)

**Key Features**:
- JWT authentication with `AuthResponse` (returns token + user in one response)
- Document upload with async ingestion via Celery
- RAG proxy endpoints (forward to RAG microservice)
- Chat session management (CRUD for multi-turn conversations)
- Progress tracking with weak topic detection

**Startup**: `backend/start.sh` runs `alembic upgrade head` then starts uvicorn

**Directory Structure**:
```
backend/
  app/
    main.py                   # FastAPI app with CORS
    config.py                 # Pydantic Settings from .env
    celery_app.py             # Celery worker config
    tasks.py                  # ingest_document async task
    api/
      users.py                # Register, login, me
      documents.py            # Upload, list, share
      quiz.py                 # Generate, get
      attempts.py             # Submit, list
      progress.py             # Student metrics
      rag.py                  # RAG proxy to microservice
      chat.py                 # Chat session CRUD
    core/security.py          # JWT + password hashing
    db/models.py              # 11 SQLAlchemy models
    schemas/                  # Pydantic request/response
      user.py                 # UserCreate, AuthResponse, etc.
    services/
      rag_client.py           # HTTP singleton for RAG service
  alembic/                    # Database migrations
  start.sh                    # Auto-migrate + start script
```

**Database Models** (11 tables):
- `users` — email, password_hash, role, education_level
- `documents` — filename, subject, level, year, ingestion_status, is_personal, is_shared
- `document_shares` — M2M for student document sharing
- `topics` — self-referential hierarchy
- `subscriptions` — M2M user-topic
- `questions` — extracted from documents, tagged
- `solutions` — answer explanations
- `quizzes` — mode, duration, document_id
- `quiz_questions` — M2M quiz-question (ordered)
- `attempts` — score, duration, document_id
- `attempt_answers` — per-question correctness
- `progress` — per-student per-topic accuracy

### 3. RAG Service (LlamaIndex Microservice)

**Tech**: FastAPI + LlamaIndex + Groq LLM (llama-3.3-70b-versatile) + FastEmbed (BAAI/bge-small-en-v1.5)

**Key Design**:
- **Per-collection indexes**: Each `{level}_{subject}` combination gets its own VectorStoreIndex persisted to disk
- **Singleton pattern**: `get_rag_engine()` returns a single `LlamaIndexRAGEngine` instance
- **Lazy configuration**: LlamaIndex Settings are configured on first use, not at import time (fast health checks)

**Embedding Strategy** (when using Groq LLM):
- Groq does not offer embeddings
- If `OPENAI_API_KEY` is set -> use OpenAI `text-embedding-3-small`
- Otherwise -> use **FastEmbed** (free, local, ONNX-based, no API key) with `BAAI/bge-small-en-v1.5`

**RAG Query Flow** (two code paths):

#### Path A: With Chat History (follow-up questions)
```
User question + chat_history
  -> _condense_question(): rewrite follow-up as standalone
     (includes collection context hint, filters failed responses from history)
  -> Retrieve: index.as_retriever(similarity_top_k) with condensed question
  -> Log retrieval scores (min/max/avg)
  -> Build context from retrieved nodes
  -> Synthesis prompt with conversation history + exam content
  -> Groq LLM.complete()
  -> Return answer + sources + condensed_question
```

#### Path B: Without Chat History (first question)
```
User question
  -> _is_vague_query(): detect short/generic questions
  -> If vague: _expand_query_with_context() adds collection context
     e.g. "what about this paper?" -> "P6 Social studies exam paper: what about this paper? What topics, questions, and content are covered..."
  -> Retrieve: index.as_retriever(similarity_top_k) with (expanded) question
  -> Log retrieval scores (min/max/avg)
  -> Build context from retrieved nodes
  -> Choose prompt: overview prompt (vague) vs strict prompt (specific)
  -> Groq LLM.complete()
  -> Return answer + sources + expanded_question (if expanded)
```

**Vague Query Detection** (`_is_vague_query`):
- Matches queries <= 5 words
- Matches patterns: "what about this", "tell me about", "this paper", "overview", etc.

**Document Ingestion** (`ingest`):
```
PDF files in source_path
  -> Groq Vision OCR (llama-4-scout) for scanned pages
  -> Text chunking via SentenceSplitter (1024 tokens, 100 overlap)
  -> Build VectorStoreIndex with FastEmbed embeddings
  -> Persist to disk at storage/{collection}/
```

**Directory Structure**:
```
rag-service/
  app/
    main.py                   # FastAPI app
    config.py                 # Settings (provider, API keys, chunking)
    providers.py              # LLM + embedding factory
    rag/engine.py             # LlamaIndexRAGEngine (main class)
    routes/
      ingest.py               # POST /ingest/
      query.py                # POST /query/, POST /query/direct
      retrieve.py             # POST /retrieve/
  storage/                    # Persisted vector indexes per collection
```

**Configuration** (`rag-service/app/config.py`):
```python
LLAMA_INDEX_PROVIDER = "groq"                              # groq | openai | gemini
GROQ_MODEL = "llama-3.3-70b-versatile"                     # LLM for synthesis
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # OCR
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 100
SIMILARITY_TOP_K = 10
KG_RAG_ENABLED = False                                     # PropertyGraph (optional)
```

---

## Data Flows

### Flow 1: Document Upload and Ingestion
```
1. Admin uploads PDF via /admin/documents page
2. Frontend: POST /api/documents/ (multipart/form-data)
3. Backend: saves file to uploads/, creates Document (status=PENDING)
4. Backend: queues Celery task ingest_document(doc_id, file_path)
5. Celery worker: reads PDF from shared backend_uploads volume
6. Celery worker: POST /ingest/ to RAG service with collection name
7. RAG service: OCR -> chunk -> embed -> build VectorStoreIndex -> persist
8. Celery worker: updates Document status to COMPLETED (or FAILED)
9. Frontend: SWR polls document list, shows updated status
```

### Flow 2: Ask AI (Chat with Exam Paper)
```
1. Student selects a collection (e.g. "P6_Social_studies") on /student/ask-ai
2. Student types "what about this paper?" (first message, no history)
3. Frontend: POST /api/rag/query { question, collection, top_k, chat_history=[] }
4. Backend: forwards to RAG service POST /query/
5. RAG service:
   a. No chat_history -> Path B
   b. Detects vague query -> expands with collection context
   c. Retrieves top-k nodes from VectorStoreIndex
   d. Uses overview synthesis prompt
   e. Returns { answer, sources, expanded_question }
6. Frontend: displays answer + source citations
7. Student asks follow-up "what about the religion questions?"
8. Frontend: builds chat_history from previous messages
9. RAG service:
   a. Has chat_history -> Path A
   b. Condenses follow-up into standalone question
   c. Retrieves with condensed question
   d. Synthesizes with conversation context
```

### Flow 3: Student Takes Adaptive Practice
```
1. Student: POST /api/quiz/generate (mode="adaptive")
2. Backend: queries Progress table for topics with accuracy < 60%
3. Backend: calls RAG /query/ with topic filters
4. Backend: creates Quiz + QuizQuestion records
5. Frontend: renders exam with timer
6. Student submits -> POST /api/attempts/
7. Backend: grades, updates Progress per-topic metrics
8. Frontend: shows score breakdown + recommendations
```

---

## Environment Variables

All services read from the root `.env` file (via `env_file: .env` in docker-compose):

```env
# -- Database --
POSTGRES_USER=exam_prep
POSTGRES_PASSWORD=exam_prep_dev
POSTGRES_DB=exam_prep

# -- Auth --
SECRET_KEY=your-secret-key-change-in-production

# -- LLM / RAG --
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=                   # Optional: for OpenAI embeddings
GOOGLE_API_KEY=                   # Optional: for Gemini provider

# -- Frontend --
NEXT_PUBLIC_API_URL=http://localhost:8000

# -- Celery --
CELERY_BROKER_URL=redis://redis:6379/0
```

---

## Error Handling

All APIs follow this convention:
```json
{
  "success": false,
  "error_code": "DOCUMENT_PARSE_FAILED",
  "message": "PDF parsing failed: unsupported format",
  "details": {}
}
```

Frontend Axios interceptor catches 401 -> clears Zustand auth store -> redirects to login.

---

## Scaling Considerations

### Current (MVP)
- Single PostgreSQL, single Redis
- In-memory VectorStoreIndex persisted to disk
- Celery with Redis broker
- Single RAG service instance
- FastEmbed local embeddings (no API cost)

### Future
- Neo4j for PropertyGraph (when KG_RAG_ENABLED=true)
- Pinecone / pgvector for scalable vector storage
- Multiple RAG service instances behind load balancer
- Database read replicas
- Redis Cluster for Celery scaling
