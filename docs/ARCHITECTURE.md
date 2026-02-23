# E-exam-prepare Architecture

## System Overview

E-exam-prepare is a three-tier application with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                             │
│  (UI, routing, state mgmt with SWR/Zustand, auth with next-auth)│
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP REST API
┌────────────────────────▼────────────────────────────────────────┐
│                   FastAPI Backend                                │
│  (Routes, user mgmt, quiz logic, attempt grading, progress)      │
└─────────────┬──────────────────────────────┬────────────────────┘
              │                              │
              │ SQLAlchemy ORM              │ HTTP Client
              │                             │
    ┌─────────▼──────────┐      ┌──────────▼──────────────┐
    │  PostgreSQL DB     │      │  RAG Service (Python)   │
    │  (users, docs,     │      │  (LlamaIndex, LLM)      │
    │   quizzes, score)  │      │                         │
    └────────────────────┘      └─────────┬────────────────┘
                                         │
                    ┌────────────────────┼──────────────────┐
                    │                    │                  │
            ┌───────▼─────────┐  ┌──────▼────────┐  ┌──────▼────────┐
            │ Vector Store    │  │  Graph Store  │  │  LLM API      │
            │ (pgvector/      │  │  (Neo4j/      │  │  (OpenAI/     │
            │  Pinecone)      │  │   Simple)     │  │   Google)     │
            └─────────────────┘  └───────────────┘  └───────────────┘
```

## Core Components

### 1. Frontend (Next.js)
**Responsible**: User interface, client-side routing, authentication UI, state management

**Key Features**:
- Role-based dashboards (Student/Admin)
- Exam practice interface with timer
- Progress visualization
- Document upload (admin only)

**Key Technologies**:
- Next.js 14 (App Router)
- React 18
- TailwindCSS for styling
- SWR/React Query for API calls
- Zustand for global state
- NextAuth for JWT-based auth

**Directory Structure**:
```
frontend/
├── app/                    # Route pages
│   ├── (auth)/            # Auth flows
│   ├── (student)/         # Student dashboard, exam, progress
│   └── (admin)/           # Admin dashboard, document management
├── components/            # Reusable React components
│   ├── exam/             # Question renderer, timer
│   ├── progress/         # Charts and analytics
│   └── shared/           # Navbar, buttons, modals
├── hooks/                # Custom hooks (useExamQuiz, useProgress, etc.)
└── lib/                  # Utilities, types, constants
```

### 2. Backend (FastAPI)
**Responsible**: Business logic, API routes, database operations, RAG integration

**Key Features**:
- JWT authentication
- Document CRUD
- Quiz generation (adaptive, topic-focused, real exam)
- Attempt submission and grading
- Progress tracking and analytics
- Admin endpoints for student management

**Architecture Pattern**: Service layer + Router pattern
```python
# routes (api/quiz.py)
@router.post("/generate")
async def generate_quiz(request: QuizGenerateRequest):
    service = QuizGenerationService(rag_client, db_client)
    quiz = service.generate(...)
    return quiz

# service (services/quiz_gen.py)
class QuizGenerationService:
    def generate(self, mode, student_id, count):
        # Business logic: adaptive vs random, RAG retrieval
```

**Database Tables**:
- `users` - Student/Admin accounts
- `documents` - Exam papers metadata
- `questions` - Extracted questions
- `solutions` - Answer explanations
- `topics` - Topic taxonomy
- `subscriptions` - Student → Topics mapping
- `attempts` - Quiz submissions
- `progress` - Per-topic metrics

**Directory Structure**:
```
backend/
├── api/                  # Route handlers (quiz, attempts, etc.)
├── models/              # Pydantic schemas + SQLAlchemy ORM models
├── services/            # Business logic
│   ├── rag_service.py  # RAG client wrapper
│   ├── quiz_gen.py     # Quiz generation
│   ├── grading.py      # Answer grading
│   └── progress.py     # Analytics
├── db/                  # Database setup, CRUD
├── middleware/          # Auth, error handling
└── config.py           # Environment configuration
```

### 3. RAG Service (Python Microservice)
**Responsible**: Document ingestion, vector indexing, retrieval, RAG queries

**Key Technologies**:
- LlamaIndex for RAG orchestration
- LlamaCloud + LlamaParse for advanced PDF parsing
- OpenAI/Google embeddings and LLMs
- PostgreSQL pgvector for vector storage (or Pinecone/Weaviate)
- PropertyGraphIndex for semantic relationships (optional)
- BGE reranker for ranking results

**Architecture**:
```
PDF Upload
  ↓
LlamaParse (OCR) or standard readers
  ↓
Text chunking (SentenceSplitter)
  ↓
VectorStoreIndex (embedding + storage)
  ↓
PropertyGraphIndex (optional - relationship extraction)
  ↓
Persist to disk

Query:
  VectorIndexRetriever (semantic search)
  + BM25Retriever (keyword search)
  = QueryFusionRetriever (hybrid)
  → SentenceTransformerRerank (rerank top-k)
  → LLM synthesis (generate answer)
  → PropertyGraph augmentation (optional - add graph context)
```

**Query Strategies** (implemented in backend):

1. **Adaptive Mode**: 
   - Identify student's weak topics (accuracy < 60%)
   - Call RAG with topic filters
   - Return 10-15 questions on weak areas

2. **Topic-Focused Mode**:
   - Random questions from subscribed topics
   - Filter by difficulty if requested

3. **Real Exam Mode**:
   - Retrieve complete exam by ID
   - Include metadata (duration, instructions, marking scheme)
   - Respect question order and timing

**Directory Structure**:
```
rag-service/
├── rag/
│   ├── llama_index_rag.py    # Main RAG implementation
│   ├── queries.py             # Query strategies
│   └── utils.py              # Helpers
├── config/
│   ├── settings.py           # Environment config
│   ├── domain_config.py      # Domain-specific configs
│   └── constants.py          # Enums, constants
├── routes/
│   ├── ingest.py            # Document ingestion
│   ├── retrieve.py          # Hybrid retrieval
│   └── query.py             # RAG queries
└── main.py                  # FastAPI app
```

## Data Flows

### Flow 1: Admin Uploads Exam Paper
```
1. Admin: POST /api/documents/upload (PDF file)
2. Backend: Store file, extract metadata, queue async job
3. Celery Worker: Call RAG Service /ingest
4. RAG Service: Parse PDF → Chunk → Embed → Store in vector + graph store
5. RAG returns: success, documents_loaded, nodes_created
6. Backend: Update document status to "completed"
7. Frontend: Notify admin of success
```

### Flow 2: Student Takes Adaptive Practice
```
1. Student: GET /api/progress (see weak topics)
   Example: Geometry 45%, Algebra 80%
2. Student: POST /api/quiz/generate (mode="adaptive")
3. Backend: Query Progress DB → find topics with accuracy < 60%
4. Backend: Call RAG /query with filters {topics: ["Geometry"], difficulty: "medium"}
5. RAG Service: Hybrid search + rank + LLM synthesis → 15 questions
6. Backend: Store quiz, return to frontend
7. Frontend: Render exam with timer
8. Student: Submit answers
9. Backend: Grade using marking scheme → calculate topic breakdown
10. Backend: Update Progress table
11. Frontend: Show score + weak topic recommendations
```

### Flow 3: Student Views Solution
```
1. Student: Click "Show Solution" on failed question
2. Frontend: POST /api/attempts/{id}/solution (question_id)
3. Backend: Call RAG /query (question_text, filters={source_document_id})
4. RAG: Retrieve relevant chunks + extract explanation with source attribution
5. Backend: Return solution with source document, page number, confidence
6. Frontend: Display explanation with "See original PDF" link
```

### Flow 4: Admin Views Student Progress
```
1. Admin: GET /api/admin/students/{student_id}/progress
2. Backend: Aggregate Progress table data
3. Return: {
     overall_accuracy: 68%,
     topic_metrics: [...],
     weak_topics: ["Geometry", "Trigonometry"],
     recommendations: ["Practice Geometry 5 more questions"],
     learning_trend: [...last 30 days]
   }
4. Frontend: Render charts, heatmaps, recommendations
```

## Configuration & Environment

Key environment variables control RAG behavior:

```env
LLAMA_INDEX_PROVIDER=openai  # or gemini
OPENAI_API_KEY=sk-...
CHUNK_SIZE=1024
CHUNK_OVERLAP=100
SIMILARITY_TOP_K=10
KG_RAG_ENABLED=true
KG_RAG_GRAPH_STORE=simple  # simple, neo4j, nebula
KG_RAG_EXTRACTOR_TYPE=simple  # simple, dynamic, schema
WEAK_TOPIC_THRESHOLD=0.60  # 60% accuracy
```

Domain-specific configurations in `rag-service/config/domain_config.py`:
```python
DOMAINS = {
    "S3_Math": {
        "rag_parsing": {
            "instruction": "Extract mathematical problems and solutions...",
            "parsing_tier": "parse_document_with_llm",
        },
        "kg_rag": {
            "entities": ["TOPIC", "FORMULA", "QUESTION"],
            "relations": ["COVERS", "USES_FORMULA"],
        }
    }
}
```

## Scaling Considerations

### Phase 1 (MVP - Current)
- Single PostgreSQL database
- SimplePropertyGraphStore (in-memory)
- Pinecone or pgvector for vectors
- Celery with Redis for async jobs
- One RAG service instance

### Phase 2 (Hundreds of Users)
- Horizontal scaling: Multiple backend instances (load balancer)
- Multiple RAG service instances per domain/subject
- Neo4j for PropertyGraph (scales to billions of triplets)
- Database read replicas

### Phase 3 (Thousands of Users)
- Distributed caching (Redis cluster)
- Message queue scaling (Kafka instead of Redis)
- Vector store sharding by domain
- Async question extraction (extract in background, no blocking)

## Error Handling Convention

All APIs follow this error format:
```json
{
  "success": false,
  "error_code": "DOCUMENT_PARSE_FAILED",
  "message": "PDF parsing failed: unsupported format",
  "details": { "file": "exam_2019.pdf", "reason": "..." }
}
```

Frontend uses error codes to show localized messages.

## Testing Strategy

1. **Frontend**: Jest + React Testing Library
   - Component tests
   - Hook tests (useExamQuiz, useProgress)

2. **Backend**: pytest
   - Route tests (mocking RAG service)
   - Service tests (quiz gen, grading logic)
   - Database tests (CRUD operations)

3. **RAG Service**: pytest + LlamaIndex testing utilities
   - Ingestion tests
   - Retrieval tests
   - Query tests

4. **Integration**: Docker Compose + pytest
   - Full stack test: upload → ingest → quiz → grade → progress

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/test.yml
- Lint (ESLint, Black, isort)
- Type check (mypy, TypeScript)
- Unit tests
- Integration tests
- Build Docker images
- Push to registry
```

## Monitoring & Logging

- Backend: Structured logging (JSON)
- RAG Service: Track ingestion time, retrieval latency, LLM costs
- Frontend: Error reporting (Sentry optional)
- Database: Slow query logs, connection pool monitoring
