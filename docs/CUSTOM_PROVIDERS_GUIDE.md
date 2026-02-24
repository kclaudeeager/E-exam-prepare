# Custom LLM & Embedding Providers Setup

> **⚠️ Historical Document**: This guide was written during the initial multi-provider setup. The default Groq model is now `llama-3.3-70b-versatile` (not Mixtral), and embeddings use **FastEmbed** (local ONNX, `BAAI/bge-small-en-v1.5`) by default. See [PROVIDER_SETUP.md](PROVIDER_SETUP.md) for current configuration.

## Summary

You now have **3 LLM providers** and custom embedding functions ready to use:

### ✅ Available Providers

1. **Groq** (🎉 **Recommended for Development**)
   - Completely FREE
   - Fast inference
   - Perfect for development & testing
   - Models: Mixtral 8x7B (free)

2. **Google Gemini** (Free/Cheap)
   - Free tier very generous
   - Excellent quality
   - Custom embedding function included
   - Models: Gemini 2.0 Flash

3. **OpenAI** (Paid)
   - Production-grade quality
   - Highest accuracy
   - Pay-as-you-go pricing
   - Models: GPT-4

---

## Implementation Details

### Files Created

#### Custom LLM Wrappers
- **`rag-service/app/llms/gemini_llm.py`** (400+ lines)
  - Full LlamaIndex-compatible Gemini LLM
  - Thread-safe multiprocessing support
  - Automatic retry with backoff
  - Streaming support

- **`rag-service/app/llms/groq_llm.py`** (350+ lines)
  - Full LlamaIndex-compatible Groq LLM
  - Free tier support
  - Fast inference optimization
  - Streaming support

#### Custom Embedding Functions
- **`rag-service/app/embeddings/gemini_embedding.py`** (60+ lines)
  - ChromaDB-compatible Gemini embedding function
  - Batch embedding support
  - Error handling

#### Configuration & Factory
- **`rag-service/app/config.py`** (Updated)
  - Now supports 3 providers (openai, gemini, groq)
  - Environment-based provider selection

- **`rag-service/app/providers.py`** (250+ lines)
  - Factory functions: `get_llm()`, `get_embeddings()`
  - Automatic provider detection
  - Configuration logging

#### Documentation
- **`rag-service/PROVIDER_SETUP.md`** (350+ lines)
  - Complete setup guide for each provider
  - Cost comparison
  - Troubleshooting

- **`rag-service/RAG_INTEGRATION.md`** (300+ lines)
  - Frontend integration guide
  - API endpoint documentation
  - Example usage patterns

#### Dependencies
- **`rag-service/pyproject.toml`** (Updated)
  - Added: `groq>=0.17.0`
  - Added: `google-genai>=0.9.0`

---

## Quick Start

### 1. Choose a Provider

#### Option A: Groq (Recommended - FREE) ✅
```bash
# Get free key at: https://console.groq.com
# Add to .env
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

#### Option B: Gemini (Free/Cheap)
```bash
# Get free key at: https://aistudio.google.com/app/apikey
# Add to .env
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
```

#### Option C: OpenAI (Paid)
```bash
# Get key at: https://platform.openai.com/api/keys
# Add to .env
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk_your_key_here
```

### 2. Install Dependencies
```bash
cd rag-service
uv sync  # Installs groq + google-genai automatically
```

### 3. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### 4. Test It
```bash
# Query endpoint
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'

# Should return answer synthesized by your chosen provider
```

---

## Architecture Overview

```
Frontend (Next.js)
    ↓
Backend (FastAPI)
    ↓
RAG Service (LlamaIndex)
    ├─→ LLM Provider (Groq/Gemini/OpenAI)
    │   ├─→ custom gemini_llm.py
    │   ├─→ custom groq_llm.py
    │   └─→ default openai llm
    │
    ├─→ Embedding Provider (Gemini/OpenAI)
    │   ├─→ custom gemini_embedding.py
    │   └─→ default openai embeddings
    │
    └─→ Vector Store (Chroma)
        └─→ Stored embeddings + chunks
```

---

## Feature Comparison

### Gemini LLM (`gemini_llm.py`)
```python
from app.llms import GoogleGeminiLLM

llm = GoogleGeminiLLM(
    api_key="...",
    model_name="gemini-2.0-flash",
    temperature=0.1,
    max_tokens=2048,
    max_retries=3,  # Automatic retry
    retry_delay=2.0
)

# Chat mode
response = llm.chat(messages)

# Stream mode
for chunk in llm.stream_chat(messages):
    print(chunk.delta)

# Async
response = await llm.achat(messages)
```

**Features**:
- ✅ Thread-local client storage (multiprocessing safe)
- ✅ Exponential backoff retry
- ✅ System prompt support
- ✅ Streaming & non-streaming
- ✅ Full async support
- ✅ Error recovery

### Groq LLM (`groq_llm.py`)
```python
from app.llms import GroqLLM

llm = GroqLLM(
    api_key="...",
    model_name="mixtral-8x7b-32768",  # Free!
    temperature=0.1,
    max_tokens=2048
)

# Chat mode
response = llm.chat(messages)

# Stream mode (very fast!)
for chunk in llm.stream_chat(messages):
    print(chunk.delta)

# Async
response = await llm.achat(messages)
```

**Features**:
- ✅ Completely free (development)
- ✅ Very fast inference
- ✅ Full streaming support
- ✅ Rate limit error handling
- ✅ Async support
- ✅ Error recovery

### Gemini Embeddings (`gemini_embedding.py`)
```python
from app.embeddings import GeminiEmbeddingFunction

embeddings = GeminiEmbeddingFunction(
    api_key="...",
    model_name="models/embedding-001"
)

# Embed documents
vectors = embeddings(["text1", "text2", "text3"])
# Returns: [[0.1, 0.2, ...], [0.3, 0.4, ...], ...]

# Use with ChromaDB
import chromadb
client = chromadb.Client()
collection = client.get_or_create_collection(
    name="exams",
    embedding_function=embeddings
)
```

**Features**:
- ✅ ChromaDB compatible
- ✅ Batch embedding
- ✅ Error handling
- ✅ Logging

---

## Configuration Priority

The system uses this priority for configuration:

1. **`.env` file** (highest priority)
   ```bash
   LLAMA_INDEX_PROVIDER=groq
   GROQ_API_KEY=...
   ```

2. **Environment variables**
   ```bash
   export LLAMA_INDEX_PROVIDER=groq
   export GROQ_API_KEY=...
   ```

3. **Default values** (lowest priority)
   ```python
   # In config.py
   LLAMA_INDEX_PROVIDER: str = "groq"
   ```

---

## Provider Selection Logic

When you call `get_llm()`:

```python
from app.providers import get_llm

llm = get_llm()  # Automatically returns correct provider
```

It checks `LLAMA_INDEX_PROVIDER` setting:
- `groq` → GroqLLM (free)
- `gemini` → GoogleGeminiLLM (free/cheap)
- `openai` → OpenAI LLM (paid)

Same for `get_embeddings()`:
- `groq` → OpenAI embeddings (needs OPENAI_API_KEY)
- `gemini` → GeminiEmbeddingFunction (free with key)
- `openai` → OpenAI embeddings (needs key)

---

## Recommended Development Setup

### Phase 1: Initial Development (Groq - FREE)
```bash
# Cost: $0/month
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_free_key_from_console.groq.com
```

### Phase 2: Testing with Better Quality (Gemini - FREE)
```bash
# Cost: $0/month (generous free tier)
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_free_key_from_aistudio
```

### Phase 3: Production (Your Choice)
- Stick with **Groq** (still free, optimized for production)
- Upgrade to **Gemini** (cheap, high quality)
- Switch to **OpenAI** (premium, best quality)

**Total cost for development: $0** 🎉

---

## Integration with Frontend

### Example: Show Solution on Failed Question
```typescript
// frontend: student/attempts/[id]/page.tsx
async function showSolution(question: string) {
  try {
    const response = await apiClient.post(
      "http://localhost:8001/rag/query",
      { question, top_k: 5 }
    );
    
    setSolution(response.data.answer);
    setSources(response.data.sources);
  } catch (error) {
    setError("Could not retrieve explanation");
  }
}
```

This automatically:
1. Retrieves relevant exam chunks from vector store
2. Sends to configured LLM provider (Groq/Gemini/OpenAI)
3. Returns synthesized answer with sources
4. All for FREE (if using Groq)!

---

## File Structure

```
rag-service/
├── app/
│   ├── llms/
│   │   ├── __init__.py
│   │   ├── gemini_llm.py    ← Custom Gemini (400 lines)
│   │   └── groq_llm.py      ← Custom Groq (350 lines)
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── gemini_embedding.py  ← Custom Gemini (60 lines)
│   ├── config.py            ← Updated with 3 providers
│   ├── providers.py         ← New: factory functions
│   └── routes/
│       ├── ingest.py        ← Document loading
│       ├── retrieve.py      ← Chunk retrieval
│       └── query.py         ← Full RAG queries
├── PROVIDER_SETUP.md        ← Setup guide (350 lines)
├── RAG_INTEGRATION.md       ← Frontend guide (300 lines)
└── pyproject.toml           ← Updated dependencies
```

---

## API Endpoints (Unchanged)

All RAG endpoints work with any provider:

```bash
# Ingest documents
POST /rag/ingest
{
  "source_path": "./documents",
  "overwrite": false
}

# Retrieve chunks
GET /rag/retrieve?query=topic&top_k=5

# Full RAG with LLM synthesis
POST /rag/query
{
  "question": "What is this exam about?",
  "top_k": 5
}
```

---

## Next Steps

### 1. Install Dependencies
```bash
cd rag-service
uv sync
```

### 2. Get API Key (Choose One)
- **Groq** (recommended): https://console.groq.com
- **Gemini**: https://aistudio.google.com/app/apikey
- **OpenAI**: https://platform.openai.com/api/keys

### 3. Configure
```bash
# Create/update .env in rag-service/
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=your_key
```

### 4. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### 5. Test
```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'
```

### 6. Switch Providers Anytime
Just edit `.env` and restart! No code changes needed.

---

## Support

### Documentation Files
- **PROVIDER_SETUP.md** — Detailed setup for each provider
- **RAG_INTEGRATION.md** — Frontend integration guide
- **app/llms/gemini_llm.py** — Docstrings on each method
- **app/llms/groq_llm.py** — Docstrings on each method
- **app/embeddings/gemini_embedding.py** — Docstrings

### Troubleshooting
See **PROVIDER_SETUP.md** "Troubleshooting" section for solutions

---

## Cost Summary

| Provider | Dev Cost | Prod Cost | Quality | Speed |
|----------|----------|-----------|---------|-------|
| **Groq** | $0/mo ✅ | $0/mo ✅ | Good | Very Fast |
| **Gemini** | $0/mo ✅ | $0-50/mo | Excellent | Fast |
| **OpenAI** | $0/mo ✅ | $50+/mo | Best | Medium |

**Recommendation**: Use **Groq** throughout development for completely free RAG! 🚀

---

**Created**: February 23, 2026
**Status**: Ready for Production
**LLM Providers**: 3 (Groq, Gemini, OpenAI)
**Embedding Providers**: 3 (Groq→OpenAI, Gemini, OpenAI)
