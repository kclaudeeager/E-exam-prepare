# Copilot Instructions for E-exam-prepare

## Project Vision
**E-exam-prepare** is a personalized exam preparation e-learning platform that helps students prepare for exams by practicing with past papers in a guided, adaptive way. The system uses RAG (Retrieval-Augmented Generation) to analyze exam papers and answer documents, generate random quizzes, time student attempts, and provide explanations for correct solutions.

## System Architecture

### High-Level Flow
```
Exam Documents (PDFs) 
  → RAG Ingestion Pipeline
  → Vector Store
  → Quiz Generation Engine
  → Student Practice Interface
  → Assessment & Feedback
  → Progress Tracking
```

### Core Modules (Must Be Modular for Easy Onboarding)

#### 1. **Frontend** (Next.js + TypeScript)
- **dashboard/**: Student/Admin dashboards with role-based views
- **exam-practice/**: Timed exam interface, question rendering, submission
- **document-management/**: Upload, organize, view documents
- **progress/**: Score history, analytics, performance charts
- **shared/**: Reusable components, hooks, utilities

**Key Pattern**: Use custom React hooks for API calls (e.g., `useExamQuiz`, `useDocumentUpload`) - isolates business logic from UI.

#### 2. **Backend** (Python FastAPI or Node.js)
- **api/documents/**: CRUD for exam papers and solutions
- **api/quiz/**: Generate random quizzes from documents (RAG integration)
- **api/attempts/**: Record exam attempts, scoring, timing
- **api/users/**: Auth, role management (student/admin)
- **api/progress/**: Analytics and student learning trajectories

**Key Pattern**: All endpoints return structured responses with clear error codes for client-side handling.

#### 3. **RAG Engine** (Python microservice with LlamaIndex)
**Framework**: LlamaIndex with PropertyGraphIndex for semantic relationship extraction

**Architecture**:
- **Document Ingestion Pipeline** (`_build_indexes()`): 
  - Load PDFs via SimpleDirectoryReader (with LlamaParse for advanced parsing)
  - Chunk via SentenceSplitter (configurable chunk_size/overlap)
  - Build dual indexes: VectorStoreIndex + PropertyGraphIndex
  - Persist to disk for fast reload
  
- **Retrieval Strategy** (Hybrid):
  - VectorIndexRetriever: Semantic search via embeddings
  - BM25Retriever: Keyword/BM25 matching for exact terms
  - QueryFusionRetriever: Reciprocal rank fusion of above two
  - SentenceTransformerRerank (BGE): Rerank top candidates
  - PropertyGraphRetriever (optional): Graph-based traversal for concept relationships

- **Query Engine** (`_create_query_engine()`):
  - Executes hybrid retrieval → reranking → LLM synthesis
  - PropertyGraph augmentation: if enabled, enriches answer with extracted triplets

**Extractors** (for PropertyGraph):
- **SimpleLLMPathExtractor**: Single-hop (subject, relation, object) triplets
- **DynamicLLMPathExtractor**: Multi-hop paths with entity/relation type constraints
- **SchemaLLMPathExtractor**: Strict schema validation (exam entity→relation mapping)
- **ImplicitPathExtractor**: Captures pre-existing relationships

**Key Methods**:
- `ingest(source_path, overwrite)`: Load documents, chunk, build both indexes
- `retrieve(query, top_k)`: Return ranked chunks + graph triplets (if enabled)
- `query(question, top_k)`: Full RAG with LLM answer + graph augmentation
- `_pg_augmented_query()`: Re-synthesize answer using both vector context + graph paths

**Key Pattern**: Store exam metadata (official_duration_minutes, instructions) in document metadata before ingestion — retrieved during quiz setup.

#### 4. **Database**
- **documents**: Store metadata (subject, level, year, uploader, created_at, official_duration, instructions)
- **questions**: Extracted questions with embeddings, topic/subtopic tags, source references
- **solutions**: Answer explanations linked to questions with confidence scores
- **users**: Student/Admin profiles with roles and subscriptions (topics user wants to focus on)
- **attempts**: Exam submissions with timestamps, answers, scores, topic-level breakdown
- **progress**: Per-student, per-topic metrics (accuracy %, attempts count, last_attempted_date)
- **subscriptions**: Track which topics each student is focusing on

**Key Pattern**: Soft deletes for audit trail; never delete exam attempts. Topic-level metrics enable adaptive recommendations.

## User Workflows

### Admin Flow
1. Log in → Document Management
2. Upload exam paper + answer document (PDF)
3. System processes: Extract questions/solutions → Generate embeddings
4. Optionally curate/edit extracted content (validate RAG accuracy)
5. View student progress dashboard (aggregate stats, learning curves)

### Student Flow
1. Log in → Practice Dashboard
2. **Subscribe to topics** (Math → Algebra, Geometry; Biology → Genetics, etc.)
3. **Three Quiz Modes**:
   - **Adaptive Practice**: System recommends weak topics based on past performance
   - **Topic-Focused**: Random quiz within subscribed topics (5-15 questions)
   - **Real Exam Simulation**: Full-length exam with official timing (e.g., 2.5 hours for S3 Math)
4. Timer countdown during attempt (with pause alerts for real exams)
5. Submit answers → Get instant score breakdown by topic
6. Click "Show Solution" on failed questions → RAG retrieves explanation + source document
7. View analytics: accuracy per topic, improvement trends, weakness recommendations

## Critical Design Patterns

### Modularity for Onboarding
- **Clear folder structure**: Each feature is self-contained (documents/, quiz/, progress/)
- **API contract definitions**: Shared TypeScript interfaces/Pydantic models prevent integration bugs
- **Environment config**: Externalize RAG model choice, database URLs, vector store type
- **Documentation-first**: Every module has `README.md` explaining purpose and key functions

### Adaptive Quiz Engine (Core Intelligence)
- **Weak Topic Detection**: Calculate accuracy per topic from `attempts` table
  - If accuracy < 60% in a topic → flag for adaptive practice
  - Recommend: "You scored 45% on Geometry - practice more Geometry questions?"
- **Adaptive Quiz Generation**: When student chooses "Recommended Practice"
  - Retrieve weak topics from progress table
  - Query RAG for questions ONLY from those topics
  - Deliver 10-15 questions, slightly easier than real exam difficulty
- **Real Exam Mode**: Fetch complete exam with:
  - Official duration from document metadata (e.g., "2 hours 30 minutes")
  - Question order as published
  - Official marking scheme for grading
  - Display timer with warnings at 10 mins, 5 mins remaining

### RAG Integration Pattern (LlamaIndex-based)

**Singleton Architecture** (`__new__` pattern):
- One instance per (provider, collection, reuse_index) combo
- Prevents duplicate index loading in memory
- Supports multiple collections (Math, Biology, etc. can each have their own index)

**Settings Configuration** (via config/settings.py):
- `LLAMA_INDEX_PROVIDER`: "openai" or "gemini" (determines LLM + embeddings)
- `CHUNK_SIZE` / `CHUNK_OVERLAP`: Default 1024/100 for semantic coherence
- `SIMILARITY_TOP_K`: How many results to rerank (default 10)
- `kg_rag.enabled`: Enable PropertyGraph for exam relationship extraction
- `kg_rag.extractors.type`: "simple", "dynamic", or "schema" — choose based on domain richness
- `kg_rag.graph_store`: "simple" (in-memory), "neo4j" (scalable), or "nebula"

**Ingest Pipeline** (call once per document upload):
```python
rag = LlamaIndexRAG(provider="openai", collection="S3_Math")
result = rag.ingest(
    source_path="/path/to/exam_papers/",
    overwrite=False  # Append to existing index
)
# Returns: {success, documents_loaded, nodes_created, time_seconds, property_graph_built}
```

**Retrieval Modes**:
- `retrieve(query, top_k=10)`: Get ranked chunks + graph triplets
  - Returns: `{results: [{rank, score, content, metadata}, ...], graph_paths: [...]}`
  - Used for displaying source material during quiz review
  
- `query(question, top_k=10)`: Full RAG with LLM answer
  - Returns: `{answer: "synthesized response", sources: [...], graph_enhanced: bool}`
  - Used for "Show Solution" explanations after quiz submission

**Graph Extraction for Exams** (PropertyGraph):
- Extract triplets like: `(Algebra_Topic) -[SUBTOPIC_OF]-> (Math), (Question_2019_Q5) -[COVERS]-> (Algebra)`
- Use `SchemaLLMPathExtractor` for structured exam domain:
  ```yaml
  extractors:
    type: schema
    entities: [SUBJECT, TOPIC, QUESTION, YEAR, DIFFICULTY]
    relations: [COVERS, PREREQUISITE_FOR, SIMILAR_TO, FROM_EXAM]
  ```
- Enables graph queries: "Find all Geometry questions harder than student's last attempt"

### Error Handling Convention
```
{
  "success": false,
  "error_code": "DOCUMENT_PARSE_FAILED",  // Specific code for client handling
  "message": "PDF parsing failed: unsupported format",
  "details": { /* debug info */ }
}
```

## Technology Choices

### Frontend: Next.js
- **Why**: Server-side rendering for better SEO, API routes reduce backend coupling
- **Key Libraries**: TailwindCSS (styling), SWR/React Query (data fetching), next-auth (auth)
- **Structure**: `app/` directory with route groups for role-based UI separation

### Backend: Python FastAPI (Recommended) OR Node.js
- **Python**: Better for RAG/ML integration, LangChain ecosystem, vector operations
- **Node.js**: If team prefers TypeScript everywhere, but adds LLM library complexity
- **Choice**: **Default to Python** for RAG flexibility

### Vector Store Options
- **Development**: Pinecone (free tier), Supabase pgvector (PostgreSQL)
- **Production**: Weaviate (self-hosted), Milvus, or Pinecone (scaled)

### LLM Options
- **Commercial**: OpenAI API (GPT-4 for explanations), Claude for nuance
- **Open-Source**: Llama 2, Mistral (via Ollama locally)
- **Recommendation**: Start with OpenAI (easiest RAG integration), swap later if cost is concern

## Development Workflow

### Local Setup
```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all Python dependencies (workspace: backend + rag-service + web-scrap)
uv sync --all-packages

# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# RAG Service (separate process)
cd rag-service && uv run uvicorn app.main:app --reload --port 8001

# Or use Make targets
make install          # uv sync + npm install
make dev-all          # run all three services in parallel
```

### Key Commands (Root Makefile)
```bash
# Run all services
make dev-all

# Run tests
make test             # pytest backend + rag-service + jest frontend

# Format & lint code
make lint             # ruff check backend/ rag-service/
make format           # ruff format backend/ rag-service/
```

### Code Standards for Easy Onboarding
- **Frontend**: ESLint + Prettier (format on save)
- **Backend**: Ruff for linting + formatting (replaces Black, isort, Flake8)
- **Commit**: Conventional commits (feat:, fix:, refactor:)
- **PR Reviews**: Require clear docstrings on RAG/embedding functions (most prone to errors)

## Data Flow: Quiz Generation Example

### Scenario 1: Adaptive Practice (Student's Weak Areas)
```
1. Student clicks "Get Recommended Practice"
  ↓
2. Backend queries Progress table: student's topics with accuracy < 60%
  → Result: {Geometry: 45%, Biology_Genetics: 35%}
  ↓
3. Backend calls RAG Service: retrieve_questions(
     topics=["Geometry", "Biology_Genetics"],
     difficulty="medium",
     count=15
   )
  ↓
4. RAG queries vector store with topic filters
  → Returns 15 questions, tagged by source exam/year
  ↓
5. Frontend renders 15-question quiz with standard timer
  ↓
6. Student submits
  ↓
7. Backend grades, calculates per-topic accuracy, updates Progress
  → Geometry attempt #5: 8/10 (80% - improvement!)
  ↓
8. Frontend shows: "Great improvement on Geometry! Keep practicing."
```

### Scenario 2: Real Exam Simulation (Full-Length, Timed)
```
1. Student selects "S3 Mathematics 2019 - Real Exam"
  ↓
2. Backend retrieves exam with metadata:
   - official_duration_minutes: 150 (2 hours 30 mins)
   - question_count: 45
   - instructions: "Answer all questions. Show working."
  ↓
3. Frontend starts exact 150-minute countdown timer
  ↓
4. Timer alerts at 10 mins and 5 mins remaining (per exam instructions)
  ↓
5. Student submits before/at deadline
  ↓
6. Backend grades using official marking scheme
  ↓
7. Frontend displays:
   - Total score: 78/100
   - Per-topic breakdown (Algebra: 90%, Geometry: 65%, Trigonometry: 80%)
   - Official pass threshold indicator
  ↓
8. Student can review failed questions + retrieve explanations
```

### Scenario 3: Topic-Focused Practice (Student Subscription)
```
1. Student subscribed to: Math, Biology, English
  ↓
2. Student clicks "Math Practice - Random 10 Questions"
  ↓
3. Backend calls RAG: retrieve_questions(
     subject="Math",
     subscribed_topics_only=True,
     count=10,
     random=True
   )
  ↓
4. Quiz generated, student completes
  ↓
5. Results update Progress.topic_metrics for all Math subtopics practiced
```

## Important Implementation Notes
- **PDF Parsing**: Use LlamaParse (via LlamaCloud API) for OCR-rich exam papers; fallback to PyPDF2/pdfplumber
- **Exam Metadata Extraction**: Extract `official_duration_minutes`, `instructions`, `marking_scheme` from PDF metadata/headers before chunking — store in document metadata
- **Document Ingestion**: Queue as async job (Celery/Bull) to prevent upload blocking; support incremental appends (overwrite=False adds to existing index)
- **Singleton Pattern**: Use `LlamaIndexRAG(provider="openai", collection="S3_Math")` — only one instance per collection in memory
- **Hybrid Retrieval**: Always use Vector + BM25 fusion for both semantic + keyword matching (critical for exam papers with specific terminologies)
- **PropertyGraph Configuration**: Start with `SimpleLLMPathExtractor` for MVP; upgrade to `SchemaLLMPathExtractor` when you have domain-specific entity/relation types defined
- **Reranking**: BGE reranker essential for curating top-k before LLM synthesis (reduces hallucinations with large retrieval sets)
- **Topic Filtering in Adaptive Mode**: Add metadata tags (topic, subtopic, difficulty, year) during ingestion — filter RAG queries by these before retrieval
- **Caching Retrieved Paths**: Cache graph triplets for frequent queries to reduce LLM extraction costs
- **Rate Limiting**: Implement per-student quota on `query()` calls (expensive LLM synthesis) — batch questions during admin review if possible
- **Graph Store Scaling**: Use SimplePropertyGraphStore for development (<1M triplets); migrate to Neo4j when handling 1000+ exams
- **Weak Topic Threshold**: Configurable (default 60%) — update Progress.topic_metrics after each attempt, query RAG with filtered topic list for adaptive quizzes

## Extending the System
1. **New Features**: Create isolated module under `/api` or `/app` with own `routes/`, `models/`, `services/`
2. **New Subject/Level**: Update enum constants in shared interfaces, test with existing documents
3. **New RAG Model**: Swap embedding provider in `rag-service/app/config.py`, test on sample questions
4. **Scale to Admins**: Add `/api/admin/students` endpoint returning aggregate progress, paginate results
5. **Graph Extraction Tuning**: Migrate from SimpleLLMPathExtractor → SchemaLLMPathExtractor with custom entity/relation types (e.g., EXAM, QUESTION, CONCEPT, COVERS, PREREQUISITE_FOR)
6. **Vector Store Migration**: Start with SimplePropertyGraphStore (in-memory); move to Neo4j for horizontal scaling and advanced Cypher queries
