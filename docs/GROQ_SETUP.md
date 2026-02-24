# Groq LLM Integration - E-exam-prepare RAG Service

## Overview

**Groq** is now the **default LLM provider** for the E-exam-prepare RAG service. Groq offers:
- ✅ **Completely free** API (no credit card needed)
- ✅ **Ultra-fast inference** (sub-second latency via LPU™)
- ✅ **Deterministic performance** (predictable compute time)
- ✅ **Streaming support** (real-time responses)
- ✅ **Multiple models** (Mixtral, Llama 2, Llama 3)

## Quick Start

### 1. Get a Free Groq API Key

1. Visit: https://console.groq.com
2. Sign up (free account, no credit card required)
3. Navigate to **API Keys** → Create new API key
4. Copy your API key

### 2. Configure Environment

Add to `.env` in the `rag-service/` directory:

```bash
# Default provider (Groq recommended for development)
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_api_key_here

# Optional: For better embeddings (fallback when using Groq LLM)
OPENAI_API_KEY=sk_... (optional but recommended)
```

Or set via environment variables:

```bash
export LLAMA_INDEX_PROVIDER=groq
export GROQ_API_KEY=gsk_your_api_key_here
```

### 3. Install Dependencies

```bash
# Install all dependencies including llama-index-llms-groq
uv sync --all-packages
```

### 4. Verify Configuration

```bash
cd rag-service

# Check that Groq is properly detected
python -c "from app.config import settings; print(f'Provider: {settings.LLAMA_INDEX_PROVIDER}')"

# Expected output: Provider: groq
```

## Configuration Details

### Default Settings

| Setting | Value | Notes |
|---------|-------|-------|
| `LLAMA_INDEX_PROVIDER` | `groq` | Default provider |
| `GROQ_API_KEY` | Required | Get free key at https://console.groq.com |
| `CHUNK_SIZE` | 1024 | Tokens per chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between chunks |
| `SIMILARITY_TOP_K` | 10 | Top K results to retrieve |

### Groq Models Available

The RAG service uses **llama-3.3-70b-versatile** by default:

```python
GROQ_MODEL = "llama-3.3-70b-versatile"  # Default (free tier)
```

Other available models:
- `mixtral-8x7b-32768` - Mixtral (free, good quality)
- `llama3-70b-8192` - Llama 3 (free, larger context)
- See https://console.groq.com/docs/models for full list

### Embedding Strategy

When using **Groq LLM**:
- **LLM**: llama-3.3-70b-versatile (free, via Groq)
- **Embeddings**: FastEmbed BAAI/bge-small-en-v1.5 (free, local, ONNX-based, no API key)
  - If `OPENAI_API_KEY` is set -> uses OpenAI text-embedding-3-small instead
  - FastEmbed is the default and recommended for development

**Recommendation**: FastEmbed works great out of the box with no API key. Optionally set `OPENAI_API_KEY` for higher-quality embeddings.

## Usage Examples

### 1. Chat Completion (Non-streaming)

```python
from app.providers import get_llm

llm = get_llm()  # Returns Groq LLM
response = llm.complete("Explain photosynthesis")
print(response.text)
```

### 2. Streaming Chat

```python
from app.providers import get_llm

llm = get_llm()
response = llm.stream_complete("What is quantum entanglement?")
for chunk in response:
    print(chunk.delta, end="", flush=True)
```

### 3. RAG Query (Retrieve + Synthesize)

```python
from app.rag.engine import get_rag_engine

engine = get_rag_engine()
result = engine.query(
    question="Explain the importance of low latency LLMs",
    collection="S3_Math"
)
print(result.answer)
print(f"Sources: {result.sources}")
```

### 4. Ingest Documents

```python
from app.rag.engine import get_rag_engine

engine = get_rag_engine()
result = engine.ingest(
    source_path="/path/to/exam_papers/",
    collection="S3_Math"
)
print(f"Documents loaded: {result['documents_loaded']}")
```

## Switching Providers

You can switch between providers by changing `LLAMA_INDEX_PROVIDER`:

### Option 1: Use OpenAI (Paid)

```bash
export LLAMA_INDEX_PROVIDER=openai
export OPENAI_API_KEY=sk_...
```

### Option 2: Use Google Gemini (Free tier available)

```bash
export LLAMA_INDEX_PROVIDER=gemini
export GOOGLE_API_KEY=...
```

### Option 3: Use Groq (Free, recommended)

```bash
export LLAMA_INDEX_PROVIDER=groq
export GROQ_API_KEY=gsk_...
```

## Deployment Checklist

- [ ] Groq API key obtained from https://console.groq.com
- [ ] `.env` file updated with `GROQ_API_KEY`
- [ ] `LLAMA_INDEX_PROVIDER=groq` set in `.env`
- [ ] Dependencies installed: `uv sync --all-packages`
- [ ] RAG service tested: `uv run pytest tests/`
- [ ] Embeddings verified (optional: set `OPENAI_API_KEY` for best results)

## Troubleshooting

### Error: "GROQ_API_KEY not configured"

**Solution**: Ensure your `.env` file has:
```bash
GROQ_API_KEY=gsk_your_actual_key
```

Then restart the service.

### Error: "connection timeout" or "rate limited"

**Solution**: Groq has generous free tier limits (~30,000 tokens/minute). If rate-limited:
- Reduce `max_tokens` in requests
- Space out requests slightly
- Check https://status.groq.com for service status

### Slow embeddings with Groq LLM

**Solution**: Set `OPENAI_API_KEY` to use OpenAI embeddings (cheaper + faster than LLM inference):
```bash
export OPENAI_API_KEY=sk_...
```

Or switch to Gemini for free embeddings:
```bash
export LLAMA_INDEX_PROVIDER=gemini
export GOOGLE_API_KEY=...
```

## Architecture

```
┌─────────────────────────────────────────┐
│   RAG Service (FastAPI)                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  LlamaIndex Settings             │  │
│  │  - LLM: Groq (Mixtral 8x7B)     │  │
│  │  - Embeddings: OpenAI (fallback) │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  RAG Engine                      │  │
│  │  - Ingest → Vector Index         │  │
│  │  - Retrieve → Hybrid (Vec+BM25)  │  │
│  │  - Query → LLM synthesis via Groq│  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  API Routes                      │  │
│  │  POST /ingest (upload documents) │  │
│  │  POST /query (RAG search)        │  │
│  │  POST /retrieve (retrieval only) │  │
│  │  GET /health (service health)    │  │
│  └──────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
              ↓
        ┌──────────────┐
        │ Groq API     │
        │ (Free tier)  │
        └──────────────┘
```

## Performance Benchmarks

Typical latencies with Groq (from official docs):

- **Mixtral 8x7B**: <100ms first token, continuous token generation
- **Llama 3 70B**: <150ms first token
- **Quality**: Excellent for exam explanation generation

## Cost Comparison

| Provider | LLM Cost | Embedding Cost | Total (1K queries) |
|----------|----------|----------------|-------------------|
| **Groq** ✨ | FREE | ~$0.02 (OpenAI) | **~$0.02/1K** |
| OpenAI | ~$0.30 | ~$0.02 | **~$0.32/1K** |
| Gemini | FREE (tier) | FREE (tier) | **~$0.00 (limits)** |

**Best for E-exam-prepare**: Groq (free LLM) + optional OpenAI embeddings (cheap)

## Resources

- **Groq Console**: https://console.groq.com
- **Groq Docs**: https://console.groq.com/docs
- **Groq Models**: https://console.groq.com/docs/models
- **LlamaIndex Groq**: https://docs.llamaindex.ai/en/stable/module_guides/models/llms/integrations/groq/
- **Discord Community**: https://discord.gg/JvNsBDKeCG

## Summary

✅ **Groq is now the default, fully integrated, and production-ready for E-exam-prepare**

- Free API key (no credit card)
- Ultra-fast inference (sub-second responses)
- Used across all RAG operations (ingest, retrieve, query)
- Fallback to OpenAI embeddings for quality
- Easy switching between providers via `LLAMA_INDEX_PROVIDER` env var
