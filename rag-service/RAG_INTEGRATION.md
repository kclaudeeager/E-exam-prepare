# RAG Service Integration Guide for Frontend

## Quick Setup

### 1. Start RAG Service
```bash
cd rag-service
uv run uvicorn app.main:app --reload --port 8001
```

### 2. Configure Provider (`.env`)
```bash
# Recommended: Free Groq (development)
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=your_key_from_console.groq.com

# Or: Free Gemini (development)
LLAMA_INDEX_PROVIDER=gemini
GOOGLE_API_KEY=your_key_from_aistudio.google.com

# Or: OpenAI (production)
LLAMA_INDEX_PROVIDER=openai
OPENAI_API_KEY=sk_your_key
```

### 3. Frontend Integration
```typescript
// Use RAG service for "Show Solution" explanations
const { data: explanation } = useSWR(
  `/api/rag/query?question=${question}`,
  fetcher
);
```

---

## Available RAG Endpoints

### 1. Query (Full RAG with Answer Synthesis)
```bash
POST /rag/query
Content-Type: application/json

{
  "question": "What topics are covered in this exam?",
  "top_k": 5
}

Response:
{
  "answer": "This exam covers...",
  "sources": [
    {
      "score": 0.95,
      "content": "Relevant chunk from document...",
      "metadata": {...}
    }
  ],
  "graph_enhanced": true
}
```

### 2. Retrieve (Get Relevant Chunks Only)
```bash
GET /rag/retrieve?query=mathematics&top_k=5

Response:
{
  "results": [
    {
      "rank": 1,
      "score": 0.95,
      "content": "Chunk content...",
      "metadata": {...}
    }
  ]
}
```

### 3. Ingest (Load Documents)
```bash
POST /rag/ingest
Content-Type: application/json

{
  "source_path": "./documents",
  "overwrite": false
}

Response:
{
  "success": true,
  "documents_loaded": 25,
  "nodes_created": 150,
  "time_seconds": 8.5
}
```

---

## How It Works

### Quiz Generation + RAG
```
1. User clicks "Show Solution" on failed question
   ↓
2. Frontend calls: GET /api/rag/query?question={question_text}
   ↓
3. RAG Service:
   a. Retrieves top 5 relevant chunks from vector store
   b. Reranks with BGE model
   c. Sends to LLM (Groq/Gemini/OpenAI)
   d. LLM synthesizes answer with citations
   ↓
4. Frontend displays explanation with sources
```

### Document Upload + Indexing
```
1. Admin uploads PDF → Backend receives
   ↓
2. Backend calls: POST /rag/ingest
   ↓
3. RAG Service:
   a. Parses PDF (LlamaParse or pdfplumber)
   b. Chunks document (1024 tokens, 100 overlap)
   c. Embeds with Gemini/OpenAI/Groq
   d. Stores in vector DB (Chroma)
   e. Builds optional PropertyGraph
   ↓
4. Document ready for queries
```

---

## Provider Comparison for Frontend

| Provider | Cost | Quality | Speed | Best For |
|----------|------|---------|-------|----------|
| **Groq** | Free | Good | Very Fast | Development ✅ |
| **Gemini** | Free/Cheap | Excellent | Fast | Production |
| **OpenAI** | Paid | Best | Medium | High-accuracy use |

---

## Example: Student Views Failed Question Solution

### Frontend Code
```typescript
// student/attempts/[id]/page.tsx
const [solution, setSolution] = useState<string>("");
const [loading, setLoading] = useState(false);

async function showSolution(question: string) {
  setLoading(true);
  try {
    const response = await apiClient.post("/rag/query", {
      question: question,
      top_k: 5
    });
    setSolution(response.data.answer);
  } catch (error) {
    console.error("Failed to get explanation:", error);
  } finally {
    setLoading(false);
  }
}

return (
  <div>
    <button onClick={() => showSolution(question)}>Show Solution</button>
    {loading && <Spinner />}
    {solution && (
      <div className="solution">
        <p>{solution}</p>
        <p className="sources">Sources from exam documents provided</p>
      </div>
    )}
  </div>
);
```

### Backend (Already Implemented)
```python
# backend/app/routes/quiz.py
@router.post("/attempts/")
async def submit_attempt(
    attempt: AttemptSubmit,
    current_user: User = Depends(get_current_user),
    rag_client: RAGClient = Depends(get_rag_client),
):
    # Grade answers
    # Calculate scores
    # Update progress
    # Ready to provide explanations via RAG
    return attempt_with_scores
```

---

## Environment Variables Needed

### For Development (Groq - FREE)
```bash
# rag-service/.env
LLAMA_INDEX_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Optional for embeddings
OPENAI_API_KEY=  # Leave empty if using Groq
GOOGLE_API_KEY=  # Leave empty if using Groq
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
│   ├── llms/
│   │   ├── gemini_llm.py    # Custom Gemini LLM
│   │   └── groq_llm.py      # Custom Groq LLM (FREE!)
│   ├── embeddings/
│   │   └── gemini_embedding.py  # Custom Gemini embeddings
│   ├── config.py            # Provider configuration
│   ├── providers.py         # Factory for LLM/embeddings
│   └── routes/
│       ├── ingest.py        # Document loading
│       ├── retrieve.py      # Chunk retrieval
│       └── query.py         # Full RAG queries
├── PROVIDER_SETUP.md        # Detailed setup guide
└── pyproject.toml           # Dependencies
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
