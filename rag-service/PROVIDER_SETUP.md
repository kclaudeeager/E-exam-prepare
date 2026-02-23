# RAG Service Provider Setup Guide

## Overview

The RAG service supports **3 LLM providers** during development:

| Provider | LLM Model | Cost | Best For |
|----------|-----------|------|----------|
| **Groq** (Recommended) | Mixtral 8x7B | **FREE** ✅ | Development & Testing |
| **Gemini** | Gemini 2.0 Flash | Free/Cheap | Development & Production |
| **OpenAI** | GPT-4 | Paid | Production Use |

---

## Quick Start: Groq (Recommended for Development)

### 1. Get Free Groq API Key
```bash
# Visit: https://console.groq.com
# Sign up (free)
# Create API key
# Copy key to .env file
```

### 2. Configure Environment
```bash
# In rag-service/.env or root .env
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### 4. Test It
```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'
```

**Cost**: **$0** - Completely free! 🎉

---

## Option 2: Google Gemini

### 1. Get Free Google API Key
```bash
# Visit: https://aistudio.google.com/app/apikey
# Click "Create API Key"
# Select/create a project
# Copy key to .env file
```

### 2. Configure Environment
```bash
# In rag-service/.env
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_google_api_key_here
```

### 3. Features
- ✅ Free tier available (high limits)
- ✅ Custom embedding function included
- ✅ High-quality Gemini LLM
- ✅ Good for production use

### 4. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

**Cost**: **$0-25/month** - Free tier very generous

---

## Option 3: OpenAI

### 1. Get OpenAI API Key
```bash
# Visit: https://platform.openai.com/api/keys
# Create new secret key
# Add credit card for billing
# Copy key to .env file
```

### 2. Configure Environment
```bash
# In rag-service/.env
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk-your_openai_key_here
```

### 3. Features
- ✅ GPT-4 access (highest quality)
- ✅ Best for production
- ⚠️ Paid service (pay-as-you-go)

### 4. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

**Cost**: **$0.03 per 1K input tokens, $0.06 per 1K output tokens**

---

## Architecture: Custom LLM/Embedding Wrappers

### 1. Google Gemini LLM (`app/llms/gemini_llm.py`)
```python
from app.llms import GoogleGeminiLLM

llm = GoogleGeminiLLM(
    api_key="your_key",
    model_name="gemini-2.0-flash",
    temperature=0.1,
    max_tokens=2048
)

# Use in queries
response = llm.chat(messages)
```

**Features**:
- Thread-local client storage (multiprocessing safe)
- Automatic retry with exponential backoff
- System prompt support
- Streaming & non-streaming modes
- Async support

---

### 2. Groq LLM (`app/llms/groq_llm.py`)
```python
from app.llms import GroqLLM

llm = GroqLLM(
    api_key="your_key",
    model_name="mixtral-8x7b-32768",  # Free model
    temperature=0.1,
    max_tokens=2048
)

# Use in queries
response = llm.chat(messages)
```

**Features**:
- Fast inference (Groq is optimized for speed)
- Completely free (development phase)
- Full streaming support
- Error handling for rate limits
- Async support

---

### 3. Gemini Embeddings (`app/embeddings/gemini_embedding.py`)
```python
from app.embeddings import GeminiEmbeddingFunction

embeddings = GeminiEmbeddingFunction(
    api_key="your_key",
    model_name="models/embedding-001"
)

# Use in RAG
vectors = embeddings(["text1", "text2"])
```

**Features**:
- Custom ChromaDB embedding function
- Batch embedding support
- Error handling & logging

---

## Configuration via `.env`

### Example: Groq (Recommended)
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

### Example: Gemini
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
```

### Example: OpenAI
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk_your_key_here
```

---

## Usage in RAG Service

### 1. Automatic Provider Detection
The RAG engine automatically loads the correct provider from config:

```python
# app/providers.py
from app.providers import get_llm, get_embeddings

llm = get_llm()  # Returns GroqLLM, GoogleGeminiLLM, or OpenAI
embeddings = get_embeddings()  # Returns matching embeddings
```

### 2. Query with Selected Provider
```bash
# Sends query to whichever provider is configured
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is machine learning?",
    "top_k": 5
  }'
```

### 3. Retrieve with Selected Provider
```bash
# Uses vector store with embeddings from configured provider
curl -X GET http://localhost:8001/rag/retrieve?query=ML
```

---

## API Endpoints

All RAG endpoints work with any configured provider:

### `/rag/ingest` — Load Documents
```bash
curl -X POST http://localhost:8001/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_path": "./documents", "overwrite": false}'
```

### `/rag/retrieve` — Retrieve Chunks
```bash
curl -X GET "http://localhost:8001/rag/retrieve?query=exam&top_k=5"
```

### `/rag/query` — Full RAG with LLM Synthesis
```bash
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What topics are in the math exam?"}'
```

---

## Recommended Setup for Development

### Phase 1: Free Development (Groq)
```bash
# Cost: $0/month
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_free_key
```

### Phase 2: Free with Gemini (Optional)
```bash
# Cost: $0/month (generous free tier)
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_free_key
```

### Phase 3: Production (Your Choice)
- Stick with **Groq** (still free for production)
- Upgrade to **Gemini** (free/cheap tier)
- Switch to **OpenAI** (best quality, requires payment)

---

## Switching Providers at Runtime

Edit `.env` and restart service:
```bash
# Update .env
LLAMA_INDEX_PROVIDER=gemini

# Restart
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

No code changes needed! 🎉

---

## Cost Comparison

| Scenario | Groq | Gemini | OpenAI |
|----------|------|--------|--------|
| **1M questions/month** | $0 | $0-10 | $50-150 |
| **10M questions/month** | $0 | $10-50 | $500-1500 |
| **Production Quality** | ✅ Good | ✅ Excellent | ✅ Best |
| **Recommended For** | Dev/Test | Dev/Prod | Prod Only |

---

## Troubleshooting

### "GROQ_API_KEY not configured"
```bash
# Solution: Add to .env
GROQ_API_KEY=your_key_from_console.groq.com
```

### "GOOGLE_API_KEY not configured"
```bash
# Solution: Add to .env
GOOGLE_API_KEY=your_key_from_aistudio.google.com
```

### "OPENAI_API_KEY not configured"
```bash
# Solution: Add to .env
OPENAI_API_KEY=sk_your_key_from_platform.openai.com
```

### Slow responses from Groq
- Groq is optimized for speed but free tier has rate limits
- Reduce `SIMILARITY_TOP_K` in config if too slow
- Consider upgrading to Gemini or OpenAI

### High API costs on OpenAI
- Switch to Groq or Gemini
- Reduce `SIMILARITY_TOP_K` to retrieve fewer chunks
- Use streaming responses to catch errors early

---

## Next Steps

1. **Get Free Key**: Choose Groq, Gemini, or OpenAI
2. **Add to .env**: `LLAMA_INDEX_PROVIDER=groq` + API key
3. **Start RAG Service**: `cd rag-service && uv run uvicorn app.main:app --reload --port 8001`
4. **Test Query**: Use curl to query RAG service
5. **Upload Documents**: Use `/rag/ingest` to load PDFs
6. **Switch Anytime**: Edit `.env` to try different providers

---

**Recommendation**: Start with **Groq** for completely free development! 🚀
