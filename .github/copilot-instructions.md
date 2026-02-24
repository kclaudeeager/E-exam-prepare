# Copilot Instructions for E-exam-prepare

## Project Vision
**E-exam-prepare** is a personalized exam preparation e-learning platform that helps students prepare for exams by practicing with past papers in a guided, adaptive way. The system uses RAG (Retrieval-Augmented Generation) to analyze exam papers and answer documents, generate random quizzes, time student attempts, and provide explanations for correct solutions.

## System Architecture

### High-Level Flow
```
Exam Documents (PDFs)
  -> RAG Ingestion Pipeline (Groq Vision OCR -> chunk -> embed -> VectorStoreIndex)
  -> Per-Collection Vector Indexes (persisted to disk)
  -> Quiz Generation Engine / Ask AI Chat
  -> Student Practice Interface (timed quizzes, Ask AI)
  -> Assessment & Feedback (auto-grade, explanations)
  -> Progress Tracking (per-topic accuracy, weak topic detection)
```

### Docker Compose Services (6 containers)
```
postgres (16-alpine)  +  redis (7-alpine)
  -> backend (FastAPI :8000, auto-migrates on start via start.sh)
  -> rag-service (FastAPI :8001, LlamaIndex + Groq)
  -> celery-worker (async ingestion, shares uploads + storage volumes)
  -> frontend (Next.js :3000)
```

**Shared volumes**: `backend_uploads` (PDFs, mounted on backend + rag-service + celery-worker), `rag_storage` (vector indexes, mounted on rag-service + celery-worker)

### Core Modules

#### 1. **Frontend** (Next.js 14 + TypeScript)
- **app/(auth)/**: Login, Register pages
- **app/dashboard/**: Role-based dashboard (student vs admin)
- **app/student/**: Practice, Progress, Attempts, **Ask AI** (chat with exam papers)
- **app/admin/**: Documents (upload + ingestion status), Students, Analytics
- **components/AuthGuard.tsx**: Hydration-aware auth wrapper (prevents SSR flash)
- **lib/stores/auth.ts**: Zustand with `persist` + `hasHydrated` flag
- **lib/api/**: Axios singleton with JWT interceptors (authAPI, documentAPI, ragAPI, chatAPI)
- **lib/hooks/**: useAuth, useDocuments, useQuiz, useAttempts, useProgress

**Key Patterns**:
- Custom React hooks isolate API calls from UI
- AuthGuard waits for `hasHydrated` before checking auth, preventing redirect loops
- Axios 401 interceptor clears Zustand store (not just localStorage)
- SWR for GET requests with auto-cache and deduplication

#### 2. **Backend** (Python FastAPI)
- **api/users.py**: Register, Login (returns `AuthResponse { access_token, token_type, user }`), Me
- **api/documents.py**: Admin upload, student upload, list (role/level-aware), share/unshare
- **api/quiz.py**: Generate (adaptive/topic/real-exam modes, requires document_id + subject)
- **api/attempts.py**: Submit answers (auto-grade), list, get
- **api/progress.py**: Per-topic metrics, weak topic detection
- **api/rag.py**: Proxy endpoints forwarding to RAG microservice
- **api/chat.py**: Chat session CRUD (multi-turn conversation management)
- **services/rag_client.py**: HTTP singleton wrapping RAG service API calls
- **start.sh**: Runs `alembic upgrade head` then starts uvicorn (used in Docker)

**Key Patterns**:
- `AuthResponse` schema returns token + user in a single response (both login and register)
- Celery task `ingest_document(doc_id, file_path)` for async ingestion
- `WEAK_TOPIC_THRESHOLD` (default 0.60) configurable via env

#### 3. **RAG Engine** (Python microservice with LlamaIndex)
**File**: `rag-service/app/rag/engine.py` (LlamaIndexRAGEngine class)

**LLM & Embeddings**:
- **LLM**: Groq `llama-3.3-70b-versatile` (free, via `llama-index-llms-groq`)
- **Embeddings**: FastEmbed `BAAI/bge-small-en-v1.5` (free, local ONNX, no API key needed)
  - Falls back to OpenAI `text-embedding-3-small` if `OPENAI_API_KEY` is set
- **Vision OCR**: Groq `meta-llama/llama-4-scout-17b-16e-instruct` for scanned PDF pages

**Singleton Pattern**: `get_rag_engine()` returns one global instance. Lazy configuration — LlamaIndex Settings configured on first use (fast health checks at startup).

**Per-Collection Indexes**: Each `{level}_{subject}` (e.g. `P6_Social_studies`) has its own VectorStoreIndex persisted at `storage/{collection}/`. Loaded on demand and cached in `self._indexes`.

**Document Ingestion** (`ingest`):
```
PDF files -> Groq Vision OCR (for scanned pages)
  -> SentenceSplitter (chunk_size=1024, overlap=100)
  -> Build VectorStoreIndex with FastEmbed embeddings
  -> Persist to disk at storage/{collection}/
```

**Query Flow** (two code paths in `query()` method):

**Path A — With chat_history** (follow-up questions):
1. `_condense_question()`: Rewrites follow-up as standalone question
   - Includes collection context hint (e.g. "This is about P6 Social studies")
   - Filters out failed assistant responses from history
2. Retrieve with condensed question via `index.as_retriever(similarity_top_k)`
3. Log retrieval scores (min/max/avg) for debugging
4. Synthesize with conversation history block + exam content context
5. Returns: `{ answer, sources, condensed_question }`

**Path B — Without chat_history** (first question in session):
1. `_is_vague_query()`: Detects short/generic questions (<=5 words or pattern match)
   - Patterns: "what about this", "tell me about", "this paper", "overview", etc.
2. If vague: `_expand_query_with_context()` prepends collection name + context
   - e.g. "what about this paper?" -> "P6 Social studies exam paper: what about this paper? What topics, questions, and content are covered in the P6 Social studies exam?"
3. Retrieve with (expanded) question
4. Log retrieval scores
5. Choose synthesis prompt: **overview prompt** (vague) vs **strict prompt** (specific)
   - Overview prompt asks LLM to summarize subject, format, topics, details
   - Strict prompt tells LLM to say "I could not find" if answer not in content
6. Returns: `{ answer, sources, expanded_question (if expanded) }`

**Key Methods**:
- `ingest(source_path, collection, overwrite)`: Load PDFs, chunk, embed, build index
- `retrieve(query, collection, top_k)`: Return ranked chunks with scores
- `query(question, collection, top_k, chat_history)`: Full RAG with LLM answer
- `_condense_question(question, chat_history, collection)`: Rewrite follow-up as standalone
- `_is_vague_query(question)`: Detect vague/short questions
- `_expand_query_with_context(question, collection)`: Add collection context for better retrieval

**Configuration** (`rag-service/app/config.py`):
```python
LLAMA_INDEX_PROVIDER = "groq"          # groq | openai | gemini
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 100
SIMILARITY_TOP_K = 10
KG_RAG_ENABLED = False                 # PropertyGraph (optional, future)
```

#### 4. **Database** (PostgreSQL 16, 11 tables)
- **users**: email, password_hash, role (student/admin), education_level (P6/S3/S6/TTC)
- **documents**: filename, subject, level, year, ingestion_status, is_personal, is_shared, official_duration_minutes, instructions
- **document_shares**: M2M junction for student document sharing
- **topics**: Self-referential hierarchy (parent_id)
- **subscriptions**: M2M user-topic
- **questions**: Extracted from documents, tagged with topics
- **solutions**: Answer explanations linked to questions
- **quizzes**: mode, duration, document_id
- **quiz_questions**: M2M quiz-question (ordered)
- **attempts**: score, duration, document_id
- **attempt_answers**: Per-question correctness
- **progress**: Per-student per-topic accuracy metrics

**Key Pattern**: Soft deletes for audit trail; never delete exam attempts. Topic-level metrics enable adaptive recommendations.

## Authentication Flow (Current Implementation)

```
1. User calls POST /api/users/login (or /register)
2. Backend returns AuthResponse { access_token, token_type: "bearer", user: UserRead }
3. Frontend stores token via apiClient.setToken(), user in Zustand store
4. Zustand persist middleware saves to localStorage
5. On page load: Zustand hydrates from localStorage, sets hasHydrated=true
6. AuthGuard component waits for hasHydrated before checking isAuthenticated
7. All API requests: Axios interceptor adds Authorization: Bearer {token}
8. On 401: Axios interceptor calls useAuthStore.getState().logout() (clears Zustand + token)
9. AuthGuard detects isAuthenticated=false -> redirect to /login
```

**Critical**: Both `/login` and `/register` return the same `AuthResponse` shape. Frontend never needs a separate `/me` call after auth.

## User Workflows

### Admin Flow
1. Log in -> Document Management
2. Upload exam paper PDF (specify subject, level, year)
3. System queues Celery task -> RAG ingestion (OCR -> chunk -> embed -> index)
4. Document status: PENDING -> INGESTING -> COMPLETED
5. View student progress dashboard

### Student Flow
1. Log in -> Practice Dashboard
2. **Ask AI**: Select collection (ingested paper), chat with it
   - First question gets smart expansion if vague
   - Follow-ups use chat history condensation
3. **Three Quiz Modes**:
   - **Adaptive Practice**: System recommends weak topics (accuracy < 60%)
   - **Topic-Focused**: Random quiz within subscribed topics
   - **Real Exam Simulation**: Full-length exam with official timing
4. Submit answers -> auto-grade -> per-topic score breakdown
5. View analytics: accuracy per topic, improvement trends

## Development Workflow

### Docker Setup (Recommended)
```bash
# Create root .env with API keys (see docs/SETUP_GUIDE.md)
make docker-up          # starts all 6 containers

# Rebuild a single service after code changes
docker compose up -d --build rag-service

# View logs
docker compose logs -f rag-service
docker compose logs backend --tail=50
```

### Local Setup
```bash
uv sync --all-packages                      # Python deps
cd frontend && npm install                   # JS deps
make dev-all                                 # all 3 services in parallel
```

### Key Commands (Root Makefile)
```bash
make docker-up        # Docker Compose up (all services)
make dev-all          # Local dev (3 servers in parallel)
make install          # uv sync + npm install
make test             # pytest + jest
make lint             # ruff check
make format           # ruff format
```

### Code Standards
- **Frontend**: ESLint + Prettier (format on save)
- **Backend**: Ruff for linting + formatting
- **Commit**: Conventional commits (feat:, fix:, refactor:)
- **All documentation**: Lives in `docs/` folder (not scattered in root or sub-services)

## Important Implementation Notes

- **PDF Parsing**: Groq Vision (`llama-4-scout`) for OCR on scanned exam papers; LlamaParse as optional advanced parser
- **Document Ingestion**: Queued as Celery async task. `backend_uploads` volume shared across backend, rag-service, and celery-worker containers
- **Singleton RAG Engine**: `get_rag_engine()` returns one global instance; per-collection indexes loaded on demand
- **Vague Query Expansion**: First-time questions like "what about this paper?" are expanded with collection context before vector search, improving retrieval relevance
- **Chat History Condensation**: Follow-up questions are rewritten as standalone queries with collection context hint; failed assistant responses are filtered from history
- **Dual Synthesis Prompts**: Vague questions get an overview prompt (summarize the paper); specific questions get a strict prompt (answer from content or say "could not find")
- **Retrieval Score Logging**: Both code paths log min/max/avg similarity scores for debugging retrieval quality
- **Embedding Strategy**: FastEmbed (free, local, ONNX) by default when using Groq LLM; OpenAI embeddings if `OPENAI_API_KEY` is provided
- **Auth Pattern**: `AuthResponse` returns token + user together; Zustand `hasHydrated` flag prevents SSR redirect loops; AuthGuard wraps protected layouts
- **Weak Topic Threshold**: Configurable via `WEAK_TOPIC_THRESHOLD` env var (default 0.60)

## Extending the System
1. **New Features**: Create isolated module under `backend/app/api/` with own routes + schemas
2. **New Subject/Level**: Update enum constants in shared interfaces, upload documents
3. **New RAG Model**: Change `LLAMA_INDEX_PROVIDER` and model name in `.env`, restart RAG service
4. **PropertyGraph**: Set `KG_RAG_ENABLED=true` in config; implement extractors in engine.py
5. **Scale Vector Store**: Current: persisted VectorStoreIndex on disk. Future: pgvector, Pinecone, or Weaviate
6. **All docs**: `docs/` folder — see `docs/DOCS_INDEX.md` for full map
