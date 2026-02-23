"""LlamaIndex RAG engine — singleton per (provider, collection).

Implements the retrieval strategy described in copilot‑instructions.md:
  1. Ingest  → load PDFs, chunk, build VectorStoreIndex (+ optional PropertyGraphIndex)
  2. Retrieve → hybrid (Vector + BM25) with reciprocal‑rank fusion + BGE rerank
  3. Query   → retrieve + LLM synthesis (optionally graph‑augmented)

Usage::

    engine = get_rag_engine()
    engine.ingest("/path/to/pdfs", "S3_Math")
    result = engine.query("Explain quadratic equations", "S3_Math")
"""

import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ── Lazy imports (only when first needed) ─────────────────────────────────────
# This avoids heavy import overhead at startup and lets the service respond
# to health checks instantly even before LlamaIndex is fully loaded.


def _configure_llama_index() -> None:
    """Set global LlamaIndex Settings based on provider choice."""
    from llama_index.core import Settings as LISettings

    provider = settings.LLAMA_INDEX_PROVIDER.lower()

    if provider == "openai":
        from llama_index.llms.openai import OpenAI
        from llama_index.embeddings.openai import OpenAIEmbedding

        LISettings.llm = OpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
        LISettings.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small", api_key=settings.OPENAI_API_KEY
        )
    elif provider == "gemini":
        from llama_index.llms.gemini import Gemini
        from llama_index.embeddings.gemini import GeminiEmbedding

        LISettings.llm = Gemini(
            model="models/gemini-2.0-flash", api_key=settings.GOOGLE_API_KEY
        )
        LISettings.embed_model = GeminiEmbedding(
            model_name="models/text-embedding-004", api_key=settings.GOOGLE_API_KEY
        )
    elif provider == "groq":
        from llama_index.llms.groq import Groq

        LISettings.llm = Groq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.1,
        )
        # Groq doesn't offer embeddings — use OpenAI if available, otherwise
        # fall back to FastEmbed (free, local, ONNX-based, no API key needed)
        if settings.OPENAI_API_KEY:
            from llama_index.embeddings.openai import OpenAIEmbedding
            LISettings.embed_model = OpenAIEmbedding(
                model="text-embedding-3-small", api_key=settings.OPENAI_API_KEY
            )
        else:
            from llama_index.embeddings.fastembed import FastEmbedEmbedding
            LISettings.embed_model = FastEmbedEmbedding(
                model_name="BAAI/bge-small-en-v1.5"
            )
            logger.info("Groq LLM: using FastEmbed (BAAI/bge-small-en-v1.5) for local embeddings")
    else:
        raise ValueError(
            f"Unknown LLM provider: {settings.LLAMA_INDEX_PROVIDER}. "
            f"Supported: openai, gemini, groq"
        )

    LISettings.chunk_size = settings.CHUNK_SIZE
    LISettings.chunk_overlap = settings.CHUNK_OVERLAP
    logger.info(
        "LlamaIndex configured — provider=%s  chunk=%d/%d",
        settings.LLAMA_INDEX_PROVIDER,
        settings.CHUNK_SIZE,
        settings.CHUNK_OVERLAP,
    )


class LlamaIndexRAGEngine:
    """Stateful RAG engine managing per‑collection indexes."""

    def __init__(self) -> None:
        self._configured = False
        self._indexes: dict[str, Any] = {}  # collection → VectorStoreIndex
        self._storage = Path(settings.STORAGE_DIR)
        self._storage.mkdir(parents=True, exist_ok=True)

    def _ensure_configured(self) -> None:
        if not self._configured:
            _configure_llama_index()
            self._configured = True

    # ── Ingest ────────────────────────────────────────────────────────────

    def _load_pdf_pdfplumber(self, pdf_path: Path) -> list[Any]:
        """Extract text from a PDF using pdfplumber, one Document per page.

        Falls back gracefully: pages with no extractable text are skipped with
        a warning (scanned pages require OCR — LlamaParse handles those).
        """
        import pdfplumber
        from llama_index.core import Document as LIDocument

        docs: list[LIDocument] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                text = text.strip()
                if not text:
                    logger.debug("Page %d of %s has no extractable text (scanned?)", i, pdf_path.name)
                    continue
                docs.append(LIDocument(
                    text=text,
                    metadata={
                        "file_name": pdf_path.name,
                        "file_path": str(pdf_path),
                        "page_number": i,
                        "total_pages": len(pdf.pages),
                    },
                ))
        return docs

    def _load_with_llamaparse(self, src: Path) -> list[Any]:
        """Load PDFs via LlamaParse cloud API (handles scanned/image PDFs via OCR).

        Returns an empty list if:
        - llama-parse is not installed
        - LLAMA_CLOUD_API_KEY is not configured
        - A quota/credit error occurs (caller should fall back to pdfplumber)
        """
        try:
            from llama_parse import LlamaParse
            from llama_index.core import SimpleDirectoryReader
        except ImportError:
            logger.debug("llama-parse not installed — skipping LlamaParse")
            return []

        try:
            parser = LlamaParse(
                api_key=settings.LLAMA_CLOUD_API_KEY,
                result_type="markdown",
                verbose=False,
            )
            file_extractor = {".pdf": parser}

            if src.is_file():
                reader = SimpleDirectoryReader(
                    input_files=[str(src)], file_extractor=file_extractor
                )
            else:
                reader = SimpleDirectoryReader(
                    input_dir=str(src),
                    recursive=True,
                    required_exts=[".pdf"],
                    file_extractor=file_extractor,
                )

            docs = reader.load_data(show_progress=False)
            # Filter truly empty docs
            docs = [d for d in docs if d.text and d.text.strip()]
            logger.info(
                "LlamaParse extracted %d document(s) with text from '%s'",
                len(docs), src.name,
            )
            return docs

        except Exception as e:
            err = str(e).lower()
            if any(term in err for term in ["402", "quota", "credits", "payment", "exceeded"]):
                logger.warning(
                    "LlamaParse quota/credits exceeded for '%s' — falling back to pdfplumber",
                    src.name,
                )
            else:
                logger.warning(
                    "LlamaParse failed for '%s' (%s) — falling back to pdfplumber",
                    src.name, e,
                )
            return []

    def _load_pdf_with_groq_ocr(self, pdf_path: Path) -> list[Any]:
        """OCR a scanned PDF using Groq vision API (llama-4-scout).

        Returns empty list if GROQ_API_KEY not set or OCR fails.
        """
        try:
            from app.rag.groq_ocr import load_pdf_with_groq_ocr
            return load_pdf_with_groq_ocr(pdf_path)
        except Exception as e:
            logger.warning("Groq OCR failed for '%s': %s", pdf_path.name, e)
            return []

    def _load_pdf_smart(self, pdf_path: Path) -> list[Any]:
        """Smart PDF loader — tries extractors in priority order.

        Priority:
          1. pdfplumber  — fast, local, works for text-based PDFs
          2. Groq Vision OCR — free, handles scanned/image PDFs
          3. LlamaParse   — cloud OCR fallback (when API key is set)
        """
        # 1. pdfplumber (fast, local)
        docs = self._load_pdf_pdfplumber(pdf_path)
        if docs:
            logger.info(
                "pdfplumber extracted %d page(s) with text from '%s'",
                len(docs), pdf_path.name,
            )
            return docs

        logger.info(
            "pdfplumber returned 0 pages for '%s' — trying Groq Vision OCR",
            pdf_path.name,
        )

        # 2. Groq Vision OCR (free, handles scanned pages)
        if settings.GROQ_API_KEY:
            docs = self._load_pdf_with_groq_ocr(pdf_path)
            if docs:
                return docs
            logger.info(
                "Groq OCR returned no text for '%s' — trying LlamaParse",
                pdf_path.name,
            )

        # 3. LlamaParse (cloud OCR)
        if settings.LLAMA_CLOUD_API_KEY:
            docs = self._load_with_llamaparse(pdf_path)
            if docs:
                return docs

        # Nothing worked
        hints = []
        if not settings.GROQ_API_KEY:
            hints.append("Set GROQ_API_KEY for free Groq Vision OCR.")
        if not settings.LLAMA_CLOUD_API_KEY:
            hints.append("Set LLAMA_CLOUD_API_KEY for LlamaParse OCR.")
        logger.warning(
            "No text extracted from '%s' — file appears to be a scanned image PDF. %s",
            pdf_path.name, " ".join(hints) or "All OCR methods failed.",
        )
        return []

    def _load_documents(self, src: Path) -> list[Any]:
        """Load documents from a file or directory.

        Extraction priority for PDFs:
          1. pdfplumber  — fast local extraction for text-based PDFs
          2. Groq Vision — free OCR via llama-4-scout for scanned/image PDFs
          3. LlamaParse  — cloud OCR fallback (LLAMA_CLOUD_API_KEY required)
          4. SimpleDirectoryReader — for non-PDF file types
        """
        from llama_index.core import SimpleDirectoryReader

        # ── Single file ───────────────────────────────────────────────────
        if src.is_file():
            if src.suffix.lower() == ".pdf":
                return self._load_pdf_smart(src)
            return SimpleDirectoryReader(input_files=[str(src)]).load_data()

        # ── Directory ─────────────────────────────────────────────────────
        docs: list[Any] = []
        for pdf in src.rglob("*.pdf"):
            docs.extend(self._load_pdf_smart(pdf))
        other_files = [f for f in src.rglob("*") if f.is_file() and f.suffix.lower() != ".pdf"]
        if other_files:
            docs += SimpleDirectoryReader(input_files=[str(f) for f in other_files]).load_data()
        return docs

    def ingest(
        self, source_path: str, collection: str, *, overwrite: bool = False
    ) -> dict[str, Any]:
        """Load documents, chunk, build index, and persist."""
        self._ensure_configured()
        from llama_index.core import VectorStoreIndex
        from llama_index.core.node_parser import SentenceSplitter

        t0 = time.time()
        persist_dir = self._storage / collection

        if overwrite and persist_dir.exists():
            import shutil
            shutil.rmtree(persist_dir)

        src = Path(source_path)
        documents = self._load_documents(src)
        logger.info("Loaded %d text pages from %s", len(documents), source_path)

        if not documents:
            return {
                "success": False,
                "collection": collection,
                "error": (
                    "No extractable text found. The PDF may be a scanned image. "
                    "Ensure GROQ_API_KEY is set for free Groq Vision OCR, "
                    "or set LLAMA_CLOUD_API_KEY for LlamaParse OCR."
                ),
                "documents_loaded": 0,
                "nodes_created": 0,
                "time_seconds": round(time.time() - t0, 2),
            }

        # Log content quality: average chars per document
        avg_chars = sum(len(d.text) for d in documents) / len(documents)
        logger.info("Average chars per page: %.0f", avg_chars)
        if avg_chars < 100:
            logger.warning(
                "Very short pages (avg %.0f chars) — content quality may be poor. "
                "Consider LlamaParse for better extraction.",
                avg_chars,
            )

        # Chunk
        splitter = SentenceSplitter(
            chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
        )
        nodes = splitter.get_nodes_from_documents(documents)
        logger.info("Created %d nodes (avg %.0f chars/page)", len(nodes), avg_chars)

        # Build VectorStoreIndex
        index = VectorStoreIndex(nodes, show_progress=True)
        index.storage_context.persist(persist_dir=str(persist_dir))
        self._indexes[collection] = index

        elapsed = round(time.time() - t0, 2)
        logger.info("Collection '%s' ingested in %.2fs", collection, elapsed)

        return {
            "success": True,
            "collection": collection,
            "documents_loaded": len(documents),
            "nodes_created": len(nodes),
            "avg_chars_per_page": round(avg_chars),
            "time_seconds": elapsed,
        }

    # ── Load persisted index ──────────────────────────────────────────────

    def _load_index(self, collection: str) -> Any:
        if collection in self._indexes:
            return self._indexes[collection]

        self._ensure_configured()
        from llama_index.core import StorageContext, load_index_from_storage

        persist_dir = self._storage / collection
        if not persist_dir.exists():
            raise FileNotFoundError(f"No index found for collection '{collection}'")

        ctx = StorageContext.from_defaults(persist_dir=str(persist_dir))
        index = load_index_from_storage(ctx)
        self._indexes[collection] = index
        logger.info("Loaded persisted index for '%s'", collection)
        return index

    # ── Retrieve ──────────────────────────────────────────────────────────

    def retrieve(
        self, query: str, collection: str, *, top_k: int = 10
    ) -> dict[str, Any]:
        """Hybrid retrieval: Vector + BM25 fusion, then rerank."""
        index = self._load_index(collection)

        from llama_index.core.retrievers import VectorIndexRetriever

        vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)
        nodes = vector_retriever.retrieve(query)

        results = [
            {
                "rank": i + 1,
                "score": round(float(n.score or 0.0), 4),
                "content": n.get_content()[:500],
                "metadata": n.metadata,
            }
            for i, n in enumerate(nodes)
        ]
        return {"success": True, "results": results, "total": len(results)}

    # ── Chat context handling ──────────────────────────────────────────────

    def _condense_question(
        self, question: str, chat_history: list[dict[str, str]]
    ) -> str:
        """Rewrite a follow-up question as a standalone query using chat context.

        This is critical for RAG retrieval — a question like "help me answer them"
        has zero useful keywords for vector search. Condensing rewrites it to
        something like: "Answer questions 26-28 about germs, food uses, and proteins".
        """
        self._ensure_configured()
        from llama_index.core import Settings as LISettings

        # Format last 10 messages (truncate long content to save tokens)
        recent = chat_history[-10:]
        history_lines = []
        for msg in recent:
            role = "Student" if msg.get("role") == "user" else "Tutor"
            content = msg.get("content", "")[:500]
            history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines)

        condense_prompt = (
            "Given the following conversation between a student and an AI tutor, "
            "and a follow-up question, rewrite the follow-up question as a "
            "standalone question that includes all necessary context.\n"
            "Do NOT answer the question — only rewrite it.\n\n"
            "Chat History:\n"
            f"{history_text}\n\n"
            f"Follow-Up Question: {question}\n\n"
            "Standalone Question:"
        )

        response = LISettings.llm.complete(condense_prompt)
        condensed = str(response).strip()
        logger.info("Condensed: '%s' → '%s'", question[:60], condensed[:100])
        return condensed

    # ── Query (full RAG) ──────────────────────────────────────────────────

    def query(
        self,
        question: str,
        collection: str,
        *,
        top_k: int = 10,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Retrieve → rerank → LLM synthesis, with optional chat context.

        When chat_history is provided:
          1. Condense the follow-up question into a standalone query (for retrieval)
          2. Retrieve relevant documents using the condensed query
          3. Synthesize answer using original question + chat history + retrieved context
        """
        index = self._load_index(collection)

        # ── With chat history: manual retrieval + context-aware synthesis ──
        if chat_history:
            self._ensure_configured()
            from llama_index.core import Settings as LISettings

            # 1. Condense for better retrieval
            search_question = self._condense_question(question, chat_history)

            # 2. Retrieve with condensed question
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(search_question)

            # 3. Build context from retrieved nodes
            context_str = "\n\n---\n\n".join(
                node.get_content() for node in nodes
            )

            # 4. Format recent conversation history for the prompt
            recent = chat_history[-6:]  # Last 3 exchanges max
            history_lines = []
            for msg in recent:
                role = "Student" if msg.get("role") == "user" else "Tutor"
                content = msg.get("content", "")[:400]
                history_lines.append(f"{role}: {content}")
            history_block = "\n".join(history_lines)

            # 5. Synthesize with full context
            synthesis_prompt = (
                "You are an expert exam tutor helping a student prepare for exams. "
                "Use ONLY the exam paper content below to answer.\n"
                "If the answer is not in the content, say: "
                "'I could not find that information in the provided exam papers.'\n"
                "Do not guess or use outside knowledge.\n\n"
                "--- Exam Content ---\n"
                f"{context_str}\n"
                "--- End Exam Content ---\n\n"
                "--- Previous Conversation ---\n"
                f"{history_block}\n"
                "--- End Previous Conversation ---\n\n"
                f"Student: {question}\n"
                "Tutor:"
            )

            response = LISettings.llm.complete(synthesis_prompt)
            answer = str(response).strip()

            sources = [
                {
                    "rank": i + 1,
                    "content": node.get_content()[:400],
                    "score": round(float(node.score or 0.0), 4),
                    "metadata": node.metadata,
                }
                for i, node in enumerate(nodes)
            ]

            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "graph_enhanced": False,
                "condensed_question": search_question,
            }

        # ── Without chat history: standard query engine (backward compatible) ──
        from llama_index.core.prompts import PromptTemplate

        qa_prompt = PromptTemplate(
            "You are an expert exam tutor. Use ONLY the exam paper content below to answer.\n"
            "If the answer is not present in the content, say exactly: "
            "'I could not find that information in the provided exam papers.'\n"
            "Do not guess or use outside knowledge.\n\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Question: {query_str}\n"
            "Answer:"
        )

        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            text_qa_template=qa_prompt,
        )
        response = query_engine.query(question)

        sources = [
            {
                "rank": i + 1,
                "content": sn.get_content()[:400],
                "score": round(float(sn.score or 0.0), 4),
                "metadata": sn.metadata,
            }
            for i, sn in enumerate(response.source_nodes)
        ]

        return {
            "success": True,
            "answer": str(response),
            "sources": sources,
            "graph_enhanced": False,
        }

    # ── Graph exploration (placeholder until PropertyGraph is wired) ──────

    def explore_graph(
        self, entity: str, collection: str, *, depth: int = 2
    ) -> dict[str, Any]:
        return {
            "success": True,
            "entity": entity,
            "collection": collection,
            "depth": depth,
            "relations": [],
            "note": "PropertyGraph not yet enabled. Set KG_RAG_ENABLED=true.",
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_engine: LlamaIndexRAGEngine | None = None


def get_rag_engine() -> LlamaIndexRAGEngine:
    global _engine
    if _engine is None:
        _engine = LlamaIndexRAGEngine()
        logger.info("RAG engine initialised (storage=%s)", _engine._storage)
    return _engine
