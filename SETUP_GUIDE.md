# E-exam-prepare Setup Guide

## Quick Start (5 minutes)

### 1. Get a Free Groq API Key
```bash
# Visit https://console.groq.com (no credit card needed)
# Create account → API Keys → Generate new key
# Copy your key: gsk_...
```

### 2. Configure Environment
Create `.env` file in project root with:
```bash
# RAG Service
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Backend
DATABASE_URL=postgresql+psycopg://exam_prep:exam_prep_dev@localhost:5432/exam_prep
SECRET_KEY=your-secret-key-change-in-production
RAG_SERVICE_URL=http://localhost:8001
```

Or copy each to respective `.env` files:
- `rag-service/.env` - Groq + RAG config
- `backend/.env` - Database + Backend config

### 3. Install Dependencies
```bash
cd /path/to/E-exam-prepare
uv sync --all-packages
```

### 4. Start Services

**Terminal 1 - RAG Service** (port 8001):
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

**Terminal 2 - Backend** (port 8000):
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 3 - Frontend** (port 3000):
```bash
cd frontend
npm install  # Only first time
npm run dev
```

### 5. Access the App
```
Frontend: http://localhost:3000
Backend API: http://localhost:8000
RAG Service: http://localhost:8001
API Docs: http://localhost:8000/docs
```

---

## System Architecture

```
┌─────────────────┐
│  Frontend       │ (Next.js)
│  (port 3000)    │
└────────┬────────┘
         │
         ↓ HTTP
┌─────────────────────────────────────────┐
│  Backend API                            │ (FastAPI)
│  • User management                      │ (port 8000)
│  • Quiz generation & grading            │
│  • Progress tracking                    │
│  • RAG Service integration              │
└────────┬────────────────────────────────┘
         │
         ↓ HTTP (RAG queries)
┌─────────────────────────────────────────┐
│  RAG Service                            │ (FastAPI)
│  • Document ingestion                   │ (port 8001)
│  • Hybrid retrieval (Vector + BM25)     │
│  • LLM synthesis (Groq)                 │
│  • Embedding generation                 │
└────────┬────────────────────────────────┘
         │
         ↓ API
    ┌────────────────┐
    │  Groq API      │ (Free)
    │  LPU™ Inference│
    └────────────────┘
```

---

## 🎯 Groq Integration

### Why Groq?
- **Completely FREE** - No credit card needed
- **Ultra-fast** - Sub-100ms response times
- **Deterministic** - Predictable performance
- **Production-ready** - Used by major AI companies

### Supported Models
```
GROQ_LLM_MODEL = "mixtral-8x7b-32768"  # Default (free, excellent quality)
```

Other available:
- `llama3-70b-8192` - Larger, better quality
- `llama2-70b-4096` - Good quality
- See https://console.groq.com/docs/models

### How It Works
```
User submits quiz
   ↓
Backend → RAG Service
   ↓
RAG retrieves exam content from vector store
   ↓
RAG uses Groq LLM to generate quiz questions
   ↓
Groq returns in <100ms (free, no billing)
   ↓
Backend formats and sends to frontend
   ↓
Student takes quiz
```

---

## 📋 Configuration Details

### Environment Variables

#### RAG Service (rag-service/.env)
```bash
# Required
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Optional (for embeddings)
OPENAI_API_KEY=sk_...           # For better embeddings quality
GOOGLE_API_KEY=...              # For Gemini embeddings

# Performance tuning
CHUNK_SIZE=1024                 # Token size per document chunk
CHUNK_OVERLAP=100               # Overlap between chunks
SIMILARITY_TOP_K=10             # Results to return before LLM

# Optional advanced
KG_RAG_ENABLED=false            # Knowledge graph (experimental)
LLAMA_CLOUD_API_KEY=...         # For LlamaParse OCR
```

#### Backend (backend/.env)
```bash
# Database
DATABASE_URL=postgresql+psycopg://exam_prep:exam_prep_dev@localhost:5432/exam_prep

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# RAG Service
RAG_SERVICE_URL=http://localhost:8001

# Optional
GROQ_API_KEY=gsk_...            # Pass to RAG if needed
```

#### Frontend (frontend/.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
```

---

## 🚀 Common Tasks

### Upload Exam Papers
1. Log in as admin
2. Go to Document Management
3. Upload PDF (exam paper + solution)
4. RAG service automatically:
   - Extracts questions
   - Generates embeddings
   - Indexes for retrieval

### Generate Quiz
1. Student selects topic
2. Chooses mode:
   - **Adaptive Practice** - System recommends weak areas
   - **Topic Practice** - Random quiz from selected topic
   - **Real Exam Simulation** - Full-length timed exam
3. System calls RAG Service → Groq → Quiz generated
4. Student takes quiz (with timer)
5. Instant grading + explanation generation

### View Progress
1. Student dashboard shows:
   - Accuracy by topic
   - Improvement trends
   - Recommended practice areas
2. Admin dashboard shows:
   - Aggregate student stats
   - Most difficult topics
   - Learning curves

---

## 🔧 Switching LLM Providers

### Option 1: Keep Groq (Recommended)
```bash
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_...
```
Cost: FREE (LLM) + optional $0.02/1K queries (embeddings)

### Option 2: Use OpenAI
```bash
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk_...
```
Cost: ~$0.30/1K queries

### Option 3: Use Google Gemini
```bash
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=...
```
Cost: FREE (both LLM + embeddings on free tier)

---

## 🧪 Testing

### Test RAG Service
```bash
# Start RAG service, then:
curl -X POST http://localhost:8001/health
# Should return: {"status": "ok"}
```

### Test Backend
```bash
# Start backend, then run tests:
cd backend
uv run pytest tests/test_users.py -v
```

### Test Frontend
```bash
cd frontend
npm run test
```

---

## 📊 Database Setup (Optional)

### PostgreSQL (Production)
```bash
# Install PostgreSQL
brew install postgresql@15

# Create database
createdb exam_prep
createuser exam_prep -P
psql exam_prep -c "GRANT ALL PRIVILEGES ON DATABASE exam_prep TO exam_prep;"

# Update DATABASE_URL
export DATABASE_URL="postgresql+psycopg://exam_prep:password@localhost:5432/exam_prep"
```

### SQLite (Development - No Setup Needed)
```bash
# Tests use in-memory SQLite automatically
uv run pytest tests/
```

---

## 🐛 Troubleshooting

### "Cannot connect to RAG Service"
```bash
# Make sure RAG service is running:
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### "GROQ_API_KEY not configured"
```bash
# Ensure .env file has the key:
cat rag-service/.env | grep GROQ_API_KEY
# Should show: GROQ_API_KEY=gsk_...
```

### "Rate limited"
Groq free tier allows ~30K tokens/min. If hitting limits:
- Space out requests
- Reduce `max_tokens` in config
- Check https://status.groq.com

### Port already in use
```bash
# Change ports in .env or startup commands:
# Frontend: npm run dev -- -p 3001
# Backend: uvicorn app.main:app --port 8001
# RAG: uvicorn app.main:app --port 8002
```

---

## 📚 Documentation

- **Groq**: https://console.groq.com/docs
- **LlamaIndex**: https://docs.llamaindex.ai
- **FastAPI**: https://fastapi.tiangolo.com
- **Next.js**: https://nextjs.org/docs

---

## 🎓 Project Structure

```
E-exam-prepare/
├── frontend/              # Next.js web app
│   ├── app/              # Page routes
│   ├── components/       # React components
│   ├── hooks/            # Custom hooks
│   └── styles/           # TailwindCSS
│
├── backend/              # FastAPI API
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── config.py     # Settings
│   └── tests/            # Integration tests
│
├── rag-service/          # RAG engine (LlamaIndex)
│   ├── app/
│   │   ├── rag/          # RAG engine
│   │   ├── llms/         # LLM providers
│   │   ├── embeddings/   # Embedding functions
│   │   ├── routes/       # API endpoints
│   │   └── config.py     # Settings
│   └── GROQ_SETUP.md     # Groq guide
│
└── GROQ_INTEGRATION.md   # This setup guide
```

---

## ✅ Deployment Checklist

- [ ] Groq API key obtained
- [ ] `.env` files created with required variables
- [ ] Dependencies installed: `uv sync --all-packages`
- [ ] RAG service starts: `uvicorn app.main:app --port 8001`
- [ ] Backend starts: `uvicorn app.main:app --port 8000`
- [ ] Frontend starts: `npm run dev`
- [ ] Can access http://localhost:3000
- [ ] Backend API docs at http://localhost:8000/docs
- [ ] Tests pass: `pytest tests/`

---

## 🎉 Success!

Your E-exam-prepare platform is now running with:
- ✅ Groq for free, ultra-fast LLM inference
- ✅ LlamaIndex RAG for intelligent document retrieval
- ✅ Next.js frontend with responsive design
- ✅ FastAPI backend with JWT authentication
- ✅ Adaptive learning system based on student progress

**Total setup time**: ~5 minutes (excluding npm install)
**Monthly cost**: FREE (Groq) + optional embeddings
**Inference speed**: <100ms per query (Groq's LPU™)

Happy exam prep! 🎓

---

For detailed Groq integration info, see `rag-service/GROQ_SETUP.md`
