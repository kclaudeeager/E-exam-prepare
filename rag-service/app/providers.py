"""Factory for initializing LLM and embedding providers."""

import logging
from typing import Union, Optional

from llama_index.core.llms import LLM
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from app.config import settings
from app.llms import GoogleGeminiLLM, GroqLLM
from app.embeddings import GeminiEmbeddingFunction

logger = logging.getLogger(__name__)


def get_llm() -> LLM:
    """
    Factory function to get LLM based on configured provider.

    Returns:
        LLM instance (OpenAI, GoogleGeminiLLM, or GroqLLM)

    Raises:
        ValueError: If provider is not supported or required credentials missing
    """
    provider = settings.LLAMA_INDEX_PROVIDER.lower()

    if provider == "openai":
        logger.info("Using OpenAI LLM (gpt-4)")
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4",
            temperature=0.1,
            max_tokens=2048,
        )

    elif provider == "gemini":
        logger.info("Using Google Gemini LLM")
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured")
        return GoogleGeminiLLM(
            api_key=settings.GOOGLE_API_KEY,
            model_name="gemini-2.0-flash",
            temperature=0.1,
            max_tokens=2048,
        )

    elif provider == "groq":
        logger.info("Using Groq LLM (free, recommended for development)")
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured. Get free key at https://console.groq.com")
        return GroqLLM(
            api_key=settings.GROQ_API_KEY,
            model_name="mixtral-8x7b-32768",  # Free model
            temperature=0.1,
            max_tokens=2048,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: openai, gemini, groq"
        )


def get_embeddings():
    """
    Factory function to get embedding provider based on configured LLM provider.

    Returns:
        Embedding instance (OpenAIEmbedding or GeminiEmbeddingFunction)

    Raises:
        ValueError: If required credentials missing
    """
    provider = settings.LLAMA_INDEX_PROVIDER.lower()

    if provider == "openai":
        logger.info("Using OpenAI Embeddings (text-embedding-3-small)")
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        return OpenAIEmbedding(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small",
        )

    elif provider == "gemini":
        logger.info("Using Google Gemini Embeddings (embedding-001)")
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured")
        return GeminiEmbeddingFunction(
            api_key=settings.GOOGLE_API_KEY,
            model_name="models/embedding-001",
        )

    elif provider == "groq":
        # Groq doesn't offer embeddings; use OpenAI or Gemini as fallback
        logger.info(
            "Groq LLM detected: Groq doesn't offer embeddings. "
            "Using OpenAI embeddings as fallback (requires OPENAI_API_KEY)."
        )
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY not configured with Groq LLM. Embeddings may not work properly. "
                "For free embeddings, set LLAMA_INDEX_PROVIDER=gemini instead."
            )
        return OpenAIEmbedding(
            api_key=settings.OPENAI_API_KEY or "",
            model="text-embedding-3-small",
        )

    else:
        raise ValueError(
            f"Unsupported embedding provider: {provider}. "
            f"Supported: openai, gemini"
        )


def print_provider_info():
    """Print information about current LLM/embedding providers."""
    provider = settings.LLAMA_INDEX_PROVIDER.lower()

    info = {
        "openai": {
            "llm": "GPT-4 (paid)",
            "embedding": "text-embedding-3-small (paid)",
            "cost": "Moderate",
            "use_case": "Production use, high quality",
        },
        "gemini": {
            "llm": "Gemini 2.0 Flash (free tier available)",
            "embedding": "Gemini Embedding 001 (free tier available)",
            "cost": "Free/Cheap",
            "use_case": "Development with free tier, good quality",
        },
        "groq": {
            "llm": "Mixtral 8x7B (completely free)",
            "embedding": "OpenAI (fallback, requires key)",
            "cost": "Free LLM only",
            "use_case": "Development/testing (RECOMMENDED)",
        },
    }

    if provider in info:
        details = info[provider]
        logger.info(
            f"\n{'='*60}\n"
            f"RAG Provider Configuration: {provider.upper()}\n"
            f"{'-'*60}\n"
            f"LLM: {details['llm']}\n"
            f"Embedding: {details['embedding']}\n"
            f"Cost: {details['cost']}\n"
            f"Use Case: {details['use_case']}\n"
            f"{'='*60}"
        )
