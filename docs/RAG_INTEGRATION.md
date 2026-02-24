# RAG Service Integration Guide for Frontend

## Quick Setup

### 1. Start All Services (Docker)
```bash
# Recommended: all 6 services at once
make docker-up
```

### 2. Configure Provider (root `.env`)
```bash
# Required: Free Groq (development)
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=your_key_from_console.groq.com

# Embeddings: FastEmbed (free, local ONNX) is the default
# No API key needed for embeddings!
```

### 3. Frontend Integration
```typescript
// Ask AI: chat with exam papers via RAG
const response = await ragAPI.query({
  question: "What topics are covered?",
  collection: "P6_Social_studies",
  chat_history: previousMessages
});
```

---

## Available RAG Endpoints

All endpoints use per-collection indexes. Collections are named `{level}_{subject}` (e.g., `P6_Social_studies`, `S6_Physics`).

### 1. Query (Full RAG with Answer Synthesis)
```bash
POST /query/
Content-Type: application/json

{
  "question": "What topics are covered in this exam?",
  "collection": "P6_Social_studies",
  "top_k": 10,
  "chat_history": []   // optional, for follow-up questions
}

Response:
{
  "answer": "This exam covers...",
  "sources": [
    {
      "score": 0.65,
      "content": "Relevant chunk from document...",
      "metadata": {...}
    }
  ]
}
```

**Two code paths in the engine:**
- **Without chat_history**: Detects vague queries and expands them with collection context. Uses "overview" prompt for vague questions, "strict" prompt for specific ones.
- **With chat_history**: Condenses follow-up into standalone question with collection context, then retrieves and synthesizes.

### 2. Retrieve (Get Relevant Chunks Only)
```bash
GET /retrieve/?query=mathematics&collection=P6_Mathematics&top_k=10

Response:
{
  "results": [
    {
      "rank": 1,
      "score": 0.65,
      "content": "Chunk content...",
      "metadata": {...}
    }
  ]
}
```

### 3. Ingest (Load Documents into Collection)
```bash
POST /ingest/
Content-Type: application/json

{
  "source_path": "/app/uploads/document.pdf",
  "collection": "P6_Social_studies",
  "overwrite": false
}

Response:
{
  "success": true,
  "documents_loaded": 5,
  "nodes_created": 42,
  "time_seconds": 12.3
}
```

### 4. Collections (List Available)
```bash
GET /collections/

Response:
{
  "collections": ["P6_Mathematics", "P6_Social_studies", "S6_Physics"]
}
```

### 5. Health Check
```bash
GET /health

Response: { "status": "healthy" }
```

---

## How It Works

### Ask AI — Chat with Exam Papers
```
1. Student opens Ask AI, selects a collection (e.g., P6_Social_studies)
   ↓
2. First question (no chat history):
   a. Engine detects if query is vague (≤5 words or pattern match)
   b. If vague: expands with collection context for better retrieval
   c. Retrieves top-k chunks from per-collection VectorStoreIndex
   d. Logs retrieval scores (min/max/avg) for debugging
   e. Synthesizes with overview prompt (vague) or strict prompt (specific)
   ↓
3. Follow-up questions (with chat history):
   a. Condenses follow-up into standalone question with collection context
   b. Filters failed assistant responses from history
   c. Retrieves with condensed question
   d. Synthesizes with conversation history block
   ↓
4. Frontend displays answer with source citations
```

### Document Upload + Indexing
```
1. Admin uploads PDF → Backend saves to backend_uploads volume
   ↓
2. Backend queues Celery task: ingest_document(doc_id, file_path)
   ↓
3. Celery worker calls RAG service POST /ingest/
   ↓
4. RAG Engine:
   a. Loads PDF pages
   b. For scanned pages: Groq Vision OCR (llama-4-scout-17b-16e-instruct)
   c. SentenceSplitter chunks (1024 tokens, 100 overlap)
   d. Embeds with FastEmbed (BAAI/bge-small-en-v1.5, local ONNX)
   e. Builds VectorStoreIndex (LlamaIndex, persisted to disk)
   f. Saves index at storage/{collection}/
   ↓
5. Document status: PENDING → INGESTING → COMPLETED
```

---

## Provider Comparison for Frontend

| Provider | Cost | Quality | Speed | Best For |
|----------|------|---------|-------|----------|
| **Groq** | Free | Good | Very Fast | Development ✅ |
| **Gemini** | Free/Cheap | Excellent | Fast | Production |
| **OpenAI** | Paid | Best | Medium | High-accuracy use |

---

## Example: Ask AI — Chat with Exam Papers

### Frontend Code
```typescript
// student/ask-ai/page.tsx
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [collection, setCollection] = useState<string>("");
const [loading, setLoading] = useState(false);

async function sendMessage(question: string) {
  setLoading(true);
  try {
    // Build chat history from previous messages
    const chatHistory = messages.map(m => ({
      role: m.role,
      content: m.content
    }));
    
    const response = await ragAPI.query({
      question,
      collection,
      top_k: 10,
      chat_history: chatHistory
    });
    
    setMessages(prev => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: response.answer }
    ]);
  } catch (error) {
    console.error("Failed to get answer:", error);
  } finally {
    setLoading(false);
  }
}
```

---

## Environment Variables Needed

### For Development (Groq + FastEmbed — FREE)
```bash
# Root .env (used by Docker Compose)
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Embeddings: FastEmbed (BAAI/bge-small-en-v1.5) is used by default
# No API key needed for embeddings!

# Optional: Use OpenAI embeddings instead of FastEmbed
# OPENAI_API_KEY=sk_...
```

### For Gemini (Optional)
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_key_from_aistudio.google.com
OPENAI_API_KEY=  # Leave empty
GROQ_API_KEY=    # Leave empty
```

### For OpenAI (Production)
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk_your_key_here
GOOGLE_API_KEY=   # Leave empty
GROQ_API_KEY=     # Leave empty
```

---

## Troubleshooting

### "Failed to generate embeddings"
- Check API key is correct
- Ensure provider is configured in `.env`
- Restart RAG service: `uv run uvicorn app.main:app --reload --port 8001`

### "RAG service not responding"
```bash
# Check if running
curl http://localhost:8001/health

# Restart if down
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### Slow response times
- Increase `SIMILARITY_TOP_K` in `config.py` (default 10)
- Or switch provider (Groq is fastest)

### Rate limiting on free tier
- Groq free tier: Fast but has rate limits
- Gemini free tier: Very generous limits
- Consider upgrading to paid tier if needed

---

## File Locations

```
rag-service/
├── app/
│   ├── rag/
│   │   └── engine.py         # LlamaIndexRAGEngine (core RAG logic)
│   ├── llms/
│   │   ├── gemini_llm.py     # Custom Gemini LLM
│   │   └── groq_llm.py       # Custom Groq LLM
│   ├── embeddings/
│   │   └── gemini_embedding.py  # Custom Gemini embeddings
│   ├── config.py             # Provider configuration
│   ├── providers.py          # Factory for LLM/embeddings
│   └── routes/
│       ├── ingest.py         # Document loading (POST /ingest/)
│       ├── retrieve.py       # Chunk retrieval (GET /retrieve/)
│       ├── query.py          # Full RAG queries (POST /query/)
│       └── collections.py    # List collections (GET /collections/)
├── storage/                  # Persisted per-collection VectorStoreIndex data
│   ├── P6_Mathematics/
│   ├── P6_Social_studies/
│   └── S6_Physics/
└── pyproject.toml            # Dependencies
```

---

## Next Steps

1. **Set up RAG Service**
   - Get free Groq key from console.groq.com
   - Add to .env: `GROQ_API_KEY=...`
   - Start service: `uv run uvicorn app.main:app --reload --port 8001`

2. **Test RAG**
   - Upload test PDF via admin page
   - Take a quiz
   - Click "Show Solution" to trigger RAG

3. **Monitor**
   - Check RAG logs for errors
   - Monitor API response times
   - Track token usage (free with Groq!)

---

**Pro Tip**: Use Groq during development for completely free RAG! 🚀
